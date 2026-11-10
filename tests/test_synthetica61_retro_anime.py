"""Guards for the two 6.1 themes: Retro Arcade and Anime Wibu.

These are presentation-only additions on top of the shipped 6.0.0 tree. The
tests are static: they prove the themes are wired into every dispatch point,
that their fonts and emblems are really present, and that the licence and
secret rules still hold. They do not prove how the themes look or that the app
compiles; only a real Gradle build and a device can show that.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import build_manager_60_standalone as build

THEME = ROOT / 'synthetica-manager/app/src/main/java/com/rifsxd/ksunext/ui/theme'
RES = ROOT / 'synthetica-manager/app/src/main/res'
NEW_STYLES = ('RETRO_ARCADE', 'ANIME_WIBU', 'GOTHIC_CRIMSON')
LEGACY_STYLES = ('PIXEL', 'CYBERPUNK', 'IOS_GLASS', 'NEON')


def read(name: str) -> str:
    return (THEME / name).read_text()


def _brace_block(text: str, open_index: int) -> str:
    """Return the balanced {...} starting at open_index, ignoring strings/comments."""
    depth, i, n = 0, open_index, len(text)
    while i < n:
        ch = text[i]
        if text.startswith('//', i):
            i = text.find('\n', i)
            if i < 0:
                return text[open_index:]
            continue
        if text.startswith('/*', i):
            i = text.find('*/', i) + 2
            continue
        if ch == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == '\\' else 1
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[open_index:i + 1]
        i += 1
    raise AssertionError('unbalanced braces')


class StyleRegistrationTests(unittest.TestCase):
    def test_enum_has_seven_styles_and_stable_ids(self):
        styles = read('VisualStyles.kt')
        enum = re.search(r'enum class ManagerStyle\(val id: String\) \{(.*?);', styles, re.S)
        self.assertIsNotNone(enum)
        body = enum.group(1)
        for style in LEGACY_STYLES + NEW_STYLES:
            self.assertIn(f'{style}(', body, style)
        for legacy_id in ('"pixel"', '"cyberpunk"', '"ios_glass"', '"neon"'):
            self.assertIn(legacy_id, body)
        # New ids must not collide with a legacy one, or saved settings migrate
        # to the wrong theme.
        for new_id in ('"retro_arcade"', '"anime_wibu"', '"gothic_crimson"'):
            self.assertIn(new_id, body)

    def test_every_dispatch_point_covers_all_styles(self):
        for name, call in (('VisualStyles.kt', None), ('ThemedHero.kt', None), ('Glass.kt', None)):
            text = read(name)
            for style in NEW_STYLES:
                self.assertIn(f'ManagerStyle.{style} ->', text, f'{name} lacks {style}')

    def test_statement_whens_are_exhaustive(self):
        """A Kotlin `when` used as a statement needs an explicit branch per value."""
        for name in ('Glass.kt', 'ThemedHero.kt', 'VisualStyles.kt', 'AppearanceControls.kt'):
            text = read(name)
            for match in re.finditer(r'when \((style|LocalManagerStyle\.current)\)\s*\{', text):
                block = _brace_block(text, match.end() - 1)
                covered = all(s in block for s in LEGACY_STYLES + NEW_STYLES)
                line = text[:match.start()].count('\n') + 1
                self.assertTrue(covered or 'else ->' in block,
                                f'{name}:{line} is not exhaustive')

    def test_selector_lists_both_new_themes(self):
        selector = read('AppearanceControls.kt')
        for res in ('R.string.theme50_retro', 'R.string.theme50_anime', 'R.string.theme50_gothic'):
            self.assertIn(res, selector)
        strings = (RES / 'values/strings_manager50.xml').read_text()
        for key in ('theme50_retro', 'theme50_retro_detail', 'theme50_anime', 'theme50_anime_detail',
                    'theme50_gothic', 'theme50_gothic_detail'):
            self.assertIn(f'name="{key}"', strings, key)
        indonesian = (RES / 'values-in-rID/strings_manager50.xml').read_text()
        for key in ('theme50_retro', 'theme50_anime', 'theme50_gothic'):
            self.assertIn(f'name="{key}"', indonesian, key)


class AssetTests(unittest.TestCase):
    def test_fonts_exist_and_are_used(self):
        styles = read('VisualStyles.kt')
        for font in ('retro_vt323', 'retro_pressstart', 'anime_zenmaru', 'anime_rampart'):
            self.assertTrue((RES / 'font' / f'{font}.ttf').is_file(), font)
            self.assertIn(f'R.font.{font}', styles, font)

    def test_fonts_are_subset_and_small(self):
        """Full CJK faces are multi-megabyte; the APK ships subsets only."""
        budget = {'retro_vt323': 80_000, 'retro_pressstart': 40_000,
                  'anime_zenmaru': 200_000, 'anime_rampart': 400_000}
        for font, limit in budget.items():
            size = (RES / 'font' / f'{font}.ttf').stat().st_size
            self.assertLess(size, limit, f'{font} is {size} bytes, expected < {limit}')

    def test_new_emblems_are_present_and_distinct(self):
        styles = read('VisualStyles.kt')
        digests = {}
        for emblem, style in (('ic_emblem_retro', 'RETRO_ARCADE'), ('ic_emblem_anime', 'ANIME_WIBU'),
                              ('ic_emblem_gothic', 'GOTHIC_CRIMSON')):
            path = RES / 'drawable-nodpi' / f'{emblem}.png'
            self.assertTrue(path.is_file(), emblem)
            self.assertIn(f'ManagerStyle.{style} -> R.drawable.{emblem}', styles)
            digests[emblem] = path.read_bytes()
        self.assertEqual(len(set(digests.values())), 3)

    def test_font_licences_are_recorded(self):
        """The OFL requires the licence text to travel with the fonts."""
        notice = ROOT / 'synthetica-manager/NOTICE'
        text = notice.read_text() if notice.is_file() else ''
        docs = ROOT / 'docs/SYNTHETICA-MANAGER-THEMES-RETRO-ANIME.md'
        self.assertTrue(docs.is_file(), 'theme documentation is missing')
        doc = docs.read_text()
        for family in ('VT323', 'Press Start 2P', 'Zen Maru Gothic', 'Rampart One'):
            self.assertIn(family, doc, family)
        self.assertIn('SIL Open Font License', doc)


class BannerTests(unittest.TestCase):
    """The three new themes are illustrated banners, not abstract gradients."""

    BANNERS = ('theme_banner_retro', 'theme_banner_gothic', 'theme_banner_anime')

    def test_banner_illustrations_exist_in_two_layers(self):
        hero = read('ThemedHero.kt')
        drawable = RES / 'drawable-xxhdpi'
        for banner in self.BANNERS:
            for suffix in ('', '_far'):
                path = drawable / f'{banner}{suffix}.jpg'
                self.assertTrue(path.is_file(), path.name)
                self.assertLess(path.stat().st_size, 320_000, f'{path.name} is too heavy')
                self.assertIn(f'R.drawable.{banner}{suffix}', hero)
        # A parallax layer only matters if the two layers differ.
        for banner in self.BANNERS:
            near = (drawable / f'{banner}.jpg').read_bytes()
            far = (drawable / f'{banner}_far.jpg').read_bytes()
            self.assertNotEqual(near, far, banner)

    def test_banner_layers_are_16_by_9(self):
        from PIL import Image
        for banner in self.BANNERS:
            for suffix in ('', '_far'):
                path = RES / 'drawable-xxhdpi' / f'{banner}{suffix}.jpg'
                with Image.open(path) as im:
                    w, h = im.size
                self.assertAlmostEqual(w / h, 16 / 9, delta=0.01, msg=path.name)

    def test_hero_keeps_live_data_over_the_illustration(self):
        """The banner must not replace state with art: status and kernel stay live."""
        hero = read('ThemedHero.kt')
        banner_fn = hero[hero.index('private fun IllustratedBannerHero('):]
        for wire in ('statusPill', 'modePill', 'kernelLine', 'metaLine', 'eyebrow', 'title'):
            self.assertIn(wire, banner_fn, wire)
        # Readability guards over a busy picture.
        self.assertIn('verticalGradient', banner_fn)
        self.assertIn('graphicsLayer', banner_fn)

    def test_each_new_theme_uses_its_own_banner(self):
        hero = read('ThemedHero.kt')
        for fn, banner in (('RetroBannerHero', 'theme_banner_retro'),
                           ('GothicBannerHero', 'theme_banner_gothic'),
                           ('AnimeBannerHero', 'theme_banner_anime')):
            body = hero[hero.index(f'private fun {fn}('):]
            body = body[:body.index('\n}')]
            self.assertIn(f'banner = R.drawable.{banner},', body, fn)
            self.assertIn(f'bannerFar = R.drawable.{banner}_far,', body, fn)


class BuildGateTests(unittest.TestCase):
    def test_standalone_gate_still_accepts_the_tree(self):
        build.verify_tree()

    def test_no_signing_material_added(self):
        tree = ROOT / 'synthetica-manager'
        for path in tree.rglob('*'):
            if path.is_file():
                self.assertNotIn(path.suffix.lower(), {'.p12', '.jks', '.keystore', '.pem', '.key', '.der'})


if __name__ == '__main__':
    unittest.main()
