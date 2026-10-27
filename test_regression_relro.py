#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_regression_relro.py — Regression Test Suite for PS5 ELF/FSELF RELRO & 16 KiB Congruence.
Verifies:
  1. Congruence on all PT_LOAD segments (offset % align == vaddr % align)
  2. Memory bounds (filesz <= memsz)
  3. FSELF inner ELF extraction integrity
  4. Both smoke (minimal) and full (complex RELRO) variants pass cleanly
"""

import os
import sys
import subprocess

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import check_unirift_elf

def test_variant(variant_name: str):
    print(f"\n=======================================================")
    print(f"  RUNNING REGRESSION TEST: {variant_name.upper()} VARIANT")
    print(f"=======================================================")

    elf_path = os.path.join(ROOT, "build", variant_name, "eboot.elf")
    fself_path = os.path.join(ROOT, "build", variant_name, "eboot.bin")

    assert os.path.exists(elf_path), f"ELF not found: {elf_path}"
    assert os.path.exists(fself_path), f"FSELF not found: {fself_path}"

    print(f"\n[Test 1] Checking Raw ELF: {elf_path}")
    elf_ok = check_unirift_elf.check_file(elf_path)
    assert elf_ok, f"Raw ELF congruence check failed for {variant_name}"

    print(f"\n[Test 2] Checking FSELF Container & Embedded ELF: {fself_path}")
    fself_ok = check_unirift_elf.check_file(fself_path)
    assert fself_ok, f"FSELF container check failed for {variant_name}"

    print(f"\n✔ ALL REGRESSION CHECKS PASSED FOR {variant_name.upper()}!")

if __name__ == "__main__":
    test_variant("smoke")
    test_variant("full")
    print("\n🎉 ZERO CONGRUENCE VIOLATIONS DETECTED ACROSS ALL VARIANTS! 100% REGRESSION PASS!")
