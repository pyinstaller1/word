import os
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

@app.get("/")
def read_root():
    # 환경 변수가 서버 내부에서 잘 보이는지 확인하는 엔드포인트
    key = os.getenv("GEMINI_API_KEY")
    return {"status": "running", "key_found": key is not None}
