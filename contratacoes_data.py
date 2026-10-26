"""Módulo para download, cache e estruturação dos dados de Acompanhamento das Contratações 2026.
Fonte: SharePoint Kelly Alexandria (Acompanhamento das Contratações 2026.xlsx).
"""
from __future__ import annotations

import io
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CACHE_FILE = DATA_DIR / "contratacoes_2026_cache.xlsx"

# URLs
SHAREPOINT_WEB_URL = (
    "https://goiasgovbr-my.sharepoint.com/:x:/g/personal/kelly_alexandria_goias_gov_br/"
    "cQpOsBqWlE37SJGr3Ai3EVdMEgUCMxc5yb40q5zQB47790X6rw"
)
SHAREPOINT_DIRECT_DOC_URL = (
    "https://goiasgovbr-my.sharepoint.com/personal/kelly_alexandria_goias_gov_br/Documents/"
    "Acompanhamento das Contratações 2026.xlsx"
)
GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/gpineconomia/painel-orcamento/main/data/contratacoes_2026_cache.xlsx"
)

TZ_BRASILIA = timezone(timedelta(hours=-3))


def download_contratacoes_workbook(timeout: int = 30) -> bool:
    """Baixa a planilha mais recente do SharePoint (via Excel COM no Windows ou GitHub na nuvem) e salva no cache local."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Tentar via Excel COM no Windows (aproveita autenticação integrada do Windows / Office 365)
    try:
        import win32com.client
        import pythoncom

        pythoncom.CoInitialize()
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        wb = excel.Workbooks.Open(SHAREPOINT_DIRECT_DOC_URL, ReadOnly=True)
        dest_abs = str(CACHE_FILE.resolve())
        if CACHE_FILE.exists():
            try:
                CACHE_FILE.unlink()
            except Exception:
                pass
        # Formato 51 = xlOpenXMLWorkbook (.xlsx)
        wb.SaveCopyAs(dest_abs)
        wb.Close(SaveChanges=False)
        excel.Quit()

        if CACHE_FILE.exists() and CACHE_FILE.stat().st_size > 1000:
            return True
    except Exception:
        pass

    # 2. Tentar download direto via HTTP caso o link venha a ser aberto publicamente
    try:
        resp = requests.get(
            SHAREPOINT_WEB_URL + "?download=1",
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True,
        )
        if resp.status_code == 200 and resp.content.startswith(b"PK"):
            CACHE_FILE.write_bytes(resp.content)
            return True
    except Exception:
        pass

    # 3. Fallback nuvem: Repositório GitHub
    try:
        import time

        url = f"{GITHUB_RAW_URL}?_t={int(time.time())}"
        resp = requests.get(url, timeout=20, headers={"Cache-Control": "no-cache"})
        if resp.status_code == 200 and resp.content.startswith(b"PK"):
            CACHE_FILE.write_bytes(resp.content)
            return True
    except Exception:
        pass

    return CACHE_FILE.exists()


def parse_sei(val: object) -> str:
    """Extrai número de Processo SEI sem notação científica e com formatação limpa."""
    if val is None or pd.isna(val):
        return ""
    if isinstance(val, (int, float)):
        try:
            val_int = int(val)
            s_val = str(val_int)
            if len(s_val) >= 10:
                return s_val
        except Exception:
            pass
    s = str(val).strip().replace(".0", "")
    digits = re.findall(r"\d{10,16}", s)
    if digits:
        return digits[0]
    return s if s.lower() not in ["nan", "none", "-", "0"] else ""


def parse_sislog(val: object) -> str:
    """Extrai número SISLOG como texto limpo sem decimais."""
    if val is None or pd.isna(val):
        return "-"
    try:
        val_int = int(float(val))
        return str(val_int)
    except Exception:
        s = str(val).strip()
        return s if s and s.lower() not in ["nan", "none"] else "-"


def carregar_dados_brutos() -> tuple[pd.DataFrame, str]:
    """Carrega o DataFrame e extrai a data de atualização informada na planilha."""
    if not CACHE_FILE.exists():
        download_contratacoes_workbook()

    if not CACHE_FILE.exists():
        raise FileNotFoundError(f"Arquivo de cache não encontrado em {CACHE_FILE}")

    # Ler planilha
    xls = pd.ExcelFile(CACHE_FILE)
    sheet_name = "Contratações 2026" if "Contratações 2026" in xls.sheet_names else xls.sheet_names[0]
    df = pd.read_excel(CACHE_FILE, sheet_name=sheet_name)

    # Identificar se há linha com "Data da Atualização"
    data_atualizacao = ""
    for col in df.columns:
        matches = df[col].astype(str).str.extract(r"Data da Atualiza[çc][ãa]o:\s*([0-9/]+)", flags=re.IGNORECASE)
        found = matches.dropna()
        if not found.empty:
            data_atualizacao = str(found.iloc[0, 0]).strip()
            break

    if not data_atualizacao:
        mtime = CACHE_FILE.stat().st_mtime
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone(TZ_BRASILIA)
        data_atualizacao = dt.strftime("%d/%m/%Y às %H:%M")

    # Limpeza de colunas (remover espaços nos nomes)
    df.columns = [str(c).strip() for c in df.columns]

    # Filtrar apenas linhas válidas (que possuam Objeto e não sejam notas de rodapé)
    if "Objeto" in df.columns:
        df = df[df["Objeto"].notna()].copy()
        df = df[~df["Objeto"].astype(str).str.contains(r"Data da Atualiza", case=False, na=False)].copy()

    # Normalizar campos
    if "Prioridade" in df.columns:
        df["Prioridade"] = df["Prioridade"].astype(str).str.strip()
        df["Prioridade"] = df["Prioridade"].replace({"Média": "Média", "Média ": "Média", "nan": "Não informada", "": "Não informada"})

    if "Número SEI" in df.columns:
        df["Número SEI"] = df["Número SEI"].apply(parse_sei)

    if "Número da Contratação SISLOG" in df.columns:
        df["Número da Contratação SISLOG"] = df["Número da Contratação SISLOG"].apply(parse_sislog)

    if "Tipo" in df.columns:
        df["Tipo"] = df["Tipo"].astype(str).str.strip()
        df["Tipo"] = df["Tipo"].replace({"nan": "Não informado", "": "Não informado"})

    if "Status da Contratação" in df.columns:
        df["Status da Contratação"] = df["Status da Contratação"].astype(str).str.strip()
        status_map = {
            "Fase preparatória": "Fase Preparatória",
            "fase preparatória": "Fase Preparatória",
            "nan": "Não informado",
            "": "Não informado",
        }
        df["Status da Contratação"] = df["Status da Contratação"].replace(status_map)

    if "Prevista para 2026?" in df.columns:
        df["Prevista para 2026?"] = df["Prevista para 2026?"].astype(str).str.strip()
        df["Prevista para 2026?"] = df["Prevista para 2026?"].replace({"nan": "Não informado", "": "Não informado"})

    if "Unidade Demandante" in df.columns:
        df["Unidade Demandante"] = df["Unidade Demandante"].astype(str).str.strip().str.upper()
        df["Unidade Demandante"] = df["Unidade Demandante"].replace({"NAN": "Não informada", "": "Não informada"})

    if "Responsável" in df.columns:
        df["Responsável"] = df["Responsável"].astype(str).str.strip()
        df["Responsável"] = df["Responsável"].replace({"nan": "Não informado", "": "Não informado"})
    elif "Responsável " in df.columns:
        df["Responsável"] = df["Responsável "].astype(str).str.strip()
        df["Responsável"] = df["Responsável"].replace({"nan": "Não informado", "": "Não informado"})

    if "Ponto de Atenção" in df.columns:
        df["Ponto de Atenção"] = df["Ponto de Atenção"].astype(str).str.strip()
        df["Ponto de Atenção"] = df["Ponto de Atenção"].replace({"nan": "-", "": "-"})

    if "Necessitará de Parecer Jurídico" in df.columns:
        df["Necessitará de Parecer Jurídico"] = df["Necessitará de Parecer Jurídico"].astype(str).str.strip()
        df["Necessitará de Parecer Jurídico"] = df["Necessitará de Parecer Jurídico"].replace({"nan": "Não informado", "": "Não informado"})

    df = df.reset_index(drop=True)
    return df, data_atualizacao


@st.cache_data(ttl=3600, show_spinner="Carregando dados de Acompanhamento das Contratações 2026...")
def load_contratacoes_2026() -> tuple[pd.DataFrame, str]:
    """Carrega dados em cache por 60 minutos (3600s)."""
    return carregar_dados_brutos()


def clear_contratacoes_cache() -> None:
    """Limpa o cache do Streamlit e força nova leitura."""
    try:
        load_contratacoes_2026.clear()
    except Exception:
        pass
