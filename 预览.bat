@echo off
chcp 65001 >nul
title 钇·锆·拾遗 · 档案室预览
cd /d "%~dp0"

where hugo >nul 2>nul
if errorlevel 1 (
    echo [错误] 没找到 hugo 命令，请确认 Hugo extended 已安装并加入了 PATH。
    pause
    exit /b 1
)

echo ========================================
echo   钇·锆·拾遗 · Yunost Zerkalo (Y-Zr)
echo   档案室预览启动中，浏览器会自动打开
echo   停止预览：在本窗口按 Ctrl+C 或直接关闭
echo ========================================
echo.

start "" "http://localhost:1314/"
hugo server --port 1314 --baseURL http://localhost:1314/ -D
pause
