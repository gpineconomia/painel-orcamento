"""Módulo para download e carregamento dos dados de Liquidação Mensal (SAP BO - ID: 32115483)."""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

import teste_sap_bo

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "data" / "liquidado_mensal_sap.csv"


def download_liquidado_mensal_csv(timeout: int = 60) -> bool:
    """Faz login no SAP BO e baixa o CSV da instância mais recente do relatório ConsultaLiquidadoMensal (ID: 32115483, Report: 145)."""
    user = os.getenv("SAP_BO_USER", "joao-pbv")
    pwd = os.getenv("SAP_BO_PASS", "3J9h8w3d$")

    client = teste_sap_bo.SapBoClient()
    if not client.login(user, pwd):
        return False

    try:
        doc_id = 32115483
        rep_id = 145
        target_id = doc_id

        # Consulta os metadados do documento para identificar a instância executada mais recente
        try:
            url_meta = f"{client.base_url}/raylight/v1/documents/{doc_id}"
            r_meta = client.session.get(url_meta, headers={"Accept": "application/json"}, timeout=15)
            if r_meta.status_code == 200:
                doc_info = r_meta.json().get("document", {})
                last_inst = doc_info.get("lastSuccessfulInstanceId")
                if last_inst:
                    target_id = int(last_inst)
                    print(f"Baixando dados da instância mais recente do SAP BO: ID {target_id}")
        except Exception as e_meta:
            print(f"Aviso ao consultar instância mais recente: {e_meta}")

        url = f"{client.base_url}/raylight/v1/documents/{target_id}/reports/{rep_id}"
        headers = {"Accept": "text/csv"}
        resp = client.session.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
            CSV_PATH.write_bytes(resp.content)
            return True
        return False
    except Exception as e:
        print(f"Erro ao baixar ConsultaLiquidadoMensal do SAP BO: {e}")
        return False
    finally:
        client.logout()


def load_liquidado_mensal_data(auto_download_if_missing: bool = True) -> tuple[pd.DataFrame, datetime | None]:
    """Retorna DataFrame padronizado com os dados de liquidação mensal extraídos do SAP BO."""
    if not CSV_PATH.exists() and auto_download_if_missing:
        download_liquidado_mensal_csv()

    if not CSV_PATH.exists():
        return pd.DataFrame(), None

    try:
        df_raw = pd.read_csv(CSV_PATH, sep=";", skiprows=3, encoding="utf-8")
    except Exception:
        df_raw = pd.read_csv(CSV_PATH, sep=";", skiprows=3, encoding="latin1")

    # Mapeamento por índice de posição:
    # 0: Exercício (Ano)
    # 1: Período Referência (AnoMes)
    # 2: Grupo Despesa (Codigo)
    # 3: Liquidação (Num Processo Empenho)
    # 4: Beneficiário (Nome)
    # 5: Natureza Despesa (Codigo)
    # 6: Natureza Despesa (Nome)
    # 7: Liquidação (Saldo)
    cols = list(df_raw.columns)
    names_map = {}
    if len(cols) > 0: names_map[cols[0]] = "Exercicio_Ano"
    if len(cols) > 1: names_map[cols[1]] = "Periodo_AnoMes"
    if len(cols) > 2: names_map[cols[2]] = "Grupo_Despesa_Codigo"
    if len(cols) > 3: names_map[cols[3]] = "Processo_SEI_Raw"
    if len(cols) > 4: names_map[cols[4]] = "Beneficiario_Nome"
    if len(cols) > 5: names_map[cols[5]] = "Natureza_Despesa_Codigo"
    if len(cols) > 6: names_map[cols[6]] = "Natureza_Despesa_Nome"
    if len(cols) > 7: names_map[cols[7]] = "Valor_Liquidado_Saldo"

    df = df_raw.rename(columns=names_map).copy()

    # Desconsidera linhas de totalização/resumo
    if "Exercicio_Ano" in df.columns:
        df = df[df["Exercicio_Ano"].astype(str).str.contains(r"\d", regex=True)].copy()

    # Tratamento de Ano e Mês
    if "Exercicio_Ano" in df.columns:
        df["Exercicio_Ano"] = pd.to_numeric(df["Exercicio_Ano"], errors="coerce").fillna(0).astype(int)

    # Tratamento de Ano e Mês via Período Referência no formato AAAAMM (AAAA=Ano, MM=Mês)
    if "Periodo_AnoMes" in df.columns:
        p_clean = (
            df["Periodo_AnoMes"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )
        df["Periodo_AnoMes"] = p_clean
        df["Ano_Referencia"] = pd.to_numeric(p_clean.str[:4], errors="coerce").fillna(0).astype(int)
        df["Mes_Referencia"] = p_clean.str[4:6].str.zfill(2)

    # Tratamento de Processo SEI
    if "Processo_SEI_Raw" in df.columns:
        def limpa_proc(v: object) -> str:
            nums = re.findall(r"\d{10,16}", str(v))
            return nums[0] if nums else str(v).replace(".0", "").strip()
        df["Processo_SEI"] = df["Processo_SEI_Raw"].apply(limpa_proc)
    else:
        df["Processo_SEI"] = ""

    # Tratamento de Valor Liquidado
    if "Valor_Liquidado_Saldo" in df.columns:
        val_str = (
            df["Valor_Liquidado_Saldo"]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip()
        )
        df["Valor_Liquidado_Saldo"] = pd.to_numeric(val_str, errors="coerce").fillna(0.0)

    updated_at = datetime.fromtimestamp(CSV_PATH.stat().st_mtime)
    return df, updated_at
