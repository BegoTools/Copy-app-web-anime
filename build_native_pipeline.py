#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_native_pipeline.py — Comprehensive Native PS5 Build Pipeline
Supports:
  - 'smoke': Minimal Hello World (Phase C), pure VideoOut, early lifecycle logging, zero HTTP/threads.
  - 'full':  Complete UniRift / Anime Rift application (Phase G).
Enforces:
  - Clean rebuild from source
  - 16 KiB PT_LOAD alignment validation via check_unirift_elf
  - FSELF packaging and validation
"""

import os
import sys
import shutil
import subprocess
import struct
import hashlib

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
LLVM_BIN = os.path.join(ROOT, "tools", "extracted", "llvm-mingw", "llvm-mingw-20240917-ucrt-x86_64", "bin")
CLANG = os.path.join(LLVM_BIN, "clang++.exe")
LLD = os.path.join(LLVM_BIN, "ld.lld.exe")
SDK_ROOT = os.path.join(ROOT, "tools", "extracted", "ps5-payload-sdk", "ps5-payload-sdk")
SDK_LIB = os.path.join(SDK_ROOT, "target", "lib")
SDK_INC = os.path.join(SDK_ROOT, "target", "include")
SDK_CXX_INC = os.path.join(SDK_INC, "c++", "v1")

TOOL = os.path.join(ROOT, "tools", "ps5-native-app-boilerplate", "build", "host", "ps5-native-tool.exe")
LINKER_SCRIPT = os.path.join(ROOT, "ps5_native_src", "tooling", "native", "ps5-pie.ld")
SYMBOLS_MAP = os.path.join(ROOT, "ps5_native_src", "tooling", "native", "app-symbols.map")

CRT_CPP = os.path.join(ROOT, "ps5_native_src", "tooling", "native", "app_crt.cpp")
RUNTIME_CPP = os.path.join(ROOT, "ps5_native_src", "tooling", "native", "app_cpp_runtime.cpp")

MODULE_SDK = 0x02000009
COMPANION_SDK = 0x08050001
FSELF_MAGIC = 0x1D3D154F

def run_cmd(cmd, env=None, cwd=ROOT):
    merged_env = os.environ.copy()
    merged_env["PATH"] = LLVM_BIN + os.pathsep + merged_env.get("PATH", "")
    if env:
        merged_env.update(env)
    print(f"  [RUN] {' '.join(cmd[:4])} ...")
    res = subprocess.run(cmd, env=merged_env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"STDERR:\n{res.stderr}")
        print(f"STDOUT:\n{res.stdout}")
        raise RuntimeError(f"Command failed with exit code {res.returncode}")
    return res.stdout

def compile_object(src_file, obj_file, extra_defs=None):
    os.makedirs(os.path.dirname(obj_file), exist_ok=True)
    cmd = [
        CLANG,
        "-target", "x86_64-sie-ps5",
        "-std=c++20",
        "-O2",
        "-Wall", "-Wextra",
        "-fno-exceptions", "-fno-rtti",
        "-fno-stack-protector", "-fno-plt", "-femulated-tls",
        "-fvisibility-nodllstorageclass=default",
        "-ffunction-sections", "-fdata-sections",
        "-isysroot", SDK_ROOT,
        "-isystem", SDK_CXX_INC,
        "-isystem", SDK_INC,
        f"-I{os.path.join(ROOT, 'ps5_native_src', 'src')}",
        "-c", src_file,
        "-o", obj_file
    ]
    if extra_defs:
        for d in extra_defs:
            cmd.append(f"-D{d}")
    run_cmd(cmd)

def link_pie(obj_files, out_pie):
    os.makedirs(os.path.dirname(out_pie), exist_ok=True)
    so_files = [os.path.join(SDK_LIB, f) for f in os.listdir(SDK_LIB) if f.endswith(".so")]
    cmd = [
        LLD,
        "-m", "elf_x86_64",
        "-pie",
        "-z", "max-page-size=0x4000",
        "-T", LINKER_SCRIPT,
        "--eh-frame-hdr",
        "--version-script", SYMBOLS_MAP,
        "-e", "_start",
        "-o", out_pie
    ]
    cmd.extend(obj_files)
    cmd.append("--as-needed")
    cmd.extend(so_files)
    run_cmd(cmd)

def convert_elf(in_pie, out_elf):
    cmd = [
        TOOL, "link",
        "--in", in_pie,
        "--out", out_elf,
        "--stub-dir", SDK_LIB,
        "--module-sdk", hex(MODULE_SDK),
        "--companion-sdk", hex(COMPANION_SDK),
        "--file-name", "eboot.elf"
    ]
    run_cmd(cmd)

def sign_fself(in_elf, out_bin):
    os.makedirs(os.path.dirname(out_bin), exist_ok=True)
    cmd = [
        TOOL, "self",
        "--sign",
        "--in", in_elf,
        "--out", out_bin,
        "--magic", hex(FSELF_MAGIC)
    ]
    run_cmd(cmd)

def build_variant(variant="full"):
    print("=" * 74)
    print(f"  BUILDING PS5 NATIVE VARIANT: {variant.upper()}")
    print("=" * 74)

    build_dir = os.path.join(ROOT, "build", variant)
    obj_dir = os.path.join(build_dir, "obj")
    os.makedirs(obj_dir, exist_ok=True)

    # 1. Compile CRT and runtime
    crt_obj = os.path.join(obj_dir, "app_crt.o")
    runtime_obj = os.path.join(obj_dir, "app_cpp_runtime.o")
    compile_object(CRT_CPP, crt_obj)
    compile_object(RUNTIME_CPP, runtime_obj)

    # 2. Compile app sources
    extra_defs = ["UNIRIFT_SMOKE=1"] if variant == "smoke" else []
    demo_obj = os.path.join(obj_dir, "demo_renderer.o")
    main_obj = os.path.join(obj_dir, "main.o")

    demo_src = os.path.join(ROOT, "ps5_native_src", "src", "demo_renderer.cpp")
    main_src = os.path.join(ROOT, "ps5_native_src", "src", "main.cpp")
    if variant == "smoke":
        main_src = os.path.join(ROOT, "ps5_native_src", "src", "main_smoke.cpp")

    compile_object(demo_src, demo_obj, extra_defs)
    compile_object(main_src, main_obj, extra_defs)

    # 3. Link PIE
    pie_elf = os.path.join(build_dir, "llvm-pie.elf")
    link_pie([crt_obj, runtime_obj, demo_obj, main_obj], pie_elf)

    # 4. Convert to PS5 ELF
    native_elf = os.path.join(build_dir, "eboot.elf")
    convert_elf(pie_elf, native_elf)

    # 5. Sign to FSELF
    fself_bin = os.path.join(build_dir, "eboot.bin")
    sign_fself(native_elf, fself_bin)

    # 6. Validate with check_unirift_elf
    sys.path.insert(0, ROOT)
    import check_unirift_elf
    print("\n--- Validating Generated ELF ---")
    elf_pass = check_unirift_elf.check_file(native_elf)
    print("\n--- Validating Generated FSELF ---")
    fself_pass = check_unirift_elf.check_file(fself_bin)

    if not (elf_pass and fself_pass):
        raise RuntimeError("Validation failed on generated artifacts!")

    print(f"\n[PASS] Variant '{variant}' successfully built and verified!")
    return native_elf, fself_bin

if __name__ == "__main__":
    var = sys.argv[1] if len(sys.argv) > 1 else "full"
    build_variant(var)
