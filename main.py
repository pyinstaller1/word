import pandas as pd
import requests
import asyncio
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from bs4 import BeautifulSoup
from google import genai
from openai import OpenAI
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# API 설정 (사용자 키 유지)
GEMINI_KEY = "AIzaSyD3oKERtLmCXOPHOj1gILavTs4b1rhYu8I"
GPT_KEY = "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"

client_gemini = genai.Client(api_key=GEMINI_KEY)
client_gpt = OpenAI(api_key=GPT_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
BASE_FILENAME = "IT용어_엑셀.xlsx"
current_output_file = BASE_FILENAME

def save_excel_safe(df):
    global current_output_file
    filename = BASE_FILENAME
    counter = 1
    while True:
        try:
            df.to_excel(filename, index=False)
            current_output_file = filename
            break
        except PermissionError:
            filename = f"IT용어_엑셀_{counter}.xlsx"
            counter += 1
    return filename

# 크롤링 함수들 (tta, naver, itwiki) - 이전과 동일
def get_tta_data(word):
    try:
        res = requests.get(f"https://terms.tta.or.kr/dictionary/dictionaryView.do?subject={word}", headers=HEADERS, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        target = soup.select_one("div.no_css")
        return " ".join(target.get_text(separator=" ", strip=True).split()) if target else ""
    except: return ""

def get_naver_data(word):
    try:
        search_url = f"https://terms.naver.com/search.naver?query={word}&dicType=14&cid=42343"
        res = requests.get(search_url, headers=HEADERS, timeout=5)
        items = BeautifulSoup(res.text, "html.parser").select(".search_result_area .content_list > li")
        if not items: return ""
        target_item = items[0]
        it_keywords = ["정보통신", "컴퓨터", "인터넷", "통신", "데이터", "IT", "네트워크"]
        for item in items:
            if any(k in item.get_text() for k in it_keywords):
                target_item = item
                break
        d_url = "https://terms.naver.com" + target_item.select_one(".title a")['href']
        d_res = requests.get(d_url, headers=HEADERS, timeout=5)
        content = BeautifulSoup(d_res.text, "html.parser").select_one("#size_ct")
        return content.get_text(separator="\n", strip=True) if content else ""
    except: return ""

def get_itwiki_data(word):
    try:
        res = requests.get(f"https://itwiki.kr/w/{word}", headers=HEADERS, timeout=5)
        if res.status_code != 200: return ""
        soup = BeautifulSoup(res.text, "html.parser").select_one(".mw-parser-output")
        if soup:
            for tag in soup.select(".toc, .mw-editsection"): tag.decompose()
            return soup.get_text(separator="\n", strip=True)
        return ""
    except: return ""

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/download")
async def download():
    if os.path.exists(current_output_file):
        return FileResponse(current_output_file, filename=current_output_file)
    return {"error": "File not found"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # 클라이언트로부터 단어 리스트 수신
    data = await websocket.receive_text()
    list_word = [w.strip() for w in data.split(",") if w.strip()]
    
    final_results = []
    await websocket.send_json({"msg": f"💎 제목: {', '.join(list_word)}", "type": "header"})

    for idx, word in enumerate(list_word, start=1):
        await websocket.send_json({"msg": f"[{idx}/{len(list_word)}] {word}", "type": "info", "word": word})
        
        loop = asyncio.get_event_loop()
        tta = await loop.run_in_executor(None, get_tta_data, word)
        naver = await loop.run_in_executor(None, get_naver_data, word)
        itwiki = await loop.run_in_executor(None, get_itwiki_data, word)
        
        await websocket.send_json({"msg": "☑️ 크롤링 완료 (TTA, 네이버, IT위키)", "type": "detail", "word": word})

        prompt = f"IT 용어 사전용: '{word}'의 기술적 정의와 핵심 원리를 전문가 수준으로 정리해줘."
        
        # 제미나이 -> GPT 순서
        try:
            gem_res = client_gemini.models.generate_content(model="models/gemini-2.0-flash", contents=prompt)
            gem_ans = gem_res.text.strip()
            await websocket.send_json({"msg": "☑️ 제미나이 분석 완료", "type": "detail", "word": word})
        except:
            gem_ans = "Error"; await websocket.send_json({"msg": "❌ 제미나이 에러", "type": "detail", "word": word})

        try:
            gpt_res = client_gpt.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            gpt_ans = gpt_res.choices[0].message.content.strip()
            await websocket.send_json({"msg": "☑️ GPT 분석 완료", "type": "detail", "word": word})
        except:
            gpt_ans = "Error"; await websocket.send_json({"msg": "❌ GPT 에러", "type": "detail", "word": word})

        final_results.append({
            "용어": word, "수동정의(빈칸)": "", "TTA 표준정의": tta,
            "네이버 상세본문": naver, "IT위키 상세본문": itwiki,
            "제미나이 답변": gem_ans, "지피티 답변": gpt_ans
        })
        save_excel_safe(pd.DataFrame(final_results))

    await websocket.send_json({"msg": "🎊 모든 작업이 완료되었습니다! 🥳", "type": "finish"})
    await websocket.close()
