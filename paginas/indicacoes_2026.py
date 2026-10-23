"""Página: Indicações Orçamentárias por Sequencial — Execução 2026
Cruzamento Oficial: SAP BO (ConsultaDeclaradoEmpenhadoLiquidadoPagoPorSequencial ID: 42943444)
× Aba 'Indicacoes' da Planilha de Gestão Orçamentária 2026 (SharePoint).
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import common
from common import PALETTE, num, style
import indicacoes_data


def fmt_brl(v: float | int | None, prefix: bool = True) -> str:
    """Formata valor monetário no padrão brasileiro ABNT 2 (ex: R$ 3.684.748,35)."""
    if v is None or pd.isna(v) or v == "":
        return "-"
    try:
        val = float(v)
        sign = "-" if val < -0.004 else ""
        a = abs(val) if abs(val) >= 0.004 else 0.0
        s = f"{a:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {sign}{s}" if prefix else f"{sign}{s}"
    except Exception:
        return str(v)


def fmt_card_mi(v: float | int | None) -> str:
    """Formata valor abreviado em Mi / Bi com 2 casas decimais para cards (ex: R$ 207,48 Mi)."""
    if v is None or pd.isna(v) or abs(float(v)) < 0.005:
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
            s = f"{a / 1e3:,.1f} mil"
        else:
            s = f"{a:,.2f}"
        return "R$ " + sign + s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(v)


# ------------------------------------------------------------------ CARREGAMENTO DOS DADOS
try:
    df_seq_all, df_ind_all, updated_sap, updated_plan = indicacoes_data.load_consolidado_indicacoes_2026()
except Exception as exc:
    st.error(f"Erro ao carregar dados de Indicações 2026: {exc}")
    st.stop()

if df_seq_all.empty:
    st.warning("Não há dados disponíveis da consulta SAP BO (ID: 42943444) para exibição.")
    st.stop()

# ------------------------------------------------------------------ BANNER SUPERIOR
dt_sap_str = updated_sap.strftime("%d/%m/%Y às %H:%M") if updated_sap else "N/D"
dt_plan_str = updated_plan.strftime("%d/%m/%Y às %H:%M") if updated_plan else "N/D"

st.html(
    f"""<div style="background:#0F2A20; border-radius:12px; padding:14px 24px; margin-bottom:1.1rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 14px rgba(15,42,32,0.18); flex-wrap:wrap; gap:12px;">
      <div>
        <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
          🎯 Indicações Orçamentárias por Sequencial · Execução 2026
        </h2>
        <div style="font-size:0.82rem; color:#A7F3D0; margin-top:4px;">
          Chave de Ligação: <strong>Nº do Sequencial (Dotação)</strong> &nbsp;|&nbsp;
          Campo <strong>Indicado (I)</strong> integrado da aba <em>Indicações</em> da Planilha 2026
        </div>
      </div>
      <div style="font-size:0.82rem; color:#A7F3D0; text-align:right;">
        <strong>SIAFIC (SAP BO):</strong> ConsultaDeclaradoEmpenhadoLiquidadoPagoPorSequencial (ID: 42943444)<br>
        <span style="font-size:0.75rem; color:#D1FAE5;">
          SAP BO: {dt_sap_str} &nbsp;•&nbsp; Planilha 2026: {dt_plan_str}
        </span>
      </div>
    </div>"""
)

# ------------------------------------------------------------------ BARRA LATERAL & FILTROS NO TOPO
with st.sidebar:
    st.markdown("## ⚙️ Controle · Indicações 2026")
    if st.button("🔄 Atualizar SAP BO + Planilha", use_container_width=True):
        with st.spinner("Sincronizando SAP BO (ID: 42943444) e Planilha 2026..."):
            indicacoes_data.download_declarado_empenhado_seq_csv()
            st.cache_data.clear()
            st.rerun()

# Opções de filtros
fontes_disp = sorted(df_seq_all["Fonte_Label"].unique().tolist())
default_fontes = [f for f in fontes_disp if f.startswith("15000100") or f.startswith("15010100")]
if not default_fontes:
    default_fontes = fontes_disp

acoes_disp = sorted(df_seq_all["Acao_Label"].unique().tolist())
grupos_disp = sorted(df_seq_all["Grupo_Label"].unique().tolist())

with st.expander("🔍 **Filtros de Dotação & Classificação Orçamentária** *(Fonte, Ação, Grupo e Sequencial)*", expanded=True):
    f_col1, f_col2, f_col3, f_col4 = st.columns([1.4, 1.5, 1.0, 1.0])
    with f_col1:
        sel_fontes = st.multiselect(
            "Fonte de Recursos",
            options=fontes_disp,
            default=default_fontes,
            help="Por padrão exibe as fontes do Tesouro / Receitas Ordinárias (15000100 e 15010100). Adicione 17540111 para incluir Operações de Crédito (PROFISCO).",
        )
    with f_col2:
        sel_acoes = st.multiselect(
            "Ação Orçamentária",
            options=acoes_disp,
            default=[],
            placeholder="Todas as Ações...",
        )
    with f_col3:
        sel_grupos = st.multiselect(
            "Grupo de Despesa",
            options=grupos_disp,
            default=[],
            placeholder="Todos os Grupos...",
        )
    with f_col4:
        ocultar_zerados = st.checkbox(
            "Apenas c/ Dotação > 0",
            value=True,
            help="Oculta sequenciais com valor Autorizado (A) igual a R$ 0,00.",
        )

# Aplica filtros no DataFrame por Sequencial
df_f = df_seq_all.copy()
if sel_fontes:
    df_f = df_f[df_f["Fonte_Label"].isin(sel_fontes)].copy()
if sel_acoes:
    df_f = df_f[df_f["Acao_Label"].isin(sel_acoes)].copy()
if sel_grupos:
    df_f = df_f[df_f["Grupo_Label"].isin(sel_grupos)].copy()
if ocultar_zerados:
    df_f = df_f[(df_f["Autorizado"] > 0) | (df_f["Indicado"] > 0) | (df_f["Empenhado"] > 0)].copy()

if df_f.empty:
    st.info("Nenhum sequencial encontrado para os filtros selecionados.")
    st.stop()

# ------------------------------------------------------------------ CÁLCULO DOS TOTAIS DOS CARDS
tot_aut = float(df_f["Autorizado"].sum())
tot_ind = float(df_f["Indicado"].sum())
tot_saldo_ind = float(df_f["Saldo_Indicacao"].sum())
tot_emp = float(df_f["Empenhado"].sum())
tot_saldo_emp = float(df_f["Saldo_Empenho"].sum())
tot_liq = float(df_f["Liquidado"].sum())
tot_pago = float(df_f["Pago"].sum())

tot_ind_a_emp = tot_ind - tot_emp
tot_emp_a_liq = tot_emp - tot_liq
tot_liq_a_pag = tot_liq - tot_pago
qtd_seqs = len(df_f)
qtd_ind_ativas = int(df_f["Qtd_Indicacoes"].sum())

pct_ind_aut = (tot_ind / tot_aut * 100) if tot_aut > 0 else 0.0
pct_emp_aut = (tot_emp / tot_aut * 100) if tot_aut > 0 else 0.0
pct_emp_ind = (tot_emp / tot_ind * 100) if tot_ind > 0 else 0.0
pct_liq_emp = (tot_liq / tot_emp * 100) if tot_emp > 0 else 0.0
pct_pag_liq = (tot_pago / tot_liq * 100) if tot_liq > 0 else 0.0
pct_saldo_ind = (tot_saldo_ind / tot_aut * 100) if tot_aut > 0 else 0.0
pct_saldo_emp = (tot_saldo_emp / tot_aut * 100) if tot_aut > 0 else 0.0

# ------------------------------------------------------------------ LINHA 1: 5 CARDS PRINCIPAIS DO FUNIL (A -> I -> E -> L -> P)
c1, c2, c3, c4, c5 = st.columns(5)
common.kpi(
    c1,
    "Autorizado (A)",
    fmt_card_mi(tot_aut),
    f"{fmt_brl(tot_aut)} · {qtd_seqs} sequenciais",
)
common.kpi(
    c2,
    "Indicado (I)",
    fmt_card_mi(tot_ind),
    f"{fmt_brl(tot_ind)} ({pct_ind_aut:.1f}% de A · {qtd_ind_ativas} ind.)",
)
common.kpi(
    c3,
    "Empenhado (E)",
    fmt_card_mi(tot_emp),
    f"{fmt_brl(tot_emp)} ({pct_emp_aut:.1f}% de A · {pct_emp_ind:.1f}% de I)",
)
common.kpi(
    c4,
    "Liquidado (L)",
    fmt_card_mi(tot_liq),
    f"{fmt_brl(tot_liq)} ({pct_liq_emp:.1f}% do Empenhado)",
)
common.kpi(
    c5,
    "Pago (P)",
    fmt_card_mi(tot_pago),
    f"{fmt_brl(tot_pago)} ({pct_pag_liq:.1f}% do Liquidado)",
)

st.markdown("<div style='height:0.65rem'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ LINHA 2: 4 CARDS DE SALDOS DISPONÍVEIS E GAPS OPERACIONAIS
s1, s2, s3, s4 = st.columns(4)
common.kpi(
    s1,
    "Saldo Disponível p/ Indicação (A − I)",
    fmt_card_mi(tot_saldo_ind),
    f"{fmt_brl(tot_saldo_ind)} ({pct_saldo_ind:.1f}% livre p/ indicar)",
    warn=(tot_saldo_ind < 0),
)
common.kpi(
    s2,
    "Saldo Disponível p/ Empenho (A − E)",
    fmt_card_mi(tot_saldo_emp),
    f"{fmt_brl(tot_saldo_emp)} ({pct_saldo_emp:.1f}% livre p/ empenhar)",
    warn=(tot_saldo_emp < 0),
)
common.kpi(
    s3,
    "Indicado a Empenhar (I − E)",
    fmt_card_mi(tot_ind_a_emp),
    f"{fmt_brl(tot_ind_a_emp)} indicado aguardando empenho",
    warn=(tot_ind_a_emp > 5_000_000),
)
common.kpi(
    s4,
    "Empenhado a Liquidar (E − L)",
    fmt_card_mi(tot_emp_a_liq),
    f"{fmt_brl(tot_emp_a_liq)} em execução contratual",
)

st.markdown("<div style='height:0.9rem'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ BARRA VISUAL DE PROGRESSO DO CICLO ORÇAMENTÁRIO
w_pago = min(100.0, max(0.0, (tot_pago / tot_aut * 100) if tot_aut > 0 else 0.0))
w_liq_extra = min(100.0 - w_pago, max(0.0, ((tot_liq - tot_pago) / tot_aut * 100) if tot_aut > 0 else 0.0))
w_emp_extra = min(100.0 - w_pago - w_liq_extra, max(0.0, ((tot_emp - tot_liq) / tot_aut * 100) if tot_aut > 0 else 0.0))
w_ind_extra = min(100.0 - w_pago - w_liq_extra - w_emp_extra, max(0.0, ((tot_ind - tot_emp) / tot_aut * 100) if tot_aut > 0 else 0.0))
w_livre = max(0.0, 100.0 - w_pago - w_liq_extra - w_emp_extra - w_ind_extra)

st.html(
    f"""<div style="background:#FFFFFF; border:1px solid #E1EEE7; border-radius:16px; padding:16px 22px;
                box-shadow:0 2px 12px rgba(4,120,87,0.06); margin-bottom:1.2rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap;">
        <span style="font-size:0.82rem; font-weight:700; color:#0F2A20; text-transform:uppercase; letter-spacing:0.06em;">
          📊 Termômetro de Execução da Dotação Autorizada (A ➔ I ➔ E ➔ L ➔ P)
        </span>
        <span style="font-size:0.8rem; color:#047857; font-weight:600;">
          Indicado: {pct_ind_aut:.1f}% &nbsp;|&nbsp; Empenhado: {pct_emp_aut:.1f}% &nbsp;|&nbsp;
          Liquidado: {(tot_liq / tot_aut * 100 if tot_aut else 0):.1f}% &nbsp;|&nbsp;
          Pago: {(tot_pago / tot_aut * 100 if tot_aut else 0):.1f}%
        </span>
      </div>
      <div style="display:flex; height:26px; border-radius:10px; overflow:hidden; background:#EEF6F2; border:1px solid #DCEBE3;">
        <div style="width:{w_pago:.2f}%; background:#065F46;" title="Pago: {fmt_brl(tot_pago)}"></div>
        <div style="width:{w_liq_extra:.2f}%; background:#0D9488;" title="Liquidado a Pagar: {fmt_brl(tot_liq_a_pag)}"></div>
        <div style="width:{w_emp_extra:.2f}%; background:#10B981;" title="Empenhado a Liquidar: {fmt_brl(tot_emp_a_liq)}"></div>
        <div style="width:{w_ind_extra:.2f}%; background:#F59E0B;" title="Indicado a Empenhar: {fmt_brl(tot_ind_a_emp)}"></div>
        <div style="width:{w_livre:.2f}%; background:#E2E8F0;" title="Saldo Livre p/ Indicação: {fmt_brl(tot_saldo_ind)}"></div>
      </div>
      <div style="display:flex; flex-wrap:wrap; gap:18px; margin-top:10px; font-size:0.78rem; color:#475569;">
        <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#065F46;margin-right:5px;"></span><strong>Pago (P):</strong> {fmt_brl(tot_pago)}</div>
        <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#0D9488;margin-right:5px;"></span><strong>Liquidado a Pagar (L−P):</strong> {fmt_brl(tot_liq_a_pag)}</div>
        <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#10B981;margin-right:5px;"></span><strong>Empenhado a Liquidar (E−L):</strong> {fmt_brl(tot_emp_a_liq)}</div>
        <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#F59E0B;margin-right:5px;"></span><strong>Indicado a Empenhar (I−E):</strong> {fmt_brl(tot_ind_a_emp)}</div>
        <div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#CBD5E1;margin-right:5px;"></span><strong>Saldo Disponível p/ Indicação (A−I):</strong> {fmt_brl(tot_saldo_ind)}</div>
      </div>
    </div>"""
)

# ------------------------------------------------------------------ TABELA PRINCIPAL POR SEQUENCIAL (ESTILO POWER BI / GESTÃO ORÇAMENTÁRIA)
st.markdown("### 📋 Quadro de Execução Orçamentária por Sequencial (Dotação)")

rows_html = []
for idx, (_, r) in enumerate(df_f.iterrows()):
    bg = "#FFFFFF" if idx % 2 == 0 else "#E6F4EE"
    seq_n = int(r["Seq"])
    class_orc = r["Classificacao_Orcamentaria"]
    acao_c = r["Acao_Cod"]
    acao_desc = indicacoes_data.ACOES_DESCRICAO.get(acao_c, "")
    grp_lbl = r["Grupo_Label"]
    qtd_i = int(r["Qtd_Indicacoes"])

    v_aut = float(r["Autorizado"])
    v_ind = float(r["Indicado"])
    v_s_ind = float(r["Saldo_Indicacao"])
    v_emp = float(r["Empenhado"])
    v_s_emp = float(r["Saldo_Empenho"])
    v_liq = float(r["Liquidado"])
    v_pag = float(r["Pago"])

    cor_s_ind = "#B91C1C" if v_s_ind < -0.01 else ("#047857" if v_s_ind > 0.01 else "#64748B")
    cor_s_emp = "#B91C1C" if v_s_emp < -0.01 else ("#047857" if v_s_emp > 0.01 else "#64748B")
    badge_ind = (
        f'<span style="background:#D1FAE5;color:#065F46;font-size:0.68rem;padding:1px 6px;border-radius:99px;margin-left:6px;font-weight:600;">{qtd_i} ind.</span>'
        if qtd_i > 0
        else ""
    )

    rows_html.append(
        f"""<tr style="background:{bg}; border-bottom:1px solid #DCEBE3;">
          <td style="padding:9px 12px; font-weight:700; color:#0F2A20; text-align:center;">{seq_n}</td>
          <td style="padding:9px 12px;">
            <div style="font-weight:600; color:#0F2A20; font-family:'Inter',monospace; font-size:0.84rem;">{class_orc}</div>
            <div style="font-size:0.72rem; color:#5B7A6C;">Ação {acao_c} ({acao_desc[:48]}{'...' if len(acao_desc) > 48 else ''}) · {grp_lbl}</div>
          </td>
          <td style="padding:9px 12px; text-align:right; font-weight:600; color:#0F2A20;">{fmt_brl(v_aut, prefix=False)}</td>
          <td style="padding:9px 12px; text-align:right; font-weight:700; color:#047857; background:rgba(16,185,129,0.07);">{fmt_brl(v_ind, prefix=False)}{badge_ind}</td>
          <td style="padding:9px 12px; text-align:right; font-weight:600; color:{cor_s_ind};">{fmt_brl(v_s_ind, prefix=False)}</td>
          <td style="padding:9px 12px; text-align:right; font-weight:600; color:#0F2A20;">{fmt_brl(v_emp, prefix=False)}</td>
          <td style="padding:9px 12px; text-align:right; font-weight:600; color:{cor_s_emp};">{fmt_brl(v_s_emp, prefix=False)}</td>
          <td style="padding:9px 12px; text-align:right; font-weight:600; color:#0F2A20;">{fmt_brl(v_liq, prefix=False)}</td>
          <td style="padding:9px 12px; text-align:right; font-weight:600; color:#0F2A20;">{fmt_brl(v_pag, prefix=False)}</td>
        </tr>"""
    )

table_html = f"""
<div style="background:#FFFFFF; border:1px solid #BFE6D1; border-radius:16px; overflow-x:auto;
            box-shadow:0 4px 16px rgba(4,120,87,0.08); margin-bottom:1rem;">
  <table style="width:100%; border-collapse:collapse; font-family:'Inter','Segoe UI',sans-serif; font-size:0.85rem;">
    <thead>
      <tr style="background:linear-gradient(90deg, #065F46 0%, #047857 100%); color:#FFFFFF;">
        <th style="padding:12px 12px; text-align:center; font-weight:700; width:52px;">Seq</th>
        <th style="padding:12px 12px; text-align:left; font-weight:700;">Classificação Orçamentária</th>
        <th style="padding:12px 12px; text-align:right; font-weight:700;">Autorizado (A)</th>
        <th style="padding:12px 12px; text-align:right; font-weight:700; background:rgba(255,255,255,0.12);">Indicado (I)</th>
        <th style="padding:12px 12px; text-align:right; font-weight:700;">Saldo Disponível p/<br>Indicação (A−I)</th>
        <th style="padding:12px 12px; text-align:right; font-weight:700;">Empenhado (E)</th>
        <th style="padding:12px 12px; text-align:right; font-weight:700;">Saldo Disponível p/<br>Empenho (A−E)</th>
        <th style="padding:12px 12px; text-align:right; font-weight:700;">Liquidado (L)</th>
        <th style="padding:12px 12px; text-align:right; font-weight:700;">Pago (P)</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
    <tfoot>
      <tr style="background:#065F46; color:#FFFFFF; font-weight:700; font-size:0.89rem;">
        <td style="padding:12px 12px; text-align:center;" colspan="2">Total ({qtd_seqs} sequenciais)</td>
        <td style="padding:12px 12px; text-align:right;">{fmt_brl(tot_aut, prefix=False)}</td>
        <td style="padding:12px 12px; text-align:right; background:rgba(255,255,255,0.14); color:#A7F3D0;">{fmt_brl(tot_ind, prefix=False)}</td>
        <td style="padding:12px 12px; text-align:right;">{fmt_brl(tot_saldo_ind, prefix=False)}</td>
        <td style="padding:12px 12px; text-align:right;">{fmt_brl(tot_emp, prefix=False)}</td>
        <td style="padding:12px 12px; text-align:right;">{fmt_brl(tot_saldo_emp, prefix=False)}</td>
        <td style="padding:12px 12px; text-align:right;">{fmt_brl(tot_liq, prefix=False)}</td>
        <td style="padding:12px 12px; text-align:right;">{fmt_brl(tot_pago, prefix=False)}</td>
      </tr>
    </tfoot>
  </table>
</div>
"""
st.html(table_html)

# Botão de download CSV da tabela consolidada
df_export = df_f[[
    "Seq", "Classificacao_Orcamentaria", "Acao_Label", "Grupo_Label", "Fonte_Label",
    "Autorizado", "Indicado", "Saldo_Indicacao", "Empenhado", "Saldo_Empenho", "Liquidado", "Pago", "Qtd_Indicacoes"
]].rename(columns={
    "Classificacao_Orcamentaria": "Classificação Orçamentária",
    "Acao_Label": "Ação Orçamentária",
    "Grupo_Label": "Grupo de Despesa",
    "Fonte_Label": "Fonte de Recursos",
    "Autorizado": "Autorizado (A)",
    "Indicado": "Indicado (I)",
    "Saldo_Indicacao": "Saldo Disponível p/ Indicação (A-I)",
    "Empenhado": "Empenhado (E)",
    "Saldo_Empenho": "Saldo Disponível p/ Empenho (A-E)",
    "Liquidado": "Liquidado (L)",
    "Pago": "Pago (P)",
    "Qtd_Indicacoes": "Qtd. Indicações Ativas",
})
csv_bytes = df_export.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig").encode("utf-8-sig")
st.download_button(
    "⬇️ Baixar Planilha Consolidada por Sequencial (CSV)",
    data=csv_bytes,
    file_name="indicacoes_por_sequencial_2026.csv",
    mime="text/csv",
)

st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ ABAS ANALÍTICAS E DRILL-DOWN DAS INDICAÇÕES
tab_graf, tab_det, tab_acao = st.tabs([
    "📊 Visão Analítica & Gráficos",
    "🔎 Detalhamento das Indicações (Aba Indicações 2026)",
    "🏛️ Consolidação por Ação & Grupo",
])

with tab_graf:
    g_col1, g_col2 = st.columns([1.1, 1.3])

    with g_col1:
        # Gráfico de Funil / Etapas da Execução Orçamentária
        etapas_df = pd.DataFrame({
            "Etapa": ["1. Autorizado (A)", "2. Indicado (I)", "3. Empenhado (E)", "4. Liquidado (L)", "5. Pago (P)"],
            "Valor": [tot_aut, tot_ind, tot_emp, tot_liq, tot_pago],
            "Cor": ["#065F46", "#047857", "#10B981", "#0D9488", "#2DD4BF"],
        })
        etapas_df["Texto"] = etapas_df["Valor"].apply(lambda v: f"{fmt_card_mi(v)} ({(v / tot_aut * 100 if tot_aut else 0):.1f}%)")
        fig_funil = px.bar(
            etapas_df,
            x="Valor",
            y="Etapa",
            orientation="h",
            text="Texto",
            color="Etapa",
            color_discrete_sequence=["#065F46", "#047857", "#10B981", "#0D9488", "#2DD4BF"],
            title="Funil Consolidado da Execução 2026 (A ➔ I ➔ E ➔ L ➔ P)",
        )
        fig_funil.update_traces(textposition="outside", cliponaxis=False)
        fig_funil.update_layout(showlegend=False, yaxis=dict(autorange="reversed"))
        st.plotly_chart(style(fig_funil, height=390), use_container_width=True)

    with g_col2:
        # Comparativo por Sequencial (Top 10 por Autorizado)
        top_seq = df_f.sort_values("Autorizado", ascending=False).head(10).copy()
        top_seq["Seq_Lbl"] = top_seq["Seq"].apply(lambda s: f"Seq {int(s)}")
        melt_seq = top_seq.melt(
            id_vars=["Seq_Lbl"],
            value_vars=["Autorizado", "Indicado", "Empenhado", "Liquidado", "Pago"],
            var_name="Estágio",
            value_name="Valor",
        )
        fig_seq = px.bar(
            melt_seq,
            x="Seq_Lbl",
            y="Valor",
            color="Estágio",
            barmode="group",
            color_discrete_map={
                "Autorizado": "#065F46",
                "Indicado": "#F59E0B",
                "Empenhado": "#10B981",
                "Liquidado": "#0D9488",
                "Pago": "#6EE7B7",
            },
            title="Comparativo por Sequencial (Top 10 Dotações)",
            labels={"Seq_Lbl": "Sequencial", "Valor": "Valor (R$)"},
        )
        st.plotly_chart(style(fig_seq, height=390), use_container_width=True)

with tab_det:
    st.markdown("#### 🔎 Lançamentos Individuais na Aba `Indicações` da Planilha 2026")
    if df_ind_all.empty:
        st.info("Nenhum lançamento encontrado na aba Indicações da planilha 2026.")
    else:
        d_col1, d_col2, d_col3, d_col4 = st.columns([1.0, 1.2, 1.0, 1.8])
        seqs_na_tabela = sorted(df_f["Seq"].unique().tolist())
        opcoes_seq_det = [f"Seq {s}" for s in sorted(df_ind_all["Seq"].unique().tolist())]

        with d_col1:
            sel_seq_det = st.multiselect(
                "Filtrar por Sequencial",
                options=opcoes_seq_det,
                default=[],
                placeholder="Todos os Sequenciais...",
            )
        with d_col2:
            unidades_det = sorted(df_ind_all["Unidade"].dropna().unique().tolist())
            sel_uni_det = st.multiselect(
                "Unidade (Aba Contratos)",
                options=unidades_det,
                default=[],
                placeholder="Todas as Unidades...",
            )
        with d_col3:
            sel_sit_det = st.selectbox(
                "Situação da Indicação",
                options=["Apenas Ativas (Compor Indicado)", "Todas (Ativas + Canceladas)", "Apenas Canceladas"],
                index=0,
            )
        with d_col4:
            busca_det = st.text_input(
                "Buscar por Processo SEI, Contrato, Objeto, Resumo ou IPOF",
                placeholder="Ex: 041/2025, Vigilância, 2025170100527...",
            )

        df_det = df_ind_all.copy()
        if sel_sit_det.startswith("Apenas Ativas"):
            df_det = df_det[df_det["Situacao_Clean"].str.lower() == "ativo"].copy()
        elif sel_sit_det.startswith("Apenas Canceladas"):
            df_det = df_det[df_det["Situacao_Clean"].str.lower() != "ativo"].copy()

        if sel_seq_det:
            seqs_nums = [int(s.replace("Seq ", "")) for s in sel_seq_det]
            df_det = df_det[df_det["Seq"].isin(seqs_nums)].copy()
        else:
            # Respeita os sequenciais filtrados no topo (ou inclui todos se não filtrado)
            if sel_acoes or sel_grupos:
                df_det = df_det[df_det["Seq"].isin(seqs_na_tabela)].copy()

        if sel_uni_det:
            df_det = df_det[df_det["Unidade"].isin(sel_uni_det)].copy()

        if busca_det.strip():
            termo_b = busca_det.strip().lower()
            mask_b = (
                df_det["Processo"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Contrato"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Objeto"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Resumo"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["IPOF"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Observação"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Empresa_Contratada"].astype(str).str.lower().str.contains(termo_b, na=False)
            )
            df_det = df_det[mask_b].copy()

        soma_det = float(df_det["Valor_Indicado_2026"].sum())
        st.caption(
            f"Exibindo **{len(df_det)}** lançamento(s) de indicação · Soma do Valor Indicado no filtro: **{fmt_brl(soma_det)}**"
        )

        df_det_view = df_det[[
            "Seq", "Item Aba Contratos", "Unidade", "Resumo", "Contrato",
            "Empresa_Contratada", "Processo", "IPOF", "Valor_Indicado_2026",
            "Situacao_Clean", "Data_Indicacao", "Observação"
        ]].copy()
        df_det_view["Data_Indicacao"] = df_det_view["Data_Indicacao"].dt.strftime("%d/%m/%Y").fillna("-")
        df_det_view = df_det_view.rename(columns={
            "Seq": "Sequencial",
            "Item Aba Contratos": "Item",
            "Resumo": "Despesa (Resumo)",
            "Empresa_Contratada": "Fornecedor / Empresa",
            "Processo": "Processo SEI",
            "Valor_Indicado_2026": "Valor Indicado 2026",
            "Situacao_Clean": "Situação",
            "Data_Indicacao": "Data",
        }).sort_values(["Sequencial", "Valor Indicado 2026"], ascending=[True, False])

        st.dataframe(
            df_det_view,
            use_container_width=True,
            hide_index=True,
            height=440,
            column_config={
                "Sequencial": st.column_config.NumberColumn("Seq", format="%d", width="small"),
                "Valor Indicado 2026": st.column_config.NumberColumn("Valor Indicado (R$)", format="R$ %.2f"),
            },
        )

with tab_acao:
    st.markdown("#### 🏛️ Consolidação por Ação Orçamentária")
    por_acao = (
        df_f.groupby(["Acao_Cod", "Acao_Label"], as_index=False)
        .agg(
            Sequenciais=("Seq", "count"),
            Autorizado=("Autorizado", "sum"),
            Indicado=("Indicado", "sum"),
            Saldo_Indicacao=("Saldo_Indicacao", "sum"),
            Empenhado=("Empenhado", "sum"),
            Saldo_Empenho=("Saldo_Empenho", "sum"),
            Liquidado=("Liquidado", "sum"),
            Pago=("Pago", "sum"),
        )
        .sort_values("Autorizado", ascending=False)
    )
    por_acao["% Indicado"] = (por_acao["Indicado"] / por_acao["Autorizado"] * 100).fillna(0.0)
    por_acao["% Empenhado"] = (por_acao["Empenhado"] / por_acao["Autorizado"] * 100).fillna(0.0)

    st.dataframe(
        por_acao.drop(columns=["Acao_Cod"]).rename(columns={
            "Acao_Label": "Ação Orçamentária",
            "Autorizado": "Autorizado (A)",
            "Indicado": "Indicado (I)",
            "Saldo_Indicacao": "Saldo p/ Indicação (A-I)",
            "Empenhado": "Empenhado (E)",
            "Saldo_Empenho": "Saldo p/ Empenho (A-E)",
            "Liquidado": "Liquidado (L)",
            "Pago": "Pago (P)",
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Autorizado (A)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Indicado (I)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Saldo p/ Indicação (A-I)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Empenhado (E)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Saldo p/ Empenho (A-E)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Liquidado (L)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Pago (P)": st.column_config.NumberColumn(format="R$ %.2f"),
            "% Indicado": st.column_config.NumberColumn(format="%.1f%%"),
            "% Empenhado": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    st.markdown("#### 📦 Consolidação por Grupo de Despesa (GND)")
    por_grp = (
        df_f.groupby("Grupo_Label", as_index=False)
        .agg(
            Sequenciais=("Seq", "count"),
            Autorizado=("Autorizado", "sum"),
            Indicado=("Indicado", "sum"),
            Saldo_Indicacao=("Saldo_Indicacao", "sum"),
            Empenhado=("Empenhado", "sum"),
            Saldo_Empenho=("Saldo_Empenho", "sum"),
            Liquidado=("Liquidado", "sum"),
            Pago=("Pago", "sum"),
        )
        .sort_values("Grupo_Label")
    )
    st.dataframe(
        por_grp.rename(columns={
            "Grupo_Label": "Grupo de Despesa",
            "Autorizado": "Autorizado (A)",
            "Indicado": "Indicado (I)",
            "Saldo_Indicacao": "Saldo p/ Indicação (A-I)",
            "Empenhado": "Empenhado (E)",
            "Saldo_Empenho": "Saldo p/ Empenho (A-E)",
            "Liquidado": "Liquidado (L)",
            "Pago": "Pago (P)",
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Autorizado (A)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Indicado (I)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Saldo p/ Indicação (A-I)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Empenhado (E)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Saldo p/ Empenho (A-E)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Liquidado (L)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Pago (P)": st.column_config.NumberColumn(format="R$ %.2f"),
        },
    )
