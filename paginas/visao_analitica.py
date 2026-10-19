"""Página: análise detalhada do planejamento (para a equipe de planejamento)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from plotly.subplots import make_subplots

from common import ACCENT, MESES, NI, PALETTE, chart_top_despesas, chart_unidades, brl, build_context, kpi, num, style

ctx = build_context(ano=2027)
st.session_state["ctx"] = ctx
df, ANO, DIMS = ctx.df, ctx.ANO, ctx.DIMS
C_TOTAL, C_MESES = ctx.C_TOTAL, ctx.C_MESES
C_ITEM, C_OBJ, C_NUM, C_EMP, C_CLASS = ctx.C_ITEM, ctx.C_OBJ, ctx.C_NUM, ctx.C_EMP, ctx.C_CLASS
C_SIT, C_IPOF, C_GRUPO, C_TIPO = ctx.C_SIT, ctx.C_IPOF, ctx.C_GRUPO, ctx.C_TIPO
C_UNI, C_DEP, C_PROF = ctx.C_UNI, ctx.C_DEP, ctx.C_PROF
C_FIM, C_ULT, C_GLOBAL = ctx.C_FIM, ctx.C_ULT, ctx.C_GLOBAL
total, por_grupo = ctx.total, ctx.por_grupo

if ctx.warning:
    st.warning(ctx.warning)

# ------------------------------------------------------------------ BANNER SUPERIOR
st.html(
    f"""<div style="background:#0A6B56; border-radius:12px; padding:12px 24px; margin-bottom:1.2rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 14px rgba(10,107,86,0.18);">
      <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
        Visão Analítica · Planejamento 2027
      </h2>
      <div style="text-align:right;">
        <div style="font-size:0.85rem; color:#A7F3D0; font-weight:600;">Secretaria de Estado da Economia · GPIN</div>
        <div style="font-size:0.75rem; color:#D1FAE5; opacity:0.85; margin-top:2px;">● Atualizado em {ctx.updated_at:%d/%m/%Y %H:%M}</div>
      </div>
    </div>"""
)

# ------------------------------------------------------------------ CARDS NO TOPO (PADRÃO VISÃO ANALÍTICA)
tot_geral = float(df[C_TOTAL].sum())
tot_custeio = float(por_grupo.get("Custeio", 0.0))
tot_invest = float(por_grupo.get("Investimento", 0.0))
pct_custeio = (tot_custeio / tot_geral * 100) if tot_geral > 0 else 0.0
pct_invest = (tot_invest / tot_geral * 100) if tot_geral > 0 else 0.0
cota = ctx.cota_tesouro
saldo_cota = cota - tot_geral
sem_est = int((df[C_TOTAL] == 0).sum())

c1, c2, c3, c4, c5 = st.columns(5)
card_base_style = "border-radius:14px; padding:16px 18px; color:#FFFFFF; text-align:left; transition: transform 0.15s ease;"

with c1:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #064E3B 0%, #022C22 100%);
                    box-shadow: 0 6px 18px rgba(6,78,59,0.32), inset 0 1px 0 rgba(255,255,255,0.25);
                    border: 1.5px solid rgba(52,211,153,0.45); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_geral, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#6EE7B7; margin-top:8px; font-weight:700;">
            Estimado Total {ANO}
          </div>
        </div>"""
    )

with c2:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #312E81 0%, #1E1B4B 100%);
                    box-shadow: 0 4px 14px rgba(49,46,129,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(165,180,252,0.3); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_custeio, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#C7D2FE; margin-top:8px; font-weight:700; display:flex; justify-content:space-between;">
            <span>Custeio</span>
            <span style="background:rgba(255,255,255,0.2); padding:1px 6px; border-radius:4px;">{pct_custeio:.1f}%</span>
          </div>
        </div>"""
    )

with c3:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #0284C7 0%, #0369A1 100%);
                    box-shadow: 0 4px 14px rgba(2,132,199,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(186,230,253,0.3); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_invest, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#BAE6FD; margin-top:8px; font-weight:700; display:flex; justify-content:space-between;">
            <span>Investimento</span>
            <span style="background:rgba(255,255,255,0.2); padding:1px 6px; border-radius:4px;">{pct_invest:.1f}%</span>
          </div>
        </div>"""
    )

with c4:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #0E7490 0%, #155E75 100%);
                    box-shadow: 0 4px 14px rgba(14,116,144,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(cota, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#A5F3FC; margin-top:8px; font-weight:700;">
            Cota Tesouro
          </div>
        </div>"""
    )

with c5:
    saldo_color = "#BFDBFE" if saldo_cota >= 0 else "#FECDD3"
    saldo_bg = "linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)" if saldo_cota >= 0 else "linear-gradient(135deg, #991B1B 0%, #7F1D1D 100%)"
    st.html(
        f"""<div class="notranslate" translate="no" style="background: {saldo_bg};
                    box-shadow: 0 4px 14px rgba(37,99,235,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(saldo_cota, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:{saldo_color}; margin-top:8px; font-weight:700;">
            Saldo Orçamentário
          </div>
        </div>"""
    )

st.write("")

tab_geral, tab_onde, tab_quando, tab_qual, tab_dados = st.tabs(
    ["📊 Visão geral", "📍 Onde", "📅 Quando", "✅ Andamento e qualidade", "📋 Dados"]
)

# ------------------------------------------------------------------ Visão geral
with tab_geral:
    a, b = st.columns((2, 3))
    fig = chart_unidades(ctx, 520)
    if fig is not None:
        a.plotly_chart(fig, width="stretch")
    b.plotly_chart(chart_top_despesas(ctx, 15, 520), width="stretch")

# ------------------------------------------------------------------ Onde
with tab_onde:
    dim_label = st.selectbox("Agrupar por", [d for d in DIMS if d != "Situação"], index=list(DIMS).index("Unidade")
                             if "Unidade" in DIMS else 0, key="dim_onde")
    dim = DIMS[dim_label]
    stack_label = st.selectbox("Quebrar cores por", [d for d in DIMS if d != dim_label],
                               index=0, key="stack_onde")
    stack = DIMS[stack_label]
    cats = df.groupby(dim)[C_TOTAL].sum().sort_values(ascending=False)
    keep = cats.head(15).index
    g = df[df[dim].isin(keep)].groupby([dim, stack])[C_TOTAL].sum().reset_index()
    fig = px.bar(g, y=dim, x=C_TOTAL, color=stack, orientation="h", barmode="stack",
                 title=f"Estimado {ANO} por {dim_label} (top 15), por {stack_label}",
                 category_orders={dim: list(keep)[::-1]}, labels={C_TOTAL: "Estimado (R$)"})
    st.plotly_chart(style(fig, max(380, 32 * len(keep) + 120)), width="stretch")

    if C_MESES:
        h = df[df[dim].isin(keep)].groupby(dim)[C_MESES].sum().loc[list(keep)]
        h.columns = [c.replace("Estimado ", "")[:3] for c in h.columns]
        fig = px.imshow(h, aspect="auto", color_continuous_scale="Greens", text_auto=".2s",
                        title=f"Mapa de calor: {dim_label} × mês (R$)")
        st.plotly_chart(style(fig, max(380, 32 * len(keep) + 120)), width="stretch")

# ------------------------------------------------------------------ Quando
with tab_quando:
    q1, q2 = st.columns((3, 1))
    dim_q_label = q2.selectbox("Quebrar por", list(DIMS), index=0, key="dim_q")
    dim_q = DIMS[dim_q_label]
    m = df.groupby(dim_q)[C_MESES].sum()
    ordem = m.sum(axis=1).sort_values(ascending=False).index
    if len(ordem) > 8:
        resto = m.loc[ordem[8:]].sum()
        m = m.loc[ordem[:8]]
        m.loc["Outros"] = resto
    else:
        m = m.loc[ordem]
    m = m.rename_axis(dim_q)
    mm = m.reset_index().melt(id_vars=dim_q, var_name="Mês", value_name="Estimado")
    mm["Mês"] = mm["Mês"].str.replace("Estimado ", "", regex=False)
    fig = px.bar(mm, x="Mês", y="Estimado", color=dim_q, barmode="stack",
                 category_orders={"Mês": MESES}, title=f"Estimado {ANO} por mês e {dim_q_label}")
    q1.plotly_chart(style(fig, 440), width="stretch")

    mensal = pd.DataFrame({"Mês": MESES[:len(C_MESES)], "Estimado": [df[c].sum() for c in C_MESES]})
    mensal["Acumulado"] = mensal["Estimado"].cumsum()
    mensal["% do ano"] = mensal["Estimado"] / mensal["Estimado"].sum() * 100 if mensal["Estimado"].sum() else 0
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=mensal["Mês"], y=mensal["Estimado"], name="Mensal", marker_color=PALETTE[0])
    fig.add_scatter(x=mensal["Mês"], y=mensal["Acumulado"], name="Acumulado", mode="lines+markers",
                    line=dict(color=ACCENT, width=3), secondary_y=True)
    fig.update_layout(title=f"Fluxo mensal e acumulado {ANO}")
    fig.update_yaxes(showgrid=False, secondary_y=True)
    st.plotly_chart(style(fig, 380), width="stretch")
    fmt_moeda = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731
    mensal_display = pd.DataFrame({
        "Mês": mensal["Mês"],
        "Estimado (R$)": mensal["Estimado"].map(fmt_moeda),
        "Acumulado (R$)": mensal["Acumulado"].map(fmt_moeda),
        "% do ano": mensal["% do ano"].map(lambda v: f"{v:,.1f}%".replace(".", ",")),
    })
    st.dataframe(mensal_display, hide_index=True, width="stretch")

# ------------------------------------------------------------------ Andamento e qualidade
with tab_qual:
    s1, s2 = st.columns(2)
    if C_IPOF:
        ip = df.assign(**{C_IPOF: df[C_IPOF].str.replace("\n", " ")}).groupby(C_IPOF).agg(
            Despesas=(C_TOTAL, "size"), Estimado=(C_TOTAL, "sum")).reset_index()
        fig = px.bar(ip.sort_values("Estimado"), y=C_IPOF, x="Estimado", orientation="h", text="Despesas",
                     title="Situação do IPOF (valor estimado; rótulo = nº de despesas)")
        fig.update_traces(marker_color=PALETTE[0], texttemplate="%{text} desp.")
        s1.plotly_chart(style(fig, 360), width="stretch")
    if C_TIPO:
        tp = df.groupby(C_TIPO)[C_TOTAL].sum().reset_index()
        fig = px.bar(tp.sort_values(C_TOTAL), y=C_TIPO, x=C_TOTAL, orientation="h",
                     title="Tipo de Despesa (Permanente / Sazonal)", labels={C_TOTAL: "Estimado"})
        fig.update_traces(marker_color=PALETTE[1])
        s2.plotly_chart(style(fig, 360), width="stretch")

    st.subheader("Pontos de atenção")
    cols_view = [c for c in (C_ITEM, C_NUM, C_OBJ, C_UNI, C_GRUPO, C_IPOF, C_TOTAL) if c]
    cfg_cols = {C_TOTAL: st.column_config.NumberColumn(format="R$ %.2f")}

    st.markdown(f"**Despesas sem estimativa {ANO}** (valor = 0): {num(sem_est)}")
    with st.expander("Ver despesas sem estimativa"):
        st.dataframe(df[df[C_TOTAL] == 0][cols_view], hide_index=True, width="stretch", column_config=cfg_cols)

    soma = df[C_MESES].sum(axis=1)
    div = df[(soma - df[C_TOTAL]).abs() > 1]
    st.markdown(f"**Total ≠ soma dos meses**: {num(len(div))}")
    if len(div):
        with st.expander("Ver divergências"):
            st.dataframe(div.assign(**{"Soma dos meses": soma[div.index]})[cols_view + ["Soma dos meses"]],
                         hide_index=True, width="stretch",
                         column_config={**cfg_cols, "Soma dos meses": st.column_config.NumberColumn(format="R$ %.2f")})

    incompleto = df[(df[C_TOTAL] > 0) & ((df[C_GRUPO] == NI) | (df[C_UNI] == NI) | (df[C_TIPO] == NI))] \
        if C_GRUPO and C_UNI and C_TIPO else df.iloc[0:0]
    st.markdown(f"**Com estimativa mas sem Grupo/Tipo/Unidade preenchidos**: {num(len(incompleto))}")
    if len(incompleto):
        with st.expander("Ver despesas incompletas"):
            st.dataframe(incompleto[cols_view + [C_TIPO]], hide_index=True, width="stretch", column_config=cfg_cols)

    if C_ULT:
        dias = st.slider("Considerar estimativa desatualizada após (dias)", 15, 180, 60, key="dias")
        limite = pd.Timestamp.today().normalize() - pd.Timedelta(days=dias)
        base = df[df[C_TOTAL] > 0]
        velha = base[base["_ult"].notna() & (base["_ult"] < limite)]
        sem_data = base[base["_ult"].isna()]
        st.markdown(f"**Estimativa desatualizada (> {dias} dias)**: {num(len(velha))} · "
                    f"**Sem data da última estimativa**: {num(len(sem_data))}")
        with st.expander("Ver estimativas desatualizadas"):
            st.dataframe(velha.sort_values("_ult")[cols_view + ["_ult"]].rename(columns={"_ult": "Última estimativa"}),
                         hide_index=True, width="stretch",
                         column_config={**cfg_cols, "Última estimativa": st.column_config.DateColumn(format="DD/MM/YYYY")})

# ------------------------------------------------------------------ Dados
with tab_dados:
    C_DEFICIT = getattr(ctx, "C_DEFICIT", None)
    cols = [c for c in (C_ITEM, C_NUM, C_OBJ, C_CLASS, C_EMP, C_SIT, C_IPOF, C_GRUPO, C_TIPO, C_UNI,
                        C_FIM, C_GLOBAL, C_DEFICIT, C_TOTAL, *C_MESES) if c]
    view = df[cols].sort_values(C_ITEM if C_ITEM else C_TOTAL, ascending=True).copy()
    if C_FIM:  # mistura datas e texto ("Indeterminado")
        view[C_FIM] = view[C_FIM].map(lambda x: "" if pd.isna(x) else str(x)[:10])
    st.dataframe(
        view, hide_index=True, width="stretch", height=600,
        column_config={c: st.column_config.NumberColumn(format="R$ %.2f") for c in [C_TOTAL, C_GLOBAL, C_DEFICIT, *C_MESES] if c},
    )
    st.download_button("⬇️ Baixar CSV filtrado", view.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       "planejamento_despesas.csv", "text/csv")
