"""Página Streamlit para visualização da Apresentação Executiva da Alta Gestão."""
from __future__ import annotations

from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

BASE_DIR = Path(__file__).parent.parent
HTML_PATH = BASE_DIR / "apresentacao_alta_gestao.html"

st.set_page_config(page_title="Apresentação Alta Gestão", page_icon="📊", layout="wide")

if not HTML_PATH.exists():
    # Tenta buscar no diretório brain
    brain_path = Path(r"C:\Users\joao.veronez\.gemini\antigravity\brain\1c42b43d-4384-4107-b309-7bf1a885bf28\apresentacao_alta_gestao.html")
    if brain_path.exists():
        html_content = brain_path.read_text(encoding="utf-8")
    else:
        st.error("Arquivo da apresentação não encontrado.")
        st.stop()
else:
    html_content = HTML_PATH.read_text(encoding="utf-8")

# Botões de utilidade no Streamlit
col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    st.caption("Apresentação interativa adaptada para computadores, tablets e smartphones (com suporte a toque/swipe).")
with col_t2:
    st.download_button(
        label="📥 Baixar Apresentação (HTML)",
        data=html_content,
        file_name="apresentacao_alta_gestao_economia_go.html",
        mime="text/html",
        use_container_width=True
    )

# Renderiza o HTML com altura dinâmica
components.html(html_content, height=920, scrolling=True)
