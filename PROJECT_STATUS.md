# Stock Predictor - 프로젝트 현황

## 프로젝트 개요
NASDAQ/AMEX 종목을 기술적 분석, 모멘텀, 펀더멘털, 머신러닝(RF+GBM 앙상블) 4가지 방법으로
종합 분석하여 당일/일주일 내 상승 확률이 높은 종목을 추천하는 프로그램.

## 사용자 정보
- GitHub: gtsungho
- 저장소: https://github.com/gtsungho/stock-predictor
- 기기: 갤럭시 S25 울트라 (안드로이드)
- 용도: 혼자 사용

## 완료된 작업

### 1. 백엔드 개발 (완료)
- `backend/data/fetcher.py` - Yahoo Finance 무료 API로 데이터 수집 (캐싱 포함)
- `backend/analysis/technical.py` - 기술적 분석 (RSI, MACD, BB, 스토캐스틱, ADX, CCI, MFI 등) / `ta` 라이브러리 사용
- `backend/analysis/momentum.py` - 모멘텀 분석 (거래량, 돌파, 갭, 변동성 수축)
- `backend/analysis/fundamental.py` - 펀더멘털 분석 (PER, PEG, ROE, 성장률)
- `backend/analysis/ml_model.py` - ML 예측 (RandomForest + GradientBoosting 앙상블, 50+피처)
- `backend/scoring/ensemble.py` - 4개 분석 가중 합산 (기술25%, 모멘텀25%, 펀더멘털20%, ML30%)
- `backend/engine.py` - 분석 파이프라인 오케스트레이션
- `backend/main.py` - FastAPI 서버 (REST API + WebSocket + 정적파일 서빙)
- `backend/requirements.txt` - 패키지: yfinance, pandas, ta, numpy, scikit-learn, fastapi, uvicorn 등

### 2. 프론트엔드 개발 (완료)
- `frontend/index.html` - 모바일 최적화 UI (다크 테마)
- `frontend/css/style.css` - 반응형 스타일
- `frontend/js/app.js` - API 연동, 실시간 진행 상태, 필터/정렬, 상세 모달
- `frontend/manifest.json` - PWA 설정
- `frontend/sw.js` - Service Worker (오프라인 캐시)

### 3. 로컬 실행 환경 (완료)
- `start.bat` - Windows용 실행 스크립트 (Python Embedded 자동 다운로드, pip, 패키지 설치, 서버 시작)
- `start.sh` - WSL/Linux용 실행 스크립트
- Python Embedded 사용 → 전역 Python 설치 불필요, 모든 파일이 C:\csh\test_apk 안에 생성
- 로컬 서버 테스트 완료 (http://localhost:8000 정상 작동 확인)

### 4. 클라우드 배포 준비 (완료)
- `Dockerfile` - Docker 기반 배포 설정
- `render.yaml` - Render.com 배포 설정
- `.gitignore` - python/, cache/, models/, results/, venv/, __pycache__ 제외
- GitHub 저장소 푸시 완료

### 5. 인프라 설치 (완료)
- Git for Windows 설치됨 (winget으로 v2.53.0.2)
- start.bat CRLF 줄바꿈 변환 완료

## 진행 중인 작업

### Render.com 배포 (완료)
- 배포 URL: https://stock-predictor-glwr.onrender.com/
- 정상 작동 확인됨

## 남은 작업
1. Render.com에서 배포 완료 → URL 확인
2. 안드로이드 폰에서 해당 URL 접속 → Chrome 메뉴 → "홈 화면에 추가"
3. (선택) 분석 결과 테스트 및 튜닝

## 기술 스택
- Backend: Python 3.11, FastAPI, scikit-learn, ta, yfinance
- Frontend: HTML/CSS/JS (PWA)
- 배포: Docker, Render.com (무료, 월 750시간)
- 데이터: Yahoo Finance API (무료)

## 주요 결정사항
- `pandas-ta` → `ta` 라이브러리로 변경 (Python Embedded 호환 문제)
- `xgboost` 제거 → `scikit-learn`의 GradientBoosting 사용 (설치 호환성)
- APK 대신 PWA 방식 채택 (홈화면 추가로 앱처럼 사용)
- Python Embedded 사용 (전역 Python 설치 없이 프로젝트 폴더 내 독립 실행)
- Render.com 무료 플랜 사용 (15분 미사용시 슬립, 자동과금 없음)
