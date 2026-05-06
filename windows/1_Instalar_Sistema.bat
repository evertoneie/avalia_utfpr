@echo off
setlocal
cd /d "%~dp0\.."

echo ========================================================
echo   Instalador: Sistema de Avaliacao Docente (Windows)
echo ========================================================
echo.
echo 1. Criando ambiente isolado do Python...
python -m venv venv

echo.
echo 2. Instalando as bibliotecas necessarias...
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo 3. Baixando a Inteligencia Artificial (Ollama - Llama 3)...
echo Atencao: Este download tem cerca de 4.7 GB. Por favor, aguarde.
ollama run llama3

echo.
echo ========================================================
echo Instalacao concluida com sucesso!
echo ========================================================
pause
