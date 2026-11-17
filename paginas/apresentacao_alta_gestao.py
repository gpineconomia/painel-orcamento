"""Página Streamlit para visualização da Apresentação Executiva da Alta Gestão."""
from __future__ import annotations

from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

BASE_DIR = Path(__file__).parent.parent
BRAIN_DIR = Path(r"C:\Users\joao.veronez\.gemini\antigravity\brain\1c42b43d-4384-4107-b309-7bf1a885bf28")

# Seletor de Versão da Apresentação
col_sel, col_info = st.columns([1.35, 1.65])
with col_sel:
    versao = st.segmented_control(
        "Selecione a Versão",
        options=["Versão 6 (17/11)", "Versão 5 (16/11)", "Versão 4 (11/11)", "Versão 3 (06/11)", "Versão 2 (05/11)", "Versão 1 (04/11)"],
        default="Versão 6 (17/11)",
        key="versao_apresentacao"
    )

if versao == "Versão 1 (04/11)":
    html_file = BASE_DIR / "apresentacao_alta_gestao_v1.html"
    if not html_file.exists():
        html_file = BRAIN_DIR / "apresentacao_alta_gestao_v1.html"
    download_name = "apresentacao_alta_gestao_v1_04_11.html"
    metric_label = "V1 (04/11/2026): Déficit R$ 47,45 Mi • Piso Essencial R$ 191,54 Mi • 19 Demandas"
elif versao == "Versão 2 (05/11)":
    html_file = BASE_DIR / "apresentacao_alta_gestao_v2.html"
    if not html_file.exists():
        html_file = BRAIN_DIR / "apresentacao_alta_gestao_v2.html"
    download_name = "apresentacao_alta_gestao_v2_05_11.html"
    metric_label = "V2 (05/11/2026): Déficit R$ 45,26 Mi • Piso Essencial R$ 189,35 Mi • Serviços Gerais R$ 3,39 Mi"
elif versao == "Versão 3 (06/11)":
    html_file = BASE_DIR / "apresentacao_alta_gestao_v3.html"
    if not html_file.exists():
        html_file = BRAIN_DIR / "apresentacao_alta_gestao_v3.html"
    download_name = "apresentacao_alta_gestao_v3_06_11.html"
    metric_label = "V3 (06/11/2026): Déficit R$ 44,54 Mi • Piso Essencial R$ 188,63 Mi • 18 Demandas"
elif versao == "Versão 4 (11/11)":
    html_file = BASE_DIR / "apresentacao_alta_gestao_v4.html"
    if not html_file.exists():
        html_file = BRAIN_DIR / "apresentacao_alta_gestao_v4.html"
    download_name = "apresentacao_alta_gestao_v4_11_11.html"
    metric_label = "V4 (11/11/2026): Déficit R$ 43,66 Mi • Piso Essencial R$ 187,75 Mi • 18 Demandas (Serviços Gerais R$ 2,51 Mi)"
elif versao == "Versão 5 (16/11)":
    html_file = BASE_DIR / "apresentacao_alta_gestao_v5.html"
    if not html_file.exists():
        html_file = BRAIN_DIR / "apresentacao_alta_gestao_v5.html"
    download_name = "apresentacao_alta_gestao_v5_16_11.html"
    metric_label = "V5 (16/11/2026): Déficit R$ 42,57 Mi • Piso Essencial R$ 186,66 Mi • 18 Demandas (Serviços Gerais R$ 1,43 Mi)"
else:
    html_file = BASE_DIR / "apresentacao_alta_gestao_v6.html"
    if not html_file.exists():
        html_file = BRAIN_DIR / "apresentacao_alta_gestao_v6.html"
    download_name = "apresentacao_alta_gestao_v6_17_11.html"
    metric_label = "V6 (17/11/2026): Déficit R$ 42,46 Mi • Piso Essencial R$ 186,54 Mi • 18 Demandas (Comando Volante R$ 221,5 mil • SAP R$ 175,7 mil)"

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
