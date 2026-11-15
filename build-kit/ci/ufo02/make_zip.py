#!/usr/bin/env python3
"""Rakit zip AnyKernel3 dari pohon anykernel + Image.gz, lalu periksa hasilnya.

Kenapa tidak memakai `zip` biasa: dua hal pernah menggigit. Nama berkas di dalam
zip harus relatif terhadap akar anykernel (bukan memuat jalur panjang), dan
Image.gz harus ada di akar zip. Keduanya diperiksa ulang setelah menulis, karena
zip yang "terbuat" tanpa Image.gz akan lolos dari pemeriksaan sekilas.
"""
import pathlib
import sys
import zipfile


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(__doc__)
        print("usage: make_zip.py <anykernel-tree> <Image.gz> <out.zip>")
        return 2
    tree, image, outzip = (pathlib.Path(a) for a in argv[1:4])

    if not tree.is_dir():
        print(f"GAGAL: {tree} bukan direktori")
        return 1
    if not image.is_file():
        print(f"GAGAL: {image} tidak ada")
        return 1

    with zipfile.ZipFile(outzip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(tree.rglob("*")):
            if f.is_dir() or f.suffix == ".zip":
                continue
            z.write(f, f.relative_to(tree).as_posix())
        z.write(image, "Image.gz")

    # Periksa isi, jangan percaya bahwa menulis berarti benar.
    with zipfile.ZipFile(outzip) as z:
        names = z.namelist()
        broken = z.testzip()
        need = {"Image.gz", "anykernel.sh"}
        missing = need - set(names)

    print(f"zip     : {outzip} ({outzip.stat().st_size:,} byte)")
    print(f"berkas  : {len(names)}")
    print(f"rusak   : {broken or 'tidak ada'}")
    print(f"hilang  : {', '.join(sorted(missing)) if missing else 'tidak ada'}")
    return 1 if (broken or missing) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
