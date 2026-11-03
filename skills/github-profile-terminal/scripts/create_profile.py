#!/usr/bin/env python3
"""Create a self-contained GitHub profile in a new, empty directory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from render_profile import build_readme, load_avatar, normalize_config, public_stats, render

SKILL_ROOT = Path(__file__).resolve().parents[1]
RAMP = "@%#*+=-:. "


def image_to_ascii(image_path, columns=58, rows=38):
    try:
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError as exc:
        raise ValueError("For image conversion, install Pillow: python3 -m pip install Pillow") from exc
    with Image.open(image_path) as original:
        rgba = ImageOps.exif_transpose(original).convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        resampling = getattr(Image, "Resampling", Image).LANCZOS
        image = ImageOps.fit(background.convert("L"), (348, 348), method=resampling)
        image = image.resize((columns, rows), resample=resampling)
        image = ImageEnhance.Contrast(ImageOps.autocontrast(image, cutoff=1)).enhance(1.08)
        pixels = list(image.getdata())
    return ["".join(RAMP[min(len(RAMP)-1, px * len(RAMP) // 256)]
                    for px in pixels[y*columns:(y+1)*columns]).rstrip() for y in range(rows)]


def generate(config_path, out, avatar_image=None, avatar_text=None, auto_refresh=False, fetch_stats=False):
    config = normalize_config(json.loads(Path(config_path).read_text(encoding="utf-8")))
    if avatar_image and avatar_text:
        raise ValueError("choose either an image or an ASCII avatar")
    if avatar_image:
        avatar = image_to_ascii(avatar_image)
    else:
        avatar = load_avatar(avatar_text or SKILL_ROOT / "assets" / "placeholder-avatar.txt")
    stats = public_stats(config) if fetch_stats else {}
    svg = render(config, avatar, stats)
    readme = build_readme(config)
    out = Path(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError(f"output directory must be empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir()
    (out / "scripts").mkdir()
    (out / "profile-config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "assets" / "profile-avatar.txt").write_text("\n".join(avatar) + "\n", encoding="utf-8")
    (out / "profile.svg").write_text(svg, encoding="utf-8")
    (out / "README.md").write_text(readme, encoding="utf-8")
    shutil.copyfile(SKILL_ROOT / "scripts" / "render_profile.py", out / "scripts" / "render_profile.py")
    if auto_refresh:
        workflow = out / ".github" / "workflows"
        workflow.mkdir(parents=True)
        shutil.copyfile(SKILL_ROOT / "assets" / "refresh-profile.yml", workflow / "refresh-profile.yml")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="profile settings as JSON")
    parser.add_argument("--output", type=Path, required=True, help="new or empty output directory")
    avatars = parser.add_mutually_exclusive_group()
    avatars.add_argument("--avatar-image", type=Path, help="local image; only converted text is copied")
    avatars.add_argument("--avatar-text", type=Path, help="existing ASCII portrait, at most 58x38")
    parser.add_argument("--auto-refresh", action="store_true", help="include daily GitHub Actions workflow")
    parser.add_argument("--fetch-stats", action="store_true", help="fetch public statistics now")
    args = parser.parse_args()
    try:
        target = generate(args.config, args.output, args.avatar_image, args.avatar_text,
                          args.auto_refresh, args.fetch_stats)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Profile creation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Profile generated in {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
