#!/bin/bash
echo "=========================================="
echo "  Stock Predictor - 서버 시작"
echo "=========================================="
echo

cd "$(dirname "$0")/backend"

# 가상환경 확인
if [ ! -d "venv" ]; then
    echo "[1/3] 가상환경 생성 중..."
    python3 -m venv venv
fi

echo "[2/3] 패키지 설치 확인 중..."
source venv/bin/activate
pip install -r requirements.txt -q

echo
echo "[3/3] 서버 시작 중..."
echo
echo "=========================================="
echo "  브라우저에서 http://localhost:8000 접속"
echo "  안드로이드: 같은 Wi-Fi에서 PC_IP:8000 접속"
echo "  종료: Ctrl+C"
echo "=========================================="
echo

python main.py
