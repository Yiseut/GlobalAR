@echo off
setlocal
cd /d "%~dp0"
npx wrangler pages deploy web --project-name globalar --branch main --commit-dirty=true
pause
