---
name: github-profile-terminal
description: Create or update a personalized terminal-style GitHub profile README with an ASCII portrait, project and contact links, and optional public-statistics refresh. Use when a user asks to design, build, or publish a GitHub profile, an ASCII avatar profile, or a terminal-style profile card.
---

# GitHub Profile Terminal

Create an accessible SVG profile card and README from the user's confirmed public details. The bundled generator produces a self-contained profile repository; it does not require the skill after generation.

## Workflow

1. Establish the GitHub username and any preferred display name, focus, workflow, up to three projects, up to two contacts, tagline, and theme (`blue`, `violet`, or `mint`). Use supplied facts and verified public links. Never invent achievements, counts, or affiliations. Keep unknown fields empty. Ask for an avatar image only when one is not already available; offer a placeholder if the user prefers.
2. Copy `assets/example-config.json` to a working JSON file and replace its example values. Choose `include_forks` deliberately. The star total excludes GitHub-marked forks by default; set `excluded_repos` for mirrors or other repositories the user does not want counted. Only include information the user intends to make public.
3. Run `scripts/create_profile.py` with `--config CONFIG.json --output NEW_EMPTY_DIRECTORY`. Add `--avatar-image LOCAL_IMAGE` to convert an image with Pillow, or `--avatar-text FILE` for a 58-column-by-38-row ASCII portrait. Without either option, a placeholder is used. The source image is never copied to the output. Install Pillow only if needed and permitted by the environment.
4. Add `--fetch-stats` only to fetch initial **public** GitHub statistics; otherwise numbers display as dashes. Add `--auto-refresh` only if the user wants a daily GitHub Actions workflow with repository `contents: write` permission. The generator refuses to write into a nonempty output directory. Validate the SVG and show a rendered preview, checking long or CJK text and link destinations.
5. If publication is authorized, inspect the target GitHub account and existing `USERNAME/USERNAME` repository first. The repository and README must be public for a profile README to appear. Preserve existing README content and workflows: merge the generated content deliberately instead of overwriting unrelated work. Do not publish personal information or modify an account without the user's authorization. After publishing, verify the actual profile image and links; if Actions was enabled, check the first run and report any failure.

## Commands

From the profile output directory, `python3 scripts/render_profile.py --update` refreshes the SVG using only public GitHub API data. It uses `GITHUB_TOKEN` if present, never requires a personal access token, and leaves the previous SVG untouched if fetching fails. The README's project/contact links are created at generation time; update those links in `README.md` when editing them later. The generator's built-in help describes all options.

The scripts use Python's standard library except for converting image files, which requires Pillow. `assets/refresh-profile.yml` is copied only when explicitly requested.
