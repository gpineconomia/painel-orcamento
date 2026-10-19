"""Página: Planejamento vs IPOF — Conciliação entre a Planilha e os dados oficiais do SAP BO."""
from __future__ import annotations

import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import brl, num, style, PALETTE
import common
import ploa_ipof_data

# ------------------------------------------------------------------ CARREGAMENTO DOS DADOS
ano_selecionado = st.sidebar.radio("Exercício em Análise", [2026, 2027], index=0, horizontal=True)

try:
    df_planilha_raw, updated_planilha, _ = common.get_data(ano=ano_selecionado)
    df_sap, updated_sap = ploa_ipof_data.load_sap_ipof_data()
except Exception as exc:
    st.error(f"Erro ao carregar dados para conciliação: {exc}")
    st.stop()

if df_planilha_raw.empty or df_sap.empty:
    st.warning("Não há dados suficientes da Planilha ou do SAP BO para conciliação.")
    st.stop()

# ------------------------------------------------------------------ BANNER SUPERIOR
dt_sap_str = updated_sap.strftime("%d/%m/%Y às %H:%M") if updated_sap else "N/D"
st.html(
    f"""<div style="background:#0F2A20; border-radius:12px; padding:12px 24px; margin-bottom:1.2rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 14px rgba(15,42,32,0.18);">
      <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
        ⚖️ Planejamento vs IPOF · Conciliação Orçamentária {ano_selecionado}
      </h2>
      <div style="font-size:0.85rem; color:#A7F3D0; text-align:right;">
        <strong>Fonte Oficial SAP BO:</strong> PDF PLOA (ID: 32837188)<br>
        <span style="font-size:0.75rem; color:#D1FAE5;">Sincronizado em: {dt_sap_str}</span>
      </div>
    </div>"""
)

# ------------------------------------------------------------------ TRATAMENTO E PARSING DE DADOS
# Identifica colunas relevantes na planilha de planejamento
col_item = [c for c in df_planilha_raw.columns if c.strip().lower() == "item"][0]
col_obj = [c for c in df_planilha_raw.columns if "objeto" in str(c).lower()][0]
col_uni = [c for c in df_planilha_raw.columns if "unidade" in str(c).lower()][0]
col_total = [c for c in df_planilha_raw.columns if "estimado total" in str(c).lower()][0]
col_ipof_planilha = [c for c in df_planilha_raw.columns if "ipof" in str(c).lower() and "situa" not in str(c).lower()][0]
col_proc_planilha = [c for c in df_planilha_raw.columns if "processo" in str(c).lower() and "sislog" not in str(c).lower()][0]
col_sit_planilha = [c for c in df_planilha_raw.columns if "situa" in str(c).lower() and "ipof" in str(c).lower()][0]

# Prepara base da Planilha desmembrando IPOFs (cada linha pode ter múltiplos IPOFs separados por quebra de linha)
linhas_desmembradas = []
for _, row in df_planilha_raw.iterrows():
    v_ipofs = str(row.get(col_ipof_planilha, ""))
    nums_ipof = re.findall(r"\d{10,15}", v_ipofs)
    
    val_total = pd.to_numeric(row.get(col_total), errors="coerce") or 0.0
    if val_total <= 0:
        continue

    item_id = str(row.get(col_item, "")).replace(".0", "")
    objeto = str(row.get(col_obj, ""))
    unidade = str(row.get(col_uni, ""))
    processo = str(row.get(col_proc_planilha, "")).strip().replace(".0", "")
    sit_planilha = str(row.get(col_sit_planilha, "")).strip()

    if not nums_ipof:
        linhas_desmembradas.append({
            "Item": item_id,
            "Unidade": unidade,
            "Objeto": objeto,
            "Valor_Estimado_Item": val_total,
            "Num_IPOF": "(Sem IPOF na Planilha)",
            "Processo_SEI_Planilha": processo,
            "Situacao_Planilha": sit_planilha or "(não informado)",
            "Qtd_IPOFs_No_Item": 0,
        })
    else:
        for ipof in nums_ipof:
            linhas_desmembradas.append({
                "Item": item_id,
                "Unidade": unidade,
                "Objeto": objeto,
                "Valor_Estimado_Item": val_total,
                "Num_IPOF": ipof,
                "Processo_SEI_Planilha": processo,
                "Situacao_Planilha": sit_planilha or "(não informado)",
                "Qtd_IPOFs_No_Item": len(nums_ipof),
            })

df_plan_exploded = pd.DataFrame(linhas_desmembradas)

# Filtra dados do SAP BO para o exercício de referência ou consolidado
# Considera o ano selecionado ou todas as parcelas ativas
df_sap_ano = df_sap[df_sap["Ano_Referencia"].isin([ano_selecionado, 0])].copy() if "Ano_Referencia" in df_sap.columns else df_sap.copy()
if df_sap_ano.empty:
    df_sap_ano = df_sap.copy()

# Agrupa valores do SAP BO por número de IPOF (um IPOF pode ter mais de uma parcela ou dotação)
sap_resumo = df_sap_ano.groupby("Num_IPOF_Oficial", as_index=False).agg({
    "Valor_Parcela_Oficial": "sum",
    "Situacao_IPOF_Oficial": "first",
    "Processo_SEI_Oficial": "first",
    "Acao_Oficial": "first",
    "Fonte_Oficial": "first",
    "Natureza_Despesa_Oficial": "first",
    "Descricao_Despesa_Oficial": "first",
})

# ------------------------------------------------------------------ CRUZAMENTO (JOIN)
# Cruzamento 1: O que está na Planilha com os dados do SAP BO
df_cruzado = pd.merge(
    df_plan_exploded,
    sap_resumo,
    left_on="Num_IPOF",
    right_on="Num_IPOF_Oficial",
    how="left"
)

# Classificação de Conformidade
def classificar_status(r):
    num_ipof = r["Num_IPOF"]
    val_plan = r["Valor_Estimado_Item"]
    val_sap = r["Valor_Parcela_Oficial"]
    
    if num_ipof == "(Sem IPOF na Planilha)":
        return "🔴 Sem IPOF na Planilha"
    if pd.isna(val_sap) or val_sap == 0:
        return "🟡 IPOF não localizado no SAP BO"
    
    # Se o item tem múltiplos IPOFs, avaliamos por proximidade
    dif = abs(val_plan - val_sap)
    if dif < 1.0 or (r["Qtd_IPOFs_No_Item"] > 1 and val_sap > 0):
        return "🟢 Conforme Oficial"
    elif val_sap > val_plan:
        return "🔵 Oficial Maior que Estimado"
    else:
        return "🟠 Oficial Menor que Estimado"

df_cruzado["Status_Conformidade"] = df_cruzado.apply(classificar_status, axis=1)

# ------------------------------------------------------------------ FILTROS NA BARRA LATERAL
with st.sidebar:
    st.header("Filtros de Conciliação")
    
    opts_unidade = sorted([str(x) for x in df_cruzado["Unidade"].unique() if pd.notna(x)])
    sel_unidade = st.multiselect("Unidade", opts_unidade, key="f_conc_uni")
    
    opts_status = sorted(df_cruzado["Status_Conformidade"].unique())
    sel_status = st.multiselect("Status de Conformidade", opts_status, key="f_conc_status")
    
    busca_conc = st.text_input("🔎 Buscar (Objeto, IPOF, Processo SEI, Item)", key="f_conc_busca")

df_view = df_cruzado.copy()
if sel_unidade:
    df_view = df_view[df_view["Unidade"].isin(sel_unidade)]
if sel_status:
    df_view = df_view[df_view["Status_Conformidade"].isin(sel_status)]
if busca_conc:
    m = (
        df_view["Objeto"].astype(str).str.contains(busca_conc, case=False, na=False) |
        df_view["Num_IPOF"].astype(str).str.contains(busca_conc, case=False, na=False) |
        df_view["Processo_SEI_Planilha"].astype(str).str.contains(busca_conc, case=False, na=False) |
        df_view["Item"].astype(str).str.contains(busca_conc, case=False, na=False)
    )
    df_view = df_view[m]

# ------------------------------------------------------------------ KPIS NO TOPO
k1, k2, k3, k4 = st.columns(4)

total_planejado_itens = df_planilha_raw[col_total].sum()
itens_com_ipof = df_plan_exploded[df_plan_exploded["Num_IPOF"] != "(Sem IPOF na Planilha)"]["Item"].nunique()
itens_totais = df_planilha_raw[col_item].nunique()
pct_cobertura = (itens_com_ipof / itens_totais * 100) if itens_totais else 0

ipofs_encontrados_sap = df_cruzado[df_cruzado["Valor_Parcela_Oficial"].notna()]["Num_IPOF"].nunique()
total_valor_oficial_casado = df_cruzado["Valor_Parcela_Oficial"].fillna(0).sum()

with k1:
    st.markdown(
        f'<div class="kpi"><div class="label">Total Estimado ({ano_selecionado})</div>'
        f'<div class="value">{brl(total_planejado_itens)}</div>'
        f'<div class="sub">{num(itens_totais)} despesas na planilha</div></div>',
        unsafe_allow_html=True
    )
with k2:
    st.markdown(
        f'<div class="kpi"><div class="label">Cobertura de IPOFs</div>'
        f'<div class="value">{pct_cobertura:.1f}%</div>'
        f'<div class="sub">{itens_com_ipof} de {itens_totais} itens c/ IPOF informado</div></div>',
        unsafe_allow_html=True
    )
with k3:
    st.markdown(
        f'<div class="kpi"><div class="label">IPOFs Localizados no SAP</div>'
        f'<div class="value">{ipofs_encontrados_sap}</div>'
        f'<div class="sub">Convalidados na base oficial do Estado</div></div>',
        unsafe_allow_html=True
    )
with k4:
    st.markdown(
        f'<div class="kpi"><div class="label">Valor Oficial Validado</div>'
        f'<div class="value">{brl(total_valor_oficial_casado)}</div>'
        f'<div class="sub">Total de parcelas registradas no SAP BO</div></div>',
        unsafe_allow_html=True
    )

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ ABAS DETALHADAS
tab_tabela, tab_graficos, tab_sap_sobras = st.tabs([
    "📋 Tabela de Conciliação Cruzada",
    "📊 Diagnóstico Visual de Aderência",
    "🔍 IPOFs no SAP BO sem Vínculo na Planilha"
])

with tab_tabela:
    st.subheader("Confronto: Estimativa da Unidade vs Registro Oficial no SAP BO")
    
    cols_display = [
        "Item", "Unidade", "Objeto", "Num_IPOF", 
        "Valor_Estimado_Item", "Valor_Parcela_Oficial", "Status_Conformidade",
        "Situacao_IPOF_Oficial", "Acao_Oficial", "Natureza_Despesa_Oficial"
    ]
    
    tabela_fmt = df_view[cols_display].copy()
    tabela_fmt = tabela_fmt.rename(columns={
        "Valor_Estimado_Item": f"Estimado {ano_selecionado} (R$)",
        "Valor_Parcela_Oficial": "Oficial SAP BO (R$)",
        "Num_IPOF": "Nº IPOF",
        "Status_Conformidade": "Status",
        "Situacao_IPOF_Oficial": "Situação SAP BO",
        "Acao_Oficial": "Ação Oficial",
        "Natureza_Despesa_Oficial": "Natureza Despesa"
    })
    
    st.dataframe(
        tabela_fmt,
        use_container_width=True,
        hide_index=True,
        column_config={
            f"Estimado {ano_selecionado} (R$)": st.column_config.NumberColumn(format="R$ %,.2f"),
            "Oficial SAP BO (R$)": st.column_config.NumberColumn(format="R$ %,.2f"),
        }
    )

with tab_graficos:
    g1, g2 = st.columns(2)
    
    with g1:
        st.subheader("Distribuição por Status de Conformidade")
        status_counts = df_cruzado["Status_Conformidade"].value_counts().reset_index()
        status_counts.columns = ["Status", "Quantidade"]
        
        cores_map = {
            "🟢 Conforme Oficial": "#10B981",
            "🔴 Sem IPOF na Planilha": "#EF4444",
            "🟡 IPOF não localizado no SAP BO": "#F59E0B",
            "🔵 Oficial Maior que Estimado": "#3B82F6",
            "🟠 Oficial Menor que Estimado": "#F97316",
        }
        fig_status = px.pie(
            status_counts,
            values="Quantidade",
            names="Status",
            color="Status",
            color_discrete_map=cores_map,
            hole=0.45
        )
        fig_status = style(fig_status, height=360)
        st.plotly_chart(fig_status, use_container_width=True)

    with g2:
        st.subheader("Aderência Oficial por Unidade")
        uni_conf = df_cruzado.groupby(["Unidade", "Status_Conformidade"]).size().reset_index(name="Qtd")
        fig_uni = px.bar(
            uni_conf,
            x="Unidade",
            y="Qtd",
            color="Status_Conformidade",
            color_discrete_map=cores_map,
            barmode="stack"
        )
        fig_uni = style(fig_uni, height=360)
        st.plotly_chart(fig_uni, use_container_width=True)

with tab_sap_sobras:
    st.subheader("IPOFs Ativos no SAP BO que não foram mapeados na Planilha")
    st.caption("Esta listagem aponta despesas registradas oficialmente no sistema orçamentário estadual que não possuem correspondência direta nos itens da planilha.")
    
    ipofs_na_planilha = set(df_plan_exploded["Num_IPOF"].unique())
    df_sobras_sap = sap_resumo[~sap_resumo["Num_IPOF_Oficial"].isin(ipofs_na_planilha)].copy()
    
    st.markdown(f"**Total de IPOFs oficiais sem vínculo:** {num(len(df_sobras_sap))} | **Valor Total:** {brl(df_sobras_sap['Valor_Parcela_Oficial'].sum())}")
    
    cols_sobra = ["Num_IPOF_Oficial", "Processo_SEI_Oficial", "Situacao_IPOF_Oficial", "Valor_Parcela_Oficial", "Acao_Oficial", "Descricao_Despesa_Oficial"]
    st.dataframe(
        df_sobras_sap[cols_sobra].rename(columns={
            "Num_IPOF_Oficial": "Nº IPOF (SAP BO)",
            "Processo_SEI_Oficial": "Processo SEI",
            "Situacao_IPOF_Oficial": "Situação",
            "Valor_Parcela_Oficial": "Valor Oficial (R$)",
            "Acao_Oficial": "Ação Orçamentária",
            "Descricao_Despesa_Oficial": "Descrição"
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Valor Oficial (R$)": st.column_config.NumberColumn(format="R$ %,.2f"),
        }
    )
