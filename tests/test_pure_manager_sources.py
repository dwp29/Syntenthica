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


class UnresolvedReferences(unittest.TestCase):
    """The failure that actually broke build #4.

    Kotlin fails with `Unresolved reference` when a type from a sibling package is
    used but not imported. That is a one-line mistake with a 2.5-minute feedback
    loop, and the whole reason build #4 was red: MainActivity used ThemePrefsSaver
    without importing it. This walks every project type and checks each use site
    is either imported, co-located, or fully qualified.
    """

    DECL = re.compile(
        r"(?m)^\s*(?:private |internal |public )?"
        r"(?:data |sealed |enum |abstract |open )?"
        r"(?:class|object|interface|typealias) (\w+)"
    )
    TOPVAL = re.compile(r"(?m)^(?:private |internal |public )?val (\w+)\s*[:=]")

    def declarations(self):
        """name -> package, for every exported type and top-level val."""
        found = {}
        for f in kt_files():
            text = f.read_text()
            pkg = re.search(r"(?m)^package ([\w.]+)", text).group(1)
            for name in self.DECL.findall(text) + self.TOPVAL.findall(text):
                found[name] = (pkg, f.name)
        return found

    def test_project_types_are_imported_where_used(self):
        decls = self.declarations()
        problems = []
        for f in kt_files():
            text = f.read_text()
            pkg = re.search(r"(?m)^package ([\w.]+)", text).group(1)
            imports = set(re.findall(r"(?m)^import ([\w.]+)", text))
            body = re.sub(r"(?m)^import .*$", "", text)
            body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
            body = re.sub(r"//[^\n]*", "", body)
            for name, (home_pkg, home_file) in decls.items():
                if home_pkg == pkg or home_file == f.name:
                    continue
                if not re.search(r"\b" + name + r"\b", body):
                    continue
                if f"{home_pkg}.{name}" in imports:
                    continue
                if re.search(r"\b" + home_pkg + r"\." + name, body):
                    continue  # fully qualified at the use site
                problems.append(f"{f.name}: uses {name} (from {home_pkg}) without import")
        self.assertEqual([], problems, "\n".join(problems))


class Interactions(unittest.TestCase):
    """The bug the owner found on a device: nothing could be tapped.

    Build 0.1.0 compiled cleanly, installed, opened, and was completely inert.
    onPrefs was declared on PureShell and never called; there was not one
    clickable modifier in the file. A compiler cannot see that, and neither could
    any of the checks above, so it is pinned here.
    """

    def setUp(self):
        self.shell = (SRC / "net/pure/manager/ui/PureShell.kt").read_text()

    def test_the_shell_actually_calls_back(self):
        self.assertIn("onPrefs(", self.shell,
                      "onPrefs is declared but never invoked; every control is inert")
        calls = [l for l in self.shell.splitlines()
                 if "onPrefs(" in l and "onPrefs:" not in l]
        self.assertGreaterEqual(len(calls), 5, "expected the theme controls to write prefs")

    def test_there_are_tappable_elements(self):
        # Counting `.clickable` understates it: OptionRow and StepButton each hold
        # one and are reused. Count the reusable rows plus the raw modifiers.
        direct = self.shell.count(".clickable")
        reused = self.shell.count("OptionRow(") + self.shell.count("StepButton(") \
            - 2  # the two declarations
        self.assertGreaterEqual(direct + reused, 12,
                                f"{direct} direct clicks and {reused} reused rows")

    def test_all_four_screens_are_reachable(self):
        for label in ("Berkas", "Tema", "Modul", "Setelan"):
            self.assertIn(label, self.shell, f"screen {label} missing")
        self.assertIn("Screen.entries", self.shell,
                      "navigation must be generated from the screen list, not hand-wired")

    def test_scrollable_content(self):
        self.assertIn("verticalScroll", self.shell,
                      "content longer than the viewport would be unreachable")

    def test_no_hardcoded_font_sizes(self):
        """Build 0.1.0 hardcoded 8.5.sp-22.sp, bypassing the type ramp entirely."""
        matches = re.findall(r"fontSize\s*=", self.shell)
        self.assertEqual([], matches,
                         "text sizes must come from MaterialTheme.typography")

    def test_system_insets_are_applied(self):
        """Edge-to-edge without insets put the title under the status bar."""
        self.assertIn("LocalSystemInsets", self.shell)
        self.assertGreaterEqual(self.shell.count("insets.top"), 2)
        self.assertGreaterEqual(self.shell.count("insets.bottom"), 2)

    def test_type_ramp_is_scaled(self):
        tokens = (SRC / "net/pure/manager/theme/Tokens.kt").read_text()
        for role in ("headlineMedium", "titleLarge", "bodyLarge", "bodySmall", "labelMedium"):
            self.assertIn(role, tokens, f"{role} is not restated in typographyFor")
        self.assertIn("scale)", tokens, "typographyFor ignores its scale argument")


class IosLook(unittest.TestCase):
    """The reference the owner gave: iCloud Drive, with real blur.

    Pins the parts that are easy to lose in a rewrite. Uses Text blocks and
    presence checks rather than counting exact call sites, because the previous
    version of this suite failed on its own arithmetic rather than on the code.
    """

    def setUp(self):
        self.shell = (SRC / "net/pure/manager/ui/PureShell.kt").read_text()
        self.tokens = (SRC / "net/pure/manager/theme/Tokens.kt").read_text()
        self.glass = (SRC / "net/pure/manager/ui/Glass.kt").read_text()

    def test_blur_is_real_and_pinned(self):
        """A translucent rectangle is not glass; the dependency has to be present."""
        gradle = (ROOT / "pure-manager/app/build.gradle.kts").read_text()
        self.assertIn("dev.chrisbanes.haze:haze:", gradle,
                      "no blur library, so 'glass' would be a grey box")
        self.assertIn("hazeChild(", self.glass)
        self.assertIn("blurRadius", self.glass)

    def test_haze_version_matches_the_toolchain(self):
        """Haze 1.2+ requires Kotlin 2.1; this project is on 2.0.21."""
        gradle = (ROOT / "pure-manager/app/build.gradle.kts").read_text()
        version = re.search(r"dev\.chrisbanes\.haze:haze:([\d.]+)", gradle).group(1)
        major, minor, _ = (int(x) for x in version.split("."))
        self.assertLessEqual((major, minor), (1, 1),
                             f"haze {version} needs a newer Kotlin than this project pins")

    def test_glass_is_a_token_not_a_theme_check(self):
        self.assertIn("enum class ChromeStyle", self.tokens)
        self.assertIn("ChromeStyle.GLASS", self.tokens)
        # The chrome decision must come from the spec, never from the id.
        self.assertNotRegex(self.glass, r'"(ios|pixel|windows|cyber)"',
                            "Glass.kt branches on a theme id")

    def test_only_ios_gets_glass_for_now(self):
        ios_block = self.tokens[self.tokens.index('id = "ios"'):]
        end = ios_block.find(chr(41) + chr(10))
        ios_block = ios_block[: end + 2]
        self.assertIn("ChromeStyle.GLASS", ios_block)
        for other in ('id = "pixel"', 'id = "windows"', 'id = "cyber"'):
            block = self.tokens[self.tokens.index(other):]
            end = block.find(chr(41) + chr(10))
            block = block[: end + 2]
            self.assertNotIn("ChromeStyle.GLASS", block,
                             f"{other} should stay solid")

    def test_ios_keeps_its_distinctive_parts(self):
        for token in ("useLargeTitle", "defaultGrid", "floatingAction", "separator"):
            self.assertIn(token, self.tokens)
        self.assertIn("SearchField(", self.shell)
        self.assertIn("IosFolder(", self.shell)
        self.assertGreaterEqual(self.shell.count("GroupCard("), 3)
        self.assertIn("grid = !grid", self.shell, "the grid/list toggle is not wired")

    def test_every_screen_reads_the_type_ramp(self):
        self.assertNotRegex(self.shell, r"fontSize\s*=",
                           "shell went back to hardcoded text sizes")


class NeverDeadOnArrival(unittest.TestCase):
    """0.1.2 force-closed on launch. These pin the ways back in.

    The cause could not be read -- no logcat, no artifact download -- so the app
    now has to survive its own theme system rather than be trusted to.
    """

    def setUp(self):
        self.main = (SRC / "net/pure/manager/MainActivity.kt").read_text()
        self.glass = (SRC / "net/pure/manager/ui/Glass.kt").read_text()
        self.crash = (SRC / "net/pure/manager/PureCrash.kt").read_text()

    def test_crash_recorder_is_installed_before_the_first_frame(self):
        self.assertIn("PureCrash.install(this)", self.main)
        install_at = self.main.index("PureCrash.install(this)")
        content_at = self.main.index("        setContent {")
        self.assertLess(install_at, content_at,
                        "crash recorder must be installed before composition")

    def test_crash_recorder_does_not_swallow_the_crash(self):
        """A handler that never calls through hides the system dialog and tombstones."""
        self.assertIn("previous?.uncaughtException(thread, error)", self.crash)
        self.assertIn("Thread.setDefaultUncaughtExceptionHandler", self.crash)

    def test_blur_is_gated_and_can_be_turned_off(self):
        # A device whose RenderEffect rejects the radius must not be able to kill
        # the process from inside a draw pass.
        self.assertIn("blurSupported", self.glass)
        self.assertIn("SDK_INT >= 31", self.glass)
        self.assertIn("LocalBlurEnabled", self.glass)

    def test_glass_falls_back_to_a_tint_not_to_nothing(self):
        self.assertIn("fallback", self.glass)
        self.assertIn("glassTint", self.glass)

    def test_theme_system_failure_shows_a_screen(self):
        self.assertIn("FallbackScreen", self.main)
        self.assertIn("catch (e: Throwable)", self.main)

    def test_fallback_screen_reads_no_tokens(self):
        """It must render even when the token system is what failed."""
        fallback = (SRC / "net/pure/manager/ui/FallbackScreen.kt").read_text()
        self.assertNotIn("LocalPureSpec", fallback)
        self.assertNotIn("haze", fallback)
        self.assertNotIn("MaterialTheme.typography", fallback)

    def test_blur_pref_survives_rotation(self):
        saver = (SRC / "net/pure/manager/theme/ThemePrefsSaver.kt").read_text()
        self.assertIn("p.blur", saver)
        self.assertIn("blur =", saver)


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
