#!/usr/bin/env python3
"""
Generate animated rating-history graphs and live badge data for
Codeforces, LeetCode and CodeChef.

Outputs (in --out):
  cf-rating.svg, leetcode-rating.svg, codechef-rating.svg   animated graphs
  badge-*.json                                              shields.io endpoint badges
  data/*.json                                               cached raw data

If a platform can't be reached, the last good data from --prev is reused,
so a flaky API never blanks the README.

Standard library only. Run:  python scripts/cp_graphs.py --out dist --prev prev
"""

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HANDLES = {
    "codeforces": "thehav0k",
    "leetcode": "thehav0k",
    "codechef": "thehav0k",
}

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# ── Theme (Tokyo Night) ──────────────────────────────────────────────────────
BG, PANEL, GRID = "#1a1b27", "#1f2335", "#2a2e42"
TEXT, MUTED = "#c0caf5", "#737aa2"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"

ACCENTS = {
    "codeforces": ("#70a5fd", "#bf91f3"),
    "leetcode": ("#ffa116", "#f7768e"),
    "codechef": ("#e0af68", "#bf91f3"),
}

LOGOS = {
    "codeforces": "M4.5 7.5C5.328 7.5 6 8.172 6 9v10.5c0 .828-.672 1.5-1.5 1.5h-3C.673 21 0 20.328 0 19.5V9c0-.828.673-1.5 1.5-1.5h3zm9-4.5c.828 0 1.5.672 1.5 1.5v15c0 .828-.672 1.5-1.5 1.5h-3c-.827 0-1.5-.672-1.5-1.5v-15c0-.828.673-1.5 1.5-1.5h3zm9 7.5c.828 0 1.5.672 1.5 1.5v7.5c0 .828-.672 1.5-1.5 1.5h-3c-.828 0-1.5-.672-1.5-1.5V12c0-.828.672-1.5 1.5-1.5h3z",
    "leetcode": "M13.483 0a1.374 1.374 0 0 0-.961.438L7.116 6.226l-3.854 4.126a5.266 5.266 0 0 0-1.209 2.104 5.35 5.35 0 0 0-.125.513 5.527 5.527 0 0 0 .062 2.362 5.83 5.83 0 0 0 .349 1.017 5.938 5.938 0 0 0 1.271 1.818l4.277 4.193.039.038c2.248 2.165 5.852 2.133 8.063-.074l2.396-2.392c.54-.54.54-1.414.003-1.955a1.378 1.378 0 0 0-1.951-.003l-2.396 2.392a3.021 3.021 0 0 1-4.205.038l-.02-.019-4.276-4.193c-.652-.64-.972-1.469-.948-2.263a2.68 2.68 0 0 1 .066-.523 2.545 2.545 0 0 1 .619-1.164L9.13 8.114c1.058-1.134 3.204-1.27 4.43-.278l3.501 2.831c.593.48 1.461.387 1.94-.207a1.384 1.384 0 0 0-.207-1.943l-3.5-2.831c-.8-.647-1.766-1.045-2.774-1.202l2.015-2.158A1.384 1.384 0 0 0 13.483 0zm-2.866 12.815a1.38 1.38 0 0 0-1.38 1.382 1.38 1.38 0 0 0 1.38 1.382H20.79a1.38 1.38 0 0 0 1.38-1.382 1.38 1.38 0 0 0-1.38-1.382z",
    "codechef": "M11.2574.0039c-.37.0101-.7353.041-1.1003.095C9.6164.153 9.0766.4236 8.482.694c-.757.3244-1.5147.6486-2.2176.7027-1.1896.3785-1.568.919-1.8925 1.3516 0 .054-.054.1079-.054.1079-.4325.865-.4873 1.73-.325 2.5952.1621.5407.3786 1.0282.5408 1.5148.3785 1.0274.7578 2.0007.92 3.1362.1622.3244.3235.7571.4316 1.1897.2704.8651.542 1.8383 1.353 2.5952l.0057-.0028c.0175.0183.0301.0387.0482.0568.0072-.0036.0141-.0063.0213-.0099l-.0213-.5849c.6489-.9733 1.5673-1.6221 2.865-1.8925.5195-.1093 1.081-.1497 1.6625-.1278a8.7733 8.7733 0 0 1 1.7988.2357c1.4599.3785 2.595 1.1358 2.6492 1.7846.0273.3549.0398.6952.0326 1.0364-.001.064-.0046.1285-.007.193l.1362.0682c.075-.0375.1424-.107.2059-.1902.0008-.001.002-.002.0028-.0028.0018-.0023.0039-.0061.0057-.0085.0396-.0536.0747-.1236.1107-.1931.0188-.0377.0372-.0866.0554-.1292.2048-.4622.362-1.1536.538-1.9635.0541-.2703.1092-.4864.1633-.7027.4326-.9733 1.0266-1.8382 1.6213-2.6492.9733-1.3518 1.8928-2.5962 1.7846-4.0561-1.784-3.4608-4.2718-4.0017-5.5695-4.272-.2163-.0541-.3233-.0539-.4856-.108-1.3382-.2433-2.4945-.3953-3.6046-.3648zm5.0428 14.3788a9.8602 9.8602 0 0 0-.0326-.9824c-.0541-.703-1.1892-1.46-2.7032-1.8386-.588-.1336-1.1764-.2142-1.7448-.2356-.539-.0137-1.0657.0248-1.5546.1277-1.2436.2704-2.2162.9193-2.811 1.8925l.0511 1.431c.6672-.3558 1.7326-.8747 3.139-.9994.0662-.0059.1368-.0059.2044-.0099.1177-.013.2667-.044.4444-.044 1.6075 0 3.2682.5336 4.8767 1.6483.039-.2744.0611-.549.071-.8234l.044.0227c.0028-.0622.0143-.1268.0156-.1888zM11.256.0578c.1239-.0034.2538.01.379.0114-.23-.0022-.4588.0026-.6871.0156.103-.0061.2046-.0242.308-.027zm.4983.0156c.6552.014 1.3255.0711 2.0387.1803-.6834-.0987-1.3646-.1671-2.0387-.1803zm-1.3147.0554c-.076.0087-.1527.0133-.2285.0241-.8168.1167-1.7742.7015-2.75 1.045.3545-.1323.7143-.2957 1.0747-.4501C9.0765.4774 9.6705.207 10.1571.1529c.0939-.0139.1886-.0133.2825-.0241zm-.2285.24c.1622 0 .3787-.0002.5409.0539-.1425-.0357-.2595-.026-.3706-.0142a1.174 1.174 0 0 1 .3166.0681c.5796 1.0012-.4264 5.2791-.6786 8.1492.1559 1.0276.3138 1.9963.4628 2.7201-.7029-1.7843-1.4067-4.921-1.5148-7.354-.054-.9733.001-1.8386.2172-2.4874C9.401.8557 9.7244.4228 10.2111.3687zm3.1361.271c-.811 2.1088-.9184 6.1092-.9725 7.3528-.054.5407-.0001 1.73.054 2.5952 0 .2163.054.4325.054.6488 0-.2163-.054-.3786-.054-.5948-.4326-3.2442-.974-7.1362.9185-10.002zm3.352.3777c-.2704 2.1628-1.4047 3.191-1.7832 5.2998-.1081 1.6762-.325 3.6222-.379 5.2984-.0541-1.6762-.0007-3.4601.2697-5.2444.2703-1.8384.8651-3.6776 1.8925-5.3538zm-10.381.433c-.3581.1194-.632.248-.8575.3805.2317-.1358.4996-.2666.8575-.3805zm.2101.1974c.2155.0025.4384.0734.6006.2357-.0067-.004-.0078-.0033-.0142-.0071.1331.0929.2666.2093.3932.3847-.2036.9673.2553 3.0317.0398 4.6694.0763 1.5485.0717 3.1804.849 4.4594-.9796-1.5107-1.176-3.4375-1.3218-5.236-.1128-1.0907-.2035-2.0969-.4642-2.9033-.144-.3047-.2684-.5745-.3833-.822-.0247-.0369-.0447-.0784-.071-.1135-.1082-.1082-.1619-.2696-.1619-.3777 0-.054.0539-.1618.108-.1618.054-.0541.1616-.0553.2157-.1094a1.013 1.013 0 0 1 .2101-.0184zm-1.3459.6133c-.0604.0201-.0923.041-.1405.061.1768-.034.3617.0339.5196.318-.1877.8916.4364 3.3685.4288 5.104.3124 1.8478.5496 3.8498 1.5716 5.1152C6.3723 11.5076 5.886 9.1286 5.5076 7.128 5.183 5.56 4.9125 4.2086 4.3718 3.776c-.054-.1081-.1079-.163-.1079-.2711 0-.1622-.0002-.3786.1079-.5949-.2772.6337-.4047 1.2673-.3706 1.901-.0445-.6487.0857-1.2905.3706-1.901 0-.054.054-.0538.054-.1079.012-.016.0314-.0349.044-.0511.0618-.0983.1308-.189.2257-.257.0557-.0615.0965-.1191.159-.1817-.0526.0555-.0872.1092-.1335.1647.0273-.018.0523-.0368.0838-.0525.1081-.1082.2154-.1633.3776-.1633zm-.3776.1633c-.0038.0075-.0076.0111-.0114.0184.0125-.0099.0242-.0208.037-.0298-.0074.0037-.0182.0077-.0256.0114zm14.7608 1.1343c-.0017.0052-.004.0104-.0057.0156.0378-.005.0751-.0173.1135-.0156-.0378-.0022-.0763.0103-.115.0199-.8634 2.6418-1.8874 5.2844-2.9118 7.9262a.0184.0184 0 0 1-.0015.0028c-.0874.4652-.234.8842-.5395 1.1898.4326-.4867.4854-1.1907.5395-2.0558.054-.811.0544-1.6761.487-2.5413 0-.0531.0012-.1058.0525-.159.0003-.0009.0012-.0019.0015-.0028.0973-.3524.202-.6885.3166-1.018.4183-1.2896 1.1396-3.1653 2.0131-3.3405.0163-.0052.034-.018.0497-.0213zM8.3726 16.2113l-.3238.1079c.1623.2163.2696.379.3777.433.1081.054.2168.108.379.108.0541 0 .1618 0 .2159-.054l.812-.2698c.0541 0 .1078-.054.1619-.054.1081 0 .1616 0 .2697.054l.2712.2698.2697-.054c-.1081-.1622-.2695-.3236-.3776-.3776-.1082-.0541-.2169-.1094-.379-.1094h-.108l-.866.3252h-.1618c-.1082 0-.2157 0-.2698-.054-.054-.054-.163-.1629-.2712-.3251zm-2.5953.541c-.2703.1621-.649.4324-1.1897.6487-.5407.2163-.9734.4325-1.1897.6488-.2163.2163-.3237.4326-.3237.6488 0 .1082.0537.1632.1618.2172.054.0541.1632.0539.2172.108.757.3244 1.5133.7019 2.2162 1.0803.1082.0541.2171.1632.2712.2173.054.054.1078.054.1618.054.1082 0 .2695-.0538.3777-.162.1081-.108.1632-.217.1632-.325 0-.1082-.055-.1618-.1632-.2158 0 0-.4328-.2165-1.1898-.541-.4866-.2162-.9179-.4326-1.1883-.5948.1623-.2704.486-.4865.9726-.7028.5407-.2163.9196-.4326 1.0818-.5948.054-.0541.054-.1078.054-.1619 0-.054-.0539-.1631-.108-.2172-.054-.054-.163-.1079-.2711-.1079zm11.247 0c-.054 0-.1618.0537-.2158.1078-.0541.1081-.1093.1632-.1093.2172v.054c.1622.1622.3797.2695.7041.3776.2704.054.5403.1632.8107.2172.3244.1082.5407.2693.6488.4856v.0553c0 .0541-.1088.1616-.3251.2698-.1082.054-.3245.2167-.5949.433-.2703.1622-.4326.3236-.5948.3776-.2163.1082-.3776.217-.4316.3252-.0541.054-.054.1077-.054.1618 0 .1081.0539.1077.108.2158.054.1081.1616.1093.2157.1093.054 0 .1078-.0554.1619-.0554.2703-.1622.6492-.3782 1.0818-.7567.4866-.3784.8655-.6484 1.0818-.8106.2163-.1082.3237-.2169.3237-.379 0-.0541.0002-.1618-.1079-.2159-.3785-.4325-.9185-.7022-1.5674-.9185-.1081-.0541-.2704-.1092-.5948-.1633-.1622-.054-.3249-.1079-.433-.1079zm-2.9743.8106c-.2704 0-.4866.055-.6488.2172-.2163.1622-.2699.4323-.2158.7567 0 .2703.1075.4865.2697.7027.1622.2163.3786.3252.5949.3252.1622 0 .2708-.0553.433-.1094.2703-.1622.379-.4319.379-.9185 0-.3785-.109-.6485-.2711-.8107-.1622-.1081-.3246-.1632-.541-.1632zm-4.4877.054c-.2704 0-.4866.055-.6488.2171-.2163.1622-.27.4323-.2158.7567 0 .2704.1075.4865.2697.7028s.3786.3251.5949.3251c.1622 0 .2708-.0552.433-.1093.2703-.1622.3776-.432.3776-.9186 0-.4325-.1075-.7025-.2697-.8106-.1622-.1082-.3247-.1633-.541-.1633zm0 .6501c.1622 0 .2711.1076.2711.2698 0 .1622-.163.2697-.2711.2697-.1622 0-.2698-.1075-.2698-.2697s.1076-.2698.2698-.2698zm4.3798.054c.1622 0 .2711.1075.2711.2697 0 .1082-.109.2698-.2711.2698-.1622 0-.2698-.1076-.2698-.2698 0-.1622.1076-.2697.2698-.2697zm-2.7032 2.1083l.1619.3237c.054.1081.1076.163.2158.2711.054.054.163.1619.2712.1619h.1078c.1082 0 .1618 0 .2158-.054.0541-.054.1632-.0538.2173-.1079l.1618-.1618c.054-.054.108-.1092.108-.1633.054-.054.0537-.1078.1078-.1618 0-.0541.054-.108.054-.108-.0541.1082-.1618.2156-.2158.3238-.1082.054-.1616.1632-.2698.1632-.1081.0541-.217.054-.3251.054s-.2157.0001-.2697-.054c-.1082 0-.1632-.0538-.2173-.1079l-.1618-.1632c-.054-.0541-.1078-.1618-.1619-.2158zm-.866 1.0278c-1.1355 0-1.8377 1.5136-3.4598.1619-.4326 2.6494 2.7583 2.866 4.11 1.7306.9192-.811.6475-1.9465-.6502-1.8925zm2.8664 0c-1.2977-.054-1.568 1.0815-.6488 1.8925 1.3518 1.1355 4.5412.9188 4.1087-1.7306-1.6221 1.3517-2.2703-.1619-3.4599-.1619z",
}
LOGO_FILL = {"codeforces": "#1f8acb", "leetcode": "#ffa116", "codechef": "#c9a27e"}

# (lower bound, title, band colour, readable text colour)
CF_TIERS = [
    (0, "Newbie", "#808080", "#a9a9a9"),
    (1200, "Pupil", "#008000", "#3fbf3f"),
    (1400, "Specialist", "#03a89e", "#2fd4c6"),
    (1600, "Expert", "#0000ff", "#6e8bff"),
    (1900, "Candidate Master", "#aa00aa", "#d36bd3"),
    (2100, "Master", "#ff8c00", "#ffa94d"),
    (2300, "International Master", "#ff8c00", "#ffa94d"),
    (2400, "Grandmaster", "#ff0000", "#ff6b6b"),
    (2600, "International Grandmaster", "#ff0000", "#ff6b6b"),
    (3000, "Legendary Grandmaster", "#aa0000", "#ff5252"),
]
CC_TIERS = [
    (0, "1★", "#666666", "#9e9e9e"),
    (1400, "2★", "#1e7d22", "#4caf50"),
    (1600, "3★", "#3366cc", "#6e9bff"),
    (1800, "4★", "#684273", "#b07cc0"),
    (2000, "5★", "#ffbf00", "#ffd24d"),
    (2200, "6★", "#ff7f00", "#ffa24d"),
    (2500, "7★", "#d0011b", "#ff5a6e"),
]


def tier(tiers, rating):
    cur = tiers[0]
    for t in tiers:
        if rating is not None and rating >= t[0]:
            cur = t
    return cur


# ── HTTP ─────────────────────────────────────────────────────────────────────
def http(url, data=None, headers=None, timeout=30):
    hdrs = {"User-Agent": UA, "Accept": "*/*"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def http_json(url, **kw):
    return json.loads(http(url, **kw))


# ── Fetchers: each returns a dict with a common shape ────────────────────────
#   points: [[unix_ts, rating, contest_name], ...]  (sorted)
#   current, max, solved, title, max_title
def fetch_codeforces(handle):
    info = http_json(f"https://codeforces.com/api/user.info?handles={handle}")["result"][0]
    hist = http_json(f"https://codeforces.com/api/user.rating?handle={handle}")["result"]
    points = [[r["ratingUpdateTimeSeconds"], r["newRating"], r["contestName"]] for r in hist]

    solved = None
    try:
        subs = http_json(f"https://codeforces.com/api/user.status?handle={handle}", timeout=60)["result"]
        solved = len({(s["problem"].get("contestId"), s["problem"].get("index"))
                      for s in subs if s.get("verdict") == "OK"})
    except Exception as e:  # solved count is a nice-to-have
        print(f"  codeforces: solved count unavailable ({e})")

    return {
        "points": sorted(points),
        "current": info.get("rating"),
        "max": info.get("maxRating"),
        "title": (info.get("rank") or "unrated").title(),
        "max_title": (info.get("maxRank") or "unrated").title(),
        "solved": solved,
    }


LC_QUERY = """
query profile($username: String!) {
  matchedUser(username: $username) {
    submitStatsGlobal { acSubmissionNum { difficulty count } }
  }
  userContestRanking(username: $username) {
    attendedContestsCount rating globalRanking topPercentage badge { name }
  }
  userContestRankingHistory(username: $username) {
    attended rating contest { title startTime }
  }
}"""


def fetch_leetcode(handle):
    body = json.dumps({"query": LC_QUERY, "variables": {"username": handle}}).encode()
    data = http_json("https://leetcode.com/graphql", data=body, headers={
        "Content-Type": "application/json",
        "Referer": f"https://leetcode.com/u/{handle}/",
        "Origin": "https://leetcode.com",
    })["data"]

    hist = data.get("userContestRankingHistory") or []
    points = [[h["contest"]["startTime"], round(h["rating"]), h["contest"]["title"]]
              for h in hist if h.get("attended")]
    ranking = data.get("userContestRanking") or {}

    solved = None
    user = data.get("matchedUser") or {}
    for row in (user.get("submitStatsGlobal") or {}).get("acSubmissionNum", []):
        if row.get("difficulty") == "All":
            solved = row.get("count")

    badge = (ranking.get("badge") or {}).get("name")
    top = ranking.get("topPercentage")
    title = badge or (f"Top {top:.1f}%" if top else None)
    current = round(ranking["rating"]) if ranking.get("rating") else None
    return {
        "points": sorted(points),
        "current": current,
        "max": max((p[1] for p in points), default=current),
        "title": title,
        "max_title": badge,
        "solved": solved,
    }


def _codechef_rows_to_points(rows):
    points = []
    for r in rows:
        try:
            if r.get("end_date"):
                dt = datetime.strptime(r["end_date"][:19], "%Y-%m-%d %H:%M:%S")
            else:
                dt = datetime(int(r["getyear"]), int(r["getmonth"]), int(r["getday"]))
            points.append([int(dt.replace(tzinfo=timezone.utc).timestamp()),
                           int(r["rating"]), r.get("name") or r.get("code") or ""])
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(points)


def fetch_codechef(handle):
    try:
        page = http(f"https://www.codechef.com/users/{handle}")
        m = re.search(r"var\s+all_rating\s*=\s*(\[.*?\])\s*;", page, re.S)
        if not m:
            raise ValueError("rating data not found in profile page")
        points = _codechef_rows_to_points(json.loads(m.group(1)))
        cur = re.search(r'class="rating-number"[^>]*>\s*(\d+)', page)
        hi = re.search(r"Highest Rating\s*(\d+)", page)
        solved = re.search(r"Total Problems Solved:\s*(\d+)", page)
        current = int(cur.group(1)) if cur else (points[-1][1] if points else None)
        highest = int(hi.group(1)) if hi else max((p[1] for p in points), default=current)
        solved = int(solved.group(1)) if solved else None
    except Exception as e:
        print(f"  codechef: profile page failed ({e}); trying fallback API")
        d = http_json(f"https://codechef-api.vercel.app/handle/{handle}")
        points = _codechef_rows_to_points(d.get("ratingData") or [])
        current, highest, solved = d.get("currentRating"), d.get("highestRating"), None

    return {
        "points": points,
        "current": current,
        "max": highest,
        "title": tier(CC_TIERS, current)[1] if current else None,
        "max_title": tier(CC_TIERS, highest)[1] if highest else None,
        "solved": solved,
    }


FETCHERS = {"codeforces": fetch_codeforces, "leetcode": fetch_leetcode, "codechef": fetch_codechef}
NAMES = {"codeforces": "Codeforces", "leetcode": "LeetCode", "codechef": "CodeChef"}
FILES = {"codeforces": "cf-rating.svg", "leetcode": "leetcode-rating.svg", "codechef": "codechef-rating.svg"}


# ── SVG rendering ────────────────────────────────────────────────────────────
CSS = """
.fade{opacity:0;animation:fade .8s ease-out forwards}
.rise{opacity:0;animation:rise .8s ease-out forwards}
.line{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 2.4s cubic-bezier(.45,.05,.35,1) .4s forwards}
.area{opacity:0;animation:fade 1.2s ease-out 1.8s forwards}
.dot{opacity:0;animation:pop .4s ease-out forwards}
.pulse{transform-box:fill-box;transform-origin:center;opacity:0;animation:pulse 2.2s ease-out 3s infinite}
.peak{opacity:0;animation:rise .6s ease-out 2.8s forwards}
@keyframes fade{to{opacity:1}}
@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes pop{from{opacity:0}to{opacity:1}}
@keyframes pulse{0%{opacity:.9;transform:scale(1)}100%{opacity:0;transform:scale(3.4)}}
"""


def _nice_step(span, max_ticks):
    for step in (25, 50, 100, 200, 250, 500, 1000):
        if span / step <= max_ticks:
            return step
    return 1000


def _month_ticks(t0, t1, max_labels):
    start = datetime.fromtimestamp(t0, timezone.utc)
    months = []
    y, m = start.year, start.month
    while True:
        m += 1
        if m > 12:
            y, m = y + 1, 1
        ts = datetime(y, m, 1, tzinfo=timezone.utc).timestamp()
        if ts > t1:
            break
        months.append((ts, y, m))
    for step in (1, 2, 3, 4, 6, 12, 24):
        picked = [t for t in months if (t[2] - 1) % step == 0]
        if len(picked) <= max_labels:
            return picked
    return months[:: max(1, len(months) // max_labels)]


def render(platform, handle, d, w, h):
    esc = html.escape
    a1, a2 = ACCENTS[platform]
    tiers = CF_TIERS if platform == "codeforces" else CC_TIERS if platform == "codechef" else None
    pts = d.get("points") or []
    narrow = w < 600
    uid = platform[:2]

    cur, mx = d.get("current"), d.get("max")
    cur_col = tier(tiers, cur)[3] if tiers and cur else a1
    max_col = tier(tiers, mx)[3] if tiers and mx else a2

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
           f'role="img" aria-label="{NAMES[platform]} rating history for {esc(handle)}">',
           f"<title>{NAMES[platform]} rating history · {esc(handle)}</title>",
           f"<style>{CSS}</style>",
           "<defs>",
           f'<linearGradient id="{uid}l" x1="0" x2="1"><stop offset="0" stop-color="{a1}"/>'
           f'<stop offset="1" stop-color="{a2}"/></linearGradient>',
           f'<linearGradient id="{uid}a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a1}" '
           f'stop-opacity=".35"/><stop offset="1" stop-color="{a1}" stop-opacity="0"/></linearGradient>',
           f'<clipPath id="{uid}c"><rect x="0" y="0" width="{w}" height="{h}" rx="12"/></clipPath>',
           "</defs>",
           f'<g clip-path="url(#{uid}c)"><rect width="{w}" height="{h}" fill="{BG}"/>',
           f'<rect width="{w}" height="3" fill="url(#{uid}l)"/>']

    # Header: logo, name, handle
    out.append(f'<g class="rise" style="animation-delay:.05s">'
               f'<g transform="translate(20 20) scale(1.1667)"><path d="{LOGOS[platform]}" '
               f'fill="{LOGO_FILL[platform]}"/></g>'
               f'<text x="58" y="36" fill="{TEXT}" font-family="{FONT}" font-size="18" '
               f'font-weight="700">{NAMES[platform]}</text>')
    sub = f"@{handle}"
    if pts:
        sub += f" · {len(pts)} rated contest{'s' if len(pts) != 1 else ''}"
    out.append(f'<text x="58" y="55" fill="{MUTED}" font-family="{FONT}" font-size="12">{esc(sub)}</text></g>')

    # Header: current / max on the right
    if cur is not None:
        label = esc(d.get("title") or "")
        out.append(f'<g class="rise" style="animation-delay:.25s" font-family="{FONT}" text-anchor="end">'
                   f'<text x="{w-20}" y="40" fill="{cur_col}" font-size="26" font-weight="800">{cur}</text>'
                   f'<text x="{w-20}" y="58" fill="{MUTED}" font-size="11.5">'
                   f'<tspan fill="{cur_col if tiers else MUTED}">{label}</tspan>'
                   f'{" · " if label and mx else ""}'
                   f'{"max " if mx else ""}<tspan fill="{max_col}" font-weight="700">'
                   f'{mx if mx else ""}</tspan></text></g>')

    px0, px1 = 52, w - 22
    py0, py1 = 82, h - 34

    if not pts:
        out.append(f'<text class="fade" x="{w/2}" y="{(py0+py1)/2}" text-anchor="middle" fill="{MUTED}" '
                   f'font-family="{FONT}" font-size="14">No rated contests yet — the graph appears '
                   f'after the first one</text>')
        out.append("</g></svg>")
        return "\n".join(out)

    ts = [p[0] for p in pts]
    rs = [p[1] for p in pts]
    t0, t1 = ts[0], ts[-1]
    if t1 - t0 < 86400 * 30:
        t0, t1 = t0 - 86400 * 15, t1 + 86400 * 15
    lo, hi = min(rs), max(rs)
    step = _nice_step(max(hi - lo, 100) + 200, 5 if narrow else 6)
    y_lo = (lo - 60) // step * step
    y_hi = -((-(hi + 60)) // step) * step

    def X(t):
        return px0 + (t - t0) / (t1 - t0) * (px1 - px0)

    def Y(r):
        return py1 - (r - y_lo) / (y_hi - y_lo) * (py1 - py0)

    # Tier bands
    if tiers:
        for i, (lb, _, col, _) in enumerate(tiers):
            ub = tiers[i + 1][0] if i + 1 < len(tiers) else 10 ** 5
            a, b = max(lb, y_lo), min(ub, y_hi)
            if a < b:
                out.append(f'<rect class="fade" x="{px0}" y="{Y(b):.1f}" width="{px1-px0}" '
                           f'height="{Y(a)-Y(b):.1f}" fill="{col}" fill-opacity=".13"/>')

    # Grid + axis labels
    g = [f'<g class="fade" style="animation-delay:.1s" font-family="{FONT}" font-size="10.5" fill="{MUTED}">']
    r = y_lo
    while r <= y_hi:
        y = Y(r)
        g.append(f'<line x1="{px0}" x2="{px1}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        g.append(f'<text x="{px0-8}" y="{y+3.5:.1f}" text-anchor="end">{r}</text>')
        r += step
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    for t, yy, mm in _month_ticks(t0, t1, 4 if narrow else 8):
        x = X(t)
        g.append(f'<text x="{x:.1f}" y="{h-14}" text-anchor="middle">{months[mm-1]} \'{yy % 100:02d}</text>')
    g.append("</g>")
    out.extend(g)

    # Area + line
    coords = [(X(t), Y(r)) for t, r, _ in pts]
    line = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in coords)
    area = f"{line} L{coords[-1][0]:.1f} {py1} L{coords[0][0]:.1f} {py1} Z"
    out.append(f'<path class="area" d="{area}" fill="url(#{uid}a)"/>')
    out.append(f'<path class="line" pathLength="1" d="{line}" fill="none" stroke="url(#{uid}l)" '
               f'stroke-width="{2.2 if narrow else 2.6}" stroke-linejoin="round" stroke-linecap="round"/>')

    # Dots, timed to appear as the line reaches them
    dr = 2.6 if narrow or len(pts) > 40 else 3.2
    for (x, y), (t, rating, name) in zip(coords, pts):
        delay = 0.4 + 2.4 * (x - px0) / max(px1 - px0, 1)
        out.append(f'<circle class="dot" style="animation-delay:{delay:.2f}s" cx="{x:.1f}" cy="{y:.1f}" '
                   f'r="{dr}" fill="{BG}" stroke="{a1}" stroke-width="1.8">'
                   f'<title>{esc(name)} — {rating}</title></circle>')

    # Peak marker
    i_max = max(range(len(pts)), key=lambda i: (pts[i][1], pts[i][0]))
    mx_x, mx_y = coords[i_max]
    anchor = "end" if mx_x > w - 90 else "start" if mx_x < 90 else "middle"
    out.append(f'<g class="peak"><circle cx="{mx_x:.1f}" cy="{mx_y:.1f}" r="{dr+1.8}" fill="{max_col}"/>'
               f'<text x="{mx_x:.1f}" y="{mx_y-10:.1f}" text-anchor="{anchor}" fill="{max_col}" '
               f'font-family="{FONT}" font-size="11" font-weight="700">▲ {pts[i_max][1]}</text></g>')

    # Pulsing latest point
    lx, ly = coords[-1]
    out.append(f'<circle class="pulse" cx="{lx:.1f}" cy="{ly:.1f}" r="{dr+1}" fill="none" '
               f'stroke="{cur_col}" stroke-width="1.6"/>')
    out.append(f'<circle class="dot" style="animation-delay:2.8s" cx="{lx:.1f}" cy="{ly:.1f}" '
               f'r="{dr+1}" fill="{cur_col}"/>')

    out.append("</g></svg>")
    return "\n".join(out)


# ── shields.io endpoint badges ───────────────────────────────────────────────
def badge_json(label, message, color, logo=None):
    b = {"schemaVersion": 1, "label": label, "message": str(message), "color": color.lstrip("#"),
         "labelColor": "1a1b27", "style": "for-the-badge"}
    if logo:
        b.update({"namedLogo": logo, "logoColor": "white"})
    return b


def badges_for(platform, d):
    tiers = CF_TIERS if platform == "codeforces" else CC_TIERS if platform == "codechef" else None
    cur, mx = d.get("current"), d.get("max")
    out = {"rating": badge_json(f"{NAMES[platform]} Rating", "unrated", "737aa2", platform),
           "max": badge_json("Max Rating", "—", "737aa2", platform),
           "solved": badge_json(f"{NAMES[platform]} Solved", "—", "737aa2", platform)}
    if cur is not None:
        col = tier(tiers, cur)[3] if tiers else "ffa116"
        msg = f"{cur} · {d['title']}" if d.get("title") else cur
        out["rating"] = badge_json(f"{NAMES[platform]} Rating", msg, col, platform)
    if mx is not None:
        col = tier(tiers, mx)[3] if tiers else "f7768e"
        msg = f"{mx} · {d['max_title']}" if d.get("max_title") else mx
        out["max"] = badge_json("Max Rating", msg, col, platform)
    if d.get("solved") is not None:
        out["solved"] = badge_json(f"{NAMES[platform]} Solved", f"{d['solved']}+", "70a5fd", platform)
    return out


# ── main ─────────────────────────────────────────────────────────────────────
SIZES = {"codeforces": (880, 300), "leetcode": (430, 280), "codechef": (430, 280)}
SHORT = {"codeforces": "cf", "leetcode": "leetcode", "codechef": "codechef"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--prev", default="prev", help="previous output, used when a site is unreachable")
    args = ap.parse_args()
    os.makedirs(os.path.join(args.out, "data"), exist_ok=True)

    for platform, handle in HANDLES.items():
        print(f"{platform}:")
        cache_new = os.path.join(args.out, "data", f"{platform}.json")
        cache_old = os.path.join(args.prev, "data", f"{platform}.json")
        try:
            d = FETCHERS[platform](handle)
            print(f"  fetched {len(d['points'])} contests, current={d['current']} max={d['max']} "
                  f"solved={d['solved']}")
        except Exception as e:
            print(f"  fetch failed: {e}")
            if os.path.exists(cache_old):
                with open(cache_old) as f:
                    d = json.load(f)
                print("  using cached data from previous run")
            else:
                d = {"points": [], "current": None, "max": None, "title": None,
                     "max_title": None, "solved": None}
                print("  no cache available, rendering placeholder")

        d["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(cache_new, "w") as f:
            json.dump(d, f, indent=1)

        w, h = SIZES[platform]
        with open(os.path.join(args.out, FILES[platform]), "w") as f:
            f.write(render(platform, handle, d, w, h))

        for kind, b in badges_for(platform, d).items():
            with open(os.path.join(args.out, f"badge-{SHORT[platform]}-{kind}.json"), "w") as f:
                json.dump(b, f)

    return 0


if __name__ == "__main__":
    sys.exit(main())
