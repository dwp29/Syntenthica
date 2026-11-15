#!/usr/bin/env python3
"""Gerbang navigasi: setiap layar harus punya pintu, dan setiap tab harus ada.

Tiga kali dalam sesi ini sebuah layar nyaris menjadi yatim: Diagnostics, Control
dan Device check tadinya hanya bisa dibuka dari Home; Boost dan Customization
hanya dari Settings. Compiler tidak pernah mengeluh soal layar yang tak bisa
dibuka - hanya pengguna. Gate ini menghitungnya dari kode.
"""
from __future__ import annotations
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
UI = ROOT / "synthetica-manager/app/src/main/java/com/rifsxd/ksunext/ui"
TABS = ("HomeScreen", "SuperUserScreen", "ModuleScreen", "SettingScreen", "DownloadScreen")

def main() -> int:
    files = {p: p.read_text(encoding="utf-8") for p in UI.rglob("*.kt")}
    all_text = "\n".join(files.values())

    # Nama destinasi berasal dari nama fungsi, bukan nama berkas: Settings.kt
    # mendeklarasikan SettingScreen, Template.kt mendeklarasikan
    # AppProfileTemplateScreen, dan membaca nama berkas menghasilkan enam laporan
    # palsu saat gerbang ini pertama dijalankan.
    declared: list[str] = []
    for path, text in files.items():
        if "@Destination" not in text:
            continue
        match = re.search(r"@Destination[^\n]*\n(?:@[^\n]*\n)*fun (\w+)", text)
        if not match:
            problems.append(f"{path.name}: @Destination tanpa fungsi yang bisa dibaca")
            continue
        declared.append(match.group(1))
    declared.sort()
    problems: list[str] = []

    for stem in declared:
        dest = f"{stem}Destination"
        if dest not in all_text:
            problems.append(f"{stem}: deklarasi ada tapi destinasinya tidak dirujuk siapa pun")
            continue
        if stem == "HomeScreen":
            continue
        # Tab dirujuk lewat enum, bukan navigate(); keduanya sah.
        if len(re.findall(rf"\bnavigate\({dest}\b", all_text)) == 0 and dest not in files[UI / "screen/BottomBarDestination.kt"]:
            problems.append(f"{stem}: tidak ada navigate({dest}) dan bukan tab")

    enum_file = files[UI / "screen/BottomBarDestination.kt"]
    for tab in TABS:
        if f"{tab}Destination" not in enum_file:
            problems.append(f"tab {tab} hilang dari BottomBarDestination")

    # Titik masuk Tools harus >1 supaya tidak bisa hilang bersama satu layar.
    tools_doors = len(re.findall(r"\bnavigate\(ToolsScreenDestination\b", all_text))
    if tools_doors < 2:
        problems.append(f"ToolsScreen hanya punya {tools_doors} pintu, minimal 2")

    if problems:
        for p in problems:
            print(f"[nav] {p}", file=sys.stderr)
        return 1
    print(f"[nav] {len(declared)} layar, semuanya punya pintu; {len(TABS)} tab; Tools punya {tools_doors} pintu")
    return 0

if __name__ == "__main__":
    sys.exit(main())
