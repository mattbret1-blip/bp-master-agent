@echo off
REM One-time setup: creates a virtual environment, installs dependencies,
REM and copies .env.example to .env if needed. Edit .env afterwards and
REM set your provider key + model, then run run.bat.
py -m venv .venv 2>nul || python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo Setup done. Edit .env and set your provider key + model, then run run.bat
