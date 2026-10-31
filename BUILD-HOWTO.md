# BUILD-HOWTO — Synthetica 2.0

## Kebutuhan mesin

- Ubuntu 24.04 (atau setara), 4 core, RAM ≥ 8 GB, disk bebas ± 20 GB.
- Kernel: `clang-18 lld-18 llvm-18 gcc-aarch64-linux-gnu gcc-arm-linux-gnueabi bc flex bison libssl-dev libelf-dev device-tree-compiler cpio lz4 xz-utils python3 patch openssl zip rsync git curl`
- APK: JDK 21 + Android SDK (`platforms;android-36`, `build-tools;36.1.0`, `ndk;29.0.14206865`, `cmake;3.22.1`), set `ANDROID_SDK_ROOT`.

## Cara cepat

```bash
cat Synthetica-2.0-SOURCE.zip.00* > Synthetica-2.0-SOURCE.zip   # gabungkan split
unzip Synthetica-2.0-SOURCE.zip && cd Synthetica-2.0-SOURCE
export ANDROID_SDK_ROOT=$HOME/android-sdk
bash BUILD-SEMUA.sh 4        # argumen = jumlah jobs
```

Hasil akhir di `out/`:
- `Synthetica-2.0.apk` (install)
- `Synthetica-2.0.zip` (flash)
- `Synthetica-2.0-LOG.zip` (log collector, hanya bila perlu)

## Yang dilakukan BUILD-SEMUA.sh

1. **APK**: salin `manager-source` ke folder kerja, timpa tema dengan `build-kit/ci/ksun-overlay`,
   patch MainActivity (GlassBackground + GlassSplash), set `applicationId net.ember.labs` +
   label **Synthetica**, build Gradle release, suntik `libksud.so` dari
   `build-kit/ci/rollercoaster/manager/base.apk`, tanda tangani dengan
   `secretkey/synthetica-2.0.p12`, tulis `MANAGER.json`.
2. **Kernel**: salin identitas APK ke `artifacts/manager/`, jalankan
   `build_chronicle_base.py` dengan `SP_PROFILE=synthetica SP_BUILD_NAME=Synthetica SP_BUILD_KVER=2.0`
   (basis resep 1.16: tree `c1e6f795`, profil daily mq-deadline).
3. **Paket**: `package_release.py` membuat `Synthetica-2.0.zip` (installer Inggris ringkas,
   بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ di awal, الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ saat sukses,
   tanpa backup boot, menulis `<storage>/Synthetica/install-log-*.txt`).

## Verifikasi sebelum flash

```bash
sha256sum out/Synthetica-2.0.apk out/Synthetica-2.0.zip
unzip -p out/Synthetica-2.0.zip anykernel.sh | grep -E "Bismillah pattern|بِسْمِ|الْحَمْدُ" 
gzip -dc artifacts/Image.gz | strings | grep -m1 "^Linux version"   # harus ...-Synthetica-2.0
diff <(sort artifacts/generated.config.txt) <(sort reference-1.16/generated.config.txt) | head
```

## Kalau gagal boot

Jangan wipe. Flash `Synthetica-2.0-LOG.zip`, ambil `<storage>/synthetica-logs/<waktu>/`,
dan restore boot image cadanganmu sendiri (installer 2.0 memang tanpa backup boot).
