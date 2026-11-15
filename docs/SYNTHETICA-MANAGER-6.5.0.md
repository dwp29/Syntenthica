# Synthetica Manager 6.5.0

> **Retro Arcade juga sudah dihapus — 6.5.1, permanen.** Dokumen ini ditulis saat
> `RETRO_ARCADE` masih ada, jadi bagian di bawah yang menyebutnya sebagai tema
> yang bertahan **sudah tidak berlaku**. Empat tema yang tersisa: `PIXEL`,
> `CYBERPUNK`, `IOS_GLASS`, `NEON`. Rinciannya ada di bagian terakhir,
> "Retro Arcade: dihapus permanen".

Status: **unsigned APK built and verified. Not signed, so not installable as an update.**

## What changed from 6.0.0

### 1. Two themes removed
`ANIME_WIBU` and `GOTHIC_CRIMSON` are gone, on request, because seven themes with near
identical motion made the selector noisy rather than useful. `RETRO_ARCADE` was left alone
in 6.5.0 and then removed in 6.5.1 (see the last section).

Removal had to be all-at-once: every `when` over `ManagerStyle` is exhaustive, so deleting
the enum entries alone breaks compilation. 53 dispatch points were cleared across
`Glass.kt`, `ThemedHero.kt`, `VisualStyles.kt` and `AppearanceControls.kt`, together with:

- `ic_emblem_anime.png`, `ic_emblem_gothic.png`
- `theme_banner_anime.jpg`, `theme_banner_anime_far.jpg`, `theme_banner_gothic.jpg`,
  `theme_banner_gothic_far.jpg`
- `anime_zenmaru.ttf`, `anime_rampart.ttf`
- `AnimeShapes`, `GothicShapes`, `AnimeTypography`, `GothicTypography`
- `AnimeWibuSplash`, `GothicCrimsonSplash`, `AnimeBannerHero`, `GothicBannerHero`
- `theme50_anime*`, `theme50_gothic*` strings in both languages

Verified in the built APK: no `anime_wibu`, `gothic_crimson`, `ANIME WIBU` or
`GOTHIC CRIMSON` anywhere in the DEX; 2 banner JPEGs instead of 6.

### 2. Accents carry the theme instead of tinting it
The old accent table was mislabelled and faint. The ids were still `cyan`/`pink`/`violet`/
`lime`, but cyan resolved to `0xFFFF665E` (salmon), pink to `0xFFF4F3ED` (near-white),
violet to `0xFFFFC785` (peach), lime to `0xFFAFE2C5` (pale mint). Nine places additionally
drew the accent at alpha 0.05–0.20, which is why it read as a wash.

`accentTierForStyle` now returns three saturated colours per theme in that theme's own key:

| Theme | Tier 1 (primary) | Tier 2 | Tier 3 |
|---|---|---|---|
| PIXEL | signal red `FF5548` | orange `FF8A3D` | amber `FFC785` |
| CYBERPUNK | acid volt `D4FF00` | lime `9CFF3B` | pale volt `FBFF9E` |
| IOS_GLASS | system blue `3E9BFF` | sky `6FB8FF` | deep blue `1E6FD9` |
| NEON | cyan `00F0FF` | electric cyan `5BF6FF` | deep cyan `00B8CC` |
| ~~RETRO_ARCADE~~ | ~~phosphor amber `FFB000`~~ | ~~bright amber `FFCC4D`~~ | ~~dim amber `D98E00`~~ (dihapus 6.5.1) |

Tier 2 and 3 are wired into `tertiary` and `secondary` so badges, charts and dock details
stop being grey filler. The nine faint accent alphas were raised to 0.22–0.34.
`signatureColorForStyle` provides each theme's identifying colour.

### 3. Motion suits the subject
All seven themes previously shared one linear 0..1 sweep with one duration and one easing.
`ThemeMotion` shapes the cycle per theme:

- PIXEL — quantised to 12 hard steps; a dot matrix has no in-between
- CYBERPUNK — sweeps for 80% of the cycle, then holds still
- IOS_GLASS — smoothstep over 9 s; nothing snaps
- NEON — triangle wave, even rise and fall
- ~~RETRO_ARCADE~~ — ~~ease-in fall, ease-out rise, like gravity~~ (dihapus 6.5.1)

The speed setting scales all five by the same factor.

### 4. Custom background image (new)
`CustomWallpaper.kt`: import a picture from the gallery, stored in app-private storage, with
opacity (0.15–1.0) and blur (0–24 dp) controls. It composites **under** the theme canvas, so
theme art remains as texture. AMOLED still forces true black and skips both. A corrupt or
deleted file falls back to the procedural background; images are downsampled to 1600 px wide.

## Identity

| | |
|---|---|
| package | `net.ember.labs` |
| versionName | `6.5.0` |
| versionCode | `75000` |
| UAPI | 4 |
| APK (unsigned) | 9 187 079 bytes |
| SHA-256 | `5e8c405a4d6e7a071d5d8e15d219a102ad699709ad8db80cd315f1b7ccb14e9d` |
| built by | CI run `43717733729`, workflow `synthetica65-manager.yml` |
| Drive | `Synthetica-Manager-6.5.0-UNSIGNED.apk`, id `1vaE9I_aFA5UoLynXnCVjmNpJnx9rEHIl` |

## Not done, and why

**It is not signed.** The key for `net.ember.labs` is `fe833710a733f630…` (1381-byte DER,
`0x565`), which signs the shipped 6.0.0 APK. That key is **not in this repository and never
was** — `git log --all` shows no `.p12`/`.jks` for it. Without it this APK cannot be signed
to match, so it will not install as an update over 6.0.0, and a kernel pinned to
`fe833710…` will not accept it.

**Nothing was tested on a device.** No install, no rendering, no gesture, no wallpaper
import. The only proofs are: it compiles, the identity in the manifest is correct, the
DEX contents match the intent, and it is zip- and 16 KiB-aligned.

## CI gates that changed

`tests/verify_synthetica60_apk.py` no longer demands the retired emblems or banners, and now
asserts the two retired style ids are **absent** from the DEX. `build_manager_60_standalone.py`
and `tests/test_synthetica60_standalone.py` moved to 6.5.0 / 75000.
`tests/test_synthetica61_retro_anime.py` was deleted: it locked all three 6.1 themes and
could not survive the removal of two of them.

## Retro Arcade: dihapus permanen (6.5.1)

Atas permintaan pemilik proyek, Retro Arcade dicabut seluruhnya — bukan
disembunyikan dari pemilih tema. Tidak ada jalur untuk mengaktifkannya kembali.

Yang dihapus:

- entri enum `RETRO_ARCADE`, sehingga `ManagerStyle` tinggal empat nilai dan
  setiap `when` atasnya kembali exhaustive tanpa cabang mati;
- `retro_arcade` sebagai id preferensi `manager_visual_style`; konfigurasi JSON
  lama yang masih memuatnya akan jatuh ke `PIXEL` lewat `fromId`;
- `RetroShapes`, `RetroTypography`, `RetroArcadeSplash`, `RetroBannerHero`, dan
  seluruh cabang RETRO di `Glass.kt`, `ThemedHero.kt`, `VisualStyles.kt`,
  `AppearanceControls.kt`;
- lima aset: `ic_emblem_retro.png`, `theme_banner_retro.jpg`,
  `theme_banner_retro_far.jpg`, `retro_pressstart.ttf`, `retro_vt323.ttf`;
- string `theme50_retro` dan `theme50_retro_detail` di kedua bahasa.

Gate `tests/verify_synthetica60_apk.py` sekarang menolak build yang memuat
`anime_wibu`, `gothic_crimson`, atau `retro_arcade` di DEX, dan mewajibkan tepat
empat emblem serta nol banner JPEG.

Catatan jujur soal prosesnya: penghapusan pertama (commit `d346b27`) lolos test
host tetapi **gagal dikompilasi** di CI (run `43729698703`) — regex yang saya
pakai untuk memotong blok `RETRO_ARCADE -> {}` ikut memakan `fun shapesForStyle`
dan `data class ManagerDockSpec`. Keduanya dipulihkan di commit `3fd95d6`, dan
run `43729971270` hijau. Pelajarannya: "nol sisa RETRO" bukan bukti selesai;
hanya kompilasi penuh yang membuktikan.
