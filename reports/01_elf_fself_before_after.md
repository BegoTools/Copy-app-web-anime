# تقرير مقارنة قبل وبعد الإصلاح (ELF & FSELF Alignment Report)

**تاريخ الاختبار:** 24 أكتوبر 2026  
**الهدف:** التحقق من إزالة خطأ عدم تطابق إزاحة قطاع RELRO مع العنوان الافتراضي (16 KiB PT_LOAD Congruence).

---

## 1. مقارنة قطاعات البرنامج قبل وبعد الإصلاح

### قبل الإصلاح (Broken Baseline Build)
```text
File: dist/eboot.elf & dist/PPSA91360/eboot.bin (Inner ELF)
Program Headers: offset=0x40, count=14, entry_size=56
  [LOAD #1] offset=0x004000 vaddr=0x00000000 filesz=0x0035a8 memsz=0x0035a8 align=0x4000 -> PASS
  [LOAD #2] offset=0x008000 vaddr=0x00004000 filesz=0x001598 memsz=0x001598 align=0x4000 -> PASS
  [LOAD #3] offset=0x00c108 vaddr=0x00008000 filesz=0x000568 memsz=0x000568 align=0x4000 -> FAIL
      ERROR: Congruence violation: offset % align = 0x108 != vaddr % align = 0x0
  [GNU_RELRO] offset=0x00c108 vaddr=0x00008000 filesz=0x000568 memsz=0x004000 align=0x1
  [LOAD #4] offset=0x010000 vaddr=0x0000c000 filesz=0x000250 memsz=0x000ed0 align=0x4000 -> PASS
  [LOAD #5] offset=0x010ed0 vaddr=0x0000ced0 filesz=0x001648 memsz=0x001648 align=0x4000 -> PASS
Result: === FAIL ===
```

### بعد الإصلاح النظيف الكامل (Clean Fixed Rebuild)
```text
File: build/full/eboot.elf & build/full/eboot.bin (Inner ELF)
Program Headers: offset=0x40, count=14, entry_size=56
  [LOAD #1] offset=0x004000 vaddr=0x00000000 filesz=0x0035a8 memsz=0x0035a8 align=0x4000 -> PASS
  [LOAD #2] offset=0x008000 vaddr=0x00004000 filesz=0x001598 memsz=0x001598 align=0x4000 -> PASS
  [LOAD #3] offset=0x00c000 vaddr=0x00008000 filesz=0x000568 memsz=0x000568 align=0x4000 -> PASS
  [GNU_RELRO] offset=0x00c000 vaddr=0x00008000 filesz=0x000568 memsz=0x004000 align=0x1
  [LOAD #4] offset=0x010000 vaddr=0x0000c000 filesz=0x000260 memsz=0x000ee0 align=0x4000 -> PASS
  [LOAD #5] offset=0x010ee0 vaddr=0x0000cee0 filesz=0x001648 memsz=0x001648 align=0x4000 -> PASS
Result: === PASS ===
```

---

## 2. جدول مقارنة تفصيلي للقطاع المعطوب (LOAD Segment #3)

| الخاصية | قبل الإصلاح | بعد الإصلاح | الشرط الملزم | النتيجة |
|---|---|---|---|---|
| `p_offset` | `0x0000C108` | `0x0000C000` | — | تم تصحيح الإزاحة لبداية قسم RELRO |
| `p_vaddr` | `0x00008000` | `0x00008000` | — | مطابق للعنوان الافتراضي |
| `p_align` | `0x00004000` (16 KiB) | `0x00004000` (16 KiB) | $2^N$ | متوافق مع حدود صفحات كيرنل PS5 |
| `p_offset % p_align` | `0x108` | `0x000` | مساوي لـ `vaddr % align` | **تطابق تام (0 == 0)** |
| `p_filesz <= p_memsz` | `0x568 <= 0x568` | `0x568 <= 0x568` | $\le$ | محقق |

---

## 3. الفحص باستخدام أداة `ps5-native-tool self --inspect`

```text
file: eboot.bin
container: signed, plaintext
segments: 12
authority: 0x3100000000000002
program type: 0x0000000000000001
app version: 0x0000000000000000
firmware version: 0x0000000000000000
digest: 9929e1e1269ad6c79f85c3a124a4370ad698354b624e7007b7b46ebf9902aa75
integrity: valid
```

---

## 4. نتيجة اختبارات الانحدار (Regression Tests)
- **نسخة Smoke (الأدنى اعتماداً):** PASS (0 violations).
- **نسخة Full (التطبيق الكامل مع الجداول والثوابت):** PASS (0 violations).
- **استخراج الـELF الداخلي من FSELF وإعادة فحصه:** PASS (تطابق تام مع الـELF الأصلي).
