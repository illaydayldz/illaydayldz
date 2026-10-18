"""Generates assets/stats.svg from the GitHub GraphQL API.

Runs inside GitHub Actions (see .github/workflows/stats.yml) using the
built-in GITHUB_TOKEN, so no external stats service is needed.
Run locally with:  GITHUB_TOKEN=... python scripts/generate_stats.py
"""
import json
import os
import sys
import urllib.request
from html import escape

LOGIN = os.environ.get("GH_LOGIN", "illaydayldz")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "stats.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""

PURPLES = ["#8b5cf6", "#a78bfa", "#c4b5fd", "#6d28d9", "#ddd6fe", "#4c1d95"]
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(json.dumps(data["errors"], indent=2))
    return data["data"]["user"]


def summarize(user):
    repos = user["repositories"]
    cc = user["contributionsCollection"]
    langs = {}
    for repo in repos["nodes"]:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    stats = [
        ("Contributions (last year)", cc["contributionCalendar"]["totalContributions"]),
        ("Commits (last year)", cc["totalCommitContributions"]),
        ("Pull requests (last year)", cc["totalPullRequestContributions"]),
        ("Public repositories", repos["totalCount"]),
        ("Stars earned", sum(r["stargazerCount"] for r in repos["nodes"])),
        ("Followers", user["followers"]["totalCount"]),
    ]
    return stats, langs


def render(stats, langs):
    W, H = 840, 300
    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f"<style>text{{font-family:{FONT};}}</style>",
        f'<rect width="{W}" height="{H}" rx="18" fill="#000000"/>',
        '<text x="48" y="58" font-size="24" font-weight="700" fill="#ffffff">GitHub Stats</text>',
    ]
    # Left card: numbers
    o.append('<rect x="48" y="84" width="362" height="186" rx="12" fill="#0e0e12" stroke="#26222f"/>')
    for i, (label, value) in enumerate(stats):
        y = 116 + i * 27
        o.append(f'<text x="68" y="{y}" font-size="13" fill="#bdbdc7">{escape(label)}</text>')
        o.append(f'<text x="390" y="{y}" font-size="14" font-weight="700" fill="#a78bfa" text-anchor="end">{value}</text>')
    # Right card: languages
    o.append('<rect x="430" y="84" width="362" height="186" rx="12" fill="#0e0e12" stroke="#26222f"/>')
    o.append('<text x="450" y="116" font-size="15" font-weight="700" fill="#ffffff">Top languages</text>')
    total = sum(langs.values())
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    if not total:
        o.append('<text x="450" y="160" font-size="13" fill="#bdbdc7">No public code yet</text>')
    else:
        bar_x, bar_w = 450, 322
        o.append(f'<clipPath id="bar"><rect x="{bar_x}" y="132" width="{bar_w}" height="10" rx="5"/></clipPath>')
        o.append('<g clip-path="url(#bar)">')
        x = bar_x
        for i, (name, size) in enumerate(top):
            w = bar_w * size / sum(s for _, s in top)
            o.append(f'<rect x="{x:.1f}" y="132" width="{w + 0.5:.1f}" height="10" fill="{PURPLES[i % len(PURPLES)]}"/>')
            x += w
        o.append("</g>")
        for i, (name, size) in enumerate(top):
            col, row = i % 2, i // 2
            lx, ly = 450 + col * 165, 174 + row * 30
            pct = 100 * size / total
            o.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{PURPLES[i % len(PURPLES)]}"/>')
            o.append(f'<text x="{lx + 16}" y="{ly}" font-size="12.5" fill="#bdbdc7">{escape(name)} '
                     f'<tspan fill="#8b8b96">{pct:.1f}%</tspan></text>')
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    if "--placeholder" in sys.argv:
        stats = [(l, "–") for l in ["Contributions (last year)", "Commits (last year)",
                                    "Pull requests (last year)", "Public repositories",
                                    "Stars earned", "Followers"]]
        svg = render(stats, {})
    else:
        svg = render(*summarize(fetch()))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", os.path.abspath(OUT))
