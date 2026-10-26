"""Render the trophy and streak cards for the profile README.

Reads public contribution data for USERNAME through the GitHub GraphQL API
and writes trophies.svg and streak.svg into the directory given as argument.
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

API = "https://api.github.com/graphql"

NIGHT = "#0B1220"
PANEL = "#111A2E"
LINE = "#1E293B"
TEXT = "#F8FAFC"
MUTED = "#94A3B8"
DIM = "#334155"
TEAL_DARK = "#0F766E"
TEAL = "#14B8A6"
TEAL_BRIGHT = "#2DD4BF"
TEAL_LIGHT = "#5EEAD4"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

PROFILE = """
query($login: String!, $after: String) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    pullRequests { totalCount }
    contributionsCollection { contributionYears }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, first: 100, after: $after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { stargazerCount }
    }
  }
}
"""

YEAR = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}
"""

RANKS = ["C", "B", "A", "AA", "AAA", "S", "SS", "SSS"]

# (title, stat key, minimum value for each rank in RANKS)
TROPHIES = [
    ("Commits", "commits", [1, 10, 100, 200, 500, 1000, 2000, 4000]),
    ("Stars", "stars", [1, 10, 30, 50, 100, 200, 700, 2000]),
    ("Followers", "followers", [1, 10, 20, 50, 100, 200, 400, 1000]),
    ("Repositories", "repositories", [1, 10, 20, 30, 35, 40, 45, 50]),
    ("Pull requests", "pull_requests", [1, 10, 20, 50, 100, 200, 500, 1000]),
    ("Experience", "years", [0, 1, 2, 3, 5, 7, 10, 15]),
]


def query(token, text, **variables):
    body = json.dumps({"query": text, "variables": variables}).encode()
    headers = {"Authorization": f"bearer {token}", "Content-Type": "application/json"}
    request = urllib.request.Request(API, body, headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def collect(token, login, today):
    """Fetch the numbers both cards need."""
    profile = user = query(token, PROFILE, login=login)
    stars = 0
    while True:
        repos = user["repositories"]
        stars += sum(node["stargazerCount"] for node in repos["nodes"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        user = query(token, PROFILE, login=login, after=repos["pageInfo"]["endCursor"])

    days, commits = {}, 0
    for year in sorted(profile["contributionsCollection"]["contributionYears"]):
        span = {"from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"}
        data = query(token, YEAR, login=login, **span)["contributionsCollection"]
        commits += data["totalCommitContributions"]
        for week in data["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                when = date.fromisoformat(day["date"])
                if when <= today:
                    days[when] = day["contributionCount"]

    created = datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00")).date()
    return {
        "days": days,
        "commits": commits,
        "stars": stars,
        "followers": profile["followers"]["totalCount"],
        "repositories": profile["repositories"]["totalCount"],
        "pull_requests": profile["pullRequests"]["totalCount"],
        "years": (today - created).days // 365,
    }


def streaks(days, today):
    """Return (length, start, end) for the current and the longest streak."""
    active = sorted(day for day, count in days.items() if count > 0)
    longest = current = (0, None, None)
    start = previous = None
    length = 0
    for day in active:
        if previous and day - previous == timedelta(days=1):
            length += 1
        else:
            start, length = day, 1
        if length > longest[0]:
            longest = (length, start, day)
        previous = day
    # A streak stays alive until a whole day passes without contributions.
    if active and (today - active[-1]).days <= 1:
        current = (length, start, active[-1])
    return current, longest


def fmt_date(day):
    return f"{MONTHS[day.month - 1]} {day.day}, {day.year}"


def fmt_range(start, end, today):
    if start is None:
        return "No contributions yet"
    last = "Present" if (today - end).days <= 1 else fmt_date(end)
    return f"{fmt_date(start)} – {last}" if start != end else fmt_date(start)


def text(x, y, value, size, color, weight=400, spacing=0):
    return (f'<text x="{x}" y="{y}" text-anchor="middle" font-family="{FONT}" '
            f'font-size="{size}" font-weight="{weight}" letter-spacing="{spacing}" '
            f'fill="{color}">{value}</text>')


def rank_of(value, thresholds):
    rank = None
    for name, minimum in zip(RANKS, thresholds):
        if value >= minimum:
            rank = name
    return rank


def rank_color(rank):
    if rank is None:
        return DIM
    if rank.startswith("S"):
        return TEAL_LIGHT
    if rank.startswith("A"):
        return TEAL_BRIGHT
    return TEAL_DARK


def cup(x, y, rank):
    color = rank_color(rank)
    glow = ' filter="url(#glow)"' if rank and rank.startswith("S") else ""
    return f'''<g transform="translate({x},{y})"{glow}>
    <path d="M8 4h32v12c0 10-7 18-16 18S8 26 8 16z" fill="{color}"/>
    <path d="M8 8H3v5c0 5 3 9 8 10M40 8h5v5c0 5-3 9-8 10" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round"/>
    <rect x="21" y="33" width="6" height="7" fill="{color}"/>
    <rect x="14" y="40" width="20" height="6" rx="2" fill="{color}"/>
    {text(24, 21, rank or "–", 11 if rank and len(rank) == 3 else 13, NIGHT, 800)}
  </g>'''


def trophies_svg(stats):
    tile, gap, pad, height = 120, 10, 16, 168
    width = pad * 2 + tile * len(TROPHIES) + gap * (len(TROPHIES) - 1)
    tiles = []
    for index, (title, key, thresholds) in enumerate(TROPHIES):
        value = stats[key]
        rank = rank_of(value, thresholds)
        x = pad + index * (tile + gap)
        label = f"{value} yr{'s' if value != 1 else ''}" if key == "years" else f"{value:,}"
        tiles.append(f'''<g>
    <rect x="{x}" y="{pad}" width="{tile}" height="{height - pad * 2}" rx="10" fill="{PANEL}" stroke="{LINE}"/>
    {cup(x + tile / 2 - 24, pad + 14, rank)}
    {text(x + tile / 2, pad + 92, title.upper(), 10, MUTED, 600, 1.2)}
    {text(x + tile / 2, pad + 118, label, 18, TEXT, 700)}
  </g>''')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="GitHub trophies">
  <defs>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect width="{width}" height="{height}" rx="14" fill="{NIGHT}"/>
  {"".join(tiles)}
</svg>
'''


def streak_svg(stats, today):
    width, height = 802, 196
    days = stats["days"]
    active = sorted(day for day, count in days.items() if count > 0)
    total = sum(days.values())
    current, longest = streaks(days, today)
    total_range = fmt_range(active[0], today, today) if active else "No contributions yet"
    left, middle, right = width / 6, width / 2, width * 5 / 6
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="GitHub contribution streak">
  <rect width="{width}" height="{height}" rx="14" fill="{NIGHT}"/>
  <path d="M{width / 3} 40V156M{width * 2 / 3} 40V156" stroke="{LINE}" stroke-width="1.5"/>

  {text(left, 92, f"{total:,}", 32, TEXT, 700)}
  {text(left, 124, "Total contributions", 14, MUTED, 500)}
  {text(left, 150, total_range, 12, MUTED)}

  <circle cx="{middle}" cy="84" r="44" fill="none" stroke="{TEAL_BRIGHT}" stroke-width="5"/>
  <circle cx="{middle}" cy="40" r="13" fill="{NIGHT}"/>
  <path transform="translate({middle - 8},29)" d="M8 0c1 4 7 7 7 13a7 7 0 0 1-14 0c0-3 2-5 3-7 1 3 2 4 3 4 0-3-1-6 1-10z" fill="{TEAL_BRIGHT}"/>
  {text(middle, 96, current[0], 32, TEXT, 700)}
  {text(middle, 156, "Current streak", 15, TEAL_LIGHT, 700)}
  {text(middle, 178, fmt_range(current[1], current[2], today) if current[0] else "Start a new one today", 12, MUTED)}

  {text(right, 92, longest[0], 32, TEXT, 700)}
  {text(right, 124, "Longest streak", 14, MUTED, 500)}
  {text(right, 150, fmt_range(longest[1], longest[2], today) if longest[0] else "No streak yet", 12, MUTED)}
</svg>
'''


def main():
    out = sys.argv[1]
    today = datetime.now(ZoneInfo(os.environ.get("TIMEZONE", "UTC"))).date()
    stats = collect(os.environ["GITHUB_TOKEN"], os.environ["USERNAME"], today)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "trophies.svg"), "w", encoding="utf-8") as f:
        f.write(trophies_svg(stats))
    with open(os.path.join(out, "streak.svg"), "w", encoding="utf-8") as f:
        f.write(streak_svg(stats, today))


if __name__ == "__main__":
    main()
