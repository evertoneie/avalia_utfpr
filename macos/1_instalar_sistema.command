#!/bin/bash
# Navega para a pasta raiz do projeto de forma segura
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

echo "1. Criando ambiente isolado Python (venv)..."
python3 -m venv venv

# Verifica se o venv foi realmente criado
if [ ! -f "venv/bin/activate" ]; then
    echo "❌ ERRO: O Mac não conseguiu criar o ambiente virtual."
    echo "Verifique se o Python3 está instalado corretamente."
    exit 1
fi

source venv/bin/activate

echo "2. Instalando as bibliotecas do sistema..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "3. Baixando a Inteligência Artificial Llama 3 (4.7 GB)..."
ollama pull llama3

echo "========================================================"
echo "✅ Instalação Concluída!"
echo "Pode fechar esta janela."
