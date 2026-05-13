#!/bin/bash
cd "$(dirname "$0")/.." || exit

echo "Ligando o motor da Inteligência Artificial..."
ollama serve &>/dev/null &

echo "Verificando ambiente virtual..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ ERRO: Ambiente virtual não encontrado!"
    echo "Você precisa rodar o instalador (1_instalar_sistema.command) primeiro."
    exit 1
fi

echo "Abrindo o painel no Safari/Chrome..."
# Chama o streamlit diretamente por dentro do python3 (evita o erro "command not found")
python3 -m streamlit run app_avaliacao.py
