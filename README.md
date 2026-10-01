# SPRIX Automation Assistant

نسخة أتمتة محلية لحساب الطالب. تستخدم Playwright لفتح بوابة SPRIX ثم الانتقال إلى رابط منصة البرمجة، وتستخدم بيانات الدخول التي يكتبها المستخدم داخل الواجهة.

## مهم
- لا توجد محاولة لتجاوز CAPTCHA أو MFA أو صلاحيات المنصة.
- كلمة المرور لا تُكتب في السجلات.
- إذا ظهرت CAPTCHA/MFA يتوقف التشغيل ويطلب من المستخدم إكمالها في المتصفح.
- يجب استخدام الحساب المصرح للطالب فقط.
- selectors مصممة كـ heuristics لأن الصفحة الداخلية تتطلب جلسة دخول ولا يمكن ضمان ثبات DOM.

## تشغيل Termux

```bash
pkg update
pkg install python -y
pip install -r requirements.txt
python -m playwright install chromium
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

ثم افتح:
http://127.0.0.1:8000

إذا رفض Termux تنزيل Chromium، شغّل المتصفح المثبت على جهازك عبر إعداد Playwright المناسب أو استخدم جهاز Linux/Windows للتشغيل.

## AI

ضع مزود OpenAI-compatible في `.env`:
AI_BASE_URL
AI_API_KEY
AI_MODEL

مثال endpoint شائع:
`https://api.openai.com/v1`

لا تضع المفتاح داخل GitHub.

## طريقة العمل

1. المستخدم يدخل Student ID/Code وكلمة المرور في الواجهة.
2. Playwright يفتح SPRIX.
3. يضغط رابط منصة البرمجة الرسمي.
4. يكتشف حقول الدخول ويحاول تسجيل الدخول.
5. يقرأ نص الصفحة.
6. يطلب من نموذج AI إخراج إجابة منظمة JSON.
7. يملأ textarea/contenteditable/code editor المناسب.
8. يبحث عن Submit/Check/Run/Next.
9. لا يتخطى تحديات الحماية.
10. يسجل أحداث التشغيل بدون كلمة المرور.

إذا تغيرت الواجهة، عدّل `sprix_adapter.py` بدل تغيير الـbackend كله.
