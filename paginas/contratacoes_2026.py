"""Página: Acompanhamento das Contratações 2026."""
from __future__ import annotations

import streamlit as st
import contratacoes_data

with st.sidebar:
    st.markdown("### 🔄 Atualização")
    if st.button("🔄 Atualizar Contratações", use_container_width=True, help="Força a atualização imediata da planilha"):
        contratacoes_data.clear_contratacoes_cache()
        st.cache_data.clear()
        st.success("Cache limpo! Recarregando...")
        st.rerun()

contratacoes_data.render_contratacoes_dashboard(key_prefix="page_")
