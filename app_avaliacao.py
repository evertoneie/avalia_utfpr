import streamlit as st
import pdfplumber
import pandas as pd
import re
import ollama
import json
import plotly.express as px
import itertools
import tempfile
import os

# ==========================================
# CONFIGURAÇÃO INICIAL E ARMAZENAMENTO
# ==========================================
st.set_page_config(page_title="Sistema Integrado de Avaliação Docente", layout="wide")

CONFIG_FILE = "config_sistema.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Carrega a configuração salva
config = load_config()

# ==========================================
# TELA DE SETUP (PRIMEIRO ACESSO)
# ==========================================
if not config:
    st.title("👋 Bem-vindo ao Sistema de Avaliação Docente!")
    st.markdown("Parece que é a sua primeira vez aqui. Vamos configurar o sistema para aumentar a precisão da leitura dos PDFs.")
    
    perfil = st.radio("Selecione o seu perfil de uso:", ["Sou Professor", "Sou Chefia de Departamento / Coordenação"])
    
    if perfil == "Sou Professor":
        nome_prof = st.text_input("Qual é o seu nome completo?")
        st.markdown("*O sistema usará seu nome para procurá-lo diretamente nos relatórios, garantindo 100% de precisão.*")
        if st.button("Salvar e Iniciar", type="primary"):
            if nome_prof.strip():
                save_config({"perfil": "Professor", "lista_professores": [nome_prof.strip()]})
                st.rerun()
            else:
                st.error("Por favor, insira seu nome.")
                
    else:
        st.markdown("Como Chefia, você pode cadastrar o nome dos professores do departamento. O sistema usará essa base para identificar de quem é cada PDF de forma infalível.")
        
        col1, col2 = st.columns(2)
        with col1:
            nomes_texto = st.text_area("Opção A: Digite/Cole os nomes (um por linha, sem acentos ou caracteres especiais)", height=200, placeholder="Fulano de Tal\nCiclano das Tantas\n...")
        with col2:
            arquivo_csv = st.file_uploader("Opção B: Enviar lista em .CSV", type="csv")
            st.markdown("*Dica: O CSV deve ter os nomes na primeira coluna.*")
            
        if st.button("Salvar Base de Professores e Iniciar", type="primary"):
            lista_final = []
            if nomes_texto:
                lista_final.extend([n.strip() for n in nomes_texto.split('\n') if n.strip()])
            if arquivo_csv:
                try:
                    df_csv = pd.read_csv(arquivo_csv, header=None)
                    lista_final.extend(df_csv.iloc[:, 0].dropna().astype(str).tolist())
                except Exception as e:
                    st.error("Erro ao ler CSV.")
            
            # Limpa duplicatas
            lista_final = list(set([n.strip() for n in lista_final if n.strip()]))
            
            if len(lista_final) > 0:
                save_config({"perfil": "Chefia", "lista_professores": lista_final})
                st.rerun()
            else:
                st.warning("Insira pelo menos um nome para continuar, ou feche a aba se quiser testar sem configuração.")
    st.stop() # Impede que o resto do app carregue até configurar

# ==========================================
# MENU LATERAL (CONFIGURAÇÕES)
# ==========================================
with st.sidebar:
    st.subheader("⚙️ Configurações Atuais")
    st.write(f"**Perfil:** {config.get('perfil', 'N/A')}")
    st.write(f"**Professores Registrados:** {len(config.get('lista_professores', []))}")
    
    with st.expander("Ver lista de nomes"):
        for n in config.get('lista_professores', []):
            st.write(f"- {n}")
            
    st.markdown("---")
    if st.button("🔄 Resetar / Alterar Nomes"):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        st.rerun()

# ==========================================
# APLICAÇÃO PRINCIPAL
# ==========================================
st.title("📊 Sistema Integrado: Avaliação Docente e Risco de Evasão")

if 'df_avaliacao' not in st.session_state:
    st.session_state['df_avaliacao'] = None
if 'df_evasao' not in st.session_state:
    st.session_state['df_evasao'] = None

tab1, tab2, tab3, tab4 = st.tabs([
    "📄 1. Processar PDFs", 
    "📈 2. Dashboard Docente", 
    "🚨 3. Painel de Evasão",
    "👥 4. Comparativo Chefia"
])

# ==========================================
# ABA 1: EXTRAÇÃO E PROCESSAMENTO
# ==========================================
with tab1:
    st.markdown("Faça o upload de **um ou vários** PDFs simultaneamente. A IA processará todos os arquivos em lote.")
    
    uploaded_files = st.file_uploader("Selecione os arquivos PDF das avaliações", type="pdf", accept_multiple_files=True)

    if uploaded_files:
        comentarios_preparados = []
        resumo_arquivos = []
        
        # Puxa a lista de professores da configuração e ordena por tamanho do nome
        lista_busca_professores = sorted(config.get('lista_professores', []), key=len, reverse=True)
        
        with st.spinner("Lendo PDFs e mapeando a estrutura visual das tabelas..."):
            for uploaded_file in uploaded_files:
                texto_completo = ""
                
                with pdfplumber.open(uploaded_file) as pdf:
                    for page in pdf.pages:
                        texto_completo += page.extract_text() + "\n"
                        
                    # 1. CAPTURA DO NOME (MÉTODO WHITELIST + FALLBACK)
                    professor_encontrado = None
                    try:
                        texto_busca_norm = re.sub(r'\s+', ' ', texto_completo[:2000].replace('\n', ' ')).strip().lower()
                        
                        for prof_registrado in lista_busca_professores:
                            prof_norm = re.sub(r'\s+', ' ', prof_registrado).strip().lower()
                            if prof_norm and prof_norm in texto_busca_norm:
                                professor_encontrado = prof_registrado 
                                break
                        
                        if not professor_encontrado:
                            texto_cabecalho = texto_completo.split('*Os alunos')[0]
                            linhas_cabecalho = texto_cabecalho.split('\n')
                            
                            lixo_sub = [r'Professor', r'Pato Branco', r'C[aâ]mpus:', r'Campus', r'UTFPR', r'UNIVERSI\w*', r'TECHOLOGICA', r'PARAN[AÁ]']
                            lixo_drop = [
                                r'\d{2}/\d{2}/\d{4}', r'\d{2}:\d{2}', r'Avalia[cç][aã]o do Docente', r'Minist[eé]rio da Educa[cç][aã]o', 
                                r'Universidade\s+Tec', r'UNIVERSIDADE\s+TEC', r'M[eé]dia de todas', r'm[eé]dia final', r'Semestre/ano', 
                                r'Universo \(', r'Avalia[cç][õo]es realizadas', r'Avalia[cç][õo]es n[aã]o', r'pontos', r'realizadas\)',
                                r'diferen[cç]a entre universo', r'todos os cursos', r'disciplinas e campi'
                            ]
                            
                            nome_parts = []
                            for linha in linhas_cabecalho:
                                linha = linha.strip()
                                if not linha: continue
                                drop = False
                                for ld in lixo_drop:
                                    if re.search(ld, linha, re.IGNORECASE):
                                        drop = True
                                        break
                                if drop: continue
                                if re.match(r'^\d+(?:[.,]\d+)?$', linha) or re.match(r'^\d{1,2}/\d{4}$', linha): continue
                                for ls in lixo_sub:
                                    linha = re.sub(ls, '', linha, flags=re.IGNORECASE).strip()
                                linha = re.sub(r'FEDERAL,\s*DO', '', linha, flags=re.IGNORECASE).strip()
                                linha = re.sub(r'^[,.-]+$', '', linha).strip()
                                if len(linha) > 2: nome_parts.append(linha)
                                    
                            professor_encontrado = " ".join(nome_parts)
                            professor_encontrado = re.sub(r'\s+', ' ', professor_encontrado).strip()
                            if not professor_encontrado: professor_encontrado = "Desconhecido"
                            
                        padrao_metadados = r'(\d+(?:[.,]\d+)?)\D+?(?<!\d/)(?<!\d)(0?[12]\s*/\s*20\d{2})(?!\d)\D+?(\d+)\D+?(\d+)\D+?(\d+)'
                        match_valores = re.search(padrao_metadados, texto_completo)
                        if match_valores:
                            media, semestre_ano, universo, realizadas, nao_realizadas = match_valores.groups()
                            semestre_ano = semestre_ano.replace(' ', '')
                            semestre, ano = semestre_ano.split('/')
                        else:
                            media, semestre, ano, universo, realizadas, nao_realizadas = 0, "0", "0000", 0, 0, 0
                    except Exception as e:
                        professor_encontrado, media, semestre, ano, universo, realizadas, nao_realizadas = "Erro", 0, "0", "0000", 0, 0, 0

                    # 2. Extração Física dos Comentários
                    comentarios_arquivo = []
                    for page in pdf.pages:
                        tabelas = page.extract_tables()
                        for tabela in tabelas:
                            for row in tabela:
                                if not row or len(row) < 2: continue
                                
                                col0 = str(row[0]).strip() if row[0] is not None else ""
                                col1 = str(row[1]).strip() if row[1] is not None else ""
                                
                                if "Avaliação do Docente" in col1 or "Comentários dos Alunos" in col1: continue
                                if not col1 or len(col1) < 5: continue
                                    
                                if re.match(r'^\d+$', col0):
                                    texto_limpo = re.sub(r'\s+', ' ', col1.replace('\n', ' ')).strip()
                                    comentarios_arquivo.append(texto_limpo)
                                elif col0 == "" and len(comentarios_arquivo) > 0:
                                    texto_limpo = re.sub(r'\s+', ' ', col1.replace('\n', ' ')).strip()
                                    comentarios_arquivo[-1] += " " + texto_limpo
                                    
                    # Fallback Textual
                    if len(comentarios_arquivo) == 0 and "Comentários dos Alunos para o Professor" in texto_completo:
                        bloco_comentarios = texto_completo.split("Comentários dos Alunos para o Professor")[1]
                        bloco_comentarios = re.sub(r'Avaliação do Docente pelo Discente.*?\d/\d', '', bloco_comentarios, flags=re.DOTALL)
                        linhas = bloco_comentarios.split('\n')
                        comentario_atual, numero_esperado = "", 1 
                        for linha in linhas:
                            linha = linha.strip()
                            if not linha: continue
                            match = re.match(r'^(\d{1,2})(?:\s+|$)', linha)
                            if match:
                                num_encontrado = int(match.group(1))
                                if numero_esperado <= num_encontrado <= numero_esperado + 3:
                                    if len(comentario_atual) > 5: comentarios_arquivo.append(comentario_atual.strip())
                                    comentario_atual = linha[match.end():].strip() + " "
                                    numero_esperado = num_encontrado + 1
                                    continue
                            comentario_atual += linha + " "
                        if len(comentario_atual) > 5: comentarios_arquivo.append(comentario_atual.strip())

                resumo_arquivos.append({
                    "Arquivo": uploaded_file.name,
                    "Professor": professor_encontrado,
                    "Semestre": f"{semestre}/{ano}",
                    "Qtd. Comentários Extraídos": len(comentarios_arquivo)
                })

                for c in comentarios_arquivo:
                    comentarios_preparados.append({
                        'professor': professor_encontrado, 'ano': ano, 'semestre': semestre,
                        'media': media, 'universo': universo, 'realizadas': realizadas,
                        'nao_realizadas': nao_realizadas, 'comentario_original': c
                    })

        st.success(f"✅ Leitura concluída: **{len(uploaded_files)} arquivo(s)** contendo **{len(comentarios_preparados)} comentários reais**.")
        with st.expander("Clique para verificar a extração de cada PDF"):
            st.dataframe(pd.DataFrame(resumo_arquivos), width="stretch")

        # 3. Análise IA em Lote
        if len(comentarios_preparados) > 0:
            if st.button("Iniciar Análise na GPU", type="primary"):
                prompt_sistema = """Você é um analista educacional. Leia o comentário do aluno e extraia duas coisas:
                1. Categorias de Avaliação: Didatica, Avaliacao/Provas, Dominio de Conteudo, Organizacao, Postura/Relacionamento, Elogio, Outros.
                2. Motivos de Risco de Evasão (se houver queixa grave): Tempo/Trabalho, Saude/Fadiga Mental, Dificuldade Extrema, Infraestrutura/Deslocamento, Nenhum.
                
                Retorne APENAS um JSON válido neste formato:
                {"categorias_avaliacao": ["cat1"], "motivos_evasao": ["motivo1"], "resumo": "resumo de 1 linha", "sentimento": "Positivo", "Negativo" ou "Neutro"}"""
                
                resultados_avaliacao, resultados_evasao = [], []
                barra_progresso = st.progress(0)
                status_texto = st.empty()
                total = len(comentarios_preparados)
                
                for i, item in enumerate(comentarios_preparados):
                    status_texto.text(f"Analisando comentário {i+1} de {total}... (Prof. {item['professor']})")
                    try:
                        resposta = ollama.chat(model='llama3', messages=[
                            {'role': 'system', 'content': prompt_sistema},
                            {'role': 'user', 'content': item['comentario_original']}
                        ], format='json')
                        
                        dados = json.loads(resposta['message']['content'])
                        
                        cat_aval = dados.get('categorias_avaliacao', ['Outros'])
                        if isinstance(cat_aval, str): cat_aval = [cat_aval]
                        cat_evasao = dados.get('motivos_evasao', ['Nenhum'])
                        if isinstance(cat_evasao, str): cat_evasao = [cat_evasao]
                        
                        base_dict = item.copy()
                        base_dict['resumo_ia'] = dados.get('resumo', '')
                        
                        for cat in cat_aval:
                            row_aval = base_dict.copy()
                            row_aval['categoria_identificada'] = cat
                            row_aval['sentimento'] = dados.get('sentimento', 'Neutro')
                            resultados_avaliacao.append(row_aval)
                            
                        for motivo in cat_evasao:
                            motivo_limpo = motivo.strip().capitalize()
                            if motivo_limpo not in ['Nenhum', 'None', '', 'Nenhuma']:
                                row_evasao = base_dict.copy()
                                row_evasao['fator_evasao'] = motivo_limpo
                                resultados_evasao.append(row_evasao)
                                
                    except Exception as e:
                        st.error(f"Erro no comentário {i+1}: {e}")
                        
                    barra_progresso.progress((i + 1) / total)
                    
                status_texto.text("Análise em lote concluída com sucesso!")
                
                df_aval = pd.DataFrame(resultados_avaliacao)
                df_evas = pd.DataFrame(resultados_evasao)
                st.session_state['df_avaliacao'] = df_aval
                st.session_state['df_evasao'] = df_evas
                
                st.success("✅ Lote processado! Acesse os painéis nas abas superiores.")
                
                col_d1, col_d2 = st.columns(2)
                col_d1.download_button("Baixar CSV - Avaliações", data=df_aval.to_csv(index=False).encode('utf-8'), file_name="avaliacoes.csv", mime="text/csv")
                if not df_evas.empty:
                    col_d2.download_button("Baixar CSV - Risco Evasão", data=df_evas.to_csv(index=False).encode('utf-8'), file_name="evasao.csv", mime="text/csv")

# ==========================================
# ABA 2: DASHBOARD DOCENTE
# ==========================================
with tab2:
    st.markdown("### 📈 Painel Interativo de Avaliação Docente")
    if st.session_state['df_avaliacao'] is not None:
        df_dash = st.session_state['df_avaliacao'].copy()
        df_dash['periodo'] = df_dash['semestre'].astype(str) + '/' + df_dash['ano'].astype(str)
        
        f_col1, f_col2, f_col3 = st.columns(3)
        prof_sel = f_col1.multiselect("Filtrar Professor(es)", options=df_dash['professor'].unique(), default=df_dash['professor'].unique())
        per_sel = f_col2.multiselect("Filtrar Semestre/Ano", options=df_dash['periodo'].unique(), default=df_dash['periodo'].unique())
        sent_sel = f_col3.multiselect("Filtrar Sentimento", options=df_dash['sentimento'].unique(), default=df_dash['sentimento'].unique())
        
        df_filtrado = df_dash[(df_dash['professor'].isin(prof_sel)) & (df_dash['periodo'].isin(per_sel)) & (df_dash['sentimento'].isin(sent_sel))]
        
        if not df_filtrado.empty:
            st.markdown("---")
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total de Apontamentos", len(df_filtrado))
            kpi2.metric("Avaliações Negativas", len(df_filtrado[df_filtrado['sentimento'] == 'Negativo']))
            kpi3.metric("Taxa de Críticas", f"{(len(df_filtrado[df_filtrado['sentimento'] == 'Negativo']) / len(df_filtrado)) * 100:.1f}%")
            
            gcol1, gcol2 = st.columns([2, 1])
            with gcol1:
                fig_cat = px.bar(df_filtrado['categoria_identificada'].value_counts().reset_index(), y='categoria_identificada', x='count', orientation='h', title="Volume por Categoria", color='count', color_continuous_scale='Blues')
                fig_cat.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="Quantidade", yaxis_title="")
                st.plotly_chart(fig_cat, width="stretch")
            with gcol2:
                fig_pie = px.pie(df_filtrado, names='sentimento', title="Sentimento Geral", color='sentimento', color_discrete_map={'Positivo': '#2ecc71', 'Neutro': '#95a5a6', 'Negativo': '#e74c3c'}, hole=0.4)
                st.plotly_chart(fig_pie, width="stretch")

            st.dataframe(df_filtrado[['professor', 'periodo', 'categoria_identificada', 'sentimento', 'resumo_ia', 'comentario_original']], width="stretch")
        else:
            st.warning("Nenhum dado para os filtros selecionados.")
    else:
        st.info("Processe os PDFs na Aba 1.")

# ==========================================
# ABA 3: DASHBOARD DE EVASÃO
# ==========================================
with tab3:
    st.markdown("### 🚨 Painel de Mapeamento de Risco de Evasão")
    if st.session_state['df_evasao'] is not None:
        df_evasao = st.session_state['df_evasao'].copy()
        if df_evasao.empty:
            st.success("🎉 Nenhum relato de risco de evasão detectado neste lote.")
        else:
            df_evasao['periodo'] = df_evasao['semestre'].astype(str) + '/' + df_evasao['ano'].astype(str)
            evasao_sel = st.multiselect("Analisar evasão por Professor", options=df_evasao['professor'].unique(), default=df_evasao['professor'].unique())
            df_evasao_filtrado = df_evasao[df_evasao['professor'].isin(evasao_sel)]
            
            if not df_evasao_filtrado.empty:
                e_kpi1, e_kpi2 = st.columns(2)
                e_kpi1.metric("🚨 Total de Alertas Detectados", len(df_evasao_filtrado))
                e_kpi2.metric("⚠️ Fator de Maior Risco", df_evasao_filtrado['fator_evasao'].mode()[0])
                
                e_col1, e_col2 = st.columns([1, 1])
                with e_col1:
                    fig_evasao = px.bar(df_evasao_filtrado['fator_evasao'].value_counts().reset_index(), x='fator_evasao', y='count', title="Fatores de Risco", color='count', color_continuous_scale='Reds')
                    st.plotly_chart(fig_evasao, width="stretch")
                with e_col2:
                    fig_pie_evasao = px.pie(df_evasao_filtrado, names='fator_evasao', title="Concentração", hole=0.3, color_discrete_sequence=px.colors.sequential.OrRd[::-1])
                    st.plotly_chart(fig_pie_evasao, width="stretch")
                
                st.dataframe(df_evasao_filtrado[['professor', 'periodo', 'fator_evasao', 'resumo_ia', 'comentario_original']], width="stretch")
    else:
        st.info("Processe os PDFs na Aba 1.")

# ==========================================
# ABA 4: COMPARATIVO CHEFIA (NOVO MODELO LINEAR)
# ==========================================
with tab4:
    st.markdown("### 👥 Painel Estratégico da Chefia de Departamento")
    st.markdown("Visão macro linear para ranqueamento e identificação rápida de gargalos no corpo docente.")

    if st.session_state['df_avaliacao'] is not None:
        df_comp = st.session_state['df_avaliacao'].copy()
        professores_unicos = df_comp['professor'].unique()

        if len(professores_unicos) <= 1:
            st.warning("⚠️ O painel comparativo exige PDFs de 2 ou mais professores diferentes.")
        else:
            # KPIs Iniciais
            c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
            c_kpi1.metric("Docentes Analisados", len(professores_unicos))
            c_kpi2.metric("Total de Apontamentos", len(df_comp))
            
            total_alertas_evasao = len(st.session_state['df_evasao']) if st.session_state['df_evasao'] is not None else 0
            c_kpi3.metric("Alertas Críticos de Evasão", total_alertas_evasao)
            
            st.markdown("---")
            
            # ---------------------------------------------------------
            # SEÇÃO 1: ALERTAS AUTOMATIZADOS
            # ---------------------------------------------------------
            st.subheader("💡 Destaques Departamentais (Automático)")
            
            df_sent = df_comp.groupby(['professor', 'sentimento']).size().unstack(fill_value=0).reset_index()
            for col in ['Positivo', 'Negativo', 'Neutro']:
                if col not in df_sent.columns: df_sent[col] = 0
            df_sent['Total'] = df_sent['Positivo'] + df_sent['Negativo'] + df_sent['Neutro']
            df_sent['% Negativo'] = (df_sent['Negativo'] / df_sent['Total']) * 100
            df_sent['% Positivo'] = (df_sent['Positivo'] / df_sent['Total']) * 100
            
            prof_mais_criticado = df_sent.loc[df_sent['% Negativo'].idxmax()] if not df_sent.empty else None
            prof_mais_elogiado = df_sent.loc[df_sent['% Positivo'].idxmax()] if not df_sent.empty else None
            
            df_negativos = df_comp[df_comp['sentimento'] == 'Negativo']
            gargalo_didatica = "N/A"
            gargalo_provas = "N/A"
            if not df_negativos.empty:
                didatica_counts = df_negativos[df_negativos['categoria_identificada'] == 'Didatica']['professor'].value_counts()
                if not didatica_counts.empty: gargalo_didatica = didatica_counts.idxmax()
                
                provas_counts = df_negativos[df_negativos['categoria_identificada'] == 'Avaliacao/Provas']['professor'].value_counts()
                if not provas_counts.empty: gargalo_provas = provas_counts.idxmax()

            col_a1, col_a2, col_a3 = st.columns(3)
            if prof_mais_elogiado is not None:
                col_a1.info(f"🏆 **Maior Aprovação:**\n\n**{prof_mais_elogiado['professor']}** ({prof_mais_elogiado['% Positivo']:.1f}%)")
                col_a2.error(f"⚠️ **Maior Rejeição:**\n\n**{prof_mais_criticado['professor']}** ({prof_mais_criticado['% Negativo']:.1f}%)")
            col_a3.warning(f"🚨 **Pior em Didática:** {gargalo_didatica}\n\n🚨 **Pior em Provas:** {gargalo_provas}")

            st.markdown("---")
            
            # ---------------------------------------------------------
            # SEÇÃO 2: RANKING DE SENTIMENTO (BARRAS 100%)
            # ---------------------------------------------------------
            st.subheader("📊 Ranking Geral de Aprovação vs. Rejeição")
            st.markdown("Gráfico normalizado (100%). Ordenado do professor com **maior taxa de rejeição** (topo) para o mais bem avaliado (base).")
            
            df_sent_melt = df_sent.melt(id_vars=['professor', 'Total', '% Negativo'], value_vars=['Negativo', 'Neutro', 'Positivo'], var_name='Sentimento', value_name='Quantidade')
            df_sent_melt = df_sent_melt.sort_values(by='% Negativo', ascending=False)
            
            fig_ranking = px.bar(
                df_sent_melt, 
                y='professor', 
                x='Quantidade', 
                color='Sentimento', 
                orientation='h',
                color_discrete_map={'Positivo': '#2ecc71', 'Neutro': '#95a5a6', 'Negativo': '#e74c3c'}
            )
            # CORREÇÃO: Aplica a normalização e o empilhamento dentro do update_layout
            fig_ranking.update_layout(
                barmode='stack',
                barnorm='percent',
                xaxis_title="Proporção (%)", 
                yaxis_title="", 
                height=max(300, len(professores_unicos) * 45)
            )
            fig_ranking.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_ranking, width="stretch")

            st.markdown("---")
            
            # ---------------------------------------------------------
            # SEÇÃO 3: MAPA DE CALOR (DIAGNÓSTICO EXATO)
            # ---------------------------------------------------------
            st.subheader("🔥 Mapa de Gargalos: Onde o professor está errando?")
            st.markdown("Este mapa foca **exclusivamente nas críticas (Sentimento Negativo)**. Ele mostra exatamente qual categoria gerou a insatisfação de cada professor.")
            
            if not df_negativos.empty:
                heatmap_data = df_negativos.groupby(['professor', 'categoria_identificada']).size().unstack(fill_value=0)
                fig_heat = px.imshow(heatmap_data, text_auto=True, color_continuous_scale='YlOrRd', aspect="auto")
                fig_heat.update_layout(xaxis_title="Motivo da Crítica", yaxis_title="", height=max(300, len(heatmap_data) * 45))
                st.plotly_chart(fig_heat, width="stretch")
            else:
                st.success("🎉 Excelente! Não houve nenhuma crítica (Sentimento Negativo) registrada neste lote.")
                fig_heat = None

            # --- BOTÃO DE GERAÇÃO DE PDF ---
            st.markdown("---")
            st.subheader("📥 Exportar Relatório Executivo")
            
            if st.button("Gerar Relatório Fotográfico (PDF)", type="secondary"):
                try:
                    from fpdf import FPDF
                    with st.spinner("Diagramando o relatório..."):
                        pdf = FPDF(orientation="L", unit="mm", format="A4")
                        pdf.set_auto_page_break(auto=True, margin=15)
                        
                        pdf.add_page()
                        pdf.set_font("Arial", 'B', 18)
                        pdf.cell(0, 15, "Relatorio Estrategico da Chefia de Departamento", ln=True, align='C')
                        pdf.set_font("Arial", '', 12)
                        pdf.cell(0, 8, f"Docentes analisados: {len(professores_unicos)}", ln=True, align='C')
                        pdf.ln(5)

                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_rank:
                            fig_ranking.write_image(tmp_rank.name, width=1200, height=600)
                            pdf.image(tmp_rank.name, x=20, y=None, w=250)

                        if fig_heat is not None:
                            pdf.add_page()
                            pdf.set_font("Arial", 'B', 16)
                            pdf.cell(0, 15, "Diagnostico de Gargalos (Criticas por Categoria)", ln=True, align='C')
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_heat:
                                fig_heat.write_image(tmp_heat.name, width=1200, height=500)
                                pdf.image(tmp_heat.name, x=20, y=None, w=250)

                        tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                        pdf.output(tmp_pdf.name)
                        
                        with open(tmp_pdf.name, "rb") as f:
                            pdf_bytes = f.read()

                        os.unlink(tmp_rank.name)
                        if fig_heat is not None: os.unlink(tmp_heat.name)

                        st.success("✅ Relatório Executivo gerado com sucesso!")
                        st.download_button(
                            label="⬇️ Baixar PDF da Chefia",
                            data=pdf_bytes,
                            file_name="relatorio_chefia_ranking.pdf",
                            mime="application/pdf"
                        )
                except ImportError:
                    st.error("⚠️ Instale no terminal: pip install fpdf kaleido")
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {e}")
    else:
        st.info("Processe os arquivos PDF na Aba 1.")
