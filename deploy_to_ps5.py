#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anime Rift — PS5 13.60 One-Command LAN & USB Deployment Tool
"""

import os
import sys
import ftplib
import socket
import argparse

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")


def upload_ftp_directory(ftp: ftplib.FTP, local_dir: str, remote_dir: str):
    try:
        ftp.mkd(remote_dir)
    except Exception:
        pass
    ftp.cwd(remote_dir)

    for item in os.listdir(local_dir):
        lpath = os.path.join(local_dir, item)
        if os.path.isdir(lpath):
            upload_ftp_directory(ftp, lpath, item)
            ftp.cwd("..")
        else:
            print(f"  --> Uploading {item} ({os.path.getsize(lpath):,} bytes)...")
            with open(lpath, "rb") as f:
                ftp.storbinary(f"STOR {item}", f)


def send_elfldr(ip: str, port: int, elf_path: str):
    print(f"[*] Sending {os.path.basename(elf_path)} to {ip}:{port}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(15)
    s.connect((ip, port))
    with open(elf_path, "rb") as f:
        data = f.read()
    s.sendall(data)
    s.close()
    print("[✔] Payload launched successfully on PS5!")


def main():
    parser = argparse.ArgumentParser(description="Anime Rift PS5 Deployment Tool")
    parser.add_argument("--ip", help="PS5 Console IP Address")
    parser.add_argument("--port", type=int, default=2121, help="FTP port (default: 2121)")
    parser.add_argument(
        "--variant",
        choices=["smoke", "full"],
        default="smoke",
        help="Build variant to deploy: smoke (minimal Hello World for Phase C verification) or full (complete UniRift app)",
    )
    parser.add_argument(
        "--mode",
        choices=["shadowmount", "websrv", "elfldr", "usb"],
        default="shadowmount",
        help="Deployment mode: shadowmount (folder to /data/homebrew/PPSA91360), websrv (/data/homebrew/AnimeRift), elfldr (port 9021), or usb",
    )
    parser.add_argument("--usb", help="Target USB Drive letter (e.g. E: or F:)")
    parser.add_argument(
        "--include-images",
        action="store_true",
        help="Include .ffpkg/.ffpfsc on USB (WARNING: do not place alongside folder with same Title ID to avoid duplicate mount)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print(f"  🚀 ANIME RIFT — PS5 13.60 DEPLOYMENT ({args.variant.upper()} VARIANT) 🚀")
    print("=" * 70)

    source_dir = os.path.join(DIST, "PPSA91360_SMOKE" if args.variant == "smoke" else "PPSA91360")
    if not os.path.exists(source_dir):
        print(f"[!] Error: Source directory does not exist: {source_dir}. Run build_native_pipeline.py first.")
        sys.exit(1)

    if args.mode == "usb":
        if not args.usb:
            print("[!] Error: Specify --usb <drive> (e.g. --usb E:)")
            sys.exit(1)
        import shutil

        target_hb = os.path.join(args.usb, "homebrew")
        os.makedirs(target_hb, exist_ok=True)
        print(f"[*] Staging SINGLE clean folder source to USB: {target_hb}...")

        ppsa_dst = os.path.join(target_hb, "PPSA91360")
        if os.path.exists(ppsa_dst):
            print(f"  -> Removing old {ppsa_dst} to avoid duplicate stale files...")
            shutil.rmtree(ppsa_dst)
        shutil.copytree(source_dir, ppsa_dst)
        print(f"[✔] Staged {source_dir} -> {ppsa_dst}")

        if args.include_images:
            print("[!] Copying .ffpkg and .ffpfsc images (Experimental)...")
            shutil.copy2(os.path.join(DIST, "PPSA91360.ffpkg"), os.path.join(target_hb, "PPSA91360.ffpkg"))
            shutil.copy2(os.path.join(DIST, "PPSA91360.ffpfsc"), os.path.join(target_hb, "PPSA91360.ffpfsc"))

        print("\n[✔] USB deployment complete! Safe single-source staged for ShadowMountPlus.")
        return

    if not args.ip:
        print("[!] Error: PS5 IP address required. Use --ip <PS5_IP>")
        sys.exit(1)

    if args.mode == "elfldr":
        send_elfldr(args.ip, 9021, os.path.join(DIST, "eboot.elf"))
        return

    print(f"[*] Connecting to PS5 FTP service at {args.ip}:{args.port}...")
    ftp = ftplib.FTP()
    ftp.connect(args.ip, args.port, timeout=15)
    ftp.login("anonymous", "codex")
    print("[✔] Connected to PS5 FTP!")

    if args.mode == "shadowmount":
        print(f"[*] Uploading Native PPSA91360 ({args.variant}) for ShadowMountPlus...")
        ftp.cwd("/data")
        try:
            ftp.mkd("homebrew")
        except Exception:
            pass
        upload_ftp_directory(ftp, source_dir, "/data/homebrew/PPSA91360")
        print("[✔] Native PPSA91360 deployed! ShadowMountPlus will auto-register it.")

    elif args.mode == "websrv":
        print("[*] Uploading AnimeRift for websrv (/data/homebrew/AnimeRift)...")
        upload_ftp_directory(
            ftp,
            os.path.join(DIST, "AnimeRift_websrv", "AnimeRift"),
            "/data/homebrew/AnimeRift",
        )
        print("[✔] Anime Rift websrv app deployed successfully!")

    ftp.quit()
    print("\n[✔] Deployment complete 100%!")


if __name__ == "__main__":
    main()
