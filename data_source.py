"""Download da planilha do SharePoint (link anônimo) e leitura em DataFrame."""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
import requests
from dotenv import load_dotenv

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

BASE_DIR = Path(__file__).parent
CACHE_FILE_2026 = BASE_DIR / "data" / "planilha_2026_cache.xlsx"
CACHE_FILE_2027 = BASE_DIR / "data" / "planilha_cache.xlsx"
CACHE_FILE_SUPRESSOES_2027 = BASE_DIR / "data" / "supressoes_2027_cache.xlsx"
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


GITHUB_RAW_BASE = "https://raw.githubusercontent.com/gpineconomia/painel-orcamento/main/data"


def fetch_from_github_cloud(filename: str, cache_file: Path) -> bool:
    """Na nuvem Streamlit Cloud (_AUTH is None), busca o arquivo mais recente diretamente do repositório público do GitHub."""
    if _AUTH is not None:
        return False
    try:
        import time
        url = f"{GITHUB_RAW_BASE}/{filename}?_t={int(time.time())}"
        resp = requests.get(url, timeout=20, headers={"Cache-Control": "no-cache"})
        if resp.status_code == 200 and len(resp.content) > 500:
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
            cache_file.write_bytes(download_workbook(cfg["url"]))
        except Exception as exc:  # noqa: BLE001
            if not cache_file.exists():
                raise
            warning = f"Não foi possível atualizar da fonte ({exc}). Exibindo dados do cache."
    else:
        fetch_from_github_cloud(filename, cache_file)

    raw = pd.read_excel(io.BytesIO(cache_file.read_bytes()), sheet_name=cfg["sheet"], header=None)
    raw = raw.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    df = _promote_header(raw)
    updated = datetime.fromtimestamp(cache_file.stat().st_mtime)
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
                cache_file.write_bytes(download_workbook(url))
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
    updated = datetime.fromtimestamp(cache_file.stat().st_mtime)
    return df, updated, warning


