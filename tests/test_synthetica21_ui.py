"""Host-side regression checks for UI source (not Android UI tests)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "build-kit/ci/build_manager_cyberbrutal_patch.py"
OVERLAY = ROOT / "build-kit/ci/ksun-cyberbrutal"
spec = importlib.util.spec_from_file_location("cyberbrutal_patcher", PATCHER)
assert spec is not None and spec.loader is not None
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


def luminance(rgb: str) -> float:
    channels = [int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class AboutUiSourceTests(unittest.TestCase):
    def test_about_is_bounded_scrollable_and_contains_credits_and_reporting(self):
        about = (OVERLAY / "component/AboutCard.kt").read_text()
        self.assertEqual(about.count("ContributorsSection()"), 1)
        # The second occurrence is the private function declaration.
        self.assertEqual(about.count("IssueReportSection()"), 2)
        self.assertIn("Dialog(onDismissRequest = dismiss)", about)
        self.assertIn("IconButton(onClick = onDismiss", about)
        self.assertIn(".heightIn(max = maxDialogHeight)", about)
        self.assertIn(".verticalScroll(rememberScrollState())", about)
        self.assertIn("MaterialTheme.colorScheme", about)
        self.assertIn("brutalPlate(active = true)", about)
        self.assertIn("KernelSU-Next (GPL-3.0)", about)
        for name in ("issue_report_title", "issue_report_body", "issue_report_body_2",
                     "issue_report_github_link", "issue_report_telegram_link"):
            self.assertIn("R.string." + name, about)
        self.assertIn("uriHandler.openUri(githubIssueUrl)", about)
        self.assertIn("uriHandler.openUri(telegramUrl)", about)
        self.assertIn("UPSTREAM // KERNELSU-NEXT", about)

    def test_all_upstream_credits_and_destinations_are_preserved(self):
        credits = (OVERLAY / "component/ContributorsSection.kt").read_text()
        blocks = re.findall(r"    Contributor\(\n(.*?)    \),", credits, re.DOTALL)
        records = []
        for block in blocks:
            records.append(dict(re.findall(r'(\w+)\s*=\s*"([^"\n]*)"', block)))
        expected = [
            ("rifsxd", "Rifat Azad", "Lead Developer", "https://github.com/rifsxd", "https://github.com/KernelSU-Next/KernelSU-Next/tree/dev?tab=readme-ov-file#-donations"),
            ("tiann", "Weishu", "KernelSU Author", "https://github.com/tiann", "https://www.patreon.com/weishu"),
            ("fatalcoder524", None, "Frontend Maintainer", "https://github.com/fatalcoder524", "https://github.com/sponsors/fatalcoder524"),
            ("pershoot", None, "Backend Maintainer", "https://github.com/pershoot", "https://github.com/sponsors/pershoot"),
            ("maxsteeel", "Max", "Legacy Maintainer", "https://github.com/maxsteeel", "https://github.com/sponsors/maxsteeel"),
        ]
        self.assertEqual(
            [(r.get("login"), r.get("name"), r.get("role"), r.get("githubUrl"), r.get("donationUrl")) for r in records],
            expected,
        )
        self.assertIn("uriHandler.openUri(contributor.githubUrl)", credits)
        self.assertIn("uriHandler.openUri(contributor.donationUrl)", credits)
        self.assertIn("https://avatars.githubusercontent.com/${contributor.login}?s=80", credits)
        self.assertIn('contributor.login.take(1).uppercase()', credits)
        self.assertIn("MaterialTheme.shapes.extraSmall", credits)
        self.assertIn("MaterialTheme.colorScheme", credits)
        self.assertIn(".heightIn(min = 48.dp)", credits)

    def test_control_headings_and_animation_label(self):
        control = (OVERLAY / "screen/SyntheticaControl.kt").read_text()
        self.assertNotRegex(control, r'text\s*=\s*"\[0[1-9]\]')
        self.assertNotIn("DEPARTURE TELEMETRY", control)
        self.assertNotIn("AIRPORT SPLIT-FLAP", control)
        self.assertNotIn("Mechanical Solari", control)
        self.assertNotIn("TEST DEPARTURE BOARD ANIMATION", control)
        self.assertIn('text = "DEVICE TELEMETRY"', control)
        self.assertIn('text = "TEXT ANIMATION"', control)
        self.assertIn("checked = SyntheticaDepartureAnimState.value", control)
        self.assertIn("setSyntheticaDepartureAnim(context, it)", control)
        self.assertIn("setSyntheticaThemeMode(context, key)", control)
        # Actual readings and tuning values must not be removed along with section numbers.
        self.assertIn('CURRENT [${telemetry.swappiness}]', control)
        self.assertIn('listOf("40", "60", "80", "100")', control)

    def test_relocation_removes_both_home_sections_and_checks_original_links(self):
        issue_resources = '''
            R.string.issue_report_title R.string.issue_report_body R.string.issue_report_body_2
            R.string.issue_report_github_link R.string.issue_report_telegram_link
            R.string.issue_report_github R.string.issue_report_telegram
            R.drawable.ic_github R.drawable.ic_telegram
'''
        fixture = '''\n            InfoCard(autoExpand = developerOptionsEnabled)
            IssueReportCard()
            ContributorsCard()

data class Contributor(
    val login: String,
)
@Composable
fun ContributorsCard() {
    Contributor(login = "example", githubUrl = "https://example.org", role = "Developer", donationUrl = "https://example.org/support")
}
@Composable
fun IssueReportCard() { ''' + issue_resources + ''' }
@SuppressLint("RestrictedApi")
fun handleDynamicShortcuts() {}
'''
        credits = 'Contributor(login = "example", githubUrl = "https://example.org", role = "Developer", donationUrl = "https://example.org/support")'
        about = (OVERLAY / "component/AboutCard.kt").read_text()
        result = patcher.relocate_home_sections(fixture, credits, about)
        self.assertIn("BrutalStaggerItem(index = 3) { InfoCard(autoExpand = developerOptionsEnabled) }", result)
        self.assertIn("fun handleDynamicShortcuts()", result)
        self.assertNotIn("IssueReportCard(", result)
        self.assertNotIn("ContributorsCard(", result)
        self.assertNotIn("data class Contributor(", result)
        with self.assertRaisesRegex(RuntimeError, "do not preserve"):
            patcher.relocate_home_sections(fixture, credits.replace("example.org/support", "invalid.org"), about)
        with self.assertRaisesRegex(RuntimeError, "issue reporting does not preserve"):
            patcher.relocate_home_sections(fixture, credits, about.replace("R.string.issue_report_telegram_link", "R.string.missing"))
        with self.assertRaisesRegex(RuntimeError, "call"):
            patcher.relocate_home_sections(fixture.replace("            ContributorsCard()", ""), credits, about)


class AccentSourceTests(unittest.TestCase):
    def test_six_choices_have_readable_dark_and_light_color_pairs(self):
        theme = (OVERLAY / "theme/Theme.kt").read_text()
        choices = re.findall(
            r'SyntheticaAccentOption\("(\w+)", "(\w+)", Color\(0xFF([0-9A-F]{6})\), Color\(0xFF([0-9A-F]{6})\)\)',
            theme,
        )
        self.assertEqual([c[0] for c in choices], ["volt", "cyan", "violet", "rose", "amber", "mint"])
        for name, label, dark, light in choices:
            with self.subTest(accent=name):
                self.assertGreaterEqual(contrast(dark, "2A3142"), 4.5)
                self.assertGreaterEqual(contrast(dark, "0B0D12"), 4.5)
                self.assertGreaterEqual(contrast(light, "CECCC0"), 4.5)
                self.assertGreaterEqual(contrast(light, "FFFFFF"), 4.5)

    def test_accent_is_persisted_with_fallback_and_applied_to_theme_and_motion(self):
        theme = (OVERLAY / "theme/Theme.kt").read_text()
        control = (OVERLAY / "screen/SyntheticaControl.kt").read_text()
        motion = (OVERLAY / "theme/BrutalMotion.kt").read_text()
        self.assertIn('prefs.getString("synthetica_accent", "volt")', theme)
        self.assertIn('.putString("synthetica_accent", resolved)', theme)
        self.assertIn('?: SyntheticaAccentOptions.first()', theme)
        self.assertIn('baseScheme.withAccent(resolveAccent(SyntheticaAccentState.value), effectiveDark)', theme)
        self.assertIn('onPrimary = if (dark) BRUTAL_INK else Color.White', theme)
        self.assertIn('SyntheticaAccentOptions.forEach { option ->', control)
        self.assertIn('setSyntheticaAccent(context, option.id)', control)
        self.assertIn('isSelected = activeAccent == option.id', control)
        self.assertIn('selected = isSelected', control)
        self.assertIn('role = Role.RadioButton', control)
        self.assertIn('val accent = MaterialTheme.colorScheme.primary', control)
        self.assertIn('val flapAccent = MaterialTheme.colorScheme.primary', motion)
        self.assertIn('val scanColor = MaterialTheme.colorScheme.primary', motion)
        self.assertIn('val railColor = accent ?: MaterialTheme.colorScheme.primary', motion)
        self.assertIn('val accent = MaterialTheme.colorScheme.primary', motion)
        self.assertIn('val volt = MaterialTheme.colorScheme.primary', motion)
        self.assertIn('color = MaterialTheme.colorScheme.onPrimary', motion)


if __name__ == "__main__":
    unittest.main()
