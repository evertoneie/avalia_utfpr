import streamlit as st
import pdfplumber
import pandas as pd
import re
import ollama
import json
import plotly.express as px
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
    "📄 1. Processar PDFs em Lote", 
    "📈 2. Dashboard Docente", 
    "🚨 3. Painel de Evasão",
    "👥 4. Comparativo Chefia"
])

# ==========================================
# ABA 1: EXTRAÇÃO E PROCESSAMENTO EM LOTE
# ==========================================
with tab1:
    st.markdown("Faça o upload de **um ou vários** PDFs simultaneamente. A IA processará todos os arquivos de uma vez e detectará motivos de evasão.")
    
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
                        
                    try:
                        match_prof = re.search(r'([^\n]+)\s+Média de todas as avaliações', texto_completo)
                        professor = match_prof.group(1).strip() if match_prof else "Desconhecido"
                        professor = re.sub(r'(?i)^Professor\s+', '', professor)
                        
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

                    comentarios_arquivo = []
                    
                    for page in pdf.pages:
                        tabelas = page.extract_tables()
                        for tabela in tabelas:
                            for row in tabela:
                                if not row or len(row) < 2: 
                                    continue
                                
                                col0 = str(row[0]).strip() if row[0] is not None else ""
                                col1 = str(row[1]).strip() if row[1] is not None else ""
                                
                                if "Avaliação do Docente" in col1 or "Comentários dos Alunos" in col1:
                                    continue
                                    
                                if not col1 or len(col1) < 5: 
                                    continue
                                    
                                if re.match(r'^\d+$', col0):
                                    texto_limpo = re.sub(r'\s+', ' ', col1.replace('\n', ' ')).strip()
                                    comentarios_arquivo.append(texto_limpo)
                                    
                                elif col0 == "" and len(comentarios_arquivo) > 0:
                                    texto_limpo = re.sub(r'\s+', ' ', col1.replace('\n', ' ')).strip()
                                    comentarios_arquivo[-1] += " " + texto_limpo
                                    
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

        st.success(f"✅ Leitura estrutural concluída: **{len(uploaded_files)} arquivo(s)** contendo **{len(comentarios_preparados)} comentários reais**.")
        with st.expander("Clique para verificar a contagem de cada PDF"):
            st.dataframe(pd.DataFrame(resumo_arquivos), use_container_width=True)

        if len(comentarios_preparados) > 0:
            if st.button("Iniciar Análise na GPU", type="primary"):
                prompt_sistema = """Você é um analista educacional. Leia o comentário do aluno e extraia duas coisas:
                1. Categorias de Avaliação do Docente: Didatica, Avaliacao/Provas, Dominio de Conteudo, Organizacao, Postura/Relacionamento, Elogio, Outros.
                2. Motivos de Risco de Evasão (se o aluno demonstrar problemas de permanência): Tempo/Trabalho, Saude/Fadiga Mental, Dificuldade Extrema, Infraestrutura/Deslocamento, Nenhum.
                
                Retorne APENAS um JSON válido neste formato:
                {"categorias_avaliacao": ["cat1"], "motivos_evasao": ["motivo1"], "resumo": "resumo de 1 linha", "sentimento": "Positivo", "Negativo" ou "Neutro"}"""
                
                resultados_avaliacao, resultados_evasao = [], []
                barra_progresso = st.progress(0)
                status_texto = st.empty()
                total = len(comentarios_preparados)
                
                for i, item in enumerate(comentarios_preparados):
                    status_texto.text(f"Processando comentário {i+1} de {total}... (Prof. {item['professor']})")
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
                        st.error(f"Erro no processamento da linha {i+1}: {e}")
                        
                    barra_progresso.progress((i + 1) / total)
                    
                status_texto.text("Análise em lote concluída com sucesso!")
                
                df_aval = pd.DataFrame(resultados_avaliacao)
                df_evas = pd.DataFrame(resultados_evasao)
                st.session_state['df_avaliacao'] = df_aval
                st.session_state['df_evasao'] = df_evas
                
                st.success("✅ Lote processado! Acesse os painéis nas abas superiores para visualizar.")
                
                col_down1, col_down2 = st.columns(2)
                col_down1.download_button("Baixar CSV - Avaliações", data=df_aval.to_csv(index=False).encode('utf-8'), file_name="lote_avaliacoes_processadas.csv", mime="text/csv")
                if not df_evas.empty:
                    col_down2.download_button("Baixar CSV - Risco Evasão", data=df_evas.to_csv(index=False).encode('utf-8'), file_name="lote_alertas_evasao.csv", mime="text/csv")

# ==========================================
# ABA 2: DASHBOARD DOCENTE
# ==========================================
with tab2:
    st.markdown("### 📈 Painel Interativo de Avaliação Docente")
    if st.session_state['df_avaliacao'] is not None:
        df_dash = st.session_state['df_avaliacao'].copy()
        df_dash['periodo'] = df_dash['semestre'].astype(str) + '/' + df_dash['ano'].astype(str)
        
        f_col1, f_col2, f_col3 = st.columns(3)
        professores_disp = df_dash['professor'].unique().tolist()
        prof_sel = f_col1.multiselect("Filtrar Professor(es)", options=professores_disp, default=professores_disp)
        
        periodos_disp = df_dash['periodo'].unique().tolist()
        per_sel = f_col2.multiselect("Filtrar Semestre/Ano", options=periodos_disp, default=periodos_disp)
        
        sentimentos_disp = df_dash['sentimento'].unique().tolist()
        sent_sel = f_col3.multiselect("Filtrar Sentimento", options=sentimentos_disp, default=sentimentos_disp)
        
        df_filtrado = df_dash[
            (df_dash['professor'].isin(prof_sel)) & 
            (df_dash['periodo'].isin(per_sel)) &
            (df_dash['sentimento'].isin(sent_sel))
        ]
        
        if not df_filtrado.empty:
            st.markdown("---")
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total de Apontamentos", len(df_filtrado))
            kpi2.metric("Avaliações Negativas", len(df_filtrado[df_filtrado['sentimento'] == 'Negativo']))
            
            taxa_neg = (len(df_filtrado[df_filtrado['sentimento'] == 'Negativo']) / len(df_filtrado)) * 100
            kpi3.metric("Taxa de Críticas", f"{taxa_neg:.1f}%")
            
            gcol1, gcol2 = st.columns([2, 1])
            with gcol1:
                st.subheader("Volume por Categoria")
                fig_cat = px.bar(df_filtrado['categoria_identificada'].value_counts().reset_index(), y='categoria_identificada', x='count', orientation='h', color='count', color_continuous_scale='Blues', labels={'categoria_identificada': 'Categoria', 'count': 'Frequência'})
                fig_cat.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_cat, use_container_width=True)
                
            with gcol2:
                st.subheader("Sentimento Geral")
                fig_pie = px.pie(df_filtrado, names='sentimento', color='sentimento', color_discrete_map={'Positivo': '#2ecc71', 'Neutro': '#95a5a6', 'Negativo': '#e74c3c'}, hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)

            st.subheader("Auditoria de Comentários")
            st.dataframe(df_filtrado[['professor', 'periodo', 'categoria_identificada', 'sentimento', 'resumo_ia', 'comentario_original']], use_container_width=True)
        else:
            st.warning("Nenhum dado para os filtros selecionados.")
    else:
        st.info("Processe os arquivos PDF na Aba 1 para ver o painel.")

# ==========================================
# ABA 3: DASHBOARD DE EVASÃO
# ==========================================
with tab3:
    st.markdown("### 🚨 Painel de Mapeamento de Risco de Evasão")
    st.markdown("Monitoramento de queixas relacionadas à saúde mental, carga de trabalho e dificuldades estruturais em todo o lote de PDFs.")
    
    if st.session_state['df_evasao'] is not None:
        df_evasao = st.session_state['df_evasao'].copy()
        
        if df_evasao.empty:
            st.success("🎉 Excelente notícia! A inteligência artificial não detectou nenhum relato neste lote que indique risco de evasão.")
            st.balloons()
        else:
            df_evasao['periodo'] = df_evasao['semestre'].astype(str) + '/' + df_evasao['ano'].astype(str)
            
            evasao_profs = df_evasao['professor'].unique().tolist()
            evasao_sel = st.multiselect("Analisar evasão por Professor", options=evasao_profs, default=evasao_profs)
            df_evasao_filtrado = df_evasao[df_evasao['professor'].isin(evasao_sel)]
            
            if not df_evasao_filtrado.empty:
                e_kpi1, e_kpi2 = st.columns(2)
                e_kpi1.metric("🚨 Total de Alertas Detectados", len(df_evasao_filtrado))
                fator_principal = df_evasao_filtrado['fator_evasao'].mode()[0]
                e_kpi2.metric("⚠️ Fator de Maior Risco", fator_principal)
                
                st.markdown("---")
                e_col1, e_col2 = st.columns([1, 1])
                
                with e_col1:
                    st.subheader("Fatores de Risco Relatados")
                    fig_evasao = px.bar(
                        df_evasao_filtrado['fator_evasao'].value_counts().reset_index(), 
                        x='fator_evasao', y='count', 
                        color='count', color_continuous_scale='Reds',
                        labels={'fator_evasao': 'Motivo Declarado', 'count': 'Frequência'}
                    )
                    st.plotly_chart(fig_evasao, use_container_width=True)
                    
                with e_col2:
                    st.subheader("Concentração de Risco")
                    fig_pie_evasao = px.pie(df_evasao_filtrado, names='fator_evasao', hole=0.3, color_discrete_sequence=px.colors.sequential.OrRd[::-1])
                    st.plotly_chart(fig_pie_evasao, use_container_width=True)
                
                st.markdown("---")
                st.subheader("Relatos Originais")
                st.dataframe(df_evasao_filtrado[['professor', 'periodo', 'fator_evasao', 'resumo_ia', 'comentario_original']], use_container_width=True)
            else:
                 st.warning("Nenhum risco detectado para o(s) professor(es) filtrado(s).")
    else:
        st.info("Processe os arquivos PDF na Aba 1 para verificar os indicadores de evasão.")

# ==========================================
# ABA 4: COMPARATIVO CHEFIA 
# ==========================================
with tab4:
    st.markdown("### 👥 Painel Comparativo para Chefia de Departamento")
    st.markdown("Análise de desempenho cruzado entre professores. Ideal para identificar pontos fortes do corpo docente e atuar de forma direcionada.")

    if st.session_state['df_avaliacao'] is not None:
        df_comp = st.session_state['df_avaliacao'].copy()
        professores_unicos = df_comp['professor'].unique()

        if len(professores_unicos) <= 1:
            st.warning("⚠️ A análise comparativa não é possível porque somente um professor está sendo avaliado. Para liberar este painel, faça o upload de PDFs de diferentes professores na Aba 1.")
        else:
            def converter_para_float(val):
                try:
                    return float(str(val).replace(',', '.'))
                except:
                    return 0.0
            
            df_comp['media_num'] = df_comp['media'].apply(converter_para_float)

            c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
            c_kpi1.metric("Docentes em Comparação", len(professores_unicos))
            c_kpi2.metric("Total de Apontamentos Lidos", len(df_comp))
            prof_maior_media = df_comp.groupby('professor')['media_num'].max().idxmax()
            c_kpi3.metric("🏆 Maior Média Oficial do Lote", prof_maior_media)

            st.markdown("---")
            
            st.subheader("1. Ranking de Sentimento Geral (% Aprovação vs Críticas)")
            st.markdown("Cálculo em porcentagem (proporcional ao número de avaliações que cada professor recebeu).")
            
            df_sent = df_comp.groupby(['professor', 'sentimento']).size().unstack(fill_value=0).reset_index()
            for col in ['Positivo', 'Negativo', 'Neutro']:
                if col not in df_sent.columns: df_sent[col] = 0
                
            df_sent['Total'] = df_sent['Positivo'] + df_sent['Negativo'] + df_sent['Neutro']
            df_sent['% Negativo'] = (df_sent['Negativo'] / df_sent['Total']) * 100
            df_sent['% Positivo'] = (df_sent['Positivo'] / df_sent['Total']) * 100
            
            col_rank1, col_rank2 = st.columns(2)
            with col_rank1:
                df_rank_neg = df_sent.sort_values('% Negativo', ascending=True)
                fig_neg = px.bar(df_rank_neg, x='% Negativo', y='professor', orientation='h', 
                                 title="Taxa de Críticas (%)",
                                 color='% Negativo', color_continuous_scale='Reds')
                fig_neg.update_layout(xaxis_title="% de Comentários Negativos", yaxis_title="")
                st.plotly_chart(fig_neg, use_container_width=True)
            
            with col_rank2:
                df_rank_pos = df_sent.sort_values('% Positivo', ascending=True)
                fig_pos = px.bar(df_rank_pos, x='% Positivo', y='professor', orientation='h',
                                 title="Taxa de Elogios (%)",
                                 color='% Positivo', color_continuous_scale='Greens')
                fig_pos.update_layout(xaxis_title="% de Comentários Positivos", yaxis_title="")
                st.plotly_chart(fig_pos, use_container_width=True)

            st.markdown("---")
            
            st.subheader("2. Ranking por Critérios Específicos da IA")
            st.markdown("Selecione um critério para ver a distribuição de sentimentos entre os professores *exclusivamente* nesta categoria.")
            
            categorias_disp = df_comp['categoria_identificada'].unique()
            cat_selecionada = st.selectbox("🎯 Selecione o Critério a ser investigado:", options=categorias_disp)
            
            df_cat = df_comp[df_comp['categoria_identificada'] == cat_selecionada]
            fig_cat_comp = None # Variável para salvar no PDF depois
            if not df_cat.empty:
                df_cat_sent = df_cat.groupby(['professor', 'sentimento']).size().unstack(fill_value=0).reset_index()
                for col in ['Positivo', 'Negativo', 'Neutro']:
                    if col not in df_cat_sent.columns: df_cat_sent[col] = 0
                
                fig_cat_comp = px.bar(df_cat_sent, x='professor', y=['Positivo', 'Neutro', 'Negativo'], 
                                      title=f"Raio-X Institucional: {cat_selecionada}",
                                      color_discrete_map={'Positivo': '#2ecc71', 'Neutro': '#95a5a6', 'Negativo': '#e74c3c'},
                                      barmode='stack')
                fig_cat_comp.update_layout(xaxis_title="Professor", yaxis_title="Quantidade de Apontamentos")
                st.plotly_chart(fig_cat_comp, use_container_width=True)
            else:
                st.info("Não há dados suficientes para analisar este critério específico.")

            st.markdown("---")
            
            st.subheader("3. Comparativo Institucional (Média Oficial Extraída do PDF)")
            st.markdown("Este gráfico mostra a nota geral bruta concedida pelo sistema da Universidade.")
            
            df_medias = df_comp.groupby('professor')['media_num'].max().reset_index().sort_values('media_num', ascending=True)
            fig_medias = px.bar(df_medias, x='media_num', y='professor', orientation='h', text='media_num',
                                color='media_num', color_continuous_scale='Blues')
            fig_medias.update_traces(texttemplate='%{text:.1f}', textposition='outside')
            fig_medias.update_layout(xaxis_title="Nota Extraída", yaxis_title="")
            st.plotly_chart(fig_medias, use_container_width=True)

            # --- BOTÃO DE GERAÇÃO DE PDF EXECUTIVO ---
            st.markdown("---")
            st.subheader("📥 Relatório Fotográfico Executivo")
            st.markdown("Gere um documento formatado com estes gráficos para conselhos e reuniões departamentais.")

            if st.button("Gerar Relatório em PDF", type="secondary"):
                try:
                    from fpdf import FPDF
                    with st.spinner("Fotografando gráficos e diagramando o PDF..."):
                        
                        pdf = FPDF(orientation="L", unit="mm", format="A4") # Relatório em paisagem para caber os gráficos
                        pdf.set_auto_page_break(auto=True, margin=15)
                        
                        # Página 1: Capa e Ranking Geral
                        pdf.add_page()
                        pdf.set_font("Arial", 'B', 20)
                        pdf.cell(0, 15, "Relatorio Comparativo - Avaliacao Docente", ln=True, align='C')
                        
                        pdf.set_font("Arial", '', 12)
                        pdf.cell(0, 8, f"Docentes avaliados: {len(professores_unicos)}", ln=True, align='C')
                        pdf.cell(0, 8, f"Total de Apontamentos: {len(df_comp)}", ln=True, align='C')
                        pdf.ln(10)

                        # Criando imagens temporárias
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_neg:
                            fig_neg.write_image(tmp_neg.name, width=1000, height=500)
                            pdf.image(tmp_neg.name, x=10, y=None, w=130)
                            
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_pos:
                            fig_pos.write_image(tmp_pos.name, width=1000, height=500)
                            # Coloca a imagem de elogios lado a lado
                            pdf.image(tmp_pos.name, x=150, y=pdf.get_y() - 65, w=130)

                        # Página 2: Critérios Específicos e Médias Oficiais
                        pdf.add_page()
                        if fig_cat_comp is not None:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_cat:
                                fig_cat_comp.write_image(tmp_cat.name, width=1200, height=500)
                                pdf.image(tmp_cat.name, x=20, y=None, w=250)
                                pdf.ln(10)
                                
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_med:
                            fig_medias.write_image(tmp_med.name, width=1200, height=450)
                            pdf.image(tmp_med.name, x=20, y=None, w=250)

                        # Salvamento e disponibilização do buffer
                        tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                        pdf.output(tmp_pdf.name)
                        
                        with open(tmp_pdf.name, "rb") as f:
                            pdf_bytes = f.read()

                        # Limpeza dos arquivos temporários de imagem
                        os.unlink(tmp_neg.name)
                        os.unlink(tmp_pos.name)
                        if fig_cat_comp is not None: os.unlink(tmp_cat.name)
                        os.unlink(tmp_med.name)

                        st.success("✅ Relatório gerado com sucesso!")
                        st.download_button(
                            label="⬇️ Baixar PDF Gerado",
                            data=pdf_bytes,
                            file_name="relatorio_chefia_departamento.pdf",
                            mime="application/pdf"
                        )
                except ImportError:
                    st.error("⚠️ Para gerar o PDF, instale as bibliotecas necessárias no terminal: pip install fpdf kaleido")
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {e}. Verifique se as bibliotecas estão corretamente instaladas.")

    else:
        st.info("Processe os arquivos PDF na Aba 1 para liberar as análises gerenciais da Chefia.")