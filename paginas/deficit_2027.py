"""Página: Déficit Orçamentário 2027 — Análise das demandas em rascunho com necessidade de suplementação."""
from __future__ import annotations

import io
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import brl, num, style, PALETTE, fmt_brl

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
def fmt_card_mi(v: float | int | None, decimals: int = 1) -> str:
    """Formata valor em milhões sempre com Mi (ex: 49,8 Mi, 0,5 Mi, 0,7 Mi), nunca 'mil'."""
    if v is None or pd.isna(v) or v == 0:
        return f"0,{0 * decimals} Mi" if decimals > 0 else "0 Mi"
    val = float(v)
    sign = "-" if val < 0 else ""
    return f"{sign}{abs(val) / 1e6:,.{decimals}f} Mi".replace(".", ",")


def fmt_grafico_mi(v: float | int | None, decimals: int = 1, prefix: str = "R$ ") -> str:
    """Formata valor em milhões para rótulos de gráfico (ex: R$ 0,5 Mi, R$ 26,3 Mi)."""
    if v is None or pd.isna(v) or v == 0:
        return f"{prefix}0,{0 * decimals} Mi" if decimals > 0 else f"{prefix}0 Mi"
    val = float(v)
    sign = "-" if val < 0 else ""
    return f"{prefix}{sign}{abs(val) / 1e6:,.{decimals}f} Mi".replace(".", ",")


tot_deficit = float(df["Valor"].sum())
qtd_itens = len(df)

# Subtotais por momento
val_imediato_urgente = float(df[df["Prazo"].isin(["Imediato", "Dezembro/2026", "Pendente Judicial"])]["Valor"].sum())
val_sem1 = float(df[df["Prazo"].isin(["Janeiro/2027", "Fevereiro/2027", "Março/2027", "Junho/2027"])]["Valor"].sum())
val_sem2 = float(df[df["Prazo"].isin(["Setembro/2027", "Outubro/2027"])]["Valor"].sum())
val_indet = float(df[df["Prazo"].str.contains("Indeterminado", case=False, na=False)]["Valor"].sum())

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
              {fmt_card_mi(tot_deficit, 1)}
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
              {fmt_card_mi(val_imediato_urgente, 1)}
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
              {fmt_card_mi(val_sem1, 1)}
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
              {fmt_card_mi(val_sem2, 1)}
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
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #4F46E5 0%, #3730A3 100%);
                    box-shadow: 0 4px 14px rgba(79,70,229,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(165,180,252,0.35); {card_base_style}">
          <div>
            <div style="font-size:1.85rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
              {fmt_card_mi(val_indet, 1)}
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

cores_unidades = {
    "Tecnologia da Informação": "#2563EB",
    "Gestão Integrada": "#059669",
    "Receita": "#7C3AED",
    "Receita/Gestão Integrada": "#D97706",
}

# ------------------------------------------------------------------ SEÇÃO ANALÍTICA & GRÁFICOS
tab_graficos, tab_tabela, tab_timeline = st.tabs([
    "📊 Gráficos & Distribuição",
    "📋 Tabela Detalhada do Déficit",
    "⏱️ Linha do Tempo da Necessidade",
])

# ------------------------------------------------------------------ ABA 3: LINHA DO TEMPO (INSPIRAÇÃO OFICIAL)
with tab_timeline:
    st.markdown(
        """<div style="margin-bottom: 18px;">
            <h3 style="margin:0; font-size:1.5rem; font-weight:800; color:#1B365D; letter-spacing:-0.02em;">
                Necessidade de crédito adicional prevista
            </h3>
            <div style="font-size:0.95rem; color:#64748B; margin-top:4px; font-weight:500;">
                Previsão de necessidades orçamentárias para 2027 · Secretaria de Estado da Economia
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    col_card, col_time = st.columns([1.1, 3.2], gap="large")

    with col_card:
        tot_deficit_str = f"{tot_deficit / 1e6:,.2f}".replace(".", ",")
        st.markdown(
            f"""<div style="background:#FFFFFF; border:1.5px solid #E2E8F0; border-radius:18px; padding:28px 20px;
                        box-shadow:0 6px 22px rgba(27,54,93,0.07); text-align:center; height:100%; min-height:560px;
                        display:flex; flex-direction:column; justify-content:space-between; position:relative; overflow:hidden;">
                <div>
                    <!-- Ícone Gráfico -->
                    <div style="width:78px; height:78px; margin:0 auto 18px auto; background:linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
                                border:2px solid #BFDBFE; border-radius:50%; display:flex; align-items:center; justify-content:center;
                                box-shadow:0 6px 16px rgba(37,99,235,0.12);">
                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#1D4ED8" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M3 3v18h18"/>
                            <path d="m19 9-5 5-4-4-3 3"/>
                            <path d="M14 9h5v5"/>
                        </svg>
                    </div>

                    <!-- Título -->
                    <div style="font-size:1.05rem; font-weight:800; color:#1B365D; line-height:1.35; letter-spacing:-0.01em; text-transform:uppercase;">
                        Previsão de Necessidade Orçamentária para 2027
                    </div>

                    <!-- Linha divisória verde -->
                    <div style="width:52px; height:3.5px; background:#0D9488; margin:16px auto; border-radius:2px;"></div>

                    <!-- Total Estimado -->
                    <div style="font-size:1.05rem; color:#64748B; font-weight:600; margin-top:8px;">
                        Total Estimado
                    </div>
                    <div style="font-size:2.35rem; font-weight:900; color:#0A6B56; line-height:1.1; margin-top:6px; letter-spacing:-0.02em;">
                        R$ {tot_deficit_str}
                    </div>
                    <div style="font-size:1.2rem; font-weight:800; color:#0A6B56; margin-top:2px;">
                        milhões
                    </div>
                    <div style="font-size:0.85rem; color:#64748B; margin-top:10px;">
                        ({len(df)} demandas mapeadas)
                    </div>
                </div>

                <!-- Rodapé -->
                <div style="margin-top:24px; padding-top:14px; border-top:1px solid #F1F5F9; font-size:0.75rem; color:#94A3B8; line-height:1.4;">
                    Observação: valores expressos em milhões de reais (R$ mi).
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    with col_time:
        # Monta as linhas da timeline a partir de df
        prazos_ordenados = sorted(
            df["Prazo"].unique(),
            key=lambda p: df[df["Prazo"] == p]["Ordem_Cronologica"].iloc[0]
        )

        linhas_html = []
        total_prazos = len(prazos_ordenados)

        for idx, prazo in enumerate(prazos_ordenados):
            sub_df = df[df["Prazo"] == prazo]
            prazo_val = float(sub_df["Valor"].sum())
            val_str = f"{prazo_val / 1e6:,.2f} mi".replace(".", ",")
            is_judicial = ("judicial" in prazo.lower())
            is_indet = ("indeterminado" in prazo.lower())
            is_primeiro = (idx == 0)
            is_ultimo = (idx == total_prazos - 1)

            if is_judicial:
                nome_periodo = "Pendência judicial"
                sub_periodo = "<div style='font-size:0.78rem; color:#DC2626; font-weight:700; margin-top:2px;'>(estão sem IPOF)</div>"
                cor_ponto = "#DC2626"
                cor_linha = "#DC2626"
                cor_texto = "#DC2626"
                bg_row = "#FFFBFB"
            elif is_indet:
                nome_periodo = "Prazo Indeterminado"
                sub_periodo = "<div style='font-size:0.78rem; color:#4F46E5; font-weight:600; margin-top:2px;'>(demanda sem data fixa)</div>"
                cor_ponto = "#4F46E5"
                cor_linha = "#4F46E5"
                cor_texto = "#3730A3"
                bg_row = "#FBFBFF"
            else:
                nome_periodo = prazo.replace("/", " de ")
                sub_periodo = ""
                cor_ponto = "#1E40AF"
                cor_linha = "#2563EB"
                cor_texto = "#1E293B"
                bg_row = "#FFFFFF"

            # Posição da linha vertical
            if is_primeiro:
                linha_css = f"top: 50%; bottom: 0; background: {cor_linha};"
            elif is_ultimo:
                linha_css = f"top: 0; bottom: 50%; background: {cor_linha};"
            else:
                linha_css = f"top: 0; bottom: 0; background: {cor_linha};"

            # Itens deste prazo
            itens_parts = []
            for _, r in sub_df.iterrows():
                v_mi = r["Valor"] / 1e6
                v_lbl = f"{v_mi:,.2f} milhões".replace(".", ",")
                d_nome = r["Despesa"].replace("**", "").strip()
                itens_parts.append(
                    f"""<div style="margin-bottom: 5px; line-height: 1.45;">
                        <strong style="color: #0F172A; font-weight: 700;">{v_lbl}</strong> &nbsp;|&nbsp; 
                        <span style="color: #334155;">{d_nome}</span>
                    </div>"""
                )
            bloco_itens = "".join(itens_parts)

            linhas_html.append(
                f"""<div style="display:grid; grid-template-columns: 210px 140px 1fr; border-bottom:1px solid #E2E8F0; background:{bg_row}; min-height: 58px;">
                    <!-- Coluna 1: Período com Linha e Ponto -->
                    <div style="position:relative; padding:14px 10px 14px 44px; display:flex; flex-direction:column; justify-content:center;">
                        <div style="position:absolute; left:22px; {linha_css} width:3.5px; z-index:1;"></div>
                        <div style="position:absolute; left:16px; top:calc(50% - 8px); width:16px; height:16px; border-radius:50%; border:3.5px solid {cor_ponto}; background:#FFFFFF; z-index:2; box-shadow:0 0 0 2px #FFFFFF;"></div>
                        <div style="font-weight:800; font-size:0.95rem; color:{cor_texto}; line-height:1.25;">{nome_periodo}</div>
                        {sub_periodo}
                    </div>

                    <!-- Coluna 2: Valor Estimado -->
                    <div style="display:flex; align-items:center; justify-content:center; font-size:1.25rem; font-weight:800; color:#0A6B56; text-align:center; padding:12px 6px; border-left:1px solid #F1F5F9; border-right:1px solid #F1F5F9;" title="Total: {fmt_brl(prazo_val)}">
                        {val_str}
                    </div>

                    <!-- Coluna 3: Itens / Ações Previstas -->
                    <div style="padding:12px 18px; font-size:0.87rem; display:flex; flex-direction:column; justify-content:center;">
                        {bloco_itens}
                    </div>
                </div>"""
            )

        corpo_tabela = "".join(linhas_html)

        st.markdown(
            f"""<div style="border:2px solid #4F46E5; border-radius:16px; overflow:hidden; background:#FFFFFF; box-shadow:0 8px 24px rgba(79,70,229,0.08);">
                <!-- Header Navy -->
                <div style="background:#1B365D; color:#FFFFFF; display:grid; grid-template-columns: 210px 140px 1fr; padding:12px 18px; font-weight:800; font-size:0.84rem; letter-spacing:0.05em; text-transform:uppercase;">
                    <div style="padding-left: 24px;">Período</div>
                    <div style="text-align: center;">Valor Estimado</div>
                    <div style="padding-left: 10px;">Itens / Ações Previstas</div>
                </div>
                <!-- Linhas -->
                {corpo_tabela}
                <!-- Rodapé -->
                <div style="background:#F8FAFC; padding:8px 18px; font-size:0.75rem; color:#64748B; font-weight:500; border-top:1px solid #E2E8F0;">
                    Valores expressos em milhões de reais (R$ mi).
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

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
        text=df_chrono["Valor"].apply(lambda v: fmt_grafico_mi(v, 1)),
        color="Prazo",
        color_discrete_sequence=px.colors.qualitative.Prism,
    )
    fig_chrono = style(fig_chrono, height=420)
    fig_chrono.update_traces(textposition="outside", cliponaxis=False)
    max_val_c = df_chrono["Valor"].max() if not df_chrono.empty else 1.0
    fig_chrono.update_layout(showlegend=False, xaxis_title=None, yaxis_title="Valor (R$)", margin=dict(l=10, r=40, t=50, b=10))
    fig_chrono.update_yaxes(range=[0, max_val_c * 1.25])
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
            text=df_t["Valor"].apply(lambda v: fmt_grafico_mi(v, 1)),
            color="Tipo_Demanda",
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig_tipo = style(fig_tipo, height=400)
        fig_tipo.update_traces(textposition="outside", cliponaxis=False)
        max_val_t = df_t["Valor"].max() if not df_t.empty else 1.0
        fig_tipo.update_xaxes(range=[0, max_val_t * 1.35], showticklabels=True)
        fig_tipo.update_layout(showlegend=False, xaxis_title=None, yaxis_title=None, margin=dict(l=10, r=80, t=50, b=10))
        st.plotly_chart(fig_tipo, width="stretch")

    # Gráfico 4: Top 10 Maiores Demandas com Déficit
    df_top = df.sort_values("Valor", ascending=False).head(10).copy()
    if not df_top.empty:
        nome_orig = df_top["Despesa"].astype(str).str.strip()
        nome_curto = nome_orig.where(nome_orig.str.len() <= 55, nome_orig.str.slice(0, 54) + "…")
        df_top["Item_Unico"] = nome_curto + nome_curto.groupby(nome_curto).cumcount().map(lambda k: "\u200b" * k)
        df_top["Rotulo_Mi"] = df_top["Valor"].apply(
            lambda v: fmt_grafico_mi(v, 1)
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
        fig_top = style(fig_top, height=480)
        fig_top.update_traces(
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{customdata[0]}</b><br>Unidade: %{customdata[1]}<br>Prazo: %{customdata[2]}<br>Valor: %{text} (%{customdata[3]:.1f}%)<extra></extra>",
            textfont=dict(size=12, color="#0F2A20", family="Inter, Segoe UI, sans-serif"),
        )
        max_val_top = df_top["Valor"].max() if not df_top.empty else 1.0
        fig_top.update_xaxes(range=[0, max_val_top * 1.35], showticklabels=False, title=None)
        fig_top.update_yaxes(title=None, tickfont=dict(size=12))
        fig_top.update_layout(margin=dict(l=10, r=80, t=50, b=10))
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

    # 2. Filtros Específicos em Linha e Ordenação
    fc1, fc2, fc3, fc4 = st.columns([1.5, 1.1, 1.1, 1.1])
    with fc1:
        f_busca_tab = st.text_input(
            "🔍 Buscar na tabela",
            placeholder="Digite contrato, serviço ou palavra-chave...",
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
    with fc4:
        ordem_tab = st.selectbox(
            "Ordenar por:",
            ["Maior Valor (R$)", "Menor Valor (R$)", "Cronológico (Prazo)", "Despesa (A-Z)", "Unidade"],
            key="tab_def_ordem",
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
        df_tab = df_tab[df_tab["Prazo"].str.contains("Indeterminado", case=False, na=False)]

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

    # Aplica ordenação selecionada
    if ordem_tab == "Maior Valor (R$)":
        df_tab = df_tab.sort_values(by="Valor", ascending=False)
    elif ordem_tab == "Menor Valor (R$)":
        df_tab = df_tab.sort_values(by="Valor", ascending=True)
    elif ordem_tab == "Cronológico (Prazo)":
        df_tab = df_tab.sort_values(by=["Ordem_Cronologica", "Valor"], ascending=[True, False])
    elif ordem_tab == "Despesa (A-Z)":
        df_tab = df_tab.sort_values(by="Despesa", ascending=True)
    elif ordem_tab == "Unidade":
        df_tab = df_tab.sort_values(by=["Unidade", "Valor"], ascending=[True, False])

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
                Total Filtrado: <strong style="font-size:1.15rem; color:#0A6B56;">{fmt_brl(tot_tab)}</strong> 
                <span style="font-size:0.85rem; color:#15803D; font-weight:600;">({f"{pct_tab:.1f}%".replace(".", ",")} do déficit ativo)</span>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    if df_tab.empty:
        st.info("Nenhuma demanda encontrada para os filtros selecionados na tabela.")
    else:
        # 4. Tabela Interativa Formatada no Padrão Brasileiro (X.XXX.XXX,XX)
        df_view = df_tab.copy()
        df_view["Valor (R$)"] = df_view["Valor"].apply(fmt_brl)
        df_view["% do Déficit"] = df_view["% do Déficit"].apply(lambda v: f"{v:.2f}%".replace(".", ","))

        cols_display = ["Despesa", "Unidade", "Tipo_Demanda", "Prazo", "Categoria_Prazo", "Valor (R$)", "% do Déficit"]

        st.dataframe(
            df_view[cols_display],
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
                "Valor (R$)": st.column_config.TextColumn(
                    "Valor do Déficit (R$)",
                    help="Valor no padrão monetário brasileiro (R$ X.XXX.XXX,XX)",
                    alignment="right",
                ),
                "% do Déficit": st.column_config.TextColumn(
                    "% do Déficit",
                    help="Participação percentual da despesa sobre o déficit total",
                    alignment="right",
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
                                <span style="font-size:1.25rem; font-weight:800; color:#0A6B56;">{fmt_brl(d_val)}</span>
                            </div>
                            <div>
                                <span style="font-size:0.75rem; color:#64748B; text-transform:uppercase; font-weight:600;">Impacto no Déficit</span><br>
                                <span style="font-size:1.25rem; font-weight:800; color:#2563EB;">{f"{d_pct:.2f}%".replace(".", ",")}</span>
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
