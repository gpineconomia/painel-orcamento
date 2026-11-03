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
val_imediato_urgente = float(df[df["Prazo"].isin(["Imediato", "Dezembro/2026", "Pendente Judicial"])]["Valor"].sum())
val_sem1 = float(df[df["Prazo"].isin(["Janeiro/2027", "Fevereiro/2027", "Março/2027", "Junho/2027"])]["Valor"].sum())
val_sem2 = float(df[df["Prazo"].isin(["Setembro/2027", "Outubro/2027"])]["Valor"].sum())
val_indet = float(df[df["Prazo"] == "Indeterminado"]["Valor"].sum())

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
            Imediato, Pend. Judicial e Dez/26
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
              {brl(val_indet, short=True).replace("R$ ", "")}
            </div>
            <div style="font-size:0.71rem; text-transform:uppercase; letter-spacing:0.05em;
                        color:#C7D2FE; margin-top:8px; font-weight:700; white-space:nowrap;">
              Prazo Indeterminado
            </div>
          </div>
          <div style="font-size:0.70rem; color:#E0E7FF; margin-top:4px; opacity:0.85;">
            1 demanda (Convênio SEFAZ/RS)
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
    max_val_c = df_chrono["Valor"].max() if not df_chrono.empty else 1.0
    fig_chrono.update_layout(showlegend=False, xaxis_title=None, yaxis_title="Valor (R$)", margin=dict(t=40, r=30))
    fig_chrono.update_yaxes(range=[0, max_val_c * 1.20])
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
        max_val_t = df_t["Valor"].max() if not df_t.empty else 1.0
        fig_tipo.update_xaxes(range=[0, max_val_t * 1.30], showticklabels=True)
        fig_tipo.update_layout(showlegend=False, xaxis_title=None, yaxis_title=None, margin=dict(r=45))
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
        max_val_top = df_top["Valor"].max() if not df_top.empty else 1.0
        fig_top.update_xaxes(range=[0, max_val_top * 1.30], showticklabels=False, title=None)
        fig_top.update_yaxes(title=None, tickfont=dict(size=12))
        fig_top.update_layout(margin=dict(r=45))
        fig_top = style(fig_top, height=480)
        st.plotly_chart(fig_top, width="stretch")

with tab_tabela:
    st.markdown("#### 📋 Detalhamento Interativo das Demandas em Déficit")
    st.caption("Consulte, filtre e ordene as 24 demandas de suplementação orçamentária para a PLOA 2027.")

    # 1. Filtro Rápido por Segmento / Momento
    segmentos = ["Todos", "🚨 Imediato / Urgente", "📅 1º Semestre 2027", "📆 2º Semestre 2027", "⏳ Indeterminado"]
    filtro_momento = st.segmented_control(
        "Filtrar por Momento de Necessidade:",
        options=segmentos,
        default="Todos",
        key="tab_def_momento",
    )

    # 2. Filtros Específicos em Linha
    fc1, fc2, fc3 = st.columns([1.6, 1.2, 1.2])
    with fc1:
        f_busca_tab = st.text_input(
            "🔍 Buscar na tabela",
            placeholder="Digite nome do contrato, serviço ou palavra-chave...",
            key="tab_def_busca",
        )
    with fc2:
        unis_tab = sorted(df["Unidade"].unique().tolist())
        f_uni_tab = st.multiselect(
            "Unidade Responsável",
            options=unis_tab,
            default=unis_tab,
            key="tab_def_unis",
        )
    with fc3:
        tipos_tab = sorted(df["Tipo_Demanda"].unique().tolist())
        f_tipo_tab = st.multiselect(
            "Tipo de Demanda",
            options=tipos_tab,
            default=tipos_tab,
            key="tab_def_tipos",
        )

    # Aplicação dos filtros na visualização da tabela
    df_tab = df.copy()

    # Aplica segmented control
    if filtro_momento == "🚨 Imediato / Urgente":
        df_tab = df_tab[df_tab["Prazo"].isin(["Imediato", "Dezembro/2026", "Pendente Judicial"])]
    elif filtro_momento == "📅 1º Semestre 2027":
        df_tab = df_tab[df_tab["Prazo"].isin(["Janeiro/2027", "Fevereiro/2027", "Março/2027", "Junho/2027"])]
    elif filtro_momento == "📆 2º Semestre 2027":
        df_tab = df_tab[df_tab["Prazo"].isin(["Setembro/2027", "Outubro/2027"])]
    elif filtro_momento == "⏳ Indeterminado":
        df_tab = df_tab[df_tab["Prazo"] == "Indeterminado"]

    # Aplica busca textual
    if f_busca_tab:
        df_tab = df_tab[
            df_tab["Despesa"].astype(str).str.contains(f_busca_tab, case=False, na=False)
            | df_tab["Prazo"].astype(str).str.contains(f_busca_tab, case=False, na=False)
        ]

    # Aplica multiselects
    if f_uni_tab:
        df_tab = df_tab[df_tab["Unidade"].isin(f_uni_tab)]
    if f_tipo_tab:
        df_tab = df_tab[df_tab["Tipo_Demanda"].isin(f_tipo_tab)]

    # 3. Faixa de Resumo Dinâmico dos Dados Filtrados
    tot_tab = float(df_tab["Valor"].sum())
    qtd_tab = len(df_tab)
    pct_tab = (tot_tab / tot_deficit * 100) if tot_deficit > 0 else 0.0

    st.markdown(
        f"""<div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:10px; padding:10px 18px; margin: 12px 0 16px 0; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div style="color:#166534; font-size:0.95rem; font-weight:600;">
                📋 Exibindo <strong>{qtd_tab}</strong> de {qtd_itens} demandas selecionadas
            </div>
            <div style="font-size:0.95rem; color:#14532D;">
                Total Filtrado: <strong style="font-size:1.15rem; color:#0A6B56;">{brl(tot_tab)}</strong> 
                <span style="font-size:0.85rem; color:#15803D; font-weight:600;">({pct_tab:.1f}% do déficit ativo)</span>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    if df_tab.empty:
        st.info("Nenhuma demanda encontrada para os filtros selecionados na tabela.")
    else:
        # 4. Tabela Interativa Formatada
        df_view = df_tab[["Despesa", "Unidade", "Tipo_Demanda", "Prazo", "Categoria_Prazo", "Valor", "% do Déficit"]].copy()
        max_pct = float(df_raw["% do Déficit"].max()) if not df_raw.empty else 100.0

        st.dataframe(
            df_view,
            width="stretch",
            height=460,
            hide_index=True,
            column_config={
                "Despesa": st.column_config.TextColumn(
                    "Despesa em Rascunho",
                    help="Nome, objeto ou contrato da demanda com necessidade de recursos",
                    width="large",
                ),
                "Unidade": st.column_config.TextColumn(
                    "Unidade Responsável",
                    width="medium",
                ),
                "Tipo_Demanda": st.column_config.TextColumn(
                    "Tipo de Demanda",
                    width="small",
                ),
                "Prazo": st.column_config.TextColumn(
                    "Momento de Liberação",
                    help="Prazo ou calendário informado para a necessidade do orçamento",
                    width="small",
                ),
                "Categoria_Prazo": st.column_config.TextColumn(
                    "Categoria",
                    width="small",
                ),
                "Valor": st.column_config.NumberColumn(
                    "Valor do Déficit (R$)",
                    help="Valor total estimado necessário",
                    format="R$ %,.2f",
                ),
                "% do Déficit": st.column_config.ProgressColumn(
                    "% do Déficit",
                    help="Participação percentual da despesa sobre o déficit total (R$ 49,85 Mi)",
                    format="%.2f%%",
                    min_value=0.0,
                    max_value=max_pct,
                ),
            },
        )

        # 5. Inspecionar Detalhes da Demanda (Card Amigável)
        with st.expander("🔍 Inspecionar Detalhes de uma Demanda Selecionada"):
            lista_despesas = df_tab["Despesa"].tolist()
            item_sel = st.selectbox(
                "Selecione uma despesa para detalhamento:",
                options=lista_despesas,
                key="sel_despesa_inspect",
            )
            if item_sel:
                d_row = df_tab[df_tab["Despesa"] == item_sel].iloc[0]
                d_val = float(d_row["Valor"])
                d_pct = float(d_row["% do Déficit"])
                st.markdown(
                    f"""<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-left:4px solid #0A6B56; border-radius:8px; padding:16px 20px;">
                        <div style="font-size:1.15rem; font-weight:700; color:#0F172A; margin-bottom:8px;">
                            {d_row['Despesa']}
                        </div>
                        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px; margin-top:10px;">
                            <div>
                                <span style="font-size:0.75rem; color:#64748B; text-transform:uppercase; font-weight:600;">Valor Necessário</span><br>
                                <span style="font-size:1.25rem; font-weight:800; color:#0A6B56;">{brl(d_val)}</span>
                            </div>
                            <div>
                                <span style="font-size:0.75rem; color:#64748B; text-transform:uppercase; font-weight:600;">Impacto no Déficit</span><br>
                                <span style="font-size:1.25rem; font-weight:800; color:#2563EB;">{d_pct:.2f}%</span>
                            </div>
                            <div>
                                <span style="font-size:0.75rem; color:#64748B; text-transform:uppercase; font-weight:600;">Momento da Liberação</span><br>
                                <span style="font-size:1.05rem; font-weight:700; color:#334155;">{d_row['Prazo']}</span>
                            </div>
                            <div>
                                <span style="font-size:0.75rem; color:#64748B; text-transform:uppercase; font-weight:600;">Unidade / Tipo</span><br>
                                <span style="font-size:1.0rem; font-weight:600; color:#334155;">{d_row['Unidade']} · {d_row['Tipo_Demanda']}</span>
                            </div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        # 6. Botões de Exportação
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_tab.to_excel(writer, index=False, sheet_name="Deficit_2027")
            st.download_button(
                label="📥 Baixar Dados Filtrados em Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name="Deficit_2027_Filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_dl_def_xlsx",
                use_container_width=True,
            )

        with col_dl2:
            st.download_button(
                label="📄 Baixar Dados Filtrados em CSV (.csv)",
                data=df_tab.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                file_name="Deficit_2027_Filtrado.csv",
                mime="text/csv",
                key="btn_dl_def_csv",
                use_container_width=True,
            )
