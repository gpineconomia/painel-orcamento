"""Módulo para download, carregamento e conciliação por Sequencial:
SAP BO (ConsultaDeclaradoEmpenhadoLiquidadoPagoPorSequencial - ID: 42943444, Report: 107)
× Aba 'Indicacoes' da Planilha de Gestão Orçamentária 2026 (SharePoint).
"""
from __future__ import annotations

import io
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import data_source
import teste_sap_bo

BASE_DIR = Path(__file__).parent
CSV_SEQ_PATH = BASE_DIR / "data" / "declarado_empenhado_seq_sap.csv"

# Descrições oficiais das Ações Orçamentárias (extraídas da aba Orcamento da planilha 2026)
ACOES_DESCRICAO: dict[str, str] = {
    "2435": "Modernização e Institucionalização da Secretaria da Economia",
    "2588": "Soluções de TI",
    "2589": "Construção, Reforma, Ampliação e Readequação de Equipamentos Públicos",
    "2590": "Nota Fiscal do Programa de Estímulo à Cidadania",
    "2591": "Gestão da Iniciativa de Ampliação da Eficiência e Qualidade do Gasto Público",
    "2592": "Observatório de Políticas Públicas",
    "2593": "Estruturação de Projetos para Unificação de Metas e Objetivos",
    "2594": "Implantação de Centro de Custo",
    "2595": "Implantação de Sistemática de Modernização e Inovação da Administração Tributária",
    "2613": "Ação Orçamentária 2613",
    "2614": "Ação Orçamentária 2614",
    "2615": "Ação Orçamentária 2615",
    "2616": "Ação Orçamentária 2616",
    "3248": "Elaboração do Plano Estadual de Médio e Longo Prazo",
    "3365": "Sistematização de Serviços de Atendimento ao Contribuinte",
    "4243": "Gestão e Manutenção das Atividades da Economia",
}

FONTES_DESCRICAO: dict[str, str] = {
    "15000100": "15000100 - Receitas Ordinárias (Tesouro)",
    "15010100": "15010100 - Receitas Ordinárias (Outras)",
    "17540111": "17540111 - Operações de Crédito Externas (PROFISCO)",
}

GRUPOS_DESCRICAO: dict[int, str] = {
    3: "03 - Custeio",
    4: "04 - Investimento",
    5: "05 - Inversões Financeiras",
}


def _parse_ptbr_float(v: object) -> float:
    """Converte string numérica PT-BR ('3.684.748,35') ou float para float de forma segura."""
    if v is None or pd.isna(v):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v) if not pd.isna(v) else 0.0
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "<na>", "-"):
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def download_declarado_empenhado_seq_csv(timeout: int = 60) -> bool:
    """Faz login no SAP BO e baixa o CSV da aba '2026' (Report 107) do relatório ID 42943444."""
    user = os.getenv("SAP_BO_USER", "joao-pbv")
    pwd = os.getenv("SAP_BO_PASS", "3J9h8w3d$")

    client = teste_sap_bo.SapBoClient()
    if not client.login(user, pwd):
        return False

    try:
        doc_id = 42943444
        rep_id = 107  # Aba "2026"
        target_id = doc_id

        try:
            url_meta = f"{client.base_url}/raylight/v1/documents/{doc_id}"
            r_meta = client.session.get(url_meta, headers={"Accept": "application/json"}, timeout=15)
            if r_meta.status_code == 200:
                doc_info = r_meta.json().get("document", {})
                last_inst = doc_info.get("lastSuccessfulInstanceId")
                if last_inst:
                    target_id = int(last_inst)
                    print(f"Baixando ConsultaDeclaradoEmpenhadoLiquidadoPagoPorSequencial (instância {target_id}, report {rep_id})")
        except Exception as e_meta:
            print(f"Aviso ao consultar instância mais recente de {doc_id}: {e_meta}")

        url = f"{client.base_url}/raylight/v1/documents/{target_id}/reports/{rep_id}"
        headers = {"Accept": "text/csv"}
        resp = client.session.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200 and len(resp.content) > 200:
            CSV_SEQ_PATH.parent.mkdir(parents=True, exist_ok=True)
            CSV_SEQ_PATH.write_bytes(resp.content)
            return True
        return False
    except Exception as e:
        print(f"Erro ao baixar ConsultaDeclaradoEmpenhadoLiquidadoPagoPorSequencial do SAP BO: {e}")
        return False
    finally:
        client.logout()


def load_sap_sequencial_data(auto_download_if_missing: bool = True) -> tuple[pd.DataFrame, datetime | None]:
    """Carrega o CSV do relatório SAP BO 42943444 (aba 2026)."""
    if os.name != "nt":
        try:
            import time
            import requests
            url = f"https://raw.githubusercontent.com/gpineconomia/painel-orcamento/main/data/declarado_empenhado_seq_sap.csv?_t={int(time.time())}"
            resp = requests.get(url, timeout=15, headers={"Cache-Control": "no-cache"})
            if resp.status_code == 200 and len(resp.content) > 200:
                CSV_SEQ_PATH.parent.mkdir(parents=True, exist_ok=True)
                CSV_SEQ_PATH.write_bytes(resp.content)
        except Exception:
            pass
    elif not CSV_SEQ_PATH.exists() and auto_download_if_missing:
        download_declarado_empenhado_seq_csv()

    if not CSV_SEQ_PATH.exists():
        return pd.DataFrame(), None

    try:
        df_raw = pd.read_csv(CSV_SEQ_PATH, sep=";", encoding="utf-8")
    except Exception:
        df_raw = pd.read_csv(CSV_SEQ_PATH, sep=";", encoding="latin1")

    # Remove linhas vazias
    df_raw = df_raw.dropna(how="all").copy()

    rename_map = {
        "Exercício (Ano)": "Exercicio",
        "Declaração (Sequencial Dotação)": "Seq_Str",
        "Classificação orçamentária (Descrição)": "Classificacao_Orcamentaria",
        "Fonte (Codigo)": "Fonte_Cod",
        "Grupo Despesa (Cod)": "Grupo_Cod",
        "Ação (Cod)": "Acao_Cod",
        "Dotação (Valor Autorizado)": "Autorizado",
        "Valor Declarado": "Declarado_SAP",
        "Saldo Declarado": "Saldo_Declarado_SAP",
        "Valor Saldo do Empenho": "Empenhado",
        "Saldo Empenho": "Saldo_Empenho_SAP",
        "Valor Saldo Liquidado": "Liquidado",
        "Valor Saldo Pago": "Pago",
        "Valor Estimado": "Estimado_SAP",
        "Valor Anulação": "Anulacao_SAP",
    }
    df = df_raw.rename(columns=rename_map).copy()

    if "Exercicio" in df.columns:
        df = df[df["Exercicio"].astype(str).str.contains(r"\d", regex=True)].copy()

    df["Seq"] = pd.to_numeric(df["Seq_Str"].astype(str).str.strip(), errors="coerce").fillna(0).astype(int)
    df = df[df["Seq"] > 0].copy()

    df["Classificacao_Orcamentaria"] = df["Classificacao_Orcamentaria"].astype(str).str.strip()
    df["Fonte_Cod"] = df["Fonte_Cod"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df["Grupo_Cod"] = pd.to_numeric(df["Grupo_Cod"], errors="coerce").fillna(0).astype(int)
    df["Acao_Cod"] = df["Acao_Cod"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()

    for col_val in ("Autorizado", "Empenhado", "Liquidado", "Pago"):
        if col_val in df.columns:
            df[col_val] = df[col_val].apply(_parse_ptbr_float)
        else:
            df[col_val] = 0.0

    tz_brasilia = timezone(timedelta(hours=-3))
    updated_at = (
        datetime.fromtimestamp(CSV_SEQ_PATH.stat().st_mtime, tz=timezone.utc)
        .astimezone(tz_brasilia)
        .replace(tzinfo=None)
    )
    return df, updated_at


def load_aba_indicacoes_2026() -> tuple[pd.DataFrame, datetime | None]:
    """Lê a aba 'Indicacoes' da planilha 2026 e enriquece com Unidade e Fornecedor da aba 'Contratos'."""
    cache_file = data_source.CACHE_FILE_2026
    if not cache_file.exists():
        data_source.load_data(ano=2026)
    elif data_source._AUTH is None:
        data_source.fetch_from_github_cloud(cache_file.name, cache_file)

    if not cache_file.exists():
        return pd.DataFrame(), None

    excel_bytes = cache_file.read_bytes()
    xl = pd.ExcelFile(io.BytesIO(excel_bytes))

    sheet_ind = next((s for s in xl.sheet_names if "indica" in s.lower()), "Indicacoes")
    df_ind = pd.read_excel(xl, sheet_name=sheet_ind, header=1)

    # Limpa nomes de colunas
    df_ind.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df_ind.columns]
    if "Classificação do Obejto" in df_ind.columns and "Classificação do Objeto" not in df_ind.columns:
        df_ind = df_ind.rename(columns={"Classificação do Obejto": "Classificação do Objeto"})
    if "Resposável pelo Preenchimento" in df_ind.columns and "Responsável pelo Preenchimento" not in df_ind.columns:
        df_ind = df_ind.rename(columns={"Resposável pelo Preenchimento": "Responsável pelo Preenchimento"})

    # Filtra linhas que possuem Sequencial ou Valor Indicado preenchido
    df_ind["Seq"] = pd.to_numeric(df_ind.get("Sequencial"), errors="coerce").fillna(0).astype(int)
    df_ind["Valor_Indicado_2026"] = pd.to_numeric(df_ind.get("Valor Indicado 2026"), errors="coerce").fillna(0.0)
    df_ind["Situacao_Clean"] = df_ind.get("Situação", pd.Series(dtype=str)).fillna("").astype(str).str.strip()

    # Mantém linhas reais de indicação (Ativo ou Cancelado)
    df_ind = df_ind[(df_ind["Seq"] > 0) & (df_ind["Situacao_Clean"] != "")].copy()

    # Normaliza campos de texto
    for c_txt in ("Item Aba Contratos", "Processo", "Contrato", "Objeto", "Resumo", "Classificação do Objeto", "IPOF", "Observação", "Responsável pelo Preenchimento"):
        if c_txt in df_ind.columns:
            df_ind[c_txt] = (
                df_ind[c_txt]
                .fillna("-")
                .astype(str)
                .str.replace("_x000D_", " ", regex=False)
                .str.replace("\xa0", " ", regex=False)
                .str.replace(r"\.0$", "", regex=True)
                .str.strip()
            )

    df_ind["Acao_Cod"] = df_ind.get("Ação", pd.Series(dtype=str)).fillna("").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df_ind["Grupo_Cod"] = pd.to_numeric(df_ind.get("Grupo de Despesa"), errors="coerce").fillna(0).astype(int)
    df_ind["Fonte_Cod"] = df_ind.get("Fonte", pd.Series(dtype=str)).fillna("").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df_ind["Data_Indicacao"] = pd.to_datetime(df_ind.get("Data"), errors="coerce")

    # Enriquece com Unidade e Empresa Contratada a partir da aba Contratos usando 'Item Aba Contratos'
    try:
        df_contratos, _, _ = data_source.load_data(ano=2026)
        if not df_contratos.empty and "Item" in df_contratos.columns:
            mapa_uni: dict[str, str] = {}
            mapa_emp: dict[str, str] = {}
            for _, rc in df_contratos.iterrows():
                it_k = str(rc.get("Item", "")).replace(".0", "").strip()
                if it_k and it_k not in mapa_uni:
                    u_v = str(rc.get("Unidade", "-")).strip()
                    e_v = str(rc.get("Empresa Contratada", "-")).strip()
                    mapa_uni[it_k] = u_v if u_v not in ("nan", "None", "") else "-"
                    mapa_emp[it_k] = e_v if e_v not in ("nan", "None", "") else "-"
            df_ind["Unidade"] = df_ind["Item Aba Contratos"].map(lambda x: mapa_uni.get(str(x).strip(), "Não Vinculada"))
            df_ind["Empresa_Contratada"] = df_ind["Item Aba Contratos"].map(lambda x: mapa_emp.get(str(x).strip(), "-"))
        else:
            df_ind["Unidade"] = "Não Vinculada"
            df_ind["Empresa_Contratada"] = "-"
    except Exception:
        df_ind["Unidade"] = "Não Vinculada"
        df_ind["Empresa_Contratada"] = "-"

    updated_plan = data_source.to_brasilia_datetime(cache_file.stat().st_mtime)
    return df_ind, updated_plan


def load_consolidado_indicacoes_2026() -> tuple[pd.DataFrame, pd.DataFrame, datetime | None, datetime | None]:
    """
    Realiza o cruzamento oficial pela chave `Seq` (Sequencial):
    - Base Principal: ConsultaDeclaradoEmpenhadoLiquidadoPagoPorSequencial (ID: 42943444 - Report 107 / 2026)
    - Campo `Indicado` (substituindo `Declarado` em branco): Soma de `Valor Indicado 2026` (Situação = Ativo) da aba `Indicacoes` por `Seq`.
    Retorna: (df_seq_consolidado, df_indicacoes_detalhe, updated_sap, updated_planilha)
    """
    df_sap, updated_sap = load_sap_sequencial_data(auto_download_if_missing=True)
    df_ind, updated_plan = load_aba_indicacoes_2026()

    if df_sap.empty:
        return pd.DataFrame(), df_ind, updated_sap, updated_plan

    # Filtra indicações Ativas para compor o campo "Indicado" por Sequencial
    if not df_ind.empty:
        df_ind_ativo = df_ind[df_ind["Situacao_Clean"].str.lower() == "ativo"].copy()
        agrup_ind = (
            df_ind_ativo.groupby("Seq", as_index=False)
            .agg(
                Indicado=("Valor_Indicado_2026", "sum"),
                Qtd_Indicacoes=("Valor_Indicado_2026", "count"),
                Qtd_Contratos=("Contrato", lambda s: len({v for v in s if v not in ("-", "", "nan", "Não se aplica", "Em Planejamento")})),
                Qtd_Processos=("Processo", lambda s: len({v for v in s if v not in ("-", "", "nan")})),
            )
        )
    else:
        agrup_ind = pd.DataFrame(columns=["Seq", "Indicado", "Qtd_Indicacoes", "Qtd_Contratos", "Qtd_Processos"])

    df_merged = pd.merge(df_sap, agrup_ind, on="Seq", how="left")
    df_merged["Indicado"] = df_merged["Indicado"].fillna(0.0)
    df_merged["Qtd_Indicacoes"] = df_merged["Qtd_Indicacoes"].fillna(0).astype(int)
    df_merged["Qtd_Contratos"] = df_merged["Qtd_Contratos"].fillna(0).astype(int)
    df_merged["Qtd_Processos"] = df_merged["Qtd_Processos"].fillna(0).astype(int)

    # Saldos e indicadores calculados
    df_merged["Saldo_Indicacao"] = df_merged["Autorizado"] - df_merged["Indicado"]
    df_merged["Saldo_Empenho"] = df_merged["Autorizado"] - df_merged["Empenhado"]
    df_merged["Indicado_A_Empenhar"] = df_merged["Indicado"] - df_merged["Empenhado"]
    df_merged["Empenhado_A_Liquidar"] = df_merged["Empenhado"] - df_merged["Liquidado"]
    df_merged["Liquidado_A_Pagar"] = df_merged["Liquidado"] - df_merged["Pago"]

    # Rótulos amigáveis para filtros
    df_merged["Acao_Label"] = df_merged["Acao_Cod"].map(
        lambda c: f"{c} - {ACOES_DESCRICAO.get(c, 'Ação ' + c)}"
    )
    df_merged["Grupo_Label"] = df_merged["Grupo_Cod"].map(
        lambda g: GRUPOS_DESCRICAO.get(int(g), f"0{g} - Outros")
    )
    df_merged["Fonte_Label"] = df_merged["Fonte_Cod"].map(
        lambda f: FONTES_DESCRICAO.get(f, f)
    )

    df_merged = df_merged.sort_values("Seq", ascending=True).reset_index(drop=True)
    return df_merged, df_ind, updated_sap, updated_plan
