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
    """Formata valor abreviado em Mi / Bi com 2 casas decimais para cards (ex: R$ 493,72 Mi)."""
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


# ------------------------------------------------------------------ CARREGAMENTO DOS DADOS (PLOA 2027)
ano_selecionado = 2027

try:
    df_planilha_raw, updated_planilha, _ = common.get_data(ano=2027)
    df_sap, updated_sap = ploa_ipof_data.load_sap_ipof_data()
except Exception as exc:
    st.error(f"Erro ao carregar dados para conciliação: {exc}")
    st.stop()

if df_planilha_raw.empty or df_sap.empty:
    st.warning("Não há dados suficientes da Planilha ou do SIAFIC para conciliação.")
    st.stop()

# ------------------------------------------------------------------ BANNER SUPERIOR
dt_sap_str = updated_sap.strftime("%d/%m/%Y às %H:%M") if updated_sap else "N/D"
st.html(
    f"""<div style="background:#0F2A20; border-radius:12px; padding:12px 24px; margin-bottom:1.2rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 14px rgba(15,42,32,0.18);">
      <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
        ⚖️ Planejamento vs IPOF · Conciliação Orçamentária 2027
      </h2>
      <div style="font-size:0.85rem; color:#A7F3D0; text-align:right;">
        <strong>Fonte Oficial SIAFIC:</strong> PDF PLOA (ID: 32837188)<br>
        <span style="font-size:0.75rem; color:#D1FAE5;">Sincronizado em: {dt_sap_str}</span>
      </div>
    </div>"""
)

# ------------------------------------------------------------------ TRATAMENTO E PARSING DE DADOS
# Filtra permanentemente itens da planilha cuja Situação seja 'Excluído'
col_sit_item = [c for c in df_planilha_raw.columns if "situa" in str(c).lower() and "ipof" not in str(c).lower()]
if col_sit_item:
    c_sit = col_sit_item[0]
    df_planilha_raw = df_planilha_raw[
        ~df_planilha_raw[c_sit].astype(str).str.lower().str.contains("exclu")
    ].copy()

# Filtra permanentemente despesas com Ação 4144 ou 4145 na planilha (Folha de Pagamento)
col_acao_plan = [c for c in df_planilha_raw.columns if str(c).strip().lower() in ["ação", "acao", "ao"]]
if col_acao_plan:
    df_planilha_raw = df_planilha_raw[
        ~df_planilha_raw[col_acao_plan[0]].astype(str).str.contains("4144|4145", regex=True)
    ].copy()

# Identifica colunas relevantes na planilha de planejamento
col_item = [c for c in df_planilha_raw.columns if c.strip().lower() == "item"][0]
col_obj = [c for c in df_planilha_raw.columns if "objeto" in str(c).lower()][0]
col_uni = [c for c in df_planilha_raw.columns if "unidade" in str(c).lower()][0]
col_total = [c for c in df_planilha_raw.columns if "estimado total" in str(c).lower()][0]
col_ipof_planilha = [c for c in df_planilha_raw.columns if "ipof" in str(c).lower() and "situa" not in str(c).lower()][0]
col_proc_planilha = [c for c in df_planilha_raw.columns if "processo" in str(c).lower() and "sislog" not in str(c).lower()][0]
col_sit_planilha = [c for c in df_planilha_raw.columns if "situa" in str(c).lower() and "ipof" in str(c).lower()][0]

col_contrato_list = [c for c in df_planilha_raw.columns if "contrato" in str(c).lower() and "global" not in str(c).lower()]
col_contrato = col_contrato_list[0] if col_contrato_list else None

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

    contrato = ""
    if col_contrato and pd.notna(row.get(col_contrato)):
        c_raw = str(row.get(col_contrato)).replace("_x000D_", " ").replace("\xa0", " ").strip()
        if c_raw.lower() not in ["nan", "none", "<na>"]:
            contrato = c_raw.replace(".0", "")

    if not nums_ipof:
        linhas_desmembradas.append({
            "Item": item_id,
            "Unidade": unidade,
            "Objeto": objeto,
            "Contrato": contrato,
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
                "Contrato": contrato,
                "Valor_Estimado_Item": val_total,
                "Num_IPOF": ipof,
                "Processo_SEI_Planilha": processo,
                "Situacao_Planilha": sit_planilha or "(não informado)",
                "Qtd_IPOFs_No_Item": len(nums_ipof),
            })

df_plan_exploded = pd.DataFrame(linhas_desmembradas)

# Base oficial de IPOFs do SIAFIC (PDF PLOA)
df_sap_ano = df_sap.copy()

# Desconsidera linhas de resumo/soma e IPOFs não numéricos do relatório oficial
df_sap_ano = df_sap_ano[
    df_sap_ano["Num_IPOF_Oficial"].astype(str).str.isdigit()
    & (~df_sap_ano["Num_IPOF_Oficial"].astype(str).str.lower().str.contains("soma|total"))
].copy()

# Desconsidera IPOFs com ação orçamentária 4144, 4145 ou em branco/não encontrada
def is_acao_invalida(val: object) -> bool:
    s = str(val).strip().lower()
    if not s or s in ["nan", "none", "<na>", "", "0", "0.0", "0000", "0000 - nao encontrada"]:
        return True
    if "4144" in s or "4145" in s:
        return True
    return False

df_sap_ano = df_sap_ano[~df_sap_ano["Acao_Oficial"].apply(is_acao_invalida)].copy()

def extrair_procs(val: object) -> list[str]:
    """Extrai sequências numéricas de 10 a 16 dígitos correspondentes a Processos SEI."""
    if val is None or pd.isna(val):
        return []
    return re.findall(r"\d{10,16}", str(val))


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

# Dicionários de indexação rápida do SIAFIC
sap_by_ipof = sap_resumo.set_index("Num_IPOF_Oficial").to_dict(orient="index")

sap_by_proc: dict[str, dict] = {}
for _, row_sap in df_sap_ano.iterrows():
    procs_sap = extrair_procs(row_sap["Processo_SEI_Oficial"])
    for p in procs_sap:
        if p not in sap_by_proc:
            sap_by_proc[p] = {
                "ipofs": set(),
                "valor_total": 0.0,
                "situacoes": set(),
                "acoes": set(),
                "naturezas": set(),
                "descricoes": set(),
            }
        sap_by_proc[p]["ipofs"].add(str(row_sap["Num_IPOF_Oficial"]))
        sap_by_proc[p]["valor_total"] += float(row_sap.get("Valor_Parcela_Oficial", 0) or 0)
        if pd.notna(row_sap.get("Situacao_IPOF_Oficial")) and str(row_sap["Situacao_IPOF_Oficial"]).strip():
            sap_by_proc[p]["situacoes"].add(str(row_sap["Situacao_IPOF_Oficial"]).strip())
        if pd.notna(row_sap.get("Acao_Oficial")) and str(row_sap["Acao_Oficial"]).strip():
            sap_by_proc[p]["acoes"].add(str(row_sap["Acao_Oficial"]).strip())
        if pd.notna(row_sap.get("Natureza_Despesa_Oficial")) and str(row_sap["Natureza_Despesa_Oficial"]).strip():
            sap_by_proc[p]["naturezas"].add(str(row_sap["Natureza_Despesa_Oficial"]).strip())
        if pd.notna(row_sap.get("Descricao_Despesa_Oficial")) and str(row_sap["Descricao_Despesa_Oficial"]).strip():
            sap_by_proc[p]["descricoes"].add(str(row_sap["Descricao_Despesa_Oficial"]).strip())

# ------------------------------------------------------------------ CRUZAMENTO COMPLETO (IPOF + PROCESSO SEI)
linhas_cruzadas = []
for _, r_plan in df_plan_exploded.iterrows():
    ipof_val = str(r_plan["Num_IPOF"]).strip()
    val_plan = float(r_plan["Valor_Estimado_Item"] or 0)
    procs_item = extrair_procs(r_plan.get("Processo_SEI_Planilha", ""))
    
    # 1. Casamento direto por Número de IPOF
    if ipof_val != "(Sem IPOF na Planilha)" and ipof_val in sap_by_ipof:
        d_sap = sap_by_ipof[ipof_val]
        val_sap = float(d_sap.get("Valor_Parcela_Oficial") or 0)
        dif = abs(val_plan - val_sap)
        if dif < 1.0 or (r_plan["Qtd_IPOFs_No_Item"] > 1 and val_sap > 0):
            st_conf = "🟢 Conforme Oficial"
        elif val_sap > val_plan:
            st_conf = "🔵 Oficial Maior que Estimado"
        else:
            st_conf = "🟠 Oficial Menor que Estimado"
            
        linhas_cruzadas.append({
            **r_plan,
            "Valor_Parcela_Oficial": val_sap,
            "Situacao_IPOF_Oficial": d_sap.get("Situacao_IPOF_Oficial") or "-",
            "Acao_Oficial": d_sap.get("Acao_Oficial") or "-",
            "Natureza_Despesa_Oficial": d_sap.get("Natureza_Despesa_Oficial") or "-",
            "Descricao_Despesa_Oficial": d_sap.get("Descricao_Despesa_Oficial") or "-",
            "Status_Conformidade": st_conf,
            "IPOF_Encontrado_SIAFIC": ipof_val,
        })
    else:
        # 2. Casamento alternativo por Processo SEI
        procs_match = [p for p in procs_item if p in sap_by_proc]
        if procs_match:
            ipofs_enc = set()
            val_tot_proc = 0.0
            situacoes_proc = set()
            acoes_proc = set()
            naturezas_proc = set()
            descricoes_proc = set()
            
            for p in procs_match:
                info_p = sap_by_proc[p]
                ipofs_enc.update(info_p["ipofs"])
                val_tot_proc += info_p["valor_total"]
                situacoes_proc.update(info_p["situacoes"])
                acoes_proc.update(info_p["acoes"])
                naturezas_proc.update(info_p["naturezas"])
                descricoes_proc.update(info_p["descricoes"])
                
            ipofs_str = ", ".join(sorted(ipofs_enc))
            if ipof_val == "(Sem IPOF na Planilha)":
                num_ipof_exib = f"(Localizado: {ipofs_str})"
            else:
                num_ipof_exib = f"{ipof_val} (SIAFIC: {ipofs_str})"
                
            linhas_cruzadas.append({
                **r_plan,
                "Num_IPOF": num_ipof_exib,
                "Valor_Parcela_Oficial": val_tot_proc,
                "Situacao_IPOF_Oficial": ", ".join(sorted(situacoes_proc)) if situacoes_proc else "-",
                "Acao_Oficial": ", ".join(sorted(acoes_proc)) if acoes_proc else "-",
                "Natureza_Despesa_Oficial": ", ".join(sorted(naturezas_proc)) if naturezas_proc else "-",
                "Descricao_Despesa_Oficial": "; ".join(sorted(descricoes_proc)) if descricoes_proc else "-",
                "Status_Conformidade": "🟣 Localizado por Processo SEI",
                "IPOF_Encontrado_SIAFIC": ipofs_str,
            })
        else:
            # 3. Não localizado nem por IPOF nem por Processo SEI
            if ipof_val == "(Sem IPOF na Planilha)":
                st_conf = "🔴 Sem IPOF na Planilha"
            else:
                st_conf = "🟡 IPOF não localizado no SIAFIC"
                
            linhas_cruzadas.append({
                **r_plan,
                "Valor_Parcela_Oficial": None,
                "Situacao_IPOF_Oficial": "-",
                "Acao_Oficial": "-",
                "Natureza_Despesa_Oficial": "-",
                "Descricao_Despesa_Oficial": "-",
                "Status_Conformidade": st_conf,
                "IPOF_Encontrado_SIAFIC": "-",
            })

df_cruzado = pd.DataFrame(linhas_cruzadas)

# ------------------------------------------------------------------ FILTROS NA BARRA LATERAL
with st.sidebar:
    st.header("Filtros de Conciliação")
    
    opts_unidade = sorted([str(x) for x in df_cruzado["Unidade"].unique() if pd.notna(x)])
    sel_unidade = st.multiselect("Unidade", opts_unidade, key="f_conc_uni")
    
    opts_status = sorted(df_cruzado["Status_Conformidade"].unique())
    sel_status = st.multiselect("Status de Conformidade", opts_status, key="f_conc_status")
    
    busca_conc = st.text_input("🔎 Buscar (Objeto, Contrato, IPOF, Processo SEI, Item)", key="f_conc_busca")

df_view = df_cruzado.copy()
if sel_unidade:
    df_view = df_view[df_view["Unidade"].isin(sel_unidade)]
if sel_status:
    df_view = df_view[df_view["Status_Conformidade"].isin(sel_status)]
if busca_conc:
    m = (
        df_view["Objeto"].astype(str).str.contains(busca_conc, case=False, na=False) |
        df_view["Contrato"].astype(str).str.contains(busca_conc, case=False, na=False) |
        df_view["Num_IPOF"].astype(str).str.contains(busca_conc, case=False, na=False) |
        df_view["Processo_SEI_Planilha"].astype(str).str.contains(busca_conc, case=False, na=False) |
        df_view["Item"].astype(str).str.contains(busca_conc, case=False, na=False)
    )
    df_view = df_view[m]

# ------------------------------------------------------------------ KPIS NO TOPO
k1, k2, k3, k4 = st.columns(4)

total_planejado_itens = df_planilha_raw[col_total].sum()
itens_totais = df_planilha_raw[col_item].nunique()

# Itens da planilha conciliados com sucesso (IPOF ou Processo SEI)
itens_conciliados = df_cruzado[df_cruzado["Valor_Parcela_Oficial"].notna()]["Item"].nunique()
pct_cobertura = (itens_conciliados / itens_totais * 100) if itens_totais else 0

# Contagem de IPOFs oficiais únicos convalidados
ipofs_oficiais_casados = set()
for _, r_c in df_cruzado.iterrows():
    enc = str(r_c.get("IPOF_Encontrado_SIAFIC", ""))
    for ip in re.findall(r"\d{10,15}", enc):
        ipofs_oficiais_casados.add(ip)
ipofs_encontrados_sap = len(ipofs_oficiais_casados)

total_valor_oficial_casado = df_cruzado["Valor_Parcela_Oficial"].fillna(0).sum()

pct_cob_str = f"{pct_cobertura:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

with k1:
    st.markdown(
        f'<div class="kpi"><div class="label">Total Estimado ({ano_selecionado})</div>'
        f'<div class="value">{fmt_card_mi(total_planejado_itens)}</div>'
        f'<div class="sub">{num(itens_totais)} despesas na planilha</div></div>',
        unsafe_allow_html=True
    )
with k2:
    st.markdown(
        f'<div class="kpi"><div class="label">Cobertura Conciliada</div>'
        f'<div class="value">{pct_cobertura:.1f}%</div>'
        f'<div class="sub">{num(itens_conciliados)} de {num(itens_totais)} itens conciliados</div></div>',
        unsafe_allow_html=True
    )
with k3:
    st.markdown(
        f'<div class="kpi"><div class="label">IPOFs Localizados no SIAFIC</div>'
        f'<div class="value">{num(ipofs_encontrados_sap)}</div>'
        f'<div class="sub">Convalidados via IPOF ou Processo SEI</div></div>',
        unsafe_allow_html=True
    )
with k4:
    st.markdown(
        f'<div class="kpi"><div class="label">Valor Oficial Validado</div>'
        f'<div class="value">{fmt_card_mi(total_valor_oficial_casado)}</div>'
        f'<div class="sub">Total de parcelas registradas no SIAFIC</div></div>',
        unsafe_allow_html=True
    )

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ ABAS DETALHADAS
tab_tabela, tab_graficos, tab_sap_sobras = st.tabs([
    "📋 Tabela de Conciliação Cruzada",
    "📊 Diagnóstico Visual de Aderência",
    "🔍 IPOFs no SIAFIC sem Vínculo na Planilha"
])

col_est_header = f"Estimado {ano_selecionado} (R$)"
col_ofic_header = "Oficial SIAFIC (R$)"

with tab_tabela:
    st.subheader("Confronto: Estimativa da Unidade vs Registro Oficial no SIAFIC")
    
    # Ordenação por Item crescente (ordem natural: 1, 2, 3...)
    df_view_work = df_view.copy()
    df_view_work["_sort_item"] = pd.to_numeric(df_view_work["Item"], errors="coerce").fillna(999999)
    df_view_sorted = df_view_work.sort_values(by=["_sort_item", "Item"], ascending=True).copy()
    
    cols_display = [
        "Item", "Unidade", "Objeto", "Contrato", "Processo_SEI_Planilha", "Num_IPOF", 
        "Valor_Estimado_Item", "Valor_Parcela_Oficial", "Status_Conformidade",
        "Situacao_Planilha", "Situacao_IPOF_Oficial", "Acao_Oficial", "Natureza_Despesa_Oficial"
    ]
    
    tabela_fmt = df_view_sorted[cols_display].copy()
    
    # Formatação ABNT 2 (R$ X.XXX,XX)
    tabela_fmt[col_est_header] = tabela_fmt["Valor_Estimado_Item"].apply(fmt_brl)
    tabela_fmt[col_ofic_header] = tabela_fmt["Valor_Parcela_Oficial"].apply(fmt_brl)
    
    ordem_final = [
        "Item", "Unidade", "Objeto", "Contrato", "Processo_SEI_Planilha", "Num_IPOF",
        col_est_header, col_ofic_header, "Status_Conformidade",
        "Situacao_Planilha", "Situacao_IPOF_Oficial", "Acao_Oficial", "Natureza_Despesa_Oficial"
    ]
    
    tabela_exibicao = tabela_fmt[ordem_final].rename(columns={
        "Processo_SEI_Planilha": "Processo SEI",
        "Num_IPOF": "Nº IPOF",
        "Status_Conformidade": "Status",
        "Situacao_Planilha": "Situação Planilha",
        "Situacao_IPOF_Oficial": "Situação SIAFIC",
        "Acao_Oficial": "Ação Oficial",
        "Natureza_Despesa_Oficial": "Natureza Despesa"
    })
    
    st.dataframe(
        tabela_exibicao,
        use_container_width=True,
        hide_index=True,
        column_config={
            col_est_header: st.column_config.TextColumn(alignment="right"),
            col_ofic_header: st.column_config.TextColumn(alignment="right"),
        }
    )

with tab_graficos:
    st.subheader("Distribuição por Status de Conformidade")
    
    status_counts = df_cruzado["Status_Conformidade"].value_counts().reset_index()
    status_counts.columns = ["Status", "Quantidade"]
    status_counts["Percentual"] = (status_counts["Quantidade"] / status_counts["Quantidade"].sum() * 100).apply(
        lambda x: f"{x:,.1f}%".replace(".", ",")
    )
    
    cores_map = {
        "🟢 Conforme Oficial": "#10B981",
        "🟣 Localizado por Processo SEI": "#8B5CF6",
        "🔴 Sem IPOF na Planilha": "#EF4444",
        "🟡 IPOF não localizado no SIAFIC": "#F59E0B",
        "🔵 Oficial Maior que Estimado": "#3B82F6",
        "🟠 Oficial Menor que Estimado": "#F97316",
    }
    
    col_chart, col_stats = st.columns([1.2, 1])
    
    with col_chart:
        fig_status = px.pie(
            status_counts,
            values="Quantidade",
            names="Status",
            color="Status",
            color_discrete_map=cores_map,
            hole=0.45
        )
        fig_status = style(fig_status, height=380)
        st.plotly_chart(fig_status, use_container_width=True)
        
    with col_stats:
        st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)
        st.dataframe(
            status_counts.rename(columns={"Quantidade": "Qtd Itens", "Percentual": "% Total"}),
            use_container_width=True,
            hide_index=True,
        )

with tab_sap_sobras:
    st.subheader("IPOFs Ativos no SIAFIC sem Vínculo Direto de Número na Planilha")
    st.caption("Cruzamento reverso: despesas do SIAFIC que não tiveram seu número de IPOF preenchido na planilha, avaliadas por correspondência via Processo SEI.")
    
    # Mapeamento reverso: Processo da Planilha -> itens da planilha
    plan_by_proc: dict[str, list[str]] = {}
    for _, r_pl in df_plan_exploded.iterrows():
        p_list = extrair_procs(r_pl.get("Processo_SEI_Planilha", ""))
        for p in p_list:
            if p not in plan_by_proc:
                plan_by_proc[p] = []
            desc_item = f"Item {r_pl['Item']} ({r_pl['Unidade']})"
            if desc_item not in plan_by_proc[p]:
                plan_by_proc[p].append(desc_item)

    ipofs_na_planilha = set(re.findall(r"\d{10,15}", " ".join(df_plan_exploded["Num_IPOF"].astype(str))))
    df_sobras_sap = sap_resumo[
        (~sap_resumo["Num_IPOF_Oficial"].isin(ipofs_na_planilha))
        & (sap_resumo["Num_IPOF_Oficial"].astype(str).str.isdigit())
        & (~sap_resumo["Num_IPOF_Oficial"].astype(str).str.lower().str.contains("soma|total"))
        & (~sap_resumo["Acao_Oficial"].apply(is_acao_invalida))
    ].copy()

    # Identificar vínculo via Processo SEI para cada sobra do SIAFIC
    def identificar_vinculo_sobra(r):
        p_list = extrair_procs(r.get("Processo_SEI_Oficial", ""))
        itens_encontrados = []
        for p in p_list:
            if p in plan_by_proc:
                itens_encontrados.extend(plan_by_proc[p])
        itens_unicos = sorted(list(set(itens_encontrados)))
        if itens_unicos:
            return "🔗 " + ", ".join(itens_unicos)
        return "❌ Sem Vínculo"

    df_sobras_sap["Vinculo_Planilha"] = df_sobras_sap.apply(identificar_vinculo_sobra, axis=1)
    df_sobras_sap["Possui_Vinculo"] = df_sobras_sap["Vinculo_Planilha"].str.startswith("🔗")
    df_sobras_sap = df_sobras_sap.sort_values(by="Valor_Parcela_Oficial", ascending=False)

    total_sobras_qtd = len(df_sobras_sap)
    total_sobras_val = df_sobras_sap["Valor_Parcela_Oficial"].sum()
    vinc_qtd = int(df_sobras_sap["Possui_Vinculo"].sum())
    vinc_val = df_sobras_sap[df_sobras_sap["Possui_Vinculo"]]["Valor_Parcela_Oficial"].sum()
    sem_qtd = total_sobras_qtd - vinc_qtd
    sem_val = total_sobras_val - vinc_val

    # Cards informativos do cruzamento reverso
    c_s1, c_s2, c_s3 = st.columns(3)
    with c_s1:
        st.markdown(
            f'<div class="kpi"><div class="label">Total sem Nº na Planilha</div>'
            f'<div class="value">{num(total_sobras_qtd)}</div>'
            f'<div class="sub">Total: {fmt_brl(total_sobras_val)}</div></div>',
            unsafe_allow_html=True
        )
    with c_s2:
        st.markdown(
            f'<div class="kpi"><div class="label">🔗 Vinculados via Processo SEI</div>'
            f'<div class="value">{num(vinc_qtd)}</div>'
            f'<div class="sub">Total: {fmt_brl(vinc_val)}</div></div>',
            unsafe_allow_html=True
        )
    with c_s3:
        st.markdown(
            f'<div class="kpi"><div class="label">❌ Totalmente sem Vínculo</div>'
            f'<div class="value">{num(sem_qtd)}</div>'
            f'<div class="sub">Total: {fmt_brl(sem_val)}</div></div>',
            unsafe_allow_html=True
        )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    filtro_sobras = st.radio(
        "Filtrar lista do SIAFIC:",
        [
            f"Todos os IPOFs sem número na Planilha ({num(total_sobras_qtd)})",
            f"🔗 Vinculados à Planilha via Processo SEI ({num(vinc_qtd)})",
            f"❌ Totalmente sem Vínculo ({num(sem_qtd)})"
        ],
        horizontal=True,
        key="f_radio_sobras"
    )

    if "Vinculados" in filtro_sobras:
        df_sobras_view = df_sobras_sap[df_sobras_sap["Possui_Vinculo"]].copy()
    elif "sem Vínculo" in filtro_sobras:
        df_sobras_view = df_sobras_sap[~df_sobras_sap["Possui_Vinculo"]].copy()
    else:
        df_sobras_view = df_sobras_sap.copy()

    cols_sobra = [
        "Num_IPOF_Oficial", "Processo_SEI_Oficial", "Vinculo_Planilha",
        "Situacao_IPOF_Oficial", "Valor_Parcela_Oficial", "Acao_Oficial", "Descricao_Despesa_Oficial"
    ]
    df_sobras_fmt = df_sobras_view[cols_sobra].copy()
    
    # Formatação ABNT 2 (R$ X.XXX,XX)
    df_sobras_fmt["Valor Oficial (R$)"] = df_sobras_fmt["Valor_Parcela_Oficial"].apply(fmt_brl)
    
    cols_sobra_ordem = [
        "Num_IPOF_Oficial", "Processo_SEI_Oficial", "Vinculo_Planilha", "Situacao_IPOF_Oficial",
        "Valor Oficial (R$)", "Acao_Oficial", "Descricao_Despesa_Oficial"
    ]
    
    st.dataframe(
        df_sobras_fmt[cols_sobra_ordem].rename(columns={
            "Num_IPOF_Oficial": "Nº IPOF (SIAFIC)",
            "Processo_SEI_Oficial": "Processo SEI",
            "Vinculo_Planilha": "Vínculo com a Planilha (via Processo SEI)",
            "Situacao_IPOF_Oficial": "Situação",
            "Acao_Oficial": "Ação Orçamentária",
            "Descricao_Despesa_Oficial": "Descrição"
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Valor Oficial (R$)": st.column_config.TextColumn(alignment="right"),
        }
    )
