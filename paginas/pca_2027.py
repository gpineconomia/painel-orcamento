"""Página: Plano de Contratações Anual — PCA 2027 (Google Sheets - SETRAC)."""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import common
from common import style, PALETTE
import pca_data

TZ_BRASILIA = timezone(timedelta(hours=-3))


def fmt_brl(v: float | int | None) -> str:
    """Formata valor monetário no padrão brasileiro ABNT 2 (ex: R$ 1.000,00)."""
    if v is None or pd.isna(v) or v == "":
        return "-"
    try:
        val = float(v)
        sign = "-" if val < 0 else ""
        a = abs(val)
        s = f"{a:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {sign}{s}"
    except Exception:
        return str(v)


def fmt_card_mi(v: float | int | None) -> str:
    """Formata valor abreviado em Mi / Bi com 2 casas decimais para cards (ex: R$ 42,28 Mi)."""
    if v is None or pd.isna(v) or v == 0:
        return "R$ 0,00"
    try:
        val = float(v)
        sign = "-" if val < 0 else ""
        a = abs(val)
        if a >= 1e9:
            s = f"{a / 1e9:,.2f} Bi"
        elif a >= 1e6:
            s = f"{a / 1e6:,.2f} Mi"
        elif a >= 1e3:
            s = f"{a / 1e3:,.2f} mil"
        else:
            s = f"{a:,.2f}"
        return "R$ " + sign + s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(v)

# ------------------------------------------------------------------ CARREGAMENTO DOS DADOS DO PCA
try:
    df_pca_raw, updated_pca = pca_data.load_pca_data()
except Exception as exc:
    st.error(f"Erro ao carregar os dados do PCA 2027: {exc}")
    st.stop()

if df_pca_raw.empty:
    st.warning("Nenhum dado encontrado na aba 'PCA 2027' da planilha compartilhada do Google Drive.")
    st.stop()

# ------------------------------------------------------------------ BANNER SUPERIOR
dt_pca_str = updated_pca.strftime("%d/%m/%Y às %H:%M") if updated_pca else "N/D"

st.html(
    f"""<div style="background:#0F2A20; border-radius:12px; padding:14px 24px; margin-bottom:1.2rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 14px rgba(15,42,32,0.18);">
      <div>
        <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
          📑 Plano de Contratações Anual · PCA 2027
        </h2>
        <div style="font-size:0.82rem; color:#A7F3D0; margin-top:4px;">
          SETRAC / Secretaria da Economia de Goiás &nbsp;|&nbsp; Planejamento de Contratações, Prazos e Deadlines
        </div>
      </div>
      <div style="font-size:0.85rem; color:#A7F3D0; text-align:right;">
        <strong>Fonte:</strong> Google Sheets (SETRAC/PCA 2027)<br>
        <span style="font-size:0.75rem; color:#D1FAE5;">Sincronizado em: {dt_pca_str}</span>
      </div>
    </div>"""
)

# ------------------------------------------------------------------ FILTROS NA BARRA LATERAL
with st.sidebar:
    st.header("Filtros · PCA 2027")

    if st.button("🔄 Atualizar dados do PCA", width="stretch", key="btn_refresh_pca"):
        with st.spinner("Conectando ao Google Drive e baixando versão mais recente..."):
            pca_data.download_pca_workbook()
            st.cache_data.clear()
            st.rerun()

    busca = st.text_input("🔎 Buscar (Objeto, Processo SEI, Contrato, Unidade)", key="f_pca_busca")

    # 1. Unidades Demandantes
    opts_uni = sorted([u for u in df_pca_raw["Unidade_Demandante"].dropna().unique() if str(u).strip() != ""])
    sel_uni = st.multiselect("Unidade Demandante", opts_uni, key="f_pca_uni")

    # 2. Providência em 2027
    opts_prov = sorted([p for p in df_pca_raw["Providencia_2027"].dropna().unique() if str(p).strip() != ""])
    sel_prov = st.multiselect("Qual providência em 2027?", opts_prov, key="f_pca_prov")

    # 3. Status da Contratação
    opts_status = sorted([s for s in df_pca_raw["Status_Contratacao"].dropna().unique() if str(s).strip() != ""])
    sel_status = st.multiselect("Status da Contratação", opts_status, key="f_pca_status")

    # 4. Modalidade
    opts_mod = sorted([m for m in df_pca_raw["Modalidade"].dropna().unique() if str(m).strip() != ""])
    sel_mod = st.multiselect("Modalidade de Contratação", opts_mod, key="f_pca_mod")

    # 5. Possui Contrato Vigente?
    tipo_contrato = st.radio(
        "Contrato Vigente:",
        ["Todos", "Com Contrato Vigente", "Sem Contrato (Novas Demandas)"],
        key="f_pca_contrato_radio"
    )

    # 6. Deadlines de Contratação
    filtro_deadline = st.selectbox(
        "Janela de Deadline:",
        [
            "Todos os Prazos",
            "Prazos Vencendo em 2026",
            "Prazos Vencendo em 2027",
            "Prazos Próximos (Até 90 dias)",
            "Sem Deadline Cadastrado"
        ],
        key="f_pca_deadline_sel"
    )

# ------------------------------------------------------------------ APLICAÇÃO DOS FILTROS
df_view = df_pca_raw.copy()

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

hoje_ts = pd.Timestamp(datetime.now(TZ_BRASILIA).date())

if filtro_deadline == "Prazos Vencendo em 2026":
    df_view = df_view[df_view["Deadline_Contratacao"].dt.year == 2026]
elif filtro_deadline == "Prazos Vencendo em 2027":
    df_view = df_view[df_view["Deadline_Contratacao"].dt.year == 2027]
elif filtro_deadline == "Prazos Próximos (Até 90 dias)":
    limite_90 = hoje_ts + pd.Timedelta(days=90)
    df_view = df_view[(df_view["Deadline_Contratacao"] >= hoje_ts) & (df_view["Deadline_Contratacao"] <= limite_90)]
elif filtro_deadline == "Sem Deadline Cadastrado":
    df_view = df_view[df_view["Deadline_Contratacao"].isna()]

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

# ------------------------------------------------------------------ KPIS NO TOPO
tot_itens = len(df_view)
soma_est_2027 = df_view["Valor_Estimado_2027"].sum()
soma_total_est = df_view["Valor_Total_Estimado"].sum()

demandam_acao = len(df_view[df_view["Providencia_2027"].str.upper().str.contains("NOVA|PRORROG", na=False)])
em_andamento = len(df_view[df_view["Status_Contratacao"].str.upper().str.contains("ANDAMENTO", na=False)])
com_contrato = len(df_view[df_view["Tem_Contrato_Vigente"]])

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    common.kpi(c1, "Contratações no PCA", f"{tot_itens}", f"de {len(df_pca_raw)} mapeadas")
with c2:
    common.kpi(c2, "Estimado para 2027", fmt_card_mi(soma_est_2027), fmt_brl(soma_est_2027))
with c3:
    common.kpi(c3, "Demandam Providência", f"{demandam_acao}", "Nova contratação / Prorrogação", warn=demandam_acao > 0)
with c4:
    common.kpi(c4, "Em Andamento", f"{em_andamento}", "Processos em tramitação")
with c5:
    common.kpi(c5, "Contratos Vigentes", f"{com_contrato}", "Com contrato formal ativo")

st.markdown("<div style='margin-bottom: 1.2rem;'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ GRÁFICOS VISUAIS
col_g1, col_g2 = st.columns([1.3, 1])

with col_g1:
    # Gráfico 1: Top Unidades Demandantes por Valor Estimado para 2027
    df_uni = (
        df_view.groupby("Unidade_Demandante")["Valor_Estimado_2027"]
        .sum()
        .reset_index()
        .sort_values(by="Valor_Estimado_2027", ascending=True)
    )
    # Pega top 10 para clareza
    df_uni_top = df_uni.tail(10)

    fig_uni = px.bar(
        df_uni_top,
        x="Valor_Estimado_2027",
        y="Unidade_Demandante",
        orientation="h",
        title="Top 10 Unidades Demandantes por Valor Estimado 2027",
        text=df_uni_top["Valor_Estimado_2027"].apply(fmt_card_mi),
        color_discrete_sequence=["#047857"],
    )
    fig_uni.update_traces(textposition="outside", cliponaxis=False)
    fig_uni.update_layout(
        xaxis_title="Valor Estimado 2027",
        yaxis_title="",
        margin=dict(l=10, r=40, t=50, b=10),
        height=360,
    )
    style(fig_uni, height=360)
    st.plotly_chart(fig_uni, use_container_width=True)

with col_g2:
    # Gráfico 2: Distribuição de Providências em 2027
    df_prov = df_view["Providencia_2027"].value_counts().reset_index()
    df_prov.columns = ["Providencia", "Qtd"]

    cores_map = {
        "FAZER NOVA CONTRATAÇÃO": "#F59E0B",
        "PRORROGAR": "#3B82F6",
        "SEM PROVIDÊNCIAS": "#10B981",
        "NÃO CONTRATAR NOVAMENTE": "#6B7280",
    }
    cores_lista = [cores_map.get(str(p).upper(), "#047857") for p in df_prov["Providencia"]]

    fig_prov = go.Figure(
        data=[
            go.Pie(
                labels=df_prov["Providencia"],
                values=df_prov["Qtd"],
                hole=0.55,
                marker=dict(colors=cores_lista),
                textinfo="label+value",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig_prov.update_layout(
        title="Qual Providência Requerida em 2027?",
        showlegend=False,
        margin=dict(l=10, r=10, t=50, b=10),
        height=360,
    )
    style(fig_prov, height=360)
    st.plotly_chart(fig_prov, use_container_width=True)

# ------------------------------------------------------------------ SEGUNDA LINHA DE GRÁFICOS: MODALIDADE E DEADLINES
col_g3, col_g4 = st.columns([1, 1.3])

with col_g3:
    # Gráfico de Modalidades
    df_mod = df_view["Modalidade"].value_counts().head(6).reset_index()
    df_mod.columns = ["Modalidade", "Qtd"]
    fig_mod = px.bar(
        df_mod,
        x="Modalidade",
        y="Qtd",
        title="Contratações por Modalidade",
        text="Qtd",
        color_discrete_sequence=["#10B981"],
    )
    fig_mod.update_traces(textposition="outside")
    fig_mod.update_layout(yaxis_title="Quantidade", xaxis_title="", height=320)
    style(fig_mod, height=320)
    st.plotly_chart(fig_mod, use_container_width=True)

with col_g4:
    # Deadlines por Trimestre/Ano
    df_deadlines = df_view.dropna(subset=["Deadline_Contratacao"]).copy()
    if not df_deadlines.empty:
        df_deadlines["Periodo_Deadline"] = df_deadlines["Deadline_Contratacao"].dt.to_period("Q").astype(str)
        df_dead_grp = (
            df_deadlines.groupby(["Periodo_Deadline", "Providencia_2027"])
            .size()
            .reset_index(name="Qtd")
            .sort_values(by="Periodo_Deadline")
        )
        # Limita aos próximos períodos relevantes
        fig_dead = px.bar(
            df_dead_grp,
            x="Periodo_Deadline",
            y="Qtd",
            color="Providencia_2027",
            title="Cronograma de Deadlines da SETRAC (por Trimestre)",
            barmode="stack",
            color_discrete_map=cores_map,
        )
        fig_dead.update_layout(xaxis_title="Trimestre do Prazo Limite", yaxis_title="Contratações", height=320)
        style(fig_dead, height=320)
        st.plotly_chart(fig_dead, use_container_width=True)
    else:
        st.info("Nenhum registro com deadline informado no filtro atual.")

# ------------------------------------------------------------------ TABELA ANALÍTICA DO PCA
st.markdown("### 📋 Tabela Analítica de Contratações (PCA 2027)")

# Formatação para exibição
df_table = df_view.copy()
df_table["Item"] = df_table["Item"].apply(lambda x: str(int(x)) if pd.notna(x) else "-")
df_table["Estimado 2027"] = df_table["Valor_Estimado_2027"].apply(fmt_brl)
df_table["Valor Total"] = df_table["Valor_Total_Estimado"].apply(fmt_brl)
df_table["Deadline SETRAC"] = df_table["Deadline_Contratacao"].apply(
    lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else "-"
)
df_table["Início SETRAC"] = df_table["Data_Inicio_SETRAC"].apply(
    lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else "-"
)

cols_display = [
    "Item",
    "Processo_SEI",
    "Contrato_Vigente",
    "Objeto_Resumido",
    "Unidade_Demandante",
    "Providencia_2027",
    "Status_Contratacao",
    "Modalidade",
    "Deadline SETRAC",
    "Estimado 2027",
    "Valor Total",
]

col_renames = {
    "Processo_SEI": "Processo SEI",
    "Contrato_Vigente": "Contrato Vigente",
    "Objeto_Resumido": "Objeto",
    "Unidade_Demandante": "Unidade Demandante",
    "Providencia_2027": "Providência 2027",
    "Status_Contratacao": "Status",
}

df_show = df_table[cols_display].rename(columns=col_renames)

st.dataframe(
    df_show,
    use_container_width=True,
    hide_index=True,
    height=480,
    column_config={
        "Item": st.column_config.TextColumn("Nº", width="small"),
        "Processo SEI": st.column_config.TextColumn("Processo SEI", width="medium"),
        "Contrato Vigente": st.column_config.TextColumn("Contrato", width="small"),
        "Objeto": st.column_config.TextColumn("Objeto da Contratação", width="large"),
        "Unidade Demandante": st.column_config.TextColumn("Unidade Demandante", width="medium"),
        "Providência 2027": st.column_config.TextColumn("Providência 2027", width="medium"),
        "Status": st.column_config.TextColumn("Status", width="small"),
        "Modalidade": st.column_config.TextColumn("Modalidade", width="small"),
        "Deadline SETRAC": st.column_config.TextColumn("Deadline", width="small"),
        "Estimado 2027": st.column_config.TextColumn("Estimado 2027", width="medium"),
        "Valor Total": st.column_config.TextColumn("Valor Total", width="medium"),
    },
)

# ------------------------------------------------------------------ DOWNLOAD EXCEL / CSV
col_down1, col_down2, _ = st.columns([1, 1, 3])

with col_down1:
    buffer_csv = io.StringIO()
    df_show.to_csv(buffer_csv, index=False, sep=";", encoding="utf-8-sig")
    st.download_button(
        label="📥 Baixar Tabela em CSV",
        data=buffer_csv.getvalue().encode("utf-8-sig"),
        file_name=f"PCA_2027_SETRAC_{datetime.now():%Y%m%d}.csv",
        mime="text/csv",
        use_container_width=True,
    )

with col_down2:
    buffer_xlsx = io.BytesIO()
    with pd.ExcelWriter(buffer_xlsx, engine="openpyxl") as writer:
        df_show.to_excel(writer, index=False, sheet_name="PCA 2027")
    st.download_button(
        label="📊 Baixar Tabela em Excel",
        data=buffer_xlsx.getvalue(),
        file_name=f"PCA_2027_SETRAC_{datetime.now():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ------------------------------------------------------------------ DETALHAMENTO DE ITEM SELECIONADO
st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
with st.expander("🔍 Inspecionar Detalhamento Completo do Objeto de um Item do PCA"):
    if not df_view.empty:
        opcoes_map = {}
        for idx_row, r in df_view.iterrows():
            if pd.notna(r.get("Item")):
                try:
                    item_num_str = f"Item {int(r['Item'])}"
                except Exception:
                    item_num_str = f"Item {r['Item']}"
            else:
                item_num_str = f"Item (L.{idx_row + 1})"
            label = f"{item_num_str} — {r['Objeto_Resumido']} ({r['Unidade_Demandante']})"
            opcoes_map[label] = r

        sel_item_str = st.selectbox("Selecione o Item para inspecionar:", list(opcoes_map.keys()), key="sel_item_pca")
        if sel_item_str:
            row_item = opcoes_map[sel_item_str]

            ci1, ci2 = st.columns([2, 1])
            with ci1:
                st.markdown(f"#### {row_item['Objeto_Resumido']}")
                st.markdown(f"**Unidade Demandante:** {row_item['Unidade_Demandante']} *(Superior: {row_item['Unidade_Superior']})*")
                st.markdown(f"**Detalhamento Completo do Objeto:**\n\n{row_item['Detalhamento_Objeto'] or '(Não detalhado)'}")

            with ci2:
                deadline_str = row_item['Deadline_Contratacao'].strftime('%d/%m/%Y') if pd.notna(row_item['Deadline_Contratacao']) else '-'
                st.markdown(
                    f"""<div style="background:#F6FAF8; border:1px solid #DCEBE3; border-radius:12px; padding:16px;">
                      <div style="font-size:0.8rem; color:#5B7A6C; text-transform:uppercase; font-weight:600;">Resumo da Demanda</div>
                      <div style="margin-top:8px; font-size:0.9rem;"><strong>Processo SEI:** {row_item['Processo_SEI'] or '-'}</div>
                      <div style="margin-top:4px; font-size:0.9rem;"><strong>Contrato Vigente:** {row_item['Contrato_Vigente']}</div>
                      <div style="margin-top:4px; font-size:0.9rem;"><strong>Modalidade:** {row_item['Modalidade']}</div>
                      <div style="margin-top:4px; font-size:0.9rem;"><strong>Providência 2027:** <span style="font-weight:600; color:#047857;">{row_item['Providencia_2027']}</span></div>
                      <div style="margin-top:4px; font-size:0.9rem;"><strong>Status:** {row_item['Status_Contratacao']}</div>
                      <div style="margin-top:4px; font-size:0.9rem;"><strong>Deadline SETRAC:** {deadline_str}</div>
                      <div style="margin-top:8px; font-size:1.05rem; font-weight:700; color:#0F2A20;">Estimado 2027: {fmt_brl(row_item['Valor_Estimado_2027'])}</div>
                      <div style="font-size:0.85rem; color:#5B7A6C;">Total Contratação: {fmt_brl(row_item['Valor_Total_Estimado'])}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
