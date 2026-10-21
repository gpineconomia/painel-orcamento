"""Oráculo — Assistente Inteligente Multi-Base do Painel de Gestão Orçamentária e Contratações (SECON-GO)."""
from __future__ import annotations

from datetime import datetime
import re
import unicodedata
from typing import Any

import pandas as pd
import streamlit as st

import data_source
import liquidado_mensal_data
import pca_data


def fmt_brl(v: float | int | None) -> str:
    """Formata valor monetário no padrão brasileiro ABNT 2 (R$ 1.234,56)."""
    if v is None or pd.isna(v) or v == "":
        return "R$ 0,00"
    try:
        val = float(v)
        sign = "-" if val < 0 else ""
        a = abs(val)
        s = f"{a:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {sign}{s}"
    except Exception:
        return str(v)


def norm_text(s: object) -> str:
    """Normaliza string para busca sem acentos e em minúsculas."""
    if s is None or pd.isna(s):
        return ""
    txt = str(s).replace("_x000D_", " ").replace("\xa0", " ").strip()
    txt = unicodedata.normalize("NFKD", txt).encode("ASCII", "ignore").decode("ASCII").lower()
    return re.sub(r"\s+", " ", txt)


MESES_NOMES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]
MESES_ABREV = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
}


def _clean_budget_df(raw: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Aplica as mesmas regras de limpeza das páginas oficiais de 2026 e 2027."""
    if raw.empty:
        return raw.copy()
    df = raw.copy()
    c_total = f"Estimado Total {ano}"
    if c_total not in df.columns:
        matches = [c for c in df.columns if str(c).startswith("Estimado Total")]
        c_total = matches[0] if matches else df.columns[0]

    c_meses = [c for m in MESES_NOMES for c in df.columns if c == f"Estimado {m}"]
    for c in [c_total, *c_meses]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    if ano == 2026:
        for c in df.columns:
            if "fonte" in str(c).lower():
                df = df[~df[c].astype(str).str.contains("17540111", na=False)]
                break
        seq_cols = [c for c in df.columns if "seq" in str(c).lower()]
        mask_seq54 = pd.Series(False, index=df.index)
        for c in seq_cols:
            val_num = pd.to_numeric(df[c], errors="coerce")
            val_str = df[c].astype(str).str.strip()
            mask_seq54 |= (val_num == 54) | (val_str.isin(["54", "54.0"]))
        for c in df.columns:
            if "ação" in str(c).lower() or "acao" in str(c).lower():
                mask_seq54 |= df[c].astype(str).str.strip().isin(["4145", "4145.0"])
        df = df[~mask_seq54]

    df = df[df[c_total] > 0].copy()

    if ano == 2026:
        df["_val_total"] = df[c_total]
        df["_val_indicado"] = pd.to_numeric(df.get("Valor Indicado", 0.0), errors="coerce").fillna(0.0)
        rest_cols = [c for c in df.columns if str(c).startswith("Valor Estimado - Valor Indicado")]
        if rest_cols:
            df["_val_restante"] = pd.to_numeric(df[rest_cols[0]], errors="coerce").fillna(0.0)
        else:
            df["_val_restante"] = df["_val_total"] - df["_val_indicado"]
    else:
        df["_val_inicial"] = df[c_meses].sum(axis=1) if c_meses else df[c_total]
        def_cols = [c for c in df.columns if "deficit" in norm_text(c)]
        df["_val_deficit"] = pd.to_numeric(df[def_cols[0]], errors="coerce").fillna(0.0) if def_cols else 0.0
        df["_val_total"] = df["_val_inicial"] + df["_val_deficit"]

    # Campo unificado de busca textual
    search_cols = [
        c for c in ["Item", "Objeto", "Resumo", "Classificação do Objeto", "Nº do Contrato (se houver)",
                    "Nº Processo (se houver)", "Nº IPOF (se houver)", "Empresa Contratada", "Unidade",
                    "Departamento", "Grupo de Despesa", "Situação", "Situação IPOF"]
        if c in df.columns
    ]
    df["_search_blob"] = df[search_cols].fillna("").astype(str).agg(" | ".join, axis=1).apply(norm_text)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_oraculo_kb() -> dict[str, Any]:
    """Carrega e indexa todas as 5 bases de dados do painel para consulta instantânea."""
    raw26, u26, _ = data_source.load_data(2026)
    raw27, u27, _ = data_source.load_data(2027)
    df_sup, u_sup, _ = data_source.load_supressoes_2027()
    df_pca, u_pca = pca_data.load_pca_data()
    df_liq, u_liq = liquidado_mensal_data.load_liquidado_mensal_data()

    df26 = _clean_budget_df(raw26, 2026)
    df27 = _clean_budget_df(raw27, 2027)

    if not df_sup.empty:
        df_sup = df_sup.copy()
        df_sup["_search_blob"] = (
            df_sup[["Unidade", "Item de Despesa", "Ação Sugerida"]]
            .fillna("").astype(str).agg(" | ".join, axis=1).apply(norm_text)
        )

    if not df_pca.empty:
        df_pca = df_pca.copy()
        pca_cols = [
            "Item", "Processo_SEI", "Objeto_Resumido", "Detalhamento_Objeto",
            "Unidade_Superior", "Unidade_Demandante", "Contrato_Vigente",
            "Modalidade", "Providencia_2027", "Status_Contratacao", "Unidade_Orcamentaria"
        ]
        df_pca["_search_blob"] = (
            df_pca[[c for c in pca_cols if c in df_pca.columns]]
            .fillna("").astype(str).agg(" | ".join, axis=1).apply(norm_text)
        )

    if not df_liq.empty:
        df_liq = df_liq.copy()
        # Filtra exercício de 2026 como padrão de análise de execução atual
        df_liq_2026 = df_liq[df_liq["Ano_Referencia"] == 2026].copy() if "Ano_Referencia" in df_liq.columns else df_liq.copy()
        df_liq_2026["_search_blob"] = (
            df_liq_2026[["Processo_SEI", "Beneficiario_Nome", "Natureza_Despesa_Nome", "Natureza_Despesa_Codigo"]]
            .fillna("").astype(str).agg(" | ".join, axis=1).apply(norm_text)
        )
    else:
        df_liq_2026 = pd.DataFrame()

    return {
        "df26": df26,
        "u26": u26,
        "df27": df27,
        "u27": u27,
        "df_sup": df_sup,
        "u_sup": u_sup,
        "df_pca": df_pca,
        "u_pca": u_pca,
        "df_liq": df_liq_2026,
        "u_liq": u_liq,
        "cota_2026": 207478837.10,
        "cota_2027": 144089232.46,
    }


# Mapeamento inteligente de siglas e unidades entre todas as planilhas
UNIT_ALIASES = {
    "sti": {
        "nome": "Superintendência de Tecnologia da Informação (STI)",
        "orc": ["Tecnologia da Informação"],
        "sup": ["STI"],
        "pca": ["Superintendência de Tecnologia da Informação"],
        "terms": ["sti", "tecnologia da informacao", "suporte tecnico", "sistemas", "infraestrutura", "dados e inteligencia", "cibernetica"],
    },
    "sgi": {
        "nome": "Superintendência de Gestão Integrada (SGI)",
        "orc": ["Gestão Integrada", "Receita/Gestão Integrada"],
        "sup": ["SGI"],
        "pca": ["Superintendência de Gestão Integrada"],
        "terms": ["sgi", "gestao integrada", "engenharia", "arquitetura", "apoio administrativo", "logistica", "gestao e desenvolvimento de pessoas", "secretaria geral", "licitacoes", "gelc", "setrac"],
    },
    "receita": {
        "nome": "Subsecretaria da Receita Estadual (SRE / Fiscalização / Informações / Créditos)",
        "orc": ["Receita", "Receita/Gestão Integrada"],
        "sup": ["RECEITA"],
        "pca": [
            "Subsecretaria da Receita Estadual",
            "Superintendência de Fiscalização Regionalizada",
            "Superintendência de Informações Fiscais",
            "Superintendência de Recuperação de Créditos",
        ],
        "terms": ["sre", "receita estadual", "subsecretaria da receita", "fiscalizacao regionalizada", "sfr", "informacoes fiscais", "sif", "recuperacao de creditos", "src", "arrecadacao"],
    },
    "tesouro": {
        "nome": "Superintendência Financeira e Contabilidade (Tesouro / SUFIN / SCC)",
        "orc": ["Tesouro"],
        "sup": [],
        "pca": ["Superintendência Financeira", "Superintendência Central de Contabilidade"],
        "terms": ["sufin", "superintendencia financeira", "contabilidade", "divida publica", "tesouro estadual"],
    },
    "gabinete": {
        "nome": "Gabinete, Controle/Auditoria, Corregedoria e Planejamento",
        "orc": ["Gabinete", "Corregedoria Fiscal", "Planejamento", "Orçamento", "Outros"],
        "sup": [],
        "pca": ["Gabinete", "Superintendência de Controle e Auditoria"],
        "terms": ["gabinete", "corregedoria", "controle e auditoria", "comunicacao setorial", "gpin"],
    },
}


STOPWORDS_PT = {
    "o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das", "em", "no", "na",
    "nos", "nas", "por", "para", "com", "sem", "qual", "quais", "quanto", "quantos", "quantas",
    "como", "onde", "quem", "que", "se", "me", "fale", "mostre", "liste", "listar", "diga",
    "sobre", "tem", "temos", "ha", "existe", "existem", "esta", "estao", "sao", "foi", "foram",
    "valor", "valores", "total", "totais", "resumo", "dados", "informacao", "informacoes",
    "planilha", "planilhas", "dashboard", "painel", "pagina", "tabela", "ano", "anos", "item",
    "itens", "processo", "processos", "contrato", "contratos", "orcamento", "despesa", "despesas",
    "contratacao", "contratacoes", "entre", "todos", "todas", "tudo", "mais", "menos", "maior",
    "maiores", "menor", "menores", "top", "ranking", "comparar", "comparativo", "compare",
    "2026", "2027", "ploa", "execucao", "planejamento", "unidade", "unidades", "superintendencia",
    "superintendencias", "base", "bases", "cota", "deficit", "estimado", "indicado", "liquidado",
    "saldo", "restante", "geral", "consolidado", "situacao",
}


def _build_panorama_geral(kb: dict[str, Any]) -> str:
    """Gera um panorama executivo completo consolidando todas as 5 bases de dados."""
    df26 = kb["df26"]
    df27 = kb["df27"]
    df_sup = kb["df_sup"]
    df_pca = kb["df_pca"]
    df_liq = kb["df_liq"]

    # 2026
    tot26 = float(df26["_val_total"].sum()) if not df26.empty else 0.0
    ind26 = float(df26["_val_indicado"].sum()) if not df26.empty else 0.0
    rest26 = float(df26["_val_restante"].sum()) if not df26.empty else 0.0
    pct26 = (ind26 / tot26 * 100) if tot26 > 0 else 0.0

    # SIAFIC 2026
    liq26 = float(df_liq["Valor_Liquidado_Saldo"].sum()) if not df_liq.empty else 0.0

    # 2027
    ini27 = float(df27["_val_inicial"].sum()) if not df27.empty else 0.0
    def27 = float(df27["_val_deficit"].sum()) if not df27.empty else 0.0
    tot27 = float(df27["_val_total"].sum()) if not df27.empty else 0.0
    cota27 = kb["cota_2027"]

    # Supressões
    sup_econ = float(df_sup["Economia Gerada"].sum()) if not df_sup.empty else 0.0
    sup_teto = float(df_sup["Teto Ajustado 2027"].sum()) if not df_sup.empty else 0.0

    # PCA 2027
    pca_geof = df_pca[df_pca["Unidade_Orcamentaria"] == "GEOF"] if not df_pca.empty else pd.DataFrame()
    pca_tes = df_pca[df_pca["Unidade_Orcamentaria"] == "Tesouro"] if not df_pca.empty else pd.DataFrame()
    tot_pca_geof = float(pca_geof["Valor_Estimado_2027"].sum()) if not pca_geof.empty else 0.0
    tot_pca_tes = float(pca_tes["Valor_Estimado_2027"].sum()) if not pca_tes.empty else 0.0
    tot_pca_all = float(df_pca["Valor_Estimado_2027"].sum()) if not df_pca.empty else 0.0

    return f"""### 🔮 Panorama Executivo Consolidado (Todas as Bases)

#### 1️⃣ Execução Orçamentária 2026 & SIAFIC
* **Estimado Total 2026:** `{fmt_brl(tot26)}` ({len(df26)} itens ativos)
* **Valor Indicado (Empenhado/Indicado):** `{fmt_brl(ind26)}` (`{pct26:.1f}%` do estimado)
* **Saldo Restante a Indicar:** `{fmt_brl(rest26)}`
* **Total Liquidado no SIAFIC (SAP BO 2026):** `{fmt_brl(liq26)}`

#### 2️⃣ Planejamento Orçamentário 2027 (PLOA)
* **Estimado Inicial 2027:** `{fmt_brl(ini27)}`
* **Estimado Déficit 2027:** `{fmt_brl(def27)}`
* **Estimado Total 2027 (Inicial + Déficit):** `{fmt_brl(tot27)}` ({len(df27)} itens)
* **Cota LOA/Tesouro 2027:** `{fmt_brl(cota27)}` (Diferença: `{fmt_brl(tot27 - cota27)}`)

#### 3️⃣ Supressões PLOA 2027
* **Itens Mapeados para Adequação/Corte:** `{len(df_sup)}` itens (STI, SGI e RECEITA)
* **Economia Total Gerada (Cortes):** `{fmt_brl(sup_econ)}`
* **Teto Ajustado Pós-Supressão:** `{fmt_brl(sup_teto)}`

#### 4️⃣ Plano de Contratações Anual — PCA 2027 (GELC)
* **Total Geral PCA 2027:** `{fmt_brl(tot_pca_all)}` ({len(df_pca)} demandas)
* **Unidade Orçamentária GEOF (Padrão):** `{fmt_brl(tot_pca_geof)}` ({len(pca_geof)} demandas)
* **Unidade Orçamentária Tesouro:** `{fmt_brl(tot_pca_tes)}` ({len(pca_tes)} demandas)"""


def _search_by_identifier(q_raw: str, kb: dict[str, Any]) -> str | None:
    """Busca exata por número de Processo SEI, número de Contrato (XX/AAAA) ou IPOF."""
    sei_matches = re.findall(r"\b\d{10,16}\b", q_raw)
    contract_matches = re.findall(r"\b\d{1,4}/20\d{2}\b", q_raw)

    if not sei_matches and not contract_matches:
        return None

    termo = sei_matches[0] if sei_matches else contract_matches[0]
    tipo_id = "Processo SEI" if sei_matches else "Contrato"

    partes = [f"### 🔎 Dossiê 360° — {tipo_id} `{termo}`\n"]
    encontrou = False

    # 1. Orçamento 2026
    df26 = kb["df26"]
    m26 = df26["_search_blob"].str.contains(re.escape(termo.lower()), na=False)
    if m26.any():
        encontrou = True
        sub = df26[m26]
        partes.append(f"#### 📌 Orçamento 2026 (Execução) — {len(sub)} registro(s) | Total: `{fmt_brl(sub['_val_total'].sum())}`")
        for _, r in sub.head(8).iterrows():
            partes.append(
                f"* **Item {r.get('Item', '-')} — {r.get('Resumo', r.get('Objeto', '-'))}** ({r.get('Unidade', '-')})\n"
                f"  * Estimado 2026: `{fmt_brl(r['_val_total'])}` | Indicado: `{fmt_brl(r['_val_indicado'])}` | "
                f"Contrato: `{r.get('Nº do Contrato (se houver)', '-')}` | Empresa: `{r.get('Empresa Contratada', '-')}`"
            )

    # 2. Liquidação SIAFIC 2026
    df_liq = kb["df_liq"]
    if not df_liq.empty:
        mliq = df_liq["_search_blob"].str.contains(re.escape(termo.lower()), na=False)
        if mliq.any():
            encontrou = True
            sub_l = df_liq[mliq]
            tot_l = float(sub_l["Valor_Liquidado_Saldo"].sum())
            benefs = ", ".join(sub_l["Beneficiario_Nome"].dropna().unique()[:3])
            partes.append(
                f"#### 💳 Liquidação SIAFIC 2026 (SAP BO)\n"
                f"* **Total Liquidado em 2026:** `{fmt_brl(tot_l)}` ({len(sub_l)} lançamentos mensais)\n"
                f"* **Beneficiário(s):** {benefs}"
            )

    # 3. Planejamento 2027
    df27 = kb["df27"]
    m27 = df27["_search_blob"].str.contains(re.escape(termo.lower()), na=False)
    if m27.any():
        encontrou = True
        sub = df27[m27]
        partes.append(f"#### 📅 Planejamento PLOA 2027 — {len(sub)} registro(s) | Total: `{fmt_brl(sub['_val_total'].sum())}`")
        for _, r in sub.head(8).iterrows():
            partes.append(
                f"* **Item {r.get('Item', '-')} — {r.get('Resumo', r.get('Objeto', '-'))}** ({r.get('Unidade', '-')})\n"
                f"  * Inicial: `{fmt_brl(r['_val_inicial'])}` | Déficit: `{fmt_brl(r['_val_deficit'])}` | Total 2027: `{fmt_brl(r['_val_total'])}`"
            )

    # 4. PCA 2027
    df_pca = kb["df_pca"]
    if not df_pca.empty:
        mpca = df_pca["_search_blob"].str.contains(re.escape(termo.lower()), na=False)
        if mpca.any():
            encontrou = True
            sub = df_pca[mpca]
            partes.append(f"#### 📑 PCA 2027 (GELC) — {len(sub)} demanda(s)")
            for _, r in sub.head(8).iterrows():
                dt_dead = r["Deadline_Contratacao"].strftime("%d/%m/%Y") if pd.notna(r["Deadline_Contratacao"]) else "N/D"
                partes.append(
                    f"* **Item {r.get('Item', '-')} — {r.get('Objeto_Resumido', '-')}** ({r.get('Unidade_Superior', '-')} · {r.get('Unidade_Demandante', '-')})\n"
                    f"  * Estimado 2027: `{fmt_brl(r['Valor_Estimado_2027'])}` | Valor Total: `{fmt_brl(r['Valor_Total_Estimado'])}` | "
                    f"Providência: `{r.get('Providencia_2027', '-')}` | Deadline: `{dt_dead}` | UO: `{r.get('Unidade_Orcamentaria', '-')}`"
                )

    if not encontrou:
        return f"Não encontrei nenhum registro com o {tipo_id} **`{termo}`** nas bases de 2026, SIAFIC, PLOA 2027, Supressões ou PCA 2027."

    return "\n\n".join(partes)


def _answer_pca_specific(q_norm: str, kb: dict[str, Any]) -> str:
    """Responde perguntas focadas no PCA 2027, cronograma, prazos, riscos, GEOF/Tesouro."""
    df_pca = kb["df_pca"].copy()
    if df_pca.empty:
        return "A base do PCA 2027 está vazia no momento."

    # Verifica se o usuário pediu especificamente Tesouro ou Todos, caso contrário destaca ambos e GEOF
    hoje = datetime.now()
    ano_at, mes_at = hoje.year, hoje.month
    ano_px, mes_px = (ano_at + 1, 1) if mes_at == 12 else (ano_at, mes_at + 1)

    s_set = pd.to_datetime(df_pca["Data_Inicio_SETRAC"], errors="coerce")
    s_con = pd.to_datetime(df_pca["Data_Encaminhamento_Contratos"], errors="coerce")
    s_dea = pd.to_datetime(df_pca["Deadline_Contratacao"], errors="coerce")

    # Se perguntou sobre riscos, atrasos, vencidos ou mês corrente
    if any(k in q_norm for k in ["risco", "atrasad", "vencid", "mes corrente", "mes atual", "este mes", "prazo", "setrac", "encaminhamento", "deadline", "alerta", "proximo mes"]):
        df_geof = df_pca[df_pca["Unidade_Orcamentaria"] == "GEOF"].copy() if "tesouro" not in q_norm else df_pca.copy()
        escopo_lbl = "Todas as UOs (GEOF + Tesouro)" if "tesouro" in q_norm or "tod" in q_norm else "UO Padrão: GEOF"
        if "tesouro" in q_norm and "geof" not in q_norm:
            df_geof = df_pca[df_pca["Unidade_Orcamentaria"] == "Tesouro"].copy()
            escopo_lbl = "UO: Tesouro"

        ss = pd.to_datetime(df_geof["Data_Inicio_SETRAC"], errors="coerce")
        sc = pd.to_datetime(df_geof["Data_Encaminhamento_Contratos"], errors="coerce")
        sd = pd.to_datetime(df_geof["Deadline_Contratacao"], errors="coerce")

        m_atual = (
            ((ss.dt.year == ano_at) & (ss.dt.month == mes_at))
            | ((sc.dt.year == ano_at) & (sc.dt.month == mes_at))
            | ((sd.dt.year == ano_at) & (sd.dt.month == mes_at))
        )
        m_venc = (ss < hoje) | (sc < hoje) | (sd < hoje)
        m_prox = (
            ((ss.dt.year == ano_px) & (ss.dt.month == mes_px))
            | ((sc.dt.year == ano_px) & (sc.dt.month == mes_px))
            | ((sd.dt.year == ano_px) & (sd.dt.month == mes_px))
        )

        sub_alerta = df_geof[m_venc | m_atual].copy()
        linhas = [
            f"### 🚨 Análise de Cronograma & Riscos — PCA 2027 ({escopo_lbl})",
            f"* **Processos com Marco no Mês Corrente ({MESES_ABREV[mes_at]}/{ano_at}):** `{int(m_atual.sum())}` demandas (`{fmt_brl(df_geof[m_atual]['Valor_Estimado_2027'].sum())}`)",
            f"* **Processos com Prazos Já Vencidos (< {hoje:%d/%m/%Y}):** `{int(m_venc.sum())}` demandas (`{fmt_brl(df_geof[m_venc]['Valor_Estimado_2027'].sum())}`)",
            f"* **Processos para o Próximo Mês ({MESES_ABREV[mes_px]}/{ano_px}):** `{int(m_prox.sum())}` demandas (`{fmt_brl(df_geof[m_prox]['Valor_Estimado_2027'].sum())}`)\n",
        ]

        if not sub_alerta.empty:
            linhas.append("#### ⚡ Relação de Processos em Atenção Imediata (Vencidos + Mês Corrente):")
            linhas.append("| Item | Objeto Resumido | Superintendência | Início SETRAC | Encam. Contratos | Deadline | Estimado 2027 |")
            linhas.append("|---|---|---|---|---|---|---|")
            for _, r in sub_alerta.sort_values("Valor_Estimado_2027", ascending=False).iterrows():
                d1 = r["Data_Inicio_SETRAC"].strftime("%d/%m/%Y") if pd.notna(r["Data_Inicio_SETRAC"]) else "-"
                d2 = r["Data_Encaminhamento_Contratos"].strftime("%d/%m/%Y") if pd.notna(r["Data_Encaminhamento_Contratos"]) else "-"
                d3 = r["Deadline_Contratacao"].strftime("%d/%m/%Y") if pd.notna(r["Deadline_Contratacao"]) else "-"
                it_n = int(r["Item"]) if pd.notna(r["Item"]) else "-"
                linhas.append(
                    f"| {it_n} | **{r['Objeto_Resumido']}** | {r['Unidade_Superior']} | `{d1}` | `{d2}` | `{d3}` | `{fmt_brl(r['Valor_Estimado_2027'])}` |"
                )
        return "\n".join(linhas)

    # Visão consolidada do PCA 2027 por Superintendência e Providência
    df_geof = df_pca[df_pca["Unidade_Orcamentaria"] == "GEOF"]
    df_tes = df_pca[df_pca["Unidade_Orcamentaria"] == "Tesouro"]

    alvo = df_pca if ("tod" in q_norm or "tesouro" in q_norm) else df_geof
    lbl_alvo = "Consolidado Geral (GEOF + Tesouro)" if len(alvo) == len(df_pca) else "Padrão GEOF (128 demandas)"

    tot_2027 = float(alvo["Valor_Estimado_2027"].sum())
    tot_glob = float(alvo["Valor_Total_Estimado"].sum())

    m_novas = alvo["Providencia_2027"].astype(str).str.upper().str.contains("NOVA", na=False)
    m_prorr = alvo["Providencia_2027"].astype(str).str.upper().str.contains("PRORROG", na=False)
    m_sem = alvo["Providencia_2027"].astype(str).str.upper().str.contains("SEM PROVID", na=False)

    por_sup = (
        alvo.groupby("Unidade_Superior", as_index=False)
        .agg(Qtd=("Objeto_Resumido", "count"), Est2027=("Valor_Estimado_2027", "sum"), Total=("Valor_Total_Estimado", "sum"))
        .sort_values("Est2027", ascending=False)
    )

    linhas = [
        f"### 📑 Resumo Analítico — PCA 2027 ({lbl_alvo})",
        f"* **Estimado PCA para 2027:** `{fmt_brl(tot_2027)}` ({len(alvo)} demandas)",
        f"* **Valor Total das Contratações:** `{fmt_brl(tot_glob)}`",
        f"* **Novas Contratações:** `{int(m_novas.sum())}` processos (`{fmt_brl(alvo[m_novas]['Valor_Estimado_2027'].sum())}`)",
        f"* **Prorrogações:** `{int(m_prorr.sum())}` aditivos (`{fmt_brl(alvo[m_prorr]['Valor_Estimado_2027'].sum())}`)",
        f"* **Sem Providências (Vigência Normal):** `{int(m_sem.sum())}` contratos (`{fmt_brl(alvo[m_sem]['Valor_Estimado_2027'].sum())}`)",
        f"* *(Comparativo de UOs: **GEOF** = `{fmt_brl(df_geof['Valor_Estimado_2027'].sum())}` [{len(df_geof)} itens] | **Tesouro** = `{fmt_brl(df_tes['Valor_Estimado_2027'].sum())}` [{len(df_tes)} itens])*\n",
        "#### 🏢 Distribuição por Superintendência / Unidade Superior:",
        "| Superintendência / Unidade Superior | Demandas | Estimado 2027 | Valor Total Contratação |",
        "|---|---|---|---|",
    ]
    for _, r in por_sup.iterrows():
        linhas.append(f"| **{r['Unidade_Superior']}** | {int(r['Qtd'])} | `{fmt_brl(r['Est2027'])}` | `{fmt_brl(r['Total'])}` |")

    return "\n".join(linhas)


def _answer_supressoes(q_norm: str, kb: dict[str, Any]) -> str:
    """Responde perguntas sobre Supressões PLOA 2027."""
    df_sup = kb["df_sup"]
    if df_sup.empty:
        return "Nenhum dado de Supressões PLOA 2027 encontrado."

    tot_orc = float(df_sup["Orçamento 2027"].sum())
    tot_teto = float(df_sup["Teto Ajustado 2027"].sum())
    tot_econ = float(df_sup["Economia Gerada"].sum())
    pct_geral = (tot_econ / tot_orc * 100) if tot_orc > 0 else 0.0

    por_u = (
        df_sup.groupby("Unidade", as_index=False)
        .agg(Itens=("Item de Despesa", "count"), Orc=("Orçamento 2027", "sum"), Teto=("Teto Ajustado 2027", "sum"), Econ=("Economia Gerada", "sum"))
        .sort_values("Econ", ascending=False)
    )

    linhas = [
        "### ✂️ Supressões PLOA · Planejamento 2027",
        f"* **Orçamento Original dos Itens Analisados:** `{fmt_brl(tot_orc)}` ({len(df_sup)} itens)",
        f"* **Economia Gerada (Total Suprimido):** `{fmt_brl(tot_econ)}` (`-{pct_geral:.1f}%`)",
        f"* **Novo Teto Ajustado 2027:** `{fmt_brl(tot_teto)}`\n",
        "#### 📊 Resumo por Unidade:",
        "| Unidade | Qtd Itens | Orçamento 2027 | Economia Gerada (Corte) | Teto Ajustado 2027 |",
        "|---|---|---|---|---|",
    ]
    for _, r in por_u.iterrows():
        linhas.append(f"| **{r['Unidade']}** | {int(r['Itens'])} | `{fmt_brl(r['Orc'])}` | `{fmt_brl(r['Econ'])}` | `{fmt_brl(r['Teto'])}` |")

    top_sup = df_sup.sort_values("Economia Gerada", ascending=False).head(10)
    linhas.append("\n#### 🔝 Top 10 Maiores Supressões (Economia Gerada):")
    linhas.append("| Unidade | Item de Despesa | Economia Gerada | Teto Ajustado | Ação Sugerida |")
    linhas.append("|---|---|---|---|---|")
    for _, r in top_sup.iterrows():
        linhas.append(
            f"| {r['Unidade']} | **{r['Item de Despesa']}** | `{fmt_brl(r['Economia Gerada'])}` | `{fmt_brl(r['Teto Ajustado 2027'])}` | {r['Ação Sugerida']} |"
        )
    return "\n".join(linhas)


def _answer_liquidacao(q_norm: str, kb: dict[str, Any]) -> str:
    """Responde perguntas sobre Liquidação Mensal no SIAFIC (SAP BO)."""
    df_liq = kb["df_liq"]
    if df_liq.empty:
        return "Os dados de Liquidação Mensal do SIAFIC não estão disponíveis no momento."

    tot_liq = float(df_liq["Valor_Liquidado_Saldo"].sum())
    qtd_procs = df_liq["Processo_SEI"].nunique()
    qtd_benef = df_liq["Beneficiario_Nome"].nunique()

    por_mes = (
        df_liq.groupby("Mes_Referencia", as_index=False)["Valor_Liquidado_Saldo"]
        .sum()
        .sort_values("Mes_Referencia")
    )
    top_benef = (
        df_liq.groupby("Beneficiario_Nome", as_index=False)["Valor_Liquidado_Saldo"]
        .sum()
        .sort_values("Valor_Liquidado_Saldo", ascending=False)
        .head(10)
    )

    linhas = [
        "### 📜 Liquidação Mensal no SIAFIC — Exercício 2026 (SAP BO)",
        f"* **Total Acumulado Liquidado em 2026:** `{fmt_brl(tot_liq)}`",
        f"* **Processos SEI com Liquidação:** `{qtd_procs}` processos",
        f"* **Fornecedores / Beneficiários Distintos:** `{qtd_benef}` credores\n",
        "#### 📅 Evolução Mensal da Liquidação (2026):",
        "| Mês | Valor Liquidado |",
        "|---|---|",
    ]
    for _, r in por_mes.iterrows():
        m_num = int(r["Mes_Referencia"])
        m_lbl = MESES_NOMES[m_num - 1] if 1 <= m_num <= 12 else f"Mês {m_num}"
        linhas.append(f"| **{m_lbl}/2026** | `{fmt_brl(r['Valor_Liquidado_Saldo'])}` |")

    linhas.append("\n#### 🏆 Top 10 Beneficiários / Fornecedores por Valor Liquidado em 2026:")
    linhas.append("| Beneficiário (Credor) | Total Liquidado 2026 |")
    linhas.append("|---|---|")
    for _, r in top_benef.iterrows():
        linhas.append(f"| **{r['Beneficiario_Nome']}** | `{fmt_brl(r['Valor_Liquidado_Saldo'])}` |")

    return "\n".join(linhas)


def _answer_unit_360(unit_key: str, kb: dict[str, Any]) -> str:
    """Gera visão 360º de uma Unidade/Superintendência cruzando 2026, 2027, Supressões e PCA 2027."""
    u_info = UNIT_ALIASES[unit_key]
    df26 = kb["df26"]
    df27 = kb["df27"]
    df_sup = kb["df_sup"]
    df_pca = kb["df_pca"]

    sub26 = df26[df26["Unidade"].isin(u_info["orc"])] if not df26.empty else pd.DataFrame()
    sub27 = df27[df27["Unidade"].isin(u_info["orc"])] if not df27.empty else pd.DataFrame()
    sub_sup = df_sup[df_sup["Unidade"].isin(u_info["sup"])] if not df_sup.empty and u_info["sup"] else pd.DataFrame()
    sub_pca = df_pca[df_pca["Unidade_Superior"].isin(u_info["pca"])] if not df_pca.empty and u_info["pca"] else pd.DataFrame()

    tot26 = float(sub26["_val_total"].sum()) if not sub26.empty else 0.0
    ind26 = float(sub26["_val_indicado"].sum()) if not sub26.empty else 0.0

    ini27 = float(sub27["_val_inicial"].sum()) if not sub27.empty else 0.0
    def27 = float(sub27["_val_deficit"].sum()) if not sub27.empty else 0.0
    tot27 = float(sub27["_val_total"].sum()) if not sub27.empty else 0.0

    linhas = [
        f"### 🏢 Raio-X 360° — {u_info['nome']}",
        "Cruzamento integrado de todas as planilhas para esta área:\n",
        f"#### 1️⃣ Execução 2026 (`{', '.join(u_info['orc'])}`)",
        f"* **Estimado Total 2026:** `{fmt_brl(tot26)}` ({len(sub26)} despesas)",
        f"* **Valor Indicado:** `{fmt_brl(ind26)}` | **Restante:** `{fmt_brl(tot26 - ind26)}`\n",
        f"#### 2️⃣ Planejamento PLOA 2027 (`{', '.join(u_info['orc'])}`)",
        f"* **Estimado Inicial 2027:** `{fmt_brl(ini27)}`",
        f"* **Estimado Déficit 2027:** `{fmt_brl(def27)}`",
        f"* **Estimado Total 2027:** `{fmt_brl(tot27)}` ({len(sub27)} despesas)\n",
    ]

    if not sub_sup.empty:
        linhas.append(f"#### 3️⃣ Supressões PLOA 2027 (`{', '.join(u_info['sup'])}`)")
        linhas.append(
            f"* **Itens afetados:** `{len(sub_sup)}` | **Orçamento Inicial:** `{fmt_brl(sub_sup['Orçamento 2027'].sum())}` | "
            f"**Economia Gerada:** `{fmt_brl(sub_sup['Economia Gerada'].sum())}` | **Teto Ajustado:** `{fmt_brl(sub_sup['Teto Ajustado 2027'].sum())}`\n"
        )

    if not sub_pca.empty:
        linhas.append("#### 4️⃣ PCA 2027 — Contratações GELC")
        linhas.append(
            f"* **Total de Demandas no PCA 2027:** `{len(sub_pca)}` itens | **Estimado 2027:** `{fmt_brl(sub_pca['Valor_Estimado_2027'].sum())}` | "
            f"**Valor Global Contratações:** `{fmt_brl(sub_pca['Valor_Total_Estimado'].sum())}`"
        )
        top_pca = sub_pca.sort_values("Valor_Estimado_2027", ascending=False).head(6)
        linhas.append("| Item | Objeto Resumido | Gerência Demandante | Providência 2027 | Estimado 2027 |")
        linhas.append("|---|---|---|---|---|")
        for _, r in top_pca.iterrows():
            it_n = int(r["Item"]) if pd.notna(r["Item"]) else "-"
            linhas.append(
                f"| {it_n} | **{r['Objeto_Resumido']}** | {r['Unidade_Demandante']} | {r['Providencia_2027']} | `{fmt_brl(r['Valor_Estimado_2027'])}` |"
            )

    if not sub27.empty:
        top27 = sub27.sort_values("_val_total", ascending=False).head(5)
        linhas.append("\n#### 🔝 Top 5 Maiores Despesas Planejadas para 2027 nesta Unidade:")
        for _, r in top27.iterrows():
            linhas.append(
                f"* **{r.get('Resumo', r.get('Objeto', '-'))}** — Total 2027: `{fmt_brl(r['_val_total'])}` (Inicial: `{fmt_brl(r['_val_inicial'])}` | Déficit: `{fmt_brl(r['_val_deficit'])}`)"
            )

    return "\n".join(linhas)


def _answer_orcamento_2026_2027(q_norm: str, kb: dict[str, Any]) -> str:
    """Responde perguntas sobre comparativo 2026 vs 2027, déficit 2027, cota ou ranking de despesas."""
    df26 = kb["df26"]
    df27 = kb["df27"]

    so_2026 = "2026" in q_norm and "2027" not in q_norm
    so_2027 = ("2027" in q_norm or "ploa" in q_norm or "deficit" in q_norm) and "2026" not in q_norm

    if so_2026:
        tot26 = float(df26["_val_total"].sum())
        ind26 = float(df26["_val_indicado"].sum())
        rest26 = float(df26["_val_restante"].sum())
        por_u = (
            df26.groupby("Unidade", as_index=False)
            .agg(Itens=("Objeto", "count"), Est=("_val_total", "sum"), Ind=("_val_indicado", "sum"), Rest=("_val_restante", "sum"))
            .sort_values("Est", ascending=False)
        )
        linhas = [
            "### 🏢 Execução Orçamentária 2026 por Unidade",
            f"* **Estimado Total 2026:** `{fmt_brl(tot26)}` | **Indicado:** `{fmt_brl(ind26)}` | **Restante:** `{fmt_brl(rest26)}`",
            f"* **Cota Tesouro 2026:** `{fmt_brl(kb['cota_2026'])}`\n",
            "| Unidade | Qtd | Estimado Total 2026 | Valor Indicado | Saldo Restante |",
            "|---|---|---|---|---|",
        ]
        for _, r in por_u.iterrows():
            linhas.append(f"| **{r['Unidade']}** | {int(r['Itens'])} | `{fmt_brl(r['Est'])}` | `{fmt_brl(r['Ind'])}` | `{fmt_brl(r['Rest'])}` |")

        top = df26.sort_values("_val_total", ascending=False).head(8)
        linhas.append("\n#### 🔝 Top 8 Maiores Despesas de 2026:")
        for _, r in top.iterrows():
            linhas.append(f"* **{r.get('Resumo', r.get('Objeto', '-'))}** ({r['Unidade']}): `{fmt_brl(r['_val_total'])}` (Indicado: `{fmt_brl(r['_val_indicado'])}`)")
        return "\n".join(linhas)

    if so_2027:
        ini27 = float(df27["_val_inicial"].sum())
        def27 = float(df27["_val_deficit"].sum())
        tot27 = float(df27["_val_total"].sum())
        cota27 = kb["cota_2027"]
        por_u = (
            df27.groupby("Unidade", as_index=False)
            .agg(Itens=("Objeto", "count"), Ini=("_val_inicial", "sum"), Def=("_val_deficit", "sum"), Tot=("_val_total", "sum"))
            .sort_values("Tot", ascending=False)
        )
        linhas = [
            "### 📊 Planejamento Orçamentário 2027 (PLOA) por Unidade",
            f"* **Estimado Inicial 2027:** `{fmt_brl(ini27)}`",
            f"* **Estimado Déficit 2027:** `{fmt_brl(def27)}`",
            f"* **Estimado Total 2027:** `{fmt_brl(tot27)}`",
            f"* **Cota LOA 2027:** `{fmt_brl(cota27)}` | **Diferença (Total - Cota):** `{fmt_brl(tot27 - cota27)}`\n",
            "| Unidade | Qtd | Estimado Inicial | Estimado Déficit | Estimado Total 2027 |",
            "|---|---|---|---|---|",
        ]
        for _, r in por_u.iterrows():
            linhas.append(
                f"| **{r['Unidade']}** | {int(r['Itens'])} | `{fmt_brl(r['Ini'])}` | `{fmt_brl(r['Def'])}` | `{fmt_brl(r['Tot'])}` |"
            )

        top = df27.sort_values("_val_total", ascending=False).head(8)
        linhas.append("\n#### 🔝 Top 8 Maiores Despesas Planejadas para 2027:")
        for _, r in top.iterrows():
            linhas.append(
                f"* **{r.get('Resumo', r.get('Objeto', '-'))}** ({r['Unidade']}): `{fmt_brl(r['_val_total'])}` (Inicial: `{fmt_brl(r['_val_inicial'])}` | Déficit: `{fmt_brl(r['_val_deficit'])}`)"
            )
        return "\n".join(linhas)

    # Comparativo 2026 vs 2027 por Unidade
    u26 = df26.groupby("Unidade")["_val_total"].sum()
    u27 = df27.groupby("Unidade")["_val_total"].sum()
    unidades = sorted(set(u26.index).union(set(u27.index)))

    linhas = [
        "### ⚖️ Comparativo Orçamento 2026 (Execução) vs 2027 (Planejamento)",
        "| Unidade | Estimado 2026 | Planejado Total 2027 | Variação (R$) | Variação (%) |",
        "|---|---|---|---|---|",
    ]
    for u in unidades:
        v26 = float(u26.get(u, 0.0))
        v27 = float(u27.get(u, 0.0))
        diff = v27 - v26
        pct = (diff / v26 * 100) if v26 > 0 else 0.0
        sinal = "+" if diff >= 0 else ""
        linhas.append(f"| **{u}** | `{fmt_brl(v26)}` | `{fmt_brl(v27)}` | `{sinal}{fmt_brl(diff)}` | `{sinal}{pct:.1f}%` |")

    t26 = float(u26.sum())
    t27 = float(u27.sum())
    dtot = t27 - t26
    ptot = (dtot / t26 * 100) if t26 > 0 else 0.0
    linhas.append(f"| **TOTAL GERAL** | **`{fmt_brl(t26)}`** | **`{fmt_brl(t27)}`** | **`{fmt_brl(dtot)}`** | **`{ptot:+.1f}%`** |")
    return "\n".join(linhas)


def _search_keyword_across_all(q_raw: str, q_norm: str, kb: dict[str, Any]) -> str:
    """Pesquisa semântica por palavras-chave simultaneamente nas 5 bases de dados."""
    tokens = [t for t in re.findall(r"[a-z0-9]{3,}", q_norm) if t not in STOPWORDS_PT]
    if not tokens:
        return _build_panorama_geral(kb)

    def match_df(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "_search_blob" not in df.columns:
            return pd.DataFrame()
        # Tenta match com todos os tokens relevantes; se vazio, tenta match com pelo menos o token mais específico
        mask_all = pd.Series(True, index=df.index)
        for t in tokens:
            mask_all &= df["_search_blob"].str.contains(re.escape(t), na=False)
        if mask_all.any():
            return df[mask_all]
        # Fallback: ordenar por número de tokens encontrados
        scores = pd.Series(0, index=df.index)
        for t in tokens:
            scores += df["_search_blob"].str.contains(re.escape(t), na=False).astype(int)
        best_max = scores.max()
        if best_max > 0:
            return df[scores == best_max]
        return pd.DataFrame()

    m26 = match_df(kb["df26"])
    m27 = match_df(kb["df27"])
    msup = match_df(kb["df_sup"])
    mpca = match_df(kb["df_pca"])
    mliq = match_df(kb["df_liq"])

    if m26.empty and m27.empty and msup.empty and mpca.empty and mliq.empty:
        return (
            f"Não encontrei registros específicos para **`{q_raw}`** nas planilhas.\n\n"
            "💡 **Dica:** Você pode perguntar por:\n"
            "* **Temas/Objetos:** *vigilância, limpeza, locação de veículos, link de dados, call center, Pix, Infoconv, Microsoft*\n"
            "* **Unidades:** *STI, SGI, Receita Estadual, SFR, SIF, Tesouro, Gabinete*\n"
            "* **Números:** *Processo SEI, Nº do Contrato (ex: 026/2023)*\n"
            "* **Dashboards:** *Resumo geral, Riscos do PCA no mês, Supressões 2027, Liquidação SIAFIC, Déficit 2027*"
        )

    termo_exib = ", ".join(tokens)
    partes = [f"### 🔮 Resultados do Oráculo para: `{termo_exib}`"]

    if not m26.empty:
        partes.append(
            f"#### 🏢 Orçamento 2026 (Execução) — `{len(m26)}` item(ns) | Total Estimado: `{fmt_brl(m26['_val_total'].sum())}` (Indicado: `{fmt_brl(m26['_val_indicado'].sum())}`)"
        )
        for _, r in m26.sort_values("_val_total", ascending=False).head(6).iterrows():
            partes.append(
                f"* **Item {r.get('Item', '-')} — {r.get('Resumo', r.get('Objeto', '-'))}** ({r.get('Unidade', '-')})\n"
                f"  * Estimado 2026: `{fmt_brl(r['_val_total'])}` | Indicado: `{fmt_brl(r['_val_indicado'])}` | "
                f"Contrato: `{r.get('Nº do Contrato (se houver)', '-')}` | SEI: `{r.get('Nº Processo (se houver)', '-')}`"
            )

    if not m27.empty:
        partes.append(
            f"#### 📅 Planejamento PLOA 2027 — `{len(m27)}` item(ns) | Total 2027: `{fmt_brl(m27['_val_total'].sum())}` (Inicial: `{fmt_brl(m27['_val_inicial'].sum())}` | Déficit: `{fmt_brl(m27['_val_deficit'].sum())}`)"
        )
        for _, r in m27.sort_values("_val_total", ascending=False).head(6).iterrows():
            partes.append(
                f"* **Item {r.get('Item', '-')} — {r.get('Resumo', r.get('Objeto', '-'))}** ({r.get('Unidade', '-')})\n"
                f"  * Total 2027: `{fmt_brl(r['_val_total'])}` | Contrato: `{r.get('Nº do Contrato (se houver)', '-')}` | Empresa: `{r.get('Empresa Contratada', '-')}`"
            )

    if not msup.empty:
        partes.append(
            f"#### ✂️ Supressões PLOA 2027 — `{len(msup)}` item(ns) | Economia Gerada: `{fmt_brl(msup['Economia Gerada'].sum())}`"
        )
        for _, r in msup.head(6).iterrows():
            partes.append(
                f"* **{r['Item de Despesa']}** ({r['Unidade']}) — Orçamento: `{fmt_brl(r['Orçamento 2027'])}` ➔ "
                f"Corte: `{fmt_brl(r['Economia Gerada'])}` ➔ Novo Teto: `{fmt_brl(r['Teto Ajustado 2027'])}` (*{r['Ação Sugerida']}*)"
            )

    if not mpca.empty:
        partes.append(
            f"#### 📑 PCA 2027 (GELC) — `{len(mpca)}` demanda(s) | Estimado 2027: `{fmt_brl(mpca['Valor_Estimado_2027'].sum())}`"
        )
        for _, r in mpca.sort_values("Valor_Estimado_2027", ascending=False).head(6).iterrows():
            it_n = int(r["Item"]) if pd.notna(r["Item"]) else "-"
            dt_d = r["Deadline_Contratacao"].strftime("%d/%m/%Y") if pd.notna(r["Deadline_Contratacao"]) else "N/D"
            partes.append(
                f"* **Item {it_n}: {r['Objeto_Resumido']}** ({r['Unidade_Superior']} · {r['Unidade_Demandante']})\n"
                f"  * Estimado 2027: `{fmt_brl(r['Valor_Estimado_2027'])}` | Providência: `{r['Providencia_2027']}` | "
                f"Status: `{r['Status_Contratacao']}` | Deadline: `{dt_d}` | UO: `{r['Unidade_Orcamentaria']}`"
            )

    if not mliq.empty:
        partes.append(
            f"#### 📜 Liquidação SIAFIC 2026 (SAP BO) — `{len(mliq)}` lançamento(s) | Total Liquidado: `{fmt_brl(mliq['Valor_Liquidado_Saldo'].sum())}`"
        )
        por_b = (
            mliq.groupby(["Beneficiario_Nome", "Processo_SEI"], as_index=False)["Valor_Liquidado_Saldo"]
            .sum()
            .sort_values("Valor_Liquidado_Saldo", ascending=False)
            .head(5)
        )
        for _, r in por_b.iterrows():
            partes.append(f"* **Credor:** {r['Beneficiario_Nome']} (SEI `{r['Processo_SEI']}`) — Liquidado: `{fmt_brl(r['Valor_Liquidado_Saldo'])}`")

    return "\n\n".join(partes)


def consultar_oraculo(pergunta: str) -> str:
    """Processa qualquer pergunta em linguagem natural cruzando todas as bases do painel."""
    if not pergunta or not pergunta.strip():
        return "Por favor, digite uma pergunta para o **Oráculo**."

    kb = load_oraculo_kb()
    q_raw = pergunta.strip()
    q_norm = norm_text(q_raw)

    # 1. Verifica busca exata por Processo SEI ou Número de Contrato
    id_ans = _search_by_identifier(q_raw, kb)
    if id_ans:
        return id_ans

    # 2. Identifica se menciona uma Unidade / Superintendência específica
    matched_unit = None
    for u_key, u_info in UNIT_ALIASES.items():
        for term in u_info["terms"]:
            if re.search(rf"\b{re.escape(term)}\b", q_norm):
                matched_unit = u_key
                break
        if matched_unit:
            break

    # 3. Verifica se é pedido de Panorama Geral / Resumo Geral (sem unidade específica)
    if not matched_unit and any(p in q_norm for p in ["panorama", "resumo geral", "visao geral", "todos os dashboards", "todas as planilhas", "grandes numeros", "o que voce sabe"]):
        return _build_panorama_geral(kb)

    # Se mencionou uma unidade e pediu visão em todas as planilhas/bases/raio-x
    if matched_unit and any(p in q_norm for p in ["todas as planilhas", "todas as bases", "raio x", "raio-x", "geral", "resumo", "como esta", "fale sobre"]):
        return _answer_unit_360(matched_unit, kb)

    # Se perguntou especificamente sobre Supressões
    if any(k in q_norm for k in ["supressao", "supressoes", "corte", "cortes", "economia gerada", "teto ajustado"]):
        if matched_unit and UNIT_ALIASES[matched_unit]["sup"]:
            df_sup = kb["df_sup"]
            sub = df_sup[df_sup["Unidade"].isin(UNIT_ALIASES[matched_unit]["sup"])]
            if not sub.empty:
                linhas = [
                    f"### ✂️ Supressões PLOA 2027 — {UNIT_ALIASES[matched_unit]['nome']}",
                    f"* **Orçamento 2027:** `{fmt_brl(sub['Orçamento 2027'].sum())}` | **Economia Gerada:** `{fmt_brl(sub['Economia Gerada'].sum())}` | **Teto Ajustado:** `{fmt_brl(sub['Teto Ajustado 2027'].sum())}`\n",
                    "| Item de Despesa | Orçamento 2027 | Economia Gerada | Teto Ajustado | Ação Sugerida |",
                    "|---|---|---|---|---|",
                ]
                for _, r in sub.sort_values("Economia Gerada", ascending=False).iterrows():
                    linhas.append(
                        f"| **{r['Item de Despesa']}** | `{fmt_brl(r['Orçamento 2027'])}` | `{fmt_brl(r['Economia Gerada'])}` | `{fmt_brl(r['Teto Ajustado 2027'])}` | {r['Ação Sugerida']} |"
                    )
                return "\n".join(linhas)
        return _answer_supressoes(q_norm, kb)

    # Se perguntou especificamente sobre PCA 2027 / GELC / Cronograma / Prazos
    if any(k in q_norm for k in ["pca", "gelc", "setrac", "deadline", "prorrogac", "nova contratacao", "novas contratacoes", "risco", "vencid", "atrasad", "mes corrente", "mes atual"]):
        if matched_unit and UNIT_ALIASES[matched_unit]["pca"] and not any(k in q_norm for k in ["risco", "vencid", "atrasad", "mes corrente", "mes atual"]):
            df_pca = kb["df_pca"]
            sub = df_pca[df_pca["Unidade_Superior"].isin(UNIT_ALIASES[matched_unit]["pca"])]
            if not sub.empty:
                linhas = [
                    f"### 📑 PCA 2027 (GELC) — {UNIT_ALIASES[matched_unit]['nome']}",
                    f"* **Total de Demandas:** `{len(sub)}` | **Estimado 2027:** `{fmt_brl(sub['Valor_Estimado_2027'].sum())}` | **Valor Total Contratação:** `{fmt_brl(sub['Valor_Total_Estimado'].sum())}`\n",
                    "| Item | Objeto Resumido | Gerência Demandante | Providência 2027 | Deadline | Estimado 2027 |",
                    "|---|---|---|---|---|---|",
                ]
                for _, r in sub.sort_values("Valor_Estimado_2027", ascending=False).iterrows():
                    it_n = int(r["Item"]) if pd.notna(r["Item"]) else "-"
                    dt_d = r["Deadline_Contratacao"].strftime("%d/%m/%Y") if pd.notna(r["Deadline_Contratacao"]) else "-"
                    linhas.append(
                        f"| {it_n} | **{r['Objeto_Resumido']}** | {r['Unidade_Demandante']} | {r['Providencia_2027']} | `{dt_d}` | `{fmt_brl(r['Valor_Estimado_2027'])}` |"
                    )
                return "\n".join(linhas)
        return _answer_pca_specific(q_norm, kb)

    # Se perguntou especificamente sobre Liquidação / SIAFIC / SAP BO
    if any(k in q_norm for k in ["liquidac", "liquidado", "siafic", "sap bo", "beneficiario", "credor", "fornecedor"]):
        return _answer_liquidacao(q_norm, kb)

    # Se mencionou uma unidade sem filtro de objeto específico
    other_tokens = [
        t for t in re.findall(r"[a-z0-9]{3,}", q_norm)
        if t not in STOPWORDS_PT and not any(t in u["terms"] or any(t in term.split() for term in u["terms"]) for u in UNIT_ALIASES.values())
    ]
    if matched_unit and not other_tokens:
        return _answer_unit_360(matched_unit, kb)

    # Se perguntou sobre comparativo 2026 vs 2027, cota, déficit, maiores despesas
    if any(k in q_norm for k in ["compar", "deficit", "cota", "maiores despesas", "top", "2026", "2027", "ploa", "execucao"]) and not other_tokens:
        return _answer_orcamento_2026_2027(q_norm, kb)

    # 4. Busca semântica multi-planilha por palavra-chave / objeto / fornecedor
    return _search_keyword_across_all(q_raw, q_norm, kb)


SUGESTOES_RAPIDAS = [
    ("📊 Panorama Geral", "Me dê um panorama geral consolidado de todos os dashboards"),
    ("🚨 Riscos PCA no Mês", "Quais processos do PCA 2027 estão com prazo vencido ou limite no mês atual?"),
    ("💻 Raio-X da STI", "Como está a STI em todas as planilhas (2026, 2027, Supressões e PCA)?"),
    ("🏢 Raio-X da SGI", "Fale sobre a SGI em todas as bases"),
    ("✂️ Supressões PLOA", "Qual o resumo das Supressões PLOA 2027 e os maiores cortes?"),
    ("📜 Liquidação SIAFIC", "Quanto já foi liquidado no SIAFIC em 2026 e quais os maiores fornecedores?"),
    ("⚖️ 2026 vs 2027", "Compare o orçamento de 2026 com o planejamento 2027 por unidade"),
    ("📑 Resumo PCA 2027", "Qual o resumo do PCA 2027 por Superintendência?"),
]


def render_oraculo_chat_ui(key_prefix: str = "modal") -> None:
    """Renderiza a interface conversacional completa do Oráculo (usada tanto no modal quanto na página dedicada)."""
    if "oraculo_messages" not in st.session_state:
        st.session_state["oraculo_messages"] = [
            {
                "role": "assistant",
                "content": (
                    "Olá! Eu sou o **Oráculo** 🔮, a inteligência analítica da Secretaria da Economia.\n\n"
                    "Conecto em tempo real as **5 bases oficiais do painel**:\n"
                    "1. **Execução Orçamentária 2026** *(SharePoint)*\n"
                    "2. **Liquidação Mensal por Contrato / SIAFIC** *(SAP BO)*\n"
                    "3. **Planejamento / PLOA 2027** *(SharePoint)*\n"
                    "4. **Supressões PLOA 2027** *(SharePoint)*\n"
                    "5. **PCA 2027 — Contratações GELC** *(Google Sheets)*\n\n"
                    "Clique em um atalho abaixo ou digite qualquer pergunta (por **Unidade**, **Objeto**, **Contrato**, **Processo SEI** ou **Prazo**):"
                ),
            }
        ]

    # Barra de atalhos inteligentes
    st.markdown(
        "<div style='font-size:0.78rem; font-weight:700; color:#047857; text-transform:uppercase; "
        "letter-spacing:0.05em; margin-bottom:6px;'>⚡ Consultas Rápidas Sugeridas:</div>",
        unsafe_allow_html=True,
    )

    cols_sug = st.columns(4)
    triggered_prompt = None
    for idx, (label_btn, prompt_txt) in enumerate(SUGESTOES_RAPIDAS):
        with cols_sug[idx % 4]:
            if st.button(label_btn, key=f"{key_prefix}_sug_{idx}", use_container_width=True):
                triggered_prompt = prompt_txt

    st.markdown("<hr style='margin:8px 0 12px 0; border-color:#DCEBE3;'>", unsafe_allow_html=True)

    # Container de mensagens com rolagem
    chat_container = st.container(height=410 if key_prefix == "modal" else 520)
    with chat_container:
        for msg in st.session_state["oraculo_messages"]:
            avatar = "🔮" if msg["role"] == "assistant" else "🧑‍💼"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    # Entrada de pergunta + botão limpar
    c_in, c_clear = st.columns([5.5, 1])
    with c_in:
        user_input = st.chat_input(
            "Pergunte ao Oráculo (ex: 'vigilância', 'STI', 'riscos PCA', 'processo SEI', 'déficit 2027')...",
            key=f"{key_prefix}_chat_input",
        )
    with c_clear:
        if st.button("🗑️ Limpar", key=f"{key_prefix}_clear_btn", use_container_width=True, help="Limpar histórico de conversa"):
            st.session_state["oraculo_messages"] = st.session_state["oraculo_messages"][:1]
            st.rerun(scope="fragment" if key_prefix == "modal" else "app")

    final_query = triggered_prompt or user_input
    if final_query:
        st.session_state["oraculo_messages"].append({"role": "user", "content": final_query})
        resposta = consultar_oraculo(final_query)
        st.session_state["oraculo_messages"].append({"role": "assistant", "content": resposta})
        st.rerun(scope="fragment" if key_prefix == "modal" else "app")


@st.dialog("🔮 Oráculo · Inteligência Orçamentária & Contratações", width="large")
def open_oraculo_dialog() -> None:
    """Modal flutuante do Oráculo acessível de qualquer página sem perder os filtros ativos."""
    render_oraculo_chat_ui(key_prefix="modal")


def inject_floating_oraculo() -> None:
    """Injeta o botão flutuante (canto inferior direito) e o atalho na barra lateral em todas as páginas."""
    st.markdown(
        """
        <style>
        /* Estilo do botão flutuante fixo no canto inferior direito */
        .st-key-btn_floating_oraculo_fab {
            position: fixed !important;
            bottom: 24px !important;
            right: 28px !important;
            z-index: 999990 !important;
            width: auto !important;
        }
        .st-key-btn_floating_oraculo_fab button {
            background: linear-gradient(135deg, #064E3B 0%, #047857 55%, #10B981 100%) !important;
            color: #FFFFFF !important;
            border: 2px solid #A7F3D0 !important;
            border-radius: 999px !important;
            padding: 10px 22px !important;
            height: 50px !important;
            font-size: 0.98rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.01em !important;
            box-shadow: 0 8px 24px rgba(6, 78, 59, 0.45), 0 0 0 4px rgba(16, 185, 129, 0.20) !important;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }
        .st-key-btn_floating_oraculo_fab button:hover {
            transform: translateY(-3px) scale(1.04) !important;
            box-shadow: 0 12px 28px rgba(6, 78, 59, 0.60), 0 0 0 6px rgba(16, 185, 129, 0.32) !important;
            color: #FFFFFF !important;
        }
        .st-key-btn_floating_oraculo_fab button p {
            font-size: 0.96rem !important;
            font-weight: 700 !important;
            color: #FFFFFF !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🔮 Oráculo IA", key="btn_floating_oraculo_fab", help="Abrir assistente inteligente sobre todas as planilhas"):
        open_oraculo_dialog()
