#!/usr/bin/env python3
"""Render a GitHub profile SVG. --update fetches public GitHub statistics."""
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

THEMES = {
    "blue": ("#0969da", "#79c0ff", "#a43f11", "#ffa657"),
    "violet": ("#8250df", "#bc8cff", "#a43f11", "#ffa657"),
    "mint": ("#116b57", "#56d8b0", "#a43f11", "#ffa657"),
}
USERNAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


def clean_text(value, field, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    if any(ord(c) < 32 and c not in "\t\n\r" for c in value):
        raise ValueError(f"{field} contains a control character")
    value = " ".join(value.split())
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > 300:
        raise ValueError(f"{field} is too long (maximum 300 characters)")
    return value


def clean_url(value, field):
    value = clean_text(value, field)
    if not value:
        return ""
    parts = urlsplit(value)
    if (parts.scheme not in ("http", "https") or not parts.hostname or
            parts.username or parts.password or any(c.isspace() for c in value)):
        raise ValueError(f"{field} must be a valid http(s) URL without credentials")
    return value


def normalize_config(data):
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    allowed = {"username", "display_name", "focus", "workflow", "tagline", "theme",
               "projects", "contacts", "include_forks", "excluded_repos"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError("unknown config fields: " + ", ".join(sorted(unknown)))
    user = clean_text(data.get("username"), "username", True)
    if not USERNAME.fullmatch(user) or "--" in user:
        raise ValueError("username must be a valid GitHub username")
    theme = data.get("theme", "blue")
    if theme not in THEMES:
        raise ValueError("theme must be blue, violet, or mint")
    result = {
        "username": user,
        "display_name": clean_text(data.get("display_name") or user, "display_name", True),
        "focus": clean_text(data.get("focus"), "focus"),
        "workflow": clean_text(data.get("workflow"), "workflow"),
        "tagline": clean_text(data.get("tagline"), "tagline"),
        "theme": theme,
    }
    for key, limit in (("projects", 3), ("contacts", 2)):
        items = data.get(key, [])
        if not isinstance(items, list) or len(items) > limit:
            raise ValueError(f"{key} must be an array with at most {limit} entries")
        entries = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"{key}[{index}] must be an object")
            permitted = {"name", "description", "url"} if key == "projects" else {"label", "value", "url"}
            if set(item) - permitted:
                raise ValueError(f"unknown fields in {key}[{index}]")
            if key == "projects":
                entry = {"name": clean_text(item.get("name"), "project name", True),
                         "description": clean_text(item.get("description"), "project description"),
                         "url": clean_url(item.get("url"), "project URL")}
            else:
                entry = {"label": clean_text(item.get("label"), "contact label", True),
                         "value": clean_text(item.get("value"), "contact value", True),
                         "url": clean_url(item.get("url"), "contact URL")}
            entries.append(entry)
        result[key] = entries
    include_forks = data.get("include_forks", False)
    if not isinstance(include_forks, bool):
        raise ValueError("include_forks must be true or false")
    result["include_forks"] = include_forks
    excluded = data.get("excluded_repos", [])
    if not isinstance(excluded, list) or len(excluded) > 100:
        raise ValueError("excluded_repos must be an array of repository names")
    result["excluded_repos"] = [clean_text(x, "excluded repository", True) for x in excluded]
    return result


def shorten(text, columns):
    """Fit approximately to a monospace column budget, including CJK characters."""
    used, out = 0, []
    for char in text:
        width = 0 if unicodedata.combining(char) else (2 if unicodedata.east_asian_width(char) in "WF" else 1)
        if used + width > columns:
            while out and used + 1 > columns:
                old = out.pop()
                used -= 0 if unicodedata.combining(old) else (2 if unicodedata.east_asian_width(old) in "WF" else 1)
            return "".join(out) + "…"
        out.append(char)
        used += width
    return "".join(out)


def load_avatar(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if len(lines) > 38 or any(len(line) > 58 for line in lines):
        raise ValueError("avatar must fit within 58 columns and 38 rows")
    if any(ord(c) < 32 or ord(c) == 127 for line in lines for c in line):
        raise ValueError("avatar must not contain control characters")
    return lines


def render(config, avatar, stats=None):
    config = normalize_config(config)
    stats = stats or {}
    esc = html.escape
    blue, blue_dark, orange, orange_dark = THEMES[config["theme"]]
    art = "\n".join(f'<tspan x="45" y="{126+i*9.5:.1f}">{esc(line)}</tspan>' for i, line in enumerate(avatar))
    def text(x, y, value, css="ink", size=15):
        return f'<text class="{css}" x="{x}" y="{y}" font-size="{size}">{esc(value)}</text>'
    def row(y, label, value, limit=30):
        return text(407, y, label + ":", "orange") + text(525, y, shorten(value, limit))
    basics = "\n".join([row(150, "Name", config["display_name"]),
                         row(180, "Focus", config["focus"] or "—"),
                         row(210, "Workflow", config["workflow"] or "—")])
    projects = "\n".join(text(407, 289+30*i, shorten(p["name"], 18) + ":", "orange") +
                         text(600, 289+30*i, shorten(p["description"], 29))
                         for i, p in enumerate(config["projects"]))
    contacts = "\n".join(row(426+25*i, c["label"], c["value"], 32)
                         for i, c in enumerate(config["contacts"]))
    def count(name):
        value = stats.get(name)
        return f"{value:,}" if isinstance(value, int) and value >= 0 else "—"
    title = esc(config["display_name"] + " · GitHub profile")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="570" viewBox="0 0 960 570" role="img" aria-labelledby="title desc">
<title id="title">{title}</title><desc id="desc">Terminal-style profile with a character portrait, projects and public GitHub statistics.</desc>
<style>
  .bg {{ fill:#fff; stroke:#d8dee4 }} .ink {{ fill:#24292f }} .muted {{ fill:#6e7781 }}
  .blue {{ fill:{blue} }} .orange {{ fill:{orange} }} .line {{ stroke:#d8dee4 }}
  text {{ font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace }}
  @media (prefers-color-scheme:dark) {{ .bg {{ fill:#0d1117; stroke:#30363d }} .ink {{ fill:#e6edf3 }} .muted {{ fill:#8b949e }} .blue {{ fill:{blue_dark} }} .orange {{ fill:{orange_dark} }} .line {{ stroke:#30363d }} }}
</style>
<rect class="bg" x="1" y="1" width="958" height="568" rx="14"/>
<circle cx="30" cy="29" r="4" fill="#ff7b72"/><circle cx="45" cy="29" r="4" fill="#e3b341"/><circle cx="60" cy="29" r="4" fill="#56d364"/>
<text class="muted" x="82" y="34" font-size="12" letter-spacing="1">PROFILE / TERMINAL</text>
<line class="line" x1="22" y1="54" x2="938" y2="54"/>
<text class="muted" xml:space="preserve" font-size="9.3">{art}</text>
{text(50, 515, shorten(config["tagline"], 47), "muted", 10)}
{text(407, 110, shorten(config["username"] + "@github", 36), "blue", 18)}
<line class="line" x1="735" y1="104" x2="920" y2="104"/>
{basics}
{text(407, 257, "— Projects", "blue", 16)}<line class="line" x1="540" y1="251" x2="920" y2="251"/>
{projects}
{text(407, 396, "— Connect", "blue", 16)}<line class="line" x1="528" y1="390" x2="920" y2="390"/>
{contacts}
{text(407, 475, "— GitHub Stats", "blue", 16)}<line class="line" x1="570" y1="469" x2="920" y2="469"/>
{text(407, 510, "Repos: " + count("repos"), "ink", 14)}
{text(555, 510, "Stars: " + count("stars"), "ink", 14)}
{text(700, 510, "Followers: " + count("followers"), "ink", 14)}
</svg>
'''


def github_json(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "github-profile-terminal"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request("https://api.github.com" + path, headers=headers)
    with urlopen(request, timeout=25) as response:
        return json.load(response)


def public_stats(config):
    config = normalize_config(config)
    user = quote(config["username"], safe="")
    account = github_json(f"/users/{user}")
    stars, page = 0, 1
    excluded = {x.casefold() for x in config["excluded_repos"]}
    while True:
        repos = github_json(f"/users/{user}/repos?type=owner&per_page=100&page={page}")
        if not isinstance(repos, list):
            raise ValueError("GitHub returned an invalid repository list")
        for repo in repos:
            if repo.get("private") or repo.get("name", "").casefold() in excluded:
                continue
            if repo.get("fork") and not config["include_forks"]:
                continue
            stars += int(repo["stargazers_count"])
        if len(repos) < 100:
            break
        page += 1
    return {"repos": int(account["public_repos"]), "stars": stars,
            "followers": int(account["followers"])}


def build_readme(config):
    config = normalize_config(config)
    esc = html.escape
    links = [(p["name"], p["url"]) for p in config["projects"] if p["url"]]
    links += [(c["label"], c["url"]) for c in config["contacts"] if c["url"]]
    link_html = " &nbsp;·&nbsp; ".join(f'<a href="{esc(url, quote=True)}">{esc(label)}</a>' for label, url in links)
    fork_note = "including forks" if config["include_forks"] else "excluding forks"
    note = f"Stars: public repositories, {fork_note}"
    if config["excluded_repos"]:
        note += "; excluded: " + ", ".join(config["excluded_repos"])
    paragraphs = [f'<p align="center"><img src="./profile.svg" alt="{esc(config["display_name"], quote=True)} GitHub terminal profile" width="100%" /></p>']
    if link_html:
        paragraphs.append(f'<p align="center">{link_html}</p>')
    if config["tagline"]:
        paragraphs.append(f'<p align="center"><sub>{esc(config["tagline"])}</sub></p>')
    paragraphs.append(f'<p align="center"><sub>{esc(note)}</sub></p>')
    return "\n\n".join(paragraphs) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("profile-config.json"))
    parser.add_argument("--avatar-text", type=Path, default=Path("assets/profile-avatar.txt"))
    parser.add_argument("--output", type=Path, default=Path("profile.svg"))
    parser.add_argument("--update", action="store_true", help="fetch public GitHub statistics")
    args = parser.parse_args()
    try:
        config = normalize_config(json.loads(args.config.read_text(encoding="utf-8")))
        avatar = load_avatar(args.avatar_text)
        stats = public_stats(config) if args.update else {}
        rendered = render(config, avatar, stats)
        args.output.write_text(rendered, encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Profile update failed: {exc}", file=sys.stderr)
        return 1
    print(f"Updated {args.output}" + (" with public GitHub statistics" if args.update else " (statistics not fetched)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
