# Synthetica Manager 6.5.0

Status: **unsigned APK built and verified. Not signed, so not installable as an update.**

## What changed from 6.0.0

### 1. Two themes removed
`ANIME_WIBU` and `GOTHIC_CRIMSON` are gone, on request, because seven themes with near
identical motion made the selector noisy rather than useful. `RETRO_ARCADE` stays.

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
| RETRO_ARCADE | phosphor amber `FFB000` | bright amber `FFCC4D` | dim amber `D98E00` |

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
- RETRO_ARCADE — ease-in fall, ease-out rise, like gravity

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
