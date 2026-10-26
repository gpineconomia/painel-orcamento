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
import plotly.express as px
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

    xls = pd.ExcelFile(CACHE_FILE)
    sheet_name = "Contratações 2026" if "Contratações 2026" in xls.sheet_names else xls.sheet_names[0]
    df = pd.read_excel(CACHE_FILE, sheet_name=sheet_name)

    # Data de sincronização oficial formatada (ex: 26/10/2026 às 11:45)
    mtime = CACHE_FILE.stat().st_mtime
    dt = datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone(TZ_BRASILIA)
    data_atualizacao = dt.strftime("%d/%m/%Y às %H:%M")

    df.columns = [str(c).strip() for c in df.columns]

    if "Objeto" in df.columns:
        df = df[df["Objeto"].notna()].copy()
        df = df[~df["Objeto"].astype(str).str.contains(r"Data da Atualiza", case=False, na=False)].copy()

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


def _card_html(row: pd.Series | dict) -> str:
    """Gera o HTML estruturado e seguro para os cartões de demanda, evitando problemas de indentação do Markdown."""
    prio = str(row.get("Prioridade", "Não informada")).strip()
    if prio == "Alta":
        borda_cor = "#EF4444"
        bg_chip = "#FEF2F2"
        txt_chip = "#DC2626"
        border_chip = "#FCA5A5"
    elif prio == "Média":
        borda_cor = "#F59E0B"
        bg_chip = "#FFFBEB"
        txt_chip = "#D97706"
        border_chip = "#FCD34D"
    elif prio == "Baixa":
        borda_cor = "#10B981"
        bg_chip = "#F0FDF4"
        txt_chip = "#16A34A"
        border_chip = "#86EFAC"
    else:
        borda_cor = "#94A3B8"
        bg_chip = "#F8FAFC"
        txt_chip = "#64748B"
        border_chip = "#CBD5E1"

    atencao = str(row.get("Ponto de Atenção", "-")).strip()
    atencao_html = ""
    if atencao and atencao != "-" and atencao.lower() != "nan":
        atencao_html = (
            f'<div style="background:#FFFBEB; border:1px solid #FDE68A; border-left:4px solid #F59E0B; '
            f'border-radius:6px; padding:6px 12px; margin:8px 0; color:#92400E; font-size:0.88rem;">'
            f'<b>⚠️ Ponto de Atenção:</b> {atencao}</div>'
        )

    sei = str(row.get("Número SEI", "-")).strip()
    if not sei or sei.lower() == "nan":
        sei = "-"
    sislog = str(row.get("Número da Contratação SISLOG", "-")).strip()
    if not sislog or sislog.lower() == "nan":
        sislog = "-"
    resp = str(row.get("Responsável", "-")).strip()
    if not resp or resp.lower() in ["nan", "none"]:
        resp = "A definir"
    tipo = str(row.get("Tipo", "-")).strip()
    status = str(row.get("Status da Contratação", "-")).strip()
    unid = str(row.get("Unidade Demandante", "-")).strip()
    parecer = str(row.get("Necessitará de Parecer Jurídico", "-")).strip()
    prev_2026 = str(row.get("Prevista para 2026?", "-")).strip()
    prev_color = "#16A34A" if prev_2026 == "Sim" else ("#DC2626" if prev_2026 == "Não" else "#64748B")
    obj = str(row.get("Objeto", "-")).strip()

    return (
        f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:6px solid {borda_cor}; '
        f'border-radius:10px; padding:14px 18px; margin-bottom:12px; box-shadow:0 1px 4px rgba(0,0,0,0.04);">'
        f'<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:6px; flex-wrap:wrap;">'
        f'<div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">'
        f'<span style="background:{bg_chip}; color:{txt_chip}; border:1px solid {border_chip}; padding:3px 10px; border-radius:6px; font-size:0.82rem; font-weight:700; text-transform:uppercase;">● {prio}</span>'
        f'<span style="background:#F1F5F9; color:#334155; padding:3px 9px; border-radius:6px; font-size:0.82rem; font-weight:600;">🏢 {unid}</span>'
        f'<span style="background:#F8FAFC; color:#64748B; border:1px solid #E2E8F0; padding:3px 9px; border-radius:6px; font-size:0.82rem;">📑 {tipo}</span>'
        f'</div>'
        f'<span style="background:#EFF6FF; color:#1D4ED8; border:1px solid #DBEAFE; padding:3px 10px; border-radius:6px; font-size:0.82rem; font-weight:600;">🔄 {status}</span>'
        f'</div>'
        f'<div style="font-size:1.05rem; font-weight:700; color:#0F172A; margin:6px 0 8px 0; line-height:1.4;">📦 {obj}</div>'
        f'{atencao_html}'
        f'<div style="display:flex; gap:16px; flex-wrap:wrap; font-size:0.82rem; color:#64748B; padding-top:8px; border-top:1px solid #F1F5F9; margin-top:6px;">'
        f'<span>📋 <b>SEI:</b> <code style="color:#0F172A; background:#F1F5F9; padding:2px 6px; border-radius:4px; font-family:monospace;">{sei}</code></span>'
        f'<span>🔢 <b>SISLOG:</b> <b style="color:#334155;">{sislog}</b></span>'
        f'<span>👤 <b>Responsável:</b> <b style="color:#334155;">{resp}</b></span>'
        f'<span>⚖️ <b>Parecer Jurídico:</b> <b style="color:#334155;">{parecer}</b></span>'
        f'<span>📅 <b>Prev. 2026:</b> <b style="color:{prev_color};">{prev_2026}</b></span>'
        f'</div>'
        f'</div>'
    )


def render_contratacoes_dashboard(key_prefix: str = "") -> None:
    """Renderiza a visualização completa do painel de contratações 2026."""
    try:
        df_raw, data_base = load_contratacoes_2026()
    except Exception as exc:
        st.error(f"Erro ao carregar dados de Contratações 2026: {exc}")
        return

    if df_raw.empty:
        st.warning("Não há contratações registradas para exibição.")
        return

    # Cabeçalho Oficial idêntico ao das outras abas (Execução 2026, Indicações e Liquidação)
    st.html(
        f"""<div style="background:#0F2A20; border-radius:12px; padding:12px 24px; margin-bottom:1.1rem;
                    display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                    box-shadow: 0 4px 14px rgba(15,42,32,0.18); flex-wrap:wrap; gap:12px;">
          <div>
            <h2 style="margin:0; font-size:1.55rem; font-weight:700; color:#FFFFFF; letter-spacing:-0.02em;">
              📋 Acompanhamento das Contratações · Execução 2026
            </h2>
          </div>
          <div style="font-size:0.85rem; color:#A7F3D0; text-align:right;">
            <strong>Fonte Oficial:</strong> GELC<br>
            <span style="font-size:0.75rem; color:#D1FAE5;">Sincronizado em: {data_base}</span>
          </div>
        </div>"""
    )

    # Filtros em expander ou na própria view
    with st.expander("🔍 Filtros de Consulta de Contratações", expanded=False):
        fcol1, fcol2, fcol3 = st.columns(3)
        with fcol1:
            unidades_disp = sorted([u for u in df_raw["Unidade Demandante"].dropna().unique() if u])
            sel_unidades = st.multiselect("Unidade Demandante", options=unidades_disp, default=[], key=f"{key_prefix}unid")
            prioridades_ordem = ["Alta", "Média", "Baixa", "Não informada"]
            prioridades_disp = [p for p in prioridades_ordem if p in df_raw["Prioridade"].values]
            sel_prioridade = st.multiselect("Prioridade", options=prioridades_disp, default=[], key=f"{key_prefix}prio")
        with fcol2:
            tipos_disp = sorted([t for t in df_raw["Tipo"].dropna().unique() if t])
            sel_tipos = st.multiselect("Tipo de Demanda", options=tipos_disp, default=[], key=f"{key_prefix}tipo")
            status_disp = sorted([s for s in df_raw["Status da Contratação"].dropna().unique() if s])
            sel_status = st.multiselect("Status da Contratação", options=status_disp, default=[], key=f"{key_prefix}stat")
        with fcol3:
            prev_opts = ["Todas", "Sim", "Não"]
            sel_prev = st.selectbox("Prevista para 2026?", options=prev_opts, index=0, key=f"{key_prefix}prev")
            busca_texto = st.text_input("Buscar por Objeto, SEI ou SISLOG", placeholder="Ex: OCR, 2026...", key=f"{key_prefix}txt").strip().lower()

    # Aplicação de filtros
    df_f = df_raw.copy()
    if sel_unidades:
        df_f = df_f[df_f["Unidade Demandante"].isin(sel_unidades)]
    if sel_prioridade:
        df_f = df_f[df_f["Prioridade"].isin(sel_prioridade)]
    if sel_tipos:
        df_f = df_f[df_f["Tipo"].isin(sel_tipos)]
    if sel_status:
        df_f = df_f[df_f["Status da Contratação"].isin(sel_status)]
    if sel_prev != "Todas":
        df_f = df_f[df_f["Prevista para 2026?"] == sel_prev]
    if busca_texto:
        mask = (
            df_f["Objeto"].astype(str).str.lower().str.contains(busca_texto, na=False)
            | df_f["Número SEI"].astype(str).str.lower().str.contains(busca_texto, na=False)
            | df_f["Número da Contratação SISLOG"].astype(str).str.lower().str.contains(busca_texto, na=False)
            | df_f["Ponto de Atenção"].astype(str).str.lower().str.contains(busca_texto, na=False)
            | df_f["Responsável"].astype(str).str.lower().str.contains(busca_texto, na=False)
        )
        df_f = df_f[mask]

    # KPIs
    total_cadastrados = len(df_raw)
    total_filtrados = len(df_f)
    prev_2026_count = (df_f["Prevista para 2026?"] == "Sim").sum()
    prev_2026_pct = (prev_2026_count / total_filtrados * 100) if total_filtrados > 0 else 0
    alta_count = (df_f["Prioridade"] == "Alta").sum()
    alta_pct = (alta_count / total_filtrados * 100) if total_filtrados > 0 else 0
    novas_count = (df_f["Tipo"] == "Nova Contratação").sum()
    fase_prep_count = (df_f["Status da Contratação"] == "Fase Preparatória").sum()
    pontos_atencao_count = (df_f["Ponto de Atenção"] != "-").sum()

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    with kpi1:
        st.markdown(
            f"""
            <div style="background:#FFF; border-radius:10px; padding:1rem; border:1px solid #E2E8F0; border-top:4px solid #3B82F6; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="font-size:0.8rem; color:#64748B; font-weight:600; text-transform:uppercase;">Total de Processos</div>
                <div style="font-size:1.8rem; font-weight:700; color:#1E293B; margin:0.2rem 0;">{total_filtrados}</div>
                <div style="font-size:0.75rem; color:#94A3B8;">de {total_cadastrados} na base geral</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi2:
        st.markdown(
            f"""
            <div style="background:#FFF; border-radius:10px; padding:1rem; border:1px solid #E2E8F0; border-top:4px solid #10B981; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="font-size:0.8rem; color:#64748B; font-weight:600; text-transform:uppercase;">Previstas para 2026</div>
                <div style="font-size:1.8rem; font-weight:700; color:#10B981; margin:0.2rem 0;">{prev_2026_count}</div>
                <div style="font-size:0.75rem; color:#94A3B8;">{prev_2026_pct:.1f}% do total</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi3:
        st.markdown(
            f"""
            <div style="background:#FFF; border-radius:10px; padding:1rem; border:1px solid #E2E8F0; border-top:4px solid #EF4444; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="font-size:0.8rem; color:#64748B; font-weight:600; text-transform:uppercase;">Prioridade Alta</div>
                <div style="font-size:1.8rem; font-weight:700; color:#EF4444; margin:0.2rem 0;">{alta_count}</div>
                <div style="font-size:0.75rem; color:#94A3B8;">{alta_pct:.1f}% com máxima atenção</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi4:
        st.markdown(
            f"""
            <div style="background:#FFF; border-radius:10px; padding:1rem; border:1px solid #E2E8F0; border-top:4px solid #8B5CF6; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="font-size:0.8rem; color:#64748B; font-weight:600; text-transform:uppercase;">Novas Contratações</div>
                <div style="font-size:1.8rem; font-weight:700; color:#8B5CF6; margin:0.2rem 0;">{novas_count}</div>
                <div style="font-size:0.75rem; color:#94A3B8;">{((novas_count/total_filtrados*100) if total_filtrados else 0):.1f}% das demandas</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi5:
        st.markdown(
            f"""
            <div style="background:#FFF; border-radius:10px; padding:1rem; border:1px solid #E2E8F0; border-top:4px solid #F59E0B; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="font-size:0.8rem; color:#64748B; font-weight:600; text-transform:uppercase;">Em Fase Preparatória</div>
                <div style="font-size:1.8rem; font-weight:700; color:#F59E0B; margin:0.2rem 0;">{fase_prep_count}</div>
                <div style="font-size:0.75rem; color:#94A3B8;">{pontos_atencao_count} com atenção</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-bottom: 1.2rem;'></div>", unsafe_allow_html=True)

    # Sub-abas: A primeira é a nova aba de Resumo por Prioridades (da maior para a menor)
    sub_resumo, sub_graf, sub_atencao, sub_tab = st.tabs([
        "⚡ Resumo por Prioridades",
        "📊 Gráficos Analíticos",
        "⚠️ Pontos de Atenção",
        "📑 Tabela Completa",
    ])

    # -------------------------------------------------------------- ABA 1: RESUMO POR PRIORIDADES (INICIAL)
    with sub_resumo:
        # Mini painel de resumo rápido das prioridades
        prio_counts = df_f["Prioridade"].value_counts()
        c_alta = prio_counts.get("Alta", 0)
        c_media = prio_counts.get("Média", 0)
        c_baixa = prio_counts.get("Baixa", 0)
        c_nao_inf = prio_counts.get("Não informada", 0)

        st.markdown(
            f"""
            <div style="display:flex; gap:12px; margin-bottom:14px; flex-wrap:wrap;">
                <div style="background:#FEF2F2; border:1px solid #FCA5A5; border-radius:8px; padding:8px 16px; font-size:0.88rem; color:#991B1B; font-weight:500;">
                    🔴 <b>Alta Prioridade:</b> <span style="font-size:1.15rem; font-weight:700;">{c_alta}</span> demandas
                </div>
                <div style="background:#FFFBEB; border:1px solid #FCD34D; border-radius:8px; padding:8px 16px; font-size:0.88rem; color:#92400E; font-weight:500;">
                    🟡 <b>Média Prioridade:</b> <span style="font-size:1.15rem; font-weight:700;">{c_media}</span> demandas
                </div>
                <div style="background:#F0FDF4; border:1px solid #86EFAC; border-radius:8px; padding:8px 16px; font-size:0.88rem; color:#166534; font-weight:500;">
                    🟢 <b>Baixa Prioridade:</b> <span style="font-size:1.15rem; font-weight:700;">{c_baixa}</span> demandas
                </div>
                {f'<div style="background:#F8FAFC; border:1px solid #CBD5E1; border-radius:8px; padding:8px 16px; font-size:0.88rem; color:#475569; font-weight:500;">⚪ <b>Não informada:</b> <span style="font-size:1.15rem; font-weight:700;">{c_nao_inf}</span></div>' if c_nao_inf > 0 else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Ordenar da MAIOR para a MENOR prioridade
        prio_rank = {"Alta": 1, "Média": 2, "Baixa": 3, "Não informada": 4}
        df_sorted = df_f.copy()
        df_sorted["_rank"] = df_sorted["Prioridade"].map(lambda p: prio_rank.get(p, 99))
        df_sorted = df_sorted.sort_values(by=["_rank", "Unidade Demandante", "Objeto"]).reset_index(drop=True)

        if df_sorted.empty:
            st.info("Nenhuma demanda encontrada para os filtros selecionados.")
        else:
            for idx, row in df_sorted.iterrows():
                st.html(_card_html(row))

    with sub_graf:
        g1, g2 = st.columns(2)
        with g1:
            df_status = df_f["Status da Contratação"].value_counts().reset_index()
            df_status.columns = ["Status", "Quantidade"]
            df_status = df_status.sort_values(by="Quantidade", ascending=True)
            fig_stat = px.bar(
                df_status,
                x="Quantidade",
                y="Status",
                orientation="h",
                title="<b>Processos por Status da Contratação</b>",
                text="Quantidade",
                color="Quantidade",
                color_continuous_scale="Blues",
            )
            fig_stat.update_layout(height=360, margin=dict(l=10, r=20, t=40, b=10), coloraxis_showscale=False)
            fig_stat.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(fig_stat, use_container_width=True, key=f"{key_prefix}f_stat")

        with g2:
            df_unid = df_f.groupby(["Unidade Demandante", "Prioridade"]).size().reset_index(name="Quantidade")
            color_map_prio = {"Alta": "#EF4444", "Média": "#F59E0B", "Baixa": "#10B981", "Não informada": "#94A3B8"}
            fig_u = px.bar(
                df_unid,
                x="Unidade Demandante",
                y="Quantidade",
                color="Prioridade",
                color_discrete_map=color_map_prio,
                title="<b>Demandas por Unidade e Prioridade</b>",
                text="Quantidade",
                barmode="stack",
            )
            fig_u.update_layout(height=360, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_u, use_container_width=True, key=f"{key_prefix}f_unid")

    with sub_atencao:
        df_alertas = df_f[df_f["Ponto de Atenção"] != "-"].copy()
        if df_alertas.empty:
            st.info("Nenhum processo com ponto de atenção registrado para os filtros selecionados.")
        else:
            for _, row in df_alertas.iterrows():
                st.html(_card_html(row))

    with sub_tab:
        cols_order = [
            "Prioridade",
            "Unidade Demandante",
            "Objeto",
            "Tipo",
            "Status da Contratação",
            "Ponto de Atenção",
            "Número SEI",
            "Número da Contratação SISLOG",
            "Responsável",
            "Necessitará de Parecer Jurídico",
            "Prevista para 2026?",
        ]
        cols_presentes = [c for c in cols_order if c in df_f.columns]
        st.dataframe(
            df_f[cols_presentes],
            use_container_width=True,
            hide_index=True,
            height=480,
            column_config={
                "Prioridade": st.column_config.TextColumn("Prioridade", width="small"),
                "Unidade Demandante": st.column_config.TextColumn("Unidade", width="small"),
                "Objeto": st.column_config.TextColumn("Objeto da Contratação", width="large"),
                "Tipo": st.column_config.TextColumn("Tipo", width="medium"),
                "Status da Contratação": st.column_config.TextColumn("Status", width="medium"),
                "Ponto de Atenção": st.column_config.TextColumn("Ponto de Atenção", width="large"),
                "Número SEI": st.column_config.TextColumn("Processo SEI", width="medium"),
                "Número da Contratação SISLOG": st.column_config.TextColumn("SISLOG", width="small"),
                "Responsável": st.column_config.TextColumn("Responsável", width="small"),
                "Necessitará de Parecer Jurídico": st.column_config.TextColumn("Parecer Jurídico", width="small"),
                "Prevista para 2026?": st.column_config.TextColumn("Prev. 2026?", width="small"),
            },
        )
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_f[cols_presentes].to_excel(writer, index=False, sheet_name="Contratações 2026")
        st.download_button(
            label="📥 Exportar Dados para Excel (.xlsx)",
            data=output.getvalue(),
            file_name="Acompanhamento_Contratacoes_2026.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}dl_excel",
        )
