import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'github-profile-terminal'
sys.path.insert(0, str(SKILL / 'scripts'))
import create_profile
import render_profile

CONFIG = {
    'username': 'example-user', 'display_name': 'Alex & 星河',
    'focus': 'Creative tools', 'workflow': 'Codex · design',
    'tagline': 'Keep making things', 'theme': 'violet',
    'projects': [{'name': 'A < B', 'description': '测试 & tools', 'url': 'https://example.com/project?a=1&b=2'}],
    'contacts': [{'label': 'Web', 'value': 'example.com', 'url': 'https://example.com'}],
    'include_forks': False, 'excluded_repos': ['mirror'],
}


class ProfileTests(unittest.TestCase):
    def test_generated_svg_is_valid_xml_and_escapes_user_text(self):
        svg = render_profile.render(CONFIG, ['&<>'], {'repos': 8, 'stars': 17, 'followers': 2})
        ET.fromstring(svg)
        self.assertIn('Alex &amp; 星河', svg)
        self.assertIn('&amp;&lt;&gt;', svg)
        self.assertIn('Repos: 8', svg)
        self.assertIn('Stars: 17', svg)
        self.assertIn('@github', svg)
        readme = render_profile.build_readme(CONFIG)
        self.assertIn('A &lt; B', readme)
        self.assertIn('a=1&amp;b=2', readme)
        self.assertIn('excluding forks', readme)

    def test_invalid_urls_usernames_and_extra_fields_are_rejected(self):
        for changes in ({'username': '../../other'}, {'theme': 'custom'}, {'api_key': 'secret'},
                        {'contacts': [{'label': 'x', 'value': 'x', 'url': 'javascript:alert(1)'}]}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    render_profile.normalize_config({**CONFIG, **changes})

    def test_stats_paginate_and_respect_forks_and_exclusions(self):
        first = [{'name': f'project-{i}', 'fork': False, 'private': False, 'stargazers_count': 2} for i in range(98)]
        first += [{'name': 'forked', 'fork': True, 'private': False, 'stargazers_count': 40},
                  {'name': 'mirror', 'fork': False, 'private': False, 'stargazers_count': 50}]
        second = [{'name': 'next', 'fork': False, 'private': False, 'stargazers_count': 3}]
        with patch.object(render_profile, 'github_json', side_effect=[{'public_repos': 101, 'followers': 7}, first, second]) as api:
            stats = render_profile.public_stats(CONFIG)
        self.assertEqual(stats, {'repos': 101, 'stars': 199, 'followers': 7})
        self.assertEqual(api.call_count, 3)

    def test_generate_is_self_contained_and_never_overwrites_nonempty_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config = base / 'config.json'
            config.write_text(json.dumps(CONFIG), encoding='utf-8')
            out = base / 'profile'
            create_profile.generate(config, out, auto_refresh=True)
            for path in ('README.md', 'profile.svg', 'profile-config.json', 'assets/profile-avatar.txt',
                         'scripts/render_profile.py', '.github/workflows/refresh-profile.yml'):
                self.assertTrue((out / path).is_file(), path)
            ET.parse(out / 'profile.svg')
            result = subprocess.run([sys.executable, 'scripts/render_profile.py'], cwd=out, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            sentinel = out / 'README.md'
            before = sentinel.read_bytes()
            with self.assertRaisesRegex(ValueError, 'must be empty'):
                create_profile.generate(config, out)
            self.assertEqual(sentinel.read_bytes(), before)

    def test_failed_stats_fetch_preserves_existing_svg(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'config.json').write_text(json.dumps(CONFIG), encoding='utf-8')
            (base / 'avatar.txt').write_text('portrait\n', encoding='utf-8')
            (base / 'profile.svg').write_text('keep this', encoding='utf-8')
            argv = ['render_profile.py', '--config', str(base / 'config.json'), '--avatar-text', str(base / 'avatar.txt'),
                    '--output', str(base / 'profile.svg'), '--update']
            with patch.object(sys, 'argv', argv), patch.object(render_profile, 'github_json', side_effect=OSError('offline')):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(render_profile.main(), 1)
            self.assertEqual((base / 'profile.svg').read_text(), 'keep this')

    def test_avatar_image_converted_without_copying_original(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest('Pillow not installed')
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            image = Image.new('RGB', (80, 80), 'white')
            ImageDraw.Draw(image).rectangle((0, 0, 35, 79), fill='black')
            image.save(base / 'portrait.png')
            (base / 'config.json').write_text(json.dumps(CONFIG), encoding='utf-8')
            out = base / 'out'
            create_profile.generate(base / 'config.json', out, avatar_image=base / 'portrait.png')
            lines = (out / 'assets/profile-avatar.txt').read_text().splitlines()
            self.assertEqual(len(lines), 38)
            self.assertTrue(all(len(line) <= 58 for line in lines))
            self.assertTrue(any('@' in line for line in lines))
            self.assertFalse(any(p.suffix.lower() == '.png' for p in out.rglob('*')))
            self.assertFalse((out / '.github').exists())


if __name__ == '__main__':
    unittest.main()
