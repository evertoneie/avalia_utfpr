@echo off
setlocal
cd /d "%~dp0\.."

echo Ligando o motor da IA...
start /b ollama serve >nul 2>&1

echo Iniciando o Painel no navegador...
call venv\Scripts\activate
python -m streamlit run app_avaliacao.py
