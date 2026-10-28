"""Módulo para download, cache e estruturação dos dados do PCA 2027 (Google Sheets - SETRAC)."""
from __future__ import annotations

import io
import os
import re
import unicodedata
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


def normalizar_chave(s: str) -> str:
    """Normaliza texto para comparação sem acentos, maiúsculas e sem pontuação."""
    if not s or str(s).strip() in ["", "-", "nan", "None"]:
        return ""
    s_norm = unicodedata.normalize("NFKD", str(s).upper()).encode("ASCII", "ignore").decode("ASCII")
    return re.sub(r"[^A-Z0-9]", "", s_norm)


CANONICAL_SUPERIORES = {
    normalizar_chave("Gabinete"): "Gabinete",
    normalizar_chave("Subsecretaria da Receita Estadual"): "Subsecretaria da Receita Estadual",
    normalizar_chave("Superintendência Central de Contabilidade"): "Superintendência Central de Contabilidade",
    normalizar_chave("Superintendência de Controle e Auditoria"): "Superintendência de Controle e Auditoria",
    normalizar_chave("Superintendência de Fiscalização Regionalizada"): "Superintendência de Fiscalização Regionalizada",
    normalizar_chave("Superintendência de Gestão Integrada"): "Superintendência de Gestão Integrada",
    normalizar_chave("Superintendência de Informações Fiscais"): "Superintendência de Informações Fiscais",
    normalizar_chave("Superintendência de Recuperação de Créditos"): "Superintendência de Recuperação de Créditos",
    normalizar_chave("Superintendência de Tecnologia da Informação"): "Superintendência de Tecnologia da Informação",
    normalizar_chave("SUPERINTENDÊNCIA DE TECNOLOGIA DA INFORMAÇÃO"): "Superintendência de Tecnologia da Informação",
    normalizar_chave("Superintendência Financeira"): "Superintendência Financeira",
}

CANONICAL_DEMANDANTES = {
    normalizar_chave("Gerência de Engenharia e Arquitetura"): "Gerência de Engenharia e Arquitetura",
    normalizar_chave("GERÊNCIA DE ENGENHARIA E ARQUITETURA"): "Gerência de Engenharia e Arquitetura",
    normalizar_chave("Gerência de Suporte Técnico"): "Gerência de Suporte Técnico",
    normalizar_chave("GERÊNCIA DE SUPORTE TÉCNICO"): "Gerência de Suporte Técnico",
    normalizar_chave("Gerência da Dívida Pública e Receita Extratributária"): "Gerência da Dívida Pública e Receita Extratributária",
    normalizar_chave("GERÊNCIA DA DÍVIDA PÚBLICA E RECEIRTA EXTRATRIBUTÁRIA"): "Gerência da Dívida Pública e Receita Extratributária",
    normalizar_chave("Gerência de Dados e Inteligência Analítica"): "Gerência de Dados e Inteligência Analítica",
    normalizar_chave("GERÊNCIA DE DADOS E INTELIGÊNCIA ANALÍTICA"): "Gerência de Dados e Inteligência Analítica",
    normalizar_chave("Gerência de Desenvolvimento de Sistemas"): "Gerência de Desenvolvimento de Sistemas",
    normalizar_chave("GERÊNCIA DE DESENVOLVIMENTO DE SISTEMAS"): "Gerência de Desenvolvimento de Sistemas",
    normalizar_chave("Gerência de Acompanhamento de Custos e Avaliação de Resultados"): "Gerência de Acompanhamento de Custos e Avaliação de Resultados",
    normalizar_chave("GERÊNCIA DE ACOMPANHAMENTO DE CUSTOS E AVALIAÇÃO DE RESULTADOS"): "Gerência de Acompanhamento de Custos e Avaliação de Resultados",
    normalizar_chave("Gerência de Arrecadação e Fiscalização"): "Gerência de Arrecadação e Fiscalização",
    normalizar_chave("GERÊNCIA DE ARRECADAÇÃO E FISCALIZAÇÃO"): "Gerência de Arrecadação e Fiscalização",
    normalizar_chave("Subsecretaria da Receita Estadual"): "Subsecretaria da Receita Estadual",
    normalizar_chave("SUBSECRETARIA DA RECEITA ESTADUAL"): "Subsecretaria da Receita Estadual",
    normalizar_chave("Comunicação Setorial"): "Comunicação Setorial",
    normalizar_chave("COMUNICAÇÃO SETORIAL"): "Comunicação Setorial",
    normalizar_chave("Aquisições e Contratos da SFR"): "Aquisições e Contratos da SFR",
    normalizar_chave("AQUISIÇÕES E CONTRATOS DA SFR"): "Aquisições e Contratos da SFR",
    normalizar_chave("Superintendência de Tecnologia da Informação"): "Superintendência de Tecnologia da Informação",
    normalizar_chave("Superintendência Financeira"): "Superintendência Financeira",
    normalizar_chave("Superintendência de Fiscalização Regionalizada"): "Superintendência de Fiscalização Regionalizada",
}


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
    from data_source import is_xlsx_content_equal
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(PCA_GSHEET_URL, timeout=timeout)
        if resp.status_code == 200 and resp.content.startswith(b"PK"):
            if not PCA_CACHE_FILE.exists() or not is_xlsx_content_equal(resp.content, PCA_CACHE_FILE.read_bytes()):
                PCA_CACHE_FILE.write_bytes(resp.content)
            return True
    except Exception as e:
        print(f"Aviso ao baixar PCA do Google Sheets: {e}")

    # Fallback se estiver na nuvem ou falhar a conexão com o Google
    try:
        resp_gh = requests.get(PCA_GITHUB_RAW_URL, timeout=15)
        if resp_gh.status_code == 200 and resp_gh.content.startswith(b"PK"):
            if not PCA_CACHE_FILE.exists() or not is_xlsx_content_equal(resp_gh.content, PCA_CACHE_FILE.read_bytes()):
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
        u_sup = CANONICAL_SUPERIORES.get(normalizar_chave(u_sup), u_sup)

        u_dem = str(row.get(c_uni_dem, "")).strip() if c_uni_dem and pd.notna(row.get(c_uni_dem)) else u_sup
        u_dem = CANONICAL_DEMANDANTES.get(normalizar_chave(u_dem), u_dem)

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
