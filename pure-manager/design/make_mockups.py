#!/usr/bin/env python3
"""Render the Pure Manager theme mockups.

Design-only script: it draws what the themes will look like, it does not build the
app. Output goes to docs/pure-manager/.

Fonts: this sandbox only has DejaVu, so the mockups use it as a stand-in. The real
app ships Inter (iOS-like), Selawik (Windows-like, OFL) and a mono face (Cyberpunk).
DejaVu Mono stands in for the mono face because it is metrically close enough to
show the density difference that actually matters.
"""
from __future__ import annotations

import pathlib
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = pathlib.Path(__file__).resolve().parents[2] / "docs" / "pure-manager"
OUT.mkdir(parents=True, exist_ok=True)

FONTS = "/usr/share/fonts/truetype/dejavu"
def sans(sz):  return ImageFont.truetype(f"{FONTS}/DejaVuSans.ttf", sz)
def bold(sz):  return ImageFont.truetype(f"{FONTS}/DejaVuSans-Bold.ttf", sz)
def mono(sz):  return ImageFont.truetype(f"{FONTS}/DejaVuSansMono.ttf", sz)
def monob(sz): return ImageFont.truetype(f"{FONTS}/DejaVuSansMono-Bold.ttf", sz)


# ---------------------------------------------------------------- themes
THEMES = {
    "ios": dict(
        label="iOS", bg="#F2F2F7", card="#FFFFFF", text="#1C1C1E", sub="#8E8E93",
        accent="#007AFF", line=None, radius=16, font=sans, title=bold,
        row_h=54, pad=14, dense=False,
    ),
    "pixel": dict(
        label="Pixel · M3 Expressive", bg="#141218", card="#211F26", text="#E6E0E9",
        sub="#938F99", accent="#D0BCFF", line=None, radius=20, font=sans, title=bold,
        row_h=62, pad=16, dense=False,
    ),
    "windows": dict(
        label="Windows · Fluent", bg="#202020", card="#2B2B2B", text="#FFFFFF",
        sub="#A6A6A6", accent="#60CDFF", line="#3D3D3D", radius=4, font=sans,
        title=bold, row_h=34, pad=8, dense=True,
    ),
    "cyberpunk": dict(
        label="Cyberpunk", bg="#08000F", card="#12081F", text="#E8FFFB", sub="#7A6B8F",
        accent="#00F0FF", line="#FF2E97", radius=3, font=mono, title=monob,
        row_h=30, pad=10, dense=True,
    ),
}

W, H = 320, 660          # screen
SCALE = 2                # render at 2x then downscale for crisp edges


def screen_layer(theme_key: str) -> Image.Image:
    t = THEMES[theme_key]
    img = Image.new("RGB", (W * SCALE, H * SCALE), t["bg"])
    d = ImageDraw.Draw(img)
    pad = t["pad"] * SCALE
    # Windows uses a left rail; content has to start after it or the rail covers
    # the first column of the file list.
    rail = 34 * SCALE if theme_key == "windows" else 0
    x0, x1 = rail + pad, (W - t["pad"]) * SCALE

    # ---- status bar
    d.text((pad, 10 * SCALE), "09:41", font=t["font"](11 * SCALE), fill=t["sub"])
    d.text(((W - 62) * SCALE, 10 * SCALE), "▮▮▮  ⌁  87%",
           font=t["font"](10 * SCALE), fill=t["sub"])

    y = 32 * SCALE

    if theme_key in ("ios", "pixel"):
        # ---- big title + search field
        d.text((pad, y), "Pure Manager", font=t["title"](22 * SCALE), fill=t["text"])
        y += 32 * SCALE
        sr = (t["radius"] if theme_key == "pixel" else 10) * SCALE
        d.rounded_rectangle([x0, y, x1, y + 30 * SCALE], radius=sr,
                            fill=t["card"] if theme_key == "pixel" else "#E4E4EA")
        d.text((pad + 10 * SCALE, y + 8 * SCALE), "⌕  Cari berkas", 
               font=t["font"](11 * SCALE), fill=t["sub"])
        y += 42 * SCALE

    elif theme_key == "windows":
        # ---- Explorer-style: breadcrumb bar in a boxed path strip
        d.rounded_rectangle([x0, y, x1, y + 24 * SCALE], radius=3 * SCALE,
                            fill="#2B2B2B", outline=t["line"], width=1)
        d.text((pad + 6 * SCALE + rail, y + 6 * SCALE),
               "  ›  Internal  ›  Download", font=t["font"](10 * SCALE),
               fill=t["sub"])
        y += 32 * SCALE

    elif theme_key == "cyberpunk":
        d.text((pad, y), ">_ pure://internal/download", font=t["font"](11 * SCALE),
               fill=t["accent"])
        y += 22 * SCALE

    # ---- file rows
    files = [
        ("R", "Retro-Arcade.apk", "24.1 MB"),
        ("Z", "Manager-6.1.zip", "18.7 MB"),
        ("P", "banner-review.png", "640 KB"),
        ("T", "theme-signing.key", "3.4 KB"),
    ]
    if theme_key == "windows":
        # column headers, the thing that makes it read as Explorer
        d.text((pad + 4 * SCALE + rail, y), "Nama", font=t["font"](9 * SCALE), fill=t["sub"])
        d.text((x1 - 48 * SCALE, y), "Ukuran", font=t["font"](9 * SCALE), fill=t["sub"])
        y += 16 * SCALE
        d.line([x0, y, x1, y], fill=t["line"], width=1)
        y += 4 * SCALE

    for letter, name, size in files:
        row_h = t["row_h"] * SCALE
        if theme_key in ("ios", "pixel"):
            card_r = (t["radius"] if theme_key == "pixel" else 12) * SCALE
            d.rounded_rectangle([x0, y, x1, y + row_h - 6 * SCALE], radius=card_r,
                                fill=t["card"])
            icon = (pad + 12 * SCALE, y + 10 * SCALE)
            ir = 9 * SCALE
            d.rounded_rectangle([icon[0], icon[1], icon[0] + ir*2, icon[1] + ir*2],
                                radius=(6 if theme_key == "pixel" else 5) * SCALE,
                                fill=t["accent"])
            d.text((icon[0] + 6 * SCALE, icon[1] + 3 * SCALE), letter,
                   font=bold(10 * SCALE), fill="#FFFFFF" if theme_key == "ios" else "#2B1D4A")
            tx = icon[0] + ir*2 + 12 * SCALE
            d.text((tx, y + 9 * SCALE), name, font=t["font"](11 * SCALE), fill=t["text"])
            d.text((tx, y + 26 * SCALE), size, font=t["font"](9 * SCALE), fill=t["sub"])
            d.text((x1 - 18 * SCALE, y + 18 * SCALE), "›", font=t["font"](14 * SCALE),
                   fill=t["sub"])
            y += row_h

        elif theme_key == "windows":
            d.rectangle([x0, y, x1, y + row_h], fill=t["card"] if letter == "R" else t["bg"])
            icon = (pad + 4 * SCALE + rail, y + 8 * SCALE)
            d.rectangle([icon[0], icon[1], icon[0] + 14 * SCALE, icon[1] + 14 * SCALE],
                        fill=t["accent"] if letter == "R" else "#4CC2FF")
            d.text((pad + 24 * SCALE + rail, y + 8 * SCALE), name,
                   font=t["font"](10 * SCALE), fill=t["text"])
            d.text((x1 - 48 * SCALE, y + 8 * SCALE), size,
                   font=t["font"](10 * SCALE), fill=t["sub"])
            y += row_h
            d.line([x0, y, x1, y], fill=t["line"], width=1)

        else:  # cyberpunk
            d.rectangle([x0, y, x1, y + row_h], fill=t["card"] if letter == "R" else None,
                        outline=t["line"] if letter == "R" else None, width=1)
            d.text((pad + 2 * SCALE, y + 7 * SCALE), "▸", font=t["font"](9 * SCALE),
                   fill=t["accent"])
            d.text((pad + 16 * SCALE, y + 7 * SCALE), name, font=t["font"](9 * SCALE),
                   fill=t["text"])
            d.text((x1 - 52 * SCALE, y + 7 * SCALE), size, font=t["font"](8 * SCALE),
                   fill=t["sub"])
            y += row_h

    return img


def nav_bar(theme_key: str) -> None:
    """Return nothing; drawn onto the composite so it can differ per theme."""
    return None


def add_chrome(img: Image.Image, theme_key: str) -> Image.Image:
    """Bottom navigation, drawn per theme so the navigation model differs too."""
    t = THEMES[theme_key]
    d = ImageDraw.Draw(img)
    pad = t["pad"] * SCALE
    # Windows uses a left rail; content has to start after it or the rail covers
    # the first column of the file list.
    rail = 34 * SCALE if theme_key == "windows" else 0
    x0, x1 = rail + pad, (W - t["pad"]) * SCALE
    by = (H - 54) * SCALE

    if theme_key == "windows":
        # left rail, Office/Fluent style
        d.rectangle([0, 60 * SCALE, 34 * SCALE, H * SCALE], fill="#272727")
        for i, g in enumerate(("▤", "▦", "⚙")):
            d.text((10 * SCALE, (120 + i * 44) * SCALE), g, font=t["font"](14 * SCALE),
                   fill=t["accent"] if i == 0 else t["sub"])
        return img

    if theme_key == "cyberpunk":
        d.line([0, (H - 40) * SCALE, W * SCALE, (H - 40) * SCALE], fill=t["line"], width=1)
        d.text((pad, (H - 30) * SCALE), "[F1]FILES  [F2]ROOT  [F3]TERM  [F4]NET",
               font=t["font"](8 * SCALE), fill=t["accent"])
        return img

    if theme_key == "pixel":
        # M3 navigation bar: pill indicator behind the active destination
        d.rounded_rectangle([x0 - 4 * SCALE, by, x1 + 4 * SCALE, H * SCALE],
                            radius=26 * SCALE, fill=t["card"])
        xs = [pad + 24 * SCALE, pad + 92 * SCALE, pad + 160 * SCALE, pad + 228 * SCALE]
        d.rounded_rectangle([xs[0] - 22 * SCALE, by + 4 * SCALE,
                             xs[0] + 22 * SCALE, by + 24 * SCALE],
                            radius=12 * SCALE, fill="#4F378B")
        for i, g in enumerate(("▤", "⌂", "⇄", "⚙")):
            d.text((xs[i] - 6 * SCALE, by + 7 * SCALE), g, font=t["font"](13 * SCALE),
                   fill=t["accent"] if i == 0 else t["sub"])
        return img

    # iOS: flush translucent bar with hairline
    d.rectangle([0, by - 1 * SCALE, W * SCALE, H * SCALE], fill="#F9F9FB")
    d.line([0, by - 1 * SCALE, W * SCALE, by - 1 * SCALE], fill="#D8D8DC", width=1)
    xs = [52 * SCALE, 120 * SCALE, 190 * SCALE, 258 * SCALE]
    for i, (g, lab) in enumerate((("▤", "Files"), ("⌂", "Home"),
                                  ("⇄", "Transfer"), ("⚙", "Settings"))):
        col = t["accent"] if i == 0 else t["sub"]
        d.text((xs[i] - 6 * SCALE, by + 5 * SCALE), g, font=t["font"](12 * SCALE), fill=col)
        d.text((xs[i] - 15 * SCALE, by + 22 * SCALE), lab, font=t["font"](7 * SCALE), fill=col)
    return img


def phone(theme_key: str) -> Image.Image:
    t = THEMES[theme_key]
    screen = screen_layer(theme_key)
    screen = add_chrome(screen, theme_key)

    if theme_key == "cyberpunk":
        # scanlines + a neon bloom around the active row
        glow = Image.new("RGB", screen.size, "#000000")
        gd = ImageDraw.Draw(glow)
        gd.rounded_rectangle([10 * SCALE, 150 * SCALE, (W - 10) * SCALE, 190 * SCALE],
                             radius=3 * SCALE, outline=t["accent"], width=2)
        glow = glow.filter(ImageFilter.GaussianBlur(6 * SCALE))
        screen = Image.blend(screen, Image.blend(screen, glow, 0.55), 0.5)
        sc = Image.new("RGBA", screen.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sc)
        for yy in range(0, H * SCALE, 3):
            sd.line([0, yy, W * SCALE, yy], fill=(0, 0, 0, 40))
        screen = Image.alpha_composite(screen.convert("RGBA"), sc).convert("RGB")

    screen = screen.resize((W, H), Image.LANCZOS)

    pad = 10
    frame = Image.new("RGB", (W + pad * 2, H + pad * 2), "#0B0B0D")
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle([0, 0, frame.width - 1, frame.height - 1], radius=26,
                         fill="#000000", outline="#2A2A2E", width=2)

    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=20, fill=255)
    frame.paste(screen, (pad, pad), mask)
    return frame


def caption_below(frame: Image.Image, theme_key: str) -> Image.Image:
    t = THEMES[theme_key]
    c = Image.new("RGB", (frame.width, 46), "#0B0B0D")
    d = ImageDraw.Draw(c)
    d.text((4, 6), t["label"], font=bold(13), fill="#EDEDED")
    note = {"ios": "list + tab bar, radius 16, soft",
            "pixel": "cards + pill nav, M3 expressive",
            "windows": "table + left rail, 1px rules",
            "cyberpunk": "mono grid + glow, 2px edges"}[theme_key]
    d.text((4, 25), note, font=sans(9), fill="#8A8A92")
    out = Image.new("RGB", (frame.width, frame.height + 46), "#0B0B0D")
    out.paste(frame, (0, 0))
    out.paste(c, (0, frame.height))
    return out


def build_theme_sheet() -> pathlib.Path:
    order = ["ios", "pixel", "windows", "cyberpunk"]
    frames = [caption_below(phone(k), k) for k in order]
    gap, margin, header = 26, 34, 74
    w = margin * 2 + sum(f.width for f in frames) + gap * (len(frames) - 1)
    h = header + max(f.height for f in frames) + margin
    sheet = Image.new("RGB", (w, h), "#0B0B0D")
    d = ImageDraw.Draw(sheet)

    d.text((margin, 22), "PURE MANAGER — empat tema, empat model layout",
           font=bold(19), fill="#FFFFFF")
    d.text((margin, 48),
           "Yang berbeda bukan hanya warna: radius, elevasi, tipografi, dan kepadatan ikut berubah.",
           font=sans(11), fill="#8A8A92")

    x = margin
    for f in frames:
        sheet.paste(f, (x, header))
        x += f.width + gap
    p = OUT / "mockup-tema-layout.png"
    sheet.save(p)
    return p


# ---------------------------------------------------------------- mode matrix
def mode_swatch(hex_col: str, w: int, h: int, label: str, sub: str,
                fg: str, radius: int, fnt) -> Image.Image:
    img = Image.new("RGB", (w, h), hex_col)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, outline="#33333A", width=1)
    d.text((12, 10), label, font=bold(11), fill=fg)
    d.text((12, h - 20), sub, font=sans(8), fill=fg + "AA" if len(fg) == 7 else fg)
    return img


def build_mode_matrix() -> pathlib.Path:
    # Each theme defines its three surface levels for light / dark / amoled.
    rows = [
        ("iOS", {"Light": ("#FFFFFF", "#1C1C1E"), "Dark": ("#1C1C1E", "#FFFFFF"),
                 "AMOLED": ("#000000", "#FFFFFF")}),
        ("Pixel", {"Light": ("#FFFBFE", "#1C1B1F"), "Dark": ("#141218", "#E6E0E9"),
                   "AMOLED": ("#000000", "#E6E0E9")}),
        ("Windows", {"Light": ("#F3F3F3", "#1A1A1A"), "Dark": ("#202020", "#FFFFFF"),
                     "AMOLED": ("#000000", "#FFFFFF")}),
        ("Cyberpunk", {"Light": ("#F4F0FF", "#12081F"), "Dark": ("#08000F", "#E8FFFB"),
                       "AMOLED": ("#000000", "#00F0FF")}),
    ]
    cw, ch, gap, margin, left = 176, 74, 14, 34, 128
    modes = ["Light", "Dark", "AMOLED"]
    w = margin * 2 + left + cw * 3 + gap * 2
    h = 96 + ch * len(rows) + gap * (len(rows) - 1) + margin + 20
    img = Image.new("RGB", (w, h), "#0B0B0D")
    d = ImageDraw.Draw(img)

    d.text((margin, 22), "Tema × Mode — tiga sumbu, bukan satu daftar",
           font=bold(19), fill="#FFFFFF")
    d.text((margin, 48),
           "AMOLED bukan \"gelap lebih pekat\": elevasi tonal dimatikan, kontras dibawa oleh border.",
           font=sans(11), fill="#8A8A92")

    for i, m in enumerate(modes):
        d.text((margin + left + i * (cw + gap) + 4, 74), m.upper(), font=bold(10),
               fill="#8A8A92")

    y = 96
    for name, spec in rows:
        d.text((margin, y + 28), name, font=bold(13), fill="#EDEDED")
        for i, m in enumerate(modes):
            bg, fg = spec[m]
            x = margin + left + i * (cw + gap)
            sub = "#000000" if m == "AMOLED" else ""
            img.paste(mode_swatch(bg, cw, ch, "Aa  Berkas", sub, fg,
                                  (16 if name == "iOS" else 20 if name == "Pixel"
                                   else 4 if name == "Windows" else 2),
                                  sans(9)), (x, y))
        y += ch + gap

    p = OUT / "mockup-matriks-mode.png"
    img.save(p)
    return p


if __name__ == "__main__":
    for path in (build_theme_sheet(), build_mode_matrix()):
        print(path, path.stat().st_size, "bytes")
