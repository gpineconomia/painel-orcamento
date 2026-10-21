"""Módulo para download, cache e estruturação dos dados do PCA 2027 (Google Sheets - SETRAC)."""
from __future__ import annotations

import io
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PCA_CACHE_FILE = DATA_DIR / "pca_2027_cache.xlsx"

# Link oficial de exportação direta do Google Sheets (aba PCA 2027)
PCA_GSHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1N_ryiz_KbqDxokvaI3NuSz7MrQvQ9xv469r3yAktt8k/export?format=xlsx"
)
PCA_GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/gpineconomia/painel-orcamento/main/data/pca_2027_cache.xlsx"
)

TZ_BRASILIA = timezone(timedelta(hours=-3))


def parse_money(val: object) -> float:
    """Converte valores monetários (float, int ou strings formatadas) para float com segurança."""
    if val is None or pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("R$", "").replace("\xa0", " ").strip()
    if not s or s.lower() in ["nan", "none", "-", "em andamento", "a definir", "aguardando"]:
        return 0.0
    # Caso como '726,300,24' ou '945,378,00' (vírgulas nos milhares e decimais)
    if s.count(",") > 1 and "." not in s:
        parts = s.split(",")
        s = "".join(parts[:-1]) + "." + parts[-1]
    elif "," in s and "." in s:
        # Padrão brasileiro 1.234,56
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:  # Padrão americano 1,234.56
            s = s.replace(",", "")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_sei(val: object) -> str:
    """Extrai número de Processo SEI sem notação científica e com formatação limpa."""
    if val is None or pd.isna(val):
        return ""
    if isinstance(val, (int, float)):
        # Evita .0 no final
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


def parse_date(val: object) -> pd.Timestamp | None:
    """Converte campo de data para Timestamp de forma segura."""
    if val is None or pd.isna(val):
        return None
    try:
        dt = pd.to_datetime(val, errors="coerce", dayfirst=True)
        return dt if pd.notna(dt) else None
    except Exception:
        return None


def download_pca_workbook(timeout: int = 25) -> bool:
    """Faz download da planilha mais recente do PCA 2027 do Google Sheets e salva no cache local."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(PCA_GSHEET_URL, timeout=timeout)
        if resp.status_code == 200 and resp.content.startswith(b"PK"):
            PCA_CACHE_FILE.write_bytes(resp.content)
            return True
    except Exception as e:
        print(f"Aviso ao baixar PCA do Google Sheets: {e}")

    # Fallback se estiver na nuvem ou falhar a conexão com o Google
    try:
        resp_gh = requests.get(PCA_GITHUB_RAW_URL, timeout=15)
        if resp_gh.status_code == 200 and resp_gh.content.startswith(b"PK"):
            PCA_CACHE_FILE.write_bytes(resp_gh.content)
            return True
    except Exception:
        pass

    return False


def load_pca_data(auto_download: bool = True) -> tuple[pd.DataFrame, datetime | None]:
    """Carrega os dados da aba 'PCA 2027' estruturados e tipados para exibição."""
    if (not PCA_CACHE_FILE.exists() or auto_download) and not PCA_CACHE_FILE.exists():
        download_pca_workbook()

    if not PCA_CACHE_FILE.exists():
        # Tenta download de emergência
        ok = download_pca_workbook()
        if not ok or not PCA_CACHE_FILE.exists():
            return pd.DataFrame(), None

    try:
        df_raw = pd.read_excel(PCA_CACHE_FILE, sheet_name="PCA 2027")
    except Exception as exc:
        print(f"Erro ao ler aba PCA 2027: {exc}")
        return pd.DataFrame(), None

    # Mapeamento e normalização das colunas
    cols = df_raw.columns.tolist()

    def find_col(term: str) -> str | None:
        for c in cols:
            if term in str(c).lower():
                return c
        return None

    c_item = find_col("nº") or cols[0]
    c_proc = find_col("processo")
    c_obj = find_col("objeto resumido") or find_col("objeto")
    c_det = find_col("detalhamento")
    c_uni_sup = find_col("unidade superior")
    c_uni_dem = find_col("unidade demandante")
    c_tem_contrato = find_col("possui contrato")
    c_tipo = find_col("tipo / agrupamento") or find_col("tipo")
    c_modalidade = find_col("modalidade")
    c_providencia = find_col("providência") or find_col("providencia")
    c_dt_inicio = find_col("limite para início") or find_col("inicio do processo")
    c_dt_encaminha = find_col("agente de contratação") or find_col("setor de contratos")
    c_deadline = find_col("deadline")
    c_status = find_col("status da contratação") or find_col("status")
    c_val_total = find_col("total estimado")
    c_val_2027 = find_col("estimado para 2027")
    c_val_contratado = find_col("valor contratado")
    c_unidade_orc = find_col("unidade orçamentária") or find_col("empenho")
    c_previsto = find_col("previsto no pca")

    records = []
    for idx, row in df_raw.iterrows():
        # Ignora linhas totalmente vazias
        if row.isna().all():
            continue

        item_num = row.get(c_item)
        proc_raw = row.get(c_proc) if c_proc else ""
        proc_clean = parse_sei(proc_raw)

        obj_res = str(row.get(c_obj, "")).strip() if c_obj and pd.notna(row.get(c_obj)) else ""
        if not obj_res or obj_res.lower() in ["nan", "none"]:
            continue

        det_obj = str(row.get(c_det, "")).strip() if c_det and pd.notna(row.get(c_det)) else ""
        u_sup = str(row.get(c_uni_sup, "")).strip() if c_uni_sup and pd.notna(row.get(c_uni_sup)) else "Não informada"
        u_dem = str(row.get(c_uni_dem, "")).strip() if c_uni_dem and pd.notna(row.get(c_uni_dem)) else u_sup

        contrato_raw = str(row.get(c_tem_contrato, "")).strip() if c_tem_contrato and pd.notna(row.get(c_tem_contrato)) else "Não"
        tem_contrato_bool = bool(contrato_raw and contrato_raw.lower() not in ["não", "nao", "-", "nan", "none", "0"])

        tipo_agrup = str(row.get(c_tipo, "")).strip() if c_tipo and pd.notna(row.get(c_tipo)) else "-"
        modalidade = str(row.get(c_modalidade, "")).strip() if c_modalidade and pd.notna(row.get(c_modalidade)) else "-"
        providencia = str(row.get(c_providencia, "")).strip() if c_providencia and pd.notna(row.get(c_providencia)) else "SEM PROVIDÊNCIAS"

        status_contratacao = str(row.get(c_status, "")).strip() if c_status and pd.notna(row.get(c_status)) else "SEM PROVIDÊNCIA"
        if status_contratacao.lower() in ["nan", "none", ""]:
            status_contratacao = "SEM PROVIDÊNCIA" if "sem provid" in providencia.lower() else "PLANEJADO"

        dt_inicio = parse_date(row.get(c_dt_inicio)) if c_dt_inicio else None
        dt_encaminha = parse_date(row.get(c_dt_encaminha)) if c_dt_encaminha else None
        deadline = parse_date(row.get(c_deadline)) if c_deadline else None

        v_total = parse_money(row.get(c_val_total)) if c_val_total else 0.0
        v_2027 = parse_money(row.get(c_val_2027)) if c_val_2027 else 0.0
        v_contratado_raw = row.get(c_val_contratado) if c_val_contratado else None
        v_contratado = parse_money(v_contratado_raw) if pd.notna(v_contratado_raw) else 0.0

        u_orc = str(row.get(c_unidade_orc, "")).strip() if c_unidade_orc and pd.notna(row.get(c_unidade_orc)) else "-"
        previsto = str(row.get(c_previsto, "")).strip() if c_previsto and pd.notna(row.get(c_previsto)) else "-"

        records.append({
            "Item": item_num,
            "Processo_SEI": proc_clean,
            "Objeto_Resumido": obj_res,
            "Detalhamento_Objeto": det_obj,
            "Unidade_Superior": u_sup,
            "Unidade_Demandante": u_dem,
            "Contrato_Vigente": contrato_raw if tem_contrato_bool else "(Sem contrato)",
            "Tem_Contrato_Vigente": tem_contrato_bool,
            "Tipo_Agrupamento": tipo_agrup,
            "Modalidade": modalidade,
            "Providencia_2027": providencia,
            "Status_Contratacao": status_contratacao,
            "Data_Inicio_SETRAC": dt_inicio,
            "Data_Encaminhamento_Contratos": dt_encaminha,
            "Deadline_Contratacao": deadline,
            "Valor_Total_Estimado": v_total,
            "Valor_Estimado_2027": v_2027,
            "Valor_Contratado": v_contratado,
            "Unidade_Orcamentaria": u_orc,
            "Previsto_PCA": previsto,
        })

    df = pd.DataFrame(records)

    # Data de modificação no fuso de Brasília
    updated_at = datetime.fromtimestamp(PCA_CACHE_FILE.stat().st_mtime, tz=timezone.utc).astimezone(TZ_BRASILIA).replace(tzinfo=None)
    return df, updated_at
