@echo off
chcp 949 >nul
title Stock Predictor Deploy

echo =============================================
echo   Stock Predictor Deploy
echo =============================================
echo.

cd /d C:\csh\test_apk

echo [1/3] Checking changes...
git status --short
echo.

set HAS_CHANGE=0
for /f %%i in ('git status --porcelain') do set HAS_CHANGE=1
if %HAS_CHANGE%==0 (
    echo No changes to deploy.
    echo.
    pause
    exit /b 0
)

echo [2/3] Git commit...
git add -A
git commit -m "update"
echo.

echo [3/3] Pushing... (Render auto deploy)
git push
echo.

if %errorlevel%==0 (
    echo =============================================
    echo   Deploy OK!
    echo =============================================
    echo   URL: https://stock-predictor-glwr.onrender.com/
    echo   Dashboard: https://dashboard.render.com
    echo =============================================
) else (
    echo =============================================
    echo   Deploy FAILED! Check push error.
    echo =============================================
)

echo.
pause
