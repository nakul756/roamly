#!/usr/bin/env sh
# Starts Roamly on http://127.0.0.1:8000 (macOS / Linux). First run installs packages and trains the model.
cd "$(dirname "$0")" && python3 -m pip install -q -r requirements.txt && cd backend && python3 -m uvicorn main:app --port 8000
