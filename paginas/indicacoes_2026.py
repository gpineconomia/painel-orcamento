"""Página: Indicações Orçamentárias por Sequencial — Execução 2026."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import common
from common import style
import indicacoes_data


def fmt_brl(v: float | int | None, prefix: bool = True) -> str:
    """Formata valor monetário sempre no padrão brasileiro (ex: R$ 3.684.748,35 ou 3.684.748,35)."""
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


def fmt_mi_always(v: float | int | None) -> str:
    """Formata valor financeiro sempre em R$ XX,XX Mi para os cards."""
    if v is None or pd.isna(v):
        return "R$ 0,00 Mi"
    try:
        val = float(v)
        if abs(val) < 0.005:
            return "R$ 0,00 Mi"
        sign = "-" if val < 0 else ""
        a = abs(val)
        s = f"{a / 1e6:,.2f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {sign}{s}"
    except Exception:
        return str(v)


def fmt_pct(v: float | int | None) -> str:
    """Formata percentual no padrão brasileiro (ex: 95,0%)."""
    if v is None or pd.isna(v):
        return "0,0%"
    return f"{float(v):.1f}%".replace(".", ",")


# ------------------------------------------------------------------ CARREGAMENTO DOS DADOS
try:
    df_seq_all, df_ind_all, updated_sap, updated_plan = indicacoes_data.load_consolidado_indicacoes_2026()
except Exception as exc:
    st.error(f"Erro ao carregar dados de Indicações 2026: {exc}")
    st.stop()

if df_seq_all.empty:
    st.warning("Não há dados disponíveis para exibição.")
    st.stop()

# ------------------------------------------------------------------ BANNER SUPERIOR
dt_sap_str = updated_sap.strftime("%d/%m/%Y às %H:%M") if updated_sap else "N/D"

st.html(
    f"""<div style="background:#0F2A20; border-radius:12px; padding:12px 24px; margin-bottom:1.1rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 14px rgba(15,42,32,0.18); flex-wrap:wrap; gap:12px;">
      <div>
        <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
          🎯 Indicações Orçamentárias por Sequencial · Execução 2026
        </h2>
      </div>
      <div style="font-size:0.85rem; color:#A7F3D0; text-align:right;">
        <strong>Fonte Oficial:</strong> SIAFIC e GPIN<br>
        <span style="font-size:0.75rem; color:#D1FAE5;">Sincronizado em: {dt_sap_str}</span>
      </div>
    </div>"""
)

# ------------------------------------------------------------------ FILTROS NA BARRA LATERAL
fontes_disp = sorted(df_seq_all["Fonte_Label"].unique().tolist())
default_fontes = [
    f for f in fontes_disp
    if "17540111" not in str(f) and "profisco" not in str(f).lower()
]

acoes_disp = sorted(df_seq_all["Acao_Label"].unique().tolist())
grupos_disp = sorted(df_seq_all["Grupo_Label"].unique().tolist())
seqs_disp = [str(int(s)) for s in sorted(df_seq_all["Seq"].unique().tolist())]

with st.sidebar:
    st.header("Filtros de Dotação")

    sel_fontes = st.multiselect(
        "Fonte de Recursos",
        options=fontes_disp,
        default=default_fontes,
        key="f_ind_fontes_sem_profisco",
        help="A fonte 17540111 (Operações de Crédito Externas - PROFISCO) vem desmarcada por padrão.",
    )

    sel_acoes = st.multiselect(
        "Ação Orçamentária",
        options=acoes_disp,
        default=[],
        key="f_ind_acoes",
        placeholder="Todas as Ações...",
    )

    sel_grupos = st.multiselect(
        "Grupo de Despesa",
        options=grupos_disp,
        default=[],
        key="f_ind_grupos",
        placeholder="Todos os Grupos...",
    )

    sel_seqs = st.multiselect(
        "Nº do Sequencial",
        options=seqs_disp,
        default=[],
        key="f_ind_seqs",
        placeholder="Todos os Sequenciais...",
    )

    ocultar_zerados = st.checkbox(
        "Apenas c/ Dotação > 0",
        value=True,
        key="f_ind_ocultar_zerados",
        help="Oculta sequenciais com valor Autorizado (A) igual a 0,00.",
    )

    st.divider()
    if st.button("🔄 Atualizar Dados", use_container_width=True):
        with st.spinner("Sincronizando SIAFIC e Planilha 2026 (SharePoint)..."):
            try:
                import sync_github
                sync_github.refresh_sharepoint_caches()
                indicacoes_data.download_declarado_empenhado_seq_csv()
                sync_github.sync_to_github(refresh_sp=False)
            except Exception:
                indicacoes_data.download_declarado_empenhado_seq_csv()
            st.cache_data.clear()
            st.rerun()

# Aplica filtros no DataFrame por Sequencial
df_f = df_seq_all.copy()
if sel_fontes:
    df_f = df_f[df_f["Fonte_Label"].isin(sel_fontes)].copy()
if sel_acoes:
    df_f = df_f[df_f["Acao_Label"].isin(sel_acoes)].copy()
if sel_grupos:
    df_f = df_f[df_f["Grupo_Label"].isin(sel_grupos)].copy()
if sel_seqs:
    df_f = df_f[df_f["Seq"].astype(int).astype(str).isin(sel_seqs)].copy()
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

pct_ind_aut = (tot_ind / tot_aut * 100) if tot_aut > 0 else 0.0
pct_emp_aut = (tot_emp / tot_aut * 100) if tot_aut > 0 else 0.0
pct_liq_aut = (tot_liq / tot_aut * 100) if tot_aut > 0 else 0.0
pct_pag_aut = (tot_pago / tot_aut * 100) if tot_aut > 0 else 0.0
pct_emp_ind = (tot_emp / tot_ind * 100) if tot_ind > 0 else 0.0
pct_liq_emp = (tot_liq / tot_emp * 100) if tot_emp > 0 else 0.0
pct_pag_liq = (tot_pago / tot_liq * 100) if tot_liq > 0 else 0.0
pct_saldo_ind = (tot_saldo_ind / tot_aut * 100) if tot_aut > 0 else 0.0
pct_saldo_emp = (tot_saldo_emp / tot_aut * 100) if tot_aut > 0 else 0.0

# ------------------------------------------------------------------ LINHA 1: TERMÔMETRO (% SOBRE O AUTORIZADO) - ESTILO "DESPESAS POR UNIDADE"
t1, t2, t3, t4 = st.columns(4)
card_base_style = "border-radius:14px; padding:16px 18px; color:#FFFFFF; text-align:left; transition: transform 0.15s ease;"

with t1:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #064E3B 0%, #022C22 100%);
                    box-shadow: 0 6px 18px rgba(6,78,59,0.32), inset 0 1px 0 rgba(255,255,255,0.25);
                    border: 1.5px solid rgba(52,211,153,0.45); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {fmt_pct(pct_ind_aut)}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#6EE7B7; margin-top:8px; font-weight:700;">
            Indicado (I / A)
          </div>
        </div>"""
    )

with t2:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #312E81 0%, #1E1B4B 100%);
                    box-shadow: 0 4px 14px rgba(49,46,129,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(165,180,252,0.3); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {fmt_pct(pct_emp_aut)}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#C7D2FE; margin-top:8px; font-weight:700;">
            Empenhado (E / A)
          </div>
        </div>"""
    )

with t3:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #0E7490 0%, #155E75 100%);
                    box-shadow: 0 4px 14px rgba(14,116,144,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {fmt_pct(pct_liq_aut)}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#A5F3FC; margin-top:8px; font-weight:700;">
            Liquidado (L / A)
          </div>
        </div>"""
    )

with t4:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
                    box-shadow: 0 4px 14px rgba(37,99,235,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {fmt_pct(pct_pag_aut)}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#BFDBFE; margin-top:8px; font-weight:700;">
            Pago (P / A)
          </div>
        </div>"""
    )

st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ LINHA 2: 5 CARDS PRINCIPAIS DO FUNIL (EM R$ XX,XX Mi)
c1, c2, c3, c4, c5 = st.columns(5)
common.kpi(
    c1,
    "Autorizado (A)",
    fmt_mi_always(tot_aut),
)
common.kpi(
    c2,
    "Indicado (I)",
    fmt_mi_always(tot_ind),
)
common.kpi(
    c3,
    "Empenhado (E)",
    fmt_mi_always(tot_emp),
)
common.kpi(
    c4,
    "Liquidado (L)",
    fmt_mi_always(tot_liq),
)
common.kpi(
    c5,
    "Pago (P)",
    fmt_mi_always(tot_pago),
)

st.markdown("<div style='height:0.65rem'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ LINHA 3: 4 CARDS DE SALDOS DISPONÍVEIS E GAPS (EM R$ XX,XX Mi)
s1, s2, s3, s4 = st.columns(4)
common.kpi(
    s1,
    "Saldo Disponível p/ Indicação (A − I)",
    fmt_mi_always(tot_saldo_ind),
    warn=(tot_saldo_ind < 0),
)
common.kpi(
    s2,
    "Saldo Disponível p/ Empenho (A − E)",
    fmt_mi_always(tot_saldo_emp),
    warn=(tot_saldo_emp < 0),
)
common.kpi(
    s3,
    "Indicado a Empenhar (I − E)",
    fmt_mi_always(tot_ind_a_emp),
    warn=(tot_ind_a_emp > 5_000_000),
)
common.kpi(
    s4,
    "Empenhado a Liquidar (E − L)",
    fmt_mi_always(tot_emp_a_liq),
)

st.markdown("<div style='height:1.1rem'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ TABELA PRINCIPAL POR SEQUENCIAL
st.markdown("### 📋 Quadro de Execução Orçamentária por Sequencial (Dotação)")

rows_html = []
for idx, (_, r) in enumerate(df_f.iterrows()):
    bg = "#FFFFFF" if idx % 2 == 0 else "#E6F4EE"
    seq_n = int(r["Seq"])
    class_orc = r["Classificacao_Orcamentaria"]
    acao_c = r["Acao_Cod"]
    acao_desc = indicacoes_data.ACOES_DESCRICAO.get(acao_c, f"Ação {acao_c}")
    grp_lbl = r["Grupo_Label"]

    v_aut = float(r["Autorizado"])
    v_ind = float(r["Indicado"])
    v_s_ind = float(r["Saldo_Indicacao"])
    v_emp = float(r["Empenhado"])
    v_s_emp = float(r["Saldo_Empenho"])
    v_liq = float(r["Liquidado"])
    v_pag = float(r["Pago"])

    cor_s_ind = "#B91C1C" if v_s_ind < -0.01 else ("#047857" if v_s_ind > 0.01 else "#64748B")
    cor_s_emp = "#B91C1C" if v_s_emp < -0.01 else ("#047857" if v_s_emp > 0.01 else "#64748B")

    rows_html.append(
        f"""<tr style="background:{bg}; border-bottom:1px solid #DCEBE3;">
          <td style="padding:9px 12px; font-weight:700; color:#0F2A20; text-align:center;">{seq_n}</td>
          <td style="padding:9px 12px;">
            <div style="font-weight:600; color:#0F2A20; font-family:'Inter',monospace; font-size:0.84rem;">{class_orc}</div>
            <div style="font-size:0.73rem; color:#334155; margin-top:3px;"><strong>Ação:</strong> {acao_c} - {acao_desc}</div>
            <div style="font-size:0.73rem; color:#5B7A6C; margin-top:1px;"><strong>Grupo:</strong> {grp_lbl}</div>
          </td>
          <td style="padding:9px 12px; text-align:right; font-weight:600; color:#0F2A20;">{fmt_brl(v_aut, prefix=False)}</td>
          <td style="padding:9px 12px; text-align:right; font-weight:600; color:#0F2A20;">{fmt_brl(v_ind, prefix=False)}</td>
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
        <th style="padding:12px 12px; text-align:right; font-weight:700;">Indicado (I)</th>
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
        <td style="padding:12px 12px; text-align:right;">{fmt_brl(tot_ind, prefix=False)}</td>
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
    "Autorizado", "Indicado", "Saldo_Indicacao", "Empenhado", "Saldo_Empenho", "Liquidado", "Pago"
]].copy()
for c_num in ("Autorizado", "Indicado", "Saldo_Indicacao", "Empenhado", "Saldo_Empenho", "Liquidado", "Pago"):
    df_export[c_num] = df_export[c_num].apply(lambda v: fmt_brl(v, prefix=False))

df_export = df_export.rename(columns={
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
})
csv_bytes = df_export.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
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
        etapas_df = pd.DataFrame({
            "Etapa": ["1. Autorizado (A)", "2. Indicado (I)", "3. Empenhado (E)", "4. Liquidado (L)", "5. Pago (P)"],
            "Valor": [tot_aut, tot_ind, tot_emp, tot_liq, tot_pago],
        })
        etapas_df["Texto"] = etapas_df["Valor"].apply(
            lambda v: f"{fmt_brl(v)} ({fmt_pct(v / tot_aut * 100 if tot_aut else 0)})"
        )
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
        fig_funil.update_traces(
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
        )
        fig_funil.update_layout(showlegend=False, yaxis=dict(autorange="reversed"), xaxis_title="Valor (R$)")
        st.plotly_chart(style(fig_funil, height=390), use_container_width=True)

    with g_col2:
        top_seq = df_f.sort_values("Autorizado", ascending=False).head(10).copy()
        top_seq["Seq_Lbl"] = top_seq["Seq"].apply(lambda s: f"Seq {int(s)}")
        melt_seq = top_seq.melt(
            id_vars=["Seq_Lbl"],
            value_vars=["Autorizado", "Indicado", "Empenhado", "Liquidado", "Pago"],
            var_name="Estágio",
            value_name="Valor",
        )
        melt_seq["Valor_Fmt"] = melt_seq["Valor"].apply(fmt_brl)
        fig_seq = px.bar(
            melt_seq,
            x="Seq_Lbl",
            y="Valor",
            color="Estágio",
            barmode="group",
            custom_data=["Estágio", "Valor_Fmt"],
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
        fig_seq.update_traces(
            hovertemplate="<b>%{x}</b> — %{customdata[0]}<br>Valor: <b>%{customdata[1]}</b><extra></extra>"
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
                "Buscar por Item, Processo SEI, Contrato, Objeto, Resumo ou IPOF",
                placeholder="Ex: 428, 041/2025, Vigilância, 2025170100527...",
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
            if sel_acoes or sel_grupos or sel_seqs:
                df_det = df_det[df_det["Seq"].isin(seqs_na_tabela)].copy()

        if sel_uni_det:
            df_det = df_det[df_det["Unidade"].isin(sel_uni_det)].copy()

        if busca_det.strip():
            termo_b = busca_det.strip().lower()
            mask_item_exato = df_det["Item Aba Contratos"].astype(str).str.strip().str.lower() == termo_b
            mask_b = (
                mask_item_exato
                | df_det["Item Aba Contratos"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Processo"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Contrato"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Objeto"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Resumo"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["IPOF"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Observação"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Empresa_Contratada"].astype(str).str.lower().str.contains(termo_b, na=False)
                | df_det["Unidade"].astype(str).str.lower().str.contains(termo_b, na=False)
            )
            df_det = df_det[mask_b].copy()
            df_det["_match_item_exato"] = (df_det["Item Aba Contratos"].astype(str).str.strip().str.lower() == termo_b).astype(int)
        else:
            df_det["_match_item_exato"] = 0

        soma_det = float(df_det["Valor_Indicado_2026"].sum())
        st.caption(
            f"Exibindo **{len(df_det)}** lançamento(s) de indicação · Soma do Valor Indicado no filtro: **{fmt_brl(soma_det)}**"
        )

        df_det["_item_num"] = pd.to_numeric(df_det["Item Aba Contratos"], errors="coerce").fillna(0)
        df_det_sorted = df_det.sort_values(
            ["_match_item_exato", "Data_Indicacao", "_item_num", "Valor_Indicado_2026"],
            ascending=[False, False, False, False],
        ).copy()
        df_det_view = pd.DataFrame({
            "Seq": df_det_sorted["Seq"].astype(int),
            "Item": df_det_sorted["Item Aba Contratos"],
            "Unidade": df_det_sorted["Unidade"],
            "Despesa (Resumo)": df_det_sorted["Resumo"],
            "Contrato": df_det_sorted["Contrato"],
            "Fornecedor / Empresa": df_det_sorted["Empresa_Contratada"],
            "Processo SEI": df_det_sorted["Processo"],
            "IPOF": df_det_sorted["IPOF"],
            "Valor Indicado 2026": df_det_sorted["Valor_Indicado_2026"].apply(lambda v: fmt_brl(v, prefix=False)),
            "Situação": df_det_sorted["Situacao_Clean"],
            "Data": df_det_sorted["Data_Indicacao"].dt.strftime("%d/%m/%Y").fillna("-"),
            "Observação": df_det_sorted["Observação"],
        })

        st.dataframe(
            df_det_view,
            use_container_width=True,
            hide_index=True,
            height=440,
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

    por_acao_fmt = pd.DataFrame({
        "Ação Orçamentária": por_acao["Acao_Label"],
        "Sequenciais": por_acao["Sequenciais"].astype(int),
        "Autorizado (A)": por_acao["Autorizado"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Indicado (I)": por_acao["Indicado"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Saldo p/ Indicação (A−I)": por_acao["Saldo_Indicacao"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Empenhado (E)": por_acao["Empenhado"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Saldo p/ Empenho (A−E)": por_acao["Saldo_Empenho"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Liquidado (L)": por_acao["Liquidado"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Pago (P)": por_acao["Pago"].apply(lambda v: fmt_brl(v, prefix=False)),
        "% Indicado": por_acao["% Indicado"].apply(fmt_pct),
        "% Empenhado": por_acao["% Empenhado"].apply(fmt_pct),
    })

    st.dataframe(
        por_acao_fmt,
        use_container_width=True,
        hide_index=True,
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
    por_grp_fmt = pd.DataFrame({
        "Grupo de Despesa": por_grp["Grupo_Label"],
        "Sequenciais": por_grp["Sequenciais"].astype(int),
        "Autorizado (A)": por_grp["Autorizado"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Indicado (I)": por_grp["Indicado"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Saldo p/ Indicação (A−I)": por_grp["Saldo_Indicacao"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Empenhado (E)": por_grp["Empenhado"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Saldo p/ Empenho (A−E)": por_grp["Saldo_Empenho"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Liquidado (L)": por_grp["Liquidado"].apply(lambda v: fmt_brl(v, prefix=False)),
        "Pago (P)": por_grp["Pago"].apply(lambda v: fmt_brl(v, prefix=False)),
    })

    st.dataframe(
        por_grp_fmt,
        use_container_width=True,
        hide_index=True,
    )
