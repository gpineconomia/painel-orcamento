"""Download da planilha do SharePoint (link anônimo) e leitura em DataFrame."""
from __future__ import annotations

import io
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
import requests
from dotenv import load_dotenv

TZ_BRASILIA = timezone(timedelta(hours=-3))


def to_brasilia_datetime(ts: float | int) -> datetime:
    """Converte timestamp Unix para datetime no fuso de Brasília (UTC-3)."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(TZ_BRASILIA).replace(tzinfo=None)

# Usa os certificados do sistema quando disponível (inclui a CA do governo no Windows).
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass

try:  # Autenticação Windows integrada (NTLM/Kerberos) com o usuário logado
    from requests_negotiate_sspi import HttpNegotiateAuth

    _AUTH = HttpNegotiateAuth()
except ImportError:  # fora do Windows / nuvem Linux (Streamlit Cloud)
    _AUTH = None

URL_2026_DEFAULT = (
    "https://gestaocolaborativa.economia.go.gov.br/sites/planejamento/orcamento/Documentos%20Compartilhados/2026/"
    "Gestao%20Orcamentaria%202026.xlsx?d=wf0c5e5b267234204ba5852af85d262a1"
)
URL_2027_DEFAULT = (
    "https://gestaocolaborativa.economia.go.gov.br/sites/planejamento/orcamento/Documentos%20Compartilhados/2027/PLOA%202027/"
    "Gestao%20Orcamentaria%20PLOA%202027.xlsx?d=w76075f5ab8a34d75950b6cddcab18c01"
)
URL_SUPRESSOES_2027_DEFAULT = (
    "https://gestaocolaborativa.economia.go.gov.br/sites/planejamento/orcamento/Documentos%20Compartilhados/2027/PLOA%202027/"
    "Supressoes%202027.xlsx?d=wb31fd57c9556440283b522a1c0457c59"
)
URL_DEFICIT_2027_DEFAULT = (
    "https://gestaocolaborativa.economia.go.gov.br/sites/planejamento/orcamento/Documentos%20Compartilhados/2027/PLOA%202027/"
    "Dados%20para%20apresenta%C3%A7%C3%A3o%20para%20Or%C3%A7amento%20central.xlsx?d=w474065bad2f84e74aba3b3f5119c9a14"
)

BASE_DIR = Path(__file__).parent
CACHE_FILE_2026 = BASE_DIR / "data" / "planilha_2026_cache.xlsx"
CACHE_FILE_2027 = BASE_DIR / "data" / "planilha_cache.xlsx"
CACHE_FILE_SUPRESSOES_2027 = BASE_DIR / "data" / "supressoes_2027_cache.xlsx"
CACHE_FILE_DEFICIT_2027 = BASE_DIR / "data" / "deficit_2027_cache.xlsx"
CACHE_FILE = CACHE_FILE_2027  # compatibilidade

load_dotenv(BASE_DIR / ".env")


def get_settings(ano: int = 2026) -> dict:
    if ano == 2026:
        url = os.getenv("SHAREPOINT_URL_2026", URL_2026_DEFAULT).strip()
        title = os.getenv("DASHBOARD_TITLE_2026", "Orçamento 2026 — Em Execução")
    else:
        url = os.getenv("SHAREPOINT_URL_2027", os.getenv("SHAREPOINT_URL", URL_2027_DEFAULT)).strip()
        title = os.getenv("DASHBOARD_TITLE_2027", os.getenv("DASHBOARD_TITLE", "Orçamento 2027 — Planejamento PLOA"))

    return {
        "url": url,
        "sheet": os.getenv("SHEET_NAME", "Contratos").strip() or "Contratos",
        "refresh_minutes": int(os.getenv("REFRESH_MINUTES", "60")),
        "title": title,
        "ano": ano,
    }


def _direct_download_url(url: str) -> str:
    """Monta a URL de download direto.

    - Link direto para o arquivo (…/arquivo.xlsx?d=…): remove a query, que faria
      o SharePoint abrir a página de visualização em HTML.
    - Link de compartilhamento anônimo (sharepoint.com/:x:/…): força download=1.
    """
    parts = urlparse(url)
    if parts.path.lower().endswith((".xlsx", ".xlsm")):
        return urlunparse(parts._replace(query=""))
    query = dict(parse_qsl(parts.query))
    query["download"] = "1"
    return urlunparse(parts._replace(query=urlencode(query)))


def download_workbook(url: str) -> bytes:
    resp = requests.get(
        _direct_download_url(url),
        timeout=(5, 25),
        allow_redirects=True,
        auth=_AUTH,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    resp.raise_for_status()
    content = resp.content
    # Arquivos .xlsx são ZIPs (começam com "PK"). Se vier HTML, o link exige login.
    if not content.startswith(b"PK"):
        raise RuntimeError(
            "O link não retornou um arquivo Excel. Verifique se o link aponta "
            "para o arquivo .xlsx e se você tem permissão de acesso."
        )
    return content


def is_xlsx_content_equal(new_bytes: bytes, existing_bytes: bytes) -> bool:
    """Compara o conteúdo real das planilhas em arquivos XLSX ignorando metadados de timestamp/criação do ZIP."""
    if new_bytes == existing_bytes:
        return True
    try:
        import hashlib
        import io
        import zipfile

        def get_hash(raw: bytes) -> str:
            h = hashlib.sha256()
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for name in sorted(zf.namelist()):
                    if name.startswith("xl/worksheets/") or name.startswith("xl/sharedStrings"):
                        h.update(zf.read(name))
            return h.hexdigest()

        return get_hash(new_bytes) == get_hash(existing_bytes)
    except Exception:
        return False


GITHUB_RAW_BASE = "https://raw.githubusercontent.com/gpineconomia/painel-orcamento/main/data"


def fetch_from_github_cloud(filename: str, cache_file: Path) -> bool:
    """Na nuvem Streamlit Cloud (_AUTH is None), busca o arquivo mais recente diretamente do repositório público do GitHub."""
    if _AUTH is not None:
        return False
    try:
        import time
        url = f"{GITHUB_RAW_BASE}/{filename}?_t={int(time.time())}"
        resp = requests.get(url, timeout=20, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"})
        if resp.status_code == 200 and len(resp.content) > 500:
            if not cache_file.exists() or not is_xlsx_content_equal(resp.content, cache_file.read_bytes()):
                cache_file.write_bytes(resp.content)
            return True
    except Exception:
        pass
    return False


def load_data(ano: int = 2026) -> tuple[pd.DataFrame, datetime, str | None]:
    """Retorna (dataframe, momento_da_atualizacao, aviso).

    Em caso de falha de rede, usa o último arquivo salvo em cache (com aviso).
    """
    cfg = get_settings(ano=ano)
    warning = None
    cache_file = CACHE_FILE_2026 if ano == 2026 else CACHE_FILE_2027
    cache_file.parent.mkdir(exist_ok=True)
    filename = cache_file.name

    if _AUTH is not None:
        try:
            if not cfg["url"]:
                raise RuntimeError(f"SHAREPOINT_URL para {ano} não configurada.")
            new_content = download_workbook(cfg["url"])
            if not cache_file.exists() or not is_xlsx_content_equal(new_content, cache_file.read_bytes()):
                cache_file.write_bytes(new_content)
        except Exception as exc:  # noqa: BLE001
            if not cache_file.exists():
                raise
            warning = f"Não foi possível atualizar da fonte ({exc}). Exibindo dados do cache."
    else:
        fetch_from_github_cloud(filename, cache_file)

    raw = pd.read_excel(io.BytesIO(cache_file.read_bytes()), sheet_name=cfg["sheet"], header=None)
    raw = raw.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    df = _promote_header(raw)
    updated = to_brasilia_datetime(cache_file.stat().st_mtime)
    return df, updated, warning


def _promote_header(raw: pd.DataFrame) -> pd.DataFrame:
    """Usa como cabeçalho a linha (entre as 15 primeiras) com mais células preenchidas."""
    header_idx = int(raw.head(15).notna().sum(axis=1).idxmax())
    names, seen = [], {}
    for i, v in enumerate(raw.iloc[header_idx]):
        name = " ".join(str(v).split()) if pd.notna(v) else f"Coluna {i + 1}"
        seen[name] = seen.get(name, 0) + 1
        names.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    df = raw.iloc[header_idx + 1:].copy()
    df.columns = names
    df = df.dropna(how="all").reset_index(drop=True)

    for col in df.columns:
        if df[col].dtype == object:
            as_num = pd.to_numeric(df[col], errors="coerce")
            if as_num.notna().sum() >= 0.8 * df[col].notna().sum() > 0:
                df[col] = as_num
    return df


def load_supressoes_2027() -> tuple[pd.DataFrame, datetime, str | None]:
    """Retorna (df_supressoes, momento_da_atualizacao, aviso)."""
    warning = None
    cache_file = CACHE_FILE_SUPRESSOES_2027
    cache_file.parent.mkdir(exist_ok=True)
    url = os.getenv("SHAREPOINT_URL_SUPRESSOES_2027", URL_SUPRESSOES_2027_DEFAULT).strip()
    filename = cache_file.name

    if _AUTH is not None:
        try:
            if url:
                new_content = download_workbook(url)
                if not cache_file.exists() or not is_xlsx_content_equal(new_content, cache_file.read_bytes()):
                    cache_file.write_bytes(new_content)
        except Exception as exc:  # noqa: BLE001
            if not cache_file.exists():
                raise
            warning = f"Não foi possível atualizar Supressões da fonte ({exc}). Exibindo dados do cache."
    else:
        fetch_from_github_cloud(filename, cache_file)

    raw = pd.read_excel(io.BytesIO(cache_file.read_bytes()), sheet_name=0, header=None)
    records = []
    current_u = ""
    for i in range(len(raw)):
        row = raw.iloc[i]
        u = str(row[1]).strip() if pd.notna(row[1]) else ""
        item = str(row[2]).strip() if pd.notna(row[2]) else ""
        orc = row[3]
        acao = str(row[4]).strip() if pd.notna(row[4]) else ""
        teto = row[5]
        econ = row[6]

        if u in ["Unidade", ""] and not item:
            continue
        if u and u not in ["Unidade"]:
            current_u = u

        if item and pd.notna(orc) and pd.notna(teto):
            try:
                orc_f = float(orc)
                teto_f = float(teto)
                econ_f = float(econ) if pd.notna(econ) else (orc_f - teto_f)
                records.append({
                    "Unidade": current_u or u,
                    "Item de Despesa": item,
                    "Orçamento 2027": orc_f,
                    "Ação Sugerida": acao if acao != "nan" else "",
                    "Teto Ajustado 2027": teto_f,
                    "Economia Gerada": econ_f,
                })
            except (ValueError, TypeError):
                pass

    df = pd.DataFrame(records)
    if not df.empty:
        df["% Redução"] = (df["Economia Gerada"] / df["Orçamento 2027"] * 100).fillna(0.0)
    updated = to_brasilia_datetime(cache_file.stat().st_mtime)
    return df, updated, warning


def load_deficit_2027() -> tuple[pd.DataFrame, datetime, str | None]:
    """Retorna (df_deficit, momento_da_atualizacao, aviso) da aba 'Rascunhos - Déficit'."""
    warning = None
    cache_file = CACHE_FILE_DEFICIT_2027
    cache_file.parent.mkdir(exist_ok=True)
    url = os.getenv("SHAREPOINT_URL_DEFICIT_2027", URL_DEFICIT_2027_DEFAULT).strip()
    filename = cache_file.name

    if _AUTH is not None:
        try:
            if url:
                new_content = download_workbook(url)
                if not cache_file.exists() or not is_xlsx_content_equal(new_content, cache_file.read_bytes()):
                    cache_file.write_bytes(new_content)
        except Exception as exc:  # noqa: BLE001
            if not cache_file.exists():
                raise
            warning = f"Não foi possível atualizar Déficit da fonte ({exc}). Exibindo dados do cache."
    else:
        fetch_from_github_cloud(filename, cache_file)

    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(cache_file.read_bytes()), data_only=True)
    sheet_matches = [s for s in wb.sheetnames if "d" in s.lower() and "ficit" in s.lower()]
    sheet_name = sheet_matches[0] if sheet_matches else wb.sheetnames[0]
    ws = wb[sheet_name]

    unit_map = {
        "business analytics": "Tecnologia da Informação",
        "sefaz/rs": "Receita",
        "licenças microsoft": "Tecnologia da Informação",
        "licencas microsoft": "Tecnologia da Informação",
        "sap": "Tecnologia da Informação",
        "inteligência artificial": "Tecnologia da Informação",
        "inteligencia artificial": "Tecnologia da Informação",
        "software assurance": "Tecnologia da Informação",
        "ar condicionado": "Gestão Integrada",
        "empilhadeira": "Receita",
        "satélite": "Receita",
        "satelite": "Receita",
        "govtech": "Receita",
        "capacitação": "Gestão Integrada",
        "capacitacao": "Gestão Integrada",
        "serviços gerais": "Gestão Integrada",
        "servicos gerais": "Gestão Integrada",
        "ocr fixo": "Receita",
        "call center": "Receita/Gestão Integrada",
        "eventos": "Gestão Integrada",
        "antivirus": "Tecnologia da Informação",
        "furgões": "Receita",
        "furgoes": "Receita",
        "corrida de rua": "Gestão Integrada",
        "monitoramento": "Gestão Integrada",
        "infraestrutura": "Tecnologia da Informação",
        "nível superior": "Gestão Integrada",
        "nivel superior": "Gestão Integrada",
        "nível médio": "Gestão Integrada",
        "nivel medio": "Gestão Integrada",
        "desenvolvimento": "Tecnologia da Informação",
    }

    start_row = 8
    for r in range(1, 15):
        val = ws.cell(row=r, column=3).value
        if val and "despesa" in str(val).lower():
            start_row = r + 1
            break

    records = []
    for r in range(start_row, 50):
        desp = ws.cell(row=r, column=3).value
        prazo_raw = ws.cell(row=r, column=4).value
        val = ws.cell(row=r, column=5).value

        if not desp or str(desp).strip().lower() == "total":
            break

        desp_str = str(desp).strip()
        desp_lower = desp_str.lower()
        val_f = float(val) if val is not None else 0.0

        if isinstance(prazo_raw, datetime):
            dt_str = prazo_raw.strftime("%m/%Y")
            mes_nome = {
                "12/2026": "Dezembro/2026",
                "01/2027": "Janeiro/2027",
                "02/2027": "Fevereiro/2027",
                "03/2027": "Março/2027",
                "06/2027": "Junho/2027",
                "09/2027": "Setembro/2027",
                "10/2027": "Outubro/2027",
            }.get(dt_str, dt_str)
            ordem = {
                "12/2026": 1,
                "01/2027": 2,
                "02/2027": 3,
                "03/2027": 4,
                "06/2027": 5,
                "09/2027": 6,
                "10/2027": 7,
            }.get(dt_str, 8)
            prazo_label = mes_nome
            prazo_cat = "Calendário PLOA"
        elif isinstance(prazo_raw, str):
            p_clean = prazo_raw.strip().lower()
            if "imediato" in p_clean:
                prazo_label = "Imediato"
                ordem = 0
                prazo_cat = "Imediato / Urgente"
            elif "judicial" in p_clean:
                prazo_label = "Pendente Judicial"
                ordem = 8
                prazo_cat = "Imediato / Urgente"
            elif "indeterminado" in p_clean:
                # No cronograma oficial da PLOA, o Convênio SEFAZ/RS está alocado em Janeiro/2027
                if "sefaz" in desp_lower:
                    prazo_label = "Janeiro/2027"
                    ordem = 2
                    prazo_cat = "Calendário PLOA"
                else:
                    prazo_label = "Indeterminado"
                    ordem = 9
                    prazo_cat = "Indeterminado"
            else:
                prazo_label = prazo_raw.strip().capitalize()
                ordem = 11
                prazo_cat = "Outros"
        else:
            prazo_label = "Não Informado"
            ordem = 12
            prazo_cat = "Outros"

        unidade = "Outros"
        for kw, u in unit_map.items():
            if kw in desp_lower:
                unidade = u
                break

        if "nova contrata" in desp_lower:
            tipo = "Nova Contratação"
        elif "prorroga" in desp_lower:
            tipo = "Prorrogação"
        elif "vigente" in desp_lower:
            tipo = "Contrato Vigente"
        elif "complementar" in desp_lower:
            tipo = "Complementar"
        else:
            tipo = "Outros"

        records.append({
            "Despesa": desp_str,
            "Unidade": unidade,
            "Tipo_Demanda": tipo,
            "Prazo": prazo_label,
            "Categoria_Prazo": prazo_cat,
            "Ordem_Cronologica": ordem,
            "Valor": val_f,
        })

    df = pd.DataFrame(records)
    tot_val = df["Valor"].sum() if not df.empty else 0.0
    if not df.empty and tot_val > 0:
        df["% do Déficit"] = (df["Valor"] / tot_val * 100).round(2)
    updated = to_brasilia_datetime(cache_file.stat().st_mtime) if cache_file.exists() else datetime.now()
    return df, updated, warning


