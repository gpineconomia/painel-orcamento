"""Página: Liquidação Mensal por Contrato — Execução 2026 vs SAP BO (ConsultaLiquidadoMensal ID: 32115483)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import difflib
import re
import unicodedata
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


def safe_float(v: object) -> float:
    """Converte valor para float de forma segura tratando NaN, None e strings vazias como 0.0."""
    if v is None:
        return 0.0
    try:
        val = pd.to_numeric(v, errors="coerce")
        if pd.isna(val) or val != val:
            return 0.0
        return float(val)
    except Exception:
        return 0.0


def extrair_procs(val: object) -> list[str]:
    """Extrai sequências de 10 a 16 dígitos correspondentes a Processos SEI."""
    if val is None or pd.isna(val):
        return []
    return re.findall(r"\d{10,16}", str(val))


def normalizar_texto(s: str) -> str:
    """Normaliza texto removendo acentos, pontuações e convertendo para maiúsculas."""
    if not s or str(s).strip() in ["", "-", "nan", "None"]:
        return ""
    s_norm = unicodedata.normalize('NFKD', str(s).upper()).encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^A-Z0-9 ]', ' ', s_norm)


STOP_WORDS = {
    'LTDA', 'EIRELI', 'ME', 'EPP', 'SA', 'EMPRESA', 'SERVICOS', 'COMERCIO',
    'ADMINISTRACAO', 'SOLUCOES', 'TECNOLOGIA', 'DO', 'DA', 'DE', 'DOS', 'DAS', 'E'
}


def clean_tokens(s: str) -> set[str]:
    """Retorna conjunto de tokens relevantes excluindo stop words e palavras curtas."""
    norm = normalizar_texto(s)
    words = [w for w in norm.split() if len(w) >= 3 and w not in STOP_WORDS]
    return set(words)


def match_fornecedor_beneficiario(forn_str: str, benef_str: str) -> float:
    """Calcula pontuação de similaridade entre o nome do Fornecedor e o Beneficiário SIAFIC."""
    t_f = clean_tokens(forn_str)
    t_b = clean_tokens(benef_str)
    if not t_f or not t_b:
        return 0.0
    inter = t_f.intersection(t_b)
    if inter:
        return 1.0 + len(inter) * 0.5
    for w1 in t_f:
        if len(w1) >= 4:
            for w2 in t_b:
                if len(w2) >= 4:
                    if w1 in w2 or w2 in w1 or difflib.SequenceMatcher(None, w1, w2).ratio() >= 0.8:
                        return 0.8
    return 0.0


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
      <div>
        <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
          📜 Liquidação Mensal por Contrato · Execução 2026
        </h2>
        <div style="font-size:0.8rem; color:#A7F3D0; margin-top:4px;">
          Filtros de base aplicados: Situação ≠ Excluído &nbsp;|&nbsp; PROFISCO ≠ Sim
        </div>
      </div>
      <div style="font-size:0.85rem; color:#A7F3D0; text-align:right;">
        <strong>Fonte Oficial SIAFIC:</strong> ConsultaLiquidadoMensal (ID: 32115483)<br>
        <span style="font-size:0.75rem; color:#D1FAE5;">Sincronizado em: {dt_sap_str}</span>
      </div>
    </div>"""
)

# ------------------------------------------------------------------ TRATAMENTO DA PLANILHA 2026
col_sit = [c for c in df_planilha_raw.columns if "situa" in str(c).lower() and "ipof" not in str(c).lower()]
col_profisco = [c for c in df_planilha_raw.columns if "profisco" in str(c).lower()]

df_plan = df_planilha_raw.copy()

# Desconsidera despesas com Situação = Excluído
if col_sit:
    df_plan = df_plan[~df_plan[col_sit[0]].astype(str).str.lower().str.contains("exclu")].copy()

# Desconsidera despesas com PROFISCO = Sim
if col_profisco:
    df_plan = df_plan[~df_plan[col_profisco[0]].astype(str).str.strip().str.lower().isin(["sim", "s"])].copy()

col_item = [c for c in df_plan.columns if str(c).strip().lower() == "item"][0]
col_contrato = [c for c in df_plan.columns if "contrato" in str(c).lower() and "global" not in str(c).lower()][0]
col_proc = [c for c in df_plan.columns if "processo" in str(c).lower() and "sislog" not in str(c).lower()][0]
col_obj = [c for c in df_plan.columns if "objeto" in str(c).lower()][0]
col_forn_list = [c for c in df_plan.columns if "empresa" in str(c).lower() or "contratada" in str(c).lower()]
col_forn = col_forn_list[0] if col_forn_list else None
col_uni = [c for c in df_plan.columns if "unidade" in str(c).lower()][0]
col_gnd_list = [c for c in df_plan.columns if "grupo de despesa" in str(c).lower()]
col_gnd = col_gnd_list[0] if col_gnd_list else None
col_class_list = [c for c in df_plan.columns if "classifica" in str(c).lower()]
col_class = col_class_list[0] if col_class_list else None
col_total_est = "Estimado Total 2026"

meses_nomes = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]
cod_meses = [f"2026{i:02d}" for i in range(1, 13)]
map_cod_to_nome = {f"2026{i:02d}": meses_nomes[i-1] for i in range(1, 13)}
map_nome_to_cod = {meses_nomes[i-1]: f"2026{i:02d}" for i in range(1, 13)}

# ------------------------------------------------------------------ TRATAMENTO DO SAP BO E CRUZAMENTO POR CONTRATO
# A liquidação é identificada pela coluna Período Referência no formato AAAAMM (AAAA=Ano, MM=Mês)
if "Ano_Referencia" in df_sap.columns:
    df_sap_2026 = df_sap[df_sap["Ano_Referencia"] == 2026].copy()
else:
    df_sap_2026 = df_sap[df_sap["Periodo_AnoMes"].astype(str).str.startswith("2026")].copy()

# 1. Agrupamento da planilha por Contrato (itens que compõem o mesmo contrato são consolidados)
contratos_agrupados: dict[str, dict] = {}
proc_to_c_keys: dict[str, set[str]] = {}

for _, r_pl in df_plan.iterrows():
    c_raw = str(r_pl.get(col_contrato, "")).replace("_x000D_", " ").replace("\xa0", " ").strip()
    tem_contrato_formal = bool(c_raw and c_raw.lower() not in ["nan", "none", "<na>", "", "em planejamento", "não se aplica", "nao se aplica"])
    
    item_str = str(r_pl.get(col_item, "")).replace(".0", "").strip()
    chave_contrato = c_raw.replace(".0", "") if tem_contrato_formal else f"(Sem Contrato Formal - Item {item_str})"
    
    procs_item = extrair_procs(r_pl.get(col_proc, ""))
    val_est_tot = safe_float(r_pl.get(col_total_est))
    
    if chave_contrato not in contratos_agrupados:
        contratos_agrupados[chave_contrato] = {
            "Contrato": chave_contrato,
            "Tem_Contrato_Formal": tem_contrato_formal,
            "Itens": set(),
            "Processos_SEI": set(),
            "Objetos": set(),
            "Fornecedores": set(),
            "Unidades": set(),
            "Grupos_Despesa": set(),
            "Classificacoes": set(),
            "Estimado_Total": 0.0,
            "Estimado_Meses": {m: 0.0 for m in meses_nomes},
            "Total_Liquidado_SIAFIC": 0.0,
            "Liquidado_Meses": {m: 0.0 for m in meses_nomes},
            "Beneficiarios_SIAFIC": set(),
            "Naturezas_SIAFIC": set(),
            "Lancamentos_SIAFIC": [],
        }
        
    contratos_agrupados[chave_contrato]["Itens"].add(item_str)
    contratos_agrupados[chave_contrato]["Processos_SEI"].update(procs_item)
    if pd.notna(r_pl.get(col_obj)):
        contratos_agrupados[chave_contrato]["Objetos"].add(str(r_pl.get(col_obj)).strip())
    if col_forn and pd.notna(r_pl.get(col_forn)) and str(r_pl.get(col_forn)).strip() not in ["", "-"]:
        contratos_agrupados[chave_contrato]["Fornecedores"].add(str(r_pl.get(col_forn)).strip())
    if pd.notna(r_pl.get(col_uni)):
        contratos_agrupados[chave_contrato]["Unidades"].add(str(r_pl.get(col_uni)).strip())
    if col_gnd and pd.notna(r_pl.get(col_gnd)):
        contratos_agrupados[chave_contrato]["Grupos_Despesa"].add(str(r_pl.get(col_gnd)).strip())
    if col_class and pd.notna(r_pl.get(col_class)):
        contratos_agrupados[chave_contrato]["Classificacoes"].add(str(r_pl.get(col_class)).strip())
        
    contratos_agrupados[chave_contrato]["Estimado_Total"] += val_est_tot
    for m in meses_nomes:
        c_m = f"Estimado {m}"
        contratos_agrupados[chave_contrato]["Estimado_Meses"][m] += safe_float(r_pl.get(c_m))

    for p in procs_item:
        proc_to_c_keys.setdefault(p, set()).add(chave_contrato)

# 2. Atribuição inteligente das linhas do SIAFIC (SAP BO) aos contratos
# Quando 2 ou mais contratos compartilham o mesmo Processo SEI, diferencia pelo Beneficiário vs Fornecedor
sobras_sap_rows: list[dict] = []

for _, row_sap in df_sap_2026.iterrows():
    p = str(row_sap.get("Processo_SEI", "")).strip()
    b = str(row_sap.get("Beneficiario_Nome", "")).strip()
    nat = str(row_sap.get("Natureza_Despesa_Nome", "")).strip()
    v = safe_float(row_sap.get("Valor_Liquidado_Saldo", 0))
    m_cod = str(row_sap.get("Periodo_AnoMes", "")).strip()
    m_nome = map_cod_to_nome.get(m_cod)

    c_candidatos = proc_to_c_keys.get(p, set()) if p else set()
    if not c_candidatos:
        sobras_sap_rows.append(row_sap.to_dict())
        continue

    if len(c_candidatos) == 1:
        targets_with_weights = [(list(c_candidatos)[0], 1.0)]
    else:
        # Calcula a melhor pontuação de similaridade para cada contrato candidato
        scores: dict[str, float] = {}
        for c_cand in c_candidatos:
            sc_max = 0.0
            for forn in contratos_agrupados[c_cand]["Fornecedores"]:
                sc = match_fornecedor_beneficiario(forn, b)
                if sc > sc_max:
                    sc_max = sc
            scores[c_cand] = sc_max

        best_score = max(scores.values()) if scores else 0.0
        if best_score <= 0.0:
            # Beneficiário não corresponde aos fornecedores dos contratos candidatos -> sobra
            sobras_sap_rows.append(row_sap.to_dict())
            continue

        best_candidates = [c for c, sc in scores.items() if sc == best_score]
        if len(best_candidates) == 1:
            targets_with_weights = [(best_candidates[0], 1.0)]
        else:
            # Empate: mais de um contrato do mesmo processo possui o mesmo fornecedor (ex: lotes 025/2024 e 032/2024 com BRFIBRA)
            # Rateia o lançamento proporcionalmente à estimativa total de cada contrato empatado
            soma_est = sum(contratos_agrupados[c]["Estimado_Total"] for c in best_candidates)
            if soma_est > 0:
                targets_with_weights = [(c, contratos_agrupados[c]["Estimado_Total"] / soma_est) for c in best_candidates]
            else:
                targets_with_weights = [(c, 1.0 / len(best_candidates)) for c in best_candidates]

    for c_target, peso in targets_with_weights:
        v_part = v * peso
        c_dict = contratos_agrupados[c_target]
        c_dict["Total_Liquidado_SIAFIC"] += v_part
        if m_nome in c_dict["Liquidado_Meses"]:
            c_dict["Liquidado_Meses"][m_nome] += v_part
        if b:
            c_dict["Beneficiarios_SIAFIC"].add(b)
        if nat:
            c_dict["Naturezas_SIAFIC"].add(nat)
        row_dict = row_sap.to_dict()
        row_dict["Valor_Liquidado_Saldo"] = v_part
        c_dict["Lancamentos_SIAFIC"].append(row_dict)

# 3. Montagem das linhas consolidadas por contrato
linhas_consolidadas = []

for c_key, c_data in contratos_agrupados.items():
    procs = list(c_data["Processos_SEI"])
    tot_liquidado_siafic = c_data["Total_Liquidado_SIAFIC"]
    meses_liquidado = {f"Liquidado_{m}": c_data["Liquidado_Meses"][m] for m in meses_nomes}
    beneficiarios_siafic = c_data["Beneficiarios_SIAFIC"]
    
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
    gnd_display = ", ".join(sorted(c_data["Grupos_Despesa"])) or "-"
    class_display = " / ".join(sorted(c_data["Classificacoes"])) or "-"
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
        "Grupo_Despesa": gnd_display,
        "Classificacao": class_display,
        "Estimado_Total_2026": val_est,
        "Total_Liquidado_SIAFIC": tot_liquidado_siafic,
        "Saldo_A_Liquidar": saldo_a_liquidar,
        "Pct_Executado": pct_exec,
        "Status_Execucao": status_exec,
        "Lancamentos_SIAFIC": c_data["Lancamentos_SIAFIC"],
        **meses_liquidado,
        **{f"Estimado_{m}": c_data["Estimado_Meses"][m] for m in meses_nomes}
    }
    linhas_consolidadas.append(row_out)

df_contratos = pd.DataFrame(linhas_consolidadas)

# ------------------------------------------------------------------ FILTROS NA BARRA LATERAL
with st.sidebar:
    st.header("Filtros de Liquidação")
    
    # 1. Unidade Gestora (desmembrada e individualizada)
    unidades_set = set()
    for u in df_contratos["Unidade"].dropna():
        for item_u in str(u).split(","):
            item_clean = item_u.strip()
            if item_clean and item_clean != "-":
                unidades_set.add(item_clean)
    opts_uni = sorted(unidades_set)
    sel_uni = st.multiselect("Unidade Gestora", opts_uni, key="f_liq_uni")
    
    # 2. Grupo de Despesa (Custeio vs Investimento)
    gnd_set = set()
    for g in df_contratos["Grupo_Despesa"].dropna():
        for item_g in str(g).split(","):
            item_clean = item_g.strip()
            if item_clean and item_clean != "-":
                gnd_set.add(item_clean)
    opts_gnd = sorted(gnd_set)
    sel_gnd = st.multiselect("Grupo de Despesa", opts_gnd, key="f_liq_gnd")
    
    # 3. Status de Execução
    opts_status = sorted(df_contratos["Status_Execucao"].unique())
    sel_status = st.multiselect("Status de Execução", opts_status, key="f_liq_status")
    
    # 4. Faixa de Execução Orçamentária
    filtro_faixa = st.selectbox(
        "Faixa de Execução:",
        [
            "Todos os Contratos",
            "Sem percentual",
            "Maior que zero até 49%",
            "De 50 a 75%",
            "Acima de 75% até 100%",
            "Acima de 100%"
        ],
        key="f_liq_faixa"
    )
    
    # 5. Tipo de Item
    tipo_contrato = st.radio(
        "Tipo de Item:",
        ["Apenas Contratos Formalizados", "Todos os Itens", "Sem Contrato Formalizado"],
        key="f_liq_tipo"
    )
    
    # 6. Busca Livre
    busca_livre = st.text_input("🔎 Buscar (Contrato, Processo, Fornecedor, Objeto)", key="f_liq_busca")

# Aplicação dos filtros
df_view = df_contratos.copy()
if sel_uni:
    df_view = df_view[df_view["Unidade"].apply(lambda u: any(x in str(u) for x in sel_uni))]
if sel_gnd:
    df_view = df_view[df_view["Grupo_Despesa"].apply(lambda g: any(x in str(g) for x in sel_gnd))]
if sel_status:
    df_view = df_view[df_view["Status_Execucao"].isin(sel_status)]
if tipo_contrato == "Apenas Contratos Formalizados":
    df_view = df_view[df_view["Tem_Contrato_Formal"]]
elif tipo_contrato == "Sem Contrato Formalizado":
    df_view = df_view[~df_view["Tem_Contrato_Formal"]]

if filtro_faixa == "Sem percentual":
    df_view = df_view[(df_view["Total_Liquidado_SIAFIC"] == 0) | (df_view["Pct_Executado"] == 0)]
elif filtro_faixa == "Maior que zero até 49%":
    df_view = df_view[(df_view["Pct_Executado"] > 0) & (df_view["Pct_Executado"] < 50.0)]
elif filtro_faixa == "De 50 a 75%":
    df_view = df_view[(df_view["Pct_Executado"] >= 50.0) & (df_view["Pct_Executado"] <= 75.0)]
elif filtro_faixa == "Acima de 75% até 100%":
    df_view = df_view[(df_view["Pct_Executado"] > 75.0) & (df_view["Pct_Executado"] <= 100.0)]
elif filtro_faixa == "Acima de 100%":
    df_view = df_view[df_view["Pct_Executado"] > 100.0]

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
tz_brasilia = timezone(timedelta(hours=-3))
hoje = datetime.now(tz_brasilia)
dia_atual = hoje.day
mes_atual = hoje.month

# Regra: % Executado Proporcional DO ANO até o momento (Janeiro até mês de corte)
# Devido ao delay operacional para apresentação e liquidação de notas fiscais, considera-se até 2 meses anteriores
idx_fim_prop = max(1, mes_atual - 2)
nome_fim_prop = meses_nomes[idx_fim_prop - 1]
meses_prop_lista = meses_nomes[:idx_fim_prop]

total_estimado_geral = df_view["Estimado_Total_2026"].sum()
total_liquidado_geral = df_view["Total_Liquidado_SIAFIC"].sum()
saldo_restante_geral = total_estimado_geral - total_liquidado_geral
pct_geral = (total_liquidado_geral / total_estimado_geral * 100) if total_estimado_geral > 0 else 0.0

total_est_prop_geral = sum(df_view[f"Estimado_{m}"].sum() for m in meses_prop_lista)
total_liq_prop_geral = sum(df_view[f"Liquidado_{m}"].sum() for m in meses_prop_lista)
pct_prop_geral = (total_liq_prop_geral / total_est_prop_geral * 100) if total_est_prop_geral > 0 else (100.0 if total_liq_prop_geral > 0 else 0.0)

contratos_com_liq_count = (df_view["Total_Liquidado_SIAFIC"] > 0).sum()

k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    st.markdown(
        f'<div class="kpi"><div class="label">Total Estimado 2026</div>'
        f'<div class="value">{fmt_card_mi(total_estimado_geral)}</div>'
        f'<div class="sub">{num(len(df_view))} contratos/despesas</div></div>',
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
        f'<div class="sub">Restante orçamentário anual</div></div>',
        unsafe_allow_html=True
    )
with k4:
    st.markdown(
        f'<div class="kpi"><div class="label">% Executado Total</div>'
        f'<div class="value">{pct_geral:.1f}%</div>'
        f'<div class="sub">Do orçamento anual 2026</div></div>',
        unsafe_allow_html=True
    )
with k5:
    st.markdown(
        f'<div class="kpi"><div class="label">% Exec. Proporcional</div>'
        f'<div class="value">{pct_prop_geral:.1f}%</div>'
        f'<div class="sub">Jan a {nome_fim_prop[:3]}/26 (delay 2 meses)</div></div>',
        unsafe_allow_html=True
    )

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ ABAS DETALHADAS
tab_contrato, tab_mensal, tab_sobras_sap = st.tabs([
    "🔎 Evolução Mensal de um Contrato Específico",
    "📅 Evolução Mês a Mês (Estimado vs Liquidado)",
    "🔍 Liquidações no SIAFIC sem Vínculo na Planilha"
])

meses_info = [
    ("Janeiro", "Jan"), ("Fevereiro", "Fev"), ("Março", "Mar"), ("Abril", "Abr"),
    ("Maio", "Mai"), ("Junho", "Jun"), ("Julho", "Jul"), ("Agosto", "Ago"),
    ("Setembro", "Set"), ("Outubro", "Out"), ("Novembro", "Nov"), ("Dezembro", "Dez")
]

# ------------------------------------------------------------------ ABA 1: EVOLUÇÃO POR CONTRATO
with tab_contrato:
    st.subheader("Evolução Mensal de um Contrato Específico")
    st.caption("Auditoria mês a mês de contratos formalizados e contratados, confrontando com os lançamentos oficiais do SIAFIC.")
    
    # Filtra exclusivamente itens que possuem contrato formal e empresa contratada
    df_contratos_insp = df_view[
        df_view["Tem_Contrato_Formal"] & 
        (df_view["Fornecedor"].astype(str).str.strip() != "-") & 
        (df_view["Fornecedor"].astype(str).str.strip() != "")
    ].sort_values(by="Contrato").copy()
    
    lista_contratos = df_contratos_insp["Contrato"].tolist()
    if not lista_contratos:
        st.info("Nenhum contrato formal com fornecedor contratado encontrado para os filtros selecionados.")
    else:
        rotulo_map = {
            r["Contrato"]: f"{r['Contrato']} · {r['Fornecedor'][:55]} ({r['Unidade']})"
            for _, r in df_contratos_insp.iterrows()
        }
        contrato_selecionado = st.selectbox(
            "Selecione um contrato formal:",
            options=lista_contratos,
            format_func=lambda c: rotulo_map.get(c, c),
            key="f_contrato_drilldown"
        )
        
        c_row = df_contratos_insp[df_contratos_insp["Contrato"] == contrato_selecionado].iloc[0]
        
        # Card resumo do contrato
        st.markdown(
            f"""<div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:10px; padding:14px 20px; margin-bottom:1.2rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                    <span style="color:#166534; font-size:1.2rem; font-weight:700;">📄 {c_row['Contrato']}</span>
                    <span style="background:#DCFCE7; color:#15803D; font-weight:600; padding:3px 10px; border-radius:6px; font-size:0.85rem;">
                        Status: {c_row['Status_Execucao']}
                    </span>
                </div>
                <div style="margin-top:8px; font-size:0.92rem; color:#1F2937; line-height:1.5;">
                    <strong>Processo SEI:</strong> {c_row['Processo_SEI']} &nbsp;|&nbsp; 
                    <strong>Unidade:</strong> {c_row['Unidade']} &nbsp;|&nbsp; 
                    <strong>Grupo:</strong> {c_row.get('Grupo_Despesa', '-')} &nbsp;|&nbsp; 
                    <strong>Item(ns):</strong> {c_row.get('Itens', '-')}<br>
                    <strong>Fornecedor:</strong> {c_row['Fornecedor']}<br>
                    <strong>Objeto:</strong> {c_row['Objeto']}
                </div>
            </div>""",
            unsafe_allow_html=True
        )
        
        # Cálculo do % Executado Proporcional DO ANO até o momento (Janeiro até 2 meses anteriores)
        # Devido ao delay operacional para apresentação e liquidação de notas fiscais no SIAFIC
        est_prop_c = sum(safe_float(c_row.get(f"Estimado_{m}", 0.0)) for m in meses_prop_lista)
        liq_prop_c = sum(safe_float(c_row.get(f"Liquidado_{m}", 0.0)) for m in meses_prop_lista)
        pct_prop_c = (liq_prop_c / est_prop_c * 100) if est_prop_c > 0 else (100.0 if liq_prop_c > 0 else 0.0)
        pct_prop = pct_prop_c
        label_card_prop = "% Exec. Proporcional"
        sub_card_prop = f"Jan a {nome_fim_prop[:3]}/26 · {fmt_card_mi(liq_prop_c)} de {fmt_card_mi(est_prop_c)}"

        # KPIs individuais do contrato
        kc1, kc2, kc3, kc4, kc5 = st.columns(5)
        c_est_tot = float(c_row["Estimado_Total_2026"])
        c_liq_tot = float(c_row["Total_Liquidado_SIAFIC"])
        c_saldo = float(c_row["Saldo_A_Liquidar"])
        c_pct = float(c_row["Pct_Executado"])
        
        with kc1:
            st.markdown(
                f'<div class="kpi"><div class="label">Total Estimado 2026</div>'
                f'<div class="value">{fmt_card_mi(c_est_tot)}</div>'
                f'<div class="sub">Total: {fmt_brl(c_est_tot)}</div></div>',
                unsafe_allow_html=True
            )
        with kc2:
            st.markdown(
                f'<div class="kpi"><div class="label">Liquidado SIAFIC 2026</div>'
                f'<div class="value">{fmt_card_mi(c_liq_tot)}</div>'
                f'<div class="sub">Total: {fmt_brl(c_liq_tot)}</div></div>',
                unsafe_allow_html=True
            )
        with kc3:
            st.markdown(
                f'<div class="kpi"><div class="label">Saldo a Liquidar</div>'
                f'<div class="value">{fmt_card_mi(c_saldo)}</div>'
                f'<div class="sub">Diferença restante</div></div>',
                unsafe_allow_html=True
            )
        with kc4:
            st.markdown(
                f'<div class="kpi"><div class="label">% Executado Total</div>'
                f'<div class="value">{c_pct:.1f}%</div>'
                f'<div class="sub">Da estimativa anual realizada</div></div>',
                unsafe_allow_html=True
            )
        with kc5:
            st.markdown(
                f'<div class="kpi"><div class="label">{label_card_prop}</div>'
                f'<div class="value">{pct_prop_c:.1f}%</div>'
                f'<div class="sub">{sub_card_prop}</div></div>',
                unsafe_allow_html=True
            )
            
        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
        
        # Monta dados dos 12 meses para o contrato
        linhas_c_meses = []
        for nome_m, abbr_m in meses_info:
            v_est = float(c_row.get(f"Estimado_{nome_m}", 0.0) or 0.0)
            v_liq = float(c_row.get(f"Liquidado_{nome_m}", 0.0) or 0.0)
            dif = v_est - v_liq
            pct_m = (v_liq / v_est * 100) if v_est > 0 else (100.0 if v_liq > 0 else 0.0)
            linhas_c_meses.append({
                "Mês": nome_m,
                "Abreviacao": abbr_m,
                "Estimado": v_est,
                "Liquidado": v_liq,
                "Saldo do Mês": dif,
                "% Executado": pct_m,
            })
            
        df_c_meses = pd.DataFrame(linhas_c_meses)
        
        col_c_tab, col_c_chart = st.columns([1.1, 1])
        
        with col_c_tab:
            st.markdown("##### 📑 Cronograma Mês a Mês do Contrato")
            df_c_tab_fmt = df_c_meses.copy()
            df_c_tab_fmt["Estimado (R$)"] = df_c_tab_fmt["Estimado"].apply(fmt_brl)
            df_c_tab_fmt["Liquidado SIAFIC (R$)"] = df_c_tab_fmt["Liquidado"].apply(fmt_brl)
            df_c_tab_fmt["Saldo do Mês (R$)"] = df_c_tab_fmt["Saldo do Mês"].apply(fmt_brl)
            df_c_tab_fmt["% Exec."] = df_c_tab_fmt["% Executado"].apply(lambda x: f"{x:.1f}%")
            
            linha_tot = pd.DataFrame([{
                "Mês": "TOTAL ANUAL",
                "Estimado (R$)": fmt_brl(c_est_tot),
                "Liquidado SIAFIC (R$)": fmt_brl(c_liq_tot),
                "Saldo do Mês (R$)": fmt_brl(c_saldo),
                "% Exec.": f"{c_pct:.1f}%",
            }])
            df_c_final = pd.concat([df_c_tab_fmt[["Mês", "Estimado (R$)", "Liquidado SIAFIC (R$)", "Saldo do Mês (R$)", "% Exec."]], linha_tot], ignore_index=True)
            
            st.dataframe(
                df_c_final,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Estimado (R$)": st.column_config.TextColumn(alignment="right"),
                    "Liquidado SIAFIC (R$)": st.column_config.TextColumn(alignment="right"),
                    "Saldo do Mês (R$)": st.column_config.TextColumn(alignment="right"),
                    "% Exec.": st.column_config.TextColumn(alignment="right"),
                }
            )
            
        with col_c_chart:
            st.markdown("##### 📊 Comparativo Mensal (Estimado vs Liquidado)")
            fig_c = go.Figure()
            fig_c.add_trace(go.Bar(
                x=df_c_meses["Abreviacao"],
                y=df_c_meses["Estimado"],
                name="Estimado (Planilha)",
                marker_color="#3B82F6",
                hovertemplate="%{x}: R$ %{y:,.2f}<extra>Estimado</extra>"
            ))
            fig_c.add_trace(go.Bar(
                x=df_c_meses["Abreviacao"],
                y=df_c_meses["Liquidado"],
                name="Liquidado (SIAFIC)",
                marker_color="#10B981",
                hovertemplate="%{x}: R$ %{y:,.2f}<extra>Liquidado</extra>"
            ))
            fig_c.update_layout(
                barmode="group",
                margin=dict(l=10, r=10, t=25, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig_c = style(fig_c, height=360)
            st.plotly_chart(fig_c, use_container_width=True)
            
        # Lançamentos detalhados no SIAFIC (SAP BO) atribuídos a este contrato específico
        lancamentos_c = c_row.get("Lancamentos_SIAFIC")
        if isinstance(lancamentos_c, list) and lancamentos_c:
            df_sap_contrato = pd.DataFrame(lancamentos_c)
        else:
            df_sap_contrato = pd.DataFrame()
        
        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
        st.markdown("##### 🧾 Lançamentos Oficiais de Liquidação no SIAFIC (SAP BO)")
        
        if df_sap_contrato.empty:
            st.info("ℹ️ Não constam lançamentos de liquidação registrados no SIAFIC para este contrato em 2026.")
        else:
            map_meses_abbrev = {
                f"2026{i:02d}": f"{['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'][i-1]}/2026"
                for i in range(1, 13)
            }
            df_sap_disp = df_sap_contrato.copy()
            df_sap_disp["Mês Referência"] = df_sap_disp["Periodo_AnoMes"].map(map_meses_abbrev).fillna(df_sap_disp["Periodo_AnoMes"])
            df_sap_disp["Valor Liquidado (R$)"] = df_sap_disp["Valor_Liquidado_Saldo"].apply(fmt_brl)
            
            cols_sap_show = ["Processo_SEI", "Mês Referência", "Beneficiario_Nome", "Natureza_Despesa_Nome", "Valor Liquidado (R$)"]
            st.dataframe(
                df_sap_disp[cols_sap_show].rename(columns={
                    "Processo_SEI": "Processo SEI",
                    "Beneficiario_Nome": "Beneficiário",
                    "Natureza_Despesa_Nome": "Natureza da Despesa",
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Valor Liquidado (R$)": st.column_config.TextColumn(alignment="right"),
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
    
    # Processos e despesas do SIAFIC que não foram vinculados a contratos da planilha
    meses_sobras = [
        ("Jan", "202601"), ("Fev", "202602"), ("Mar", "202603"), ("Abr", "202604"),
        ("Mai", "202605"), ("Jun", "202606"), ("Jul", "202607"), ("Ago", "202608"),
        ("Set", "202609"), ("Out", "202610"), ("Nov", "202611"), ("Dez", "202612")
    ]
    
    sobras_by_proc: dict[str, dict] = {}
    for r_sob in sobras_sap_rows:
        p_sob = str(r_sob.get("Processo_SEI", "")).strip() or "(Sem Processo SEI)"
        b_sob = str(r_sob.get("Beneficiario_Nome", "")).strip()
        nat_sob = str(r_sob.get("Natureza_Despesa_Nome", "")).strip()
        v_sob = float(r_sob.get("Valor_Liquidado_Saldo", 0) or 0)
        m_sob = str(r_sob.get("Periodo_AnoMes", "")).strip()
        
        if p_sob not in sobras_by_proc:
            sobras_by_proc[p_sob] = {
                "Processo_SEI": p_sob,
                "beneficiarios": set(),
                "naturezas": set(),
                "total_liquidado": 0.0,
                "meses": {cod: 0.0 for _, cod in meses_sobras}
            }
        sobras_by_proc[p_sob]["total_liquidado"] += v_sob
        if b_sob:
            sobras_by_proc[p_sob]["beneficiarios"].add(b_sob)
        if nat_sob:
            sobras_by_proc[p_sob]["naturezas"].add(nat_sob)
        if m_sob in sobras_by_proc[p_sob]["meses"]:
            sobras_by_proc[p_sob]["meses"][m_sob] += v_sob
            
    sobras_sap_list = []
    for p_sap, data_sap in sobras_by_proc.items():
        if data_sap["total_liquidado"] > 0:
            item_sobra = {
                "Processo_SEI": p_sap,
                "Beneficiario": ", ".join(sorted(data_sap["beneficiarios"])) or "-",
                "Natureza_Despesa": "; ".join(sorted(data_sap["naturezas"])) or "-",
                "Total_Liquidado": data_sap["total_liquidado"],
            }
            for sigla, cod in meses_sobras:
                item_sobra[sigla] = data_sap["meses"].get(cod, 0.0)
            sobras_sap_list.append(item_sobra)
            
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
        
        cols_sobras_display = ["Processo_SEI", "Beneficiario", "Natureza_Despesa"]
        col_cfg_sobras = {
            "Total Liquidado (R$)": st.column_config.TextColumn(alignment="right"),
        }
        
        for sigla, _ in meses_sobras:
            col_name = f"{sigla}/26 (R$)"
            df_sobras_fmt[col_name] = df_sobras_fmt[sigla].apply(fmt_brl)
            cols_sobras_display.append(col_name)
            col_cfg_sobras[col_name] = st.column_config.TextColumn(alignment="right")
            
        cols_sobras_display.append("Total Liquidado (R$)")
        
        st.dataframe(
            df_sobras_fmt[cols_sobras_display].rename(columns={
                "Processo_SEI": "Processo SEI",
                "Beneficiario": "Beneficiário",
                "Natureza_Despesa": "Natureza da Despesa"
            }),
            use_container_width=True,
            hide_index=True,
            column_config=col_cfg_sobras
        )
