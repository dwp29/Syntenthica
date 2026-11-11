#!/usr/bin/env python3
"""Render the Pure Manager design deck as single-page, phone-readable images.

Two earlier attempts failed on the user's phone: PNG mockups that were too wide to
read, and an HTML prototype that only opened inside the Arena viewer. So every
page here is one portrait image, self-contained, and also merged into a single PDF
plus a single tall PNG, so at least one of the three opens on any device.
"""
from __future__ import annotations

import pathlib
from PIL import Image, ImageDraw, ImageFont

OUT = pathlib.Path(__file__).resolve().parents[2] / "docs" / "pure-manager" / "deck"
OUT.mkdir(parents=True, exist_ok=True)

F = "/usr/share/fonts/truetype/dejavu"
S = lambda n: ImageFont.truetype(f"{F}/DejaVuSans.ttf", n)
B = lambda n: ImageFont.truetype(f"{F}/DejaVuSans-Bold.ttf", n)
M = lambda n: ImageFont.truetype(f"{F}/DejaVuSansMono.ttf", n)
MB = lambda n: ImageFont.truetype(f"{F}/DejaVuSansMono-Bold.ttf", n)

W, H = 1080, 1920          # one phone screen, portrait
PAD = 56
BG = "#0B0B0D"
FG = "#FFFFFF"
DIM = "#8A8A92"
LINE = "#26262E"

HDR = B(46)
H2 = B(34)
BODY = S(26)
SMALL = S(22)
TINY = S(19)
MONO = M(22)


def canvas():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    return img, d


def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def para(d, text, x, y, font, maxw, fill=FG, lh=None, limit=None):
    lh = lh or int(font.size * 1.45)
    for i, ln in enumerate(wrap(d, text, font, maxw)):
        if limit and i >= limit:
            break
        d.text((x, y), ln, font=font, fill=fill)
        y += lh
    return y


def header(d, kicker, title, sub=None):
    d.text((PAD, 74), kicker.upper(), font=MB(20), fill="#5A5A66")
    y = 108
    for ln in wrap(d, title, HDR, W - PAD * 2):
        d.text((PAD, y), ln, font=HDR, fill=FG)
        y += 54
    if sub:
        y += 8
        y = para(d, sub, PAD, y, BODY, W - PAD * 2, DIM)
    d.line([PAD, y + 22, W - PAD, y + 22], fill=LINE, width=2)
    return y + 58


def card(d, x, y, w, h, radius=18, fill="#141418", outline=LINE):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill,
                        outline=outline, width=2)


def footer(d, page, total):
    d.line([PAD, H - 92, W - PAD, H - 92], fill=LINE, width=2)
    d.text((PAD, H - 74), "Pure Manager · desain", font=TINY, fill="#4A4A56")
    t = f"{page} / {total}"
    d.text((W - PAD - d.textlength(t, font=MB(19)), H - 74), t, font=MB(19),
           fill="#4A4A56")


# ---------------------------------------------------------------- pages
def page_cover():
    img, d = canvas()
    d.text((PAD, 240), "PURE", font=B(150), fill=FG)
    d.text((PAD, 380), "MANAGER", font=B(150), fill="#3A3A46")
    d.line([PAD, 560, W - PAD, 560], fill="#FF2E97", width=4)
    para(d, "Rancangan desain — untuk disetujui sebelum satu baris kode ditulis.",
         PAD, 600, BODY, W - PAD * 2, DIM)

    y = 720
    items = [
        ("Isi", "Tema, layout, tab kustomisasi, alur AI, arsitektur modul"),
        ("Belum", "Tidak ada kode aplikasi. Ini dokumen persetujuan."),
        ("Ukuran", "Dibuat agar terbaca di layar HP, bukan desktop."),
    ]
    for k, v in items:
        d.text((PAD, y), k.upper(), font=MB(19), fill="#5A5A66")
        y += 30
        y = para(d, v, PAD, y, BODY, W - PAD * 2, FG)
        y += 34

    card(d, PAD, H - 420, W - PAD * 2, 220)
    d.text((PAD + 32, H - 388), "Tiga format, isi sama", font=B(28), fill=FG)
    for i, t in enumerate(["PDF  (paling mudah dibuka di HP)",
                           "Satu PNG tinggi  (geser ke bawah)",
                           "11 PNG terpisah  (satu layar per gambar)"]):
        d.text((PAD + 32, H - 344 + i * 40), "· " + t, font=SMALL, fill=DIM)
    return img


def page_theme(theme, page, total):
    """One theme per page, drawn at phone scale so it reads on a phone."""
    T = {
        "ios": dict(name="iOS", bg="#F2F2F7", surf="#FFFFFF", surf2="#E4E4EA",
                    txt="#1C1C1E", sub="#8E8E93", acc="#007AFF", r=34, rr=26,
                    row=118, nav="tab", note="Tab bar bawah · kartu terpisah · radius 34 · font Inter"),
        "pixel": dict(name="Pixel · M3 Expressive", bg="#141218", surf="#211F26",
                      surf2="#2B2930", txt="#E6E0E9", sub="#938F99", acc="#D0BCFF",
                      r=46, rr=38, row=136, nav="tab", note="Pill indikator · kartu tonal · radius 46 · Material Symbols"),
        "win": dict(name="Windows · Fluent", bg="#202020", surf="#2B2B2B",
                    surf2="#333333", txt="#FFFFFF", sub="#A6A6A6", acc="#60CDFF",
                    r=8, rr=6, row=84, nav="rail", note="Rail kiri + kolom tabel · garis 1px · font Selawik"),
        "cyber": dict(name="Cyberpunk", bg="#08000F", surf="#12081F", surf2="#1B0E2E",
                      txt="#E8FFFB", sub="#7A6B8F", acc="#00F0FF", r=6, rr=4,
                      row=78, nav="cmd", note="Baris perintah F1–F4 · grid mono · aksen neon"),
    }[theme]
    img, d = canvas()

    y = header(d, "Tema", T["name"], T["note"])

    # ---- device frame
    fx, fy = PAD, y
    fw, fh = W - PAD * 2, H - y - 210
    d.rounded_rectangle([fx, fy, fx + fw, fy + fh], radius=40, fill="#000",
                        outline="#2A2A2E", width=3)

    ix, iy = fx + 14, fy + 14
    iw, ih = fw - 28, fh - 28
    d.rounded_rectangle([ix, iy, ix + iw, iy + ih], radius=30, fill=T["bg"])

    # status bar
    d.text((ix + 32, iy + 22), "09:41", font=B(22), fill=T["sub"])
    s = "▮▮▮  87%"
    d.text((ix + iw - 32 - d.textlength(s, font=B(20)), iy + 24), s,
           font=B(20), fill=T["sub"])

    rail = 96 if T["nav"] == "rail" else 0
    cx = ix + 32 + rail
    cw = iw - 64 - rail
    cy = iy + 76

    if T["nav"] == "rail":
        d.rectangle([ix + 1, iy + 84, ix + rail, iy + ih - 1], fill=T["surf2"])
        for i, g in enumerate(["▤", "◈", "✦", "⚙"]):
            col = T["acc"] if i == 0 else T["sub"]
            d.text((ix + 34, iy + 130 + i * 92), g, font=S(34), fill=col)

    if T["nav"] == "cmd":
        d.text((cx, cy), ">_ pure://internal/download", font=MB(24),
               fill=T["acc"])
        cy += 52
    else:
        d.text((cx, cy), "Berkas", font=B(40), fill=T["txt"])
        cy += 62
        d.rounded_rectangle([cx, cy, cx + cw, cy + 64], radius=T["rr"],
                            fill=T["surf2"])
        d.text((cx + 22, cy + 18), "⌕  Cari berkas", font=S(24), fill=T["sub"])
        cy += 86

    # column header for the table theme
    if T["nav"] == "rail":
        d.text((cx + 8, cy), "Nama", font=S(19), fill=T["sub"])
        d.text((cx + cw - 110, cy), "Ukuran", font=S(19), fill=T["sub"])
        cy += 30
        d.line([cx, cy, cx + cw, cy], fill="#3D3D3D", width=2)
        cy += 8

    files = [("R", "Retro-Arcade.apk", "24.1 MB"),
             ("Z", "Manager-6.1.zip", "18.7 MB"),
             ("P", "banner-review.png", "640 KB"),
             ("T", "theme-signing.key", "3.4 KB"),
             ("A", "voice-note.m4a", "2.1 MB"),
             ("V", "Deck-ujian.pdf", "1.0 MB")]
    for i, (l, n, sz) in enumerate(files):
        rh = T["row"]
        if T["nav"] == "tab":
            d.rounded_rectangle([cx, cy, cx + cw, cy + rh - 14], radius=T["rr"],
                                fill=T["surf"],
                                outline=("#2A2A2E" if T["bg"] == "#000000" else None))
            ix2 = cx + 22
            d.rounded_rectangle([ix2, cy + (rh - 14) // 2 - 32, ix2 + 64,
                                 cy + (rh - 14) // 2 + 32], radius=18,
                                fill=T["acc"])
            d.text((ix2 + 22, cy + (rh - 14) // 2 - 22), l, font=B(26),
                   fill="#FFF" if theme == "ios" else "#2B1D4A")
            d.text((ix2 + 92, cy + 26), n, font=B(27), fill=T["txt"])
            d.text((ix2 + 92, cy + 66), sz, font=S(21), fill=T["sub"])
        elif T["nav"] == "rail":
            if i == 0:
                d.rectangle([cx, cy, cx + cw, cy + rh], fill=T["surf"])
            d.rectangle([cx + 10, cy + 22, cx + 50, cy + 62], fill=T["acc"])
            d.text((cx + 70, cy + 26), n, font=S(26), fill=T["txt"])
            d.text((cx + cw - 110, cy + 26), sz, font=S(24), fill=T["sub"])
            d.line([cx, cy + rh, cx + cw, cy + rh], fill="#3D3D3D", width=1)
        else:
            if i == 0:
                d.rectangle([cx, cy, cx + cw, cy + rh], fill=T["surf"],
                            outline=T["border"] if False else "#FF2E97", width=2)
            d.text((cx + 12, cy + 20), "▸", font=S(20), fill=T["acc"])
            d.text((cx + 46, cy + 20), n, font=M(21), fill=T["txt"])
            d.text((cx + cw - 120, cy + 20), sz, font=M(18), fill=T["sub"])
        cy += rh

    # storage strip, drawn above the navigation so the list is not half empty
    sy = iy + ih - 176
    if T["nav"] != "rail":
        d.rounded_rectangle([cx, sy, cx + cw, sy + 14], radius=7, fill=T["surf2"])
        d.rounded_rectangle([cx, sy, cx + int(cw * 0.63), sy + 14], radius=7,
                            fill=T["acc"])
        d.text((cx, sy + 26), "182 GB / 256 GB terpakai", font=S(20), fill=T["sub"])

    # ---- navigation
    ny = iy + ih - 120
    if T["nav"] == "tab":
        d.rectangle([ix + 1, ny, ix + iw - 1, iy + ih - 1], fill=T["surf"])
        d.line([ix + 1, ny, ix + iw - 1, ny], fill="#2A2A2E", width=1)
        if theme == "pixel":
            d.rounded_rectangle([ix + 62, ny + 18, ix + 262, ny + 70],
                                radius=26, fill="#4F378B")
        for i, (g, lab) in enumerate([("▤", "Berkas"), ("◈", "Tema"),
                                       ("✦", "AI"), ("⚙", "Setelan")]):
            col = T["acc"] if i == 0 else T["sub"]
            px = ix + 92 + i * 224
            d.text((px, ny + 28), g, font=S(30), fill=col)
            d.text((px - 16, ny + 70), lab, font=S(19), fill=col)
    elif T["nav"] == "cmd":
        d.line([ix + 1, ny + 40, ix + iw - 1, ny + 40], fill="#FF2E97", width=2)
        d.text((ix + 32, ny + 62), "[F1]FILES [F2]ROOT [F3]TERM [F4]NET",
               font=MB(19), fill=T["acc"])

    footer(d, page, total)
    return img


def page_custom_tab(page, total):
    img, d = canvas()
    y = header(d, "Permintaan Anda", "Tab Kustomisasi Tema",
               "Tab tersendiri di aplikasi, dengan pratinjau langsung. "
               "Semua baris di bawah ini adalah token yang bisa diubah pengguna.")

    rows = [
        ("Tema", "iOS · Pixel · Windows · Cyberpunk"),
        ("Mode", "Light · Dark · AMOLED · ikuti jadwal"),
        ("Aksen", "12 warna siap + color picker bebas"),
        ("Font", "Inter · Roboto · Selawik · JetBrains Mono · .ttf sendiri"),
        ("Layout", "Kepadatan: lega / normal / padat"),
        ("Baris", "Kartu atau tabel berkolom"),
        ("Ikon", "4 set, mengikuti tema"),
        ("Animasi", "Penuh · Redam · Mati (hormati setelan sistem)"),
        ("Sudut", "Slider radius global"),
    ]
    ch = 108
    for name, desc in rows:
        card(d, PAD, y, W - PAD * 2, ch - 12)
        d.text((PAD + 28, y + 22), name, font=B(27), fill=FG)
        d.text((PAD + 28, y + 60), desc, font=TINY, fill=DIM)
        d.text((W - PAD - 46, y + 34), "›", font=B(32), fill="#4A4A56")
        y += ch

    y += 10
    card(d, PAD, y, W - PAD * 2, 190, fill="#1A0D14", outline="#FF2E97")
    d.text((PAD + 28, y + 24), "Yang saya tolak", font=B(26), fill="#FF2E97")
    para(d, "Tema yang diunduh sebagai APK terpisah — itu kode asing di dalam "
            "aplikasi Anda. Cukup berkas token JSON yang ditandatangani.",
         PAD + 28, y + 64, SMALL, W - PAD * 2 - 56, "#E8B8CC")
    footer(d, page, total)
    return img


def page_ai_flow(page, total):
    img, d = canvas()
    y = header(d, "Alur yang Anda minta", "Tekan lama → pilih agen AI",
               "Status tiap agen ditampilkan apa adanya. Tidak ada yang "
               "disembunyikan tanpa alasan.")

    # file chip
    card(d, PAD, y, W - PAD * 2, 120, fill="#141418")
    d.rounded_rectangle([PAD + 26, y + 30, PAD + 90, y + 94], radius=18,
                        fill="#007AFF")
    d.text((PAD + 48, y + 48), "P", font=B(28), fill="#FFF")
    d.text((PAD + 112, y + 34), "banner-review.png", font=B(28), fill=FG)
    d.text((PAD + 112, y + 74), "640 KB · 1080×1920", font=TINY, fill=DIM)
    y += 150

    d.text((PAD, y), "Apa yang ingin dilakukan?", font=S(24), fill=DIM)
    y += 48

    agents = [
        ("✂", "Edit gambar", "Crop, filter, hapus background", "LOKAL", "#10B981"),
        ("🏷", "Beri nama otomatis", "Baca isi, usulkan nama", "LOKAL", "#10B981"),
        ("🔍", "Cari yang mirip", "Kemiripan visual, bukan nama", "LOKAL", "#10B981"),
        ("✦", "Tanya AI", "Butuh Nano atau kunci API", "OPSIONAL", "#F59E0B"),
    ]
    for g, nm, ds, badge, col in agents:
        h = 136
        card(d, PAD, y, W - PAD * 2, h - 14)
        d.ellipse([PAD + 26, y + 40, PAD + 52, y + 66], fill=col)
        d.text((PAD + 26, y + 34), g, font=S(24), fill=FG)
        d.text((PAD + 74, y + 26), nm, font=B(26), fill=FG)
        d.text((PAD + 74, y + 64), ds, font=TINY, fill=DIM)
        tw = d.textlength(badge, font=MB(17))
        d.rounded_rectangle([W - PAD - 30 - tw - 24, y + 34,
                             W - PAD - 30, y + 34 + 40],
                            radius=20, fill=col)
        d.text((W - PAD - 30 - tw - 12, y + 41), badge, font=MB(17), fill="#000")
        y += h

    y += 6
    card(d, PAD, y, W - PAD * 2, 250, fill="#101A14", outline="#10B981")
    d.text((PAD + 28, y + 24), "Kenapa banyak yang LOKAL", font=B(25),
           fill="#10B981")
    para(d, "Gemini Nano hanya ada di sebagian HP flagship, DAN mensyaratkan "
            "bootloader terkunci. Pengguna file manager yang root justru paling "
            "tidak bisa memakainya. Karena itu fondasi AI adalah model lokal "
            "yang diunduh, bukan Nano.",
         PAD + 28, y + 62, TINY, W - PAD * 2 - 56, "#9AD8BC")
    footer(d, page, total)
    return img


def page_variants(page, total):
    img, d = canvas()
    y = header(d, "Keputusan Anda", "Full & Minimal — satu kunci",
               "Package sama, kunci tanda tangan sama, jadi bisa saling "
               "menggantikan tanpa uninstall.")

    cards = [
        ("FULL", "± 150 MB", "#FF2E97",
         ["Semua fitur sudah di dalam", "Langsung pakai",
          "Modul FFmpeg ikut → build ini GPL"]),
        ("MINIMAL", "± 15 MB", "#00F0FF",
         ["Modul diunduh saat dibutuhkan", "Hemat storage",
          "APK utama tetap Apache-2.0"]),
    ]
    for i, (nm, sz, col, pts) in enumerate(cards):
        cx = PAD + i * ((W - PAD * 2) // 2 + 8)
        cw = (W - PAD * 2) // 2 - 8
        card(d, cx, y, cw, 470, fill="#141418", outline=col)
        d.text((cx + 26, y + 26), nm, font=MB(26), fill=col)
        d.text((cx + 26, y + 66), sz, font=B(44), fill=FG)
        yy = y + 150
        for p in pts:
            for ln in wrap(d, "· " + p, TINY, cw - 52):
                d.text((cx + 26, yy), ln, font=TINY, fill=DIM)
                yy += 30
            yy += 12
    y += 510

    y = header_plain(d, y, "Tab Modul di dalam aplikasi")
    mods = [
        ("OCR (teks dari gambar)", "4 MB", "TERPASANG", "#10B981"),
        ("FFmpeg", "22 MB", "BELUM", "#4A4A56"),
        ("Model embedding", "60 MB", "BELUM", "#4A4A56"),
        ("Whisper-tiny", "75 MB", "BELUM", "#4A4A56"),
    ]
    for nm, sz, st, col in mods:
        card(d, PAD, y, W - PAD * 2, 92)
        d.text((PAD + 26, y + 20), nm, font=S(24), fill=FG)
        d.text((PAD + 26, y + 54), sz, font=TINY, fill=DIM)
        tw = d.textlength(st, font=MB(16))
        d.rounded_rectangle([W - PAD - 26 - tw - 22, y + 26,
                             W - PAD - 26, y + 26 + 38], radius=19, fill=col)
        d.text((W - PAD - 26 - tw - 11, y + 33), st, font=MB(16), fill="#000")
        y += 104

    footer(d, page, total)
    return img


def header_plain(d, y, title):
    d.text((PAD, y), title, font=H2, fill=FG)
    return y + 62


def page_modules(page, total):
    img, d = canvas()
    y = header(d, "Jawaban pertanyaan Anda", "Dari mana modul diunduh",
               "GitHub Releases. Bukan Play Store — dan ini alasannya.")

    y = header_plain(d, y, "Yang bekerja di luar Play Store")
    ok = [
        ("Unduh berkas biasa", "Dari GitHub Releases, verifikasi SHA-256 + "
                               "tanda tangan Ed25519. Bisa, tak terbatas."),
        ("APK Full", "Semua di dalam. Bisa, tapi besar dan GPL."),
    ]
    for nm, ds in ok:
        card(d, PAD, y, W - PAD * 2, 130, outline="#10B981")
        d.text((PAD + 26, y + 20), "✓ " + nm, font=B(25), fill="#10B981")
        para(d, ds, PAD + 26, y + 60, TINY, W - PAD * 2 - 52, DIM)
        y += 144

    y = header_plain(d, y + 8, "Yang TIDAK bekerja")
    card(d, PAD, y, W - PAD * 2, 190, outline="#EF4444")
    d.text((PAD + 26, y + 20), "✗ Dynamic Feature Module", font=B(25),
           fill="#EF4444")
    para(d, "Wajib Play Core dan Play Store sebagai penyedia unduhan. "
            "bundletool --local-testing hanya untuk uji internal, bukan rilis.",
         PAD + 26, y + 60, TINY, W - PAD * 2 - 52, DIM)
    y += 216

    y = header_plain(d, y, "Alur unduh di aplikasi")
    steps = ["Tekan fitur yang butuh modul",
             "Aplikasi hitung: belum ada / versi beda",
             "Unduh dari GitHub Releases + progress",
             "Verifikasi SHA-256 dan tanda tangan",
             "Pasang ke filesDir/modules/",
             "Muat dengan System.load / DexClassLoader"]
    for i, s in enumerate(steps):
        cy = y + i * 78
        d.ellipse([PAD, cy + 6, PAD + 44, cy + 50], fill="#1B0E2E",
                  outline="#00F0FF", width=2)
        d.text((PAD + 15, cy + 14), str(i + 1), font=MB(22), fill="#00F0FF")
        para(d, s, PAD + 62, cy + 14, SMALL, W - PAD * 2 - 70, FG)
    footer(d, page, total)
    return img


def page_summary(page, total):
    img, d = canvas()
    y = header(d, "Ringkasan", "Yang perlu Anda setujui",
               "Setelah ini disetujui, saya mulai menulis kode. Sebelum itu, "
               "tidak ada kode.")

    items = [
        ("Tema", "4 tema, 4 model navigasi berbeda — bukan sekadar warna"),
        ("Tab kustomisasi", "Tab sendiri dengan pratinjau langsung"),
        ("Varian", "Full 150 MB dan Minimal 15 MB, satu kunci tanda tangan"),
        ("Modul", "GitHub Releases + verifikasi tanda tangan"),
        ("AI", "4 lapis: lokal → Nano → BYOK → tanpa AI"),
        ("Tab Modul", "Terlihat di aplikasi, bisa unduh & hapus"),
        ("Android TV", "Didukung"),
    ]
    for nm, ds in items:
        card(d, PAD, y, W - PAD * 2, 124)
        d.text((PAD + 26, y + 22), nm, font=B(26), fill=FG)
        yy = y + 62
        for ln in wrap(d, ds, TINY, W - PAD * 2 - 52)[:2]:
            d.text((PAD + 26, yy), ln, font=TINY, fill=DIM)
            yy += 28
        y += 136

    card(d, PAD, y + 6, W - PAD * 2, 150, fill="#101A14", outline="#10B981")
    d.text((PAD + 26, y + 28), "Kalau setuju", font=B(25), fill="#10B981")
    para(d, "Balas \"setuju\", dan saya mulai tahap 1: kerangka aplikasi, "
            "4 tema, tab kustomisasi, tanpa fitur berat dulu.",
         PAD + 26, y + 66, TINY, W - PAD * 2 - 52, "#9AD8BC")
    footer(d, page, total)
    return img


def build():
    pages: list[Image.Image] = []
    pages.append(page_cover())
    n = 10
    for i, t in enumerate(["ios", "pixel", "win", "cyber"]):
        pages.append(page_theme(t, 2 + i, n))
    pages.append(page_custom_tab(6, n))
    pages.append(page_ai_flow(7, n))
    pages.append(page_variants(8, n))
    pages.append(page_modules(9, n))
    pages.append(page_summary(10, n))

    # one page per file
    for i, p in enumerate(pages, 1):
        p.save(OUT / f"{i:02d}.png")

    # single tall PNG: easiest thing to open and scroll in any mobile browser
    tall = Image.new("RGB", (W, H * len(pages)), BG)
    for i, p in enumerate(pages):
        tall.paste(p, (0, i * H))
    tall.save(OUT.parent / "visualisasi-lengkap.png")

    # PDF: opens natively on Android and is the most reliable single file
    pages[0].save(OUT.parent / "visualisasi-lengkap.pdf", save_all=True,
                  append_images=pages[1:], resolution=150.0)
    return OUT, len(pages)


if __name__ == "__main__":
    out, n = build()
    print(f"{n} halaman -> {out}")
