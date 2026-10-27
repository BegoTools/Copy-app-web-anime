# تقرير خط الأساس التشخيصي (Baseline Report) — UniRift / Anime Rift PS5 13.60

**تاريخ التوثيق:** 24 أكتوبر 2026  
**الجهاز المستهدف:** PlayStation 5 — Firmware 13.60 (Jailbreak + kstuff-lite + ShadowMountPlus 1.7-beta5fix1)  
**معرّف التطبيق (Title ID):** `PPSA91360`  
**رمز المحتوى (Content ID):** `UP9000-PPSA91360_00-ANIMERIFTPS51360`  

---

## 1. معلومات البيئة والأدوات (Build Provenance & Environment)

| الأداة / العنصر | الإصدار / المسار | الحالة |
|---|---|---|
| Host OS | Windows 10/11 x86_64 (PowerShell 5.1 / Python 3.11.15) | Active |
| Host C/C++ Compiler | Clang 19.1.0 (`tools/extracted/llvm-mingw/.../bin/clang.exe`) | Verified |
| Host C++ Compiler | Clang++ 19.1.0 (`tools/extracted/llvm-mingw/.../bin/clang++.exe`) | Verified |
| Target Linker | LLD 19.1.0 (`tools/extracted/llvm-mingw/.../bin/ld.lld.exe`) | Verified |
| Target Profile | `x86_64-sie-ps5` (FreeBSD 9 ABI 2, Zen2, ET_SCE_EXEC_ASLR 0xFE10) | Verified in Clang |
| PS5 Payload SDK | `tools/extracted/ps5-payload-sdk/ps5-payload-sdk` | Verified headers & stubs |
| Source Repository | `tools/ps5-native-app-boilerplate` (Git commit `470695e0c557f99ff2df0e36e4df713c5e636526`) | Verified |
| Application Sources | `ps5_native_src/src/main.cpp`, `ps5_native_src/src/demo_renderer.cpp` | Verified |
| Converter Source | `ps5_native_src/tooling/native/sce_module_writer.cpp` | **خلل بنيوي مؤكد (P0)** |

---

## 2. جدول البصمات والأحجام لملفات خط الأساس (Baseline Artifacts Manifest)

جميع الملفات أدناه تم حفظ نسخة أصلية منها في مجلد: `backup/baseline_artifacts/`.

| الملف | الحجم (بايت) | بصمة SHA-256 | نتيجة الفحص (check_unirift_elf) |
|---|---|---|---|
| `dist/eboot.elf` | 75,460 | `8bb5ce7ca634a4d9a9b31b2ac341b9b54e413fd7497417729bbf74f2ae312c18` | **FAIL** (LOAD #3 congruence) |
| `dist/PPSA91360/eboot.bin` | 30,244 | `a525b9e926a5f94b8b436aed2b6dcd9c7d3cc371e07be186188e61bb1d5bd625` | **FAIL** (Inner ELF LOAD #3) |
| `dist/PPSA91360/sce_module/libc.prx` | 1,284,674 | `e6ff45d16adf687855cc3b33b0c8a4132b6504360b221e0a34c7e99fb3ba0036` | **PASS** (Clean-room shim) |
| `dist/PPSA91360/sce_sys/param.json` | 931 | `d5203a2e876e0540fc34e905426c94f0257a9b220f400a0242f28c02120def9a` | Valid JSON / Schema PASS |
| `dist/PPSA91360.ffpkg` | 68,681,728 | `a3d5b6bbd2ed072caac26a3c09ef5a276f077c477f2a6134d7229fae6280ea16` | Superblock UFS2 valid |
| `dist/PPSA91360.ffpfsc` | 43,122,688 | `c6457ccc211f15541f942c67c971e46fa95dbf33bc5437200058a8b2582934c3` | MkPFS container v2 |
| `dist/AnimeRift_websrv/AnimeRift/ffplay.elf` | 41,849,656 | `53435afe6d7a16792eb5cbc3002aa044052e907e792ad33c94850c3f87d388ad` | **Non-native** (System V DYN 0x0003) |

---

## 3. مخطط شجرة الاعتمادية وموقع توليد RELRO (Dependency Graph)

```
[src/main.cpp + demo_renderer.cpp + app_crt.cpp + app_cpp_runtime.cpp]
                   │
                   ▼  (clang -target x86_64-sie-ps5)
         [Object Files: *.o]
                   │
                   ▼  (ld.lld -T ps5-pie.ld --as-needed target/lib/*.so)
     [Intermediate PIE: llvm-pie.elf]
          ├── .text (0x0000..0x35A8)
          ├── .rodata / eh_frame (0x4000..0x5598)
          ├── .data.rel.ro (0x8000..0xC108)  <-- بداية نطاق RELRO الحقيقية
          ├── .got / .got.plt (0xC108..0xC670) <-- إزاحة GOT داخل RELRO
          └── .data / .bss (0xC000 / 0xE000)
                   │
                   ▼
  ★ [مالك توليد RELRO: ps5-native-tool link] ★
  [tooling/native/sce_module_writer.cpp :: write_executable]
    - الخطأ السابق: relro_file = got.file_offset; (0xC108)
    - المفترض:      relro_file = first_relro_section.file_offset; (0x8000)
    - المخالفة:     p_offset % 0x4000 = 0x108 != p_vaddr % 0x4000 = 0x000
                   │
                   ▼
       [Native ELF: eboot.elf]
                   │
                   ▼  (ps5-native-tool self --sign)
      [FSELF Executable: eboot.bin]
                   │
                   ▼
  [Title Directory: dist/PPSA91360/]
    ├── eboot.bin
    ├── sce_module/libc.prx
    ├── sce_sys/param.json, icon0.png, ...
    └── assets/
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
 (UFS2Tool)                (MkPFS)
[PPSA91360.ffpkg]     [PPSA91360.ffpfsc]
```

---

## 4. تصنيف الادعاءات الفنية وفق درجات اليقين

1. **مؤكد من الملفات والسجلات (Confirmed):**
   - قطاع LOAD رقم 3 في `eboot.elf` و`eboot.bin` يخالف شرط التطابق: `p_offset % p_align != p_vaddr % p_align` (`0xC108 % 0x4000 = 0x108 != 0`).
   - الكود المصدري في `sce_module_writer.cpp` سطر 841 يحدد `relro_file = got.file_offset;` صراحةً بدلاً من أول قسم في نطاق RELRO.
   - `dist/AnimeRift_websrv/AnimeRift/ffplay.elf` ليس Native PS5 Executable (`0xFE10`) بل ملف Linux System V x86-64 `ET_DYN`.
   - كود الواجهة يستدعي شبكات مختلفة (`192.168.1.66:8080` في `pc_server.txt` و `192.168.1.100:8080` في كود native).
2. **مرجح من التوثيق (Likely):**
   - رفض PS5 Kernel Loader الفوري لتطبيق PPSA91360 ("تعذر بدء اللعبة أو التطبيق") سببه المباشر فشل `mmap` لقطاع RELRO بسبب عدم تطابق إزاحة الملف مع العنوان الافتراضي على حدود 16 KiB.
3. **فرضيات تحتاج اختباراً معملياً على الجهاز (Hypothesis):**
   - هل بعد إصلاح الـELF alignment سيعمل التطبيق مباشرة على FW 13.60 بدون عوائق أخرى في imports أو kstuff-lite؟ يتطلب اختبار PS5 الفعلي (Phase C و Phase D).
