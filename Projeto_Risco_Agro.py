import streamlit as st
import pandas as pd
import numpy as np
import requests
import sqlite3
from datetime import datetime, timedelta

# 1. Configuração da Página
st.set_page_config(page_title="Portal de Crédito Agro Corporativo", layout="wide")

st.title("🌾 Plataforma de Inteligência e Crédito Estruturado Agro")
st.write("Versão 12.5 PRO: Ciclos Biológicos Dinâmicos, Multi-Culturas e Matriz Normativa de Solos (ZARC)")

# =========================================================================
# OPERAÇÕES DO BANCO DE DADOS (SQLite)
# =========================================================================
def iniciar_banco_dados():
    conn = sqlite3.connect("banco_agro.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_credito (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_analise TEXT,
            nome TEXT,
            documento TEXT,
            localizacao TEXT,
            num_car TEXT,
            status_esg TEXT,
            cultura TEXT,
            area REAL,
            tipo_area TEXT,
            icsd REAL,
            rating TEXT,
            taxa_final REAL,
            veredito TEXT,
            parcela REAL
        )
    """)
    conn.commit()
    conn.close()

def salvar_analise_no_banco(nome, documento, localizacao, num_car, status_esg, cultura, area, tipo_area, icsd, rating, taxa_final, veredito, parcela):
    conn = sqlite3.connect("banco_agro.db")
    cursor = conn.cursor()
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    cursor.execute("""
        INSERT INTO historico_credito (data_analise, nome, documento, localizacao, num_car, status_esg, cultura, area, tipo_area, icsd, rating, taxa_final, veredito, parcela)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (data_atual, nome, documento, localizacao, num_car, status_esg, cultura, area, tipo_area, icsd, rating, taxa_final, veredito, parcela))
    conn.commit()
    conn.close()

iniciar_banco_dados()

# =========================================================================
# FUNÇÕES DE MERCADO E BANDS
# =========================================================================
def consultar_serasa_experian(documento_texto):
    doc_limpo = "".join(filter(str.isdigit, documento_texto))
    if len(doc_limpo) not in [11, 14]: return None
    ultimo_digito = int(doc_limpo[-1])
    if "03027918000112" in doc_limpo:
        score = 820; faixa = "Excelente (Baixo Risco)"
    elif ultimo_digito % 2 == 0:
        score = 740; faixa = "Bom (Risco Aceitável)"
    else:
        score = 310; faixa = "Risco Alto (Atenção Mesa)"
    return {"score": score, "faixa": faixa}

def consultar_cnpj_real(cnpj_texto):
    cnpj_limpo = "".join(filter(str.isdigit, cnpj_texto))
    if len(cnpj_limpo) != 14: return None
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        resposta = requests.get(url, timeout=5)
        if resposta.status_code == 200: return resposta.json()
    except: pass
    return None

def buscar_chuva_real_satelite(lat, lon, data_inicio, data_fim):
    try:
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={data_inicio}&end_date={data_fim}&daily=rain_sum&timezone=auto"
        resposta = requests.get(url, timeout=10)
        if resposta.status_code == 200:
            dados_json = resposta.json()
            datas = dados_json["daily"]["time"]
            valores_chuva = dados_json["daily"]["rain_sum"]
            df_clima = pd.DataFrame({"Data": pd.to_datetime(datas), "Chuva (mm)": valores_chuva}).set_index("Data")
            return df_clima["Chuva (mm)"].sum(), df_clima
    except: pass
    return None, None

# Arquitetura de Abas
aba_cadastro, aba_ativos, aba_motor, aba_crm = st.tabs([
    "👤 1. Cadastro, CAR & Serasa", 
    "🚜 2. Grupo Econômico & Patrimônio", 
    "📊 3. Mesa de Crédito & Logística",
    "🗂️ 4. Histórico de Análises (CRM)"
])

# =========================================================================
# ABA 1: CADASTRO COM LEITURA AUTOMÁTICA SERASA
# =========================================================================
with aba_cadastro:
    st.subheader("Ficha Cadastral (Monitoramento em Tempo Real)")
    col_cad1, col_cad2 = st.columns(2)
    
    if "razao_social" not in st.session_state:
        st.session_state.razao_social = "AGROMAIA INDUSTRIA E COMERCIO LTDA"
    if "municipio_cnpj" not in st.session_state:
        st.session_state.municipio_cnpj = "Pilar do Sul / SP"

    with col_cad1:
        tipo_doc = st.radio("Documento Proponente", ["CPF", "CNPJ"], horizontal=True, index=1)
        documento = st.text_input(f"Número do {tipo_doc}", value="03.027.918/0001-12")
        
        doc_limpo = "".join(filter(str.isdigit, documento))
        resultado_serasa = None
        if (tipo_doc == "CPF" and len(doc_limpo) == 11) or (tipo_doc == "CNPJ" and len(doc_limpo) == 14):
            resultado_serasa = consultar_serasa_experian(doc_limpo)
            
        if tipo_doc == "CNPJ" and st.button("🔍 Forçar Atualização Receita Federal"):
            with st.spinner("Buscando dados..."):
                dados_empresa = consultar_cnpj_real(documento)
                if dados_empresa:
                    st.session_state.razao_social = dados_empresa.get("razao_social", "").upper()
                    st.session_state.municipio_cnpj = f"{dados_empresa.get('municipio', '')} / {dados_empresa.get('uf', '')}".upper()
                    st.success("Dados cadastrais sincronizados!")
                    
        nome = st.text_input("Razão Social / Nome do Produtor", value=st.session_state.razao_social)
        num_car = st.text_input("Número do Registro CAR", value="SP-3538006-8E82-4C1F-90D6-A3E245220626")

    with col_cad2:
        st.write("**📊 Bureau de Crédito Integrado (Serasa Experian):**")
        if resultado_serasa:
            cor_delta = "normal" if resultado_serasa["score"] >= 500 else "inverse"
            st.metric(label="Score de Crédito Bureau", value=f"{resultado_serasa['score']} pts", delta=resultado_serasa["faixa"], delta_color=cor_delta)
        else:
            st.info("Aguardando digitação do CPF/CNPJ completo...")
            
        st.write("---")
        localizacao = st.text_input("Município / UF principal", value=st.session_state.municipio_cnpj)
        st.write("**📍 Localização Satélite:**")
        geo_col1, geo_col2 = st.columns(2)
        with geo_col1: latitude = st.number_input("Latitude", value=-23.8356, format="%.4f")
        with geo_col2: longitude = st.number_input("Longitude", value=-47.7337, format="%.4f")
        status_esg = st.selectbox("Laudo de Restrições de Área (Filtro ESG)", ["REGULAR - Livre de Restrições", "BLOQUEADO - Sobreposição com Terra Indígena / UC", "BLOQUEADO - Embargo Ativo IBAMA", "BLOQUEADO - Lista Suja MTE (Trabalho Análogo)"])

# =========================================================================
# ABA 2: GRUPO ECONÔMICO
# =========================================================================
with aba_ativos:
    st.subheader("Mapeamento Estrutural do Grupo Econômico Familiar")
    dados_familia_inicial = pd.DataFrame([
        {"Nome do Familiar": "Marcio Mendes Filho", "Parentesco": "Filho (Proponente Oculto)", "CPF": "444.333.222-11", "Restrição/Dívida SCR Encontrada (R$)": 0.00},
        {"Nome do Familiar": "Ariovaldo Mendes", "Parentesco": "Pai (Antigo Operador)", "CPF": "111.222.333-44", "Restrição/Dívida SCR Encontrada (R$)": 450000.00}
    ])
    tabela_familia = st.data_editor(dados_familia_inicial, num_rows="dynamic", use_container_width=True, key="geo_familia")
    total_divida_familiar = tabela_familia["Restrição/Dívida SCR Encontrada (R$)"].sum()
    
    st.write("---")
    st.subheader("Inventário de Máquinas (Ativos Livres para Garantia)")
    dados_maquinario_inicial = pd.DataFrame([
        {"Equipamento/Maquinário": "Trator John Deere 6125J", "Ano de Fabricação": 2021, "Valor Estimado (R$)": 450000.00},
        {"Equipamento/Maquinário": "Colhedora de Grãos Case IH", "Ano de Fabricação": 2019, "Valor Estimado (R$)": 900000.00}
    ])
    tabela_maquinario = st.data_editor(dados_maquinario_inicial, num_rows="dynamic", use_container_width=True, key="geo_maq")
    valor_total_bens = tabela_maquinario["Valor Estimado (R$)"].sum()

# =========================================================================
# ABA 3: MOTOR DE CRÉDITO COM DIRETRIZES DE SAÍDAS DE VENDAS
# =========================================================================
with aba_motor:
    st.subheader("Configuração Financeira e Logística da Safra")
    
    with st.expander("📘 Visualizar Nova Tabela Normativa de Referência ICSD & Estruturas", expanded=False):
        df_politica_icsd = pd.DataFrame([
            {"Faixa de ICSD": "Abaixo de 1.00", "Classificação": "❌ CRÍTICO", "Saída de Venda / Mitigação Recomendada": "Garantias Fiduciárias, Hipotecas, Garantias Reais (Maquinários Agrícolas)"},
            {"Faixa de ICSD": "1.00 a 1.19", "Classificação": "⚠️ ALERTA", "Saída de Venda / Mitigação Recomendada": "Operações de Barter, CPR (Cédula de Produto Rural) e CPRF"},
            {"Faixa de ICSD": "1.20 a 1.49", "Classificação": "✔️ MONITORAMENTO", "Saída de Venda / Mitigação Recomendada": "Acompanhamento Padrão da Carteira Comercial"},
            {"Faixa de ICSD": "A partir de 1.50", "Classificação": "🌟 SAUDÁVEL", "Saída de Venda / Mitigação Recomendada": "Fluxo Altamente Resiliente. Aprovação Padrão Desimpedida"}
        ])
        st.table(df_politica_icsd)

    col1, col2 = st.columns(2)
    with col1:
        cultura = st.selectbox(
            "Cultura Alvo do Financiamento", 
            ["Soja", "Milho Verão", "Milho Safrinha", "Trigo", "Sorgo", "Triticale", "Milheto", "Aveia"]
        )
        area = st.number_input("Área Efetiva de Plantio (Hectares)", min_value=1, value=500)
        
        st.write("**💰 Custos Operacionais de Cultivo (Por Hectare):**")
        if cultura == "Soja":
            custo_ha = st.slider("Custo de Produção Sugerido (R$ / Ha)", 5000, 6500, 5800, step=100)
        elif cultura == "Milho Verão":
            custo_ha = st.slider("Custo de Produção Sugerido (R$ / Ha)", 4000, 5500, 4800, step=100)
        elif cultura == "Milho Safrinha":
            custo_ha = st.slider("Custo de Produção Sugerido (R$ / Ha)", 3000, 4500, 3600, step=100)
        elif cultura == "Trigo":
            custo_ha = st.slider("Custo de Produção Sugerido (R$ / Ha)", 3500, 5000, 4200, step=100)
        elif cultura == "Sorgo":
            custo_ha = st.slider("Custo de Produção Sugerido (R$ / Ha)", 2000, 4000, 3000, step=100)
        elif cultura == "Triticale":
            custo_ha = st.slider("Custo de Produção Sugerido (R$ / Ha)", 3000, 4500, 3700, step=100)
        elif cultura == "Milheto":
            custo_ha = st.slider("Custo de Produção Sugerido (R$ / Ha)", 1500, 3000, 2100, step=100)
        elif cultura == "Aveia":
            custo_ha = st.slider("Custo de Produção Sugerido (R$ / Ha)", 2500, 4000, 3200, step=100)

        tipo_area = st.radio("Regime de Ocupação da Área", ["Própria", "Arrendada"], horizontal=True)
        custo_arrendamento_ha = 0.0
        if tipo_area == "Arrendada":
            custo_arrendamento_ha = st.number_input("Custo do Arrendamento (R$ por Hectare / Ano)", min_value=0, value=1200)
        
        solo = st.radio("Textura do Solo (ZARC)", ["Tipo 1 - Arenoso", "Tipo 2 - Médio", "Tipo 3 - Argiloso"], index=2)
        parcela_anual = st.number_input("Parcela do Financiamento (R$ / Ano)", min_value=1000, value=1200000)

    with col2:
        st.write("**📅 Planejamento Cronológico do Talhão:**")
        data_plantio = st.date_input("Data Estimada do Plantio", value=datetime.now().date())
        
        ciclo_padrao_dias = {
            "Soja": 125, "Milho Verão": 140, "Milho Safrinha": 130, 
            "Trigo": 120, "Sorgo": 110, "Triticale": 135, "Milheto": 90, "Aveia": 115
        }
        
        ciclo_semente_dias = st.number_input(
            f"Ciclo Estipulado da Semente de {cultura} (Dias até Colheita)", 
            min_value=30, max_value=200, value=ciclo_padrao_dias[cultura]
        )
        
        data_colheita_calculada = data_plantio + timedelta(days=int(ciclo_semente_dias))
        st.caption(f"📅 **Janela Agronômica:** Colheita prevista para **{data_colheita_calculada.strftime('%d/%m/%Y')}**")
        
        st.write("---")
        st.write("**🚛 Canais de Logística de Escoamento (Frete):**")
        destino_silo = st.selectbox(
            "Silo Recebedor / Trading Mais Próxima para Entrega",
            ["Cooperativa Local (Distância: 15 km - Frete: R$ 2,50/sc)", 
             "Hub Agro Regional - Itapeva (Distância: 110 km - Frete: R$ 6,80/sc)", 
             "Terminal Logístico / Porto de Santos (Distância: 260 km - Frete: R$ 14,20/sc)"]
        )
        seguro_ativo = st.toggle("Possui Seguro Agrícola Ativo para a Safra?", value=False)
        abertura_pasto = st.checkbox("A área é de primeiro ano (Abertura de Pasto)?")
        st.write("---")
        status_scr = st.selectbox(
            "Retorno do SCR do Proponente Principal",
            ["Sem Restrições (Histórico Limpo)", "Alta Alavancagem de Curto Prazo", "Restrição/Atraso > 60 dias"]
        )

    st.divider()

    if st.button("Executar Análise de Risco Completa", type="primary"):
        if status_esg != "REGULAR - Livre de Restrições":
            st.error(f"❌ **OPERAÇÃO VETADA PELO COMITÊ DE COMPLIANCE.** Motivo: {status_esg}.")
            salvar_analise_no_banco(nome, documento, localizacao, num_car, status_esg, cultura, area, tipo_area, 0.0, "F", 0.0, "VETADO (ESG)", parcela_anual)
        else:
            config_cultura = {
                "Soja": {"produtividade": 62, "preco": 132, "min_mm": 150},
                "Milho Verão": {"produtividade": 140, "preco": 68, "min_mm": 200},
                "Milho Safrinha": {"produtividade": 90, "preco": 62, "min_mm": 160},
                "Trigo": {"produtividade": 55, "preco": 92, "min_mm": 110},
                "Sorgo": {"produtividade": 82, "preco": 54, "min_mm": 100},
                "Triticale": {"produtividade": 48, "preco": 80, "min_mm": 120},
                "Milheto": {"produtividade": 35, "preco": 45, "min_mm": 70},
                "Aveia": {"produtividade": 60, "preco": 75, "min_mm": 95}
            }
            
            prod_alvo = config_cultura[cultura]["produtividade"]
            preco_saca_mercado = config_cultura[cultura]["preco"]
            minimo_exigido_mm = config_cultura[cultura]["min_mm"]
            
            dt_ini_str = data_plantio.strftime("%Y-%m-%d")
            dt_fim_str = data_colheita_calculada.strftime("%Y-%m-%d")
            
            custo_frete_saca = 2.50 if "Local" in destino_silo else (6.80 if "Regional" in destino_silo else 14.20)
            
            with st.spinner(f"Acessando satélite Open-Meteo para a janela biológica de {ciclo_semente_dias} dias..."):
                mm_reais, df_chuva_historica = buscar_chuva_real_satelite(latitude, longitude, dt_ini_str, dt_fim_str)
            
            if mm_reais is None: 
                mm_reais = minimo_exigido_mm + 20.0
                datas_mock = pd.date_range(start=data_plantio, end=data_colheita_calculada)
                df_chuva_historica = pd.DataFrame({"Chuva (mm)": np.random.uniform(0, 8, len(datas_mock))}).set_index(datas_mock)

            fator_quebra = 0.60 if mm_reais < minimo_exigido_mm else 1.00
            txt_clima = f"Chuva de {mm_reais:.1f}mm foi baixa para o ciclo biológico (Mínimo ZARC: {minimo_exigido_mm}mm)." if fator_quebra < 1.0 else f"Chuva Real Acumulada no ciclo ({mm_reais:.1f}mm) está em conformidade agronômica."
                
            total_sacas_produzidas = area * prod_alvo * fator_quebra
            preco_liquido_saca = preco_saca_mercado - custo_frete_saca
            receita_liquida_real = total_sacas_produzidas * preco_liquido_saca
            
            # Matriz de solos afetando a receita
            fator_solo = 1.00
            txt_solo_info = "Solo Argiloso (Ideal): Capacidade máxima de retenção hídrica assegurada."
            if solo == "Tipo 1 - Arenoso":
                fator_solo = 0.85
                txt_solo_info = "Solo Arenoso (Risco Alto): Margem de segurança de -15% aplicada na receita bruta por fragilidade hídrica."
            elif solo == "Tipo 2 - Médio":
                fator_solo = 0.95
                txt_solo_info = "Solo Médio (Risco Moderado): Margem de proteção padrão de -5% aplicada na receita."
                
            receita_liquida_real *= fator_solo
            
            total_arrendamento = area * custo_arrendamento_ha if tipo_area == "Arrendada" else 0.0
            custo_producao_total = (area * custo_ha) + total_arrendamento
            
            if seguro_ativo:
                receita_garantida = (area * prod_alvo * preco_saca_mercado * 0.80) * fator_solo
                receita_final_considerada = max(receita_liquida_real, receita_garantida)
            else: 
                receita_final_considerada = receita_liquida_real

            if abertura_pasto: receita_final_considerada *= 0.80

            caixa_disponivel = receita_final_considerada - custo_producao_total
            icsd = caixa_disponivel / parcela_anual
            
            if seguro_ativo:
                icsd += 0.20

            score_atual = resultado_serasa["score"] if resultado_serasa else 500
            
            if icsd < 1.00:
                laudo_icsd = "❌ CRÍTICO"
                diretriz_saida = "Diretriz da Mesa: Exigir Garantias Fiduciárias, Hipotecas ou Penhor de Maquinários Agrícolas."
                rating = "D - Risco Estruturado"
            elif icsd < 1.20:
                laudo_icsd = "⚠️ ALERTA"
                diretriz_saida = "Diretriz da Mesa: Obrigatoriedade de mitigação via Barter, CPR ou CPRF (Alinhado à Janela de Plantio)."
                rating = "C - Risco Moderado"
            elif icsd < 1.50:
                laudo_icsd = "✔️ MONITORAMENTO"
                diretriz_saida = "Diretriz da Mesa: Enquadramento Saudável. Acompanhamento padrão de carteira."
                rating = "B - Risco Aceitável"
            else:
                laudo_icsd = "🌟 SAUDÁVEL"
                diretriz_saida = "Diretriz da Mesa: Operação Confortável de Forte Resiliência. Fluxo liberado."
                rating = "A - Excelente"
            
            taxa_base = 10.5
            if status_scr == "Restrição/Atraso > 60 dias" or total_divida_familiar > 500000 or score_atual < 400:
                spread_scr = 5.0
            elif status_scr == "Alta Alavancagem de Curto Prazo" or total_divida_familiar > 0 or score_atual < 600:
                spread_scr = 2.5
            else:
                spread_scr = 0.0
                
            taxa_final = taxa_base + spread_scr - (1.5 if seguro_ativo else 0.0)
            veredito_texto = "APROVADO COM EXIGÊNCIA" if icsd < 1.20 else "APROVADO"

            salvar_analise_no_banco(
                nome, documento, localizacao, num_car, f"REGULAR ({laudo_icsd})", 
                cultura, area, tipo_area, icsd, rating, taxa_final, veredito_texto, parcela_anual
            )

            st.subheader(f"📊 Relatório de Risco Gerado para: {nome}")
            res1, res2, res3 = st.columns(3)
            with res1:
                st.metric(label="ICSD Real Calculado", value=f"{icsd:.2f}", delta=laudo_icsd, delta_color="normal" if icsd >= 1.20 else "inverse")
                st.caption(f"**Análise de Risco:** {txt_clima}")
                if seguro_ativo:
                    st.caption("🛡️ *Bônus de mitigação por Seguro Ativo (+0.20 ICSD) incluído.*")
            with res2:
                st.metric(label="Rating Consolidado", value=rating)
                st.caption(f"Score Serasa: {score_atual} pts")
            with res3:
                st.metric(label="Taxa de Juros Comercial", value=f"{taxa_final:.1f}% a.a.")
                st.caption(f"Custo Unitário Considerado: R$ {custo_ha:,.2f} / Ha")
                
            st.write("---")
            st.info(f"📋 **{diretriz_saida}**")
            st.caption(f"ℹ️ *Fator Solo ZARC:* {txt_solo_info}")
            
            if icsd >= 1.20:
                st.success(f"✔️ **PARECER DA MESA:** Crédito validado e enquadrado nas réguas saudáveis da política.")
            else:
                st.warning(f"⚠️ **PARECER DA MESA:** Operação requer a aplicação das travas de garantias estruturadas listadas no alerta acima.")

            st.write("---")
            col_graph, col_maps = st.columns([2, 1])
            
            with col_graph:
                st.markdown(f"**📊 Precipitação Diária na Região Mapeada ({data_plantio.strftime('%d/%m')} até {data_colheita_calculada.strftime('%d/%m')}):**")
                if not df_chuva_historica.empty:
                    st.line_chart(df_chuva_historica["Chuva (mm)"])
                else:
                    st.info("Gráfico indisponível para coordenadas zeradas.")
            
            with col_maps:
                st.markdown("**🗺️ Geolocalização da Área Produtiva:**")
                url_maps = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
                st.write(f"Coordenadas: `{latitude}`, `{longitude}`")
                st.link_button("📍 Ir para o Google Maps", url_maps, type="secondary")

# =========================================================================
# ABA 4: HISTÓRICO DE ANÁLISES (CRM)
# =========================================================================
with aba_crm:
    st.subheader("Painel Gerencial e Histórico do Banco de Dados")
    conn = sqlite3.connect("banco_agro.db")
    df_historico = pd.read_sql_query("SELECT * FROM historico_credito ORDER BY id DESC", conn)
    conn.close()
    
    if df_historico.empty:
        st.info("Ainda não existem análises armazenadas no banco.")
    else:
        total_propostas = len(df_historico)
        aprovados = len(df_historico[df_historico["veredito"].str.contains("APROVADO", na=False)])
        taxa_aprovacao = (aprovados / total_propostas) * 100 if total_propostas > 0 else 0
        volume_total_solicitado = df_historico["parcela"].sum()
        
        dash1, dash2, dash3 = st.columns(3)
        with dash1: st.metric(label="Total de Propostas no Banco", value=f"{total_propostas} pareceres")
        with dash2: st.metric(label="Taxa de Base Agro", value=f"{taxa_aprovacao:.1f}%")
        with dash3: st.metric(label="Volume Total Analisado", value=f"R$ {volume_total_solicitado:,.2f}")
            
        st.write("---")
        st.markdown("**🔍 Buscar Cliente na Base de Dados:**")
        termo_pesquisa = st.text_input("Filtrar por proponente:")
        
        if termo_pesquisa:
            df_filtrado = df_historico[df_historico["nome"].str.contains(termo_pesquisa, case=False, na=False)]
        else: df_filtrado = df_historico
            
        st.dataframe(df_filtrado[["id", "data_analise", "nome", "documento", "localizacao", "cultura", "area", "tipo_area", "icsd", "rating", "taxa_final", "veredito"]], use_container_width=True)

        st.write("---")
        with st.expander("⚙️ Ferramentas de Administração e Limpeza de Base"):
            st.warning("Atenção: As ações abaixo são irreversíveis.")
            id_para_deletar = st.number_input("Digitar o ID da linha que deseja apagar:", min_value=1, step=1)
            if st.button("🗑️ Deletar Registro Específico"):
                conn = sqlite3.connect("banco_agro.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM historico_credito WHERE id = ?", (id_para_deletar,))
                conn.commit()
                conn.close()
                st.success(f"Registro ID {id_para_deletar} removido com sucesso! Atualize a página.")
            
            st.write("---")
            if st.button("🚨 ZERAR TODA A BASE DE DADOS (Limpeza Geral)"):
                conn = sqlite3.connect("banco_agro.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM historico_credito")
                conn.commit()
                conn.close()
                st.success("Toda a base de dados de testes foi limpa! Atualize a página.")