#!/bin/bash
# Garante que o script rode na pasta raiz do projeto
cd "$(dirname "$0")/.." || exit

echo "========================================================"
echo " Instalador: Sistema de Avaliação Docente (Linux)"
echo "========================================================"

# Verifica se o Ollama está instalado. Se não, instala.
if ! command -v ollama &> /dev/null; then
    echo "Instalando o motor da IA (Ollama)..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

echo "Criando ambiente isolado Python (venv)..."
python3 -m venv venv
source venv/bin/activate

echo "Instalando as bibliotecas necessárias..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Baixando o modelo de IA Llama 3 (4.7 GB)... Aguarde."
ollama pull llama3

echo "Instalação Concluída com Sucesso!"
