@echo off
rem Starts the app using a free local model through Ollama (install it first: ollama.com).
set LLM_BASE_URL=http://localhost:11434/v1
if "%LLM_MODEL%"=="" set LLM_MODEL=qwen2.5:3b
cd /d "%~dp0backend"
py -m uvicorn main:app --port 8000
