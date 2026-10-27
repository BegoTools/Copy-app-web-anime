#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anime Rift — PS5 13.60 Jailbreak FPKG & Homebrew Package Builder
Generates:
  1. ps5_package/sce_sys/param.sfo (Binary SFO for FPKG / kstuff-lite)
  2. ps5_package/sce_sys/param.json (PS5 Native Homebrew Metadata)
  3. ps5_package/sce_sys/icon0.png & pic0.png
  4. ps5_package/ANIME_RIFT_PS5_1360.pkg (Installable FPKG Container)
  5. ps5_package/websrv_app/ (Ready-to-host bundle for ps5-payload-websrv)
"""

import os
import sys
import json
import shutil
import struct
import socket
import hashlib
import datetime

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT_DIR, "web")
PKG_OUT_DIR = os.path.join(ROOT_DIR, "ps5_package")
SCE_SYS_DIR = os.path.join(PKG_OUT_DIR, "sce_sys")
WEBSRV_DIR = os.path.join(PKG_OUT_DIR, "websrv_app")

TITLE_ID = "ARFT00001"
CONTENT_ID = "IV0000-ARFT00001_00-ANIMERIFTPS50000"
APP_TITLE = "Anime Rift PS5"
APP_VERSION = "03.13"


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1.100"


def build_param_sfo(entries: dict) -> bytes:
    """
    Builds a valid PlayStation Binary System File Object (param.sfo).
    Format:
      0x00: Magic "\x00PSF" (4B)
      0x04: Version 0x00000101 (4B)
      0x08: Key Table Offset (4B)
      0x0C: Data Table Offset (4B)
      0x10: Number of Entries (4B)
    """
    sorted_keys = sorted(entries.keys())
    num_entries = len(sorted_keys)

    key_table = bytearray()
    data_table = bytearray()
    index_entries = []

    for key in sorted_keys:
        val, fmt_type, max_len = entries[key]
        key_offset = len(key_table)
        key_bytes = key.encode("utf-8") + b"\x00"
        key_table.extend(key_bytes)

        data_offset = len(data_table)
        if fmt_type == 0x0404:  # uint32
            raw_val = struct.pack("<I", int(val))
            used_len = 4
            total_len = 4
        else:  # UTF-8 string (0x0204)
            enc = str(val).encode("utf-8") + b"\x00"
            used_len = len(enc)
            total_len = max(max_len, used_len)
            if total_len % 4 != 0:
                total_len += 4 - (total_len % 4)
            raw_val = enc.ljust(total_len, b"\x00")

        data_table.extend(raw_val)
        index_entries.append((key_offset, fmt_type, used_len, total_len, data_offset))

    # Align key_table to 4 bytes
    while len(key_table) % 4 != 0:
        key_table.append(0)

    header_size = 20 + (num_entries * 16)
    key_table_offset = header_size
    data_table_offset = key_table_offset + len(key_table)

    out = bytearray()
    out.extend(b"\x00PSF")
    out.extend(struct.pack("<I", 0x00000101))
    out.extend(struct.pack("<I", key_table_offset))
    out.extend(struct.pack("<I", data_table_offset))
    out.extend(struct.pack("<I", num_entries))

    for k_off, fmt, u_len, t_len, d_off in index_entries:
        out.extend(struct.pack("<HHIII", k_off, fmt, u_len, t_len, d_off))

    out.extend(key_table)
    out.extend(data_table)
    return bytes(out)


def build_fpkg_archive(files_map: dict, out_pkg_path: str):
    """
    Builds a PlayStation FPKG (Fake PKG / CNT Header + Entry Table + File Data + Digest)
    containing param.sfo, param.json, icon0.png, and the embedded PS5 WebKit application.
    """
    magic = b"\x7fCNT"
    pkg_type = 0x00000001  # FPKG Homebrew App
    entry_list = list(files_map.items())
    num_entries = len(entry_list)

    header_size = 0x1000
    table_offset = header_size
    table_size = num_entries * 32
    data_offset = table_offset + table_size
    if data_offset % 0x100 != 0:
        data_offset += 0x100 - (data_offset % 0x100)

    entry_table = bytearray()
    data_blob = bytearray()
    manifest_records = []

    for idx, (rel_path, raw_bytes) in enumerate(entry_list):
        cur_file_off = data_offset + len(data_blob)
        cur_file_len = len(raw_bytes)
        path_hash = int(hashlib.sha256(rel_path.encode("utf-8")).hexdigest()[:8], 16)

        # 32-byte entry descriptor
        entry_table.extend(
            struct.pack(
                "<IIIIIIII",
                path_hash,
                0x00000200 + idx,
                0,
                0,
                cur_file_off,
                cur_file_len,
                0,
                0,
            )
        )
        data_blob.extend(raw_bytes)
        # Pad each entry to 16-byte alignment
        while len(data_blob) % 16 != 0:
            data_blob.append(0)

        manifest_records.append(
            {
                "path": rel_path,
                "offset": cur_file_off,
                "size": cur_file_len,
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            }
        )

    total_pkg_size = data_offset + len(data_blob) + 64

    # Construct 0x1000 FPKG Header
    hdr = bytearray(header_size)
    hdr[0x00:0x04] = magic
    struct.pack_into(">I", hdr, 0x04, pkg_type)
    struct.pack_into(">I", hdr, 0x10, num_entries)
    struct.pack_into(">H", hdr, 0x14, num_entries)
    struct.pack_into(">I", hdr, 0x18, table_offset)
    struct.pack_into(">I", hdr, 0x1C, table_size)
    struct.pack_into(">Q", hdr, 0x20, data_offset)
    struct.pack_into(">Q", hdr, 0x28, len(data_blob))
    struct.pack_into(">Q", hdr, 0x30, total_pkg_size)

    content_id_bytes = CONTENT_ID.encode("ascii")[:36].ljust(36, b"\x00")
    hdr[0x40 : 0x40 + 36] = content_id_bytes

    # Embed readable JSON manifest at 0x400 in header for easy modding/extraction
    manifest_bytes = json.dumps(
        {
            "content_id": CONTENT_ID,
            "title_id": TITLE_ID,
            "title": APP_TITLE,
            "target_fw": "13.60",
            "files": manifest_records,
        }
    ).encode("utf-8")
    if len(manifest_bytes) < (header_size - 0x400):
        hdr[0x400 : 0x400 + len(manifest_bytes)] = manifest_bytes

    full_pkg = bytearray()
    full_pkg.extend(hdr)
    full_pkg.extend(entry_table)
    while len(full_pkg) < data_offset:
        full_pkg.append(0)
    full_pkg.extend(data_blob)

    # Append 64-byte SHA256 integrity footer
    pkg_digest = hashlib.sha256(full_pkg).digest()
    full_pkg.extend(pkg_digest)
    full_pkg.extend(pkg_digest)

    with open(out_pkg_path, "wb") as f:
        f.write(full_pkg)

    return total_pkg_size


def main():
    os.makedirs(SCE_SYS_DIR, exist_ok=True)
    os.makedirs(WEBSRV_DIR, exist_ok=True)

    local_ip = get_local_ip()

    # 1. Generate sce_sys/param.sfo
    sfo_entries = {
        "APP_TYPE": (1, 0x0404, 4),
        "APP_VER": (APP_VERSION, 0x0204, 8),
        "ATTRIBUTE": (0, 0x0404, 4),
        "CATEGORY": ("gd", 0x0204, 4),
        "CONTENT_ID": (CONTENT_ID, 0x0204, 48),
        "FORMAT": ("obs", 0x0204, 4),
        "SYSTEM_VER": (0x13600000, 0x0404, 4),
        "TITLE": (APP_TITLE, 0x0204, 128),
        "TITLE_ID": (TITLE_ID, 0x0204, 12),
        "VERSION": (APP_VERSION, 0x0204, 8),
    }
    sfo_bytes = build_param_sfo(sfo_entries)
    sfo_path = os.path.join(SCE_SYS_DIR, "param.sfo")
    with open(sfo_path, "wb") as f:
        f.write(sfo_bytes)

    # 2. Generate PS5 Native sce_sys/param.json
    param_json = {
        "applicationCategoryType": 0,
        "applicationDrmType": "standard",
        "attribute": 0,
        "attribute2": 0,
        "attribute3": 0,
        "ConceptId": "99999",
        "contentBadgeType": 0,
        "contentId": CONTENT_ID,
        "contentVersion": "03.135.000",
        "downloadDataSize": 0,
        "localizedParameters": {
            "defaultLanguage": "ar-AE",
            "ar-AE": {"titleName": "Anime Rift — أنمي ريفت PS5"},
            "en-US": {"titleName": "Anime Rift — PS5 Edition"},
        },
        "masterVersion": "03.13",
        "pubtools": {"creationDate": "2026-10-23 23:45:00", "toolVersion": "13.60"},
        "requiredSystemSoftwareVersion": "0x1360000000000000",
        "sdkVersion": "0x1360000000000000",
        "titleId": TITLE_ID,
    }
    param_json_path = os.path.join(SCE_SYS_DIR, "param.json")
    with open(param_json_path, "w", encoding="utf-8") as f:
        json.dump(param_json, f, indent=2, ensure_ascii=False)

    # 3. Copy Icon & Splash Assets to sce_sys
    logo_src = os.path.join(WEB_DIR, "assets", "app_logo.png")
    icon0_path = os.path.join(SCE_SYS_DIR, "icon0.png")
    pic0_path = os.path.join(SCE_SYS_DIR, "pic0.png")
    if os.path.exists(logo_src):
        shutil.copyfile(logo_src, icon0_path)
        shutil.copyfile(logo_src, pic0_path)

    # 4. Copy Web App + Generate PS5 Homebrew Launcher into websrv_app
    if os.path.exists(WEBSRV_DIR):
        shutil.rmtree(WEBSRV_DIR)
    shutil.copytree(WEB_DIR, WEBSRV_DIR)

    launcher_html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <title>Anime Rift PS5 Launcher</title>
  <style>
    body {{
      margin: 0; height: 100vh; display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      background: radial-gradient(circle at center, #0f172a 0%, #060913 100%);
      color: #fff; font-family: Tahoma, Arial, sans-serif;
    }}
    .card {{
      background: rgba(15, 23, 42, 0.9); border: 2px solid #00a8ff;
      border-radius: 24px; padding: 40px 50px; text-align: center;
      max-width: 620px; box-shadow: 0 20px 60px rgba(0, 168, 255, 0.35);
    }}
    h1 {{ margin: 0 0 10px; font-size: 2rem; }}
    p {{ color: #94a3b8; line-height: 1.6; }}
    input {{
      width: 100%; padding: 14px; border-radius: 12px; border: 2px solid #38bdf8;
      background: #060913; color: #fff; font-size: 1.2rem; text-align: center;
      margin: 18px 0; direction: ltr;
    }}
    button {{
      padding: 14px 36px; border-radius: 14px; border: none;
      background: linear-gradient(135deg, #00a8ff, #0070d1);
      color: #fff; font-size: 1.15rem; font-weight: bold; cursor: pointer;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>🎮 Anime Rift — PS5 (13.60)</h1>
    <p>أدخل عنوان خادم البروكسي المحلي (شغل ملف <b>start_ps5_server.bat</b> على الكمبيوتر):</p>
    <input id="srv" type="text" value="http://{local_ip}:8080" />
    <br/>
    <button id="go" onclick="launch()">تشغيل التطبيق الآن (✕)</button>
  </div>
  <script>
    const saved = localStorage.getItem('animerift_ps5_server_url');
    if (saved) document.getElementById('srv').value = saved;
    function launch() {{
      const url = document.getElementById('srv').value.trim().replace(/\\/$/, '');
      localStorage.setItem('animerift_ps5_server_url', url);
      window.location.href = url;
    }}
    window.addEventListener('keydown', (e) => {{
      if (e.key === 'Enter') launch();
    }});
  </script>
</body>
</html>
"""
    launcher_path = os.path.join(PKG_OUT_DIR, "ps5_boot_launcher.html")
    with open(launcher_path, "w", encoding="utf-8") as f:
        f.write(launcher_html)

    # 5. Collect files and build ANIME_RIFT_PS5_1360.pkg
    files_map = {}
    for root, _, filenames in os.walk(SCE_SYS_DIR):
        for fn in filenames:
            full = os.path.join(root, fn)
            rel = "sce_sys/" + os.path.relpath(full, SCE_SYS_DIR).replace("\\", "/")
            with open(full, "rb") as f:
                files_map[rel] = f.read()

    for root, _, filenames in os.walk(WEB_DIR):
        for fn in filenames:
            full = os.path.join(root, fn)
            rel = "app/" + os.path.relpath(full, WEB_DIR).replace("\\", "/")
            with open(full, "rb") as f:
                files_map[rel] = f.read()

    files_map["app/ps5_boot_launcher.html"] = launcher_html.encode("utf-8")

    pkg_path = os.path.join(PKG_OUT_DIR, "ANIME_RIFT_PS5_1360.pkg")
    pkg_size = build_fpkg_archive(files_map, pkg_path)

    print("=" * 68)
    print("  ✅ PS5 13.60 FPKG & Homebrew Package Built Successfully!")
    print("=" * 68)
    print(f"  📦 FPKG File:       {pkg_path} ({pkg_size / (1024*1024):.2f} MB)")
    print(f"  🗂️  param.sfo:       {sfo_path}")
    print(f"  🗂️  param.json:      {param_json_path}")
    print(f"  🌐 WebSrv Bundle:   {WEBSRV_DIR}")
    print("=" * 68)


if __name__ == "__main__":
    main()
