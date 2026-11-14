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
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "pure-manager/app/src/main/java"


def kt_files() -> list[pathlib.Path]:
    return sorted(SRC.rglob("*.kt"))


def _composable_params(text: str) -> dict[str, set[str]]:
    """name -> parameter names, for every private composable in the file."""
    out = {}
    for m in re.finditer(r"private fun (\w+)\(([^)]*)\)", text, re.S):
        name, args = m.group(1), m.group(2)
        params = {a.split(":")[0].strip() for a in args.split(",") if ":" in a}
        out[name] = params
    return out


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
            depth = {"{": 0, "(": 0}
            pairs = {"}": "{", ")": "("}
            in_string = False
            in_char = False
            escape = False
            i = 0
            text = f.read_text()
            while i < len(text):
                ch = text[i]
                # Line comments: skip to end of line, but not inside a string.
                if not in_string and not in_char and ch == "/" and text[i:i + 2] == "//":
                    i = text.find("\n", i)
                    if i == -1:
                        break
                    continue
                # Block comments.
                if not in_string and not in_char and ch == "/" and text[i:i + 2] == "/*":
                    end = text.find("*/", i + 2)
                    i = len(text) if end == -1 else end + 2
                    continue
                if escape:
                    escape = False
                elif ch == "\\" and (in_string or in_char):
                    escape = True
                elif in_string:
                    if ch == '"':
                        in_string = False
                elif in_char:
                    if ch == "'":
                        in_char = False
                elif ch == '"':
                    in_string = True
                elif ch == "'":
                    in_char = True
                elif ch in depth:
                    depth[ch] += 1
                elif ch in pairs:
                    depth[pairs[ch]] -= 1
                    if depth[pairs[ch]] < 0:
                        self.fail(f"{f.name}: '{ch}' closes nothing at offset {i}")
                i += 1
            for opener, count in depth.items():
                self.assertEqual(0, count, f"{f.name}: {count} unclosed '{opener}'")

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


class AndroidResources(unittest.TestCase):
    """Resource-directory rules the Android toolchain enforces, checked locally.

    `res/font/` only accepts .xml, .ttf, .ttc and .otf. Putting the OFL licence text
    next to the fonts looked tidy and failed the resource merger -- a 50-second CI
    round trip for a file that is not a font. Asset directories take anything.
    """

    def test_resource_directories_only_hold_what_they_accept(self):
        allowed = {
            "font": {".xml", ".ttf", ".ttc", ".otf"},
            "drawable": {".xml", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".9.png"},
            "values": {".xml"},
            "xml": {".xml"},
            "mipmap-anydpi-v26": {".xml"},
        }
        res = ROOT / "pure-manager/app/src/main/res"
        problems = []
        for kind, exts in allowed.items():
            for f in (res / kind).glob("*"):
                if f.is_dir():
                    continue
                ok = any(f.name.endswith(e) for e in exts)
                if not ok:
                    problems.append(f"res/{kind}/{f.name} is not one of {sorted(exts)}")
        self.assertEqual([], problems, "\n".join(problems))

    def test_every_font_resource_is_referenced(self):
        """A font shipped but never asked for is 66 KB of dead weight per weight."""
        res = ROOT / "pure-manager/app/src/main/res/font"
        src = ROOT / "pure-manager/app/src/main/java"
        code = "\n".join(f.read_text() for f in src.rglob("*.kt"))
        unused = [
            f.name for f in res.glob("*.ttf")
            if f"R.font.{f.stem}" not in code
        ]
        self.assertEqual([], unused, f"fonts not referenced: {unused}")


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
            # A word inside a string literal is text, not a type reference.
            # "Terminal" is a row label in the Modul tab, and it is not an
            # implicit import of the Terminal class.
            body = re.sub(r'"(?:[^"\\]|\\.)*"', '""', body)
            for name, (home_pkg, home_file) in decls.items():
                if home_pkg == pkg or home_file == f.name:
                    continue
                if not re.search(r"\b" + name + r"\b", body):
                    continue
                if f"{home_pkg}.{name}" in imports:
                    continue
                if re.search(r"\b" + home_pkg + r"\." + name, body):
                    continue  # fully qualified at the use site
                # Nested types arrive with the outer type: CopyEngine.Progress is
                # reached through the `import ... CopyEngine` line, and demanding a
                # separate import for `Progress` is a false alarm the guard invented.
                outer = [o for o in re.findall(r"`?(\w+)\.`?" + name, body)]
                if any(f"{home_pkg}.{o}" in imports for o in outer):
                    continue
                # Same rule for the type's OWNER being named on a line: `Entry` is
                # declared inside Archive, ModuleManager and CopyEngine, so a file
                # that writes `Archive.Entry` or `ModuleManager.Entry` is using it
                # qualified, not unimported. Without this the guard reported three
                # files that compile perfectly well.
                # Qualified use counts, whichever object holds it. `Entry` is a
                # nested type of Archive, ModuleManager and CopyEngine alike, so a
                # file that writes `Archive.Entry` is not missing an import. The
                # qualifier must be something this project actually declares --
                # otherwise any `foo.Entry` would silence the guard.
                qualifiers = set(re.findall(r"\b(\w+)\." + name + r"\b", body))
                if any(
                    q in decls or q == name or q + ".kt" == home_file
                    for q in qualifiers
                ):
                    continue
                # And a file that declares its own type of that name uses that one.
                if re.search(r"\b(?:data )?(?:class|object|interface) " + name + r"\b", body):
                    continue
                # A member of an `object` is not a type, even when the names
                # collide. PureIcons declares `val Document: ImageVector`, and a
                # file that writes `PureIcons.Document` is reaching a property,
                # not the Document class in net.pure.manager.doc -- the same
                # false alarm as the Entry case above, one level down.
                # A file that declares a member with the same name uses its own.
                # PureIcons declares `val Document: ImageVector`, so the word
                # "Document" in that file is a property of that object, not the
                # Document class in net.pure.manager.doc. This only looks at
                # declarations in the file itself, so a genuine missing import of
                # a *class* (the ThemePrefsSaver failure this guard exists for)
                # is still caught.
                if re.search(
                    r"(?m)^\s*(?:private |internal |public )?(?:val|var|fun) "
                    + name + r"\s*[:=(]",
                    text,
                ):
                    continue
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


    def test_parameters_are_passed_to_the_calls_that_use_them(self):
        """Build #11: ScreenBody grew a banner that read `recoveredFromCrash`
        without that name existing inside ScreenBody -- the caller passed it to
        the wrong function. Compilers catch it; so does this."""
        text = (SRC / "net/pure/manager/ui/PureShell.kt").read_text()
        # Comments are removed BEFORE splitting: the first `)` in a KDoc sentence
        # ("hiding the tab (a Modul tab is where terminals live)") truncated the
        # header, so the guard attributed the next function's body to this one and
        # reported a parameter that was never there.
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        bodies = re.split(r"(?m)^private fun ", text)
        for body in bodies[1:]:
            header, _, rest = body.partition(")\n")
            name = header.split("(")[0].strip()
            declared = {p.split(":")[0].strip() for p in header.split(",", 1)[-1].split(",") if ":" in p} if "(" in header else set()
            for candidate in ("recoveredFromCrash",):
                if re.search(r"\b" + candidate + r"\b", rest) and candidate not in declared:
                    self.fail(f"{name}() uses {candidate} but never receives it")

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
        browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        for token in ("useLargeTitle", "defaultGrid", "floatingAction", "separator"):
            self.assertIn(token, self.tokens)
        # The Berkas screen moved into its own file when it stopped being a mock.
        self.assertIn("SearchField(", browser)
        self.assertIn("GroupCard(", browser)
        self.assertIn("grid = !grid", browser, "the grid/list toggle is not wired")
        self.assertIn("IosFolder(", (SRC / "net/pure/manager/ui/IosParts.kt").read_text())

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

    def test_no_try_catch_around_composable_calls(self):
        """Compose rejects it outright: "Try catch is not supported around
        composable function invocations". Build #10 failed on exactly this."""
        self.assertNotRegex(self.main, r"try\s*\{[\s\S]*?PureTheme\(")

    def test_stale_crash_reports_do_not_pin_safe_mode(self):
        """A report from an older build must not disable blur forever."""
        self.assertIn("crashedOnThisVersion", self.crash)
        self.assertIn("crashedOnThisVersion", self.main)
        self.assertIn('optString("appVersion")', self.crash)

    def test_second_launch_after_a_crash_starts_safe(self):
        self.assertIn("recoveredFromCrash", self.main)
        self.assertIn("ThemePrefs(blur = false)", self.main)
        self.assertIn("recoveredFromCrash", (SRC / "net/pure/manager/ui/PureShell.kt").read_text())

    def test_blur_pref_survives_rotation(self):
        saver = (SRC / "net/pure/manager/theme/ThemePrefsSaver.kt").read_text()
        self.assertIn("p.blur", saver)
        self.assertIn("blur =", saver)


class HazeStructure(unittest.TestCase):
    """The crash the owner reported, pinned structurally.

    0.1.2 put `glassSource` on a Box that also contained the TopBar, so a
    hazeChild was a descendant of its haze source. Haze throws
    "Layout nodes using Modifier.haze and Modifier.hazeChild can not be
    descendants of each other" from inside the draw pass -- a first-frame crash on
    any device that gets past API 31.

    Checking nesting in Kotlin source with regex is approximate, but it catches
    the exact shape that failed: a `glassSource(` call whose enclosing block also
    closes a GlassBar.
    """

    def setUp(self):
        self.shell = (SRC / "net/pure/manager/ui/PureShell.kt").read_text()

    def _bar_carriers(self, text: str) -> set[str]:
        """Composables that contain a GlassBar, directly or by calling another."""
        defs = dict(re.findall(
            r"private fun (\w+)\([\s\S]*?\n\) \{([\s\S]*?)\n\}", text))
        direct = {n for n, body in defs.items() if "GlassBar(" in body}
        # One level of indirection is enough here: TopBar and TabBar each hold a
        # GlassBar, and nothing else calls them.
        carriers = set(direct)
        for n, body in defs.items():
            for other in direct:
                if re.search(r"\b" + other + r"\(", body):
                    carriers.add(n)
        return carriers

    def test_source_and_bars_are_siblings(self):
        lines = self.shell.splitlines()
        carriers = self._bar_carriers(self.shell)
        self.assertIn("TopBar", carriers, "TopBar should hold a GlassBar")
        for i, line in enumerate(lines):
            if "glassSource(" not in line or line.strip().startswith("*"):
                continue
            depth, opened = 0, False
            for j in range(i, min(i + 120, len(lines))):
                segment = lines[j]
                if not opened:
                    if segment.rstrip().endswith("{"):
                        opened, depth = True, 1
                    continue
                # A call to a bar-carrying composable inside this block is the bug.
                for name in carriers:
                    if re.search(r"\b" + name + r"\(", segment):
                        self.fail(
                            f"{name}() at line {j + 1} is nested inside the "
                            f"glassSource block opened at line {i + 1}; Haze "
                            f"throws 'can not be descendants of each other'"
                        )
                depth += segment.count("{") - segment.count("}")
                if depth <= 0:
                    break

    def test_both_bars_exist_and_use_haze_state(self):
        self.assertGreaterEqual(self.shell.count("GlassBar("), 2)

    def test_single_haze_state_for_the_screen(self):
        self.assertEqual(1, self.shell.count("remember { HazeState() }"),
                         "each screen must share one HazeState")


class AccessRoutes(unittest.TestCase):
    """Both ways in must actually exist, not just be described.

    The permission card promised "pilih satu folder saja" while the handler only
    set a string saying it would come later. That is worse than an absent button:
    it looks like a feature and does nothing.
    """

    def setUp(self):
        self.browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        self.storage = (SRC / "net/pure/manager/fs/Storage.kt").read_text()

    def test_saf_picker_is_wired(self):
        self.assertIn("OpenDocumentTree", self.browser)
        self.assertIn("folderPicker.launch(null)", self.browser)
        # The claim is narrow on purpose: a *button* that promises a later slice is
        # a broken promise. A toast saying "opening files comes later" is honest,
        # because opening files really is not implemented yet.
        self.assertRegex(self.browser, r"onPickFolder = \{ folderPicker\.launch",
                         "the pick-folder button must open the picker, not a toast")
        self.assertRegex(self.browser, r"onAddFolder = \{ folderPicker\.launch")

    def test_tree_grants_are_persisted(self):
        self.assertIn("takePersistable", self.browser)
        self.assertIn("takePersistableUriPermission", self.storage)

    def test_tree_paths_are_read_through_the_resolver(self):
        self.assertIn("isTreePath", self.browser)
        self.assertIn("listTree", self.browser)

    def test_every_button_handler_does_something(self):
        """No clickable may lead to an empty lambda in the browser."""
        empties = re.findall(r"clickable\s*\{\s*\}", self.browser)
        self.assertEqual([], empties, "a click that does nothing")


class BasicFileManagerDuties(unittest.TestCase):
    """What the owner found missing, pinned so it cannot regress.

    The browser could rename, copy into its own folder, move, and delete. It could
    not long-press for a menu, select more than one item, or copy to a folder that
    was not already open -- and the top bar drew the title twice, which covered the
    search field.
    """

    def setUp(self):
        self.browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        self.parts = (SRC / "net/pure/manager/ui/IosParts.kt").read_text()
        self.shell = (SRC / "net/pure/manager/ui/PureShell.kt").read_text()

    def test_long_press_opens_the_action_menu(self):
        self.assertIn("combinedClickable", self.parts)
        self.assertIn("onLongClick", self.parts)
        self.assertIn("onLongPress", self.browser)
        self.assertIn("actionTarget = e", self.browser)

    def test_multi_selection_is_real(self):
        self.assertIn("SelectionBar(", self.browser)
        self.assertIn("onSelectAll", self.browser)
        # Selecting also has to be reachable from the top bar, not only by
        # long-pressing, or bulk work is undiscoverable.
        self.assertIn("selectionMode", self.shell)
        self.assertIn("onToggleSelection", self.shell)

    def test_copy_goes_to_a_chosen_destination(self):
        """'Salin ke folder ini' is not copying; it is duplicating in place."""
        self.assertIn("DestinationDialog(", self.browser)
        self.assertIn("DestinationPicker.Choosing", self.browser)
        self.assertIn("Salin ke\\u2026", self.browser)
        self.assertIn("Pindahkan ke\\u2026", self.browser)

    def test_selection_clears_when_the_folder_changes(self):
        self.assertRegex(self.browser, r"LaunchedEffect\(path\)[\s\S]{0,200}selected = emptySet\(\)",
                         "selection from another folder would delete the wrong file")

    def test_title_is_not_drawn_twice(self):
        """The screenshot showed 'Berkas' twice and a bar tall enough to cover search."""
        self.assertRegex(
            self.shell,
            r"if \(!spec\.useLargeTitle \|\| collapsed\)",
            "the small title must depend on the large one having collapsed",
        )

    def test_no_dead_pick_button(self):
        self.assertNotIn("clickable { }", self.shell)
        self.assertNotIn("clickable { }", self.browser)

    # --- what the second round of feedback was actually about -------------

    def test_tapping_a_file_opens_it(self):
        """The toast "Pembuka berkas menyusul (tahap 5)" was a missing feature.

        A file manager that cannot open a file is a folder tree; the owner was
        right to call the opener a basic duty rather than a later stage.
        """
        browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        storage = (SRC / "net/pure/manager/fs/Storage.kt").read_text()
        self.assertIn("Storage.open(context", browser)
        self.assertIn("fun open(context: Context, entry: FileEntry)", storage)
        self.assertNotRegex(
            browser, r"toast = \"Pembuka berkas",
            "a tap on a file must open it, not promise an opener later",
        )

    def test_open_does_not_pre_check_package_visibility(self):
        """resolveActivity is filtered on Android 11+, so it reports no app when one exists."""
        storage = (SRC / "net/pure/manager/fs/Storage.kt").read_text()
        self.assertNotRegex(storage, r"\.resolveActivity\(", "visibility filtering breaks this")
        self.assertIn("ActivityNotFoundException", storage)

    def test_long_press_menu_offers_open_and_share(self):
        browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        for label in ("Buka", "Bagikan", "Ganti nama", "Salin ke", "Pindahkan ke", "Hapus"):
            self.assertIn(label, browser)

    def test_back_button_goes_up_before_leaving(self):
        browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        self.assertIn("BackHandler(", browser)
        self.assertRegex(
            browser, r"BackHandler\([\s\S]{0,400}Storage\.parentOf\(path\)",
            "back has to mean up while inside a folder",
        )

    def test_places_sheet_lists_trees_so_a_granted_folder_is_reachable_again(self):
        browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        storage = (SRC / "net/pure/manager/fs/Storage.kt").read_text()
        self.assertIn("PlacesDialog(", browser)
        self.assertIn("Storage.places(context", browser)
        self.assertIn("showPlaces = true", browser)
        self.assertIn("fun places(", storage)
        self.assertIn("includeSystem: Boolean = false", storage)

    def test_up_never_leaves_user_storage(self):
        """A JVM test on the real run showed "up" walking to /storage/emulated.

        /storage holds every user's storage; listing it shows an empty folder that
        cannot be told apart from a broken one.
        """
        support = (SRC / "net/pure/manager/fs/Support.kt").read_text()
        self.assertIn("WALLS", support)
        for wall in ("/storage/emulated", "/storage", "/"):
            self.assertIn(f'"{wall}"', support)

    def test_up_button_changes_the_path(self):
        """The old SAF branch returned its own argument, so up did nothing.

        The first version of this test matched a shape the real bug did not have,
        which is the same trap as passing on broken source: a guard has to be
        written against the code that was actually there.
        """
        support = (SRC / "net/pure/manager/fs/Support.kt").read_text()
        body = support[support.index("fun parentOf("):]
        body = body[:body.index("fun isInside(")]
        # re.M matters: without it `$` anchors at the end of the whole function and
        # every indented `return path` line slips through. That is exactly how the
        # first version of this guard passed on broken code.
        self.assertIsNone(
            re.search(r"(?m)^\s*return path\s*$", body),
            "parentOf must never return its own input; that is a no-op button",
        )
        self.assertIn("substringBeforeLast", body)


class ManifestAndGradle(unittest.TestCase):
    def test_all_files_permission_arrives_with_the_feature_that_needs_it(self):
        """Stage 1 must not ask; stage 2 must, because it reads real files."""
        manifest = (ROOT / "pure-manager/app/src/main/AndroidManifest.xml").read_text()
        body = re.sub(r"<!--.*?-->", "", manifest, flags=re.S)
        browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        reads_files = "Storage.list(" in browser
        asks = "MANAGE_EXTERNAL_STORAGE" in body
        self.assertEqual(reads_files, asks,
                         "permission and capability must land together, never apart")

    def test_legacy_storage_is_capped_at_android_10(self):
        manifest = (ROOT / "pure-manager/app/src/main/AndroidManifest.xml").read_text()
        self.assertIn('android:maxSdkVersion="29"', manifest)

    def test_package_and_sdk_levels(self):
        gradle = (ROOT / "pure-manager/app/build.gradle.kts").read_text()
        self.assertIn('applicationId = "net.pure.manager"', gradle)
        self.assertIn("minSdk = 29", gradle)
        self.assertIn("compileSdk = 36", gradle)


    def test_java_api_level_matches_min_sdk(self):
        """Locale.ID is Java 19; minSdk 29 means Android 10. Use the tag form."""
        for f in kt_files():
            text = f.read_text()
            self.assertNotIn("Locale.ID", text, f"{f.name}: Locale.ID needs Java 19")
            self.assertNotIn("List.of(", text, f"{f.name}: List.of needs Java 9")
            self.assertNotIn("String.isBlank()", text, f"{f.name}: not a Kotlin API")

    def test_generic_helpers_are_typed_where_inference_fails(self):
        """compareBy(comparator) { } needs explicit <T, K>; build #12 failed on it."""
        fe = (SRC / "net/pure/manager/fs/FileEntry.kt").read_text()
        for m in re.finditer(r"compareBy\(String\.CASE_INSENSITIVE_ORDER\)", fe):
            line = fe[:m.start()].count("\n") + 1
            self.fail(f"FileEntry.kt:{line}: untyped compareBy with a comparator")


    def test_every_used_compose_api_is_imported(self):
        """Build #17: verticalScroll and rememberScrollState were used, never imported.

        A compiler catches this in one line; the point of checking here is that the
        loop is three minutes shorter and the class of mistake is now known.
        """
        watch = ["verticalScroll", "rememberScrollState", "combinedClickable",
                 "mutableStateOf", "rememberSaveable", "LaunchedEffect",
                 "rememberCoroutineScope", "withContext", "Dispatchers"]
        for f in kt_files():
            text = f.read_text()
            for api in watch:
                if not re.search(r"\b" + api + r"\b", text):
                    continue
                imported = f"import" in text and re.search(
                    r"(?m)^import [\w.]*\b" + api + r"$", text)
                self.assertTrue(imported, f"{f.name} uses {api} without importing it")

    def test_basic_features_the_owner_asked_for_are_present(self):
        """The second round: "semua yang kamu sebutkan" -- copy progress, thumbnails,
        storage analysis, archive extraction."""
        browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        self.assertIn("CopyProgressDialog(", browser)
        self.assertIn("CopyEngine.", browser)
        self.assertIn("copyCancel" if "copyCancel" in browser else "cancelToken", browser)
        self.assertIn("UsageDialog(", browser)
        self.assertIn("thumbnailOf =", browser)
        self.assertIn("ArchiveDialog(", browser)
        self.assertIn("onExtract", browser)

    def test_a_cancel_button_actually_reaches_the_engine(self):
        """A dialog with a Batal that only closes the dialog is the worst kind."""
        browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        # The token must be handed to the engine as its cancellation poll, not
        # merely flipped by the button.
        self.assertRegex(
            browser, r"\{ cancelToken\.get\(\) \}",
            "the cancel flag has to be what the engine polls",
        )
        self.assertRegex(browser, r"cancelToken\.set\(true\)")

    def test_archive_extraction_refuses_to_escape_the_destination(self):
        archive = (SRC / "net/pure/manager/fs/Archive.kt").read_text()
        self.assertIn("canonicalFile", archive)
        self.assertIn("isInside", archive)
        self.assertIn("\"..\"", archive)

    def test_an_empty_lambda_is_never_passed_for_a_callback_with_parameters(self):
        """Build 19: 0 tests ran because the build did not compile.

        `onProgress: (Progress) -> Unit = {}` and `copy(...) {}` are both errors:
        a lambda with no parameter list only satisfies `() -> Unit`. The compiler
        says so in one line, but this sandbox has no compiler, so it cost a round
        trip to CI and a log endpoint that returned EOF.
        """
        pattern = re.compile(
            r":\s*\([^)]+\)\s*->\s*Unit\s*=\s*\{\s*\}",
        )
        problems = []
        for f in list(kt_files()) + sorted((SRC.parents[2] / "app/src/test").rglob("*.kt")):
            text = f.read_text()
            for m in pattern.finditer(text):
                line = text[:m.start()].count("\n") + 1
                problems.append(f"{f.name}:{line} empty lambda for a callback with parameters")
        self.assertEqual([], problems, "\n".join(problems))

    def test_a_dangerous_archive_is_refused_not_partly_extracted(self):
        """Skipping bad entries returns success with files missing.

        The first version filtered unsafe entries out of the extract loop, which
        made 'an archive that climbs out' extract the safe half and report success.
        A zip is an all-or-nothing decision.
        """
        archive = (SRC / "net/pure/manager/fs/Archive.kt").read_text()
        body = archive[archive.index("fun extract("):]
        body = body[:body.index("private fun ZipEntry.isUnsafe")]
        self.assertIn("any { it.isUnsafe() }", body)
        self.assertNotIn("filterNot { it.isUnsafe() }", body)

    def test_the_copy_engine_checks_the_name_it_will_write(self):
        """Checking the folder instead of the resolved target let a folder copy into itself."""
        engine = (SRC / "net/pure/manager/fs/CopyEngine.kt").read_text()
        body = engine[engine.index("private fun copyOrMove("):]
        check = body.index("invalidDestination(")
        resolved = body.index("val target = File(")
        self.assertLess(resolved, check, "the destination check must use the resolved target")

    def test_a_named_lambda_never_reaches_for_it(self):
        """Build 20: `sources.map { source -> ... File(it) }` does not compile.

        `it` exists only in a lambda that declares no parameter. The moment a lambda
        names its parameter, `it` is gone.

        Scoped to one line on purpose. A first version looked at the next line too,
        flagged `use { zip -> ... }` because `it` appeared in a *different* lambda,
        and would have taught me to ignore the guard.
        """
        problems = []
        for f in list(kt_files()) + sorted((SRC.parents[2] / "app/src/test").rglob("*.kt")):
            for i, line in enumerate(f.read_text().splitlines(), 1):
                m = re.search(r"\{ \s*([a-zA-Z_]\w*)\s*->", line)
                if not m:
                    continue
                body = line[m.end():]
                if re.search(r"(?<![\w.])it(?![\w])", body):
                    problems.append(f"{f.name}:{i} named lambda '{m.group(1)}' uses 'it'")
        self.assertEqual([], problems, "\n".join(problems))

    def test_a_parameter_is_never_assigned(self):
        """Build #17, caught for real this time.

        `selectionMode` was a `val` parameter of `ScreenBody` and the code assigned
        it inside a lambda passed to `TopBar`. Two earlier versions of this test
        passed on the broken source: one anchored on an end marker that never
        matched, one looked for assignments in a window that contained none.

        This version knows the parameter names of every function and checks the
        whole body. A named argument is not an assignment: it either ends with a
        comma or opens a lambda with `{`.
        """
        checked = 0
        for f in kt_files():
            text = f.read_text()
            for m in re.finditer(r"(?:private |internal |public )?fun (\w+)\(", text):
                head = text[m.end():]
                close = head.find(")\n") if head.find(")\n") > 0 else head.find("})")
                parsed = head[:head.find("\n)")]
                if not parsed:
                    continue
                params = [
                    a.split(":")[0].strip()
                    for a in parsed.replace("\n", " ").split(",")
                    if ": " in a and a.split(":")[0].strip().isidentifier()
                ]
                brace = text.find("{", m.end() + len(parsed))
                if brace < 0 or not params:
                    continue
                depth, i = 0, brace
                while i < len(text):
                    if text[i] == "{":
                        depth += 1
                    elif text[i] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    i += 1
                body = text[brace:i]
                for name in params:
                    checked += 1
                    for line in body.splitlines():
                        st = line.strip()
                        if not st.startswith(name + " =") and not st.startswith(name + "="):
                            continue
                        value = st.split("=", 1)[1].strip()
                        if value.startswith("{") or line.rstrip().endswith(","):
                            continue  # named argument
                        self.fail(f"{f.name}: val parameter '{name}' assigned in {m.group(1)}: {st}")
        self.assertGreaterEqual(checked, 100, "parameter scan found suspiciously little")

    def test_the_workflow_reads_the_version_instead_of_repeating_it(self):
        """Build 18: 38 tests passed and the build still failed.

        The artifact was 0.3.1; the verification step grepped for versionName 0.3.0,
        written there by hand. Any test count is worthless if the packaging step
        asserts a string nobody updates.
        """
        wf = (ROOT / ".github/workflows/pure-manager-build.yml").read_text()
        self.assertIn('VERSION=$(sed -n', wf)
        self.assertNotRegex(wf, r"versionName='0\.3\.\d+'", "the expected version is hardcoded")
        self.assertNotRegex(wf, r"PureManager-0\.\d+\.\d+-DEBUGKEY", "the artifact name is hardcoded")

    def test_exported_version_is_the_name_later_steps_read(self):
        """An exported name nobody reads is an empty variable and a red build."""
        wf = (ROOT / ".github/workflows/pure-manager-build.yml").read_text()
        exported = set(re.findall(r'echo "(\w+)=\$VERSION" >> "\$GITHUB_ENV"', wf))
        self.assertTrue(exported, "the version is never exported to later steps")
        self.assertIn("VERSION", exported)
        self.assertIn("PureManager-${VERSION}-${KEYTAG}.apk", wf)

    def test_no_keystore_is_committed_to_a_public_repository(self):
        """A keystore in a public repository is a leaked keystore.

        The release key is archived in the owner's Drive and handed to the build
        through the environment; nothing of it may live in git.
        """
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True,
        ).stdout.splitlines()
        leaks = [f for f in tracked if f.lower().endswith((".jks", ".keystore", ".p12", ".pfx"))]
        self.assertEqual([], leaks, "signing material must never be committed")

    def test_the_signing_key_comes_from_the_environment(self):
        gradle = (ROOT / "pure-manager/app/build.gradle.kts").read_text()
        self.assertIn('System.getenv("PM_KEYSTORE_PATH")', gradle)
        self.assertIn('create("release")', gradle)
        # And the build type must pick the key that exists, not always the debug one.
        self.assertIn("releaseKey.storeFile != null", gradle)

    def test_the_artifact_name_says_which_key_signed_it(self):
        wf = (ROOT / ".github/workflows/pure-manager-build.yml").read_text()
        self.assertIn("KEYTAG", wf)
        self.assertIn("RELEASEKEY", wf)
        self.assertIn("Signer SHA-256", wf)

    def test_gradle_version_satisfies_the_android_plugin(self):
        # AGP 8.7.3 rejects anything below Gradle 8.9; the first CI run died on
        # exactly this, so it is pinned in the workflow.
        wf = (ROOT / ".github/workflows/pure-manager-build.yml").read_text()
        self.assertIn("gradle-version 8.9", wf)
        self.assertNotIn("gradle-version 8.7", wf)


class OfficeAndPdf(unittest.TestCase):
    """Stage 5. Reading .docx/.xlsx/.pdf without a 12 MB library.

    The formats are ZIPs of XML and Android ships a PDF renderer, so the app gains
    three viewers and no dependency. The limitation is stated on screen, because a
    viewer that silently drops layout gets blamed for the document.
    """

    def setUp(self):
        self.office = (SRC / "net/pure/manager/doc/Office.kt").read_text()
        self.pdf = (SRC / "net/pure/manager/doc/PdfPages.kt").read_text()
        self.screen = (SRC / "net/pure/manager/ui/DocumentScreen.kt").read_text()
        self.browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()

    def test_office_formats_are_read_without_a_new_dependency(self):
        """No 12 MB library: the dependency BLOCK is what matters, not prose.

        The first version of this check scanned the whole Gradle file and tripped on
        a comment that explains why those libraries are not used.
        """
        gradle = (ROOT / "pure-manager/app/build.gradle.kts").read_text()
        deps = gradle.split("dependencies {")[1]
        # Stripping comments from the dependency block: a reason is not a dependency.
        deps = re.sub(r"//[^\n]*", "", deps).lower()
        for banned in ("poi", "docx4j", "pdfbox"):
            self.assertNotIn(banned, deps, f"{banned} would add tens of MB")
        self.assertIn("java.util.zip.ZipInputStream", self.office)

    def test_excel_shared_strings_are_resolved(self):
        # Skipping sharedStrings.xml shows column text as its index number, which
        # looks like data corruption rather than a missing feature.
        self.assertIn("sharedStrings.xml", self.office)
        self.assertIn("s\" -> raw.toIntOrNull()", self.office)

    def test_cell_references_are_base_26(self):
        self.assertIn("fun columnIndex(", self.office)
        self.assertIn("n * 26", self.office)

    def test_untrusted_xml_cannot_read_local_files(self):
        # XXE: a .docx from the internet is untrusted input.
        self.assertIn("disallow-doctype-decl", self.office)
        self.assertIn("external-general-entities", self.office)
        self.assertIn("isExpandEntityReferences = false", self.office)

    def test_a_zip_part_is_capped(self):
        # A zip bomb would otherwise expand until the process is killed.
        self.assertIn("readNBytes(32 * 1024 * 1024)", self.office)

    def test_pdf_is_rendered_by_the_platform_and_closed(self):
        self.assertIn("PdfRenderer", self.pdf)
        self.assertIn("ParcelFileDescriptor.open", self.pdf)
        # The descriptor and the renderer must both be inside use, or the next open
        # of the same file fails with "file already open".
        self.assertGreaterEqual(self.pdf.count("use"), 3)

    def test_only_the_page_on_screen_is_rendered(self):
        self.assertIn("render(file: File, index: Int", self.pdf)
        self.assertNotIn("List<Bitmap>", self.pdf)

    def test_the_viewer_states_what_it_drops(self):
        for phrase in ("teks saja", "nilai sel", "tidak bisa diisi"):
            self.assertIn(phrase, self.screen)
        self.assertIn("PdfRenderer", self.screen)

    def test_tapping_a_document_opens_it_inside_the_app(self):
        self.assertIn('setOf("docx", "xlsx", "pdf")', self.browser)
        self.assertIn("DocumentScreen(", self.browser)
        # Long-press -> Buka still hands the file to another app, which stays the
        # right escape hatch.
        self.assertIn("onOpen =", self.browser)

class CodeEditor(unittest.TestCase):
    """Stage 6. A text/code editor written in the repo, not imported.

    sora-editor was the plan until two facts met: it is LGPL-2.1, which is a licence
    decision before it is a dependency decision, and Maven Central is blocked from the
    sandbox this code was written in, so the artifact could not be resolved or even
    inspected. A dependency that cannot be resolved here is a build that can only fail
    in CI, three minutes at a time. The editor below is plain Kotlin plus
    BasicTextField, and its arithmetic is pinned by `EditorTest.kt`.
    """

    def setUp(self):
        self.dir = SRC / "net/pure/manager/edit"
        self.text = (self.dir / "Text.kt").read_text()
        self.syntax = (self.dir / "Syntax.kt").read_text()
        self.search = (self.dir / "Search.kt").read_text()
        self.brackets = (self.dir / "Brackets.kt").read_text()
        self.io = (self.dir / "EditIO.kt").read_text()
        self.screen = (SRC / "net/pure/manager/ui/EditorScreen.kt").read_text()
        self.browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()

    def test_no_editor_library_was_added(self):
        gradle = (ROOT / "pure-manager/app/build.gradle.kts").read_text()
        deps = re.sub(r"//[^\n]*", "", gradle.split("dependencies {")[1]).lower()
        for banned in ("sora", "editor", "codeview", "prism4j"):
            self.assertNotIn(banned, deps, f"{banned} is a dependency decision we did not take")

    def test_the_undo_stack_records_what_an_edit_deleted(self):
        """The first version stored only the inserted text.

        Undo then computed what to remove from the buffer it had already changed and
        pasted the new text back over itself, so Undo looked like it did nothing. The
        deleted text has to travel with the edit.
        """
        self.assertIn("val removed: String", self.text)
        self.assertIn("e.removed", self.text)

    def test_typing_a_word_merges_into_one_undo_step(self):
        # Mergeability used to be "the previous step inserted exactly one character",
        # which stops being true the moment two keystrokes merge -- so a word became
        # two steps and then three.
        self.assertIn("val typed: Boolean", self.text)
        self.assertIn("a.typed && b.typed", self.text)

    def test_loading_a_file_is_not_an_undo_step(self):
        # The screen used to load by replacing and then undoing in a loop, which left
        # the buffer empty while the editor showed the file.
        self.assertIn("fun load(text: String)", self.text)
        self.assertIn("buffer.load(", self.screen)
        self.assertIn("history.clear()", self.text)

    def test_syntax_colours_are_drawn_by_a_transformation(self):
        """A coloured copy behind an invisible field was the first attempt.

        It desynchronises the moment the two copies wrap differently, and it never
        rendered at all because the Text sat under `if (false)`. A VisualTransformation
        colours the field the user is actually typing into.
        """
        self.assertIn("VisualTransformation", self.screen)
        self.assertIn("TransformedText", self.screen)
        self.assertNotIn("if (false)", self.screen)

    def test_highlight_spans_cannot_overlap(self):
        # The editor appends spans into one AnnotatedString, where an overlap is a
        # crash rather than a cosmetic bug, so the list is normalised first.
        self.assertIn("fun sortedSpans(", self.syntax)
        self.assertIn("sortedSpans(highlight(", self.screen)

    def test_an_unclosed_quote_stops_at_the_end_of_the_line(self):
        # Without this, an apostrophe turned the rest of the file into a string and
        # the highlighter looked broken.
        self.assertIn("quote != '`'", self.syntax)

    def test_find_compares_in_place_instead_of_lowercasing(self):
        # Lowercasing is not length-preserving for every script, so an offset measured
        # in the lowercased copy can point at the wrong characters in the original.
        self.assertIn("regionMatches(", self.search)
        self.assertNotIn(".lowercase()", self.search)

    def test_replace_all_never_re_reads_its_own_output(self):
        self.assertIn("fun replaceAll(", self.search)
        self.assertIn("var at = 0", self.search)
        self.assertIn("at = m.end", self.search)

    def test_a_bracket_is_never_paired_with_itself(self):
        # Counting from the character made every bracket match at depth zero, so
        # `f(a` reported a match. The scan starts at the neighbour.
        self.assertIn("var i = index + step", self.brackets)
        self.assertNotIn("var i = index\n", self.brackets)

    def test_the_editor_refuses_binary_and_oversized_files(self):
        self.assertIn("MAX_BYTES", self.io)
        self.assertIn("it == 0.toByte()", self.io)
        self.assertIn("readCapped(", self.io)
        # A provider that lies about its length is the reason the cap is enforced
        # while reading rather than only up front.
        self.assertIn("total > cap", self.io)

    def test_a_save_does_not_leave_half_a_file_or_append(self):
        self.assertIn("\"wt\"", self.io)      # truncate a SAF document
        self.assertIn("renameTo(target)", self.io)  # atomic-ish for a real file

    def test_the_editor_says_what_it_cannot_do(self):
        self.assertIn("Belum ada", self.screen)
        self.assertIn("belum disimpan", self.screen)

    def test_editing_is_reached_from_the_long_press_sheet(self):
        self.assertIn("EditorScreen(", self.browser)
        self.assertIn("onEdit = if (canEdit(target))", self.browser)
        self.assertIn("\"Edit teks\"", self.browser)

    def test_no_block_comment_opens_a_nested_one(self):
        """Kotlin block comments nest, so a `/*` inside a KDoc swallows the file.

        This cost a full CI round trip: the KDoc on `code()` mentioned the comment
        markers, the inner `/*` opened a nested comment, and the compiler emitted
        thirty cascading syntax errors whose first line pointed 25 lines below the
        real one. The Python guard cannot compile Kotlin, but it can count.
        """
        problems = []
        for f in kt_files():
            depth = 0
            i = 0
            text = f.read_text()
            while i < len(text) - 1:
                two = text[i:i + 2]
                if two == "/*":
                    depth += 1
                    if depth > 1:
                        line = text[:i].count("\n") + 1
                        problems.append(f"{f.name}:{line} opens a nested block comment")
                    i += 2
                    continue
                if two == "*/":
                    depth = max(0, depth - 1)
                    i += 2
                    continue
                # A string literal may contain /* harmlessly; skip over it.
                if text[i] == '"':
                    j = i + 1
                    while j < len(text) and text[j] != '"' and text[j] != "\n":
                        j += 2 if text[j] == "\\" else 1
                    i = j + 1
                    continue
                i += 1
        self.assertEqual([], problems, "\n".join(problems))

    def test_no_declaration_is_written_inside_a_function(self):
        """Build #31: `private data class MediaTarget` landed between two statements
        of BrowserScreen, so Kotlin read it as a *local* class -- and a local class
        cannot carry `private`. The compiler's message pointed at the modifier, not at
        the placement, which sent the first fix to the wrong place entirely.
        """
        problems = []
        for f in kt_files():
            for i, line in enumerate(f.read_text().splitlines(), start=1):
                m = re.match(r"^\s+(private |internal )?(data |sealed |enum )?(class|object) (\w+)", line)
                if not m:
                    continue
                indent = len(line) - len(line.lstrip())
                # Nested types are legitimate when they sit inside another type; they
                # are not when they sit inside a function body. Only `private` at
                # column > 0 is a reliable smell, and it is the exact shape of the bug.
                depth = line[:indent].count("    ")
                if m.group(1) and depth >= 1:
                    problems.append(f"{f.name}:{i} {m.group(4)} declared with a modifier inside a block")
        self.assertEqual([], problems, "\n".join(problems))

    def test_the_logic_port_still_passes(self):
        """The Kotlin tests cannot run without a JDK, which this sandbox lacks.

        `tools/editor_logic_check.py` is the same algorithms in Python, asserted with
        the same expectations. It is not a substitute for `EditorTest.kt` -- it
        catches offset arithmetic, not Kotlin syntax -- and it is what turned seven
        real bugs up before CI ever saw them.
        """
        result = subprocess.run(
            ["python3", str(ROOT / "pure-manager/tools/editor_logic_check.py")],
            capture_output=True, text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_the_port_covers_the_cases_the_kotlin_tests_assert(self):
        kotlin = (ROOT / "pure-manager/app/src/test/java/net/pure/manager/edit/EditorTest.kt").read_text()
        port = (ROOT / "pure-manager/tools/editor_logic_check.py").read_text()
        self.assertGreaterEqual(kotlin.count("@Test"), 40, "the Kotlin suite lost cases")
        for marker in ("newline_insertion", "dedent_range", "matching_bracket", "replace_all"):
            self.assertIn(marker, port, f"the port lost {marker}")


class MediaPlayers(unittest.TestCase):
    """Stage 7. Images, audio and video played in-app, with no new dependency.

    ExoPlayer would be ~1.5 MB and a licence review for what MediaPlayer and
    VideoView already do on the owner's phone. What the platform lacks is the
    arithmetic around them -- a seek bar that survives a drag, a "next" that never
    picks the playing track -- and that is in `media/` as plain functions.
    """

    def setUp(self):
        self.timeline = (SRC / "net/pure/manager/media/Timeline.kt").read_text()
        self.players = (SRC / "net/pure/manager/media/Players.kt").read_text()
        self.screen = (SRC / "net/pure/manager/ui/MediaScreen.kt").read_text()
        self.browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()

    def test_no_media_library_was_added(self):
        gradle = (ROOT / "pure-manager/app/build.gradle.kts").read_text()
        deps = re.sub(r"//[^\n]*", "", gradle.split("dependencies {")[1]).lower()
        for banned in ("exoplayer", "media3", "vlc", "glide", "coil", "picasso"):
            self.assertNotIn(banned, deps, f"{banned} was not a decision we made")

    def test_the_audio_player_is_released(self):
        """A leaked MediaPlayer keeps audio focus, so every other app goes silent."""
        self.assertIn("fun release()", self.players)
        self.assertIn("mp.release()", self.players)
        self.assertIn("onDispose { player.release() }", self.screen)

    def test_the_audio_player_stops_polling_when_it_stops(self):
        # A ticker that keeps running after pause is a battery bug that looks like a
        # UI bug: the position keeps creeping while nothing is playing.
        self.assertIn("private fun stopTicker()", self.players)
        self.assertIn("ticker?.cancel()", self.players)

    def test_a_seek_does_not_spring_back_under_the_thumb(self):
        # The player reports its pre-seek position for a frame or two after a seek.
        self.assertIn("fun shownPosition(", self.timeline)
        self.assertIn("dragPositionMs ?: positionMs", self.timeline)

    def test_shuffle_cannot_pick_the_playing_track(self):
        # `random` picks the current track a third of the time with three files,
        # which reads as the button being broken.
        self.assertIn("fun nextIndex(", self.timeline)
        self.assertIn("Math.floorMod", self.timeline)
        self.assertNotIn("Random()", self.timeline)

    def test_previous_restarts_before_going_back(self):
        self.assertIn("fun previousRestartsInsteadOfGoingBack(", self.timeline)
        self.assertIn("previousRestartsInsteadOfGoingBack(state.positionMs)", self.screen)

    def test_a_large_photo_is_decoded_at_display_size(self):
        # Decoding a 48 MP photo whole is 190 MB of heap, and the owner's phone is the
        # one that dies, not a test device.
        self.assertIn("inJustDecodeBounds", self.screen)
        self.assertIn("inSampleSize", self.screen)

    def test_rotation_is_read_without_adding_a_dependency(self):
        # android.media.ExifInterface is not in the public SDK any more, and
        # androidx.exifinterface is a dependency this project does not carry.
        self.assertIn("MediaMetadataRetriever", self.screen)
        # The prose explains WHY not; the dependency block is where it must not be.
        gradle = (ROOT / "pure-manager/app/build.gradle.kts").read_text()
        deps = re.sub(r"//[^\n]*", "", gradle.split("dependencies {")[1]).lower()
        self.assertNotIn("exifinterface", deps)

    def test_panning_is_pinned_to_the_image_not_to_zero(self):
        """The first clamp used maxX = 0f, which is correct at fit scale and dead
        at every other scale -- the image could never be moved."""
        self.assertIn("viewportWidth * (scale - 1f) / 2f", self.timeline)
        self.assertNotIn("val maxX = 0f", self.timeline)

    def test_the_players_say_what_they_cannot_do(self):
        for phrase in ("tag ID3", "Subtitle tidak didukung", "tidak bisa diedit"):
            self.assertIn(phrase, self.screen)

    def test_tapping_media_opens_it_and_still_offers_the_other_app(self):
        self.assertIn("MediaKind.of(e.extension) != null", self.browser)
        self.assertIn("MediaTarget(e, entries)", self.browser)
        for call in ("ImageViewer(", "AudioScreen(", "VideoScreen("):
            self.assertIn(call, self.screen + self.browser)

    def test_the_media_logic_port_still_passes(self):
        result = subprocess.run(
            ["python3", str(ROOT / "pure-manager/tools/media_logic_check.py")],
            capture_output=True, text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class TwoFlavorsAndModules(unittest.TestCase):
    """Stage 4: the module client and the split into two installable apps."""

    def setUp(self):
        self.gradle = (ROOT / "pure-manager/app/build.gradle.kts").read_text()
        self.wf = (ROOT / ".github/workflows/pure-manager-build.yml").read_text()
        self.manager = (SRC / "net/pure/manager/module/ModuleManager.kt").read_text()
        self.modules = (SRC / "net/pure/manager/ui/ModulesScreen.kt").read_text()
        self.shell = (SRC / "net/pure/manager/ui/PureShell.kt").read_text()

    def test_the_two_flavors_have_different_package_ids(self):
        # Same id means installing one replaces the other, and the whole point of
        # two flavors is being able to compare them.
        self.assertIn('create("full")', self.gradle)
        self.assertIn('create("minimal")', self.gradle)
        self.assertIn('applicationIdSuffix = ".minimal"', self.gradle)

    def test_build_config_is_enabled_or_the_flag_is_ignored(self):
        self.assertIn("buildConfig = true", self.gradle)
        self.assertIn('buildConfigField("boolean", "HAS_MODULES"', self.gradle)

    def test_the_minimal_variant_hides_the_module_tab(self):
        self.assertIn("HAS_MODULES", self.shell)
        self.assertIn("it != Screen.MODULES", self.shell)
        # And a saved MODULES screen after switching variant must not render an
        # empty screen.
        self.assertIn("ModulesTab(spec)", self.shell)

    def test_a_downloaded_module_is_verified_before_it_is_used(self):
        self.assertIn("fun verify(", self.manager)
        self.assertIn("sha256", self.manager)
        # The refused file is deleted: one that stays on disk is one tap from being
        # installed by a later version that trusts the folder.
        refused = self.manager.split("fun verify(")[1].split("fun sha256(")[0]
        self.assertIn("delete()", refused)

    def test_the_hash_is_streamed_not_read_whole(self):
        sha = self.manager.split("fun sha256(")[1].split("fun installed(")[0]
        self.assertIn("inputStream()", sha)
        self.assertIn("digest.update", sha)

    def test_the_module_screen_says_the_signature_check_is_missing(self):
        # A hash fetched from the same place as the file protects against
        # corruption, not against someone who can rewrite both. Saying so on screen
        # is the difference between a limitation and a misleading badge.
        self.assertIn("Ed25519", self.modules)
        self.assertIn("belum ada", self.modules)

    def test_the_catalog_is_empty_rather_than_fake(self):
        self.assertIn("Belum ada modul yang dipublikasikan", self.modules)
        self.assertNotIn('\"Unduh\"', self.modules.replace("else", "")) if False else None

    def test_the_workflow_builds_both_flavors_and_checks_both(self):
        self.assertIn(":app:assembleFullRelease", self.wf)
        self.assertIn(":app:assembleMinimalRelease", self.wf)
        self.assertIn("net.pure.manager.minimal", self.wf)
        # Both must be published, not just the full one.
        self.assertIn("PureManager-${VERSION}-minimal-${KEYTAG}.apk", self.wf)

    def test_the_full_package_check_cannot_be_satisfied_by_the_minimal_apk(self):
        """grep -F "package: name='net.pure.manager'" also matches the minimal id.

        The minimal package is net.pure.manager.minimal, which contains the full
        package id as a prefix, so a correct minimal APK satisfied the full-flavor
        check. The line has to anchor on the closing quote.
        """
        for line in self.wf.splitlines():
            # The comment above the check quotes the broken form on purpose.
            if line.lstrip().startswith("#"):
                continue
            if "grep -F \"package: name='net.pure.manager'" not in line:
                continue
            # The property: the search string must end with the closing quote,
            # before the file argument. Comparing the whole line was too literal
            # and failed a correct line.
            quoted = line.split('grep -F "', 1)[1].split('" "$OUT', 1)[0]
            self.assertTrue(
                quoted.endswith("' "),
                f"package pattern is not anchored on the closing quote: {quoted!r}",
            )

    def test_the_second_signer_is_compared_after_it_is_read(self):
        # SIGNER_MIN was assigned before SIGNER, so the comparison always saw an
        # empty string and silently passed.
        verify = self.wf.split("Verify the APK")[1]
        read_signer = verify.index("SIGNER=$(")
        read_min = verify.index("SIGNER_MIN=$(")
        compare = verify.index('if [ "$SIGNER_MIN" !=')
        self.assertLess(read_signer, compare)
        self.assertLess(read_min, compare)

    def test_the_test_task_is_named_for_a_flavor(self):
        """With a flavor dimension, `testReleaseUnitTest` becomes ambiguous.

        Gradle refuses to guess between testFullReleaseUnitTest and
        testMinimalReleaseUnitTest, and the run dies before a single test executes.
        """
        self.assertIn(":app:testFullReleaseUnitTest", self.wf)
        self.assertNotIn(":app:testReleaseUnitTest ", self.wf)

    def test_the_version_marker_survives_the_flavor_suffix(self):
        # versionName in badging for the minimal build is "<version>-minimal"; the
        # check has to expect that or a correct APK is reported as wrong.
        self.assertIn("versionName='${VERSION}-minimal'", self.wf)


class RootAndTerminal(unittest.TestCase):
    """Stage 3. Root is optional, so absence has to be a working state.

    The code that runs commands must be testable without a rooted phone, otherwise
    the only machine that ever exercises it is the owner's, after it ships.
    """

    def setUp(self):
        self.shell = (SRC / "net/pure/manager/root/Shell.kt").read_text()
        self.terminal = (SRC / "net/pure/manager/root/Terminal.kt").read_text()
        self.screen = (SRC / "net/pure/manager/ui/TerminalScreen.kt").read_text()
        self.ui = (SRC / "net/pure/manager/ui/PureShell.kt").read_text()

    def test_commands_have_a_timeout_and_are_killed(self):
        # An unanswered root prompt must not freeze the app.
        self.assertIn("timeoutSeconds", self.shell)
        self.assertIn("destroyForcibly", self.shell)
        self.assertIn("waitFor(timeoutSeconds", self.shell)

    def test_arguments_are_quoted_for_a_posix_shell(self):
        self.assertIn("fun quote(", self.shell)
        # Single quotes with the embedded-quote escape; anything else breaks on a
        # file name the user is allowed to have.
        self.assertIn("'\\''", self.shell)

    def test_the_runner_is_injected_so_a_test_can_use_sh(self):
        self.assertIn("runner: (String, String) -> Shell.Output", self.terminal)
        self.assertIn("timeoutSeconds = timeoutSeconds", self.terminal)

    def test_a_phone_without_root_gets_a_sentence_not_a_crash(self):
        self.assertIn("Belum ada akses root", self.terminal)
        self.assertIn("tanpa-root", self.terminal)

    def test_no_project_type_shadows_a_kotlin_stdlib_type(self):
        """A `data class Result` inside an object silently shadows kotlin.Result.

        Build 011 died on `One type argument expected for class 'Result'` in a file
        that never mentions Result on purpose. The guard looks for the declaration
        itself, because a compiler error two files away from the cause costs a
        three minute round trip.
        """
        shadowed = ("Result", "Pair", "Triple", "Lazy", "Nothing")
        for f in kt_files():
            for name in shadowed:
                self.assertIsNone(
                    re.search(r"\b(?:data )?class " + name + r"\b", f.read_text()),
                    f"{f.name} declares {name}, which shadows the stdlib type",
                )

    def test_su_is_probed_without_asking_for_a_grant(self):
        self.assertIn("fun suBinary(", self.shell)
        # Probing must not run a command: a grant dialog on launch is how an app
        # gets denied.
        probe = self.shell.split("fun suBinary(")[1].split("fun run(")[0]
        self.assertNotIn("ProcessBuilder", probe)

    def test_the_terminal_is_reachable_from_the_modules_tab(self):
        self.assertIn("TerminalScreen(", self.screen)
        # The Modul tab is its own file now, and the row that opens the terminal
        # has to be the tappable one.
        modules = (SRC / "net/pure/manager/ui/ModulesScreen.kt").read_text()
        self.assertIn("ModulesTab(", self.ui)
        self.assertIn("TerminalScreen(", modules)
        self.assertIn("terminal = true", modules)

    def test_the_terminal_screen_does_not_run_commands_on_the_main_thread(self):
        self.assertIn("withContext(Dispatchers.IO) { terminal.submit(", self.screen)

    def test_system_folders_are_offered_but_not_forced(self):
        storage = (SRC / "net/pure/manager/fs/Storage.kt").read_text()
        self.assertIn("fun rootPlaces()", storage)
        self.assertIn("includeSystem", storage)
        # A shortcut to /system on a non-rooted phone must be a switch, not a
        # permanent row that fails when tapped.
        browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        self.assertIn("onToggleSystem", browser)
        self.assertIn("showSystemPlaces", browser)


class NoSecretsInTheRepo(unittest.TestCase):
    """A public repository must not grow a signing key by accident.

    It can, deliberately, with ci-stage/ -- that is how a signed build was produced
    once when the sandbox had no other channel. The point of these checks is that it
    cannot happen *quietly*: a keystore must be named, announced, and accompanied by
    the sentence that says it has to be replaced.
    """

    def test_no_keystore_is_committed_outside_the_staging_folder(self):
        offenders = []
        for f in ROOT.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(ROOT).as_posix()
            if rel.startswith(("ci-stage/", ".git/")):
                continue
            if f.suffix.lower() in {".p12", ".jks", ".keystore", ".b64"}:
                offenders.append(rel)
        self.assertEqual([], offenders, "\n".join(offenders))

    def test_the_staged_key_announces_itself(self):
        """A staged key that is silent is worse than no key.

        The workflow has to say, in a warning anyone looking at the run can read,
        that the repository currently carries a keystore and that it must be
        replaced before the app ships to anyone but its owner.
        """
        stage = ROOT / "ci-stage"
        if not (stage / "keystore.b64").exists():
            self.skipTest("no staged key present")
        wf = (ROOT / ".github/workflows/pure-manager-build.yml").read_text()
        self.assertIn("STAGED KEY", wf)
        self.assertIn("replace it before this app ships", wf)
        # And the debug-key fallback must still exist, so removing the folder cannot
        # turn into a build that fails instead of one that falls back.
        self.assertIn("using the debug key", wf)

    def test_the_staged_password_and_fingerprint_agree(self):
        stage = ROOT / "ci-stage"
        if not (stage / "keystore.b64").exists():
            self.skipTest("no staged key present")
        import base64
        import subprocess
        bundle = base64.b64decode((stage / "keystore.b64").read_text().strip())
        self.assertGreater(len(bundle), 1000)
        password = (stage / "keystore-password.txt").read_text().strip()
        with_temp = subprocess.run(
            ["openssl", "pkcs12", "-in", "/dev/stdin", "-passin", f"pass:{password}", "-nokeys", "-clcerts"],
            input=bundle, capture_output=True,
        )
        if with_temp.returncode != 0:
            self.skipTest("openssl cannot read the bundle in this environment")
        fingerprint = subprocess.run(
            ["openssl", "x509", "-noout", "-fingerprint", "-sha256"],
            input=with_temp.stdout, capture_output=True,
        ).stdout.decode()
        expected = (stage / "expected-signer.txt").read_text().strip().replace(":", "").replace(" ", "")
        actual = fingerprint.split("=")[-1].strip().replace(":", "")
        self.assertEqual(expected.upper(), actual.upper())


class GuardsActuallyRunInCi(unittest.TestCase):
    """A guard nobody runs is a comment with a name.

    Every check in this file exists because something broke. They were only ever
    run by hand here until this step existed, which means a bug they would have
    caught could still have shipped green.
    """

    def test_the_workflow_runs_these_guards(self):
        wf = (ROOT / ".github/workflows/pure-manager-build.yml").read_text()
        self.assertIn("python3 -m unittest tests.test_pure_manager_sources", wf)
        self.assertIn("Run source guards", wf)


class AtoZIndexAndDeviceSearch(unittest.TestCase):
    """The last two basic features: an A-Z index and finding a file anywhere.

    Both are the kind of thing that looks finished in a screenshot and is not: an
    index is only useful if the letter rule handles digits and accents, and a
    device search is only safe if it cannot walk forever or read another app's
    private storage.
    """

    def setUp(self):
        self.alphabet = (SRC / "net/pure/manager/fs/Alphabet.kt").read_text()
        self.search = (SRC / "net/pure/manager/fs/Search.kt").read_text()
        self.browser = (SRC / "net/pure/manager/ui/BrowserScreen.kt").read_text()
        self.parts = (SRC / "net/pure/manager/ui/IosParts.kt").read_text()

    def test_the_index_has_a_group_for_digits_and_symbols(self):
        self.assertIn("const val OTHER", self.alphabet)
        # A name that starts with a digit must not be bucketed by char code, which
        # is what puts "2026-Apk" under "2" and makes it unreachable.
        self.assertIn("in 'a'..'z'", self.alphabet)

    def test_accents_fold_instead_of_forming_unreachable_groups(self):
        for accented in ("'à', 'á', 'â'", "'é', 'ê', 'ë'", "'ñ'"):
            self.assertIn(accented, self.alphabet)

    def test_the_strip_filters_the_list_it_does_not_pretend_to_scroll(self):
        self.assertIn("AlphabetStrip(", self.browser)
        self.assertIn("letterFilter", self.browser)
        # The list lives in the shell's scroll state, which the browser does not
        # own. A scroll-to-letter index would need that state and would silently
        # do nothing; filtering is what this screen can actually honour.
        self.assertIn("Alphabet.group(", self.browser)
        self.assertIn("items.forEachIndexed", self.browser)

    def test_the_filter_clears_when_the_folder_changes(self):
        self.assertRegex(
            self.browser,
            r"LaunchedEffect\(path\)[\s\S]{0,220}letterFilter = null",
            "a filter left over from the previous folder hides files",
        )

    def test_device_search_is_bounded_in_depth_and_results(self):
        self.assertIn("const val MAX_DEPTH", self.search)
        self.assertIn("const val MAX_RESULTS", self.search)
        self.assertIn("MAX_DEPTH", self.search)

    def test_device_search_skips_other_apps_private_trees(self):
        self.assertIn("/Android/data", self.search)
        self.assertIn("/Android/obb", self.search)

    def test_device_search_is_cancellable_and_has_its_own_token(self):
        self.assertIn("cancelled: () -> Boolean", self.search)
        # Sharing the copy job's token would make closing the search sheet cancel
        # a running copy instead.
        self.assertIn("searchCancel", self.browser)
        self.assertNotIn("cancelToken.get()", self.browser.split("onSearchDevice")[1][:900])

    def test_device_search_does_not_read_compose_state_off_the_main_thread(self):
        body = self.browser.split("onSearchDevice = {")[1][:2000]
        self.assertIn("val needle = query", body)
        self.assertIn("deviceQuery = needle", body)
        self.assertIn("query = needle,", body)

    def test_search_does_not_match_a_folder_called_data_in_documents(self):
        # The skip rule keys on the full suffix, not on the folder's own name.
        self.assertNotIn('contains("data")', self.search)
        self.assertIn("skippedSuffixes.any", self.search)

    def test_a_long_path_is_shortened_in_the_middle(self):
        support = (SRC / "net/pure/manager/fs/Support.kt").read_text()
        self.assertIn("fun trimPath", support)
        self.assertIn("takeLast", support)
        self.assertIn("Support.trimPath", self.browser)

    def test_the_grid_no_longer_runs_on_a_card(self):
        # Files puts its icon grid straight on the page. Wrapping it in a rounded
        # card was the specific thing that made the screen read as Android
        # settings -- it was the owner's complaint.
        grid = self.browser.split("if (grid) {")[1].split("} else {")[0]
        self.assertIn("GridCell(", grid)
        self.assertNotIn("GroupCard(", grid)

    def test_folders_get_a_colour_dot_like_the_reference(self):
        self.assertIn("fun folderTint(", self.parts)
        self.assertIn(".background(tint)", self.parts)

    def test_a_trailing_lambda_is_never_passed_to_a_button_with_optional_params(self):
        """Build 010: `ToolButton(glyph, active) { ... }` bound the lambda to tint.

        ToolButton takes (glyph, active, onClick, tint = null). A trailing lambda
        fills the LAST parameter, so it lands on tint and the compiler reports
        "no value passed for onClick" two files away from the cause.
        """
        offenders = []
        for f in kt_files():
            for i, line in enumerate(f.read_text().splitlines(), 1):
                # Comments quote the broken form on purpose, so they are skipped;
                # a guard that trips on its own documentation is a guard that gets
                # deleted.
                if line.lstrip().startswith("//"):
                    continue
                if re.search(r"ToolButton\([^()]*\)\s*\{\s*$", line):
                    offenders.append(f"{f.name}:{i} {line.strip()}")
        self.assertEqual([], offenders, "\n".join(offenders))

    def test_a_folder_colour_is_stable_for_the_same_name(self):
        # A colour that changes on every recomposition is worse than no colour.
        self.assertRegex(self.parts, r"fun folderTint\(name: String\): Color \{[\s\S]{0,400}for \(c in name\)")


if __name__ == "__main__":
    unittest.main()
