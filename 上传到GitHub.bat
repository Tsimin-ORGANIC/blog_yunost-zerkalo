@echo off
REM Pure-ASCII launcher (Chinese text lives in tools\upload.ps1,
REM because cmd.exe misparses multi-byte UTF-8 batch files).
title Upload to GitHub
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\upload.ps1"
