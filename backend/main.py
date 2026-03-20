"""
FastAPI 서버 - REST API + 정적 파일 서빙
"""
import sys
from pathlib import Path

# Python Embedded 환경에서 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import json
from datetime import datetime
from contextlib import asynccontextmanager

import hashlib
import secrets
import os

from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect, Request, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from engine import analyze_single_stock, run_full_analysis, get_latest_results
import math


def sanitize_for_json(obj):
    """NaN, Infinity 등 JSON 비호환 float 값을 None으로 치환"""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj

# 인증 설정
APP_PASSWORD_HASH = hashlib.sha256("aa758800".encode()).hexdigest()
active_tokens = set()

# 분석 상태 관리
analysis_state = {
    'status': 'idle',  # idle, running, done, error
    'message': '',
    'progress': 0,
    'last_run': None,
}

# WebSocket 클라이언트들
ws_clients = set()


async def notify_clients(data: dict):
    """WebSocket으로 진행 상태 전송"""
    disconnected = set()
    for ws in ws_clients:
        try:
            await ws.send_json(data)
        except Exception:
            disconnected.add(ws)
    ws_clients -= disconnected


def progress_callback(status: str, message: str, progress: int):
    """분석 진행 콜백"""
    analysis_state['status'] = status
    analysis_state['message'] = message
    analysis_state['progress'] = progress

    # WebSocket 알림 (비동기 루프에서 실행)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(notify_clients({
                'type': 'progress',
                'status': status,
                'message': message,
                'progress': progress,
            }))
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Stock Predictor API 서버 시작")
    yield
    print("서버 종료")


app = FastAPI(title="Stock Predictor", lifespan=lifespan)

# CORS 설정 (로컬 사용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 프론트엔드 정적 파일
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def verify_token(request: Request) -> bool:
    """토큰 검증"""
    token = request.cookies.get("auth_token") or request.headers.get("X-Auth-Token")
    return token in active_tokens


@app.get("/")
async def root(request: Request):
    token = request.cookies.get("auth_token")
    if token in active_tokens:
        return FileResponse(FRONTEND_DIR / "index.html")
    return FileResponse(FRONTEND_DIR / "login.html")


@app.post("/api/login")
async def login(request: Request):
    try:
        body = await request.json()
        if isinstance(body, str):
            import json as _json
            body = _json.loads(body)
        pw = body.get("password", "")
    except Exception:
        return JSONResponse(status_code=400, content={"message": "잘못된 요청"})
    pw_hash = hashlib.sha256(pw.encode()).hexdigest()
    if pw_hash == APP_PASSWORD_HASH:
        token = secrets.token_hex(32)
        active_tokens.add(token)
        response = JSONResponse({"status": "ok"})
        response.set_cookie("auth_token", token, max_age=86400 * 30, httponly=True, samesite="lax")
        return response
    return JSONResponse(status_code=401, content={"message": "비밀번호가 틀렸습니다."})


@app.get("/manifest.json")
async def manifest():
    return FileResponse(FRONTEND_DIR / "manifest.json")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript")


# API 라우트 (인증 필요)
@app.get("/api/status")
async def get_status(request: Request):
    if not verify_token(request):
        return JSONResponse(status_code=401, content={"message": "인증 필요"})
    return analysis_state


@app.get("/api/results")
async def get_results(request: Request):
    if not verify_token(request):
        return JSONResponse(status_code=401, content={"message": "인증 필요"})
    results = get_latest_results()
    if results:
        return sanitize_for_json(results)
    return JSONResponse(
        status_code=404,
        content={"message": "아직 분석 결과가 없습니다. 분석을 실행해주세요."}
    )


@app.post("/api/analyze")
async def start_analysis(request: Request, background_tasks: BackgroundTasks):
    if not verify_token(request):
        return JSONResponse(status_code=401, content={"message": "인증 필요"})

    if analysis_state['status'] == 'running':
        return {"message": "분석이 이미 진행 중입니다.", "status": "running"}

    analysis_state['status'] = 'running'
    analysis_state['progress'] = 0
    analysis_state['message'] = '분석 시작...'

    def run_analysis():
        try:
            result = run_full_analysis(
                max_stocks=150,
                min_score=0,
                top_n=20,
                workers=4,
                progress_callback=progress_callback,
            )
            analysis_state['status'] = 'done'
            analysis_state['last_run'] = datetime.now().isoformat()
        except Exception as e:
            analysis_state['status'] = 'error'
            analysis_state['message'] = f'오류: {str(e)}'
            print(f"분석 오류: {e}")

    background_tasks.add_task(run_analysis)
    return {"message": "분석을 시작합니다.", "status": "running"}


@app.get("/api/stock/{ticker}")
async def get_stock_detail(request: Request, ticker: str):
    """개별 종목 상세 분석"""
    if not verify_token(request):
        return JSONResponse(status_code=401, content={"message": "인증 필요"})
    result = analyze_single_stock(ticker.upper())
    if result:
        from data.fetcher import get_usd_krw_rate
        result['usd_krw'] = get_usd_krw_rate()
        return sanitize_for_json(result)
    return JSONResponse(
        status_code=404,
        content={"message": f"{ticker} 분석 실패"}
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # 클라이언트가 상태 요청
            if data == "status":
                await websocket.send_json({
                    'type': 'status',
                    **analysis_state,
                })
    except WebSocketDisconnect:
        ws_clients.discard(websocket)


# 정적 파일 (CSS, JS) - 맨 마지막에 마운트
app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
