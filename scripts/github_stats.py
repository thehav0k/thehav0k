#!/usr/bin/env python3
"""
Generate a GitHub stats card and a top-languages card as static SVGs,
using the GitHub GraphQL API directly instead of the shared, frequently
rate-limited https://github-readme-stats.vercel.app service.

Outputs (in --out):
  gh-stats.svg        total stars / commits / PRs / issues / repos / followers
  gh-top-langs.svg     languages by bytes across your owned, non-fork repos
  data/gh_stats.json   cached raw numbers, used as a fallback on failure

Requires a classic Personal Access Token with just `read:user` and
`public_repo` scopes (read-only, public data only), passed as GH_TOKEN.
The default Actions GITHUB_TOKEN can't run these account-wide GraphQL
queries, only repo-scoped ones — see the README this script ships with
for how to create and add the token as a secret.

Standard library only. Run:
  GH_TOKEN=xxx python3 scripts/github_stats.py --user thehav0k --out dist --prev prev
"""

import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com/graphql"
UA = "profile-readme-stats-script"

BG, PANEL, GRID = "#1a1b27", "#1f2335", "#2a2e42"
TEXT, MUTED = "#c0caf5", "#737aa2"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"

STATS_ACCENT = ("#70a5fd", "#38bdae")
LANGS_ACCENT = ("#bf91f3", "#f7768e")

HIDE_LANGS = {"HTML", "CSS"}

# Common linguist colors for the languages likely to appear; anything
# missing falls back to a color cycled from FALLBACK_PALETTE.
LANG_COLORS = {
    "C++": "#f34b7d", "C": "#555555", "C#": "#178600", "Python": "#3572A5",
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Java": "#b07219",
    "Kotlin": "#A97BFF", "Rust": "#dea584", "Swift": "#F05138",
    "Go": "#00ADD8", "PHP": "#4F5D95", "Ruby": "#701516", "Dart": "#00B4AB",
    "HTML": "#e34c26", "CSS": "#563d7c", "Shell": "#89e051",
    "Dockerfile": "#384d54", "Makefile": "#427819", "CMake": "#DA3434",
    "SQL": "#e38c00", "PowerShell": "#012456", "Jupyter Notebook": "#DA5B0B",
    "Vue": "#41b883", "Objective-C": "#438eff", "Lua": "#000080",
    "Perl": "#0298c3", "Scala": "#c22d40", "Haskell": "#5e5086",
    "Assembly": "#6E4C13", "Batchfile": "#C1F12E", "TeX": "#3D6117",
}
FALLBACK_PALETTE = ["#70a5fd", "#bf91f3", "#38bdae", "#e0af68", "#f7768e", "#7aa2f7"]

CSS = """
.fade{opacity:0;animation:fade .8s ease-out forwards}
.rise{opacity:0;animation:rise .8s ease-out forwards}
.bar{transform:scaleX(0);transform-origin:left;animation:grow 1.4s cubic-bezier(.45,.05,.35,1) forwards}
.pct{opacity:0;animation:fade .5s ease-out forwards}
@keyframes fade{to{opacity:1}}
@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes grow{to{transform:scaleX(1)}}
"""


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


PROFILE_QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    createdAt
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: [OWNER], isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}"""

CONTRIB_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar { totalContributions }
    }
  }
}"""


def fetch(username, token):
    profile = gql(PROFILE_QUERY, {"login": username}, token)["user"]
    if profile is None:
        raise RuntimeError(f"no such user: {username}")

    stars = 0
    lang_bytes = {}
    for repo in profile["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            lang_bytes[name] = lang_bytes.get(name, 0) + edge["size"]

    created = datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    commits = prs = issues = contributions = 0
    year = created.year
    while year <= now.year:
        frm = max(created, datetime(year, 1, 1, tzinfo=timezone.utc))
        to = min(now, datetime(year + 1, 1, 1, tzinfo=timezone.utc))
        if frm >= to:
            year += 1
            continue
        cc = gql(CONTRIB_QUERY, {
            "login": username,
            "from": frm.isoformat().replace("+00:00", "Z"),
            "to": to.isoformat().replace("+00:00", "Z"),
        }, token)["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"]
        prs += cc["totalPullRequestContributions"]
        issues += cc["totalIssueContributions"]
        contributions += cc["contributionCalendar"]["totalContributions"]
        year += 1

    return {
        "name": profile["name"] or username,
        "followers": profile["followers"]["totalCount"],
        "public_repos": profile["repositories"]["totalCount"],
        "stars": stars,
        "commits": commits,
        "prs": prs,
        "issues": issues,
        "contributions": contributions,
        "languages": lang_bytes,
    }


# ── Stats card ───────────────────────────────────────────────────────────────
def render_stats(username, d, w=480, h=210):
    esc = html.escape
    a1, a2 = STATS_ACCENT
    rows = [
        ("★", "Total Stars", d["stars"]),
        ("●", "Total Commits", d["commits"]),
        ("⇄", "Total PRs", d["prs"]),
        ("!", "Total Issues", d["issues"]),
        ("▣", "Public Repos", d["public_repos"]),
        ("◕", "Followers", d["followers"]),
    ]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
           f'role="img" aria-label="GitHub stats for {esc(username)}">',
           f"<title>GitHub stats · {esc(username)}</title>",
           f"<style>{CSS}</style>",
           "<defs>",
           f'<linearGradient id="gsl" x1="0" x2="1"><stop offset="0" stop-color="{a1}"/>'
           f'<stop offset="1" stop-color="{a2}"/></linearGradient>',
           f'<clipPath id="gsc"><rect width="{w}" height="{h}" rx="12"/></clipPath>',
           "</defs>",
           f'<g clip-path="url(#gsc)"><rect width="{w}" height="{h}" fill="{BG}"/>',
           f'<rect width="{w}" height="3" fill="url(#gsl)"/>',
           f'<text class="rise" x="20" y="34" fill="{TEXT}" font-family="{FONT}" font-size="16" '
           f'font-weight="700">📊 GitHub Stats</text>',
           f'<text class="rise" style="animation-delay:.05s" x="20" y="52" fill="{MUTED}" '
           f'font-family="{FONT}" font-size="11.5">@{esc(username)} · public repos only</text>']

    cols, col_w = 2, (w - 40) / 2
    for i, (glyph, label, value) in enumerate(rows):
        cx = 20 + (i % cols) * col_w
        cy = 82 + (i // cols) * 42
        delay = 0.15 + i * 0.08
        out.append(f'<g class="rise" style="animation-delay:{delay:.2f}s">'
                   f'<text x="{cx}" y="{cy}" fill="{a1}" font-family="{FONT}" font-size="17" '
                   f'font-weight="700">{glyph}</text>'
                   f'<text x="{cx+26}" y="{cy-3}" fill="{TEXT}" font-family="{FONT}" font-size="17" '
                   f'font-weight="800">{value:,}</text>'
                   f'<text x="{cx+26}" y="{cy+13}" fill="{MUTED}" font-family="{FONT}" '
                   f'font-size="10.5">{esc(label)}</text></g>')
    out.append("</g></svg>")
    return "\n".join(out)


# ── Top languages card ───────────────────────────────────────────────────────
def render_top_langs(username, langs, w=480, h=280, top_n=8):
    esc = html.escape
    a1, a2 = LANGS_ACCENT
    items = [(n, b) for n, b in langs.items() if n not in HIDE_LANGS]
    items.sort(key=lambda x: -x[1])
    items = items[:top_n]
    total = sum(b for _, b in items) or 1

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
           f'role="img" aria-label="Most used languages for {esc(username)}">',
           f"<title>Top languages · {esc(username)}</title>",
           f"<style>{CSS}</style>",
           "<defs>",
           f'<linearGradient id="glg" x1="0" x2="1"><stop offset="0" stop-color="{a1}"/>'
           f'<stop offset="1" stop-color="{a2}"/></linearGradient>',
           f'<clipPath id="glc"><rect width="{w}" height="{h}" rx="12"/></clipPath>',
           "</defs>",
           f'<g clip-path="url(#glc)"><rect width="{w}" height="{h}" fill="{BG}"/>',
           f'<rect width="{w}" height="3" fill="url(#glg)"/>',
           f'<text class="rise" x="20" y="34" fill="{TEXT}" font-family="{FONT}" font-size="16" '
           f'font-weight="700">🧬 Most Used Languages</text>',
           f'<text class="rise" style="animation-delay:.05s" x="20" y="52" fill="{MUTED}" '
           f'font-family="{FONT}" font-size="11.5">@{esc(username)} · by bytes across owned repos</text>']

    if not items:
        out.append(f'<text class="fade" x="{w/2}" y="{h/2}" text-anchor="middle" fill="{MUTED}" '
                   f'font-family="{FONT}" font-size="13">No language data yet</text></g></svg>')
        return "\n".join(out)

    bx, by, bw = 20, 78, w - 40
    for i, (name, size) in enumerate(items):
        pct = size / total * 100
        color = LANG_COLORS.get(name, FALLBACK_PALETTE[i % len(FALLBACK_PALETTE)])
        y = by + i * 25
        delay = 0.15 + i * 0.08
        out.append(f'<g class="rise" style="animation-delay:{delay:.2f}s">'
                   f'<circle cx="{bx+4}" cy="{y-4}" r="4.5" fill="{color}"/>'
                   f'<text x="{bx+16}" y="{y}" fill="{TEXT}" font-family="{FONT}" '
                   f'font-size="12.5">{esc(name)}</text>'
                   f'<text x="{bx+bw}" y="{y}" text-anchor="end" fill="{MUTED}" font-family="{FONT}" '
                   f'font-size="11.5">{pct:.1f}%</text></g>')
        out.append(f'<rect x="{bx}" y="{y+6}" width="{bw}" height="6" rx="3" fill="{GRID}"/>')
        out.append(f'<rect class="bar" style="animation-delay:{delay+.1:.2f}s" x="{bx}" y="{y+6}" '
                   f'width="{bw*pct/100:.1f}" height="6" rx="3" fill="{color}"/>')
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
        print(f"fetched: stars={d['stars']} commits={d['commits']} prs={d['prs']} "
              f"issues={d['issues']} repos={d['public_repos']} followers={d['followers']} "
              f"languages={len(d['languages'])}")
    except Exception as e:
        print(f"fetch failed: {e}")
        if os.path.exists(cache_old):
            with open(cache_old) as f:
                d = json.load(f)
            print("using cached data from previous run")
        else:
            d = {"name": args.user, "followers": 0, "public_repos": 0, "stars": 0,
                 "commits": 0, "prs": 0, "issues": 0, "contributions": 0, "languages": {}}
            print("no cache available, rendering placeholder")

    with open(cache_new, "w") as f:
        json.dump(d, f, indent=1)

    with open(os.path.join(args.out, "gh-stats.svg"), "w") as f:
        f.write(render_stats(args.user, d))
    with open(os.path.join(args.out, "gh-top-langs.svg"), "w") as f:
        f.write(render_top_langs(args.user, d["languages"]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
