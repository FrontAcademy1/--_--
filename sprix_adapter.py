import os, json, asyncio, re
from datetime import datetime
import httpx
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

PORTAL=os.getenv("SPRIX_PORTAL_URL","https://sprixportal.jp/")
BASE=os.getenv("AI_BASE_URL","").rstrip("/")
KEY=os.getenv("AI_API_KEY","")
MODEL=os.getenv("AI_MODEL","")
HEADLESS=os.getenv("HEADLESS","false").lower()=="true"

class SprixAutomation:
    def __init__(self,student_id,password):
        self.student_id=student_id
        self.password=password
        self.running=False
        self.status="created"
        self.logs=[]
        self.pw=None; self.browser=None; self.page=None

    def log(self,msg):
        self.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        self.logs=self.logs[-100:]

    async def start(self):
        self.running=True
        try:
            self.pw=await async_playwright().start()
            self.browser=await self.pw.chromium.launch(headless=HEADLESS)
            self.page=await self.browser.new_page()
            self.status="opening"
            await self.page.goto(PORTAL, wait_until="domcontentloaded", timeout=45000)
            self.log("SPRIX portal opened")
            # Official portal exposes the programming login link. Prefer its href/text.
            link=self.page.get_by_role("link", name=re.compile("تسجيل الدخول|login",re.I))
            if await link.count():
                # The page contains multiple login links; choose the one whose surrounding text is programming.
                links=self.page.locator("a")
                chosen=None
                for i in range(min(await links.count(),80)):
                    a=links.nth(i)
                    txt=(await a.inner_text()).strip()
                    href=await a.get_attribute("href")
                    if txt and re.search("تسجيل الدخول|login",txt,re.I) and href and ("qureo" in href.lower() or "program" in (await a.evaluate("(e)=>e.parentElement?.innerText||''")).lower()):
                        chosen=a; break
                if chosen:
                    await chosen.click()
                else:
                    await link.first.click()
            else:
                await self.page.goto("https://me-portal.qureo.education/",wait_until="domcontentloaded",timeout=45000)
            await self.page.wait_for_load_state("domcontentloaded")
            self.log(f"Programming page: {self.page.url}")
            await self.login()
            self.status="ready"
            return {"ok":True,"status":self.status,"url":self.page.url,"logs":self.logs[-20:]}
        except Exception as e:
            self.status="error"
            self.running=False
            self.log("START ERROR: "+str(e))
            return {"ok":False,"error":str(e),"logs":self.logs[-20:]}

    async def login(self):
        # Heuristic login discovery: text input + password input, no credential logging.
        pwd=self.page.locator('input[type="password"]').first
        await pwd.wait_for(state="visible",timeout=20000)
        text_inputs=self.page.locator('input:not([type="hidden"]):not([type="password"])')
        candidates=[]
        for i in range(await text_inputs.count()):
            el=text_inputs.nth(i)
            if await el.is_visible():
                candidates.append(el)
        if not candidates:
            raise RuntimeError("Student ID field was not detected")
        await candidates[0].fill(self.student_id)
        await pwd.fill(self.password)
        # Never log credentials.
        buttons=self.page.get_by_role("button")
        clicked=False
        for i in range(await buttons.count()):
            b=buttons.nth(i)
            if await b.is_visible():
                txt=(await b.inner_text()).strip()
                if re.search("login|sign in|دخول|تسجيل",txt,re.I):
                    await b.click(); clicked=True; break
        if not clicked:
            await pwd.press("Enter")
        await self.page.wait_for_timeout(2500)
        body=(await self.page.locator("body").inner_text())[:6000]
        if re.search("captcha|recaptcha|تحقق أنك لست روبوت|two-factor|verification code|رمز التحقق",body,re.I):
            self.status="waiting_for_user_verification"
            self.log("Verification challenge detected; user action required")
            return
        self.log("Login flow completed")

    async def page_text(self):
        return (await self.page.locator("body").inner_text())[:18000]

    async def solve_current(self):
        if not self.page:
            return {"ok":False,"error":"No active browser session"}
        try:
            self.status="reading_question"
            txt=await self.page_text()
            if re.search("captcha|recaptcha|تحقق أنك لست روبوت|two-factor",txt,re.I):
                return {"ok":False,"status":"waiting_for_user_verification","logs":self.logs[-20:]}
            answer=await self.ask_ai(txt)
            if not answer.get("answer"):
                return {"ok":False,"error":"AI did not return an answer","raw":answer}
            self.status="filling"
            filled=await self.fill_answer(answer["answer"])
            self.log("Answer inserted" if filled else "No supported answer field detected")
            if filled:
                self.status="submitting"
                submitted=await self.click_action(["Submit","Check","Run","إرسال","تحقق","تشغيل"])
                if submitted: self.log("Submit/check action clicked")
            self.status="ready"
            return {"ok":True,"answer":answer,"filled":filled,"logs":self.logs[-20:]}
        except Exception as e:
            self.status="error"; self.log("RUN ERROR: "+str(e))
            return {"ok":False,"error":str(e),"logs":self.logs[-20:]}

    async def ask_ai(self,page_text):
        if not (BASE and KEY and MODEL):
            raise RuntimeError("Configure AI_BASE_URL, AI_API_KEY and AI_MODEL in .env")
        system="""You are an educational assistant operating on a student's authorized learning account.
Return ONLY valid JSON: {"answer":"...","explanation":"...","confidence":0.0}
Solve the current exercise from the page text. Prefer the exact expected answer/code when the page clearly specifies it.
Do not invent hidden APIs or bypass security."""
        user="PAGE TEXT:\n"+page_text
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"}
        payload={"model":MODEL,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"temperature":0}
        async with httpx.AsyncClient(timeout=90) as c:
            r=await c.post(BASE+"/chat/completions",headers=headers,json=payload)
            r.raise_for_status()
            content=r.json()["choices"][0]["message"]["content"]
        content=re.sub(r"^```json\s*|\s*```$","",content.strip(),flags=re.I)
        return json.loads(content)

    async def fill_answer(self,answer):
        # Textareas first.
        areas=self.page.locator("textarea")
        for i in range(await areas.count()):
            el=areas.nth(i)
            if await el.is_visible() and await el.is_editable():
                await el.fill(str(answer)); return True
        # Common contenteditable/code editors.
        editable=self.page.locator('[contenteditable="true"]')
        for i in range(await editable.count()):
            el=editable.nth(i)
            if await el.is_visible():
                await el.click()
                await el.press("Control+A")
                await el.type(str(answer))
                return True
        return False

    async def click_action(self,names):
        for name in names:
            try:
                b=self.page.get_by_role("button",name=re.compile(re.escape(name),re.I))
                if await b.count():
                    for i in range(await b.count()):
                        x=b.nth(i)
                        if await x.is_visible() and await x.is_enabled():
                            await x.click(); return True
            except Exception: pass
        return False

    async def stop(self):
        self.running=False
        self.status="stopped"
        try:
            if self.browser: await self.browser.close()
            if self.pw: await self.pw.stop()
        except Exception: pass
        self.log("Automation stopped")
