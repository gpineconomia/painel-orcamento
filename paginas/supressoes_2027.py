"""Página: Supressões 2027 — Análise e consulta de cortes e adequações ao teto da PLOA 2027."""
from __future__ import annotations

import io
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import brl, num, style

try:
    from common import get_supressoes_data
except ImportError:
    from data_source import load_supressoes_2027 as get_supressoes_data

# ------------------------------------------------------------------ CARREGAMENTO DOS DADOS
try:
    df_raw, updated_at, warning = get_supressoes_data()
except Exception as exc:  # noqa: BLE001
    st.error(f"Falha ao carregar as informações de Supressões 2027: {exc}")
    st.stop()

if df_raw.empty:
    st.info("Nenhum registro de supressão encontrado na planilha.")
    st.stop()

# ------------------------------------------------------------------ BANNER SUPERIOR
st.html(
    f"""<div style="background:#0A6B56; border-radius:12px; padding:12px 24px; margin-bottom:1.2rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 14px rgba(10,107,86,0.18);">
      <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
        Supressões PLOA · Planejamento 2027
      </h2>
      <div style="text-align:right;">
        <div style="font-size:0.85rem; color:#A7F3D0; font-weight:600;">Secretaria de Estado da Economia · GPIN</div>
        <div style="font-size:0.75rem; color:#D1FAE5; opacity:0.85; margin-top:2px;">● Atualizado em {updated_at:%d/%m/%Y %H:%M}</div>
      </div>
    </div>"""
)
if warning:
    st.warning(warning)

# ------------------------------------------------------------------ FILTROS NA BARRA LATERAL
filtros_aplicados: list[str] = []
df = df_raw.copy()

with st.sidebar:
    st.header("Filtros · Supressões PLOA")
    if st.button("🔄 Atualizar agora", width="stretch", key="btn_refresh_sup"):
        st.cache_data.clear()
        st.rerun()

    busca = st.text_input("🔎 Buscar (item, contrato, ação sugerida)", key="busca_sup")
    if busca:
        mask = (
            df["Item de Despesa"].astype(str).str.contains(busca, case=False, na=False)
            | df["Ação Sugerida"].astype(str).str.contains(busca, case=False, na=False)
            | df["Unidade"].astype(str).str.contains(busca, case=False, na=False)
        )
        df = df[mask]
        filtros_aplicados.append(f"Busca: “{busca}”")

    unidades_disponiveis = sorted(df["Unidade"].unique().tolist())
    sel_unidades = st.multiselect("Unidade", unidades_disponiveis, default=unidades_disponiveis, key="f_sup_unidades")
    if sel_unidades:
        df = df[df["Unidade"].isin(sel_unidades)]
        if len(sel_unidades) < len(unidades_disponiveis):
            filtros_aplicados.append(f"Unidade: {', '.join(sel_unidades)}")

    tipo_corte = st.radio(
        "Tipo de Item",
        ["Todos os Itens", "Apenas com Redução (> 0)", "Sem Redução / Mantidos"],
        index=0,
        key="f_sup_tipo_corte",
    )
    if tipo_corte == "Apenas com Redução (> 0)":
        df = df[df["Economia Gerada"] > 0]
        filtros_aplicados.append("Apenas itens com redução")
    elif tipo_corte == "Sem Redução / Mantidos":
        df = df[df["Economia Gerada"] <= 0]
        filtros_aplicados.append("Itens mantidos")

    st.caption(f"{len(df)} itens selecionados")

if df.empty:
    st.info("Nenhum registro encontrado para os filtros selecionados.")
    st.stop()

# ------------------------------------------------------------------ TOTAIS E MÉTRICAS
tot_orc = float(df["Orçamento 2027"].sum())
tot_teto = float(df["Teto Ajustado 2027"].sum())
tot_econ = float(df["Economia Gerada"].sum())
pct_global = (tot_econ / tot_orc * 100) if tot_orc > 0 else 0.0
qtd_itens = len(df)
qtd_cortados = int((df["Economia Gerada"] > 0).sum())

# ------------------------------------------------------------------ CARDS NO TOPO
c1, c2, c3, c4, c5 = st.columns(5)
card_base_style = "border-radius:14px; padding:16px 18px; color:#FFFFFF; text-align:left; transition: transform 0.15s ease;"

with c1:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #064E3B 0%, #022C22 100%);
                    box-shadow: 0 6px 18px rgba(6,78,59,0.32), inset 0 1px 0 rgba(255,255,255,0.25);
                    border: 1.5px solid rgba(52,211,153,0.45); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_orc, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#6EE7B7; margin-top:8px; font-weight:700;">
            Orçamento 2027 Proposto
          </div>
        </div>"""
    )

with c2:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #0E7490 0%, #155E75 100%);
                    box-shadow: 0 4px 14px rgba(14,116,144,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_teto, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#A5F3FC; margin-top:8px; font-weight:700;">
            Teto Ajustado 2027
          </div>
        </div>"""
    )

with c3:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #BE123C 0%, #9F1239 100%);
                    box-shadow: 0 4px 14px rgba(190,18,60,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_econ, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#FECDD3; margin-top:8px; font-weight:700;">
            Economia Total Gerada
          </div>
        </div>"""
    )

with c4:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #312E81 0%, #1E1B4B 100%);
                    box-shadow: 0 4px 14px rgba(49,46,129,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(165,180,252,0.3); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {pct_global:.1f}%
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#C7D2FE; margin-top:8px; font-weight:700;">
            Índice Global de Supressão
          </div>
        </div>"""
    )

with c5:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
                    box-shadow: 0 4px 14px rgba(30,41,59,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(148,163,184,0.3); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {qtd_cortados} <span style="font-size:1.1rem; font-weight:500; color:#94A3B8;">/ {qtd_itens}</span>
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#94A3B8; margin-top:8px; font-weight:700;">
            Itens Suprimidos / Analisados
          </div>
        </div>"""
    )

st.write("")

# ------------------------------------------------------------------ SEÇÃO ANALÍTICA & GRÁFICOS
tab_graficos, tab_tabela = st.tabs(["📊 Gráficos & Distribuição", "📋 Tabela Detalhada das Supressões"])

with tab_graficos:
    c_g1, c_g2 = st.columns([1.1, 1])

    with c_g1:
        # Comparativo Antes x Depois por Unidade
        df_u = df.groupby("Unidade")[["Orçamento 2027", "Teto Ajustado 2027", "Economia Gerada"]].sum().reset_index()
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(
            name="Orçamento Proposto",
            x=df_u["Unidade"],
            y=df_u["Orçamento 2027"],
            marker_color="#064E3B",
            text=[brl(v, short=True) for v in df_u["Orçamento 2027"]],
            textposition="outside",
        ))
        fig_comp.add_trace(go.Bar(
            name="Teto Ajustado",
            x=df_u["Unidade"],
            y=df_u["Teto Ajustado 2027"],
            marker_color="#0E7490",
            text=[brl(v, short=True) for v in df_u["Teto Ajustado 2027"]],
            textposition="outside",
        ))
        fig_comp.update_layout(
            barmode="group",
            title="Comparativo: Orçamento Proposto vs. Teto Ajustado por Unidade",
            height=420,
        )
        fig_comp = style(fig_comp, height=420)
        st.plotly_chart(fig_comp, width="stretch")

    with c_g2:
        # Donut Chart da Economia Gerada por Unidade
        cores_map = {"SGI": "#047857", "STI": "#2563EB", "RECEITA": "#7C3AED"}
        df_econ_u = df[df["Economia Gerada"] > 0].groupby("Unidade")["Economia Gerada"].sum().reset_index()
        fig_donut = px.pie(
            df_econ_u,
            values="Economia Gerada",
            names="Unidade",
            title="Distribuição da Economia Gerada por Unidade",
            hole=0.45,
            color="Unidade",
            color_discrete_map=cores_map,
        )
        fig_donut.update_traces(
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>Economia: R$ %{value:,.2f}<br>%{percent}<extra></extra>",
        )
        fig_donut = style(fig_donut, height=420)
        st.plotly_chart(fig_donut, width="stretch")

    # Ranking das Maiores Supressões (ordenado decrescente de valor, formato Mi)
    df_top = df[df["Economia Gerada"] > 0].sort_values("Economia Gerada", ascending=False).head(10).copy()
    if not df_top.empty:
        nome_orig = df_top["Item de Despesa"].astype(str).str.strip()
        nome_curto = nome_orig.where(nome_orig.str.len() <= 52, nome_orig.str.slice(0, 51) + "…")
        df_top["Item_Unico"] = nome_curto + nome_curto.groupby(nome_curto).cumcount().map(lambda k: "\u200b" * k)
        df_top["Rotulo_Mi"] = df_top["Economia Gerada"].apply(
            lambda v: f"R$ {v / 1e6:,.2f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        fig_top = px.bar(
            df_top,
            x="Economia Gerada",
            y="Item_Unico",
            color="Unidade",
            orientation="h",
            title="Top 10 Maiores Supressões (Economia Gerada)",
            color_discrete_map=cores_map,
            text="Rotulo_Mi",
            category_orders={"Item_Unico": df_top["Item_Unico"].tolist()},
            custom_data=["Item de Despesa", "Unidade"],
            labels={"Economia Gerada": "Economia (R$)", "Item_Unico": "Item de Despesa"},
        )
        fig_top.update_traces(
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{customdata[0]}</b><br>Unidade: %{customdata[1]}<br>Economia: %{text}<extra></extra>",
            textfont=dict(size=12, color="#0F2A20", family="Inter, Segoe UI, sans-serif"),
        )
        fig_top.update_xaxes(range=[0, df_top["Economia Gerada"].max() * 1.25], showticklabels=False, title=None)
        fig_top.update_yaxes(title=None, tickfont=dict(size=12))
        fig_top = style(fig_top, height=480)
        st.plotly_chart(fig_top, width="stretch")

with tab_tabela:
    st.markdown("#### Detalhamento das Ações e Cortes Propostos")

    # Exibição visual com tabela estilizada
    df_disp = df.copy()
    df_disp["Orçamento 2027 (R$)"] = df_disp["Orçamento 2027"].apply(lambda v: brl(v, short=False))
    df_disp["Teto Ajustado (R$)"] = df_disp["Teto Ajustado 2027"].apply(lambda v: brl(v, short=False))
    df_disp["Economia Gerada (R$)"] = df_disp["Economia Gerada"].apply(lambda v: brl(v, short=False))
    df_disp["% Redução"] = df_disp["% Redução"].apply(lambda v: f"{v:.1f}%")

    col_order = ["Unidade", "Item de Despesa", "Ação Sugerida", "Orçamento 2027 (R$)", "Teto Ajustado (R$)", "Economia Gerada (R$)", "% Redução"]
    st.dataframe(
        df_disp[col_order],
        width="stretch",
        height=520,
        hide_index=True,
    )

    # Botão para download dos dados filtrados
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Supressoes_2027")
    st.download_button(
        label="📥 Baixar Planilha de Supressões (Excel)",
        data=buffer.getvalue(),
        file_name="Supressoes_2027_Filtrado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="btn_dl_sup",
    )
