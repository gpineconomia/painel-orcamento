"""Página: Déficit Orçamentário 2027 — Análise das demandas em rascunho com necessidade de suplementação."""
from __future__ import annotations

import io
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import brl, num, style, PALETTE

try:
    from common import get_deficit_data
except ImportError:
    from data_source import load_deficit_2027 as get_deficit_data

# ------------------------------------------------------------------ CARREGAMENTO DOS DADOS
try:
    df_raw, updated_at, warning = get_deficit_data()
except Exception as exc:  # noqa: BLE001
    st.error(f"Falha ao carregar as informações de Déficit 2027: {exc}")
    st.stop()

if df_raw.empty:
    st.info("Nenhum registro de déficit orçamentário encontrado na planilha.")
    st.stop()

# ------------------------------------------------------------------ BANNER SUPERIOR
st.html(
    f"""<div style="background:#0A6B56; border-radius:12px; padding:12px 24px; margin-bottom:1.2rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 14px rgba(10,107,86,0.18);">
      <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
        Déficit Orçamentário · Planejamento PLOA 2027
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
    st.header("Filtros · Déficit 2027")
    busca = st.text_input("🔎 Buscar despesa", key="busca_def")
    if busca:
        mask = (
            df["Despesa"].astype(str).str.contains(busca, case=False, na=False)
            | df["Unidade"].astype(str).str.contains(busca, case=False, na=False)
            | df["Tipo_Demanda"].astype(str).str.contains(busca, case=False, na=False)
            | df["Prazo"].astype(str).str.contains(busca, case=False, na=False)
        )
        df = df[mask]
        filtros_aplicados.append(f"Busca: “{busca}”")

    # Filtro Unidade
    unidades_disponiveis = sorted(df_raw["Unidade"].unique().tolist())
    sel_unidades = st.multiselect("Unidade", unidades_disponiveis, default=unidades_disponiveis, key="f_def_unidades")
    if sel_unidades:
        df = df[df["Unidade"].isin(sel_unidades)]
        if len(sel_unidades) < len(unidades_disponiveis):
            filtros_aplicados.append(f"Unidade: {', '.join(sel_unidades)}")

    # Filtro Categoria Prazo
    cat_prazos_disponiveis = sorted(df_raw["Categoria_Prazo"].unique().tolist())
    sel_cat_prazos = st.multiselect("Categoria de Prazo", cat_prazos_disponiveis, default=cat_prazos_disponiveis, key="f_def_cat_prazos")
    if sel_cat_prazos:
        df = df[df["Categoria_Prazo"].isin(sel_cat_prazos)]
        if len(sel_cat_prazos) < len(cat_prazos_disponiveis):
            filtros_aplicados.append(f"Prazo: {', '.join(sel_cat_prazos)}")

    # Filtro Tipo de Demanda
    tipos_disponiveis = sorted(df_raw["Tipo_Demanda"].unique().tolist())
    sel_tipos = st.multiselect("Tipo de Demanda", tipos_disponiveis, default=tipos_disponiveis, key="f_def_tipos")
    if sel_tipos:
        df = df[df["Tipo_Demanda"].isin(sel_tipos)]
        if len(sel_tipos) < len(tipos_disponiveis):
            filtros_aplicados.append(f"Tipo: {', '.join(sel_tipos)}")

    st.caption(f"{len(df)} de {len(df_raw)} despesas selecionadas")

if df.empty:
    st.info("Nenhum registro encontrado para os filtros selecionados.")
    st.stop()

# ------------------------------------------------------------------ TOTAIS E MÉTRICAS
tot_deficit = float(df["Valor"].sum())
qtd_itens = len(df)

# Subtotais por momento
val_imediato_urgente = float(df[df["Prazo"].isin(["Imediato", "Dezembro/2026"])]["Valor"].sum())
val_sem1 = float(df[df["Prazo"].isin(["Janeiro/2027", "Fevereiro/2027", "Março/2027", "Junho/2027"])]["Valor"].sum())
val_sem2 = float(df[df["Prazo"].isin(["Setembro/2027", "Outubro/2027"])]["Valor"].sum())
val_judicial_indet = float(df[df["Prazo"].isin(["Pendente Judicial", "Indeterminado"])]["Valor"].sum())

# ------------------------------------------------------------------ CARDS NO TOPO
c1, c2, c3, c4, c5 = st.columns(5)
card_base_style = "border-radius:14px; padding:16px 18px; color:#FFFFFF; text-align:left; min-height:120px; height:100%; display:flex; flex-direction:column; justify-content:space-between; transition: transform 0.15s ease;"

with c1:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #991B1B 0%, #7F1D1D 100%);
                    box-shadow: 0 6px 18px rgba(153,27,27,0.32), inset 0 1px 0 rgba(255,255,255,0.25);
                    border: 1.5px solid rgba(248,113,113,0.45); {card_base_style}">
          <div>
            <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
              {brl(tot_deficit, short=True).replace("R$ ", "")}
            </div>
            <div style="font-size:0.71rem; text-transform:uppercase; letter-spacing:0.05em;
                        color:#FCA5A5; margin-top:8px; font-weight:700;">
              Déficit Total 2027
            </div>
          </div>
          <div style="font-size:0.70rem; color:#FECACA; margin-top:4px; opacity:0.85;">
            {qtd_itens} demandas orçamentárias mapeadas
          </div>
        </div>"""
    )

with c2:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #C2410C 0%, #9A3412 100%);
                    box-shadow: 0 4px 14px rgba(194,65,12,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(251,146,60,0.35); {card_base_style}">
          <div>
            <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
              {brl(val_imediato_urgente, short=True).replace("R$ ", "")}
            </div>
            <div style="font-size:0.71rem; text-transform:uppercase; letter-spacing:0.05em;
                        color:#FDBA74; margin-top:8px; font-weight:700;">
              Imediato / Urgente
            </div>
          </div>
          <div style="font-size:0.70rem; color:#FFEDD5; margin-top:4px; opacity:0.85;">
            Imediato e Dezembro/2026
          </div>
        </div>"""
    )

with c3:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #D97706 0%, #B45309 100%);
                    box-shadow: 0 4px 14px rgba(217,119,6,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(252,211,77,0.3); {card_base_style}">
          <div>
            <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
              {brl(val_sem1, short=True).replace("R$ ", "")}
            </div>
            <div style="font-size:0.71rem; text-transform:uppercase; letter-spacing:0.05em;
                        color:#FDE68A; margin-top:8px; font-weight:700;">
              1º Semestre 2027
            </div>
          </div>
          <div style="font-size:0.70rem; color:#FEF3C7; margin-top:4px; opacity:0.85;">
            Demandas de Jan a Jun/2027
          </div>
        </div>"""
    )

with c4:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #0369A1 0%, #075985 100%);
                    box-shadow: 0 4px 14px rgba(3,105,161,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(125,211,252,0.3); {card_base_style}">
          <div>
            <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
              {brl(val_sem2, short=True).replace("R$ ", "")}
            </div>
            <div style="font-size:0.71rem; text-transform:uppercase; letter-spacing:0.05em;
                        color:#BAE6FD; margin-top:8px; font-weight:700; white-space:nowrap;">
              2º Semestre 2027
            </div>
          </div>
          <div style="font-size:0.70rem; color:#E0F2FE; margin-top:4px; opacity:0.85;">
            Demandas de Set e Out/2027
          </div>
        </div>"""
    )

with c5:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #4338CA 0%, #312E81 100%);
                    box-shadow: 0 4px 14px rgba(67,56,202,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(165,180,252,0.3); {card_base_style}">
          <div>
            <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
              {brl(val_judicial_indet, short=True).replace("R$ ", "")}
            </div>
            <div style="font-size:0.71rem; text-transform:uppercase; letter-spacing:0.05em;
                        color:#C7D2FE; margin-top:8px; font-weight:700; white-space:nowrap;">
              Judicial / Indet.
            </div>
          </div>
          <div style="font-size:0.70rem; color:#E0E7FF; margin-top:4px; opacity:0.85;">
            Pendente Judicial e Indeterminado
          </div>
        </div>"""
    )

st.write("")

# ------------------------------------------------------------------ SEÇÃO ANALÍTICA & GRÁFICOS
tab_graficos, tab_tabela = st.tabs(["📊 Gráficos & Distribuição", "📋 Tabela Detalhada do Déficit"])

cores_unidades = {
    "Tecnologia da Informação": "#2563EB",
    "Gestão Integrada": "#059669",
    "Receita": "#7C3AED",
    "Receita/Gestão Integrada": "#D97706",
}

with tab_graficos:
    # Gráfico 1: Linha do tempo / Cronograma de necessidade de liberação orçamentária
    df_chrono = (
        df.groupby(["Ordem_Cronologica", "Prazo"])["Valor"]
        .sum()
        .reset_index()
        .sort_values("Ordem_Cronologica")
    )
    fig_chrono = px.bar(
        df_chrono,
        x="Prazo",
        y="Valor",
        title="Cronograma da Necessidade do Orçamento Liberado",
        text=df_chrono["Valor"].apply(lambda v: brl(v, short=True)),
        color="Prazo",
        color_discrete_sequence=px.colors.qualitative.Prism,
    )
    fig_chrono.update_traces(textposition="outside", cliponaxis=False)
    fig_chrono.update_layout(showlegend=False, xaxis_title=None, yaxis_title="Valor (R$)")
    fig_chrono = style(fig_chrono, height=420)
    st.plotly_chart(fig_chrono, width="stretch")

    c_g1, c_g2 = st.columns([1, 1])

    with c_g1:
        # Gráfico 2: Donut por Unidade Responsável
        df_u = df.groupby("Unidade")["Valor"].sum().reset_index()
        fig_donut_u = px.pie(
            df_u,
            values="Valor",
            names="Unidade",
            title="Déficit por Unidade Responsável",
            hole=0.45,
            color="Unidade",
            color_discrete_map=cores_unidades,
        )
        fig_donut_u.update_traces(
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>Déficit: R$ %{value:,.2f}<br>%{percent}<extra></extra>",
        )
        fig_donut_u = style(fig_donut_u, height=400)
        st.plotly_chart(fig_donut_u, width="stretch")

    with c_g2:
        # Gráfico 3: Distribuição por Tipo de Demanda
        df_t = df.groupby("Tipo_Demanda")["Valor"].sum().reset_index().sort_values("Valor", ascending=False)
        fig_tipo = px.bar(
            df_t,
            x="Valor",
            y="Tipo_Demanda",
            orientation="h",
            title="Déficit por Tipo de Demanda",
            text=df_t["Valor"].apply(lambda v: brl(v, short=True)),
            color="Tipo_Demanda",
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig_tipo.update_traces(textposition="outside", cliponaxis=False)
        fig_tipo.update_layout(showlegend=False, xaxis_title=None, yaxis_title=None)
        fig_tipo = style(fig_tipo, height=400)
        st.plotly_chart(fig_tipo, width="stretch")

    # Gráfico 4: Top 10 Maiores Demandas com Déficit
    df_top = df.sort_values("Valor", ascending=False).head(10).copy()
    if not df_top.empty:
        nome_orig = df_top["Despesa"].astype(str).str.strip()
        nome_curto = nome_orig.where(nome_orig.str.len() <= 55, nome_orig.str.slice(0, 54) + "…")
        df_top["Item_Unico"] = nome_curto + nome_curto.groupby(nome_curto).cumcount().map(lambda k: "\u200b" * k)
        df_top["Rotulo_Mi"] = df_top["Valor"].apply(
            lambda v: f"R$ {v / 1e6:,.2f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        fig_top = px.bar(
            df_top,
            x="Valor",
            y="Item_Unico",
            color="Unidade",
            orientation="h",
            title="Top 10 Maiores Demandas em Déficit",
            color_discrete_map=cores_unidades,
            text="Rotulo_Mi",
            category_orders={"Item_Unico": df_top["Item_Unico"].tolist()},
            custom_data=["Despesa", "Unidade", "Prazo", "% do Déficit"],
            labels={"Valor": "Déficit (R$)", "Item_Unico": "Despesa"},
        )
        fig_top.update_traces(
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{customdata[0]}</b><br>Unidade: %{customdata[1]}<br>Prazo: %{customdata[2]}<br>Valor: %{text} (%{customdata[3]:.1f}%)<extra></extra>",
            textfont=dict(size=12, color="#0F2A20", family="Inter, Segoe UI, sans-serif"),
        )
        fig_top.update_xaxes(range=[0, df_top["Valor"].max() * 1.25], showticklabels=False, title=None)
        fig_top.update_yaxes(title=None, tickfont=dict(size=12))
        fig_top = style(fig_top, height=480)
        st.plotly_chart(fig_top, width="stretch")

with tab_tabela:
    st.markdown("#### Detalhamento das Demandas em Déficit Orçamentário")

    df_disp = df.copy()
    df_disp["Valor (R$)"] = df_disp["Valor"].apply(lambda v: brl(v, short=False))
    df_disp["% do Déficit"] = df_disp["% do Déficit"].apply(lambda v: f"{v:.2f}%")

    col_order = ["Despesa", "Unidade", "Tipo_Demanda", "Prazo", "Categoria_Prazo", "Valor (R$)", "% do Déficit"]
    st.dataframe(
        df_disp[col_order],
        width="stretch",
        height=520,
        hide_index=True,
    )

    # Botão para download dos dados filtrados
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Deficit_2027")
    st.download_button(
        label="📥 Baixar Planilha de Déficit (Excel)",
        data=buffer.getvalue(),
        file_name="Deficit_2027_Filtrado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="btn_dl_def",
    )
