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
# CONFIGURAÇÃO INICIAL DA PÁGINA
# ==========================================
st.set_page_config(page_title="Sistema Integrado de Avaliação Docente", layout="wide")
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
        
        with st.spinner("Lendo PDFs e mapeando a estrutura visual das tabelas..."):
            for uploaded_file in uploaded_files:
                texto_completo = ""
                
                with pdfplumber.open(uploaded_file) as pdf:
                    for page in pdf.pages:
                        texto_completo += page.extract_text() + "\n"
                        
                    # 1. Captura dos Metadados (O TRITURADOR DE CABEÇALHOS BLINDADO COM CORTADOR)
                    try:
                        # CORTADOR DE SEGURANÇA: Isola o cabeçalho cortando no rodapé do sistema
                        texto_cabecalho = texto_completo.split('*Os alunos')[0]
                        linhas_cabecalho = texto_cabecalho.split('\n')
                        
                        # Palavras que serão APAGADAS da linha, preservando o resto
                        lixo_sub = [
                            r'Professor', r'Pato Branco', r'C[aâ]mpus:', r'Campus', r'UTFPR', 
                            r'UNIVERSI\w*', r'TECHOLOGICA', r'PARAN[AÁ]'
                        ]
                        
                        # Palavras do sistema que justificam a exclusão da LINHA INTEIRA
                        lixo_drop = [
                            r'\d{2}/\d{2}/\d{4}', r'\d{2}:\d{2}', r'Avalia[cç][aã]o do Docente', 
                            r'Minist[eé]rio da Educa[cç][aã]o', r'Universidade\s+Tec', 
                            r'UNIVERSIDADE\s+TEC', r'M[eé]dia de todas', r'm[eé]dia final', 
                            r'Semestre/ano', r'Universo \(', r'Avalia[cç][õo]es realizadas', 
                            r'Avalia[cç][õo]es n[aã]o', r'pontos', r'realizadas\)',
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
                            
                            # Pula linhas que são só números (ex: nota 25) ou ano (ex: 2/2025)
                            if re.match(r'^\d+(?:[.,]\d+)?$', linha) or re.match(r'^\d{1,2}/\d{4}$', linha):
                                continue
                                
                            # Aplica a borracha nas palavras lixo
                            for ls in lixo_sub:
                                linha = re.sub(ls, '', linha, flags=re.IGNORECASE).strip()
                                
                            # Limpa sujeiras de quebra de PDF e pontuações isoladas
                            linha = re.sub(r'FEDERAL,\s*DO', '', linha, flags=re.IGNORECASE).strip()
                            linha = re.sub(r'^[,.-]+$', '', linha).strip()
                                
                            if len(linha) > 2:
                                nome_parts.append(linha)
                                
                        professor = " ".join(nome_parts)
                        professor = re.sub(r'\s+', ' ', professor).strip()
                        if not professor:
                            professor = "Desconhecido"
                            
                        # Métricas numéricas
                        padrao_metadados = r'(\d+(?:[.,]\d+)?)\D+?(?<!\d/)(?<!\d)(0?[12]\s*/\s*20\d{2})(?!\d)\D+?(\d+)\D+?(\d+)\D+?(\d+)'
                        match_valores = re.search(padrao_metadados, texto_completo)
                        
                        if match_valores:
                            media, semestre_ano, universo, realizadas, nao_realizadas = match_valores.groups()
                            semestre_ano = semestre_ano.replace(' ', '')
                            semestre, ano = semestre_ano.split('/')
                        else:
                            media, semestre, ano, universo, realizadas, nao_realizadas = 0, "0", "0000", 0, 0, 0
                    except Exception as e:
                        professor, media, semestre, ano, universo, realizadas, nao_realizadas = "Erro", 0, "0", "0000", 0, 0, 0

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
                    "Professor": professor,
                    "Semestre": f"{semestre}/{ano}",
                    "Qtd. Comentários Extraídos": len(comentarios_arquivo)
                })

                for c in comentarios_arquivo:
                    comentarios_preparados.append({
                        'professor': professor, 'ano': ano, 'semestre': semestre,
                        'media': media, 'universo': universo, 'realizadas': realizadas,
                        'nao_realizadas': nao_realizadas, 'comentario_original': c
                    })

        st.success(f"✅ Leitura concluída: **{len(uploaded_files)} arquivo(s)** contendo **{len(comentarios_preparados)} comentários reais**.")
        with st.expander("Clique para verificar a extração de cada PDF"):
            st.dataframe(pd.DataFrame(resumo_arquivos), use_container_width=True)

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
                st.plotly_chart(fig_cat, use_container_width=True)
            with gcol2:
                fig_pie = px.pie(df_filtrado, names='sentimento', title="Sentimento Geral", color='sentimento', color_discrete_map={'Positivo': '#2ecc71', 'Neutro': '#95a5a6', 'Negativo': '#e74c3c'}, hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)

            st.dataframe(df_filtrado[['professor', 'periodo', 'categoria_identificada', 'sentimento', 'resumo_ia', 'comentario_original']], use_container_width=True)
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
                    st.plotly_chart(fig_evasao, use_container_width=True)
                with e_col2:
                    fig_pie_evasao = px.pie(df_evasao_filtrado, names='fator_evasao', title="Concentração", hole=0.3, color_discrete_sequence=px.colors.sequential.OrRd[::-1])
                    st.plotly_chart(fig_pie_evasao, use_container_width=True)
                
                st.dataframe(df_evasao_filtrado[['professor', 'periodo', 'fator_evasao', 'resumo_ia', 'comentario_original']], use_container_width=True)
    else:
        st.info("Processe os PDFs na Aba 1.")

# ==========================================
# ABA 4: COMPARATIVO CHEFIA
# ==========================================
with tab4:
    st.markdown("### 👥 Painel Estratégico da Chefia de Departamento")
    st.markdown("Visão macro para identificar os pontos fortes e os gargalos do corpo docente.")

    if st.session_state['df_avaliacao'] is not None:
        df_comp = st.session_state['df_avaliacao'].copy()
        professores_unicos = df_comp['professor'].unique()

        if len(professores_unicos) <= 1:
            st.warning("⚠️ O painel comparativo exige PDFs de 2 ou mais professores diferentes.")
        else:
            c_kpi1, c_kpi2 = st.columns(2)
            c_kpi1.metric("Docentes em Comparação", len(professores_unicos))
            c_kpi2.metric("Apontamentos Processados", len(df_comp))
            st.markdown("---")
            
            # --- 1. GRÁFICO DE RADAR ---
            st.subheader("🕸️ Perfil Docente: Mapa de Competências (Radar)")
            st.markdown("Mostra o **Volume de Elogios e Avaliações Positivas** em cada categoria, permitindo visualizar onde cada professor se destaca.")
            
            prof_radar_sel = st.multiselect("Selecione os professores para sobrepor no Radar:", options=professores_unicos, default=professores_unicos[:3])
            
            if prof_radar_sel:
                df_pos = df_comp[(df_comp['sentimento'] == 'Positivo') | (df_comp['categoria_identificada'] == 'Elogio')]
                categorias = ['Didatica', 'Avaliacao/Provas', 'Dominio de Conteudo', 'Organizacao', 'Postura/Relacionamento']
                base_grid = pd.DataFrame(list(itertools.product(prof_radar_sel, categorias)), columns=['professor', 'categoria_identificada'])
                
                df_radar_counts = df_pos.groupby(['professor', 'categoria_identificada']).size().reset_index(name='Volume Positivo')
                df_radar_final = pd.merge(base_grid, df_radar_counts, on=['professor', 'categoria_identificada'], how='left').fillna(0)

                # Paleta BOLD de Extremo Contraste
                cores_berrantes = ['#E6194B', '#3CB371', '#4363D8', '#F58231', '#911EB4', '#46F0F0', '#F032E6']
                
                fig_radar = px.line_polar(
                    df_radar_final, 
                    r='Volume Positivo', 
                    theta='categoria_identificada', 
                    color='professor', 
                    line_close=True, 
                    markers=True,
                    color_discrete_sequence=cores_berrantes 
                )
                fig_radar.update_traces(fill='toself', opacity=0.3)
                fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, showticklabels=True)), height=500)
                st.plotly_chart(fig_radar, use_container_width=True)
            else:
                st.info("Selecione ao menos um professor para exibir o radar.")

            st.markdown("---")
            
            # --- 2. MAPA DE CALOR ---
            st.subheader("🔥 Mapa de Calor: Concentração de Críticas (Gargalos)")
            st.markdown("Cruza os professores com as categorias que mais receberam **Avaliações Negativas**.")
            
            df_neg = df_comp[df_comp['sentimento'] == 'Negativo']
            if not df_neg.empty:
                heatmap_data = df_neg.groupby(['professor', 'categoria_identificada']).size().unstack(fill_value=0)
                
                fig_heat = px.imshow(heatmap_data, text_auto=True, color_continuous_scale='Reds', aspect="auto")
                fig_heat.update_layout(xaxis_title="Categoria da Crítica", yaxis_title="Professor", height=400)
                st.plotly_chart(fig_heat, use_container_width=True)
            else:
                st.success("🎉 Nenhum comentário classificado como Negativo neste lote de avaliações!")
                fig_heat = None

            # --- BOTÃO DE GERAÇÃO DE PDF ---
            st.markdown("---")
            st.subheader("📥 Exportar Relatório Executivo")
            
            if st.button("Gerar Relatório Fotográfico (PDF)", type="secondary"):
                try:
                    from fpdf import FPDF
                    with st.spinner("Fotografando gráficos de Radar e Mapa de Calor..."):
                        pdf = FPDF(orientation="L", unit="mm", format="A4")
                        pdf.set_auto_page_break(auto=True, margin=15)
                        
                        pdf.add_page()
                        pdf.set_font("Arial", 'B', 18)
                        pdf.cell(0, 15, "Relatorio Comparativo - Inteligencia Educacional", ln=True, align='C')
                        pdf.set_font("Arial", '', 12)
                        pdf.cell(0, 8, f"Docentes avaliados no relatorio: {len(prof_radar_sel)}", ln=True, align='C')
                        pdf.ln(5)

                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_radar:
                            fig_radar.write_image(tmp_radar.name, width=1200, height=600)
                            pdf.image(tmp_radar.name, x=20, y=None, w=250)

                        if fig_heat is not None:
                            pdf.add_page()
                            pdf.set_font("Arial", 'B', 16)
                            pdf.cell(0, 15, "Mapa de Gargalos Departamentais", ln=True, align='C')
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_heat:
                                fig_heat.write_image(tmp_heat.name, width=1200, height=500)
                                pdf.image(tmp_heat.name, x=20, y=None, w=250)

                        tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                        pdf.output(tmp_pdf.name)
                        
                        with open(tmp_pdf.name, "rb") as f:
                            pdf_bytes = f.read()

                        os.unlink(tmp_radar.name)
                        if fig_heat is not None: os.unlink(tmp_heat.name)

                        st.success("✅ Relatório Executivo gerado com sucesso!")
                        st.download_button(
                            label="⬇️ Baixar PDF do Conselho",
                            data=pdf_bytes,
                            file_name="relatorio_radar_chefia.pdf",
                            mime="application/pdf"
                        )
                except ImportError:
                    st.error("⚠️ Instale no terminal: pip install fpdf kaleido")
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {e}")
    else:
        st.info("Processe os arquivos PDF na Aba 1.")
