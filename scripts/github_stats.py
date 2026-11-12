#!/usr/bin/env python3
"""
Generate the GitHub cards for the profile README as static, animated SVGs,
straight from the GitHub GraphQL API instead of shared third-party card
services that are often rate-limited or down.

Outputs (in --out):
  gh-stats.svg        contributions, commits, PRs, repositories, stars, followers
  gh-top-langs.svg    languages by code size across owned, non-fork repositories
  gh-contrib.svg      contribution calendar for the last 12 months, with streaks
  data/gh_stats.json  cached numbers, reused when the API can't be reached

Public and private work are combined:
  - Languages and repository counts include private repositories when the
    token can list them, which needs a classic PAT with the `repo` scope.
  - Private contributions arrive as anonymous daily counts.
Only totals are written out. Private repository names never appear in the
SVGs or in the cached JSON, which is published to a public branch.

Standard library only. Run:
  GH_TOKEN=xxx python3 scripts/github_stats.py --user thehav0k --out dist --prev prev
"""

import argparse
import html
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

from icons import icon

API = "https://api.github.com/graphql"
UA = "profile-readme-stats-script"

BG, GRID = "#1a1b27", "#2a2e42"
TEXT, MUTED = "#c0caf5", "#737aa2"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"

STATS_ACCENT = ("#70a5fd", "#38bdae")
LANGS_ACCENT = ("#bf91f3", "#f7768e")
CONTRIB_ACCENT = ("#70a5fd", "#bf91f3")

# Heat-map shades from no contributions to the busiest quartile, in the
# same blue family as the contribution snake.
LEVELS = {
    "NONE": "#232739",
    "FIRST_QUARTILE": "#2e4580",
    "SECOND_QUARTILE": "#4064b3",
    "THIRD_QUARTILE": "#5888e6",
    "FOURTH_QUARTILE": "#8fb8ff",
}

HIDE_LANGS = {"HTML", "CSS"}
SHOWN_LANGS = 10          # legend slots; the last one becomes "Other" if needed
OTHER_COLOR = "#565f89"
FALLBACK_PALETTE = ["#70a5fd", "#bf91f3", "#38bdae", "#e0af68", "#f7768e", "#7aa2f7"]

CSS = """
.fade{opacity:0;animation:fade .8s ease-out forwards}
.rise{opacity:0;animation:rise .8s ease-out forwards}
.grow{transform-box:fill-box;transform-origin:left center;transform:scaleX(0);
animation:grow 1.4s cubic-bezier(.45,.05,.35,1) forwards}
.pulse{transform-box:fill-box;transform-origin:center;opacity:0;animation:pulse 2.2s ease-out 2s infinite}
@keyframes fade{to{opacity:1}}
@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes grow{to{transform:scaleX(1)}}
@keyframes pulse{0%{opacity:.9;transform:scale(1)}100%{opacity:0;transform:scale(2.2)}}
"""


# ── GitHub API ───────────────────────────────────────────────────────────────
def gql(query, variables, token):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": UA,
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    if "errors" in out and not out.get("data"):
        raise RuntimeError(out["errors"])
    return out["data"]


REPOS_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    name
    createdAt
    followers { totalCount }
    repositories(first: 100, after: $cursor, ownerAffiliations: [OWNER], isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        isPrivate
        stargazerCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}"""

# One calendar year per request: the API refuses ranges longer than a year.
YEAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""

# The rolling last-12-months calendar GitHub shows on the profile.
CALENDAR_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      restrictedContributionsCount
      commitContributionsByRepository(maxRepositories: 100) {
        repository { isPrivate } contributions { totalCount }
      }
      pullRequestContributionsByRepository(maxRepositories: 100) {
        repository { isPrivate } contributions { totalCount }
      }
      issueContributionsByRepository(maxRepositories: 100) {
        repository { isPrivate } contributions { totalCount }
      }
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
  }
}"""


def streaks(days):
    """Current and longest run of days with at least one contribution.
    Today doesn't break the current streak until it's over."""
    if not days:
        return 0, 0
    keys = sorted(days)
    first, last = date.fromisoformat(keys[0]), date.fromisoformat(keys[-1])
    longest = run = 0
    d = first
    while d <= last:
        run = run + 1 if days.get(d.isoformat(), 0) > 0 else 0
        longest = max(longest, run)
        d += timedelta(days=1)
    current, d = 0, last
    if days.get(d.isoformat(), 0) == 0:
        d -= timedelta(days=1)
    while days.get(d.isoformat(), 0) > 0:
        current += 1
        d -= timedelta(days=1)
    return current, longest


def fetch(username, token):
    profile, repos, cursor = None, [], None
    while True:
        user = gql(REPOS_QUERY, {"login": username, "cursor": cursor}, token)["user"]
        if user is None:
            raise RuntimeError(f"no such user: {username}")
        profile = profile or user
        page = user["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    lang_bytes, lang_colors = {}, {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            lang_bytes[name] = lang_bytes.get(name, 0) + edge["size"]
            if edge["node"]["color"]:
                lang_colors[name] = edge["node"]["color"]

    # All-time totals and a per-day map (for streaks), one year at a time
    created = datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    commits = prs = issues = contributions = 0
    days = {}
    for year in range(created.year, now.year + 1):
        frm = max(created, datetime(year, 1, 1, tzinfo=timezone.utc))
        to = min(now, datetime(year + 1, 1, 1, tzinfo=timezone.utc))
        if frm >= to:
            continue
        cc = gql(YEAR_QUERY, {
            "login": username,
            "from": frm.isoformat().replace("+00:00", "Z"),
            "to": to.isoformat().replace("+00:00", "Z"),
        }, token)["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"]
        prs += cc["totalPullRequestContributions"]
        issues += cc["totalIssueContributions"]
        contributions += cc["contributionCalendar"]["totalContributions"]
        # Windows split at UTC midnight while dates are local, so a boundary
        # day can show up in two windows with part of its count in each.
        for week in cc["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                days[day["date"]] = days.get(day["date"], 0) + day["contributionCount"]

    cal = gql(CALENDAR_QUERY, {"login": username}, token)["user"]["contributionsCollection"]
    calendar = [[day["date"], day["weekday"], day["contributionCount"], day["contributionLevel"]]
                for week in cal["contributionCalendar"]["weeks"] for day in week["contributionDays"]]
    # Private work is reported either as anonymous "restricted" contributions
    # or, when the token can read the repo, under that private repository.
    year_private = cal["restrictedContributionsCount"] + sum(
        r["contributions"]["totalCount"]
        for kind in ("commit", "pullRequest", "issue")
        for r in cal[f"{kind}ContributionsByRepository"] if r["repository"]["isPrivate"])
    current, longest = streaks(days)

    return {
        "name": profile["name"] or username,
        "since": created.year,
        "followers": profile["followers"]["totalCount"],
        "repos": len(repos),
        "private_repos": sum(1 for r in repos if r["isPrivate"]),
        "stars": sum(r["stargazerCount"] for r in repos),
        "commits": commits,
        "prs": prs,
        "issues": issues,
        "contributions": contributions,
        "languages": lang_bytes,
        "lang_colors": lang_colors,
        "calendar": calendar,
        "year_total": cal["contributionCalendar"]["totalContributions"],
        "year_private": year_private,
        "streak_current": current,
        "streak_longest": longest,
    }


# ── Shared card chrome ───────────────────────────────────────────────────────
def card_open(uid, w, h, accent, glyph, title, subtitle, aria):
    esc = html.escape
    a1, a2 = accent
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{esc(aria)}">',
            f"<title>{esc(aria)}</title>",
            f"<style>{CSS}</style>",
            "<defs>",
            f'<linearGradient id="{uid}l" x1="0" x2="1"><stop offset="0" stop-color="{a1}"/>'
            f'<stop offset="1" stop-color="{a2}"/></linearGradient>',
            f'<clipPath id="{uid}c"><rect width="{w}" height="{h}" rx="12"/></clipPath>',
            "</defs>",
            f'<g clip-path="url(#{uid}c)"><rect width="{w}" height="{h}" fill="{BG}"/>',
            f'<rect width="{w}" height="3" fill="url(#{uid}l)"/>',
            f'<g class="rise">{icon(glyph, 20, 21, 26, a1)}'
            f'<text x="58" y="36" fill="{TEXT}" font-family="{FONT}" font-size="17" '
            f'font-weight="700">{esc(title)}</text>'
            f'<text x="58" y="54" fill="{MUTED}" font-family="{FONT}" font-size="11.5">{esc(subtitle)}</text></g>']


# ── Stats card ───────────────────────────────────────────────────────────────
def render_stats(username, d, w=480, h=220):
    esc = html.escape
    a1 = STATS_ACCENT[0]
    repos = d.get("repos", d.get("public_repos", 0))
    private = d.get("private_repos", 0)
    rows = [
        ("activity", "Contributions", d.get("contributions", 0)),
        ("commit", "Commits", d.get("commits", 0)),
        ("pull", "Pull Requests", d.get("prs", 0)),
        ("repo", f"Repositories ({private} private)" if private else "Repositories", repos),
        ("star", "Stars", d.get("stars", 0)),
        ("team", "Followers", d.get("followers", 0)),
    ]
    sub = f"@{username} · public + private"
    if d.get("since"):
        sub += f" · since {d['since']}"
    out = card_open("gs", w, h, STATS_ACCENT, "chart", "GitHub Stats", sub, f"GitHub stats for {username}")

    col_w = (w - 40) / 2
    for i, (glyph, label, value) in enumerate(rows):
        cx = 20 + (i % 2) * col_w
        cy = 100 + (i // 2) * 42
        out.append(f'<g class="rise" style="animation-delay:{0.15 + i * 0.08:.2f}s">'
                   f'{icon(glyph, cx, cy - 15, 20, a1)}'
                   f'<text x="{cx+32}" y="{cy-1}" fill="{TEXT}" font-family="{FONT}" font-size="17" '
                   f'font-weight="800">{value:,}</text>'
                   f'<text x="{cx+32}" y="{cy+14}" fill="{MUTED}" font-family="{FONT}" '
                   f'font-size="10.5">{esc(label)}</text></g>')
    out.append("</g></svg>")
    return "\n".join(out)


# ── Languages card ───────────────────────────────────────────────────────────
def render_top_langs(username, d, w=480, h=220):
    esc = html.escape
    langs = d.get("languages") or {}
    colors = d.get("lang_colors") or {}
    items = sorted(((n, b) for n, b in langs.items() if n not in HIDE_LANGS), key=lambda x: -x[1])
    total = sum(b for _, b in items) or 1
    if len(items) > SHOWN_LANGS:
        items = items[:SHOWN_LANGS - 1] + [("Other", sum(b for _, b in items[SHOWN_LANGS - 1:]))]

    def color(i, name):
        if name == "Other":
            return OTHER_COLOR
        return colors.get(name) or FALLBACK_PALETTE[i % len(FALLBACK_PALETTE)]

    repos = d.get("repos", d.get("public_repos", 0))
    private = d.get("private_repos", 0)
    sub = f"@{username} · {repos} repos" + (" incl. private" if private else "") + " · by code size"
    out = card_open("gl", w, h, LANGS_ACCENT, "code", "Languages", sub, f"Most used languages for {username}")

    if not items:
        out.append(f'<text class="fade" x="{w/2}" y="{h/2+20}" text-anchor="middle" fill="{MUTED}" '
                   f'font-family="{FONT}" font-size="13">No language data yet</text></g></svg>')
        return "\n".join(out)

    # One stacked bar for the whole mix
    bx, by, bw, bh = 20, 74, w - 40, 10
    out.append(f'<clipPath id="glb"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="5"/></clipPath>')
    out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="5" fill="{GRID}"/>')
    out.append(f'<g clip-path="url(#glb)"><g class="grow" style="animation-delay:.2s">')
    x = bx
    for i, (name, size) in enumerate(items):
        seg = bw * size / total
        out.append(f'<rect x="{x:.2f}" y="{by}" width="{seg + 0.6:.2f}" height="{bh}" fill="{color(i, name)}"/>')
        x += seg
    out.append("</g></g>")

    # Two-column legend, filled top to bottom
    per_col = (len(items) + 1) // 2
    col_w = (w - 40) / 2
    for i, (name, size) in enumerate(items):
        cx = 20 + (i // per_col) * col_w
        cy = 112 + (i % per_col) * 21
        out.append(f'<g class="rise" style="animation-delay:{0.3 + i * 0.06:.2f}s">'
                   f'<circle cx="{cx+5}" cy="{cy-4}" r="4.5" fill="{color(i, name)}"/>'
                   f'<text x="{cx+17}" y="{cy}" fill="{TEXT}" font-family="{FONT}" '
                   f'font-size="12.5">{esc(name)}</text>'
                   f'<text x="{cx+col_w-24}" y="{cy}" text-anchor="end" fill="{MUTED}" '
                   f'font-family="{FONT}" font-size="11.5">{size / total * 100:.1f}%</text></g>')
    out.append("</g></svg>")
    return "\n".join(out)


# ── Contribution calendar card ───────────────────────────────────────────────
def render_contrib(username, d, w=880, h=250):
    esc = html.escape
    a1, a2 = CONTRIB_ACCENT
    cal = d.get("calendar") or []
    out = card_open("gc", w, h, CONTRIB_ACCENT, "calendar", "Contributions",
                    f"@{username} · public + private · last 12 months",
                    f"Contribution calendar for {username}")

    if not cal:
        out.append(f'<text class="fade" x="{w/2}" y="{h/2+20}" text-anchor="middle" fill="{MUTED}" '
                   f'font-family="{FONT}" font-size="13">No contribution data yet</text></g></svg>')
        return "\n".join(out)

    total, private = d.get("year_total", 0), d.get("year_private", 0)
    out.append(f'<g class="rise" style="animation-delay:.2s" font-family="{FONT}" text-anchor="end">'
               f'<text x="{w-20}" y="40" fill="{a1}" font-size="26" font-weight="800">{total:,}</text>'
               f'<text x="{w-20}" y="58" fill="{MUTED}" font-size="11.5">contributions'
               + (f' · <tspan fill="{a2}" font-weight="700">{private:,}</tspan> in private repos'
                  if private else "")
               + "</text></g>")

    # Columns are weeks starting on Sunday, like the profile graph
    weeks = []
    for day in cal:
        if not weeks or day[1] == 0:
            weeks.append([])
        weeks[-1].append(day)

    gx0, gy0 = 56, 98
    pitch = min(15.0, (w - gx0 - 20) / len(weeks))
    cell = pitch - 3
    gx0 += ((w - gx0 - 20) - pitch * len(weeks) + 3) / 2

    # Month labels, at the first column that starts in a new month
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    labels, last_month, last_col = [], None, -9
    for i, week in enumerate(weeks):
        m = int(week[0][0][5:7])
        if m != last_month:
            if i - last_col >= 3 and not (i == 0 and len(week) < 7 and week[0][0][8:] > "24"):
                labels.append((i, months[m - 1]))
                last_col = i
            last_month = m
    g = [f'<g class="fade" style="animation-delay:.1s" font-family="{FONT}" font-size="10.5" fill="{MUTED}">']
    for i, name in labels:
        g.append(f'<text x="{gx0 + i * pitch:.1f}" y="{gy0 - 8}">{name}</text>')
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        g.append(f'<text x="{gx0 - 8:.1f}" y="{gy0 + row * pitch + cell - 2:.1f}" text-anchor="end">{name}</text>')
    g.append("</g>")
    out.extend(g)

    # Cells, revealed one week at a time
    today = cal[-1]
    for i, week in enumerate(weeks):
        x = gx0 + i * pitch
        cells = []
        for day_str, weekday, count, level in week:
            cells.append(f'<rect x="{x:.1f}" y="{gy0 + weekday * pitch:.1f}" width="{cell:.1f}" '
                         f'height="{cell:.1f}" rx="2.5" fill="{LEVELS.get(level, LEVELS["NONE"])}"/>')
        out.append(f'<g class="fade" style="animation-delay:{0.2 + i * 0.02:.2f}s">{"".join(cells)}</g>')
    tx = gx0 + (len(weeks) - 1) * pitch
    ty = gy0 + today[1] * pitch
    out.append(f'<rect class="pulse" x="{tx:.1f}" y="{ty:.1f}" width="{cell:.1f}" height="{cell:.1f}" '
               f'rx="2.5" fill="none" stroke="{a2}" stroke-width="1.5"/>')

    # Footer: streaks and best day on the left, legend on the right
    best = max(cal, key=lambda c: (c[2], c[0]))
    best_date = date.fromisoformat(best[0])
    stats = [
        ("Current streak", f"{d.get('streak_current', 0)} day" + ("" if d.get("streak_current") == 1 else "s")),
        ("Longest streak", f"{d.get('streak_longest', 0)} days"),
        ("Best day", f"{best[2]} on {best_date.day} {months[best_date.month - 1]}"),
        ("All time", f"{d.get('contributions', 0):,}"),
    ]
    fy = h - 22
    parts = []
    for j, (label, value) in enumerate(stats):
        if j:
            parts.append(f'<tspan fill="{GRID}">   │   </tspan>')
        parts.append(f'<tspan>{esc(label)} </tspan><tspan fill="{TEXT}" font-weight="700">{esc(value)}</tspan>')
    out.append(f'<text class="rise" style="animation-delay:1.3s" x="20" y="{fy}" fill="{MUTED}" '
               f'font-family="{FONT}" font-size="11.5" xml:space="preserve">{"".join(parts)}</text>')

    lx = w - 20 - 5 * 14 - 30
    leg = [f'<g class="rise" style="animation-delay:1.3s" font-family="{FONT}" font-size="10.5" fill="{MUTED}">',
           f'<text x="{lx - 6}" y="{fy}" text-anchor="end">Less</text>']
    for k, shade in enumerate(LEVELS.values()):
        leg.append(f'<rect x="{lx + k * 14}" y="{fy - 10}" width="11" height="11" rx="2.5" fill="{shade}"/>')
    leg.append(f'<text x="{lx + 5 * 14 + 3}" y="{fy}">More</text></g>')
    out.extend(leg)

    out.append("</g></svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", default="dist")
    ap.add_argument("--prev", default="prev")
    args = ap.parse_args()
    os.makedirs(os.path.join(args.out, "data"), exist_ok=True)

    token = os.environ.get("GH_TOKEN") or os.environ.get("STATS_TOKEN")
    cache_new = os.path.join(args.out, "data", "gh_stats.json")
    cache_old = os.path.join(args.prev, "data", "gh_stats.json")

    try:
        if not token:
            raise RuntimeError("GH_TOKEN is not set (add a STATS_TOKEN repo secret)")
        d = fetch(args.user, token)
        print(f"fetched: contributions={d['contributions']} (last year {d['year_total']}, "
              f"{d['year_private']} private) commits={d['commits']} prs={d['prs']} "
              f"repos={d['repos']} ({d['private_repos']} private) stars={d['stars']} "
              f"followers={d['followers']} languages={len(d['languages'])} "
              f"streak={d['streak_current']}/{d['streak_longest']}")
        if not d["private_repos"]:
            print("::warning::The token can't see any private repositories, so languages are "
                  "public-only. Give STATS_TOKEN the `repo` scope to include private ones.")
    except Exception as e:
        print(f"fetch failed: {e}")
        if os.path.exists(cache_old):
            with open(cache_old) as f:
                d = json.load(f)
            print("using cached data from previous run")
        else:
            d = {"name": args.user}
            print("no cache available, rendering placeholder")

    with open(cache_new, "w") as f:
        json.dump(d, f, indent=1)

    for name, render in (("gh-stats.svg", render_stats),
                         ("gh-top-langs.svg", render_top_langs),
                         ("gh-contrib.svg", render_contrib)):
        with open(os.path.join(args.out, name), "w") as f:
            f.write(render(args.user, d))

    return 0


if __name__ == "__main__":
    sys.exit(main())
