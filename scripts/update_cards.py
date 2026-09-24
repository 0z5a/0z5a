#!/usr/bin/env python3
"""Render GitHub profile cards as SVGs stored in this repository."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    followers { totalCount }
    publicRepositories: repositories(
      privacy: PUBLIC, ownerAffiliations: OWNER, first: 1
    ) { totalCount }
    originalRepositories: repositories(
      privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false, first: 100
    ) {
      nodes {
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
    }
  }
}
"""

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#58a6ff"
COLORS = ("#58a6ff", "#a371f7", "#3fb950", "#f2cc60", "#ff7b72")


def fetch(login: str, token: str) -> dict:
    payload = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    request = Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "0z5a-profile-cards",
        },
    )
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("errors") or not result.get("data", {}).get("user"):
        raise RuntimeError(f"GitHub GraphQL did not return user {login!r}")
    return result["data"]["user"]


def svg_open(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
        f"<title>{escape(title)}</title>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" '
        f'rx="12" fill="{BG}" stroke="{BORDER}"/>',
    ]


def label(x: int, y: int, value: str, size: int = 14, color: str = TEXT,
          anchor: str = "start", weight: int = 400) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Arial,Helvetica,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}" '
        f'text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def activity_card(user: dict, updated: str) -> str:
    activity = user["contributionsCollection"]
    values = (
        ("Pull requests", activity["totalPullRequestContributions"]),
        ("Commits", activity["totalCommitContributions"]),
        ("Issues opened", activity["totalIssueContributions"]),
        ("Public repositories", user["publicRepositories"]["totalCount"]),
    )
    lines = svg_open(440, 210, "GitHub activity stats")
    lines += [label(24, 36, "GitHub Activity", 20, ACCENT, weight=700),
              label(24, 56, "Contributions in the past 12 months", 12, MUTED)]
    for index, (name, value) in enumerate(values):
        y = 83 + index * 25
        lines.append(label(24, y, name, 14, MUTED))
        lines.append(label(415, y, f"{value:,}", 15, TEXT, "end", 700))
    lines.append(label(24, 194, f"Updated {updated} UTC", 11, MUTED))
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def language_card(user: dict, updated: str) -> str:
    sizes: Counter[str] = Counter()
    for repo in user["originalRepositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            sizes[edge["node"]["name"]] += edge["size"]
    lines = svg_open(350, 210, "Top languages in original public repositories")
    lines += [label(20, 36, "Top Languages", 20, ACCENT, weight=700),
              label(20, 56, "Original public repositories · by bytes", 11, MUTED)]
    total = sum(sizes.values())
    if total:
        for index, (name, size) in enumerate(sizes.most_common(5)):
            y = 79 + index * 23
            ratio = size / total
            lines.append(label(20, y, name, 12, TEXT))
            lines.append(label(329, y, f"{ratio * 100:.1f}%", 12, MUTED, "end"))
            lines.append(f'<rect x="128" y="{y - 10}" width="155" height="8" rx="4" fill="{PANEL}"/>')
            lines.append(f'<rect x="128" y="{y - 10}" width="{max(3, round(155 * ratio))}" '
                         f'height="8" rx="4" fill="{COLORS[index]}"/>')
    else:
        lines.append(label(20, 95, "No language data yet", 14, MUTED))
    lines.append(label(20, 194, f"Updated {updated} UTC", 11, MUTED))
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def highlights_card(user: dict, updated: str) -> str:
    activity = user["contributionsCollection"]
    values = (
        ("PULL REQUESTS", activity["totalPullRequestContributions"], "past 12 months"),
        ("COMMITS", activity["totalCommitContributions"], "past 12 months"),
        ("PUBLIC REPOS", user["publicRepositories"]["totalCount"], "current"),
        ("FOLLOWERS", user["followers"]["totalCount"], "current"),
    )
    lines = svg_open(790, 144, "GitHub highlights")
    lines.append(label(20, 31, "GitHub Highlights", 18, ACCENT, weight=700))
    for index, (name, value, period) in enumerate(values):
        x = 20 + index * 193
        lines.append(f'<rect x="{x}" y="44" width="180" height="78" rx="9" '
                     f'fill="{PANEL}" stroke="{BORDER}"/>')
        lines.append(label(x + 90, 66, name, 10, MUTED, "middle", 700))
        lines.append(label(x + 90, 94, f"{value:,}", 23, TEXT, "middle", 700))
        lines.append(label(x + 90, 111, period, 10, MUTED, "middle"))
    lines.append(label(20, 137, f"Updated {updated} UTC", 10, MUTED))
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", default="0z5a")
    parser.add_argument("--input-json", type=Path,
                        help="Saved GraphQL response for offline rendering")
    args = parser.parse_args()
    if args.input_json:
        response = json.loads(args.input_json.read_text())
        user = response["data"]["user"]
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            parser.error("GITHUB_TOKEN is required unless --input-json is provided")
        user = fetch(args.login, token)
    if user["login"].lower() != args.login.lower():
        parser.error("GitHub response does not match --login")
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ASSETS.mkdir(exist_ok=True)
    for name, content in (
        ("stats.svg", activity_card(user, updated)),
        ("languages.svg", language_card(user, updated)),
        ("highlights.svg", highlights_card(user, updated)),
    ):
        (ASSETS / name).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
