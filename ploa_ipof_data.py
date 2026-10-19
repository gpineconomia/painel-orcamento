"""Carregamento e tratamento dos dados oficiais de IPOF do SAP BO."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

import teste_sap_bo

BASE_DIR = Path(__file__).parent
SAP_CSV_PATH = BASE_DIR / "data" / "ploa_ipof_oficial_sap.csv"


def download_sap_ipof_csv(timeout: int = 60) -> bool:
    """Faz login no SAP BO e baixa o CSV do relatório PDF PLOA (32837188)."""
    user = teste_sap_bo.os.getenv("SAP_BO_USER", "joao-pbv")
    pwd = teste_sap_bo.os.getenv("SAP_BO_PASS", "3J9h8w3d$")

    client = teste_sap_bo.SapBoClient()
    if not client.login(user, pwd):
        return False

    try:
        doc_id = 32837188
        url = f"{client.base_url}/raylight/v1/documents/{doc_id}/reports/16"
        headers = {"Accept": "text/csv"}
        resp = client.session.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            SAP_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
            SAP_CSV_PATH.write_bytes(resp.content)
            return True
        return False
    except Exception as e:
        print(f"Erro ao baixar do SAP BO: {e}")
        return False
    finally:
        client.logout()


def load_sap_ipof_data(auto_download_if_missing: bool = True) -> tuple[pd.DataFrame, datetime | None]:
    """Retorna DataFrame padronizado com os dados oficiais de IPOF extraídos do SAP BO."""
    if not SAP_CSV_PATH.exists() and auto_download_if_missing:
        download_sap_ipof_csv()

    if not SAP_CSV_PATH.exists():
        return pd.DataFrame(), None

    try:
        df_raw = pd.read_csv(SAP_CSV_PATH, sep=";", skiprows=3, encoding="utf-8")
    except Exception:
        df_raw = pd.read_csv(SAP_CSV_PATH, sep=";", skiprows=3, encoding="latin1")

    # Mapeamento por índice de posição para garantir precisão absoluta
    # 0: Órgão Sucessor
    # 1: Situação IPOF (Nome)
    # 2: Período Referência (Ano)
    # 3: IPOF (Num Processo)
    # 4: IPOF (Número)
    # 5: Grupo Despesa
    # 6: Ação Código
    # 7: Ação Código/Nome
    # 8: IPOF (Valor Parcela)
    # 9: Descrição Despesa
    # 10: Programa Gomap
    # 11: Projeto Gomap
    # 12: Natureza despesa
    # 13: Plano Interno (Descrição)
    # 14: Plano Interno (Nome)
    # 15: Tipo Saldo
    # 16: Fonte
    cols = list(df_raw.columns)
    names_map = {}
    if len(cols) > 0: names_map[cols[0]] = "Orgao"
    if len(cols) > 1: names_map[cols[1]] = "Situacao_IPOF_Oficial"
    if len(cols) > 2: names_map[cols[2]] = "Ano_Referencia"
    if len(cols) > 3: names_map[cols[3]] = "Processo_SEI_Oficial"
    if len(cols) > 4: names_map[cols[4]] = "Num_IPOF_Oficial"
    if len(cols) > 5: names_map[cols[5]] = "Grupo_Despesa_Oficial"
    if len(cols) > 7: names_map[cols[7]] = "Acao_Oficial"
    if len(cols) > 8: names_map[cols[8]] = "Valor_Parcela_Oficial"
    if len(cols) > 9: names_map[cols[9]] = "Descricao_Despesa_Oficial"
    if len(cols) > 12: names_map[cols[12]] = "Natureza_Despesa_Oficial"
    if len(cols) > 14: names_map[cols[14]] = "Plano_Interno_Oficial"
    if len(cols) > 16: names_map[cols[16]] = "Fonte_Oficial"

    df = df_raw.rename(columns=names_map).copy()

    # Tratamento de número de IPOF
    if "Num_IPOF_Oficial" in df.columns:
        df["Num_IPOF_Oficial"] = df["Num_IPOF_Oficial"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    else:
        df["Num_IPOF_Oficial"] = ""

    # Desconsidera linhas de totalização/resumo do relatório SAP BO (ex: "Soma:", "Total", etc.)
    df = df[
        df["Num_IPOF_Oficial"].str.isdigit()
        & (~df["Num_IPOF_Oficial"].str.lower().str.contains("soma|total"))
    ].copy()

    # Desconsidera IPOFs com ação orçamentária 4144, 4145 ou em branco/não encontrada
    if "Acao_Oficial" in df.columns:
        def is_acao_invalida(val: object) -> bool:
            s = str(val).strip().lower()
            if not s or s in ["nan", "none", "<na>", "", "0", "0.0", "0000", "0000 - nao encontrada"]:
                return True
            if "4144" in s or "4145" in s:
                return True
            return False

        df = df[~df["Acao_Oficial"].apply(is_acao_invalida)].copy()

    # Tratamento de Processo SEI
    if "Processo_SEI_Oficial" in df.columns:
        df["Processo_SEI_Oficial"] = df["Processo_SEI_Oficial"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()

    # Tratamento de Valor Parcela
    if "Valor_Parcela_Oficial" in df.columns:
        val_str = (
            df["Valor_Parcela_Oficial"]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip()
        )
        df["Valor_Parcela_Oficial"] = pd.to_numeric(val_str, errors="coerce").fillna(0.0)

    # Tratamento de Ano
    if "Ano_Referencia" in df.columns:
        df["Ano_Referencia"] = pd.to_numeric(df["Ano_Referencia"], errors="coerce").fillna(0).astype(int)

    updated_at = datetime.fromtimestamp(SAP_CSV_PATH.stat().st_mtime)
    return df, updated_at
