#!/bin/bash
cd "$(dirname "$0")/.." || exit

# Inicia o serviço do Ollama em segundo plano, caso não esteja rodando
ollama serve &>/dev/null &

echo "Iniciando o sistema..."
source venv/bin/activate
streamlit run app_avaliacao.py
