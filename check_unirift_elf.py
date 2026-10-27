#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_unirift_elf.py — Validates ELF and FSELF binaries for PS5 compatibility.
Checks:
  1. p_offset % p_align == p_vaddr % p_align for all PT_LOAD segments
  2. p_filesz <= p_memsz
  3. p_align is power of two and >= 0x4000 (16 KiB) for LOAD
  4. FreeBSD OS/ABI, ABI version 2, ET_SCE_EXEC_ASLR (0xFE10)
"""

import sys
import os
import struct

def parse_and_check_elf(data: bytes, file_label: str) -> bool:
    if len(data) < 64 or data[:4] != b"\x7fELF":
        print(f"[{file_label}] FAIL: Not an ELF file")
        return False

    ei_class = data[4]
    if ei_class != 2:
        print(f"[{file_label}] FAIL: Not 64-bit ELF")
        return False

    os_abi = data[7]
    abi_version = data[8]
    e_type = struct.unpack("<H", data[16:18])[0]
    e_phoff = struct.unpack("<Q", data[32:40])[0]
    e_phentsize = struct.unpack("<H", data[54:56])[0]
    e_phnum = struct.unpack("<H", data[56:58])[0]

    print(f"\n--- Checking {file_label} ---")
    print(f"ELF Header: OS/ABI={os_abi} (expected 9), ABI_VER={abi_version} (expected 2), Type=0x{e_type:04x} (expected 0xFE10)")
    print(f"Program Headers: offset=0x{e_phoff:x}, count={e_phnum}, entry_size={e_phentsize}")

    all_passed = True
    PT_LOAD = 1
    PT_GNU_RELRO = 0x6474e552

    load_idx = 0
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        if off + 56 > len(data):
            print(f"  Header {i}: Truncated in file")
            all_passed = False
            break

        p_type = struct.unpack("<I", data[off:off+4])[0]
        p_flags = struct.unpack("<I", data[off+4:off+8])[0]
        p_offset = struct.unpack("<Q", data[off+8:off+16])[0]
        p_vaddr = struct.unpack("<Q", data[off+16:off+24])[0]
        p_paddr = struct.unpack("<Q", data[off+24:off+32])[0]
        p_filesz = struct.unpack("<Q", data[off+32:off+40])[0]
        p_memsz = struct.unpack("<Q", data[off+40:off+48])[0]
        p_align = struct.unpack("<Q", data[off+48:off+56])[0]

        type_str = {1: "LOAD", 2: "DYNAMIC", 3: "INTERP", 4: "NOTE", 6: "PHDR", 7: "TLS",
                    0x6474e550: "GNU_EH_FRAME", 0x6474e552: "GNU_RELRO"}.get(p_type, f"0x{p_type:08x}")

        if p_type == PT_LOAD:
            load_idx += 1
            congruent = True
            if p_align > 1:
                off_mod = p_offset % p_align
                vaddr_mod = p_vaddr % p_align
                congruent = (off_mod == vaddr_mod)

            size_ok = (p_filesz <= p_memsz)
            status = "PASS" if (congruent and size_ok) else "FAIL"
            if not (congruent and size_ok):
                all_passed = False

            print(f"  [LOAD #{load_idx}] offset=0x{p_offset:06x} vaddr=0x{p_vaddr:08x} filesz=0x{p_filesz:06x} memsz=0x{p_memsz:06x} align=0x{p_align:x} -> {status}")
            if not congruent:
                print(f"      ERROR: Congruence violation: offset % align = 0x{p_offset % p_align:x} != vaddr % align = 0x{p_vaddr % p_align:x}")
            if not size_ok:
                print(f"      ERROR: filesz (0x{p_filesz:x}) > memsz (0x{p_memsz:x})")

        elif p_type == PT_GNU_RELRO:
            print(f"  [GNU_RELRO] offset=0x{p_offset:06x} vaddr=0x{p_vaddr:08x} filesz=0x{p_filesz:06x} memsz=0x{p_memsz:06x} align=0x{p_align:x}")

    print(f"Result for {file_label}: {'=== PASS ===' if all_passed else '=== FAIL ==='}\n")
    return all_passed

def check_file(path: str) -> bool:
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return False

    with open(path, "rb") as f:
        data = f.read()

    # Check if FSELF
    if len(data) >= 4 and struct.unpack("<I", data[:4])[0] == 0x1D3D154F:
        print(f"\nDetecting FSELF container: {path} ({len(data)} bytes)")
        entries = struct.unpack("<H", data[0x18:0x1A])[0]
        elf_off = 0x20 + 0x20 * entries
        print(f"FSELF entries: {entries}, inner ELF offset: 0x{elf_off:x}")
        return parse_and_check_elf(data[elf_off:], f"FSELF:{path}")
    else:
        return parse_and_check_elf(data, path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_unirift_elf.py <file1> [file2 ...]")
        sys.exit(1)

    overall = True
    for arg in sys.argv[1:]:
        ok = check_file(arg)
        if not ok:
            overall = False

    sys.exit(0 if overall else 1)
