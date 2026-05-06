# 📊 Sistema Integrado: Avaliação Docente e Mapeamento de Evasão (IA Local)

Este é um sistema desenvolvido para auxiliar Coordenações de Curso e Chefias de Departamento na análise automatizada de relatórios de avaliação docente (formato PDF). 

O sistema utiliza Inteligência Artificial (Llama 3) rodando **100% localmente** na sua máquina. Nenhum dado de aluno, nota ou comentário é enviado para a internet. Total privacidade e adequação à LGPD.

## ✨ Funcionalidades
- **Extração Cirúrgica:** Ignora falhas de formatação do PDF e extrai apenas comentários reais.
- **Processamento em Lote:** Envie 1 ou 50 relatórios de uma vez.
- **Análise de Sentimento:** Classifica comentários em Positivo, Neutro ou Negativo e gera relatórios de Didática e Postura.
- **Alerta de Evasão:** Mapeia passivamente relatos sobre saúde mental, fadiga extrema e dificuldades estruturais.
- **Painel da Chefia:** Comparações cruzadas entre docentes e exportação de Relatório Executivo em PDF.

## 🚀 Como Instalar e Rodar

Não é necessário saber programar para usar a ferramenta. Escolha o seu sistema operacional abaixo e siga os três passos:

### 🪟 Windows
**Passo 1 (Pré-requisitos):** Baixe e instale o [Python](https://www.python.org/downloads/) (marque a caixa "Add Python to PATH" durante a instalação) e o [Ollama](https://ollama.com/download/windows).
**Passo 2 (Instalação):** Entre na pasta `windows` e dê um duplo clique em `1_Instalar_Sistema.bat`. Uma tela preta baixará a inteligência artificial (Llama 3 - ~4.7GB). Aguarde finalizar.
**Passo 3 (Uso diário):** Sempre que for utilizar, dê um duplo clique em `2_Iniciar_Painel.bat`. O painel abrirá no seu navegador.

### 🐧 Linux (Ubuntu e derivados)
**Passo 1 (Pré-requisitos):** Abra o terminal e instale o Python: `sudo apt update && sudo apt install python3 python3-pip python3-venv`
**Passo 2 (Instalação):** Pelo terminal, entre na pasta `linux` e execute: `bash 1_instalar_sistema.sh`. Ele instalará o Ollama e baixará os modelos automaticamente.
**Passo 3 (Uso diário):** Execute `bash 2_iniciar_painel.sh`. O painel abrirá no seu navegador.

### 🍏 macOS
**Passo 1 (Pré-requisitos):** Se o seu Mac ainda não tiver o Python, baixe-o [aqui](https://www.python.org/downloads/macos/) e instale o [Ollama para Mac](https://ollama.com/download/mac).
**Passo 2 (Instalação):** Abra o terminal, navegue até a pasta `macos` e execute: `bash 1_instalar_sistema.command`. Aguarde o download do modelo.
**Passo 3 (Uso diário):** Dê um duplo clique no arquivo `2_iniciar_painel.command` (ou execute via terminal).

---
**Dica de Performance:** Computadores com placa de vídeo dedicada (GPUs) farão a análise em poucos segundos. O sistema funciona perfeitamente apenas com processador (CPU), mas levará um pouco mais de tempo (cerca de 15 a 30 segundos por comentário).
