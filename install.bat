@echo off
REM AI 简历 — Windows 一键安装入口（调用 install.ps1）
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
exit /b %ERRORLEVEL%
