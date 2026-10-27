#!/usr/bin/env python3
"""Restore the pinned Windows compiler without committing its download/cache."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = "llvm-mingw-20240917-ucrt-x86_64"
URL = f"https://github.com/mstorsjo/llvm-mingw/releases/download/20240917/{VERSION}.zip"
SHA256 = "7e11dfc9c576046dd2eb37187b6f2fd1ace8f2e2259ee6434174262d62ecaee2"
COMPILER_ROOT = ROOT / "tools" / "extracted" / "llvm-mingw"
BIN = COMPILER_ROOT / VERSION / "bin"
BOILERPLATE = ROOT / "tools" / "ps5-native-app-boilerplate"
HOST = BOILERPLATE / "build" / "host"
SDK = ROOT / "tools" / "extracted" / "ps5-payload-sdk" / "ps5-payload-sdk" / "target"
ZLIB = ROOT / "tools" / "extracted" / "zlib" / "zlib-1.3.2"


def check():
    required = [BIN / "clang++.exe", BIN / "ld.lld.exe",
                HOST / "ps5-native-tool.exe", SDK / "include" / "stdio.h",
                SDK / "lib" / "libSceLibcInternal.so",
                ROOT / "backup/baseline_artifacts/PPSA91360/sce_module/libc.prx"]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.is_file()]
    if missing:
        print("Missing build dependencies:\n  " + "\n  ".join(missing))
        return False
    print("Windows native build dependencies are available.")
    return True


def install_compiler():
    if (BIN / "clang++.exe").is_file():
        return
    cache = ROOT / "tools" / "downloads"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / (VERSION + ".zip")
    if not archive.exists():
        partial = archive.with_suffix(".zip.partial")
        print("Downloading pinned LLVM-MinGW toolchain...", flush=True)
        urllib.request.urlretrieve(URL, partial)
        partial.replace(archive)
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != SHA256:
        raise RuntimeError(f"Compiler checksum mismatch: {archive}")
    COMPILER_ROOT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            destination = (COMPILER_ROOT / member.filename).resolve()
            if not destination.is_relative_to(COMPILER_ROOT.resolve()):
                raise RuntimeError("Archive member escapes compiler directory")
        bundle.extractall(COMPILER_ROOT)


def rebuild_host_tool():
    HOST.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PATH"] = str(BIN) + os.pathsep + env.get("PATH", "")

    def run(*args):
        subprocess.run([str(a) for a in args], check=True, env=env, cwd=ROOT)

    objects = []
    for source in ("adler32", "compress", "crc32", "deflate", "gzclose", "gzlib",
                   "gzread", "gzwrite", "infback", "inffast", "inflate", "inftrees",
                   "trees", "uncompr", "zutil"):
        obj = HOST / (source + ".o")
        run(BIN / "clang.exe", "-O2", "-I", ZLIB, "-c", ZLIB / (source + ".c"), "-o", obj)
        objects.append(obj)
    run(BIN / "llvm-ar.exe", "rcs", HOST / "libz.a", *objects)
    native = BOILERPLATE / "tooling" / "native"
    sources = [native / (name + ".cpp") for name in
               ("native_app_builder", "self_container", "elf_object", "sce_module_writer")]
    run(BIN / "clang++.exe", "-std=c++20", "-O2", "-static", "-I", ZLIB,
        *sources, HOST / "libz.a", "-o", HOST / "ps5-native-tool.exe")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check dependencies without downloading")
    parser.add_argument("--rebuild-host-tool", action="store_true", help="Rebuild the bundled converter from source")
    args = parser.parse_args()
    if args.check:
        return 0 if check() else 1
    if os.name != "nt":
        parser.error("This setup restores the Windows pipeline; use the upstream WSL/Linux instructions on other hosts")
    install_compiler()
    if args.rebuild_host_tool or not (HOST / "ps5-native-tool.exe").is_file():
        rebuild_host_tool()
    return 0 if check() else 1


if __name__ == "__main__":
    raise SystemExit(main())
