"""Página Streamlit para visualização da Apresentação Executiva da Alta Gestão."""
from __future__ import annotations

from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

BASE_DIR = Path(__file__).parent.parent

# Seletor de Versão da Apresentação
col_sel, col_info = st.columns([1, 2])
with col_sel:
    versao = st.segmented_control(
        "Selecione a Versão",
        options=["Versão 2 (Atualizada)", "Versão 1 (Original)"],
        default="Versão 2 (Atualizada)",
        key="versao_apresentacao"
    )

if versao == "Versão 1 (Original)":
    html_file = BASE_DIR / "apresentacao_alta_gestao_v1.html"
    if not html_file.exists():
        html_file = Path(r"C:\Users\joao.veronez\.gemini\antigravity\brain\1c42b43d-4384-4107-b309-7bf1a885bf28\apresentacao_alta_gestao_v1.html")
    download_name = "apresentacao_alta_gestao_v1_deficit_47_45M.html"
    metric_label = "V1 (Base): Déficit R$ 47,45 Mi • Piso Essencial R$ 191,54 Mi • Serviços Gerais R$ 5,58 Mi"
else:
    html_file = BASE_DIR / "apresentacao_alta_gestao_v2.html"
    if not html_file.exists():
        html_file = Path(r"C:\Users\joao.veronez\.gemini\antigravity\brain\1c42b43d-4384-4107-b309-7bf1a885bf28\apresentacao_alta_gestao_v2.html")
    download_name = "apresentacao_alta_gestao_v2_deficit_45_26M.html"
    metric_label = "V2 (Atualizada): Déficit R$ 45,26 Mi • Piso Essencial R$ 189,35 Mi • Serviços Gerais R$ 3,39 Mi"

if not html_file.exists():
    html_file = BASE_DIR / "apresentacao_alta_gestao.html"

html_content = html_file.read_text(encoding="utf-8")

with col_info:
    st.markdown(
        f"""<div style='margin-top: 24px; font-size: 13px; font-weight: 700; color: #047857; 
                       background: #ECFDF5; padding: 6px 14px; border-radius: 8px; 
                       border: 1px solid #A7F3D0; display: inline-block;'>
             ● {metric_label}
           </div>""",
        unsafe_allow_html=True
    )

# Botões de utilidade no Streamlit
col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    st.caption("Apresentação interativa com 13 slides adaptada para computadores, tablets e smartphones (com suporte a toque/swipe).")
with col_t2:
    st.download_button(
        label=f"📥 Baixar {versao} (HTML)",
        data=html_content,
        file_name=download_name,
        mime="text/html",
        use_container_width=True
    )

# Renderiza o HTML com altura dinâmica
components.html(html_content, height=920, scrolling=True)
