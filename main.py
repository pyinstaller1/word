from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # 화면에 찍을 숫자 1
    result = 1
    return templates.TemplateResponse("index.html", {"request": request, "result": result})
