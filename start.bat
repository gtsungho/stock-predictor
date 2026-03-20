@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ==========================================
echo   Stock Predictor - 서버 시작
echo ==========================================
echo.

cd /d "%~dp0"

set "ROOT=%cd%"
set "PYTHON_DIR=%ROOT%\python"
set "PYTHON=%PYTHON_DIR%\python.exe"
set "PIP=%PYTHON_DIR%\Scripts\pip.exe"

REM ========================================
REM [1/4] Python Embedded 설치 확인
REM ========================================
if exist "%PYTHON%" goto :python_ok

echo [1/4] Python Embedded 다운로드 중...
if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"

powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile '%PYTHON_DIR%\python.zip'"

if not exist "%PYTHON_DIR%\python.zip" (
    echo.
    echo [오류] Python 다운로드 실패!
    echo 인터넷 연결을 확인하세요.
    echo.
    pause
    exit /b 1
)

echo    압축 해제 중...
powershell -Command "Expand-Archive -Path '%PYTHON_DIR%\python.zip' -DestinationPath '%PYTHON_DIR%' -Force"
del "%PYTHON_DIR%\python.zip"

echo    Python 설정 중...
powershell -Command "$f = Get-Item '%PYTHON_DIR%\python*._pth'; (Get-Content $f.FullName) -replace '#import site','import site' | Set-Content $f.FullName"

echo    Python Embedded 설치 완료!
goto :pip_check

:python_ok
echo [1/4] Python Embedded 확인됨

REM ========================================
REM [2/4] pip 설치 확인
REM ========================================
:pip_check
if exist "%PIP%" goto :pip_ok

echo [2/4] pip 설치 중...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYTHON_DIR%\get-pip.py'"

"%PYTHON%" "%PYTHON_DIR%\get-pip.py" --no-warn-script-location
del "%PYTHON_DIR%\get-pip.py" 2>nul
echo    pip 설치 완료!
goto :install_packages

:pip_ok
echo [2/4] pip 확인됨

REM ========================================
REM [3/4] 패키지 설치
REM ========================================
:install_packages
echo [3/4] 패키지 설치 확인 중...
"%PYTHON%" -m pip install -r "%ROOT%\backend\requirements.txt" -q --no-warn-script-location

if errorlevel 1 (
    echo.
    echo [오류] 패키지 설치 실패!
    echo.
    pause
    exit /b 1
)

REM ========================================
REM [4/4] 서버 시작
REM ========================================
echo.
echo [4/4] 서버 시작 중...
echo.
echo ==========================================
echo   브라우저에서 http://localhost:8000 접속
echo   안드로이드: 같은 Wi-Fi에서 PC_IP:8000 접속
echo   종료: Ctrl+C
echo ==========================================
echo.

cd /d "%ROOT%\backend"
"%PYTHON%" main.py

echo.
echo 서버가 종료되었습니다.
pause
