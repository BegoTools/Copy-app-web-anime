#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
package_dist.py — Assembles clean folder distributions and zip archives for PS5.
Produces:
  1. dist/PPSA91360_SMOKE/ (Minimal Hello World with early logs, zero HTTP/threads)
  2. dist/PPSA91360/       (Full UniRift application with VideoOut UI & embedded server)
  3. release/UniRift_FW13.60_smoke_folder.zip
  4. release/UniRift_FW13.60_folder.zip
  5. release/SHA256SUMS.txt
"""

import os
import sys
import shutil
import hashlib
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
RELEASE = os.path.join(ROOT, "release")
os.makedirs(DIST, exist_ok=True)
os.makedirs(RELEASE, exist_ok=True)

LIBC_PRX = os.path.join(ROOT, "backup", "baseline_artifacts", "PPSA91360", "sce_module", "libc.prx")
SCE_SYS_SRC = os.path.join(ROOT, "ps5_native_src", "sce_sys")
ASSETS_SRC = os.path.join(ROOT, "ps5_native_src", "assets")

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def make_zip(source_dir, arcname, out_zip):
    print(f"Creating archive: {out_zip} ...")
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, os.path.dirname(source_dir))
                zf.write(full_path, rel_path)
    print(f"  Archive created ({os.path.getsize(out_zip):,} bytes)")

def assemble():
    print("=" * 74)
    print("  ASSEMBLING PS5 DISTRIBUTIONS")
    print("=" * 74)

    # 1. Assemble SMOKE variant
    smoke_dir = os.path.join(DIST, "PPSA91360_SMOKE")
    if os.path.exists(smoke_dir):
        shutil.rmtree(smoke_dir)
    os.makedirs(os.path.join(smoke_dir, "sce_module"), exist_ok=True)
    os.makedirs(os.path.join(smoke_dir, "sce_sys"), exist_ok=True)
    os.makedirs(os.path.join(smoke_dir, "assets"), exist_ok=True)

    shutil.copy2(os.path.join(ROOT, "build", "smoke", "eboot.bin"), os.path.join(smoke_dir, "eboot.bin"))
    shutil.copy2(LIBC_PRX, os.path.join(smoke_dir, "sce_module", "libc.prx"))
    for item in os.listdir(SCE_SYS_SRC):
        shutil.copy2(os.path.join(SCE_SYS_SRC, item), os.path.join(smoke_dir, "sce_sys", item))
    shutil.copy2(os.path.join(ASSETS_SRC, "banner.txt"), os.path.join(smoke_dir, "assets", "banner.txt"))

    print(f"[OK] Assembled {smoke_dir}")

    # 2. Assemble FULL variant
    full_dir = os.path.join(DIST, "PPSA91360")
    if os.path.exists(full_dir):
        shutil.rmtree(full_dir)
    os.makedirs(os.path.join(full_dir, "sce_module"), exist_ok=True)
    os.makedirs(os.path.join(full_dir, "sce_sys"), exist_ok=True)

    shutil.copy2(os.path.join(ROOT, "build", "full", "eboot.bin"), os.path.join(full_dir, "eboot.bin"))
    shutil.copy2(LIBC_PRX, os.path.join(full_dir, "sce_module", "libc.prx"))
    for item in os.listdir(SCE_SYS_SRC):
        shutil.copy2(os.path.join(SCE_SYS_SRC, item), os.path.join(full_dir, "sce_sys", item))
    shutil.copytree(ASSETS_SRC, os.path.join(full_dir, "assets"))

    # Also update dist/eboot.elf and dist/AnimeRift_websrv/AnimeRift/eboot.elf
    shutil.copy2(os.path.join(ROOT, "build", "full", "eboot.elf"), os.path.join(DIST, "eboot.elf"))
    websrv_eboot = os.path.join(DIST, "AnimeRift_websrv", "AnimeRift", "eboot.elf")
    if os.path.exists(os.path.dirname(websrv_eboot)):
        shutil.copy2(os.path.join(ROOT, "build", "full", "eboot.elf"), websrv_eboot)

    print(f"[OK] Assembled {full_dir}")

    # 3. Create Release Zips
    smoke_zip = os.path.join(RELEASE, "UniRift_FW13.60_smoke_folder.zip")
    full_zip = os.path.join(RELEASE, "UniRift_FW13.60_folder.zip")

    make_zip(smoke_dir, "PPSA91360", smoke_zip)
    make_zip(full_dir, "PPSA91360", full_zip)

    # 4. Generate SHA256SUMS.txt
    manifest_files = [
        ("smoke_eboot.bin", os.path.join(smoke_dir, "eboot.bin")),
        ("full_eboot.bin", os.path.join(full_dir, "eboot.bin")),
        ("full_eboot.elf", os.path.join(DIST, "eboot.elf")),
        ("libc.prx", os.path.join(full_dir, "sce_module", "libc.prx")),
        ("UniRift_FW13.60_smoke_folder.zip", smoke_zip),
        ("UniRift_FW13.60_folder.zip", full_zip),
    ]

    sums_lines = []
    print("\n" + "=" * 74)
    print("  RELEASE ARTIFACTS & SHA-256 MANIFEST")
    print("=" * 74)
    for label, path in manifest_files:
        h = sha256_file(path)
        sz = os.path.getsize(path)
        line = f"{h}  {sz:>10}  {label}"
        sums_lines.append(line)
        print(f"  {label:<35} {sz:>10,} bytes  SHA256: {h}")

    sums_path = os.path.join(RELEASE, "SHA256SUMS.txt")
    with open(sums_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sums_lines) + "\n")
    print(f"\nWrote manifest to {sums_path}")

if __name__ == "__main__":
    assemble()
