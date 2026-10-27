# تقرير تشخيص سجلات الإقلاع والكيرنل (Loader & Kernel Log Report)

**تاريخ التشخيص:** 24 أكتوبر 2026  
**الهدف:** تفسير سجلات ShadowMount السابقة ووضع آلية التحقق المباشر من خلال كيرنل PS5 عبر `klogsrv`.

---

## 1. تحليل سجل ShadowMount السابق (`debug.log`)

في السجل القديم لجهاز PS5 على Firmware 13.60 مع ShadowMount `1.7-beta5fix1`:

```text
[01:34:04] [LINK] nullfs mounted: /mnt/usb0/homebrew/PPSA91360 -> /system_ex/app/PPSA91360
[01:34:04] [SHELLCORE] launch mount ready: PPSA91360
[01:34:04] [FAKELIB] directory mounted ...
[01:34:04] [SHELLCORE] sandbox ready handled: PPSA91360
[01:34:04] [SHELLFLAG] SceLncUtilSystemStatus poll rc=0x80020010
[01:34:04] [SHELLCORE] runtime release start: PPSA91360
```

### الاستنتاجات الهندسية المؤكدة:
1. **نجاح عملية الربط والتسجيل:** ShadowMount تمكن من عمل nullfs mount للعنوان `PPSA91360` وتجهيز الـsandbox والـfakelib بنجاح تام (`launch mount ready` ثم `sandbox ready handled`).
2. **فشل بدء التنفيذ الفوري:** في نفس الثانية (`01:34:04`)، استجابت مكتبة ShellCore بإطلاق `runtime release start`، ما يعني أن الكيرنل رفض تشغيل ملف `eboot.bin` قبل أن تبدأ دالة `main()`.
3. **رمز `0x80020010`:** هذا الرمز ظهر أثناء عمل polling لحالة النظام (`SceLncUtilSystemStatus`) وهو نتيجة مباشرة لانتهاء عملية التطبيق فور محاولة إطلاقه، وليس خطأ إعدادات ShadowMount.
4. **تضارب المصادر المتعددة:** السجل أظهر وجود نسختين من التطبيق مسجلتين في نفس الوقت (ملف `.ffpkg` ومجلد `PPSA91360` على USB)، مما استدعى تحذير `تم تجاهل PPSA91360 المكرر`.

---

## 2. العلاقة بين فشل الـLoader وعيب 16 KiB PT_LOAD Congruence

عندما يقوم نظام Prospero (المبني على كيرنل FreeBSD 9) بتحميل FSELF:
- يقوم الـLoader بفحص ترويسات `PT_LOAD` لكل قطاع قابل للتحميل في الذاكرة.
- القاعدة الملزمة في كيرنل النظام:
  $$\text{p\_offset} \pmod{\text{p\_align}} == \text{p\_vaddr} \pmod{\text{p\_align}}$$
- في الملف القديم المعطوب:
  $$\text{p\_offset} \pmod{0x4000} = 0xC108 \pmod{0x4000} = 0x108$$
  $$\text{p\_vaddr} \pmod{0x4000} = 0x8000 \pmod{0x4000} = 0x000$$
- هذا الاختلاف يجعل استدعاء `mmap` الداخلي في الكيرنل يفشل فوراً بـ `EINVAL` (Invalid Argument)، لأن إزاحة الملف لا تطابق حدود الصفحة الافتراضية للذاكرة، فيرفض الكيرنل العملية فوراً وتظهر رسالة البلايستيشن الشهيرة: **«تعذر بدء اللعبة أو التطبيق»**.

---

## 3. علامات التتبع الجديدة في نسخة Smoke المحدثة (Startup Trace Markers)

تم تضمين تسجيل منخفض المستوى (Low-Level Direct Write to FD 1/2) في ملف `main_smoke.cpp` قبل أي تهيئة للواجهة:
- `[SMOKE] PROCESS_ENTER` — وصول المعالج لنقطة الدخول `_start`.
- `[SMOKE] PRE_INIT` — انتهاء استدعاء CRT وconstructors.
- `[SMOKE] MAIN_ENTER` — الدخول في دالة `main()`.
- `[SMOKE] VIDEO_INIT_START` — بدء حجز Direct Memory وVideoOut.
- `[SMOKE] FIRST_FRAME_RENDERED` — رسم أول إطار بنجاح على الشاشة.
- `[SMOKE] ENTERING_EVENT_LOOP` — بدء حلقة العرض 60fps واستقبال أزرار DualSense.
- `[SMOKE] USER_REQUESTED_EXIT` — خروج نظيف عند الضغط على زر Circle.

---

## 4. تعليمات التقاط سجل الكيرنل المباشر عبر `klogsrv` (خطوة بخطوة)

إذا رغب المستخدم في فحص سجل الكيرنل أثناء تجربة الجهاز:
1. تشغيل بايلود `klogsrv` على الـPS5 (المشروع الرسمي: `https://github.com/ps5-payload-dev/klogsrv`).
2. من جهاز الكمبيوتر على نفس الشبكة المحلية (LAN):
   - عبر WSL أو Linux:
     ```bash
     nc <PS5_IP> 3232 | tee unirift_klog.txt
     ```
   - أو عبر PowerShell باستخدام عميل TCP مدمج:
     ```powershell
     $client = New-Object System.Net.Sockets.TcpClient("<PS5_IP>", 3232)
     $stream = $client.GetStream()
     $reader = New-Object System.IO.StreamReader($stream)
     while ($client.Connected) { $line = $reader.ReadLine(); if ($line) { Write-Output $line } }
     ```
3. تشغيل تطبيق UniRift / Anime Rift ومراقبة السطور التي تحتوي على `PPSA91360`.
