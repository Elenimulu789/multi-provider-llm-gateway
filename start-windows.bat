@echo off
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo Install uv first. See START_HERE.md.
  pause
  exit /b 1
)
uv sync --frozen
if errorlevel 1 (
  pause
  exit /b 1
)
uv run streamlit run src/app.py
pause
