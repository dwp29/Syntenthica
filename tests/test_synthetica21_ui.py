"""Host-side regression checks for the About/credits UI patch (not Android UI tests)."""
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


class AboutUiSourceTests(unittest.TestCase):
    def test_about_is_bounded_scrollable_and_contains_the_credits(self):
        about = (OVERLAY / "component/AboutCard.kt").read_text()
        self.assertEqual(about.count("ContributorsSection()"), 1)
        self.assertIn("Dialog(onDismissRequest = dismiss)", about)
        self.assertIn("IconButton(onClick = onDismiss", about)
        self.assertIn(".heightIn(max = maxDialogHeight)", about)
        self.assertIn(".verticalScroll(rememberScrollState())", about)
        self.assertIn("MaterialTheme.colorScheme", about)
        self.assertIn("brutalPlate(active = true)", about)
        self.assertIn("KernelSU-Next (GPL-3.0)", about)

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
        self.assertIn('contributor.login.take(1).uppercase()', credits)  # Offline avatar fallback.
        self.assertIn("MaterialTheme.shapes.extraSmall", credits)
        self.assertIn("MaterialTheme.colorScheme", credits)
        self.assertIn(".heightIn(min = 48.dp)", credits)

    def test_only_the_departure_test_button_is_removed(self):
        control = (OVERLAY / "screen/SyntheticaControl.kt").read_text()
        self.assertNotIn("TEST DEPARTURE BOARD ANIMATION", control)
        self.assertNotIn("SOLARI DEPARTURE BOARD TEST TRIGGERED", control)
        self.assertIn("AIRPORT SPLIT-FLAP DEPARTURE TEXT", control)
        self.assertIn("checked = SyntheticaDepartureAnimState.value", control)
        self.assertIn("setSyntheticaDepartureAnim(context, it)", control)
        self.assertIn("setSyntheticaThemeMode(context, key)", control)

    def test_relocation_keeps_issue_reporting_and_rejects_changed_credits(self):
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
fun IssueReportCard() { println("report") }
'''
        credits = 'Contributor(login = "example", githubUrl = "https://example.org", role = "Developer", donationUrl = "https://example.org/support")'
        result = patcher.relocate_home_contributors(fixture, credits)
        self.assertIn("BrutalStaggerItem(index = 4) { IssueReportCard() }", result)
        self.assertIn("fun IssueReportCard()", result)
        self.assertNotIn("ContributorsCard(", result)
        self.assertNotIn("data class Contributor(", result)
        with self.assertRaisesRegex(RuntimeError, "do not preserve"):
            patcher.relocate_home_contributors(fixture, credits.replace("example.org/support", "invalid.org"))
        with self.assertRaisesRegex(RuntimeError, "call"):
            patcher.relocate_home_contributors(fixture.replace("            ContributorsCard()", ""), credits)


if __name__ == "__main__":
    unittest.main()
