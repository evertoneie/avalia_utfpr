#!/bin/bash
cd "$(dirname "$0")/.." || exit

echo "Ligando o motor da Inteligência Artificial..."
# Mac gerencia os processos de forma estrita. O launchctl pode iniciar o Ollama se necessário
ollama serve &>/dev/null &

echo "Abrindo o painel no Safari/Chrome..."
source venv/bin/activate
streamlit run app_avaliacao.py
