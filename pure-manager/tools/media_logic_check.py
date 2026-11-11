"""Port uji: kasus yang sama dengan MediaTest.kt, dijalankan di Python.

Sandbox ini tidak punya JDK. Port ini memeriksa aritmetika waktu, pemilihan trek,
dan pembatasan zoom -- bagian yang salahnya tidak butuh HP untuk diketahui.
"""
import sys

FAIL = []


def ck(name, got, want):
    if got != want:
        FAIL.append(f"{name}: dapat {got!r}, harusnya {want!r}")


def fmt_clock(ms):
    if ms < 0 or ms == 2**63 - 1:
        return "--:--"
    t = ms // 1000
    s, m, h = t % 60, (t // 60) % 60, t // 3600
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"


ck("0", fmt_clock(0), "0:00")
ck("7s", fmt_clock(7000), "0:07")
ck("65s", fmt_clock(65000), "1:05")
ck("599s", fmt_clock(599000), "9:59")
ck("1 jam", fmt_clock(3600000), "1:00:00")
ck("2:03:04", fmt_clock(7384000), "2:03:04")
ck("tak diketahui", fmt_clock(-1), "--:--")
ck("max", fmt_clock(2**63 - 1), "--:--")
ck("999", fmt_clock(999), "0:00")
ck("1000", fmt_clock(1000), "0:01")


def shown_position(position, drag, duration):
    c = position if drag is None else drag
    return max(0, min(c, max(0, duration)))


ck("drag menang", shown_position(5000, 30000, 60000), 30000)
ck("lepas drag", shown_position(5000, None, 60000), 5000)
ck("batas atas", shown_position(90000, None, 60000), 60000)
ck("batas bawah", shown_position(-5000, None, 60000), 0)
ck("durasi tak diketahui", shown_position(12000, None, -1), 0)


def progress(position, duration):
    if duration <= 0:
        return 0.0
    return max(0.0, min(1.0, position / duration))


ck("progres tak diketahui", progress(1000, -1), 0.0)
ck("progres nol", progress(1000, 0), 0.0)
ck("progres separuh", progress(30000, 60000), 0.5)
ck("progres lebih", progress(90000, 60000), 1.0)
ck("progres negatif", progress(-1, 60000), 0.0)


def next_index(current, count, repeat, shuffle, seed=0):
    if count <= 1:
        return 0
    if shuffle:
        step = (seed % (count - 1)) + 1
        return (current + step) % count
    cand = current + 1
    return cand if cand < count else (0 if repeat else count - 1)


def prev_index(current, count, repeat, shuffle, seed=0):
    if count <= 1:
        return 0
    if shuffle:
        step = (seed % (count - 1)) + 1
        return ((current - step) % count + count) % count
    cand = current - 1
    return cand if cand >= 0 else (count - 1 if repeat else 0)


ck("berikut", next_index(1, 4, False, False), 2)
ck("akhir tanpa ulang", next_index(3, 4, False, False), 3)
ck("akhir dengan ulang", next_index(3, 4, True, False), 0)
ck("sebelum", prev_index(1, 4, False, False), 0)
ck("awal tanpa ulang", prev_index(0, 4, False, False), 0)
ck("awal dengan ulang", prev_index(0, 4, True, False), 3)
ck("satu trek", next_index(0, 1, False, True), 0)
ck("satu trek mundur", prev_index(0, 1, False, False), 0)

# Acak tidak boleh memilih trek yang sedang diputar, dan harus di dalam rentang.
for count in (2, 3, 5):
    for current in range(count):
        for seed in range(count + 3):
            n = next_index(current, count, False, True, seed)
            p = prev_index(current, count, False, True, seed)
            if n == current:
                FAIL.append(f"acak berikut memilih trek yang sama (n={count}, cur={current}, seed={seed})")
            if p == current:
                FAIL.append(f"acak mundur memilih trek yang sama (n={count}, cur={current}, seed={seed})")
            if not (0 <= n < count) or not (0 <= p < count):
                FAIL.append(f"acak keluar rentang (n={count}, cur={current}, seed={seed})")


def restarts(position, threshold=3000):
    return position > threshold


ck("baru mulai -> sebelumnya", restarts(0), False)
ck("2.999 -> sebelumnya", restarts(2999), False)
ck("3.001 -> ulang", restarts(3001), True)

IMAGE = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "heic", "heif", "dng"}
AUDIO = {"mp3", "m4a", "aac", "wav", "ogg", "oga", "opus", "flac", "mid", "midi", "amr", "weba"}
VIDEO = {"mp4", "m4v", "mkv", "webm", "3gp", "avi", "mov", "ts"}


def kind_of(ext):
    e = ext.lower()
    if e in IMAGE:
        return "IMAGE"
    if e in AUDIO:
        return "AUDIO"
    if e in VIDEO:
        return "VIDEO"
    return None


ck("jpg", kind_of("jpg"), "IMAGE")
ck("HEIC", kind_of("HEIC"), "IMAGE")
ck("mp3", kind_of("mp3"), "AUDIO")
ck("flac", kind_of("flac"), "AUDIO")
ck("mp4", kind_of("mp4"), "VIDEO")
ck("pdf", kind_of("pdf"), None)
ck("txt", kind_of("txt"), None)


def title_of(name):
    dot = name.rfind(".")
    return name[:dot] if dot > 0 else name


ck("judul", title_of("lagu favorit.mp3"), "lagu favorit")
ck("titik di depan", title_of(".nomedia"), ".nomedia")
ck("tanpa ekstensi", title_of("no-extension"), "no-extension")


def playlist_position(paths, tapped):
    return paths.index(tapped) if tapped in paths else 0


ck("posisi", playlist_position(["/a/1.mp3", "/a/2.mp3"], "/a/2.mp3"), 1)
ck("tidak ada di daftar", playlist_position(["/a/1.mp3"], "/a/x.mp3"), 0)


def clamp_zoom(scale, ox, oy, vw, vh, mn=1.0, mx=8.0):
    s = max(mn, min(scale, mx))
    maxx = max(0.0, vw * (s - 1) / 2)
    maxy = max(0.0, vh * (s - 1) / 2)
    return s, max(-maxx, min(ox, maxx)), max(-maxy, min(oy, maxy))


ck("zoom maksimum", clamp_zoom(99, 0, 0, 1000, 1000)[0], 8.0)
ck("zoom minimum", clamp_zoom(0.1, 0, 0, 1000, 1000)[0], 1.0)
ck("geser saat pas", clamp_zoom(1.0, 500, -400, 1000, 1000)[1:], (0.0, 0.0))
ck("geser batas", clamp_zoom(3.0, 5000, -5000, 1000, 1000)[1:], (1000.0, -1000.0))


def double_tap(cur, target=2.5, fit=1.0):
    return fit if cur > fit + 0.01 else target


ck("ketuk dari pas", double_tap(1.0), 2.5)
ck("ketuk dari 2.5", double_tap(2.5), 1.0)
ck("ketuk dari 1.7", double_tap(1.7), 1.0)

if FAIL:
    print("GAGAL")
    for f in FAIL:
        print(" -", f)
    sys.exit(1)
print("SEMUA KASUS LOGIKA MEDIA COCOK")
