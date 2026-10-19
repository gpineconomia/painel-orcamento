"""Página: Alta Gestão — Fiel ao layout institucional com tabela hierárquica e cards de cota."""
from __future__ import annotations

import re
import pandas as pd
import streamlit as st

from common import brl, build_context, num

ctx = build_context(ano=2027)
st.session_state["ctx"] = ctx
df, total, cota = ctx.df, ctx.total, ctx.cota_tesouro
ANO = ctx.ANO
C_TOTAL = ctx.C_TOTAL
C_MESES = ctx.C_MESES
C_UNI = ctx.C_UNI
C_RES = ctx.C_RES
C_OBJ = ctx.C_OBJ
C_PROC = getattr(ctx, "C_PROC", None)
C_N_IPOF = getattr(ctx, "C_N_IPOF", None)
C_NUM = getattr(ctx, "C_NUM", None)
C_DEFICIT = getattr(ctx, "C_DEFICIT", None)

if ctx.warning:
    st.warning(ctx.warning)


def extrair_numeros(serie: pd.Series) -> list[str]:
    """Extrai números de processos/IPOFs (>= 5 dígitos) ordenados do mais recente para o mais antigo."""
    nums = []
    for v in serie.dropna():
        cleaned = str(v).replace("_x000D_", " ").replace("\xa0", " ")
        nums.extend(re.findall(r"\b\d{5,}\b", cleaned))
    return sorted(set(nums), reverse=True)


def extrair_contratos(serie: pd.Series) -> list[str]:
    """Extrai qualquer informação preenchida no campo Contrato preservando a ordem e sem duplicatas."""
    conts = []
    for v in serie.dropna():
        cleaned = str(v).replace("_x000D_", " ").replace("\xa0", " ").strip()
        if cleaned and cleaned.lower() not in ["nan", "none"] and cleaned not in conts:
            conts.append(cleaned)
    return conts


def fmt_br(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------ PREPARAÇÃO DOS DADOS
df = df.copy()
# Estimado Inicial: soma das colunas de janeiro a dezembro
df["_val_inicial"] = df[C_MESES].sum(axis=1) if C_MESES else pd.to_numeric(df[C_TOTAL], errors="coerce").fillna(0)
# Estimado Deficit
df["_val_deficit"] = pd.to_numeric(df[C_DEFICIT], errors="coerce").fillna(0) if C_DEFICIT and C_DEFICIT in df.columns else 0.0
# Estimado Total: Estimado Inicial + Estimado Deficit
df["_val_total"] = df["_val_inicial"] + df["_val_deficit"]

tot_inicial = float(df["_val_inicial"].sum())
tot_def = float(df["_val_deficit"].sum())
tot_geral = float(df["_val_total"].sum())
diff = tot_geral - cota

tot_cota_deficit = cota + tot_def
diff_cota_def = tot_geral - tot_cota_deficit

# ------------------------------------------------------------------ BANNER SUPERIOR
st.html(
    f"""<div style="background:#0A6B56; border-radius:12px; padding:12px 24px; margin-bottom:1.2rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 14px rgba(10,107,86,0.18);">
      <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
        Despesas por Unidade · Planejamento 2027
      </h2>
      <div style="text-align:right;">
        <div style="font-size:0.85rem; color:#A7F3D0; font-weight:600;">Secretaria de Estado da Economia · GPIN</div>
        <div style="font-size:0.75rem; color:#D1FAE5; opacity:0.85; margin-top:2px;">● Atualizado em {ctx.updated_at:%d/%m/%Y %H:%M}</div>
      </div>
    </div>"""
)

# ------------------------------------------------------------------ CARDS NO TOPO
c1, c2, c3, c4 = st.columns(4)

card_base_style = "border-radius:14px; padding:18px 22px; color:#FFFFFF; text-align:left; transition: transform 0.15s ease;"

with c1:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #064E3B 0%, #022C22 100%);
                    box-shadow: 0 6px 18px rgba(6,78,59,0.32), inset 0 1px 0 rgba(255,255,255,0.25);
                    border: 1.5px solid rgba(52,211,153,0.45); {card_base_style}">
          <div style="font-size:2.0rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_geral, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#6EE7B7; margin-top:8px; font-weight:700;">
            Estimado Total
          </div>
        </div>"""
    )

with c2:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #BE123C 0%, #9F1239 100%);
                    box-shadow: 0 4px 14px rgba(190,18,60,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:2.0rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_def, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#FECDD3; margin-top:8px; font-weight:700;">
            Estimado Déficit Autorizado
          </div>
        </div>"""
    )

with c3:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #0E7490 0%, #155E75 100%);
                    box-shadow: 0 4px 14px rgba(14,116,144,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:2.0rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(cota, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#A5F3FC; margin-top:8px; font-weight:700;">
            Cota Tesouro
          </div>
        </div>"""
    )

with c4:
    st.html(
        f"""<div class="notranslate" translate="no" style="background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
                    box-shadow: 0 4px 14px rgba(37,99,235,0.22), inset 0 1px 0 rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.15); {card_base_style}">
          <div style="font-size:2.0rem; font-weight:800; line-height:1.1; color:#FFFFFF; letter-spacing:-0.02em;">
            {brl(tot_cota_deficit, short=True).replace("R$ ", "")}
          </div>
          <div style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em;
                      color:#BFDBFE; margin-top:8px; font-weight:700;">
            Cota + Déficit
          </div>
        </div>"""
    )

st.write("")

# ------------------------------------------------------------------ CONTROLES DE ORDENAÇÃO
ctrl_col1, ctrl_col2, _ = st.columns([1.6, 1.3, 3])

with ctrl_col1:
    sort_col = st.selectbox(
        "Ordenar dados por:",
        ["Estimado Total", "Estimado Déficit", "Nome da Unidade"],
        index=0,
        key="sort_col_despesas",
    )

with ctrl_col2:
    sort_dir = st.selectbox(
        "Direção:",
        ["Decrescente (Maior ➔ Menor)", "Crescente (Menor ➔ Maior)"],
        index=0,
        key="sort_dir_despesas",
    )

# Configurações de colunas da tabela hierárquica
COL_CONFIGS = {
    "Estimado Total": {
        "key": "_val_total",
        "header": "Estimado Total",
        "width": 170,
        "format": lambda val, is_footer: fmt_br(val),
        "color": lambda val, is_footer: "#FFFFFF" if is_footer else "#0A6B56",
    },
    "Estimado Déficit": {
        "key": "_val_deficit",
        "header": "Estimado Déficit",
        "width": 150,
        "format": lambda val, is_footer: fmt_br(val) if is_footer else (fmt_br(val) if val > 0 else "—"),
        "color": lambda val, is_footer: "#FFFFFF" if is_footer else ("#DC2626" if val > 0 else "#94A3B8"),
    },
}

cols_ativas = ["Estimado Total", "Estimado Déficit"]

def render_valores(val_map: dict[str, float], font_size: str, peso: str = "700", is_footer: bool = False, custom_colors: dict | None = None) -> str:
    spans = []
    for c in cols_ativas:
        cfg = COL_CONFIGS[c]
        val = val_map.get(cfg["key"], 0.0)
        txt = cfg["format"](val, is_footer)
        cor = custom_colors.get(c) if custom_colors and c in custom_colors else cfg["color"](val, is_footer)
        spans.append(f'<span style="width:{cfg["width"]}px; color:{cor};">{txt}</span>')
    return (
        f'<div style="display:flex; gap:16px; align-items:center; font-variant-numeric:tabular-nums; '
        f'font-size:{font_size}; font-weight:{peso}; text-align:right;">'
        f'{"".join(spans)}'
        f'</div>'
    )

# ------------------------------------------------------------------ ESTADO DE EXPANSÃO (CONTROLE INFERIOR)
expandir_tudo = st.session_state.get("expandir_todas_despesas", False)

# ------------------------------------------------------------------ APLICAÇÃO DA ORDENAÇÃO
is_descending = sort_dir.startswith("Decrescente")
col_sort_map = {
    "Estimado Total": "_val_total",
    "Estimado Déficit": "_val_deficit",
}
sort_k = col_sort_map.get(sort_col, "_val_total")

if sort_col == "Nome da Unidade":
    ordem_unidades = df.groupby(C_UNI)["_val_total"].sum().sort_index(ascending=not is_descending)
else:
    ordem_unidades = df.groupby(C_UNI)[sort_k].sum().sort_values(ascending=not is_descending)

open_attr = "open" if expandir_tudo else ""

linhas_html = []
for idx, (unidade, total_u) in enumerate(ordem_unidades.items()):
    bg_row = "#F6FAF8" if idx % 2 == 1 else "#FFFFFF"
    sub_df = df[df[C_UNI] == unidade].copy()
    
    u_inicial = float(sub_df["_val_inicial"].sum())
    u_def = float(sub_df["_val_deficit"].sum())
    u_total = float(sub_df["_val_total"].sum())
    val_map_u = {"_val_inicial": u_inicial, "_val_deficit": u_def, "_val_total": u_total}
    
    itens_html = []
    col_agrup = sub_df[C_RES].fillna(sub_df[C_OBJ]).fillna("(sem resumo)")
    sub_df["_agrup"] = col_agrup
    
    if sort_col == "Nome da Unidade":
        resumos_ordem = sub_df.groupby("_agrup")["_val_total"].sum().sort_index(ascending=not is_descending)
    else:
        resumos_ordem = sub_df.groupby("_agrup")[sort_k].sum().sort_values(ascending=not is_descending)
    
    for r_nome, _ in resumos_ordem.items():
        linhas_resumo = sub_df[sub_df["_agrup"] == r_nome]
        r_inicial = float(linhas_resumo["_val_inicial"].sum())
        r_def = float(linhas_resumo["_val_deficit"].sum())
        r_total = float(linhas_resumo["_val_total"].sum())
        val_map_r = {"_val_inicial": r_inicial, "_val_deficit": r_def, "_val_total": r_total}
        
        if r_total > 0 or len(resumos_ordem) == 1:
            blocos_contrato_html = []
            if C_NUM:
                contratos_data = []
                conts_unicos = []
                for v in linhas_resumo[C_NUM]:
                    c_clean = str(v).replace("_x000D_", " ").replace("\xa0", " ").strip() if pd.notna(v) else ""
                    if c_clean and c_clean.lower() not in ["nan", "none"]:
                        if c_clean not in conts_unicos:
                            conts_unicos.append(c_clean)
                    else:
                        if "(Sem contrato)" not in conts_unicos:
                            conts_unicos.append("(Sem contrato)")
                
                for c_nome in conts_unicos:
                    if c_nome == "(Sem contrato)":
                        linhas_c = linhas_resumo[linhas_resumo[C_NUM].isna() | linhas_resumo[C_NUM].astype(str).str.strip().isin(["", "nan", "NaN", "(Sem contrato)"])]
                    else:
                        linhas_c = linhas_resumo[linhas_resumo[C_NUM].astype(str).str.replace("_x000D_", " ").str.replace("\xa0", " ").str.strip() == c_nome]
                    
                    val_c_inicial = float(linhas_c["_val_inicial"].sum())
                    val_c_def = float(linhas_c["_val_deficit"].sum())
                    val_c_total = float(linhas_c["_val_total"].sum())
                    val_map_c = {"_val_inicial": val_c_inicial, "_val_deficit": val_c_def, "_val_total": val_c_total}
                    procs_c = extrair_numeros(linhas_c[C_PROC]) if C_PROC else []
                    ipofs_c = extrair_numeros(linhas_c[C_N_IPOF]) if C_N_IPOF else []
                    contratos_data.append((c_nome, val_map_c, procs_c, ipofs_c))
                
                # Ordena os contratos
                if sort_col == "Nome da Unidade":
                    contratos_data.sort(key=lambda x: str(x[0]).lower(), reverse=is_descending)
                else:
                    contratos_data.sort(key=lambda x: x[1][sort_k], reverse=is_descending)
                
                for c_nome, val_map_c, procs_c, ipofs_c in contratos_data:
                    tags_c = []
                    if c_nome != "(Sem contrato)":
                        tags_c.append(
                            f'<span style="background:#F1F5F9; color:#1E293B; font-size:0.76rem; '
                            f'font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid #CBD5E1; '
                            f'font-variant-numeric:tabular-nums;">Contrato: {c_nome}</span>'
                        )
                    if procs_c:
                        tags_c.extend(
                            f'<span style="background:#EBF5F0; color:#0A6B56; font-size:0.75rem; '
                            f'font-weight:600; padding:2px 7px; border-radius:4px; border:1px solid #CDE5DA; '
                            f'font-variant-numeric:tabular-nums;">SEI {p}</span>'
                            for p in procs_c
                        )
                    if ipofs_c:
                        tags_c.extend(
                            f'<span style="background:#F0FDF4; color:#15803D; font-size:0.75rem; '
                            f'font-weight:600; padding:2px 7px; border-radius:4px; border:1px solid #BBF7D0; '
                            f'font-variant-numeric:tabular-nums;">IPOF {i}</span>'
                            for i in ipofs_c
                        )
                    
                    if tags_c or val_map_c["_val_total"] > 0:
                        tag_valor = render_valores(val_map_c, font_size="0.82rem", peso="600",
                                                   custom_colors={"Estimado Inicial": "#475569", "Estimado Total": "#0A6B56"})
                        blocos_contrato_html.append(
                            f'<div style="display:flex; justify-content:space-between; align-items:center; '
                            f'padding:4px 0; border-bottom:1px dotted #E2ECE6;">'
                            f'<div style="flex:1; display:flex; gap:8px; flex-wrap:wrap; align-items:center; padding-right:12px;">{"".join(tags_c)}</div>'
                            f'{tag_valor}'
                            f'</div>'
                        )
            else:
                val_c_inicial = float(linhas_resumo["_val_inicial"].sum())
                val_c_def = float(linhas_resumo["_val_deficit"].sum())
                val_c_total = float(linhas_resumo["_val_total"].sum())
                val_map_c = {"_val_inicial": val_c_inicial, "_val_deficit": val_c_def, "_val_total": val_c_total}
                procs = extrair_numeros(linhas_resumo[C_PROC]) if C_PROC else []
                ipofs = extrair_numeros(linhas_resumo[C_N_IPOF]) if C_N_IPOF else []
                tags_c = [f'<span style="background:#EBF5F0; color:#0A6B56; font-size:0.75rem; font-weight:600; padding:2px 7px; border-radius:4px; border:1px solid #CDE5DA;">SEI {p}</span>' for p in procs] + \
                         [f'<span style="background:#F0FDF4; color:#15803D; font-size:0.75rem; font-weight:600; padding:2px 7px; border-radius:4px; border:1px solid #BBF7D0;">IPOF {i}</span>' for i in ipofs]
                if tags_c or val_map_c["_val_total"] > 0:
                    tag_valor = render_valores(val_map_c, font_size="0.82rem", peso="600",
                                               custom_colors={"Estimado Inicial": "#475569", "Estimado Total": "#0A6B56"})
                    blocos_contrato_html.append(
                        f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                        f'<div style="flex:1; display:flex; gap:8px; flex-wrap:wrap; align-items:center; padding-right:12px;">{"".join(tags_c)}</div>'
                        f'{tag_valor}'
                        f'</div>'
                    )

            valores_resumo = render_valores(val_map_r, font_size="0.88rem", peso="600",
                                            custom_colors={"Estimado Inicial": "#334155", "Estimado Total": "#0A6B56"})
            has_detalhes = bool(blocos_contrato_html)
            if has_detalhes:
                detalhes_content = (
                    f'<div style="padding:6px 20px 8px 64px; background:#F4F9F6; '
                    f'border-bottom:1px dashed #D6E8DF; display:flex; flex-direction:column; gap:4px;">'
                    f'{"".join(blocos_contrato_html)}'
                    f'</div>'
                )
                itens_html.append(
                    f'<details {open_attr} style="border-bottom:1px dashed #E1EEE7;">'
                    f'<summary style="display:flex; justify-content:space-between; align-items:center; '
                    f'padding:8px 20px 8px 42px; font-size:0.88rem; color:#2D4A3E; cursor:pointer; '
                    f'background:#FBFDFD; list-style:none; user-select:none; transition: background 0.15s ease;">'
                    f'<span style="flex:1; display:flex; align-items:center; font-weight:500; padding-right:12px;">'
                    f'<span style="display:inline-block; width:14px; height:14px; line-height:12px; '
                    f'text-align:center; border:1px solid #059669; border-radius:3px; margin-right:8px; '
                    f'font-size:0.7rem; color:#059669; font-weight:bold;">+</span>'
                    f'{r_nome}</span>'
                    f'{valores_resumo}'
                    f'</summary>'
                    f'{detalhes_content}'
                    f'</details>'
                )
            else:
                itens_html.append(
                    f'<div style="display:flex; justify-content:space-between; align-items:center; '
                    f'padding:8px 20px 8px 42px; font-size:0.88rem; color:#2D4A3E; '
                    f'border-bottom:1px dashed #E1EEE7; background:#FBFDFD;">'
                    f'<span style="flex:1; display:flex; align-items:center; font-weight:500; padding-right:12px;">'
                    f'<span style="color:#059669; margin-right:8px; font-size:0.75rem;">▪</span>'
                    f'{r_nome}</span>'
                    f'{valores_resumo}'
                    f'</div>'
                )
    
    valores_unidade = render_valores(val_map_u, font_size="0.95rem", peso="700",
                                     custom_colors={"Estimado Inicial": "#0F2A20", "Estimado Total": "#0A6B56"})
    linhas_html.append(
        f'<details {open_attr} style="border-bottom:1px solid #DCEBE3;">'
        f'<summary style="display:flex; justify-content:space-between; align-items:center; '
        f'padding:11px 20px; font-weight:600; color:#0F2A20; cursor:pointer; '
        f'background:{bg_row}; list-style:none; user-select:none; transition: background 0.15s ease;">'
        f'<span style="flex:1; display:flex; align-items:center; padding-right:12px;">'
        f'<span style="display:inline-block; width:18px; height:18px; line-height:16px; '
        f'text-align:center; border:1px solid #0A6B56; border-radius:4px; margin-right:10px; '
        f'font-size:0.8rem; color:#0A6B56; font-weight:bold;">+</span>'
        f'{unidade}</span>'
        f'{valores_unidade}'
        f'</summary>'
        f'<div style="background:#FAFCFB;">{"".join(itens_html)}</div>'
        f'</details>'
    )

val_map_tot = {"_val_inicial": tot_inicial, "_val_deficit": tot_def, "_val_total": tot_geral}
valores_total = render_valores(val_map_tot, font_size="1.05rem", peso="800", is_footer=True)

# Indicador visual no cabeçalho de qual coluna está ordenando
arrow = "▼" if is_descending else "▲"
header_spans = []
for c in cols_ativas:
    cfg = COL_CONFIGS[c]
    indicator = f" {arrow}" if sort_col == c else ""
    header_spans.append(f'<span style="width:{cfg["width"]}px;">{cfg["header"]}{indicator}</span>')

unidade_indicator = f" {arrow}" if sort_col == "Nome da Unidade" else ""

tabela_completa = (
    f'<div class="notranslate" translate="no" style="border:1.5px solid #0A6B56; border-radius:14px; overflow-x:auto; '
    f'box-shadow:0 4px 18px rgba(10,107,86,0.08); background:#FFFFFF; margin-top:0.5rem; margin-bottom:1rem;">'
    f'<div style="background:#0A6B56; color:#FFFFFF; padding:12px 20px; font-weight:700; '
    f'font-size:0.92rem; display:flex; justify-content:space-between; align-items:center; letter-spacing:0.02em;">'
    f'<span style="flex:1;">Unidade{unidade_indicator}</span>'
    f'<div style="display:flex; gap:16px; align-items:center; text-align:right;">'
    f'{"".join(header_spans)}'
    f'</div>'
    f'</div>'
    f'<div>{"".join(linhas_html)}</div>'
    f'<div style="background:#0A6B56; color:#FFFFFF; padding:13px 20px; font-weight:800; '
    f'font-size:1.05rem; display:flex; justify-content:space-between; align-items:center;">'
    f'<span style="flex:1;">Total</span>'
    f'{valores_total}'
    f'</div>'
    f'</div>'
)

st.html(tabela_completa)

# ------------------------------------------------------------------ CONTROLE DE EXPANSÃO (EMBAIXO DA TABELA/FORMULÁRIO)
st.checkbox("Expandir todas as despesas", key="expandir_todas_despesas")
