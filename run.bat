@echo off
REM Starts the tutor web UI on http://127.0.0.1:8000
call .venv\Scripts\activate.bat
python -m uvicorn web.app:create_app --factory --host 127.0.0.1 --port 8000
