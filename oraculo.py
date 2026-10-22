"""Oráculo — Assistente Inteligente Multi-Base do Painel de Gestão Orçamentária e Contratações (SECON-GO)."""
from __future__ import annotations

from datetime import datetime
import difflib
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
MESES_NORM_MAP = {norm_text(m): m for m in MESES_NOMES}
MESES_ABREV = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
}

# Dicionário de correção automática de erros de digitação (typos comuns em português)
TYPO_CORRECTIONS = {
    "depesa": "despesa",
    "depesas": "despesas",
    "despeza": "despesa",
    "despezas": "despesas",
    "dspesa": "despesa",
    "defict": "deficit",
    "deficite": "deficit",
    "deficti": "deficit",
    "defcit": "deficit",
    "defice": "deficit",
    "suprisao": "supressao",
    "suprisoes": "supressoes",
    "supresao": "supressao",
    "supresoes": "supressoes",
    "orcamento": "orcamento",
    "orsamento": "orcamento",
    "orcameto": "orcamento",
    "liquidacao": "liquidacao",
    "liqidacao": "liquidacao",
    "liquidaçao": "liquidacao",
    "contratacao": "contratacao",
    "contrataçao": "contratacao",
    "contratacoes": "contratacoes",
    "prorrogacao": "prorrogacao",
    "prorrogaçao": "prorrogacao",
    "superintedencia": "superintendencia",
    "superitendencia": "superintendencia",
    "fornessedor": "fornecedor",
    "fornesedor": "fornecedor",
    "vigilansa": "vigilancia",
    "limpesa": "limpeza",
    "tercerizacao": "terceirizacao",
    "terceirizaçao": "terceirizacao",
}

DOMAIN_VOCAB = [
    "despesa", "despesas", "deficit", "orcamento", "contrato", "contratos",
    "processo", "processos", "supressao", "supressoes", "liquidacao", "liquidado",
    "fornecedor", "fornecedores", "empresa", "empresas", "beneficiario", "credor",
    "unidade", "unidades", "superintendencia", "gerencia", "modalidade",
    "prorrogacao", "prorrogacoes", "contratacao", "contratacoes", "indicado",
    "restante", "saldo", "inicial", "global", "custeio", "investimento",
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
    "agosto", "setembro", "outubro", "novembro", "dezembro", "vigilancia",
    "limpeza", "veiculos", "tecnologia", "receita", "gestao", "integrada",
    "tesouro", "deadline", "setrac", "vencido", "vencidos", "atrasado", "atrasados",
    "maior", "maiores", "menor", "menores", "economias", "economia", "corte", "cortes",
]


def normalize_and_fix_typos(text: str, extra_vocab: list[str] | None = None) -> str:
    """Normaliza a pergunta e corrige automaticamente erros de digitação usando dicionário e similaridade."""
    base = norm_text(text)
    tokens = re.findall(r"[a-z0-9/]+", base)
    vocab = list(set(DOMAIN_VOCAB + (extra_vocab or [])))
    fixed_tokens = []
    for tok in tokens:
        if tok in TYPO_CORRECTIONS:
            fixed_tokens.append(TYPO_CORRECTIONS[tok])
        elif tok in STOPWORDS_PT or tok.isdigit() or len(tok) <= 4 or tok in vocab or "/" in tok:
            fixed_tokens.append(tok)
        else:
            matches = difflib.get_close_matches(tok, DOMAIN_VOCAB, n=1, cutoff=0.86)
            if matches:
                fixed_tokens.append(matches[0])
            elif extra_vocab:
                m_extra = difflib.get_close_matches(tok, extra_vocab, n=1, cutoff=0.88)
                fixed_tokens.append(m_extra[0] if m_extra else tok)
            else:
                fixed_tokens.append(tok)
    return " ".join(fixed_tokens)


def _clean_str_col(s: pd.Series) -> pd.Series:
    """Remove quebras de linha, espaços non-breaking (\\xa0) e espaços duplicados nas colunas de texto."""
    return (
        s.astype("string")
        .str.replace("_x000D_", " ", regex=False)
        .str.replace("\xa0", " ", regex=False)
        .str.replace("\n", " ", regex=False)
        .str.replace("\r", " ", regex=False)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .astype(object)
    )


def _compact_text(s: str) -> str:
    """Remove todos os espaços e caracteres especiais para busca insensível a espaços/hífens (ex: BR FIBRA == BRFIBRA)."""
    return re.sub(r"[^a-z0-9]", "", norm_text(s))


def _clean_budget_df(raw: pd.DataFrame, ano: int, only_active: bool = True) -> pd.DataFrame:
    """Aplica as mesmas regras de limpeza das páginas oficiais de 2026 e 2027."""
    if raw.empty:
        return raw.copy()
    df = raw.copy()

    # Limpa todas as colunas de texto principais para evitar falhas de agrupamento por '\xa0' ou '\n'
    for col_txt in [
        "Objeto", "Resumo", "Classificação do Objeto", "Nº do Contrato (se houver)",
        "Nº Processo (se houver)", "Nº IPOF (se houver)", "Empresa Contratada",
        "Unidade", "Departamento", "Grupo de Despesa", "Situação", "Situação IPOF", "PROFISCO"
    ]:
        if col_txt in df.columns:
            df[col_txt] = _clean_str_col(df[col_txt])

    c_total = f"Estimado Total {ano}"
    if c_total not in df.columns:
        matches = [c for c in df.columns if str(c).startswith("Estimado Total")]
        c_total = matches[0] if matches else df.columns[0]

    c_meses = [c for m in MESES_NOMES for c in df.columns if c == f"Estimado {m}"]
    for c in [c_total, *c_meses]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    if "Valor Global do Contrato" in df.columns:
        df["_val_global"] = pd.to_numeric(df["Valor Global do Contrato"], errors="coerce").fillna(0.0)
    else:
        df["_val_global"] = 0.0

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

    if only_active:
        # Aplica os filtros padrão oficiais dos painéis (Situação = Ativo, PROFISCO = Não, e em 2026 Situação IPOF = Liberado/Programada)
        if "Situação" in df.columns:
            df = df[df["Situação"].astype(str).str.strip().isin(["Ativo"])].copy()
        if ano == 2026 and "Situação IPOF" in df.columns:
            df = df[df["Situação IPOF"].astype(str).str.strip().isin(["Liberado", "Programada"])].copy()
        prof_cols = [c for c in df.columns if "profisco" in str(c).lower()]
        if prof_cols:
            is_prof_sim = df[prof_cols[0]].astype(str).str.strip().str.lower().isin(["sim", "s", "true"])
            df = df[~is_prof_sim].copy()

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

    search_cols = [
        c for c in ["Item", "Objeto", "Resumo", "Classificação do Objeto", "Nº do Contrato (se houver)",
                    "Nº Processo (se houver)", "Nº IPOF (se houver)", "Empresa Contratada", "Unidade",
                    "Departamento", "Grupo de Despesa", "Situação", "Situação IPOF"]
        if c in df.columns
    ]
    df["_search_blob"] = df[search_cols].fillna("").astype(str).agg(" | ".join, axis=1).apply(norm_text)
    df["_search_blob_compact"] = df["_search_blob"].apply(_compact_text)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_oraculo_kb() -> dict[str, Any]:
    """Carrega e indexa todas as 5 bases de dados do painel para consulta instantânea."""
    raw26, u26, _ = data_source.load_data(2026)
    raw27, u27, _ = data_source.load_data(2027)
    df_sup, u_sup, _ = data_source.load_supressoes_2027()
    df_pca, u_pca = pca_data.load_pca_data()
    df_liq, u_liq = liquidado_mensal_data.load_liquidado_mensal_data()

    df26 = _clean_budget_df(raw26, 2026, only_active=True)
    df27 = _clean_budget_df(raw27, 2027, only_active=True)
    df26_all = _clean_budget_df(raw26, 2026, only_active=False)
    df27_all = _clean_budget_df(raw27, 2027, only_active=False)

    if not df_sup.empty:
        df_sup = df_sup.copy()
        df_sup["_search_blob"] = (
            df_sup[["Unidade", "Item de Despesa", "Ação Sugerida"]]
            .fillna("").astype(str).agg(" | ".join, axis=1).apply(norm_text)
        )
        df_sup["_search_blob_compact"] = df_sup["_search_blob"].apply(_compact_text)

    if not df_pca.empty:
        df_pca = df_pca.copy()
        # Regra de negócio do Oráculo: desconsiderar valores estimados de despesas futuras do PCA 2027, mantendo Valor_Contratado
        for col_v in ["Valor_Estimado_2027", "Valor_Total_Estimado"]:
            if col_v in df_pca.columns:
                df_pca.drop(columns=[col_v], inplace=True)
        if "Valor_Contratado" in df_pca.columns:
            df_pca["Valor_Contratado"] = pd.to_numeric(df_pca["Valor_Contratado"], errors="coerce").fillna(0.0)
        else:
            df_pca["Valor_Contratado"] = 0.0
        pca_cols = [
            "Item", "Processo_SEI", "Objeto_Resumido", "Detalhamento_Objeto",
            "Unidade_Superior", "Unidade_Demandante", "Contrato_Vigente",
            "Modalidade", "Providencia_2027", "Status_Contratacao", "Unidade_Orcamentaria"
        ]
        df_pca["_search_blob"] = (
            df_pca[[c for c in pca_cols if c in df_pca.columns]]
            .fillna("").astype(str).agg(" | ".join, axis=1).apply(norm_text)
        )
        df_pca["_search_blob_compact"] = df_pca["_search_blob"].apply(_compact_text)

    if not df_liq.empty:
        df_liq = df_liq.copy()
        df_liq_2026 = df_liq[df_liq["Ano_Referencia"] == 2026].copy() if "Ano_Referencia" in df_liq.columns else df_liq.copy()
        df_liq_2026["_search_blob"] = (
            df_liq_2026[["Processo_SEI", "Beneficiario_Nome", "Natureza_Despesa_Nome", "Natureza_Despesa_Codigo"]]
            .fillna("").astype(str).agg(" | ".join, axis=1).apply(norm_text)
        )
        df_liq_2026["_search_blob_compact"] = df_liq_2026["_search_blob"].apply(_compact_text)
    else:
        df_liq_2026 = pd.DataFrame()

    # Vocabulário dinâmico extraído dos objetos e empresas reais das planilhas para correção de typos
    vocab_objs: set[str] = set()
    for s_col in [
        df26.get("Resumo", pd.Series(dtype=str)),
        df26.get("Objeto", pd.Series(dtype=str)),
        df26.get("Empresa Contratada", pd.Series(dtype=str)),
        df26.get("Classificação do Objeto", pd.Series(dtype=str)),
        df27.get("Resumo", pd.Series(dtype=str)),
        df27.get("Objeto", pd.Series(dtype=str)),
        df27.get("Empresa Contratada", pd.Series(dtype=str)),
        df27.get("Classificação do Objeto", pd.Series(dtype=str)),
        df_sup.get("Item de Despesa", pd.Series(dtype=str)),
        df_pca.get("Objeto_Resumido", pd.Series(dtype=str)),
        df_liq_2026.get("Beneficiario_Nome", pd.Series(dtype=str)),
    ]:
        for val in s_col.dropna():
            for w in re.findall(r"[a-z0-9]{3,}", norm_text(val)):
                vocab_objs.add(w)

    return {
        "df26": df26,
        "df26_all": df26_all,
        "u26": u26,
        "df27": df27,
        "df27_all": df27_all,
        "u27": u27,
        "df_sup": df_sup,
        "u_sup": u_sup,
        "df_pca": df_pca,
        "u_pca": u_pca,
        "df_liq": df_liq_2026,
        "u_liq": u_liq,
        "cota_2026": 207478837.10,
        "cota_2027": 144089232.46,
        "extra_vocab": sorted(vocab_objs),
    }


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
    "saldo", "restante", "geral", "consolidado", "situacao", "gasto", "gastos", "custo", "custos",
    "previsto", "prevista", "previstos", "previstas", "planejado", "planejada", "planejados", "planejadas",
    "estimados", "estimadas", "orcado", "orcada", "orcados", "orcadas", "gastar", "gastamos", "gastou",
    "gastara", "custa", "custam", "custara", "pagar", "pago", "pagos", "investir", "investido",
    "teremos", "tera", "vao", "vai", "serao", "sera", "alto", "alta", "baixo", "baixa", "caro", "cara",
    "teve", "tiveram", "recebeu", "receberam", "ganhou", "pca", "gelc", "siafic", "sap", "setrac",
    "geof", "possui", "possuem", "sofreu", "sofreram", "apresenta", "apresentam",
    "numero", "numeros", "nro", "num", "codigo", "codigos", "nome", "nomes", "empresa", "empresas",
    "fornecedor", "fornecedores", "credor", "credores", "beneficiario", "beneficiarios",
    "contratada", "contratadas", "contratado", "contratados", "vigente", "vigentes", "atual", "atuais",
    "ativo", "ativos", "ativa", "ativas", "sei", "ipof", "objeto", "objetos", "detalhe", "detalhes",
    "quero", "queria", "gostaria", "preciso", "pode", "poderia", "consegue", "sabe", "saber", "dizer",
    "mostrar", "informe", "informar", "buscar", "busque", "achar", "encontrar", "encontre", "ver",
    "consultar", "verificar", "calcular", "somar", "some", "favor", "gentileza", "referente", "relativo",
}

SHORT_SIGNIFICANT_TOKENS = {"ti", "rh", "bi", "ia", "ar", "tv", "pc", "uo"}


def _detect_unit(q_norm: str) -> str | None:
    for u_key, u_info in UNIT_ALIASES.items():
        for term in u_info["terms"]:
            if re.search(rf"\b{re.escape(term)}\b", q_norm):
                return u_key
    return None


def _answer_deficit_analysis(q_norm: str, kb: dict[str, Any], unit_key: str | None = None) -> str:
    """Responde de forma cirúrgica qualquer pergunta sobre Déficit 2027 (maior déficit, menor, por unidade, total)."""
    df27 = kb["df27"].copy()
    if unit_key:
        df27 = df27[df27["Unidade"].isin(UNIT_ALIASES[unit_key]["orc"])].copy()

    sub_def = df27[df27["_val_deficit"] > 0].copy()
    if sub_def.empty:
        return "Não há nenhuma despesa com déficit registrado para o filtro consultado."

    is_menor = any(w in q_norm for w in ["menor", "menores", "mais baixo", "minimo"])
    sub_def = sub_def.sort_values("_val_deficit", ascending=is_menor)

    tot_def_geral = float(sub_def["_val_deficit"].sum())
    tot_ini_geral = float(df27["_val_inicial"].sum())
    tot_2027_geral = float(df27["_val_total"].sum())

    # Top 1 individual (linha da planilha)
    top1 = sub_def.iloc[0]
    top1_item = int(top1["Item"]) if pd.notna(top1.get("Item")) and str(top1.get("Item")).replace(".0", "").isdigit() else top1.get("Item", "-")
    top1_res = top1.get("Resumo", top1.get("Objeto", "-"))
    top1_uni = top1.get("Unidade", "-")
    top1_def = float(top1["_val_deficit"])
    top1_ini = float(top1["_val_inicial"])
    top1_tot = float(top1["_val_total"])
    top1_pct = (top1_def / tot_def_geral * 100) if tot_def_geral > 0 else 0.0

    # Agrupado por Resumo (caso a mesma despesa esteja dividida em mais de um item)
    por_resumo = (
        sub_def.groupby(["Resumo", "Unidade"], as_index=False)
        .agg(Qtd=("Item", "count"), Ini=("_val_inicial", "sum"), Def=("_val_deficit", "sum"), Tot=("_val_total", "sum"))
        .sort_values("Def", ascending=is_menor)
    )
    top1_agrup = por_resumo.iloc[0]

    # Agrupado por Unidade
    por_uni = (
        sub_def.groupby("Unidade", as_index=False)
        .agg(Qtd=("Item", "count"), Ini=("_val_inicial", "sum"), Def=("_val_deficit", "sum"), Tot=("_val_total", "sum"))
        .sort_values("Def", ascending=False)
    )
    u_lider = por_uni.iloc[0]
    u_lider_pct = (float(u_lider["Def"]) / tot_def_geral * 100) if tot_def_geral > 0 else 0.0

    titulo_extremo = "Menor Déficit" if is_menor else "Maior Déficit"
    escopo_txt = f" ({UNIT_ALIASES[unit_key]['nome']})" if unit_key else " (PLOA 2027)"

    linhas = [
        f"### 🎯 Análise de Déficit Orçamentário 2027 — {titulo_extremo}{escopo_txt}\n",
        f"🏆 **Despesa com o {titulo_extremo} Individual:**",
        f"* **Item {top1_item} — {top1_res}** (*Unidade: {top1_uni}*)",
        f"  * **Déficit Estimado para 2027:** **`{fmt_brl(top1_def)}`** *(representa `{top1_pct:.1f}%` de todo o déficit de 2027)*",
        f"  * **Estimado Inicial:** `{fmt_brl(top1_ini)}` | **Estimado Total 2027:** `{fmt_brl(top1_tot)}`",
        f"  * **Contrato:** `{top1.get('Nº do Contrato (se houver)', '-')}` | **Empresa:** `{top1.get('Empresa Contratada', '-')}`",
    ]

    if int(top1_agrup["Qtd"]) > 1 and not is_menor:
        pct_ag = (float(top1_agrup["Def"]) / tot_def_geral * 100) if tot_def_geral > 0 else 0.0
        linhas.append(
            f"\n💡 **Nota Consolidada:** Somando os **{int(top1_agrup['Qtd'])} itens** de **`{top1_agrup['Resumo']}`** ({top1_agrup['Unidade']}), "
            f"o déficit acumulado desse objeto chega a **`{fmt_brl(top1_agrup['Def'])}`** (`{pct_ag:.1f}%` do déficit total)."
        )

    linhas.extend([
        f"\n📊 **Resumo Geral do Déficit 2027:**",
        f"* **Déficit Total Mapeado em 2027:** `{fmt_brl(tot_def_geral)}` (distribuído em `{len(sub_def)}` itens de despesa)",
        f"* **Unidade com Maior Déficit Acumulado:** **{u_lider['Unidade']}** com `{fmt_brl(u_lider['Def'])}` (`{u_lider_pct:.1f}%` do total, em `{int(u_lider['Qtd'])}` itens)",
        f"* **Orçamento Inicial 2027:** `{fmt_brl(tot_ini_geral)}` ➔ **Total Planejado (Inicial + Déficit):** `{fmt_brl(tot_2027_geral)}`\n",
        f"#### 🔝 Top 10 Despesas por {titulo_extremo} em 2027:",
        "| # | Item | Despesa (Resumo) | Unidade | Estimado Inicial | Déficit 2027 | Total 2027 | % do Déficit |",
        "|---|---|---|---|---|---|---|---|",
    ])

    for idx, (_, r) in enumerate(sub_def.head(10).iterrows(), 1):
        it_num = int(r["Item"]) if pd.notna(r.get("Item")) and str(r.get("Item")).replace(".0", "").isdigit() else r.get("Item", "-")
        pct_i = (float(r["_val_deficit"]) / tot_def_geral * 100) if tot_def_geral > 0 else 0.0
        linhas.append(
            f"| {idx}º | {it_num} | **{r.get('Resumo', r.get('Objeto', '-'))}** | {r.get('Unidade', '-')} | "
            f"`{fmt_brl(r['_val_inicial'])}` | **`{fmt_brl(r['_val_deficit'])}`** | `{fmt_brl(r['_val_total'])}` | `{pct_i:.1f}%` |"
        )

    if not unit_key and len(por_uni) > 1:
        linhas.extend([
            "\n#### 🏢 Déficit 2027 Consolidado por Unidade:",
            "| Unidade | Itens c/ Déficit | Déficit 2027 | % Participação |",
            "|---|---|---|---|",
        ])
        for _, r in por_uni.iterrows():
            p_u = (float(r["Def"]) / tot_def_geral * 100) if tot_def_geral > 0 else 0.0
            linhas.append(f"| **{r['Unidade']}** | {int(r['Qtd'])} | **`{fmt_brl(r['Def'])}`** | `{p_u:.1f}%` |")

    return "\n".join(linhas)


def _answer_ranking_or_extreme(q_norm: str, kb: dict[str, Any], unit_key: str | None = None) -> str | None:
    """Motor de ranking inteligente: responde 'qual a maior/menor despesa, contrato, fornecedor, corte, etc.' em qualquer base."""
    has_extreme = any(w in q_norm for w in [
        "maior", "maiores", "mais cara", "mais caro", "mais alto", "mais alta",
        "menor", "menores", "mais barata", "mais barato", "mais baixo", "mais baixa",
        "top", "ranking", "campeao", "lider", "primeiro", "principal", "principais",
        "gasta mais", "consome mais", "recebeu mais", "receberam mais", "ganhou mais",
    ])
    if not has_extreme:
        return None

    is_menor = any(w in q_norm for w in ["menor", "menores", "mais barata", "mais barato", "mais baixo", "mais baixa"])
    lbl_ord = "Menor" if is_menor else "Maior"

    # 1. Se menciona Déficit -> análise dedicada de déficit
    if "deficit" in q_norm:
        return _answer_deficit_analysis(q_norm, kb, unit_key=unit_key)

    # 2. Se menciona Supressões / Cortes / Economia
    if any(w in q_norm for w in ["supressao", "supressoes", "corte", "cortes", "economia", "reduzir", "reducao"]):
        df_sup = kb["df_sup"].copy()
        if unit_key and UNIT_ALIASES[unit_key]["sup"]:
            df_sup = df_sup[df_sup["Unidade"].isin(UNIT_ALIASES[unit_key]["sup"])].copy()
        if df_sup.empty:
            return "Não há registros de supressão para este filtro."
        sub = df_sup.sort_values("Economia Gerada", ascending=is_menor)
        top1 = sub.iloc[0]
        tot_ec = float(df_sup["Economia Gerada"].sum())
        pct1 = (float(top1["Economia Gerada"]) / tot_ec * 100) if tot_ec > 0 else 0.0
        linhas = [
            f"### ✂️ {lbl_ord} Supressão / Corte na PLOA 2027",
            f"🏆 **1º Lugar:** **{top1['Item de Despesa']}** (*Unidade: {top1['Unidade']}*)",
            f"* **Economia Gerada (Corte):** **`{fmt_brl(top1['Economia Gerada'])}`** (`{pct1:.1f}%` da economia total de `{fmt_brl(tot_ec)}`)",
            f"* **Orçamento Inicial 2027:** `{fmt_brl(top1['Orçamento 2027'])}` ➔ **Novo Teto Ajustado:** `{fmt_brl(top1['Teto Ajustado 2027'])}`",
            f"* **Ação Sugerida:** *{top1['Ação Sugerida']}*\n",
            f"#### 🔝 Top 10 {lbl_ord}es Supressões (PLOA 2027):",
            "| # | Unidade | Item de Despesa | Orçamento 2027 | Economia Gerada (Corte) | Teto Ajustado 2027 | Ação Sugerida |",
            "|---|---|---|---|---|---|---|",
        ]
        for idx, (_, r) in enumerate(sub.head(10).iterrows(), 1):
            linhas.append(
                f"| {idx}º | {r['Unidade']} | **{r['Item de Despesa']}** | `{fmt_brl(r['Orçamento 2027'])}` | **`{fmt_brl(r['Economia Gerada'])}`** | `{fmt_brl(r['Teto Ajustado 2027'])}` | {r['Ação Sugerida']} |"
            )
        return "\n".join(linhas)

    # 3. Se menciona PCA 2027 / GELC -> ranking por Valor Contratado ou por quantidade de demandas
    if any(w in q_norm for w in ["pca", "gelc"]):
        df_pca = kb["df_pca"].copy()
        if "tesouro" in q_norm and "geof" not in q_norm:
            df_pca = df_pca[df_pca["Unidade_Orcamentaria"] == "Tesouro"].copy()
        elif "tod" not in q_norm:
            df_pca = df_pca[df_pca["Unidade_Orcamentaria"] == "GEOF"].copy()

        if df_pca.empty:
            return "Nenhuma demanda encontrada no PCA 2027 para este critério."

        por_sup = (
            df_pca.groupby("Unidade_Superior", as_index=False)
            .agg(Qtd=("Objeto_Resumido", "count"), ValContratado=("Valor_Contratado", "sum"))
            .sort_values("Qtd", ascending=is_menor)
        )
        top1 = por_sup.iloc[0]
        linhas = [
            f"### 📑 Ranking de Demandas no PCA 2027 ({lbl_ord} Quantidade de Processos)",
            f"🏆 **1º Lugar:** **{top1['Unidade_Superior']}** com **`{int(top1['Qtd'])}` demandas** (Valor Contratado Vigente: `{fmt_brl(top1['ValContratado'])}`).\n",
            "| # | Superintendência / Unidade Superior | Qtd. Demandas no PCA 2027 | Valor Contratado Vigente |",
            "|---|---|---|---|",
        ]
        for idx, (_, r) in enumerate(por_sup.iterrows(), 1):
            linhas.append(f"| {idx}º | **{r['Unidade_Superior']}** | `{int(r['Qtd'])}` | `{fmt_brl(r['ValContratado'])}` |")
        return "\n".join(linhas)

    # 4. Se menciona Liquidação / SIAFIC / Fornecedor / Credor / Beneficiário
    if any(w in q_norm for w in ["liquidado", "liquidacao", "siafic", "beneficiario", "credor", "fornecedor", "empresa"]):
        if any(w in q_norm for w in ["liquidado", "liquidacao", "siafic", "beneficiario", "credor"]):
            df_liq = kb["df_liq"]
            por_b = (
                df_liq.groupby("Beneficiario_Nome", as_index=False)["Valor_Liquidado_Saldo"]
                .sum()
                .sort_values("Valor_Liquidado_Saldo", ascending=is_menor)
            )
            top1 = por_b.iloc[0]
            tot_l = float(df_liq["Valor_Liquidado_Saldo"].sum())
            pct1 = (float(top1["Valor_Liquidado_Saldo"]) / tot_l * 100) if tot_l > 0 else 0.0
            linhas = [
                f"### 💳 {lbl_ord} Fornecedor / Beneficiário Liquidado no SIAFIC (2026)",
                f"🏆 **1º Lugar:** **{top1['Beneficiario_Nome']}**",
                f"* **Total Liquidado em 2026:** **`{fmt_brl(top1['Valor_Liquidado_Saldo'])}`** (`{pct1:.1f}%` do total liquidado de `{fmt_brl(tot_l)}`)\n",
                "| # | Beneficiário / Fornecedor | Total Liquidado 2026 | % do Total |",
                "|---|---|---|---|",
            ]
            for idx, (_, r) in enumerate(por_b.head(10).iterrows(), 1):
                p = (float(r["Valor_Liquidado_Saldo"]) / tot_l * 100) if tot_l > 0 else 0.0
                linhas.append(f"| {idx}º | **{r['Beneficiario_Nome']}** | **`{fmt_brl(r['Valor_Liquidado_Saldo'])}`** | `{p:.1f}%` |")
            return "\n".join(linhas)

    # 5. Orçamento 2026 ou Planejamento 2027 (Despesas / Unidades / Custeio / Investimento / Mês)
    ano_alvo = 2026 if ("2026" in q_norm and "2027" not in q_norm) else 2027
    df_alvo = kb["df26"].copy() if ano_alvo == 2026 else kb["df27"].copy()

    if unit_key:
        df_alvo = df_alvo[df_alvo["Unidade"].isin(UNIT_ALIASES[unit_key]["orc"])].copy()

    if "investimento" in q_norm and "custeio" not in q_norm:
        df_alvo = df_alvo[df_alvo["Grupo de Despesa"].astype(str).str.lower().str.contains("investimento", na=False)].copy()
        lbl_grupo = " (Apenas Investimento)"
    elif "custeio" in q_norm and "investimento" not in q_norm:
        df_alvo = df_alvo[df_alvo["Grupo de Despesa"].astype(str).str.lower().str.contains("custeio", na=False)].copy()
        lbl_grupo = " (Apenas Custeio)"
    else:
        lbl_grupo = ""

    # Verifica se pediu um mês específico (Janeiro a Dezembro)
    col_metrica = "_val_total"
    nome_metrica = f"Estimado Total {ano_alvo}"
    for m_norm, m_orig in MESES_NORM_MAP.items():
        if re.search(rf"\b{m_norm}\b", q_norm) and f"Estimado {m_orig}" in df_alvo.columns:
            col_metrica = f"Estimado {m_orig}"
            nome_metrica = f"Estimado {m_orig}/{ano_alvo}"
            break

    if col_metrica == "_val_total":
        if ano_alvo == 2026 and "indicado" in q_norm:
            col_metrica = "_val_indicado"
            nome_metrica = "Valor Indicado 2026"
        elif ano_alvo == 2026 and ("restante" in q_norm or "saldo" in q_norm):
            col_metrica = "_val_restante"
            nome_metrica = "Saldo Restante 2026"
        elif ano_alvo == 2027 and "inicial" in q_norm:
            col_metrica = "_val_inicial"
            nome_metrica = "Estimado Inicial 2027"
        elif "global" in q_norm:
            col_metrica = "_val_global"
            nome_metrica = "Valor Global do Contrato"

    if is_menor:
        df_alvo = df_alvo[df_alvo[col_metrica] > 0].copy()

    if df_alvo.empty:
        return f"Nenhuma despesa encontrada para {ano_alvo}{lbl_grupo}."

    # Se perguntou "qual unidade tem maior/menor..."
    if any(p in q_norm for p in ["qual unidade", "quais unidades", "unidade tem", "unidade com", "por unidade"]):
        por_u = (
            df_alvo.groupby("Unidade", as_index=False)
            .agg(Qtd=("Item", "count"), Valor=(col_metrica, "sum"))
            .sort_values("Valor", ascending=is_menor)
        )
        u1 = por_u.iloc[0]
        tot_g = float(df_alvo[col_metrica].sum())
        p1 = (float(u1["Valor"]) / tot_g * 100) if tot_g > 0 else 0.0
        linhas = [
            f"### 🏢 Unidade com {lbl_ord} {nome_metrica}{lbl_grupo}",
            f"🏆 **1º Lugar:** **{u1['Unidade']}** com **`{fmt_brl(u1['Valor'])}`** (`{p1:.1f}%` do total de `{fmt_brl(tot_g)}`, em `{int(u1['Qtd'])}` despesas)\n",
            f"| # | Unidade | Qtd Despesas | {nome_metrica} | % do Total |",
            "|---|---|---|---|---|",
        ]
        for idx, (_, r) in enumerate(por_u.iterrows(), 1):
            p = (float(r["Valor"]) / tot_g * 100) if tot_g > 0 else 0.0
            linhas.append(f"| {idx}º | **{r['Unidade']}** | {int(r['Qtd'])} | **`{fmt_brl(r['Valor'])}`** | `{p:.1f}%` |")
        return "\n".join(linhas)

    sub = df_alvo.sort_values(col_metrica, ascending=is_menor)
    top1 = sub.iloc[0]
    it1 = int(top1["Item"]) if pd.notna(top1.get("Item")) and str(top1.get("Item")).replace(".0", "").isdigit() else top1.get("Item", "-")
    tot_geral = float(df_alvo[col_metrica].sum())
    pct1 = (float(top1[col_metrica]) / tot_geral * 100) if tot_geral > 0 else 0.0

    linhas = [
        f"### 🏆 Despesa com {lbl_ord} {nome_metrica}{lbl_grupo}",
        f"* **1º Lugar Individual:** **Item {it1} — {top1.get('Resumo', top1.get('Objeto', '-'))}** (*Unidade: {top1.get('Unidade', '-')}*)",
        f"  * **{nome_metrica}:** **`{fmt_brl(top1[col_metrica])}`** (`{pct1:.1f}%` do total de `{fmt_brl(tot_geral)}`)",
    ]
    if ano_alvo == 2027:
        linhas.append(f"  * **Detalhamento 2027:** Inicial: `{fmt_brl(top1['_val_inicial'])}` | Déficit: `{fmt_brl(top1['_val_deficit'])}` | Total: `{fmt_brl(top1['_val_total'])}`")
    else:
        linhas.append(f"  * **Detalhamento 2026:** Estimado: `{fmt_brl(top1['_val_total'])}` | Indicado: `{fmt_brl(top1['_val_indicado'])}` | Restante: `{fmt_brl(top1['_val_restante'])}`")
    linhas.append(f"  * **Contrato:** `{top1.get('Nº do Contrato (se houver)', '-')}` | **Empresa:** `{top1.get('Empresa Contratada', '-')}`\n")

    linhas.append(f"#### 🔝 Top 10 Despesas por {lbl_ord} {nome_metrica}{lbl_grupo}:")
    if ano_alvo == 2027:
        linhas.append("| # | Item | Despesa (Resumo) | Unidade | Inicial 2027 | Déficit 2027 | Total 2027 |")
        linhas.append("|---|---|---|---|---|---|---|")
        for idx, (_, r) in enumerate(sub.head(10).iterrows(), 1):
            it_n = int(r["Item"]) if pd.notna(r.get("Item")) and str(r.get("Item")).replace(".0", "").isdigit() else r.get("Item", "-")
            linhas.append(
                f"| {idx}º | {it_n} | **{r.get('Resumo', r.get('Objeto', '-'))}** | {r.get('Unidade', '-')} | "
                f"`{fmt_brl(r['_val_inicial'])}` | `{fmt_brl(r['_val_deficit'])}` | **`{fmt_brl(r['_val_total'])}`** |"
            )
    else:
        linhas.append("| # | Item | Despesa (Resumo) | Unidade | Estimado 2026 | Valor Indicado | Saldo Restante |")
        linhas.append("|---|---|---|---|---|---|---|")
        for idx, (_, r) in enumerate(sub.head(10).iterrows(), 1):
            it_n = int(r["Item"]) if pd.notna(r.get("Item")) and str(r.get("Item")).replace(".0", "").isdigit() else r.get("Item", "-")
            linhas.append(
                f"| {idx}º | {it_n} | **{r.get('Resumo', r.get('Objeto', '-'))}** | {r.get('Unidade', '-')} | "
                f"**`{fmt_brl(r['_val_total'])}`** | `{fmt_brl(r['_val_indicado'])}` | `{fmt_brl(r['_val_restante'])}` |"
            )

    return "\n".join(linhas)


def _build_panorama_geral(kb: dict[str, Any]) -> str:
    """Gera um panorama executivo completo consolidando todas as 5 bases de dados."""
    df26 = kb["df26"]
    df27 = kb["df27"]
    df_sup = kb["df_sup"]
    df_pca = kb["df_pca"]
    df_liq = kb["df_liq"]

    tot26 = float(df26["_val_total"].sum()) if not df26.empty else 0.0
    ind26 = float(df26["_val_indicado"].sum()) if not df26.empty else 0.0
    rest26 = float(df26["_val_restante"].sum()) if not df26.empty else 0.0
    pct26 = (ind26 / tot26 * 100) if tot26 > 0 else 0.0

    liq26 = float(df_liq["Valor_Liquidado_Saldo"].sum()) if not df_liq.empty else 0.0

    ini27 = float(df27["_val_inicial"].sum()) if not df27.empty else 0.0
    def27 = float(df27["_val_deficit"].sum()) if not df27.empty else 0.0
    tot27 = float(df27["_val_total"].sum()) if not df27.empty else 0.0
    cota27 = kb["cota_2027"]

    sup_econ = float(df_sup["Economia Gerada"].sum()) if not df_sup.empty else 0.0
    sup_teto = float(df_sup["Teto Ajustado 2027"].sum()) if not df_sup.empty else 0.0

    pca_geof = df_pca[df_pca["Unidade_Orcamentaria"] == "GEOF"] if not df_pca.empty else pd.DataFrame()
    pca_tes = df_pca[df_pca["Unidade_Orcamentaria"] == "Tesouro"] if not df_pca.empty else pd.DataFrame()
    m_novas = df_pca["Providencia_2027"].astype(str).str.upper().str.contains("NOVA", na=False) if not df_pca.empty else pd.Series(dtype=bool)
    m_prorr = df_pca["Providencia_2027"].astype(str).str.upper().str.contains("PRORROG", na=False) if not df_pca.empty else pd.Series(dtype=bool)
    val_contr_geof = float(pca_geof["Valor_Contratado"].sum()) if not pca_geof.empty else 0.0
    val_contr_tes = float(pca_tes["Valor_Contratado"].sum()) if not pca_tes.empty else 0.0
    val_contr_all = float(df_pca["Valor_Contratado"].sum()) if not df_pca.empty else 0.0

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
* **Total Geral de Demandas Mapeadas:** `{len(df_pca)}` demandas (`{int(m_novas.sum())}` novas contratações e `{int(m_prorr.sum())}` prorrogações) | **Valor Contratado Vigente:** `{fmt_brl(val_contr_all)}`
* **Unidade Orçamentária GEOF (Padrão):** `{len(pca_geof)}` demandas (Valor Contratado Vigente: `{fmt_brl(val_contr_geof)}`)
* **Unidade Orçamentária Tesouro:** `{len(pca_tes)}` demandas (Valor Contratado Vigente: `{fmt_brl(val_contr_tes)}`)"""


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

    df_pca = kb["df_pca"]
    if not df_pca.empty:
        mpca = df_pca["_search_blob"].str.contains(re.escape(termo.lower()), na=False)
        if mpca.any():
            encontrou = True
            sub = df_pca[mpca]
            partes.append(f"#### 📑 PCA 2027 (GELC) — {len(sub)} demanda(s)")
            for _, r in sub.head(8).iterrows():
                dt_set = r["Data_Inicio_SETRAC"].strftime("%d/%m/%Y") if pd.notna(r.get("Data_Inicio_SETRAC")) else "N/D"
                dt_enc = r["Data_Encaminhamento_Contratos"].strftime("%d/%m/%Y") if pd.notna(r.get("Data_Encaminhamento_Contratos")) else "N/D"
                dt_dead = r["Deadline_Contratacao"].strftime("%d/%m/%Y") if pd.notna(r.get("Deadline_Contratacao")) else "N/D"
                partes.append(
                    f"* **Item {r.get('Item', '-')} — {r.get('Objeto_Resumido', '-')}** ({r.get('Unidade_Superior', '-')} · {r.get('Unidade_Demandante', '-')})\n"
                    f"  * Valor Contratado Vigente: `{fmt_brl(r.get('Valor_Contratado', 0.0))}` | Providência: `{r.get('Providencia_2027', '-')}` | Modalidade: `{r.get('Modalidade', '-')}`\n"
                    f"  * Início SETRAC: `{dt_set}` | Encam. Contratos: `{dt_enc}` | Deadline: `{dt_dead}` | UO: `{r.get('Unidade_Orcamentaria', '-')}`"
                )

    if not encontrou:
        return f"Não encontrei nenhum registro com o {tipo_id} **`{termo}`** nas bases de 2026, SIAFIC, PLOA 2027, Supressões ou PCA 2027."

    return "\n\n".join(partes)


def _answer_pca_specific(q_norm: str, kb: dict[str, Any]) -> str:
    """Responde perguntas focadas no PCA 2027 (cronograma, prazos, riscos, GEOF/Tesouro e Valor Contratado)."""
    df_pca = kb["df_pca"].copy()
    if df_pca.empty:
        return "A base do PCA 2027 está vazia no momento."

    hoje = datetime.now()
    ano_at, mes_at = hoje.year, hoje.month
    ano_px, mes_px = (ano_at + 1, 1) if mes_at == 12 else (ano_at, mes_at + 1)

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
            f"* **Processos com Marco no Mês Corrente ({MESES_ABREV[mes_at]}/{ano_at}):** `{int(m_atual.sum())}` demandas",
            f"* **Processos com Prazos Já Vencidos (< {hoje:%d/%m/%Y}):** `{int(m_venc.sum())}` demandas",
            f"* **Processos para o Próximo Mês ({MESES_ABREV[mes_px]}/{ano_px}):** `{int(m_prox.sum())}` demandas\n",
        ]

        if not sub_alerta.empty:
            linhas.append("#### ⚡ Relação de Processos em Atenção Imediata (Vencidos + Mês Corrente):")
            linhas.append("| Item | Objeto Resumido | Superintendência | Providência 2027 | Início SETRAC | Encam. Contratos | Deadline | Valor Contratado |")
            linhas.append("|---|---|---|---|---|---|---|---|")
            for _, r in sub_alerta.sort_values("Deadline_Contratacao", ascending=True, na_position="last").iterrows():
                d1 = r["Data_Inicio_SETRAC"].strftime("%d/%m/%Y") if pd.notna(r["Data_Inicio_SETRAC"]) else "-"
                d2 = r["Data_Encaminhamento_Contratos"].strftime("%d/%m/%Y") if pd.notna(r["Data_Encaminhamento_Contratos"]) else "-"
                d3 = r["Deadline_Contratacao"].strftime("%d/%m/%Y") if pd.notna(r["Deadline_Contratacao"]) else "-"
                it_n = int(r["Item"]) if pd.notna(r["Item"]) else "-"
                linhas.append(
                    f"| {it_n} | **{r['Objeto_Resumido']}** | {r['Unidade_Superior']} | {r['Providencia_2027']} | `{d1}` | `{d2}` | `{d3}` | `{fmt_brl(r.get('Valor_Contratado', 0.0))}` |"
                )
        return "\n".join(linhas)

    df_geof = df_pca[df_pca["Unidade_Orcamentaria"] == "GEOF"]
    df_tes = df_pca[df_pca["Unidade_Orcamentaria"] == "Tesouro"]

    alvo = df_pca if ("tod" in q_norm or "tesouro" in q_norm) else df_geof
    lbl_alvo = "Consolidado Geral (GEOF + Tesouro)" if len(alvo) == len(df_pca) else f"Padrão GEOF ({len(df_geof)} demandas)"

    m_novas = alvo["Providencia_2027"].astype(str).str.upper().str.contains("NOVA", na=False)
    m_prorr = alvo["Providencia_2027"].astype(str).str.upper().str.contains("PRORROG", na=False)
    m_sem = alvo["Providencia_2027"].astype(str).str.upper().str.contains("SEM PROVID", na=False)

    alvo_c = alvo.copy()
    alvo_c["_is_nova"] = m_novas.astype(int)
    alvo_c["_is_prorr"] = m_prorr.astype(int)
    por_sup = (
        alvo_c.groupby("Unidade_Superior", as_index=False)
        .agg(Qtd=("Objeto_Resumido", "count"), Novas=("_is_nova", "sum"), Prorr=("_is_prorr", "sum"), ValContr=("Valor_Contratado", "sum"))
        .sort_values("Qtd", ascending=False)
    )

    linhas = [
        f"### 📑 Resumo de Gestão & Cronograma — PCA 2027 ({lbl_alvo})",
        f"* **Total de Demandas Analisadas:** `{len(alvo)}` processos (Valor Contratado Vigente: `{fmt_brl(alvo['Valor_Contratado'].sum())}`)",
        f"* **Novas Contratações:** `{int(m_novas.sum())}` processos",
        f"* **Prorrogações:** `{int(m_prorr.sum())}` aditivos (Valor Contratado Vigente: `{fmt_brl(alvo[m_prorr]['Valor_Contratado'].sum())}`)",
        f"* **Sem Providências (Vigência Normal):** `{int(m_sem.sum())}` contratos (Valor Contratado Vigente: `{fmt_brl(alvo[m_sem]['Valor_Contratado'].sum())}`)",
        f"* *(Distribuição por UO: **GEOF** = `{len(df_geof)}` itens | **Tesouro** = `{len(df_tes)}` itens)*\n",
        "#### 🏢 Distribuição de Demandas por Superintendência / Unidade Superior:",
        "| Superintendência / Unidade Superior | Total de Demandas | Novas Contratações | Prorrogações | Valor Contratado Vigente |",
        "|---|---|---|---|---|",
    ]
    for _, r in por_sup.iterrows():
        linhas.append(f"| **{r['Unidade_Superior']}** | `{int(r['Qtd'])}` | `{int(r['Novas'])}` | `{int(r['Prorr'])}` | `{fmt_brl(r['ValContr'])}` |")

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
        m_n = sub_pca["Providencia_2027"].astype(str).str.upper().str.contains("NOVA", na=False)
        m_p = sub_pca["Providencia_2027"].astype(str).str.upper().str.contains("PRORROG", na=False)
        linhas.append("#### 4️⃣ PCA 2027 — Contratações GELC")
        linhas.append(
            f"* **Total de Demandas no PCA 2027:** `{len(sub_pca)}` processos (`{int(m_n.sum())}` novas contratações | `{int(m_p.sum())}` prorrogações) | "
            f"**Valor Contratado Vigente:** `{fmt_brl(sub_pca['Valor_Contratado'].sum())}`"
        )
        top_pca = sub_pca.sort_values("Deadline_Contratacao", ascending=True, na_position="last").head(10)
        linhas.append("| Item | Objeto Resumido | Gerência Demandante | Providência 2027 | Valor Contratado | Deadline |")
        linhas.append("|---|---|---|---|---|---|")
        for _, r in top_pca.iterrows():
            it_n = int(r["Item"]) if pd.notna(r["Item"]) else "-"
            dt_d = r["Deadline_Contratacao"].strftime("%d/%m/%Y") if pd.notna(r.get("Deadline_Contratacao")) else "N/D"
            linhas.append(
                f"| {it_n} | **{r['Objeto_Resumido']}** | {r['Unidade_Demandante']} | {r['Providencia_2027']} | `{fmt_brl(r.get('Valor_Contratado', 0.0))}` | `{dt_d}` |"
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
    if "deficit" in q_norm:
        return _answer_deficit_analysis(q_norm, kb)

    df26 = kb["df26"]
    df27 = kb["df27"]

    so_2026 = "2026" in q_norm and "2027" not in q_norm
    so_2027 = ("2027" in q_norm or "ploa" in q_norm) and "2026" not in q_norm

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


def _extract_search_tokens(q_norm: str) -> list[str]:
    """Extrai tokens significativos da pergunta, preservando siglas de 2 letras (ex: TI, RH, AR) e removendo stopwords."""
    raw_toks = re.findall(r"[a-z0-9]{2,}", q_norm)
    tokens = [
        t for t in raw_toks
        if t not in STOPWORDS_PT and (len(t) >= 3 or t in SHORT_SIGNIFICANT_TOKENS)
    ]
    return tokens


# Mapa de expansão semântica de sinônimos do domínio orçamentário para capturar 100% dos itens relacionados
TOPIC_SYNONYM_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("veiculo", "veiculos", "frota", "carro", "carros", "caminhonete", "pickup"), r"\b(?:veicul|frota|pickup|motorista)"),
    (("aluguel", "alugueis", "imovel", "imoveis", "locacao de imovel"), r"\b(?:locacao de imovel|imovel|imoveis)"),
    (("energia", "eletrica", "luz", "equatorial", "enel", "celg"), r"\b(?:energia eletrica|energia|equatorial|enel|fotovoltaic)"),
    (("agua", "esgoto", "saneago"), r"\b(?:agua|esgoto|saneago)"),
    (("limpeza", "conservacao", "higienizacao", "copeiragem", "jardinagem"), r"\b(?:limpeza|conservacao|jardinagem)"),
    (("vigilancia", "seguranca", "armada", "monitoramento", "alarme", "cftv"), r"\b(?:vigilancia|monitoramento eletronico)"),
    (("link", "telecom", "telecomunicacoes", "fibra", "internet", "telefonia", "ddg", "0800"), r"\b(?:link de dados|telecomunicac|fibra|telefonia|ddg|0800)"),
    (("combustivel", "combustiveis", "gasolina", "diesel", "etanol", "abastecimento", "lubrificante"), r"\b(?:combustive|lubrificante|abastecimento)"),
    (("cafe", "acucar", "copa", "alimentacao", "garrafao"), r"\b(?:cafe|acucar|alimentacao)"),
    (("diaria", "diarias", "passagem", "passagens", "viagem", "viagens", "deslocamento", "deslocamentos", "hospedagem"), r"\b(?:diaria|deslocamento|passagen|viagen|hospedagen)"),
    (("correio", "correios", "postagem", "malote", "ect"), r"\b(?:correio|postagen|malote|ect)"),
    (("treinamento", "treinamentos", "capacitacao", "capacitacoes", "curso", "cursos"), r"\b(?:capacitac|curso|treinamento)"),
    (("ar condicionado", "climatizacao", "refrigeracao"), r"\b(?:ar condicionado|climatizac)"),
]


def _search_keyword_across_all(q_raw: str, q_norm: str, kb: dict[str, Any]) -> str:
    """Pesquisa semântica por palavras-chave simultaneamente nas 5 bases de dados com desambiguação e busca compacta."""
    tokens = _extract_search_tokens(q_norm)
    if not tokens:
        return _build_panorama_geral(kb)

    asks_obras = any(t in ("obra", "obras", "reforma", "reformas", "engenharia") for t in tokens) and "mao" not in q_norm
    compact_tokens = [_compact_text(t) for t in tokens if _compact_text(t)]
    full_compact_query = "".join(compact_tokens)

    # Verifica se algum padrão de sinônimo temático se aplica (apenas quando não há nome específico de empresa/contrato)
    synonym_regex: str | None = None
    if len(tokens) <= 2:
        for trigger_words, pat in TOPIC_SYNONYM_PATTERNS:
            if any(t in trigger_words for t in tokens) or any(tw in q_norm for tw in trigger_words if " " in tw):
                synonym_regex = pat
                break

    def match_df(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "_search_blob" not in df.columns:
            return pd.DataFrame()
        has_compact = "_search_blob_compact" in df.columns

        # 1. Tratamento especializado para "obras" ou "reformas" (evitando colisão com "Mão de Obra" e "Cobrança")
        if asks_obras:
            blob_sem_mao = df["_search_blob"].str.replace("mao de obra", "", regex=False)
            m_ob = blob_sem_mao.str.contains(r"\b(?:obra|obras|reforma|reformas)\b", regex=True, na=False)
            outros_toks = [t for t in tokens if t not in ("obra", "obras", "reforma", "reformas", "engenharia")]
            for ot in outros_toks:
                m_ob &= blob_sem_mao.str.contains(rf"\b{re.escape(ot)}", regex=True, na=False)
            if m_ob.any():
                return df[m_ob]

        # 2. Busca exata por fronteira de palavra OU versão compacta sem espaços (ex: BRFIBRA == BR FIBRA)
        mask_all = pd.Series(True, index=df.index)
        for t, ct in zip(tokens, compact_tokens):
            m_word = df["_search_blob"].str.contains(rf"\b{re.escape(t)}", regex=True, na=False)
            if has_compact and len(ct) >= 4:
                m_word = m_word | df["_search_blob_compact"].str.contains(re.escape(ct), na=False)
            mask_all &= m_word
        if mask_all.any():
            return df[mask_all]

        # 3. Se o usuário digitou separado o que na planilha está junto (ex: "br fibra" vs "brfibra")
        if has_compact and len(full_compact_query) >= 5:
            m_comp = df["_search_blob_compact"].str.contains(re.escape(full_compact_query), na=False)
            if m_comp.any():
                return df[m_comp]

        # 4. Expansão de sinônimos de domínio (ex: "carros" -> Frota Veicular, "luz" -> Energia Elétrica)
        if synonym_regex:
            m_syn = df["_search_blob"].str.contains(synonym_regex, regex=True, na=False)
            if m_syn.any():
                return df[m_syn]

        # 5. Substring direta para todos os tokens
        mask_sub = pd.Series(True, index=df.index)
        for t in tokens:
            mask_sub &= df["_search_blob"].str.contains(re.escape(t), na=False)
        if mask_sub.any():
            return df[mask_sub]

        # 6. Melhor pontuação por palavra inteira (somente para tokens >= 4 caracteres para evitar falso positivo)
        scores = pd.Series(0, index=df.index)
        for t, ct in zip(tokens, compact_tokens):
            if len(t) >= 4 or t in SHORT_SIGNIFICANT_TOKENS:
                m_w = df["_search_blob"].str.contains(rf"\b{re.escape(t)}", regex=True, na=False)
                if has_compact and len(ct) >= 5:
                    m_w = m_w | df["_search_blob_compact"].str.contains(re.escape(ct), na=False)
                scores += m_w.astype(int)
        best_max = scores.max()
        if best_max > 0:
            return df[scores == best_max]
        return pd.DataFrame()

    m26 = match_df(kb["df26"])
    m27 = match_df(kb["df27"])
    msup = match_df(kb["df_sup"])
    mpca = match_df(kb["df_pca"])
    mliq = match_df(kb["df_liq"])

    # Fallback inteligente: se não encontrou nos ativos, verifica se existe em PROFISCO=Sim, Rascunho ou Inativo
    aviso_inativo = ""
    if m26.empty and m27.empty and "df26_all" in kb and "df27_all" in kb:
        m26_all = match_df(kb["df26_all"])
        m27_all = match_df(kb["df27_all"])
        if not m26_all.empty or not m27_all.empty:
            m26 = m26_all
            m27 = m27_all
            aviso_inativo = (
                "\n> ⚠️ **Nota de Auditoria:** Os itens abaixo constam na planilha com status fora do filtro padrão ativo "
                "(ex: `PROFISCO = Sim`, `Situação IPOF = Rascunho` ou `Situação = Excluído`).\n"
            )

    if m26.empty and m27.empty and msup.empty and mpca.empty and mliq.empty:
        return (
            f"Não encontrei registros específicos para **`{q_raw}`** nas planilhas.\n\n"
            "💡 **Dica:** Você pode perguntar por:\n"
            "* **Empresas e Contratos:** *BRFIBRA, Sampa, Office, Microsoft, Equatorial, Saneago, 054/2025*\n"
            "* **Rankings e Extremos:** *Qual despesa tem o maior déficit para 2027? Qual o maior corte nas supressões?*\n"
            "* **Temas/Objetos:** *obras, reformas, vigilância, limpeza, locação de veículos, link de dados, call center, Pix*\n"
            "* **Unidades:** *STI, SGI, Receita Estadual, SFR, SIF, Tesouro, Gabinete*"
        )

    termo_exib = ", ".join(tokens)
    partes = [f"### 🔮 Resultados do Oráculo para: `{termo_exib}`"]
    if aviso_inativo:
        partes.append(aviso_inativo)

    # Sumário imediato de Contratos, Empresas e Processos SEI encontrados
    contratos_set: list[str] = []
    empresas_set: list[str] = []
    sei_set: list[str] = []
    for df_m, c_cont, c_emp, c_sei in [
        (m26, "Nº do Contrato (se houver)", "Empresa Contratada", "Nº Processo (se houver)"),
        (m27, "Nº do Contrato (se houver)", "Empresa Contratada", "Nº Processo (se houver)"),
        (mpca, "Contrato_Vigente", None, "Processo_SEI"),
        (mliq, None, "Beneficiario_Nome", "Processo_SEI"),
    ]:
        if not df_m.empty and len(df_m) <= 15:
            if c_cont and c_cont in df_m.columns:
                for v in df_m[c_cont].dropna():
                    s = str(v).strip()
                    if s and s.lower() not in ("nan", "none", "-", "(sem contrato)") and s not in contratos_set:
                        contratos_set.append(s)
            if c_emp and c_emp in df_m.columns:
                for v in df_m[c_emp].dropna():
                    s = str(v).strip()
                    if s and s.lower() not in ("nan", "none", "-") and s not in empresas_set:
                        empresas_set.append(s)
            if c_sei and c_sei in df_m.columns:
                for v in df_m[c_sei].dropna():
                    for num_s in re.findall(r"\b\d{10,16}\b", str(v)):
                        if num_s not in sei_set:
                            sei_set.append(num_s)

    if contratos_set or empresas_set or sei_set:
        resumo_ids = ["#### 📌 Identificação Rápida (Contratos, Empresas & Processos SEI):"]
        if contratos_set:
            resumo_ids.append(f"* **Nº do(s) Contrato(s):** `{', '.join(contratos_set[:10])}` ({len(contratos_set)} identificado(s))")
        if empresas_set:
            resumo_ids.append(f"* **Empresa(s) / Credor(es):** {', '.join(f'**{e}**' for e in empresas_set[:6])}")
        if sei_set:
            resumo_ids.append(f"* **Processo(s) SEI:** `{', '.join(sei_set[:8])}`")
        partes.append("\n".join(resumo_ids))

    if not m27.empty:
        tot_27 = float(m27["_val_total"].sum())
        ini_27 = float(m27["_val_inicial"].sum())
        def_27 = float(m27["_val_deficit"].sum())
        partes.append(
            f"#### 📅 Planejamento PLOA 2027 — `{len(m27)}` despesa(s) | **Total Planejado 2027: `{fmt_brl(tot_27)}`** (Inicial: `{fmt_brl(ini_27)}` | Déficit: `{fmt_brl(def_27)}`)"
        )
        if asks_obras:
            m_ref = m27["Resumo"].astype(str).str.contains("Reforma|Obra", case=False, na=False)
            if m_ref.any() and int(m_ref.sum()) < len(m27):
                partes.append(
                    f"* 🏗️ **Subtotal exclusivo de Reformas / Obras Prediais ({int(m_ref.sum())} itens, incluindo Reforma do Complexo e DRFs):** **`{fmt_brl(m27[m_ref]['_val_total'].sum())}`**\n"
                    f"* 🏛️ **Total Geral da Classificação 'Obras e Instalações' ({len(m27)} itens):** **`{fmt_brl(tot_27)}`**"
                )
        elif "Classificação do Objeto" in m27.columns and m27["Classificação do Objeto"].nunique() > 1:
            por_cls27 = (
                m27.groupby("Classificação do Objeto", as_index=False)
                .agg(Qtd=("Item", "count"), Ini=("_val_inicial", "sum"), Def=("_val_deficit", "sum"), Tot=("_val_total", "sum"))
                .sort_values("Tot", ascending=False)
            )
            sub_cls_lines = ["* **Subtotais por Classificação do Objeto (2027):**"]
            for _, rc in por_cls27.iterrows():
                sub_cls_lines.append(
                    f"  * **{rc['Classificação do Objeto']}** ({int(rc['Qtd'])} itens): **`{fmt_brl(rc['Tot'])}`** (Inicial: `{fmt_brl(rc['Ini'])}` | Déficit: `{fmt_brl(rc['Def'])}`)"
                )
            partes.append("\n".join(sub_cls_lines))

        linhas_t27 = [
            "| Item | Despesa (Resumo) | Empresa Contratada | Contrato | Processo SEI | Classificação | Unidade | Inicial 2027 | Déficit 2027 | Total 2027 |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for _, r in m27.sort_values("_val_total", ascending=False).head(30).iterrows():
            it_n = int(r["Item"]) if pd.notna(r.get("Item")) and str(r.get("Item")).replace(".0", "").isdigit() else r.get("Item", "-")
            linhas_t27.append(
                f"| {it_n} | **{r.get('Resumo', '-')}** | {r.get('Empresa Contratada', '-')} | `{r.get('Nº do Contrato (se houver)', '-')}` | "
                f"`{r.get('Nº Processo (se houver)', '-')}` | {r.get('Classificação do Objeto', '-')} | "
                f"{r.get('Unidade', '-')} | `{fmt_brl(r['_val_inicial'])}` | `{fmt_brl(r['_val_deficit'])}` | **`{fmt_brl(r['_val_total'])}`** |"
            )
        partes.append("\n".join(linhas_t27))

    if not m26.empty:
        partes.append(
            f"#### 🏢 Orçamento 2026 (Execução) — `{len(m26)}` despesa(s) | **Total Estimado 2026: `{fmt_brl(m26['_val_total'].sum())}`** (Indicado: `{fmt_brl(m26['_val_indicado'].sum())}` | Restante: `{fmt_brl(m26['_val_restante'].sum())}`)"
        )
        linhas_t26 = [
            "| Item | Despesa (Resumo) | Empresa Contratada | Contrato | Processo SEI | Unidade | Estimado 2026 | Valor Indicado | Saldo Restante |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for _, r in m26.sort_values("_val_total", ascending=False).head(25).iterrows():
            it_n = int(r["Item"]) if pd.notna(r.get("Item")) and str(r.get("Item")).replace(".0", "").isdigit() else r.get("Item", "-")
            linhas_t26.append(
                f"| {it_n} | **{r.get('Resumo', r.get('Objeto', '-'))}** | {r.get('Empresa Contratada', '-')} | "
                f"`{r.get('Nº do Contrato (se houver)', '-')}` | `{r.get('Nº Processo (se houver)', '-')}` | {r.get('Unidade', '-')} | "
                f"**`{fmt_brl(r['_val_total'])}`** | `{fmt_brl(r['_val_indicado'])}` | `{fmt_brl(r['_val_restante'])}` |"
            )
        partes.append("\n".join(linhas_t26))

    if not msup.empty:
        partes.append(
            f"#### ✂️ Supressões PLOA 2027 — `{len(msup)}` item(ns) | Economia Gerada: `{fmt_brl(msup['Economia Gerada'].sum())}`"
        )
        for _, r in msup.head(15).iterrows():
            partes.append(
                f"* **{r['Item de Despesa']}** ({r['Unidade']}) — Orçamento: `{fmt_brl(r['Orçamento 2027'])}` ➔ "
                f"Corte: `{fmt_brl(r['Economia Gerada'])}` ➔ Novo Teto: `{fmt_brl(r['Teto Ajustado 2027'])}` (*{r['Ação Sugerida']}*)"
            )

    if not mpca.empty:
        partes.append(
            f"#### 📑 PCA 2027 (GELC · Cronograma & Contratações) — `{len(mpca)}` demanda(s) | Valor Contratado Vigente: `{fmt_brl(mpca['Valor_Contratado'].sum())}`"
        )
        linhas_tpca = [
            "| Item | Objeto Resumido | Contrato Vigente | Processo SEI | Superintendência / Gerência | Valor Contratado Vigente | Providência 2027 | Deadline | UO |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for _, r in mpca.head(20).iterrows():
            it_n = int(r["Item"]) if pd.notna(r["Item"]) else "-"
            dt_d = r["Deadline_Contratacao"].strftime("%d/%m/%Y") if pd.notna(r.get("Deadline_Contratacao")) else "N/D"
            linhas_tpca.append(
                f"| {it_n} | **{r['Objeto_Resumido']}** | `{r.get('Contrato_Vigente', '-')}` | `{r.get('Processo_SEI', '-')}` | "
                f"{r['Unidade_Superior']} · {r['Unidade_Demandante']} | `{fmt_brl(r.get('Valor_Contratado', 0.0))}` | "
                f"{r['Providencia_2027']} | `{dt_d}` | `{r['Unidade_Orcamentaria']}` |"
            )
        partes.append("\n".join(linhas_tpca))

    if not mliq.empty:
        partes.append(
            f"#### 📜 Liquidação SIAFIC 2026 (SAP BO) — `{len(mliq)}` lançamento(s) | Total Liquidado: `{fmt_brl(mliq['Valor_Liquidado_Saldo'].sum())}`"
        )
        por_b = (
            mliq.groupby(["Beneficiario_Nome", "Processo_SEI"], as_index=False)["Valor_Liquidado_Saldo"]
            .sum()
            .sort_values("Valor_Liquidado_Saldo", ascending=False)
            .head(10)
        )
        for _, r in por_b.iterrows():
            partes.append(f"* **Credor:** {r['Beneficiario_Nome']} (SEI `{r['Processo_SEI']}`) — Liquidado em 2026: `{fmt_brl(r['Valor_Liquidado_Saldo'])}`")

    return "\n\n".join(partes)


def _build_global_master_digest(kb: dict[str, Any]) -> str:
    """Constrói um resumo executivo denso e enxuto de todas as 5 planilhas (incluindo todas as Classificações de Objeto) para o LLM."""
    df26 = kb["df26"]
    df27 = kb["df27"]
    df_sup = kb["df_sup"]
    df_pca = kb["df_pca"]
    df_liq = kb["df_liq"]

    partes = ["=== CONTEXTO OFICIAL DAS 5 BASES (SECRETARIA DA ECONOMIA - GO) ==="]

    if not df26.empty:
        tot26 = float(df26["_val_total"].sum())
        ind26 = float(df26["_val_indicado"].sum())
        rest26 = float(df26["_val_restante"].sum())
        u26_str = "; ".join(
            f"{r['Unidade']}: Est={fmt_brl(r['_val_total'])}, Ind={fmt_brl(r['_val_indicado'])}"
            for _, r in df26.groupby("Unidade", as_index=False)[["_val_total", "_val_indicado"]].sum().sort_values("_val_total", ascending=False).iterrows()
        )
        cls26_str = "; ".join(
            f"{r['Classificação do Objeto']} ({int(r['Qtd'])}): {fmt_brl(r['Tot'])}"
            for _, r in df26.groupby("Classificação do Objeto", as_index=False).agg(Qtd=("Item", "count"), Tot=("_val_total", "sum")).sort_values("Tot", ascending=False).iterrows()
        ) if "Classificação do Objeto" in df26.columns else ""
        top26_str = "\n".join(
            f"  - Item {r.get('Item')}: {r.get('Resumo')} ({r.get('Unidade')}) | Contrato={r.get('Nº do Contrato (se houver)')} | Empresa={r.get('Empresa Contratada')} | Est.26={fmt_brl(r['_val_total'])} | Ind={fmt_brl(r['_val_indicado'])}"
            for _, r in df26.sort_values("_val_total", ascending=False).head(10).iterrows()
        )
        partes.append(
            f"[1. EXECUÇÃO 2026] Total={fmt_brl(tot26)} ({len(df26)} itens) | Indicado={fmt_brl(ind26)} | Restante={fmt_brl(rest26)} | Cota={fmt_brl(kb['cota_2026'])}\n"
            f"Unidades 2026: {u26_str}\nClassificações 2026: {cls26_str}\nTop 10 Despesas 2026:\n{top26_str}"
        )

    if not df27.empty:
        ini27 = float(df27["_val_inicial"].sum())
        def27 = float(df27["_val_deficit"].sum())
        tot27 = float(df27["_val_total"].sum())
        u27_str = "; ".join(
            f"{r['Unidade']}: Ini={fmt_brl(r['_val_inicial'])}, Déf={fmt_brl(r['_val_deficit'])}, Tot={fmt_brl(r['_val_total'])}"
            for _, r in df27.groupby("Unidade", as_index=False)[["_val_inicial", "_val_deficit", "_val_total"]].sum().sort_values("_val_total", ascending=False).iterrows()
        )
        cls27_str = "; ".join(
            f"{r['Classificação do Objeto']} ({int(r['Qtd'])}): Ini={fmt_brl(r['Ini'])}, Déf={fmt_brl(r['Def'])}, Tot={fmt_brl(r['Tot'])}"
            for _, r in df27.groupby("Classificação do Objeto", as_index=False).agg(Qtd=("Item", "count"), Ini=("_val_inicial", "sum"), Def=("_val_deficit", "sum"), Tot=("_val_total", "sum")).sort_values("Tot", ascending=False).iterrows()
        ) if "Classificação do Objeto" in df27.columns else ""
        sub_def = df27[df27["_val_deficit"] > 0].sort_values("_val_deficit", ascending=False)
        def_str = "\n".join(
            f"  - Item {r.get('Item')}: {r.get('Resumo')} ({r.get('Unidade')}) | Contrato={r.get('Nº do Contrato (se houver)')} | Ini={fmt_brl(r['_val_inicial'])} | DÉFICIT={fmt_brl(r['_val_deficit'])} | Tot={fmt_brl(r['_val_total'])}"
            for _, r in sub_def.head(15).iterrows()
        )
        top27_str = "\n".join(
            f"  - Item {r.get('Item')}: {r.get('Resumo')} ({r.get('Unidade')}) | Contrato={r.get('Nº do Contrato (se houver)')} | Ini={fmt_brl(r['_val_inicial'])} | Déf={fmt_brl(r['_val_deficit'])} | Tot={fmt_brl(r['_val_total'])}"
            for _, r in df27.sort_values("_val_total", ascending=False).head(10).iterrows()
        )
        partes.append(
            f"\n[2. PLOA 2027 (BASE OFICIAL ÚNICA PARA VALORES DE DESPESAS PLANEJADAS DE 2027)] Inicial={fmt_brl(ini27)} | Déficit={fmt_brl(def27)} ({len(sub_def)} itens) | Total={fmt_brl(tot27)} ({len(df27)} itens) | Cota={fmt_brl(kb['cota_2027'])}\n"
            f"Unidades 2027: {u27_str}\nTodas as Classificações de Objeto 2027: {cls27_str}\nTop 15 Maiores Déficits 2027:\n{def_str}\nTop 10 Maiores Despesas Totais 2027:\n{top27_str}"
        )

    if not df_sup.empty:
        sup_str = "\n".join(
            f"  - [{r['Unidade']}] {r['Item de Despesa']} | Orç={fmt_brl(r['Orçamento 2027'])} | Corte={fmt_brl(r['Economia Gerada'])} | Teto={fmt_brl(r['Teto Ajustado 2027'])} | Ação: {r['Ação Sugerida']}"
            for _, r in df_sup.sort_values("Economia Gerada", ascending=False).head(15).iterrows()
        )
        partes.append(
            f"\n[3. SUPRESSÕES PLOA 2027] Orç.Original={fmt_brl(df_sup['Orçamento 2027'].sum())} | Economia(Cortes)={fmt_brl(df_sup['Economia Gerada'].sum())} | Teto Ajustado={fmt_brl(df_sup['Teto Ajustado 2027'].sum())}\n"
            f"Top 15 Supressões:\n{sup_str}"
        )

    if not df_pca.empty:
        df_geof = df_pca[df_pca["Unidade_Orcamentaria"] == "GEOF"]
        df_tes = df_pca[df_pca["Unidade_Orcamentaria"] == "Tesouro"]
        m_n = df_pca["Providencia_2027"].astype(str).str.upper().str.contains("NOVA", na=False)
        m_p = df_pca["Providencia_2027"].astype(str).str.upper().str.contains("PRORROG", na=False)
        pca_sup_str = "; ".join(
            f"{r['Unidade_Superior']}: {int(r['Qtd'])} demandas (Val.Contratado={fmt_brl(r['ValC'])})"
            for _, r in df_pca.groupby("Unidade_Superior", as_index=False).agg(Qtd=("Objeto_Resumido", "count"), ValC=("Valor_Contratado", "sum")).sort_values("Qtd", ascending=False).iterrows()
        )
        partes.append(
            f"\n[4. PCA 2027 (GELC - CRONOGRAMA, PROCESSOS E VALOR CONTRATADO VIGENTE)] Total={len(df_pca)} demandas (Novas={int(m_n.sum())}, Prorrogações={int(m_p.sum())}) | Valor Contratado Vigente Geral={fmt_brl(df_pca['Valor_Contratado'].sum())} | GEOF={len(df_geof)} demandas (Val.Contratado={fmt_brl(df_geof['Valor_Contratado'].sum())}) | Tesouro={len(df_tes)} demandas (Val.Contratado={fmt_brl(df_tes['Valor_Contratado'].sum())})\n"
            f"Demandas por Superintendência no PCA: {pca_sup_str}"
        )

    if not df_liq.empty:
        tot_liq = float(df_liq["Valor_Liquidado_Saldo"].sum())
        mes_liq_str = "; ".join(
            f"Mês {int(r['Mes_Referencia'])}: {fmt_brl(r['Valor_Liquidado_Saldo'])}"
            for _, r in df_liq.groupby("Mes_Referencia", as_index=False)["Valor_Liquidado_Saldo"].sum().sort_values("Mes_Referencia").iterrows()
        )
        top_cred_str = "\n".join(
            f"  - {r['Beneficiario_Nome']}: {fmt_brl(r['Valor_Liquidado_Saldo'])}"
            for _, r in df_liq.groupby("Beneficiario_Nome", as_index=False)["Valor_Liquidado_Saldo"].sum().sort_values("Valor_Liquidado_Saldo", ascending=False).head(10).iterrows()
        )
        partes.append(
            f"\n[5. LIQUIDAÇÃO SIAFIC 2026] Total Liquidado={fmt_brl(tot_liq)} ({df_liq['Processo_SEI'].nunique()} processos)\n"
            f"Por Mês: {mes_liq_str}\nTop 10 Credores:\n{top_cred_str}"
        )

    return "\n".join(partes)


def _consultar_motor_deterministico(pergunta: str, kb: dict[str, Any]) -> str:
    """Executa o motor analítico determinístico em Pandas para extrair tabelas e cálculos exatos."""
    q_raw = pergunta.strip()

    id_ans = _search_by_identifier(q_raw, kb)
    if id_ans:
        return id_ans

    q_norm = normalize_and_fix_typos(q_raw, extra_vocab=kb.get("extra_vocab"))
    matched_unit = _detect_unit(q_norm)

    if "deficit" in q_norm:
        return _answer_deficit_analysis(q_norm, kb, unit_key=matched_unit)

    other_specific_tokens = [
        t for t in _extract_search_tokens(q_norm)
        if t not in DOMAIN_VOCAB
        and not any(t in u["terms"] or any(t in term.split() for term in u["terms"]) for u in UNIT_ALIASES.values())
    ]

    # Se existem termos específicos de empresa/objeto (ex: "BRFIBRA", "obras", "vigilância"), prioriza a busca multi-base detalhada!
    if other_specific_tokens:
        return _search_keyword_across_all(q_raw, q_norm, kb)

    rank_ans = _answer_ranking_or_extreme(q_norm, kb, unit_key=matched_unit)
    if rank_ans:
        return rank_ans

    if not matched_unit and any(p in q_norm for p in ["panorama", "resumo geral", "visao geral", "todos os dashboards", "todas as planilhas", "grandes numeros", "o que voce sabe"]):
        return _build_panorama_geral(kb)

    if matched_unit and any(p in q_norm for p in ["todas as planilhas", "todas as bases", "raio x", "raio-x", "geral", "resumo", "como esta", "fale sobre"]):
        return _answer_unit_360(matched_unit, kb)

    if any(k in q_norm for k in ["supressao", "supressoes", "corte", "cortes", "economia gerada", "teto ajustado"]):
        return _answer_supressoes(q_norm, kb)

    if any(k in q_norm for k in ["pca", "gelc", "setrac", "deadline", "prorrogac", "nova contratacao", "novas contratacoes", "risco", "vencid", "atrasad", "mes corrente", "mes atual"]):
        return _answer_pca_specific(q_norm, kb)

    if any(k in q_norm for k in ["liquidac", "liquidado", "siafic", "sap bo"]):
        return _answer_liquidacao(q_norm, kb)

    if matched_unit:
        return _answer_unit_360(matched_unit, kb)

    if any(k in q_norm for k in ["compar", "cota", "2026", "2027", "ploa", "execucao"]):
        return _answer_orcamento_2026_2027(q_norm, kb)

    return _search_keyword_across_all(q_raw, q_norm, kb)


def _chamar_llm_generativo(pergunta: str, analise_pandas: str, kb: dict[str, Any], historico: list[dict[str, str]] | None = None) -> str | None:
    """Aciona o modelo de IA Generativa (LLM) com todo o contexto das 5 planilhas + cálculos exatos do Pandas."""
    import os
    import requests

    master_digest = _build_global_master_digest(kb)
    system_prompt = (
        "Você é o **Oráculo** 🔮, o Assistente de Inteligência Artificial especialista em Orçamento Público, "
        "Finanças e Contratações da Secretaria de Estado da Economia de Goiás (GPIN / GELC).\n"
        "DIRETRIZES OBRIGATÓRIAS:\n"
        "1. Responda sempre em português do Brasil, de forma inteligente, analítica, executiva, clara e direta.\n"
        "2. Utilize EXCLUSIVAMENTE os números reais fornecidos no CONTEXTO OFICIAL e na ANÁLISE PANDAS abaixo. Nunca invente valores e NUNCA omita itens que constem na tabela do RECORTE ESPECÍFICO / CÁLCULO EXATO PANDAS.\n"
        "3. REGRA DE OURO SOBRE VALORES DE 2027: Para valores orçamentários previstos/planejados para 2027 (Estimado Inicial, Déficit, Estimado Total, Cortes/Supressões), utilize EXCLUSIVAMENTE a base oficial PLOA 2027 (Planejamento 2027) e Supressões PLOA 2027 (os valores de despesas estimadas futuras do PCA 2027 foram desconsiderados). Do PCA 2027 você pode informar os dados de gestão/cronograma (quantidade de demandas, objeto, superintendência/gerência, modalidade, providência 2027, datas) e o 'Valor Contratado Vigente' (Valor_Contratado dos contratos atuais).\n"
        "4. Formate todos os valores monetários no padrão brasileiro ABNT 2 (ex: R$ 17.498.729,59) e use espaços normais (nunca use caracteres unicode especiais ou espaços estreitos).\n"
        "5. Quando o usuário perguntar sobre um tema/categoria (ex: obras, reformas, vigilância) ou 'qual o maior/menor', liste TODOS os itens correspondentes presentes na ANÁLISE PANDAS em uma tabela Markdown completa sem esquecer nenhum item (por exemplo, em obras/reformas de 2027, inclua sempre a Reforma do Complexo e todas as Reformas de DRFs).\n"
        "6. Você consegue manter conversa contínua, responder perguntas de acompanhamento ('e o segundo?', 'some esses dois', 'compare com 2026', 'escreva um parecer/resumo executivo'), cruzar informações entre as 5 planilhas e tolerar erros de digitação do usuário.\n\n"
        f"{master_digest}\n\n"
        f"=== RECORTE ESPECÍFICO / CÁLCULO EXATO PANDAS PARA A PERGUNTA ATUAL ===\n{analise_pandas}"
    )

    msgs: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if historico:
        for m in historico[-6:]:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                msgs.append({"role": m["role"], "content": str(m["content"])[:2500]})
    if not msgs or msgs[-1].get("content") != pergunta:
        msgs.append({"role": "user", "content": pergunta})

    # 1. Tenta OpenAI API se configurada no ambiente
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini", "messages": msgs, "temperature": 0.1},
                timeout=25,
            )
            if r.status_code == 200:
                txt = r.json()["choices"][0]["message"]["content"]
                return txt.replace("\u202f", " ").replace("\xa0", " ").strip()
        except Exception:
            pass

    # 2. Usa endpoint LLM Generativo OpenAI-compatible gratuito (Pollinations OpenAI GPT)
    import time
    for model_name in ("openai", "openai-fast", "openai"):
        try:
            r = requests.post(
                "https://text.pollinations.ai/openai",
                headers={"Content-Type": "application/json"},
                json={
                    "model": model_name,
                    "messages": msgs,
                    "temperature": 0.1,
                },
                timeout=28,
            )
            if r.status_code == 200:
                data = r.json()
                txt = data["choices"][0]["message"]["content"]
                if txt and len(txt.strip()) > 20:
                    return txt.replace("\u202f", " ").replace("\xa0", " ").strip()
            time.sleep(1.2)
        except Exception:
            time.sleep(1.0)
            continue

    return None


def consultar_oraculo(pergunta: str, historico: list[dict[str, str]] | None = None) -> str:
    """Processa qualquer pergunta combinando Motor Pandas Multi-Base + IA Generativa (LLM)."""
    if not pergunta or not pergunta.strip():
        return "Por favor, digite uma pergunta para o **Oráculo**."

    kb = load_oraculo_kb()
    analise_pandas = _consultar_motor_deterministico(pergunta, kb)

    # Aciona o LLM Generativo com todo o contexto + cálculos do Pandas
    resposta_ia = _chamar_llm_generativo(pergunta, analise_pandas, kb, historico=historico)
    if resposta_ia:
        return resposta_ia

    # Fallback imediato caso sem internet externa
    return analise_pandas


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
                    "Digite qualquer pergunta abaixo (por **Unidade**, **Objeto**, **Rankings**, **Déficit**, **Contrato**, **Processo SEI** ou **Prazo**):"
                ),
            }
        ]

    chat_container = st.container(height=470 if key_prefix == "modal" else 560)
    with chat_container:
        for msg in st.session_state["oraculo_messages"]:
            avatar = "🔮" if msg["role"] == "assistant" else "🧑‍💼"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    c_in, c_clear = st.columns([5.5, 1])
    with c_in:
        user_input = st.chat_input(
            "Pergunte ao Oráculo (ex: 'qual despesa tem maior déficit em 2027?', 'vigilância', 'STI', 'riscos PCA')...",
            key=f"{key_prefix}_chat_input",
        )
    with c_clear:
        if st.button("🗑️ Limpar", key=f"{key_prefix}_clear_btn", use_container_width=True, help="Limpar histórico de conversa"):
            st.session_state["oraculo_messages"] = st.session_state["oraculo_messages"][:1]
            st.rerun(scope="fragment" if key_prefix == "modal" else "app")

    if user_input:
        st.session_state["oraculo_messages"].append({"role": "user", "content": user_input})
        with chat_container:
            with st.chat_message("user", avatar="🧑‍💼"):
                st.markdown(user_input)
            with st.chat_message("assistant", avatar="🔮"):
                with st.spinner("🔮 Oráculo analisando as 5 bases com IA..."):
                    resposta = consultar_oraculo(user_input, historico=st.session_state["oraculo_messages"][:-1])
                    st.markdown(resposta)
        st.session_state["oraculo_messages"].append({"role": "assistant", "content": resposta})
        st.rerun(scope="fragment" if key_prefix == "modal" else "app")


@st.dialog("🔮 Oráculo · Inteligência Analítica", width="large")
def open_oraculo_dialog() -> None:
    """Modal flutuante do Oráculo acessível de qualquer página sem perder os filtros ativos."""
    render_oraculo_chat_ui(key_prefix="modal")


def inject_floating_oraculo() -> None:
    """Injeta o botão flutuante (canto inferior direito) em todas as páginas."""
    st.markdown(
        """
        <style>
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
