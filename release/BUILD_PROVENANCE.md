# وثيقة إثبات البناء وسلسلة الأدوات (Build Provenance & Environment)

**التطبيق:** UniRift / Anime Rift — PS5 Native Title  
**معرّف التطبيق:** `PPSA91360`  
**رمز المحتوى:** `UP9000-PPSA91360_00-ANIMERIFTPS51360`  
**تاريخ الإنتاج:** 24 أكتوبر 2026  

---

## 1. مواصفات بيئة الترجمة والأدوات

```text
Host Operating System:       Windows 10/11 x86_64
Host Toolchain:              LLVM-MinGW (UCRT x86_64) 20240917
Compiler:                    Clang version 19.1.0 (Target: x86_64-sie-ps5)
Linker:                      LLD 19.1.0 (-m elf_x86_64 -pie -z max-page-size=0x4000)
Python Runtime:              Python 3.11.15
PS5 Payload SDK:             PS5 Payload SDK (FreeBSD 9 ABI 2 headers + stubs)
Native Converter:            ps5-native-tool (C++20 native converter, patched for 16 KiB RELRO)
Repository Git Commit:       470695e0c557f99ff2df0e36e4df713c5e636526 (tools/ps5-native-app-boilerplate)
```

---

## 2. جدول البصمات المرجعية لمخرجات الإصدار (Release SHA-256 Checksums)

| اسم الملف | الحجم (بايت) | بصمة SHA-256 |
|---|---|---|
| `smoke_eboot.bin` | 18,521 | `40776ded4cc570b9fb62bd2c81b13c7ee629e168bda6ea3b3fef90a549e476ac` |
| `full_eboot.bin` | 30,260 | `8b4062c34cf62d62037b1d81ece3bab92733e8ee0305b2af9cbe73d30ef8efa5` |
| `full_eboot.elf` | 75,476 | `5d93fd6e5e1bcc6faabbca86cf9a903526b20ea265b01c639e67d780d23900be` |
| `libc.prx` | 1,284,674 | `e6ff45d16adf687855cc3b33b0c8a4132b6504360b221e0a34c7e99fb3ba0036` |
| `UniRift_FW13.60_smoke_folder.zip` | 16,989,223 | `03b9dceab4a94fb9e4b1f3b1e3c45379b646b1e130f46dff3c3bf36fd579a57a` |
| `UniRift_FW13.60_folder.zip` | 48,683,385 | `0b83ed6909666f7f04c7fcca468f3f1cd2f4b5a29881b5bdf541b535eb48a8b2` |
