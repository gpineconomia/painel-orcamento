"""Painel de Gestão Orçamentária — Execução 2026 e Planejamento 2027."""
from __future__ import annotations

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from common import inject_css, REFRESH_SECONDS
import oraculo

st.set_page_config(page_title="Gestão Orçamentária", page_icon="📊", layout="wide")
inject_css()
st_autorefresh(interval=REFRESH_SECONDS * 1000, key="auto_refresh")

# ------------------------------------------------------------------ navegação de páginas
page_oraculo = st.Page("paginas/oraculo_ia.py", title="Oráculo (Assistente IA)", icon="🔮")

pages = {
    "Orçamento 2026 (Execução)": [
        st.Page("paginas/execucao_2026.py", title="Despesas por Unidade", icon="🏢", default=True),
        st.Page("paginas/visao_2026.py", title="Visão Analítica", icon="📊"),
        st.Page("paginas/liquidacao_contrato.py", title="Liquidação por Contrato", icon="📜"),
        st.Page("paginas/indicacoes_2026.py", title="Indicações", icon="🎯"),
        st.Page("paginas/contratacoes_2026.py", title="Contratações", icon="📋"),
    ],
    "Orçamento 2027 (Planejamento)": [
        st.Page("paginas/despesas_unidade.py", title="Despesas por Unidade", icon="🏢"),
        st.Page("paginas/visao_analitica.py", title="Visão Analítica", icon="📊"),
        st.Page("paginas/supressoes_2027.py", title="Supressões PLOA", icon="✂️"),
        st.Page("paginas/pca_2027.py", title="PCA 2027 (GELC)", icon="📑"),
    ],
    "Inteligência Analítica": [
        page_oraculo,
    ],
}

pg = st.navigation(pages)

with st.sidebar:
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 Atualizar Painel", use_container_width=True, help="Baixa as alterações mais recentes do SharePoint/SIAFIC e recarrega os dados"):
        with st.spinner("Sincronizando todas as bases de dados..."):
            from common import executar_atualizacao_geral
            executar_atualizacao_geral()

# Botão flutuante do Oráculo em todas as páginas de dashboard
if pg != page_oraculo:
    oraculo.inject_floating_oraculo()

pg.run()

