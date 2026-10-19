"""Painel de Gestão Orçamentária — Execução 2026 e Planejamento 2027."""
from __future__ import annotations

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from common import inject_css, REFRESH_SECONDS

st.set_page_config(page_title="Gestão Orçamentária", page_icon="📊", layout="wide")
inject_css()
st_autorefresh(interval=REFRESH_SECONDS * 1000, key="auto_refresh")

# ------------------------------------------------------------------ navegação de páginas
pages = {
    "Orçamento 2026 (Execução)": [
        st.Page("paginas/execucao_2026.py", title="Despesas por Unidade", icon="🏢", default=True),
        st.Page("paginas/visao_2026.py", title="Visão Analítica", icon="📊"),
    ],
    "Orçamento 2027 (Planejamento)": [
        st.Page("paginas/despesas_unidade.py", title="Despesas por Unidade", icon="🏢"),
        st.Page("paginas/visao_analitica.py", title="Visão Analítica", icon="📊"),
        st.Page("paginas/supressoes_2027.py", title="Supressões", icon="✂️"),
    ],
}

pg = st.navigation(pages)
pg.run()
