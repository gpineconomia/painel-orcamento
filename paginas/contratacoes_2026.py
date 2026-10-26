"""Página: Acompanhamento das Contratações 2026."""
from __future__ import annotations

import io
import pandas as pd
import plotly.express as px
import streamlit as st

import common
from common import style
import contratacoes_data


# ------------------------------------------------------------------ CARREGAMENTO DOS DADOS
try:
    df_raw, data_base = contratacoes_data.load_contratacoes_2026()
except Exception as exc:
    st.error(f"Erro ao carregar dados de Contratações 2026: {exc}")
    st.stop()

if df_raw.empty:
    st.warning("Não há contratações registradas para exibição.")
    st.stop()


# ------------------------------------------------------------------ SIDEBAR (FILTROS)
with st.sidebar:
    st.markdown("### 🔍 Filtros de Contratações")

    if st.button("🔄 Atualizar Dados", use_container_width=True, help="Força a atualização imediata da planilha"):
        contratacoes_data.clear_contratacoes_cache()
        st.cache_data.clear()
        st.success("Cache limpo! Recarregando...")
        st.rerun()

    st.markdown("---")

    # Filtro: Unidade Demandante
    unidades_disp = sorted([u for u in df_raw["Unidade Demandante"].dropna().unique() if u])
    sel_unidades = st.multiselect("Unidade Demandante", options=unidades_disp, default=[])

    # Filtro: Prioridade
    prioridades_ordem = ["Alta", "Média", "Baixa", "Não informada"]
    prioridades_disp = [p for p in prioridades_ordem if p in df_raw["Prioridade"].values]
    sel_prioridade = st.multiselect("Prioridade", options=prioridades_disp, default=[])

    # Filtro: Tipo de Contratação
    tipos_disp = sorted([t for t in df_raw["Tipo"].dropna().unique() if t])
    sel_tipos = st.multiselect("Tipo de Demanda", options=tipos_disp, default=[])

    # Filtro: Status
    status_disp = sorted([s for s in df_raw["Status da Contratação"].dropna().unique() if s])
    sel_status = st.multiselect("Status da Contratação", options=status_disp, default=[])

    # Filtro: Prevista para 2026?
    prev_opts = ["Todas", "Sim", "Não"]
    sel_prev = st.selectbox("Prevista para 2026?", options=prev_opts, index=0)

    # Filtro: Parecer Jurídico
    parecer_opts = ["Todos"] + sorted([p for p in df_raw["Necessitará de Parecer Jurídico"].dropna().unique() if p])
    sel_parecer = st.selectbox("Parecer Jurídico", options=parecer_opts, index=0)

    # Filtro: Responsável
    resp_disp = sorted([r for r in df_raw["Responsável"].dropna().unique() if r and r != "Não informado"])
    sel_resp = st.multiselect("Responsável", options=resp_disp, default=[])

    # Busca livre
    busca_texto = st.text_input("🔎 Buscar por termo ou SEI", placeholder="Ex: OCR, 20260000..., etc.").strip().lower()


# ------------------------------------------------------------------ APLICAÇÃO DOS FILTROS
df_f = df_raw.copy()

if sel_unidades:
    df_f = df_f[df_f["Unidade Demandante"].isin(sel_unidades)]

if sel_prioridade:
    df_f = df_f[df_f["Prioridade"].isin(sel_prioridade)]

if sel_tipos:
    df_f = df_f[df_f["Tipo"].isin(sel_tipos)]

if sel_status:
    df_f = df_f[df_f["Status da Contratação"].isin(sel_status)]

if sel_prev != "Todas":
    df_f = df_f[df_f["Prevista para 2026?"] == sel_prev]

if sel_parecer != "Todos":
    df_f = df_f[df_f["Necessitará de Parecer Jurídico"] == sel_parecer]

if sel_resp:
    df_f = df_f[df_f["Responsável"].isin(sel_resp)]

if busca_texto:
    mask = (
        df_f["Objeto"].astype(str).str.lower().str.contains(busca_texto, na=False)
        | df_f["Número SEI"].astype(str).str.lower().str.contains(busca_texto, na=False)
        | df_f["Número da Contratação SISLOG"].astype(str).str.lower().str.contains(busca_texto, na=False)
        | df_f["Ponto de Atenção"].astype(str).str.lower().str.contains(busca_texto, na=False)
        | df_f["Responsável"].astype(str).str.lower().str.contains(busca_texto, na=False)
    )
    df_f = df_f[mask]


# ------------------------------------------------------------------ CABEÇALHO DA PÁGINA
st.markdown(
    """
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.2rem;">
        <div>
            <h1 style="margin: 0; padding: 0; font-size: 2.1rem; color: #1E293B;">📋 Acompanhamento das Contratações 2026</h1>
            <p style="margin: 0.3rem 0 0 0; color: #64748B; font-size: 1.05rem;">
                Painel Estratégico de Gestão de Demandas, Aquisições e Processos Licitatórios
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Badges informativas
st.markdown(
    f"""
    <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1.5rem;">
        <span style="background-color: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; padding: 0.3rem 0.7rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 500;">
            📁 <b>Fonte Oficial:</b> SharePoint (Kelly Alexandria)
        </span>
        <span style="background-color: #F0FDF4; color: #15803D; border: 1px solid #BBF7D0; padding: 0.3rem 0.7rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 500;">
            🔄 <b>Sincronização:</b> Automática a cada 60 minutos
        </span>
        <span style="background-color: #F8FAFC; color: #475569; border: 1px solid #E2E8F0; padding: 0.3rem 0.7rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 500;">
            📅 <b>Data Base:</b> {data_base}
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ CARDS KPI DE TOPO
total_cadastrados = len(df_raw)
total_filtrados = len(df_f)

prev_2026_count = (df_f["Prevista para 2026?"] == "Sim").sum()
prev_2026_pct = (prev_2026_count / total_filtrados * 100) if total_filtrados > 0 else 0

alta_count = (df_f["Prioridade"] == "Alta").sum()
alta_pct = (alta_count / total_filtrados * 100) if total_filtrados > 0 else 0

novas_count = (df_f["Tipo"] == "Nova Contratação").sum()
fase_prep_count = (df_f["Status da Contratação"] == "Fase Preparatória").sum()
pontos_atencao_count = (df_f["Ponto de Atenção"] != "-").sum()

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(
        f"""
        <div style="{style('card')} padding: 1.1rem; border-top: 4px solid #3B82F6;">
            <div style="{style('card_title')}">Total de Processos</div>
            <div style="{style('card_value')} color: #1E293B;">{total_filtrados}</div>
            <div style="{style('card_sub')}">de {total_cadastrados} na base geral</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div style="{style('card')} padding: 1.1rem; border-top: 4px solid #10B981;">
            <div style="{style('card_title')}">Previstas para 2026</div>
            <div style="{style('card_value')} color: #10B981;">{prev_2026_count}</div>
            <div style="{style('card_sub')}">{prev_2026_pct:.1f}% do total filtrado</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""
        <div style="{style('card')} padding: 1.1rem; border-top: 4px solid #EF4444;">
            <div style="{style('card_title')}">Prioridade Alta</div>
            <div style="{style('card_value')} color: #EF4444;">{alta_count}</div>
            <div style="{style('card_sub')}">{alta_pct:.1f}% com máxima atenção</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col4:
    st.markdown(
        f"""
        <div style="{style('card')} padding: 1.1rem; border-top: 4px solid #8B5CF6;">
            <div style="{style('card_title')}">Novas Contratações</div>
            <div style="{style('card_value')} color: #8B5CF6;">{novas_count}</div>
            <div style="{style('card_sub')}">{((novas_count/total_filtrados*100) if total_filtrados else 0):.1f}% das demandas</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col5:
    st.markdown(
        f"""
        <div style="{style('card')} padding: 1.1rem; border-top: 4px solid #F59E0B;">
            <div style="{style('card_title')}">Em Fase Preparatória</div>
            <div style="{style('card_value')} color: #F59E0B;">{fase_prep_count}</div>
            <div style="{style('card_sub')}">{pontos_atencao_count} com pontos de atenção</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ ABAS DE VISUALIZAÇÃO
tab_graficos, tab_atencao, tab_tabela = st.tabs([
    "📊 Visão Analítica & Gráficos",
    f"⚠️ Pontos de Atenção ({pontos_atencao_count})",
    f"📑 Tabela Detalhada ({total_filtrados})",
])

# ------------------------------------------------------------------ ABA 1: GRÁFICOS
with tab_graficos:
    gcol1, gcol2 = st.columns(2)

    with gcol1:
        # Gráfico: Status das Contratações
        df_status = df_f["Status da Contratação"].value_counts().reset_index()
        df_status.columns = ["Status", "Quantidade"]
        df_status = df_status.sort_values(by="Quantidade", ascending=True)

        fig_status = px.bar(
            df_status,
            x="Quantidade",
            y="Status",
            orientation="h",
            title="<b>Processos por Status da Contratação</b>",
            text="Quantidade",
            color="Quantidade",
            color_continuous_scale="Blues",
        )
        fig_status.update_layout(
            height=380,
            margin=dict(l=10, r=20, t=40, b=10),
            xaxis_title="Número de Processos",
            yaxis_title=None,
            coloraxis_showscale=False,
            font=dict(family="sans-serif", size=12),
        )
        fig_status.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(fig_status, use_container_width=True)

    with gcol2:
        # Gráfico: Unidade Demandante por Prioridade
        df_unid = df_f.groupby(["Unidade Demandante", "Prioridade"]).size().reset_index(name="Quantidade")
        color_map_prio = {
            "Alta": "#EF4444",
            "Média": "#F59E0B",
            "Baixa": "#10B981",
            "Não informada": "#94A3B8",
        }
        fig_unid = px.bar(
            df_unid,
            x="Unidade Demandante",
            y="Quantidade",
            color="Prioridade",
            color_discrete_map=color_map_prio,
            title="<b>Demandas por Unidade e Prioridade</b>",
            text="Quantidade",
            barmode="stack",
        )
        fig_unid.update_layout(
            height=380,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis_title=None,
            yaxis_title="Número de Processos",
            legend_title=None,
            font=dict(family="sans-serif", size=12),
        )
        st.plotly_chart(fig_unid, use_container_width=True)

    gcol3, gcol4 = st.columns(2)

    with gcol3:
        # Gráfico: Tipo de Demanda
        df_tipo = df_f["Tipo"].value_counts().reset_index()
        df_tipo.columns = ["Tipo", "Quantidade"]
        fig_tipo = px.pie(
            df_tipo,
            names="Tipo",
            values="Quantidade",
            title="<b>Distribuição por Tipo de Contratação</b>",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig_tipo.update_layout(
            height=350,
            margin=dict(l=10, r=10, t=40, b=10),
            legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
        )
        st.plotly_chart(fig_tipo, use_container_width=True)

    with gcol4:
        # Gráfico: Necessidade de Parecer Jurídico
        df_par = df_f["Necessitará de Parecer Jurídico"].value_counts().reset_index()
        df_par.columns = ["Parecer Jurídico", "Quantidade"]
        fig_par = px.bar(
            df_par,
            x="Parecer Jurídico",
            y="Quantidade",
            color="Parecer Jurídico",
            color_discrete_sequence=["#3B82F6", "#10B981", "#64748B"],
            title="<b>Necessidade de Parecer Jurídico</b>",
            text="Quantidade",
        )
        fig_par.update_layout(
            height=350,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis_title=None,
            yaxis_title="Quantidade",
            showlegend=False,
        )
        fig_par.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(fig_par, use_container_width=True)


# ------------------------------------------------------------------ ABA 2: PONTOS DE ATENÇÃO
with tab_atencao:
    df_alertas = df_f[df_f["Ponto de Atenção"] != "-"].copy()

    if df_alertas.empty:
        st.info("Nenhum processo com ponto de atenção registrado para os filtros selecionados.")
    else:
        st.markdown(
            f"""
            <div style="margin-bottom: 1rem; color: #475569; font-size: 0.95rem;">
                Exibindo <b>{len(df_alertas)}</b> processo(s) que possuem observações críticas ou pontos de atenção registrados pela equipe:
            </div>
            """,
            unsafe_allow_html=True,
        )

        for _, row in df_alertas.iterrows():
            prio = row["Prioridade"]
            prio_color = "#EF4444" if prio == "Alta" else ("#F59E0B" if prio == "Média" else "#10B981")
            sei_str = row["Número SEI"] if row["Número SEI"] else "Não informado"
            sislog_str = row["Número da Contratação SISLOG"] if row["Número da Contratação SISLOG"] != "-" else "S/ SISLOG"
            resp_str = row["Responsável"] if row["Responsável"] != "Não informado" else "A definir"

            st.markdown(
                f"""
                <div style="background: white; border-radius: 8px; border: 1px solid #E2E8F0; border-left: 5px solid {prio_color}; padding: 1rem 1.25rem; margin-bottom: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                        <span style="font-weight: 600; font-size: 1.05rem; color: #1E293B;">
                            📦 {row['Objeto']}
                        </span>
                        <span style="background-color: {prio_color}15; color: {prio_color}; border: 1px solid {prio_color}40; padding: 0.2rem 0.6rem; border-radius: 6px; font-size: 0.8rem; font-weight: 600;">
                            Prioridade {prio}
                        </span>
                    </div>
                    <div style="background: #FEF3C7; border: 1px solid #FDE68A; border-radius: 6px; padding: 0.5rem 0.8rem; margin: 0.5rem 0; color: #92400E; font-size: 0.92rem;">
                        <b>⚠️ Ponto de Atenção:</b> {row['Ponto de Atenção']}
                    </div>
                    <div style="display: flex; gap: 1.5rem; flex-wrap: wrap; font-size: 0.85rem; color: #64748B; margin-top: 0.4rem;">
                        <span>🏢 <b>Unidade:</b> {row['Unidade Demandante']}</span>
                        <span>📑 <b>Tipo:</b> {row['Tipo']}</span>
                        <span>🔍 <b>Status:</b> {row['Status da Contratação']}</span>
                        <span>📋 <b>SEI:</b> <code>{sei_str}</code></span>
                        <span>🔢 <b>SISLOG:</b> {sislog_str}</span>
                        <span>👤 <b>Responsável:</b> {resp_str}</span>
                        <span>⚖️ <b>Parecer Jurídico:</b> {row['Necessitará de Parecer Jurídico']}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ------------------------------------------------------------------ ABA 3: TABELA DETALHADA
with tab_tabela:
    st.markdown(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
            <span style="color: #475569; font-size: 0.95rem;">
                Total de registros filtrados: <b>{len(df_f)}</b>
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Ordenar colunas para apresentação otimizada
    cols_order = [
        "Prioridade",
        "Unidade Demandante",
        "Objeto",
        "Tipo",
        "Status da Contratação",
        "Ponto de Atenção",
        "Número SEI",
        "Número da Contratação SISLOG",
        "Responsável",
        "Necessitará de Parecer Jurídico",
        "Prevista para 2026?",
    ]
    cols_presentes = [c for c in cols_order if c in df_f.columns]
    df_exibicao = df_f[cols_presentes].copy()

    st.dataframe(
        df_exibicao,
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config={
            "Prioridade": st.column_config.TextColumn("Prioridade", width="small"),
            "Unidade Demandante": st.column_config.TextColumn("Unidade", width="small"),
            "Objeto": st.column_config.TextColumn("Objeto da Contratação", width="large"),
            "Tipo": st.column_config.TextColumn("Tipo", width="medium"),
            "Status da Contratação": st.column_config.TextColumn("Status", width="medium"),
            "Ponto de Atenção": st.column_config.TextColumn("Ponto de Atenção", width="large"),
            "Número SEI": st.column_config.TextColumn("Processo SEI", width="medium"),
            "Número da Contratação SISLOG": st.column_config.TextColumn("SISLOG", width="small"),
            "Responsável": st.column_config.TextColumn("Responsável", width="small"),
            "Necessitará de Parecer Jurídico": st.column_config.TextColumn("Parecer Jurídico", width="small"),
            "Prevista para 2026?": st.column_config.TextColumn("Prev. 2026?", width="small"),
        },
    )

    # Botão de exportação para Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_exibicao.to_excel(writer, index=False, sheet_name="Contratações 2026")
    excel_data = output.getvalue()

    st.download_button(
        label="📥 Exportar Dados para Excel (.xlsx)",
        data=excel_data,
        file_name="Acompanhamento_Contratacoes_2026.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
