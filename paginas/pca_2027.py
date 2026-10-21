"""Página: PCA 2027 por Superintendência — Tabela hierárquica e cards executivos nos moldes de Despesas por Unidade."""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
import pandas as pd
import streamlit as st

import common
from common import brl, num
import pca_data

TZ_BRASILIA = timezone(timedelta(hours=-3))

# ------------------------------------------------------------------ CARREGAMENTO DOS DADOS DO PCA
try:
    df_pca_raw, updated_pca = pca_data.load_pca_data()
except Exception as exc:
    st.error(f"Erro ao carregar os dados do PCA 2027: {exc}")
    st.stop()

if df_pca_raw.empty:
    st.warning("Nenhum dado encontrado na aba 'PCA 2027' da planilha compartilhada do Google Drive.")
    st.stop()


def fmt_br(v: float) -> str:
    """Formata valor em padrão brasileiro ABNT 2."""
    if v is None or pd.isna(v):
        return "0,00"
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------ BANNER SUPERIOR
dt_pca_str = updated_pca.strftime("%d/%m/%Y às %H:%M") if updated_pca else "N/D"

st.html(
    f"""<div style="background:#0A6B56; border-radius:12px; padding:12px 24px; margin-bottom:1.2rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 14px rgba(10,107,86,0.18);">
      <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
        Plano de Contratações Anual (PCA) 2027
      </h2>
      <div style="text-align:right;">
        <div style="font-size:0.85rem; color:#A7F3D0; font-weight:600;">Secretaria da Economia · GELC</div>
        <div style="font-size:0.75rem; color:#D1FAE5; opacity:0.85; margin-top:2px;">● Atualizado em {dt_pca_str}</div>
      </div>
    </div>"""
)

# ------------------------------------------------------------------ FILTROS NA BARRA LATERAL
with st.sidebar:
    st.header("Filtros · PCA 2027")

    if st.button("🔄 Atualizar dados do PCA", width="stretch", key="btn_refresh_pca_unidade"):
        with st.spinner("Conectando ao Google Drive e baixando versão mais recente..."):
            pca_data.download_pca_workbook()
            st.cache_data.clear()
            st.rerun()

    busca = st.text_input("🔎 Buscar (Objeto, Processo SEI, Contrato, Unidade)", key="f_pca_u_busca")

    # 1. Superintendência / Unidade Superior
    opts_sup = sorted([s for s in df_pca_raw["Unidade_Superior"].dropna().unique() if str(s).strip() != ""])
    sel_sup = st.multiselect("Superintendência / Unidade Superior", opts_sup, key="f_pca_u_sup")

    # 2. Unidade Demandante (Gerência)
    opts_uni = sorted([u for u in df_pca_raw["Unidade_Demandante"].dropna().unique() if str(u).strip() != ""])
    sel_uni = st.multiselect("Unidade Demandante (Gerência)", opts_uni, key="f_pca_u_uni")

    # 3. Providência em 2027
    opts_prov = sorted([p for p in df_pca_raw["Providencia_2027"].dropna().unique() if str(p).strip() != ""])
    sel_prov = st.multiselect("Qual providência em 2027?", opts_prov, key="f_pca_u_prov")

    # 4. Status da Contratação
    opts_status = sorted([s for s in df_pca_raw["Status_Contratacao"].dropna().unique() if str(s).strip() != ""])
    sel_status = st.multiselect("Status da Contratação", opts_status, key="f_pca_u_status")

    # 5. Modalidade
    opts_mod = sorted([m for m in df_pca_raw["Modalidade"].dropna().unique() if str(m).strip() != ""])
    sel_mod = st.multiselect("Modalidade de Contratação", opts_mod, key="f_pca_u_mod")

    # 6. Possui Contrato Vigente?
    tipo_contrato = st.radio(
        "Contrato Vigente:",
        ["Todos", "Com Contrato Vigente", "Sem Contrato (Novas Demandas)"],
        key="f_pca_u_contrato_radio"
    )

# ------------------------------------------------------------------ APLICAÇÃO DOS FILTROS
df_view = df_pca_raw.copy()

if sel_sup:
    df_view = df_view[df_view["Unidade_Superior"].isin(sel_sup)]
if sel_uni:
    df_view = df_view[df_view["Unidade_Demandante"].isin(sel_uni)]
if sel_prov:
    df_view = df_view[df_view["Providencia_2027"].isin(sel_prov)]
if sel_status:
    df_view = df_view[df_view["Status_Contratacao"].isin(sel_status)]
if sel_mod:
    df_view = df_view[df_view["Modalidade"].isin(sel_mod)]

if tipo_contrato == "Com Contrato Vigente":
    df_view = df_view[df_view["Tem_Contrato_Vigente"]]
elif tipo_contrato == "Sem Contrato (Novas Demandas)":
    df_view = df_view[~df_view["Tem_Contrato_Vigente"]]

if busca:
    b_norm = busca.strip().lower()
    m_busca = (
        df_view["Objeto_Resumido"].astype(str).str.lower().str.contains(b_norm, na=False) |
        df_view["Detalhamento_Objeto"].astype(str).str.lower().str.contains(b_norm, na=False) |
        df_view["Processo_SEI"].astype(str).str.lower().str.contains(b_norm, na=False) |
        df_view["Contrato_Vigente"].astype(str).str.lower().str.contains(b_norm, na=False) |
        df_view["Unidade_Demandante"].astype(str).str.lower().str.contains(b_norm, na=False) |
        df_view["Unidade_Superior"].astype(str).str.lower().str.contains(b_norm, na=False)
    )
    df_view = df_view[m_busca]

# ------------------------------------------------------------------ TOTAIS GERAIS
tot_geral_2027 = float(df_view["Valor_Estimado_2027"].sum())
tot_geral_contratacao = float(df_view["Valor_Total_Estimado"].sum())

mask_novas = df_view["Providencia_2027"].astype(str).str.upper().str.contains("NOVA", na=False)
tot_novas = float(df_view[mask_novas]["Valor_Estimado_2027"].sum())
qtd_novas = int(mask_novas.sum())

mask_prorr = df_view["Providencia_2027"].astype(str).str.upper().str.contains("PRORROG", na=False)
tot_prorr = float(df_view[mask_prorr]["Valor_Estimado_2027"].sum())
qtd_prorr = int(mask_prorr.sum())

mask_sem = df_view["Providencia_2027"].astype(str).str.upper().str.contains("SEM PROVID", na=False)
tot_sem = float(df_view[mask_sem]["Valor_Estimado_2027"].sum())
qtd_sem = int(mask_sem.sum())

# ------------------------------------------------------------------ CARDS NO TOPO
c1, c2, c3, c4 = st.columns(4)
card_base_style = "border-radius:14px; padding:18px 22px; color:#FFFFFF; text-align:left; transition: transform 0.15s ease;"

with c1:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #064E3B 0%, #022C22 100%);
                    box-shadow: 0 6px 18px rgba(6,78,59,0.32), inset 0 1px 0 rgba(255,255,255,0.25);
                    border: 1.5px solid rgba(52,211,153,0.45); {card_base_style}">
          <div style="font-size:2.0rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_geral_2027, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#6EE7B7; margin-top:8px; font-weight:700;">
            Estimado PCA 2027
          </div>
          <div style="font-size:0.74rem; color:#A7F3D0; margin-top:3px;">
            {len(df_view)} demandas mapeadas
          </div>
        </div>"""
    )

with c2:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #B45309 0%, #78350F 100%);
                    box-shadow: 0 4px 14px rgba(180,83,9,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:2.0rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_novas, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#FDE68A; margin-top:8px; font-weight:700;">
            Novas Contratações 2027
          </div>
          <div style="font-size:0.74rem; color:#FEF3C7; margin-top:3px;">
            {qtd_novas} processos a licitar
          </div>
        </div>"""
    )

with c3:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #1D4ED8 0%, #1E3A8A 100%);
                    box-shadow: 0 4px 14px rgba(29,78,216,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:2.0rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_prorr, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#BFDBFE; margin-top:8px; font-weight:700;">
            Prorrogações 2027
          </div>
          <div style="font-size:0.74rem; color:#DBEAFE; margin-top:3px;">
            {qtd_prorr} aditivos contratuais
          </div>
        </div>"""
    )

with c4:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #0F766E 0%, #115E59 100%);
                    box-shadow: 0 4px 14px rgba(15,118,110,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:2.0rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_sem, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#99F6E4; margin-top:8px; font-weight:700;">
            Sem Providências
          </div>
          <div style="font-size:0.74rem; color:#CCFBF1; margin-top:3px;">
            {qtd_sem} contratos em vigência normal
          </div>
        </div>"""
    )

st.write("")

# ------------------------------------------------------------------ CONTROLES DE ORDENAÇÃO
ctrl_col1, ctrl_col2, _ = st.columns([1.8, 1.3, 3])

with ctrl_col1:
    sort_col = st.selectbox(
        "Ordenar dados por:",
        ["Estimado para 2027", "Valor Total Contratação", "Superintendência / Unidade Superior"],
        index=0,
        key="sort_col_pca_u",
    )

with ctrl_col2:
    sort_dir = st.selectbox(
        "Direção:",
        ["Decrescente (Maior ➔ Menor)", "Crescente (Menor ➔ Maior)"],
        index=0,
        key="sort_dir_pca_u",
    )

# Configurações de colunas da tabela hierárquica
COL_CONFIGS = {
    "Estimado para 2027": {
        "key": "Valor_Estimado_2027",
        "header": "Estimado 2027",
        "width": 170,
        "format": lambda val, is_footer: fmt_br(val),
        "color": lambda val, is_footer: "#FFFFFF" if is_footer else "#0A6B56",
    },
    "Valor Total Contratação": {
        "key": "Valor_Total_Estimado",
        "header": "Valor Total Contratação",
        "width": 190,
        "format": lambda val, is_footer: fmt_br(val),
        "color": lambda val, is_footer: "#FFFFFF" if is_footer else "#475569",
    },
}

cols_ativas = ["Estimado para 2027", "Valor Total Contratação"]


def render_valores(val_map: dict[str, float], font_size: str, peso: str = "700", is_footer: bool = False, custom_colors: dict | None = None) -> str:
    spans = []
    for c in cols_ativas:
        cfg = COL_CONFIGS[c]
        val = val_map.get(cfg["key"], 0.0)
        txt = cfg["format"](val, is_footer)
        cor = custom_colors.get(c) if custom_colors and c in custom_colors else cfg["color"](val, is_footer)
        spans.append(f'<span style="width:{cfg["width"]}px; color:{cor};">{txt}</span>')
    return (
        f'<div style="display:flex; gap:16px; align-items:center; font-variant-numeric:tabular-nums; '
        f'font-size:{font_size}; font-weight:{peso}; text-align:right;">'
        f'{"".join(spans)}'
        f'</div>'
    )


# ------------------------------------------------------------------ ESTADO DE EXPANSÃO (CONTROLE INFERIOR)
expandir_tudo = st.session_state.get("expandir_todas_pca_u", False)
open_attr = "open" if expandir_tudo else ""

# ------------------------------------------------------------------ APLICAÇÃO DA ORDENAÇÃO
is_descending = sort_dir.startswith("Decrescente")
col_sort_map = {
    "Estimado para 2027": "Valor_Estimado_2027",
    "Valor Total Contratação": "Valor_Total_Estimado",
}
sort_k = col_sort_map.get(sort_col, "Valor_Estimado_2027")

if sort_col == "Superintendência / Unidade Superior":
    ordem_superintendencias = df_view.groupby("Unidade_Superior")["Valor_Estimado_2027"].sum().sort_index(ascending=not is_descending)
else:
    ordem_superintendencias = df_view.groupby("Unidade_Superior")[sort_k].sum().sort_values(ascending=not is_descending)

linhas_html = []
for idx, (sup_nome, total_sup) in enumerate(ordem_superintendencias.items()):
    bg_row = "#F6FAF8" if idx % 2 == 1 else "#FFFFFF"
    sub_df = df_view[df_view["Unidade_Superior"] == sup_nome].copy()

    s_est_2027 = float(sub_df["Valor_Estimado_2027"].sum())
    s_total_est = float(sub_df["Valor_Total_Estimado"].sum())
    val_map_sup = {"Valor_Estimado_2027": s_est_2027, "Valor_Total_Estimado": s_total_est}

    # Ordena as demandas dentro da Superintendência
    if sort_col == "Superintendência / Unidade Superior":
        sub_df = sub_df.sort_values(by="Objeto_Resumido", ascending=not is_descending)
    else:
        sub_df = sub_df.sort_values(by=sort_k, ascending=not is_descending)

    itens_html = []
    for _, row in sub_df.iterrows():
        r_est_2027 = float(row["Valor_Estimado_2027"])
        r_total_est = float(row["Valor_Total_Estimado"])
        val_map_r = {"Valor_Estimado_2027": r_est_2027, "Valor_Total_Estimado": r_total_est}

        valores_item = render_valores(val_map_r, font_size="0.86rem", peso="600")

        # Tags do Item
        tags = []

        # Tag da Gerência Demandante (em destaque)
        if row["Unidade_Demandante"]:
            tags.append(
                f'<span style="background:#E0F2FE; color:#0369A1; font-size:0.75rem; '
                f'font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid #BAE6FD;">'
                f'📍 {row["Unidade_Demandante"]}</span>'
            )

        # Contrato Vigente
        if row["Tem_Contrato_Vigente"]:
            tags.append(
                f'<span style="background:#F1F5F9; color:#1E293B; font-size:0.75rem; '
                f'font-weight:700; padding:2px 7px; border-radius:4px; border:1px solid #CBD5E1; '
                f'font-variant-numeric:tabular-nums;">Contrato: {row["Contrato_Vigente"]}</span>'
            )
        else:
            tags.append(
                f'<span style="background:#F8FAFC; color:#64748B; font-size:0.73rem; '
                f'font-weight:600; padding:2px 6px; border-radius:4px; border:1px dashed #CBD5E1;">'
                f'Sem Contrato</span>'
            )

        # Processo SEI
        if row["Processo_SEI"]:
            tags.append(
                f'<span style="background:#EBF5F0; color:#0A6B56; font-size:0.75rem; '
                f'font-weight:600; padding:2px 7px; border-radius:4px; border:1px solid #CDE5DA; '
                f'font-variant-numeric:tabular-nums;">SEI {row["Processo_SEI"]}</span>'
            )

        # Providência 2027
        prov = str(row["Providencia_2027"]).upper()
        if "NOVA" in prov:
            tags.append(
                f'<span style="background:#FEF3C7; color:#B45309; font-size:0.74rem; '
                f'font-weight:700; padding:2px 7px; border-radius:4px; border:1px solid #FCD34D;">'
                f'Nova Contratação</span>'
            )
        elif "PRORROG" in prov:
            tags.append(
                f'<span style="background:#EFF6FF; color:#1D4ED8; font-size:0.74rem; '
                f'font-weight:700; padding:2px 7px; border-radius:4px; border:1px solid #BFDBFE;">'
                f'Prorrogar</span>'
            )
        elif "NÃO CONTRATAR" in prov:
            tags.append(
                f'<span style="background:#F3F4F6; color:#4B5563; font-size:0.74rem; '
                f'font-weight:600; padding:2px 7px; border-radius:4px; border:1px solid #D1D5DB;">'
                f'Não Contratar</span>'
            )
        else:
            tags.append(
                f'<span style="background:#ECFDF5; color:#047857; font-size:0.74rem; '
                f'font-weight:600; padding:2px 7px; border-radius:4px; border:1px solid #A7F3D0;">'
                f'Sem Providências</span>'
            )

        # Status
        st_txt = str(row["Status_Contratacao"]).upper()
        if "ANDAMENTO" in st_txt:
            tags.append(
                f'<span style="background:#EEF2FF; color:#4338CA; font-size:0.73rem; '
                f'font-weight:600; padding:2px 6px; border-radius:4px; border:1px solid #C7D2FE;">'
                f'Em Andamento</span>'
            )
        elif "PLANEJADO" in st_txt:
            tags.append(
                f'<span style="background:#FDF4FF; color:#86198F; font-size:0.73rem; '
                f'font-weight:600; padding:2px 6px; border-radius:4px; border:1px solid #F5D0FE;">'
                f'Planejado</span>'
            )

        # Deadline
        if pd.notna(row["Deadline_Contratacao"]):
            dt_d_str = row["Deadline_Contratacao"].strftime("%d/%m/%Y")
            tags.append(
                f'<span style="background:#FFFBEB; color:#92400E; font-size:0.73rem; '
                f'font-weight:600; padding:2px 6px; border-radius:4px; border:1px solid #FDE68A;">'
                f'Deadline: {dt_d_str}</span>'
            )

        # Modalidade
        if row["Modalidade"] and row["Modalidade"] != "-":
            tags.append(
                f'<span style="background:#F8FAFC; color:#475569; font-size:0.72rem; '
                f'padding:2px 6px; border-radius:4px; border:1px solid #E2E8F0;">'
                f'{row["Modalidade"]}</span>'
            )

        detalhe_extra = ""
        if row["Detalhamento_Objeto"]:
            detalhe_extra = (
                f'<div style="font-size:0.80rem; color:#475569; margin-top:6px; line-height:1.45; '
                f'background:#F1F5F9; padding:8px 12px; border-radius:6px; border-left:3px solid #0A6B56;">'
                f'<strong>Detalhamento:</strong> {row["Detalhamento_Objeto"]}'
                f'</div>'
            )

        item_label = f"Item {int(row['Item'])}" if pd.notna(row['Item']) else "Item -"
        itens_html.append(
            f'<div style="padding:10px 20px 10px 42px; border-bottom:1px dashed #E1EEE7; background:#FBFDFD;">'
            f'<div style="display:flex; justify-content:space-between; align-items:flex-start;">'
            f'<div style="flex:1; padding-right:16px;">'
            f'<div style="font-size:0.90rem; font-weight:600; color:#0F2A20;">'
            f'<span style="color:#059669; margin-right:6px; font-size:0.75rem;">▪</span>'
            f'{item_label}: {row["Objeto_Resumido"]}'
            f'</div>'
            f'<div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; align-items:center;">'
            f'{"".join(tags)}'
            f'</div>'
            f'{detalhe_extra}'
            f'</div>'
            f'<div style="align-self:center;">{valores_item}</div>'
            f'</div>'
            f'</div>'
        )

    # Badges da Superintendência no resumo
    qtd_s_itens = len(sub_df)
    qtd_s_gerencias = sub_df["Unidade_Demandante"].nunique()
    qtd_s_novas = len(sub_df[sub_df["Providencia_2027"].str.upper().str.contains("NOVA", na=False)])
    qtd_s_prorr = len(sub_df[sub_df["Providencia_2027"].str.upper().str.contains("PRORROG", na=False)])

    resumo_s_badges = [
        f'<span style="font-size:0.74rem; color:#5B7A6C; background:#EEF6F2; padding:2px 7px; '
        f'border-radius:999px; font-weight:600; margin-left:8px;">{qtd_s_itens} demandas ({qtd_s_gerencias} gerências)</span>'
    ]
    if qtd_s_novas > 0:
        resumo_s_badges.append(
            f'<span style="font-size:0.72rem; color:#B45309; background:#FEF3C7; padding:2px 6px; '
            f'border-radius:4px; font-weight:700; margin-left:4px;">{qtd_s_novas} novas</span>'
        )
    if qtd_s_prorr > 0:
        resumo_s_badges.append(
            f'<span style="font-size:0.72rem; color:#1D4ED8; background:#EFF6FF; padding:2px 6px; '
            f'border-radius:4px; font-weight:700; margin-left:4px;">{qtd_s_prorr} prorrogações</span>'
        )

    valores_sup = render_valores(val_map_sup, font_size="0.95rem", peso="700",
                                custom_colors={"Estimado para 2027": "#0A6B56", "Valor Total Contratação": "#1E293B"})

    linhas_html.append(
        f'<details {open_attr} style="border-bottom:1px solid #DCEBE3;">'
        f'<summary style="display:flex; justify-content:space-between; align-items:center; '
        f'padding:11px 20px; font-weight:600; color:#0F2A20; cursor:pointer; '
        f'background:{bg_row}; list-style:none; user-select:none; transition: background 0.15s ease;">'
        f'<span style="flex:1; display:flex; align-items:center; padding-right:12px;">'
        f'<span style="display:inline-block; width:18px; height:18px; line-height:16px; '
        f'text-align:center; border:1px solid #0A6B56; border-radius:4px; margin-right:10px; '
        f'font-size:0.8rem; color:#0A6B56; font-weight:bold;">+</span>'
        f'{sup_nome}'
        f'{"".join(resumo_s_badges)}</span>'
        f'{valores_sup}'
        f'</summary>'
        f'<div style="background:#FAFCFB;">{"".join(itens_html)}</div>'
        f'</details>'
    )

val_map_tot = {"Valor_Estimado_2027": tot_geral_2027, "Valor_Total_Estimado": tot_geral_contratacao}
valores_total = render_valores(val_map_tot, font_size="1.05rem", peso="800", is_footer=True)

# Indicador visual no cabeçalho
arrow = "▼" if is_descending else "▲"
header_spans = []
for c in cols_ativas:
    cfg = COL_CONFIGS[c]
    indicator = f" {arrow}" if sort_col == c else ""
    header_spans.append(f'<span style="width:{cfg["width"]}px;">{cfg["header"]}{indicator}</span>')

sup_indicator = f" {arrow}" if sort_col == "Superintendência / Unidade Superior" else ""

tabela_completa = (
    f'<div class="notranslate" translate="no" style="border:1.5px solid #0A6B56; border-radius:14px; overflow-x:auto; '
    f'box-shadow:0 4px 18px rgba(10,107,86,0.08); background:#FFFFFF; margin-top:0.5rem; margin-bottom:1rem;">'
    f'<div style="background:#0A6B56; color:#FFFFFF; padding:12px 20px; font-weight:700; '
    f'font-size:0.92rem; display:flex; justify-content:space-between; align-items:center; letter-spacing:0.02em;">'
    f'<span style="flex:1;">Superintendência / Unidade Superior{sup_indicator}</span>'
    f'<div style="display:flex; gap:16px; align-items:center; text-align:right;">'
    f'{"".join(header_spans)}'
    f'</div>'
    f'</div>'
    f'<div>{"".join(linhas_html)}</div>'
    f'<div style="background:#0A6B56; color:#FFFFFF; padding:13px 20px; font-weight:800; '
    f'font-size:1.05rem; display:flex; justify-content:space-between; align-items:center;">'
    f'<span style="flex:1;">Total Geral ({len(df_view)} demandas)</span>'
    f'{valores_total}'
    f'</div>'
    f'</div>'
)

st.html(tabela_completa)

# ------------------------------------------------------------------ CONTROLE DE EXPANSÃO (EMBAIXO DA TABELA)
st.checkbox("Expandir todas as superintendências", key="expandir_todas_pca_u")

# ------------------------------------------------------------------ DOWNLOADS
col_d1, col_d2, _ = st.columns([1, 1, 3])

with col_d1:
    buffer_csv = io.StringIO()
    df_view.to_csv(buffer_csv, index=False, sep=";", encoding="utf-8-sig")
    st.download_button(
        label="📥 Baixar Tabela em CSV",
        data=buffer_csv.getvalue().encode("utf-8-sig"),
        file_name=f"PCA_2027_Superintendencias_{datetime.now():%Y%m%d}.csv",
        mime="text/csv",
        use_container_width=True,
    )

with col_d2:
    buffer_xlsx = io.BytesIO()
    with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
        df_view.to_excel(writer, index=False, sheet_name="PCA 2027")
    st.download_button(
        label="📊 Baixar Tabela em Excel",
        data=buffer_xlsx.getvalue(),
        file_name=f"PCA_2027_Superintendencias_{datetime.now():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
