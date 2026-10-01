import asyncio, json, os
from pathlib import Path
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()
from sprix_adapter import SprixAutomation

app=FastAPI(title="SPRIX Automation")
app.mount("/static", StaticFiles(directory="static"), name="static")
bot=None

@app.get("/", response_class=HTMLResponse)
async def home():
    return Path("templates/index.html").read_text(encoding="utf-8")

@app.post("/start")
async def start(student_id:str=Form(...), password:str=Form(...)):
    global bot
    if bot and bot.running:
        return JSONResponse({"ok":False,"error":"Automation is already running"})
    bot=SprixAutomation(student_id=student_id, password=password)
    result=await bot.start()
    return result

@app.post("/run")
async def run_once():
    if not bot:
        return {"ok":False,"error":"Start a session first"}
    return await bot.solve_current()

@app.post("/stop")
async def stop():
    if bot:
        await bot.stop()
    return {"ok":True}

@app.get("/status")
async def status():
    if not bot:
        return {"running":False,"status":"idle","logs":[]}
    return {"running":bot.running,"status":bot.status,"logs":bot.logs[-30:]}
