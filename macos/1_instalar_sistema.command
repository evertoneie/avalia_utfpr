#!/bin/bash
# Força o terminal a entrar na pasta onde este script está localizado, e depois volta pra raiz
cd "$(dirname "$0")/.." || exit

echo "========================================================"
echo " Instalador: Sistema de Avaliação Docente (macOS)"
echo "========================================================"

# Verifica se o Ollama está no Mac
if ! command -v ollama &> /dev/null; then
    echo "⚠️ ATENÇÃO: O Ollama não foi encontrado."
    echo "Por favor, baixe e instale o Ollama para Mac em: https://ollama.com/download/mac"
    echo "Após instalar, rode este script novamente."
    exit 1
fi

echo "Criando ambiente isolado Python (venv)..."
python3 -m venv venv
source venv/bin/activate

echo "Instalando as bibliotecas do sistema..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Baixando a Inteligência Artificial Llama 3 (4.7 GB)..."
ollama pull llama3

echo "========================================================"
echo "Instalação Concluída!"
echo "Pode fechar esta janela."
