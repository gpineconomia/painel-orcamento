"""Página: Acompanhamento das Contratações 2026."""
from __future__ import annotations

import streamlit as st
import contratacoes_data

# Cabeçalho da página
st.markdown(
    """
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.2rem;">
        <div>
            <h1 style="margin: 0; padding: 0; font-size: 2.1rem; color: #1E293B;">📋 Contratações 2026</h1>
            <p style="margin: 0.3rem 0 0 0; color: #64748B; font-size: 1.05rem;">
                Painel Estratégico de Gestão de Demandas, Aquisições e Processos Licitatórios
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 🔄 Atualização")
    if st.button("🔄 Atualizar Contratações", use_container_width=True, help="Força a atualização imediata da planilha"):
        contratacoes_data.clear_contratacoes_cache()
        st.cache_data.clear()
        st.success("Cache limpo! Recarregando...")
        st.rerun()

contratacoes_data.render_contratacoes_dashboard(key_prefix="page_")
