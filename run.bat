@echo off
rem Starts Roamly on http://127.0.0.1:8000 (Windows). First run installs packages and trains the model.
cd /d "%~dp0"
py -m pip install -q -r requirements.txt
cd backend
py -m uvicorn main:app --port 8000
