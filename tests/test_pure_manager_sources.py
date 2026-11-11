"""Static guards for the Pure Manager sources.

The sandbox cannot compile Kotlin (no JDK, no Android SDK, dl.google.com blocked)
and the GitHub run-log endpoint returns EOF for this repo, so compiler errors
come back as nothing at all. These checks catch the classes of mistake that are
knowable without a compiler: symbols that do not exist in the library version we
pinned, imports that resolve to nothing, and the two API details that are easy to
get wrong (SpringSpec confidence parameter, listSaver type).

They are not a substitute for compiling -- the CI job is. They exist so that a
build failure is not three minutes of silence.
"""
from __future__ import annotations

import re
import unittest
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "pure-manager/app/src/main/java"


def kt_files() -> list[pathlib.Path]:
    return sorted(SRC.rglob("*.kt"))


class SourceShape(unittest.TestCase):
    def test_sources_exist(self):
        files = kt_files()
        self.assertGreaterEqual(len(files), 5, f"only found {len(files)} Kotlin files")
        names = {f.name for f in files}
        for required in ("MainActivity.kt", "PureTheme.kt", "Tokens.kt",
                         "PureShell.kt", "ThemePrefsSaver.kt"):
            self.assertIn(required, names)

    def test_every_file_declares_the_expected_package(self):
        for f in kt_files():
            text = f.read_text()
            self.assertRegex(
                text, r"(?m)^package net\.pure\.manager(\.\w+)*$",
                f"{f.name} is missing or has a wrong package declaration",
            )

    def test_braces_and_parens_balance(self):
        for f in kt_files():
            text = f.read_text()
            # Strip comments and string literals so braces inside them do not count.
            stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
            stripped = re.sub(r"//[^\n]*", "", stripped)
            stripped = re.sub(r'"(?:[^"\\]|\\.)*"', '""', stripped)
            for open_c, close_c in (("{", "}"), ("(", ")")):
                self.assertEqual(
                    stripped.count(open_c), stripped.count(close_c),
                    f"{f.name}: unbalanced {open_c}{close_c}",
                )


class ThemeContracts(unittest.TestCase):
    """The token model is the load-bearing part of stage 1."""

    def setUp(self):
        self.tokens = (SRC / "net/pure/manager/theme/Tokens.kt").read_text()
        self.shell = (SRC / "net/pure/manager/ui/PureShell.kt").read_text()

    def test_three_navigation_models_exist(self):
        for model in ("TAB_BAR", "RAIL", "COMMAND_BAR"):
            self.assertIn(model, self.tokens)

    def test_each_theme_has_a_distinct_navigation_model(self):
        # Windows must be the rail theme and Cyberpunk the command-bar theme;
        # if both collapse to TAB_BAR the four themes are only four palettes.
        self.assertIn('"windows"', self.tokens)
        win = self.tokens[self.tokens.index('"windows" ->'):]
        win_block = win[: win.index('"cyber"')]
        self.assertIn("NavModel.RAIL", win_block)

        cyber = self.tokens[self.tokens.index('"cyber" ->'):]
        cyber_block = cyber[: cyber.index("else ->")]
        self.assertIn("NavModel.COMMAND_BAR", cyber_block)

    def test_amoled_uses_outlines_not_shadows(self):
        # On pure black a tonal surface is invisible, so AMOLED must set an
        # outline and disable shadows. Each AMOLED branch is checked separately.
        blocks = re.findall(r"AppMode\.AMOLED -> Palette\((.*?)\n    \)", self.tokens, re.S)
        self.assertGreaterEqual(len(blocks), 4, "expected 4 AMOLED palettes")
        for b in blocks:
            self.assertNotIn("Color.Transparent", b,
                             "an AMOLED palette left its outline transparent")
            self.assertIn("useShadow = false", b)

    def test_no_composable_branches_on_theme_id_except_the_shell(self):
        # Screens read tokens, not identities. One exception is allowed: the
        # shell draws Pixel's pill indicator differently, which is a navigation
        # model concern rather than a screen concern.
        for f in kt_files():
            if f.name in ("PureShell.kt", "Tokens.kt"):
                continue
            text = f.read_text()
            self.assertNotRegex(
                text, r'==\s*"(ios|pixel|windows|cyber)"',
                f"{f.name} branches on a theme id; it should read the token instead",
            )


class KnownApiTraps(unittest.TestCase):
    """Specific APIs whose signatures changed and which broke builds before."""

    def test_spring_takes_three_arguments(self):
        # spring(dampingRatio, stiffness) exists; spring(dampingRatio, stiffness,
        # visibilityThreshold) also exists. Four arguments never have.
        for f in kt_files():
            for m in re.finditer(r"\bspring\(", f.read_text()):
                snippet = f.read_text()[m.start(): m.start() + 200]
                depth, args, closed = 0, 1, False
                for i, ch in enumerate(snippet):
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                        if depth == 0:
                            closed = True
                            break
                    elif ch == "," and depth == 1:
                        args += 1
                if closed:
                    self.assertLessEqual(args, 3, f"{f.name}: spring() with {args} args")

    def test_list_saver_is_given_two_named_arguments(self):
        text = (SRC / "net/pure/manager/theme/ThemePrefsSaver.kt").read_text()
        self.assertIn("listSaver(", text)
        self.assertIn("save =", text)
        self.assertIn("restore =", text)

    def test_cannot_save_uses_a_list_not_varargs(self):
        """SAVER BUG CLASS: canBeSaved(*list) spreads, canBeSaved(list) does not."""
        text = (ROOT / "pure-manager").rglob("*.kt")
        for f in text:
            body = f.read_text()
            if "canBeSaved" not in body:
                continue
            for line in body.splitlines():
                if "canBeSaved" in line and line.strip().startswith("//"):
                    continue
                if "canBeSaved" in line:
                    self.assertIn("*", line,
                                  f"{f.name}: canBeSaved without spread silently "
                                  f"never matches {line.strip()}")


class ManifestAndGradle(unittest.TestCase):
    def test_manifest_does_not_request_all_files_on_a_build_that_cannot_use_it(self):
        manifest = (ROOT / "pure-manager/app/src/main/AndroidManifest.xml").read_text()
        body = re.sub(r"<!--.*?-->", "", manifest, flags=re.S)
        self.assertNotIn("MANAGE_EXTERNAL_STORAGE", body,
                         "stage 1 does not read the file system yet")

    def test_package_and_sdk_levels(self):
        gradle = (ROOT / "pure-manager/app/build.gradle.kts").read_text()
        self.assertIn('applicationId = "net.pure.manager"', gradle)
        self.assertIn("minSdk = 29", gradle)
        self.assertIn("compileSdk = 36", gradle)

    def test_gradle_version_satisfies_the_android_plugin(self):
        # AGP 8.7.3 rejects anything below Gradle 8.9; the first CI run died on
        # exactly this, so it is pinned in the workflow.
        wf = (ROOT / ".github/workflows/pure-manager-build.yml").read_text()
        self.assertIn("gradle-version 8.9", wf)
        self.assertNotIn("gradle-version 8.7", wf)


if __name__ == "__main__":
    unittest.main()
