"""Página: Liquidação Mensal por Contrato — Execução 2026 vs SAP BO (ConsultaLiquidadoMensal ID: 32115483)."""
from __future__ import annotations

import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import num, style, PALETTE
import common
import liquidado_mensal_data


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


def extrair_procs(val: object) -> list[str]:
    """Extrai sequências de 10 a 16 dígitos correspondentes a Processos SEI."""
    if val is None or pd.isna(val):
        return []
    return re.findall(r"\d{10,16}", str(val))


# ------------------------------------------------------------------ CARREGAMENTO DOS DADOS (2026)
try:
    df_planilha_raw, updated_planilha, _ = common.get_data(ano=2026)
    df_sap, updated_sap = liquidado_mensal_data.load_liquidado_mensal_data()
except Exception as exc:
    st.error(f"Erro ao carregar dados de liquidação 2026: {exc}")
    st.stop()

if df_planilha_raw.empty or df_sap.empty:
    st.warning("Não há dados suficientes da Planilha 2026 ou do SIAFIC para conciliação de liquidação.")
    st.stop()

# ------------------------------------------------------------------ BANNER SUPERIOR
dt_sap_str = updated_sap.strftime("%d/%m/%Y às %H:%M") if updated_sap else "N/D"
st.html(
    f"""<div style="background:#0F2A20; border-radius:12px; padding:12px 24px; margin-bottom:1.2rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 14px rgba(15,42,32,0.18);">
      <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
        📜 Liquidação Mensal por Contrato · Execução 2026
      </h2>
      <div style="font-size:0.85rem; color:#A7F3D0; text-align:right;">
        <strong>Fonte Oficial SIAFIC:</strong> ConsultaLiquidadoMensal (ID: 32115483)<br>
        <span style="font-size:0.75rem; color:#D1FAE5;">Sincronizado em: {dt_sap_str}</span>
      </div>
    </div>"""
)

# ------------------------------------------------------------------ TRATAMENTO DA PLANILHA 2026
col_sit = [c for c in df_planilha_raw.columns if "situa" in str(c).lower() and "ipof" not in str(c).lower()]
df_plan = df_planilha_raw.copy()
if col_sit:
    df_plan = df_plan[~df_plan[col_sit[0]].astype(str).str.lower().str.contains("exclu")].copy()

col_item = [c for c in df_plan.columns if str(c).strip().lower() == "item"][0]
col_contrato = [c for c in df_plan.columns if "contrato" in str(c).lower() and "global" not in str(c).lower()][0]
col_proc = [c for c in df_plan.columns if "processo" in str(c).lower() and "sislog" not in str(c).lower()][0]
col_obj = [c for c in df_plan.columns if "objeto" in str(c).lower()][0]
col_forn_list = [c for c in df_plan.columns if "empresa" in str(c).lower() or "contratada" in str(c).lower()]
col_forn = col_forn_list[0] if col_forn_list else None
col_uni = [c for c in df_plan.columns if "unidade" in str(c).lower()][0]
col_total_est = "Estimado Total 2026"

meses_nomes = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]
cod_meses = [f"2026{i:02d}" for i in range(1, 13)]
map_cod_to_nome = {f"2026{i:02d}": meses_nomes[i-1] for i in range(1, 13)}
map_nome_to_cod = {meses_nomes[i-1]: f"2026{i:02d}" for i in range(1, 13)}

# ------------------------------------------------------------------ TRATAMENTO DO SAP BO
df_sap_2026 = df_sap[df_sap["Exercicio_Ano"] == 2026].copy()

# Mapeia liquidação do SIAFIC por processo SEI
sap_by_proc: dict[str, dict] = {}
for _, row_sap in df_sap_2026.iterrows():
    p = str(row_sap["Processo_SEI"]).strip()
    if not p:
        continue
    if p not in sap_by_proc:
        sap_by_proc[p] = {
            "total_liquidado": 0.0,
            "meses": {c: 0.0 for c in cod_meses},
            "outros_meses": 0.0,
            "beneficiarios": set(),
            "naturezas": set(),
        }
    val = float(row_sap.get("Valor_Liquidado_Saldo", 0) or 0)
    sap_by_proc[p]["total_liquidado"] += val
    m = str(row_sap.get("Periodo_AnoMes", "")).strip()
    if m in sap_by_proc[p]["meses"]:
        sap_by_proc[p]["meses"][m] += val
    else:
        sap_by_proc[p]["outros_meses"] += val

    if pd.notna(row_sap.get("Beneficiario_Nome")) and str(row_sap["Beneficiario_Nome"]).strip():
        sap_by_proc[p]["beneficiarios"].add(str(row_sap["Beneficiario_Nome"]).strip())
    if pd.notna(row_sap.get("Natureza_Despesa_Nome")) and str(row_sap["Natureza_Despesa_Nome"]).strip():
        sap_by_proc[p]["naturezas"].add(str(row_sap["Natureza_Despesa_Nome"]).strip())

# ------------------------------------------------------------------ CRUZAMENTO POR CONTRATO / ITEM
# Agrupamento da planilha por Contrato (itens que compõem o mesmo contrato são consolidados)
contratos_agrupados: dict[str, dict] = {}
for _, r_pl in df_plan.iterrows():
    c_raw = str(r_pl.get(col_contrato, "")).replace("_x000D_", " ").replace("\xa0", " ").strip()
    tem_contrato_formal = bool(c_raw and c_raw.lower() not in ["nan", "none", "<na>", "", "em planejamento", "não se aplica", "nao se aplica"])
    
    item_str = str(r_pl.get(col_item, "")).replace(".0", "").strip()
    chave_contrato = c_raw.replace(".0", "") if tem_contrato_formal else f"(Sem Contrato Formal - Item {item_str})"
    
    procs_item = extrair_procs(r_pl.get(col_proc, ""))
    val_est_tot = float(pd.to_numeric(r_pl.get(col_total_est), errors="coerce") or 0)
    
    if chave_contrato not in contratos_agrupados:
        contratos_agrupados[chave_contrato] = {
            "Contrato": chave_contrato,
            "Tem_Contrato_Formal": tem_contrato_formal,
            "Itens": set(),
            "Processos_SEI": set(),
            "Objetos": set(),
            "Fornecedores": set(),
            "Unidades": set(),
            "Estimado_Total": 0.0,
            "Estimado_Meses": {m: 0.0 for m in meses_nomes},
        }
        
    contratos_agrupados[chave_contrato]["Itens"].add(item_str)
    contratos_agrupados[chave_contrato]["Processos_SEI"].update(procs_item)
    if pd.notna(r_pl.get(col_obj)):
        contratos_agrupados[chave_contrato]["Objetos"].add(str(r_pl.get(col_obj)).strip())
    if col_forn and pd.notna(r_pl.get(col_forn)):
        contratos_agrupados[chave_contrato]["Fornecedores"].add(str(r_pl.get(col_forn)).strip())
    if pd.notna(r_pl.get(col_uni)):
        contratos_agrupados[chave_contrato]["Unidades"].add(str(r_pl.get(col_uni)).strip())
        
    contratos_agrupados[chave_contrato]["Estimado_Total"] += val_est_tot
    for m in meses_nomes:
        c_m = f"Estimado {m}"
        contratos_agrupados[chave_contrato]["Estimado_Meses"][m] += float(pd.to_numeric(r_pl.get(c_m), errors="coerce") or 0)

# Montagem das linhas consolidadas com cruzamento SIAFIC
linhas_consolidadas = []
processos_mapeados_planilha = set()

for c_key, c_data in contratos_agrupados.items():
    procs = list(c_data["Processos_SEI"])
    processos_mapeados_planilha.update(procs)
    
    # Consolidação dos valores liquidados do SIAFIC para este contrato
    tot_liquidado_siafic = 0.0
    meses_liquidado = {f"Liquidado_{m}": 0.0 for m in meses_nomes}
    beneficiarios_siafic = set()
    naturezas_siafic = set()
    
    for p in procs:
        if p in sap_by_proc:
            tot_liquidado_siafic += sap_by_proc[p]["total_liquidado"]
            for cod, val_m in sap_by_proc[p]["meses"].items():
                nome_m = map_cod_to_nome.get(cod)
                if nome_m:
                    meses_liquidado[f"Liquidado_{nome_m}"] += val_m
            beneficiarios_siafic.update(sap_by_proc[p]["beneficiarios"])
            naturezas_siafic.update(sap_by_proc[p]["naturezas"])
            
    val_est = c_data["Estimado_Total"]
    saldo_a_liquidar = val_est - tot_liquidado_siafic
    pct_exec = (tot_liquidado_siafic / val_est * 100) if val_est > 0 else (100.0 if tot_liquidado_siafic > 0 else 0.0)
    
    # Classificação de Status de Liquidação
    if tot_liquidado_siafic == 0:
        if not procs:
            status_exec = "⚪ Sem Processo SEI"
        else:
            status_exec = "⚪ Sem Liquidação no SIAFIC"
    elif abs(val_est - tot_liquidado_siafic) < 1.0 or (val_est > 0 and 99.0 <= pct_exec <= 101.0):
        status_exec = "🟢 Conforme / 100% Liquidado"
    elif tot_liquidado_siafic > val_est and val_est > 0:
        status_exec = "🟠 Liquidado Acima do Estimado"
    else:
        status_exec = "🔵 Em Liquidação"
        
    forn_display = ", ".join(sorted(c_data["Fornecedores"])) or (", ".join(sorted(beneficiarios_siafic)) if beneficiarios_siafic else "-")
    obj_display = " / ".join(sorted(c_data["Objetos"]))
    uni_display = ", ".join(sorted(c_data["Unidades"]))
    procs_display = ", ".join(sorted(procs)) if procs else "(não informado)"
    itens_display = ", ".join(sorted(c_data["Itens"], key=lambda x: pd.to_numeric(x, errors="coerce") or 0))
    
    row_out = {
        "Contrato": c_data["Contrato"],
        "Tem_Contrato_Formal": c_data["Tem_Contrato_Formal"],
        "Itens": itens_display,
        "Processo_SEI": procs_display,
        "Objeto": obj_display,
        "Fornecedor": forn_display,
        "Unidade": uni_display,
        "Estimado_Total_2026": val_est,
        "Total_Liquidado_SIAFIC": tot_liquidado_siafic,
        "Saldo_A_Liquidar": saldo_a_liquidar,
        "Pct_Executado": pct_exec,
        "Status_Execucao": status_exec,
        **meses_liquidado,
        **{f"Estimado_{m}": c_data["Estimado_Meses"][m] for m in meses_nomes}
    }
    linhas_consolidadas.append(row_out)

df_contratos = pd.DataFrame(linhas_consolidadas)

# ------------------------------------------------------------------ FILTROS NA BARRA LATERAL
with st.sidebar:
    st.header("Filtros de Liquidação")
    
    opts_uni = sorted([str(u) for u in df_contratos["Unidade"].unique() if u and u != "-"])
    sel_uni = st.multiselect("Unidade", opts_uni, key="f_liq_uni")
    
    opts_status = sorted(df_contratos["Status_Execucao"].unique())
    sel_status = st.multiselect("Status de Execução", opts_status, key="f_liq_status")
    
    tipo_contrato = st.radio(
        "Tipo de Item:",
        ["Todos os Itens", "Apenas Contratos Formalizados", "Sem Contrato Formalizado"],
        key="f_liq_tipo"
    )
    
    busca_livre = st.text_input("🔎 Buscar (Contrato, Processo SEI, Objeto, Fornecedor, Item)", key="f_liq_busca")

# Aplicação dos filtros
df_view = df_contratos.copy()
if sel_uni:
    df_view = df_view[df_view["Unidade"].apply(lambda u: any(x in str(u) for x in sel_uni))]
if sel_status:
    df_view = df_view[df_view["Status_Execucao"].isin(sel_status)]
if tipo_contrato == "Apenas Contratos Formalizados":
    df_view = df_view[df_view["Tem_Contrato_Formal"]]
elif tipo_contrato == "Sem Contrato Formalizado":
    df_view = df_view[~df_view["Tem_Contrato_Formal"]]
if busca_livre:
    m = (
        df_view["Contrato"].astype(str).str.contains(busca_livre, case=False, na=False) |
        df_view["Processo_SEI"].astype(str).str.contains(busca_livre, case=False, na=False) |
        df_view["Objeto"].astype(str).str.contains(busca_livre, case=False, na=False) |
        df_view["Fornecedor"].astype(str).str.contains(busca_livre, case=False, na=False) |
        df_view["Itens"].astype(str).str.contains(busca_livre, case=False, na=False)
    )
    df_view = df_view[m]

# ------------------------------------------------------------------ KPIS NO TOPO
k1, k2, k3, k4 = st.columns(4)

total_estimado_geral = df_view["Estimado_Total_2026"].sum()
total_liquidado_geral = df_view["Total_Liquidado_SIAFIC"].sum()
saldo_restante_geral = total_estimado_geral - total_liquidado_geral
pct_geral = (total_liquidado_geral / total_estimado_geral * 100) if total_estimado_geral > 0 else 0.0

contratos_com_liq_count = (df_view["Total_Liquidado_SIAFIC"] > 0).sum()

with k1:
    st.markdown(
        f'<div class="kpi"><div class="label">Total Estimado 2026</div>'
        f'<div class="value">{fmt_card_mi(total_estimado_geral)}</div>'
        f'<div class="sub">{num(len(df_view))} contratos/despesas filtradas</div></div>',
        unsafe_allow_html=True
    )
with k2:
    st.markdown(
        f'<div class="kpi"><div class="label">Total Liquidado (SIAFIC)</div>'
        f'<div class="value">{fmt_card_mi(total_liquidado_geral)}</div>'
        f'<div class="sub">{num(contratos_com_liq_count)} contratos com liquidação</div></div>',
        unsafe_allow_html=True
    )
with k3:
    st.markdown(
        f'<div class="kpi"><div class="label">Saldo a Liquidar</div>'
        f'<div class="value">{fmt_card_mi(saldo_restante_geral)}</div>'
        f'<div class="sub">Restante para execução orçamentária</div></div>',
        unsafe_allow_html=True
    )
with k4:
    st.markdown(
        f'<div class="kpi"><div class="label">Índice de Execução</div>'
        f'<div class="value">{pct_geral:.1f}%</div>'
        f'<div class="sub">Executado do orçamento estimado 2026</div></div>',
        unsafe_allow_html=True
    )

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ ABAS DETALHADAS
tab_detalhada, tab_mensal, tab_sobras_sap = st.tabs([
    "📋 Painel por Contrato",
    "📅 Evolução Mês a Mês (Estimado vs Liquidado)",
    "🔍 Liquidações no SIAFIC sem Vínculo na Planilha"
])

# ------------------------------------------------------------------ ABA 1: PAINEL POR CONTRATO
with tab_detalhada:
    st.subheader("Acompanhamento Individual por Contrato")
    
    # Seletor de detalhamento mensal
    ver_meses = st.checkbox("Exibir colunas com liquidação mês a mês (Jan, Fev, Mar, Abr)", value=False)
    
    cols_base = [
        "Contrato", "Processo_SEI", "Objeto", "Fornecedor", "Unidade",
        "Estimado_Total_2026", "Total_Liquidado_SIAFIC", "Saldo_A_Liquidar",
        "Pct_Executado", "Status_Execucao"
    ]
    
    if ver_meses:
        # Meses que já possuem liquidação oficial
        cols_meses_show = ["Liquidado_Janeiro", "Liquidado_Fevereiro", "Liquidado_Março", "Liquidado_Abril"]
        cols_base = (
            cols_base[:6]
            + cols_meses_show
            + cols_base[6:]
        )
        
    df_table = df_view.sort_values(by="Total_Liquidado_SIAFIC", ascending=False).copy()
    
    # Formatação ABNT 2
    df_table_fmt = df_table[cols_base].copy()
    df_table_fmt["Estimado Total 2026 (R$)"] = df_table_fmt["Estimado_Total_2026"].apply(fmt_brl)
    df_table_fmt["Liquidado SIAFIC 2026 (R$)"] = df_table_fmt["Total_Liquidado_SIAFIC"].apply(fmt_brl)
    df_table_fmt["Saldo a Liquidar (R$)"] = df_table_fmt["Saldo_A_Liquidar"].apply(fmt_brl)
    df_table_fmt["% Exec."] = df_table_fmt["Pct_Executado"].apply(lambda x: f"{x:.1f}%")
    
    if ver_meses:
        df_table_fmt["Jan/26 (R$)"] = df_table_fmt["Liquidado_Janeiro"].apply(fmt_brl)
        df_table_fmt["Fev/26 (R$)"] = df_table_fmt["Liquidado_Fevereiro"].apply(fmt_brl)
        df_table_fmt["Mar/26 (R$)"] = df_table_fmt["Liquidado_Março"].apply(fmt_brl)
        df_table_fmt["Abr/26 (R$)"] = df_table_fmt["Liquidado_Abril"].apply(fmt_brl)
        
        ordem_colunas = [
            "Contrato", "Processo_SEI", "Objeto", "Fornecedor", "Unidade",
            "Estimado Total 2026 (R$)",
            "Jan/26 (R$)", "Fev/26 (R$)", "Mar/26 (R$)", "Abr/26 (R$)",
            "Liquidado SIAFIC 2026 (R$)", "Saldo a Liquidar (R$)", "% Exec.", "Status_Execucao"
        ]
    else:
        ordem_colunas = [
            "Contrato", "Processo_SEI", "Objeto", "Fornecedor", "Unidade",
            "Estimado Total 2026 (R$)", "Liquidado SIAFIC 2026 (R$)",
            "Saldo a Liquidar (R$)", "% Exec.", "Status_Execucao"
        ]
        
    tabela_final = df_table_fmt[ordem_colunas].rename(columns={
        "Processo_SEI": "Processo SEI",
        "Status_Execucao": "Status"
    })
    
    st.dataframe(
        tabela_final,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Estimado Total 2026 (R$)": st.column_config.TextColumn(alignment="right"),
            "Liquidado SIAFIC 2026 (R$)": st.column_config.TextColumn(alignment="right"),
            "Saldo a Liquidar (R$)": st.column_config.TextColumn(alignment="right"),
            "% Exec.": st.column_config.TextColumn(alignment="right"),
            "Jan/26 (R$)": st.column_config.TextColumn(alignment="right"),
            "Fev/26 (R$)": st.column_config.TextColumn(alignment="right"),
            "Mar/26 (R$)": st.column_config.TextColumn(alignment="right"),
            "Abr/26 (R$)": st.column_config.TextColumn(alignment="right"),
        }
    )

# ------------------------------------------------------------------ ABA 2: EVOLUÇÃO MÊS A MÊS
with tab_mensal:
    st.subheader("Comparativo Mensal: Planejado vs Executado Oficial")
    
    dados_mensais = []
    acum_est = 0.0
    acum_liq = 0.0
    
    for m in meses_nomes:
        val_est_m = df_view[f"Estimado_{m}"].sum()
        val_liq_m = df_view[f"Liquidado_{m}"].sum()
        acum_est += val_est_m
        acum_liq += val_liq_m
        
        dados_mensais.append({
            "Mês": m,
            "Estimado": val_est_m,
            "Liquidado": val_liq_m,
            "Diferença": val_liq_m - val_est_m,
            "Acumulado Estimado": acum_est,
            "Acumulado Liquidado": acum_liq,
        })
        
    df_mensal_comp = pd.DataFrame(dados_mensais)
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("##### 📊 Liquidação Mensal (R$ Milhões)")
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=df_mensal_comp["Mês"],
            y=df_mensal_comp["Estimado"],
            name="Estimado (Planilha)",
            marker_color="#3B82F6"
        ))
        fig_bar.add_trace(go.Bar(
            x=df_mensal_comp["Mês"],
            y=df_mensal_comp["Liquidado"],
            name="Liquidado (SIAFIC)",
            marker_color="#10B981"
        ))
        fig_bar.update_layout(
            barmode="group",
            margin=dict(l=10, r=10, t=25, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig_bar = style(fig_bar, height=360)
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col_g2:
        st.markdown("##### 📈 Curva Acumulada de Execução")
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=df_mensal_comp["Mês"],
            y=df_mensal_comp["Acumulado Estimado"],
            name="Estimado Acumulado",
            mode="lines+markers",
            line=dict(color="#3B82F6", width=3)
        ))
        fig_line.add_trace(go.Scatter(
            x=df_mensal_comp["Mês"],
            y=df_mensal_comp["Acumulado Liquidado"],
            name="Liquidado Acumulado",
            mode="lines+markers",
            line=dict(color="#10B981", width=3)
        ))
        fig_line.update_layout(
            margin=dict(l=10, r=10, t=25, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig_line = style(fig_line, height=360)
        st.plotly_chart(fig_line, use_container_width=True)
        
    st.markdown("##### 📑 Tabela Resumo da Execução por Mês")
    tabela_mensal_fmt = df_mensal_comp[["Mês", "Estimado", "Liquidado", "Diferença"]].copy()
    tabela_mensal_fmt["Estimado (R$)"] = tabela_mensal_fmt["Estimado"].apply(fmt_brl)
    tabela_mensal_fmt["Liquidado SIAFIC (R$)"] = tabela_mensal_fmt["Liquidado"].apply(fmt_brl)
    tabela_mensal_fmt["Diferença (R$)"] = tabela_mensal_fmt["Diferença"].apply(fmt_brl)
    
    st.dataframe(
        tabela_mensal_fmt[["Mês", "Estimado (R$)", "Liquidado SIAFIC (R$)", "Diferença (R$)"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Estimado (R$)": st.column_config.TextColumn(alignment="right"),
            "Liquidado SIAFIC (R$)": st.column_config.TextColumn(alignment="right"),
            "Diferença (R$)": st.column_config.TextColumn(alignment="right"),
        }
    )

# ------------------------------------------------------------------ ABA 3: SOBRAS DO SIAFIC
with tab_sobras_sap:
    st.subheader("Processos com Liquidação em 2026 sem Contrato na Planilha")
    st.caption("Despesas liquidadas oficialmente no SIAFIC em 2026 cujo Processo SEI não foi encontrado na planilha de planejamento/execução de 2026.")
    
    # Processos do SIAFIC que não estão em processos_mapeados_planilha
    sobras_sap_list = []
    for p_sap, data_sap in sap_by_proc.items():
        if p_sap not in processos_mapeados_planilha and data_sap["total_liquidado"] > 0:
            sobras_sap_list.append({
                "Processo_SEI": p_sap,
                "Beneficiario": ", ".join(sorted(data_sap["beneficiarios"])) or "-",
                "Natureza_Despesa": "; ".join(sorted(data_sap["naturezas"])) or "-",
                "Total_Liquidado": data_sap["total_liquidado"],
                "Jan": data_sap["meses"].get("202601", 0.0),
                "Fev": data_sap["meses"].get("202602", 0.0),
                "Mar": data_sap["meses"].get("202603", 0.0),
                "Abr": data_sap["meses"].get("202604", 0.0),
            })
            
    df_sobras = pd.DataFrame(sobras_sap_list)
    
    if df_sobras.empty:
        st.success("🎉 Todas as liquidações do SIAFIC 2026 possuem correspondência com processos da planilha!")
    else:
        df_sobras = df_sobras.sort_values(by="Total_Liquidado", ascending=False)
        tot_sobras_val = df_sobras["Total_Liquidado"].sum()
        
        c_sb1, c_sb2 = st.columns(2)
        with c_sb1:
            st.markdown(
                f'<div class="kpi"><div class="label">Processos sem Vínculo na Planilha</div>'
                f'<div class="value">{num(len(df_sobras))}</div>'
                f'<div class="sub">Despesas registradas apenas no SIAFIC</div></div>',
                unsafe_allow_html=True
            )
        with c_sb2:
            st.markdown(
                f'<div class="kpi"><div class="label">Total Liquidado sem Vínculo</div>'
                f'<div class="value">{fmt_card_mi(tot_sobras_val)}</div>'
                f'<div class="sub">Total: {fmt_brl(tot_sobras_val)}</div></div>',
                unsafe_allow_html=True
            )
            
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        
        df_sobras_fmt = df_sobras.copy()
        df_sobras_fmt["Total Liquidado (R$)"] = df_sobras_fmt["Total_Liquidado"].apply(fmt_brl)
        df_sobras_fmt["Jan/26 (R$)"] = df_sobras_fmt["Jan"].apply(fmt_brl)
        df_sobras_fmt["Fev/26 (R$)"] = df_sobras_fmt["Fev"].apply(fmt_brl)
        df_sobras_fmt["Mar/26 (R$)"] = df_sobras_fmt["Mar"].apply(fmt_brl)
        df_sobras_fmt["Abr/26 (R$)"] = df_sobras_fmt["Abr"].apply(fmt_brl)
        
        cols_sobras_display = [
            "Processo_SEI", "Beneficiario", "Natureza_Despesa",
            "Jan/26 (R$)", "Fev/26 (R$)", "Mar/26 (R$)", "Abr/26 (R$)",
            "Total Liquidado (R$)"
        ]
        
        st.dataframe(
            df_sobras_fmt[cols_sobras_display].rename(columns={
                "Processo_SEI": "Processo SEI",
                "Beneficiario": "Beneficiário",
                "Natureza_Despesa": "Natureza da Despesa"
            }),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total Liquidado (R$)": st.column_config.TextColumn(alignment="right"),
                "Jan/26 (R$)": st.column_config.TextColumn(alignment="right"),
                "Fev/26 (R$)": st.column_config.TextColumn(alignment="right"),
                "Mar/26 (R$)": st.column_config.TextColumn(alignment="right"),
                "Abr/26 (R$)": st.column_config.TextColumn(alignment="right"),
            }
        )
