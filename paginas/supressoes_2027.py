"""Página: Supressões 2027 — Análise e consulta de cortes e adequações ao teto da PLOA 2027."""
from __future__ import annotations

import io
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import brl, num, style, get_total_despesas_unidade_2027, fmt_brl

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

# Total estimado nas Despesas por Unidade (2027) para cálculo do índice global
tot_despesas_unidade_2027 = get_total_despesas_unidade_2027(sel_unidades)
pct_global = (tot_econ / tot_despesas_unidade_2027 * 100) if tot_despesas_unidade_2027 > 0 else 0.0
pct_alvo = (tot_econ / tot_orc * 100) if tot_orc > 0 else 0.0
qtd_itens = len(df)
qtd_cortados = int((df["Economia Gerada"] > 0).sum())

# ------------------------------------------------------------------ CARDS NO TOPO
c1, c2, c3, c4, c5 = st.columns(5)
card_base_style = "border-radius:14px; padding:18px 20px; color:#FFFFFF; text-align:left; min-height:148px; height:100%; display:flex; flex-direction:column; justify-content:space-between; transition: transform 0.15s ease;"

with c1:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #064E3B 0%, #022C22 100%);
                    box-shadow: 0 6px 18px rgba(6,78,59,0.32), inset 0 1px 0 rgba(255,255,255,0.25);
                    border: 1.5px solid rgba(52,211,153,0.45); {card_base_style}">
          <div>
            <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
              {brl(tot_orc, short=True).replace("R$ ", "")}
            </div>
            <div style="font-size:0.71rem; text-transform:uppercase; letter-spacing:0.05em;
                        color:#6EE7B7; margin-top:8px; font-weight:700;">
              Proposta dos Contratos Alvo
            </div>
          </div>
          <div style="font-size:0.70rem; color:#A7F3D0; margin-top:4px; opacity:0.85;">
            Estimado inicial dos itens analisados
          </div>
        </div>"""
    )

with c2:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #0E7490 0%, #155E75 100%);
                    box-shadow: 0 4px 14px rgba(14,116,144,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div>
            <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
              {brl(tot_teto, short=True).replace("R$ ", "")}
            </div>
            <div style="font-size:0.71rem; text-transform:uppercase; letter-spacing:0.05em;
                        color:#A5F3FC; margin-top:8px; font-weight:700;">
              Teto dos Contratos Alvo
            </div>
          </div>
          <div style="font-size:0.70rem; color:#BAE6FD; margin-top:4px; opacity:0.85;">
            Limite pós-supressão dos itens
          </div>
        </div>"""
    )

with c3:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #BE123C 0%, #9F1239 100%);
                    box-shadow: 0 4px 14px rgba(190,18,60,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div>
            <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
              {brl(tot_econ, short=True).replace("R$ ", "")}
            </div>
            <div style="font-size:0.71rem; text-transform:uppercase; letter-spacing:0.05em;
                        color:#FECDD3; margin-top:8px; font-weight:700;">
              Economia Total Gerada
            </div>
          </div>
          <div style="font-size:0.70rem; color:#FFE4E6; margin-top:4px; opacity:0.85;">
            Redução total proposta
          </div>
        </div>"""
    )

with c4:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #312E81 0%, #1E1B4B 100%);
                    box-shadow: 0 4px 14px rgba(49,46,129,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(165,180,252,0.3); {card_base_style}">
          <div>
            <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
              {pct_alvo:.1f}%
            </div>
            <div style="font-size:0.71rem; text-transform:uppercase; letter-spacing:0.05em;
                        color:#C7D2FE; margin-top:8px; font-weight:700; white-space:nowrap;">
              Redução nos Contratos Alvo
            </div>
          </div>
          <div style="font-size:0.70rem; color:#E0E7FF; margin-top:4px; opacity:0.85;">
            Sobre {brl(tot_orc, short=True)} (Contratos Alvo)
          </div>
        </div>"""
    )

with c5:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
                    box-shadow: 0 4px 14px rgba(30,41,59,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(148,163,184,0.3); {card_base_style}">
          <div>
            <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
              {pct_global:.1f}%
            </div>
            <div style="font-size:0.71rem; text-transform:uppercase; letter-spacing:0.05em;
                        color:#94A3B8; margin-top:8px; font-weight:700; white-space:nowrap;">
              Índice Global de Supressão
            </div>
          </div>
          <div style="font-size:0.70rem; color:#CBD5E1; margin-top:4px; opacity:0.85;">
            Sobre {brl(tot_despesas_unidade_2027, short=True)} (Despesas por Unidade)
          </div>
        </div>"""
    )

# ------------------------------------------------------------------ SEÇÃO ANALÍTICA & GRÁFICOS
tab_graficos, tab_tabela = st.tabs(["📊 Gráficos & Distribuição", "📋 Tabela Detalhada das Supressões"])

with tab_graficos:
    c_g1, c_g2 = st.columns([1.1, 1])

    with c_g1:
        # Comparativo Antes x Depois por Unidade
        df_u = df.groupby("Unidade")[["Orçamento 2027", "Teto Ajustado 2027", "Economia Gerada"]].sum().reset_index()
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(
            name="Proposta Contratos Alvo",
            x=df_u["Unidade"],
            y=df_u["Orçamento 2027"],
            marker_color="#064E3B",
            text=[brl(v, short=True) for v in df_u["Orçamento 2027"]],
            textposition="outside",
        ))
        fig_comp.add_trace(go.Bar(
            name="Teto Contratos Alvo",
            x=df_u["Unidade"],
            y=df_u["Teto Ajustado 2027"],
            marker_color="#0E7490",
            text=[brl(v, short=True) for v in df_u["Teto Ajustado 2027"]],
            textposition="outside",
        ))
        fig_comp.update_layout(
            barmode="group",
            title="Comparativo: Proposta Inicial vs. Teto Ajustado (Contratos Alvo por Unidade)",
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
    st.markdown("#### 📋 Detalhamento Interativo das Supressões e Ajustes Propostos")
    st.caption("Consulte, filtre e ordene as propostas de adequação orçamentária dos contratos alvo para a PLOA 2027.")

    # 1. Filtro Rápido por Segmento / Tipo de Item
    segmentos_sup = ["Todos os Itens", "✂️ Apenas com Redução (> 0)", "🛡️ Sem Redução / Mantidos"]
    filtro_tipo_corte = st.segmented_control(
        "Filtrar por Situação da Redução:",
        options=segmentos_sup,
        default="Todos os Itens",
        key="tab_sup_tipo_corte",
    )

    # 2. Filtros Específicos em Linha e Ordenação
    fc1, fc2, fc3 = st.columns([1.6, 1.2, 1.2])
    with fc1:
        f_busca_tab = st.text_input(
            "🔍 Buscar na tabela",
            placeholder="Digite nome do contrato, item ou ação sugerida...",
            key="tab_sup_busca",
        )
    with fc2:
        unis_tab = sorted(df["Unidade"].unique().tolist())
        f_uni_tab = st.multiselect(
            "Unidade Responsável",
            options=unis_tab,
            default=unis_tab,
            key="tab_sup_unis",
        )
    with fc3:
        ordem_tab = st.selectbox(
            "Ordenar por:",
            ["Maior Economia (R$)", "Maior % Redução", "Maior Proposta Inicial (R$)", "Maior Teto Ajustado (R$)", "Item de Despesa (A-Z)", "Unidade"],
            key="tab_sup_ordem",
        )

    # Aplicação dos filtros na visualização da tabela
    df_tab = df.copy()

    # Aplica segmented control
    if filtro_tipo_corte == "✂️ Apenas com Redução (> 0)":
        df_tab = df_tab[df_tab["Economia Gerada"] > 0]
    elif filtro_tipo_corte == "🛡️ Sem Redução / Mantidos":
        df_tab = df_tab[df_tab["Economia Gerada"] <= 0]

    # Aplica busca textual
    if f_busca_tab:
        df_tab = df_tab[
            df_tab["Item de Despesa"].astype(str).str.contains(f_busca_tab, case=False, na=False)
            | df_tab["Ação Sugerida"].astype(str).str.contains(f_busca_tab, case=False, na=False)
            | df_tab["Unidade"].astype(str).str.contains(f_busca_tab, case=False, na=False)
        ]

    # Aplica multiselect de unidades
    if f_uni_tab:
        df_tab = df_tab[df_tab["Unidade"].isin(f_uni_tab)]

    # Aplica ordenação selecionada
    if ordem_tab == "Maior Economia (R$)":
        df_tab = df_tab.sort_values(by="Economia Gerada", ascending=False)
    elif ordem_tab == "Maior % Redução":
        df_tab = df_tab.sort_values(by="% Redução", ascending=False)
    elif ordem_tab == "Maior Proposta Inicial (R$)":
        df_tab = df_tab.sort_values(by="Orçamento 2027", ascending=False)
    elif ordem_tab == "Maior Teto Ajustado (R$)":
        df_tab = df_tab.sort_values(by="Teto Ajustado 2027", ascending=False)
    elif ordem_tab == "Item de Despesa (A-Z)":
        df_tab = df_tab.sort_values(by="Item de Despesa", ascending=True)
    elif ordem_tab == "Unidade":
        df_tab = df_tab.sort_values(by=["Unidade", "Economia Gerada"], ascending=[True, False])

    # 3. Faixa de Resumo Dinâmico dos Dados Filtrados
    tot_tab_orc = float(df_tab["Orçamento 2027"].sum())
    tot_tab_teto = float(df_tab["Teto Ajustado 2027"].sum())
    tot_tab_econ = float(df_tab["Economia Gerada"].sum())
    pct_tab_reducao = (tot_tab_econ / tot_tab_orc * 100) if tot_tab_orc > 0 else 0.0
    qtd_tab = len(df_tab)

    st.markdown(
        f"""<div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:10px; padding:12px 18px; margin: 12px 0 16px 0; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
            <div style="color:#166534; font-size:0.95rem; font-weight:600;">
                📋 Exibindo <strong>{qtd_tab}</strong> de {qtd_itens} itens selecionados
            </div>
            <div style="display:flex; gap:16px; flex-wrap:wrap; font-size:0.92rem; color:#1F2937;">
                <div>Proposta Inicial: <strong>{fmt_brl(tot_tab_orc)}</strong></div>
                <div>Teto Ajustado: <strong>{fmt_brl(tot_tab_teto)}</strong></div>
                <div>Economia: <strong style="color:#0A6B56; font-size:1.05rem;">{fmt_brl(tot_tab_econ)}</strong> <span style="color:#15803D; font-weight:600;">({f"{pct_tab_reducao:.1f}%".replace(".", ",")})</span></div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    if df_tab.empty:
        st.info("Nenhum registro encontrado para os filtros selecionados na tabela.")
    else:
        # 4. Tabela Interativa Formatada no Padrão Brasileiro (X.XXX.XXX,XX)
        df_disp = df_tab.copy()
        df_disp["Proposta Inicial (R$)"] = df_disp["Orçamento 2027"].apply(fmt_brl)
        df_disp["Teto Ajustado (R$)"] = df_disp["Teto Ajustado 2027"].apply(fmt_brl)
        df_disp["Economia Gerada (R$)"] = df_disp["Economia Gerada"].apply(fmt_brl)
        df_disp["% Redução"] = df_disp["% Redução"].apply(lambda v: f"{v:.1f}%".replace(".", ","))

        col_order = ["Unidade", "Item de Despesa", "Ação Sugerida", "Proposta Inicial (R$)", "Teto Ajustado (R$)", "Economia Gerada (R$)", "% Redução"]

        st.dataframe(
            df_disp[col_order],
            width="stretch",
            height=480,
            hide_index=True,
            column_config={
                "Unidade": st.column_config.TextColumn(
                    "Unidade",
                    width="small",
                ),
                "Item de Despesa": st.column_config.TextColumn(
                    "Item de Despesa / Contrato",
                    help="Objeto, processo ou contrato analisado para supressão",
                    width="large",
                ),
                "Ação Sugerida": st.column_config.TextColumn(
                    "Ação Sugerida / Justificativa",
                    help="Medida recomendada para atingimento do teto",
                    width="large",
                ),
                "Proposta Inicial (R$)": st.column_config.TextColumn(
                    "Proposta Inicial (R$)",
                    help="Valor estimado inicialmente antes dos cortes",
                    alignment="right",
                ),
                "Teto Ajustado (R$)": st.column_config.TextColumn(
                    "Teto Ajustado (R$)",
                    help="Valor limite fixado pós-supressão",
                    alignment="right",
                ),
                "Economia Gerada (R$)": st.column_config.TextColumn(
                    "Economia Gerada (R$)",
                    help="Valor financeiro suprimido",
                    alignment="right",
                ),
                "% Redução": st.column_config.TextColumn(
                    "% Redução",
                    help="Percentual de corte sobre a proposta inicial do item",
                    alignment="right",
                ),
            },
        )

        # 5. Inspecionar Detalhes da Supressão (Card Amigável)
        with st.expander("🔍 Inspecionar Detalhes de um Item Selecionado"):
            lista_itens = df_tab["Item de Despesa"].tolist()
            item_sel = st.selectbox(
                "Selecione um item para detalhamento e ação sugerida:",
                options=lista_itens,
                key="sel_item_sup_inspect",
            )
            if item_sel:
                i_row = df_tab[df_tab["Item de Despesa"] == item_sel].iloc[0]
                i_orc = float(i_row["Orçamento 2027"])
                i_teto = float(i_row["Teto Ajustado 2027"])
                i_econ = float(i_row["Economia Gerada"])
                i_pct = float(i_row["% Redução"])

                st.markdown(
                    f"""<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-left:4px solid #0A6B56; border-radius:8px; padding:16px 20px;">
                        <div style="font-size:1.15rem; font-weight:700; color:#0F172A; margin-bottom:6px;">
                            {i_row['Item de Despesa']} <span style="font-size:0.85rem; font-weight:600; color:#047857; background:#DCFCE7; padding:2px 8px; border-radius:4px; margin-left:8px;">{i_row['Unidade']}</span>
                        </div>
                        <div style="margin-top:10px; padding:10px 14px; background:#FFFFFF; border:1px dashed #CBD5E1; border-radius:6px; font-size:0.92rem; color:#334155; line-height:1.5;">
                            <strong>Ação Sugerida:</strong> {i_row['Ação Sugerida']}
                        </div>
                        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin-top:14px;">
                            <div>
                                <span style="font-size:0.75rem; color:#64748B; text-transform:uppercase; font-weight:600;">Proposta Inicial</span><br>
                                <span style="font-size:1.15rem; font-weight:700; color:#334155;">{fmt_brl(i_orc)}</span>
                            </div>
                            <div>
                                <span style="font-size:0.75rem; color:#64748B; text-transform:uppercase; font-weight:600;">Teto Ajustado</span><br>
                                <span style="font-size:1.15rem; font-weight:700; color:#0E7490;">{fmt_brl(i_teto)}</span>
                            </div>
                            <div>
                                <span style="font-size:0.75rem; color:#64748B; text-transform:uppercase; font-weight:600;">Economia Gerada</span><br>
                                <span style="font-size:1.25rem; font-weight:800; color:#0A6B56;">{fmt_brl(i_econ)}</span>
                            </div>
                            <div>
                                <span style="font-size:0.75rem; color:#64748B; text-transform:uppercase; font-weight:600;">Índice de Redução</span><br>
                                <span style="font-size:1.25rem; font-weight:800; color:#2563EB;">{f"{i_pct:.1f}%".replace(".", ",")}</span>
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
                df_tab.to_excel(writer, index=False, sheet_name="Supressoes_2027")
            st.download_button(
                label="📥 Baixar Dados Filtrados em Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name="Supressoes_2027_Filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_dl_sup_xlsx",
                use_container_width=True,
            )

        with col_dl2:
            st.download_button(
                label="📄 Baixar Dados Filtrados em CSV (.csv)",
                data=df_tab.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                file_name="Supressoes_2027_Filtrado.csv",
                mime="text/csv",
                key="btn_dl_sup_csv",
                use_container_width=True,
            )
