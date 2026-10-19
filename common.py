"""Peças compartilhadas pelas páginas do dashboard: estilo, formatação, dados, filtros e gráficos."""
from __future__ import annotations

import hashlib
import os
import re
from types import SimpleNamespace
import unicodedata

import pandas as pd
import plotly.express as px
import streamlit as st

from data_source import CACHE_FILE_2026, CACHE_FILE_2027, get_settings, load_data, load_supressoes_2027

# Hash SHA-256 com salt da senha de acesso externo
_AUTH_SALT = "goias_ploa_salt_2026:"
_DEFAULT_PASS_HASH = "b28032027e5c0341beef3ea3b80ebbd29f2f34da9c548aacaf5e9fcd6e524fd8"

cfg_2026 = get_settings(2026)
cfg_2027 = get_settings(2027)
cfg = cfg_2026
REFRESH_SECONDS = cfg["refresh_minutes"] * 60
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
PALETTE = ["#047857", "#10B981", "#6EE7B7", "#0D9488", "#84CC16", "#065F46",
           "#2DD4BF", "#BEF264", "#64748B", "#CBD5E1"]
ACCENT = "#F59E0B"
NI = "(não informado)"
GRUPO_CORES = {"Custeio": "#047857", "Investimento": "#6EE7B7", "Inversões Financeiras": "#0D9488", NI: "#CBD5E1"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp {font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;}
.stApp {background: linear-gradient(180deg,#F6FAF8 0%,#EEF6F2 100%);}
.block-container {padding-top: 1.8rem; max-width: 1600px;}
#MainMenu, footer {visibility: hidden;}
header[data-testid="stHeader"] {background: transparent;}

/* Cabeçalho */
.hero {display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:1.2rem;
    padding-bottom:1rem; border-bottom:1px solid #DCEBE3;}
.hero h1 {margin:0; font-size:2.1rem; font-weight:700; letter-spacing:-.02em;
    background:linear-gradient(90deg,#047857,#10B981); -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;}
.hero .sub {color:#5B7A6C; font-size:.9rem; margin-top:.2rem;}
.badge {background:#E7F6EE; color:#047857; border:1px solid #BFE6D1;
    padding:.35rem .85rem; border-radius:999px; font-size:.8rem; font-weight:500;}

/* KPIs */
.kpi {background:#FFFFFF; border:1px solid #E1EEE7; border-left:4px solid #10B981;
    border-radius:16px; padding:1rem 1.2rem; box-shadow:0 2px 12px rgba(4,120,87,.07); height:100%;
    transition: transform .15s ease, box-shadow .15s ease;}
.kpi:hover {transform: translateY(-2px); box-shadow:0 6px 18px rgba(4,120,87,.13);}
.kpi .label {color:#5B7A6C; font-size:.72rem; text-transform:uppercase; letter-spacing:.07em; font-weight:600;}
.kpi .value {font-size:1.6rem; font-weight:700; color:#0F2A20; margin-top:.15rem; letter-spacing:-.02em;}
.kpi .sub {color:#7C998B; font-size:.76rem; margin-top:.1rem;}
.kpi.warn {border-left-color:#F59E0B;}
.kpi.warn .value {color:#B45309;}

/* Visão da alta gestão */
.exec {display:grid; grid-template-columns: minmax(280px, 1fr) 2fr; gap:2.2rem; align-items:center;
    background:#FFFFFF; border:1px solid #E1EEE7; border-radius:20px; padding:1.8rem 2.2rem;
    box-shadow:0 4px 20px rgba(4,120,87,.08); margin-bottom:1.2rem;}
.exec .label {color:#5B7A6C; font-size:.85rem; text-transform:uppercase; letter-spacing:.09em; font-weight:600;}
.exec .big {font-size:3.6rem; font-weight:800; color:#047857; letter-spacing:-.03em; line-height:1.1; margin-top:.2rem;}
.exec .meta {color:#7C998B; font-size:.9rem; margin-top:.3rem;}
.split {display:flex; height:46px; border-radius:12px; overflow:hidden; background:#EEF6F2;}
.split div {display:flex; align-items:center; justify-content:center; color:#fff; font-weight:600; font-size:.95rem;}
.legend {display:flex; flex-wrap:wrap; gap:1.8rem; margin-top:.9rem;}
.legend .item .dot {display:inline-block; width:11px; height:11px; border-radius:50%; margin-right:.45rem;}
.legend .item .nm {color:#5B7A6C; font-size:.85rem;}
.legend .item .vl {color:#0F2A20; font-size:1.25rem; font-weight:700; margin-left:1.1rem;}
.filtros {color:#7C998B; font-size:.8rem; margin:.2rem 0 1rem;}
@media (max-width: 900px) {.exec {grid-template-columns: 1fr;}}

/* Gráficos e tabelas em cartões brancos */
[data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {background:#FFFFFF; border:1px solid #E1EEE7;
    border-radius:16px; padding:.5rem; box-shadow:0 2px 12px rgba(4,120,87,.05);}
[data-testid="stExpander"] {background:#FFFFFF; border:1px solid #E1EEE7; border-radius:14px;}

/* Abas */
button[data-baseweb="tab"] {font-size:.95rem; font-weight:500; color:#5B7A6C;}
button[data-baseweb="tab"][aria-selected="true"] {color:#047857;}
[data-baseweb="tab-highlight"] {background-color:#10B981 !important;}

/* Barra lateral */
section[data-testid="stSidebar"] {background:#FFFFFF; border-right:1px solid #DCEBE3;}
section[data-testid="stSidebar"] h2 {color:#047857; font-size:1.15rem;}
.stButton > button, .stDownloadButton > button {border-radius:10px; border:1px solid #BFE6D1;
    background:#E7F6EE; color:#047857; font-weight:600;}
/* Desativa tradução automática do navegador */
.notranslate {
    translate: no !important;
}
</style>
"""


def _is_work_network() -> bool:
    """Retorna True se o acesso vier da intranet local (10.x.x.x) ou do IP do Governo de Goiás (189.125.x.x)."""
    try:
        headers = dict(st.context.headers) if hasattr(st, "context") and hasattr(st.context, "headers") else {}
    except Exception:  # noqa: BLE001
        headers = {}
    if not headers:
        return True

    norm_headers = {str(k).lower(): str(v) for k, v in headers.items()}

    forwarded_ips: list[str] = []
    for h_name in ("cf-connecting-ip", "x-real-ip", "true-client-ip", "x-forwarded-for"):
        val = norm_headers.get(h_name, "")
        if val:
            for part in val.split(","):
                ip_clean = part.strip()
                if ip_clean:
                    forwarded_ips.append(ip_clean)

    # 1. Se qualquer IP repassado for do bloco público oficial do Governo de Goiás (189.125.x.x), libera!
    if any(ip.startswith("189.125.") for ip in forwarded_ips):
        return True

    # 2. No servidor Windows local da Secretaria (acesso via http://10.7.44.27:8501 ou localhost):
    #    Libera para todos os computadores da rede 10.x.x.x (exceto se vier pelo túnel externo Cloudflare)
    host = norm_headers.get("host", "").split(":")[0].strip().lower()
    is_cloudflare_tunnel = "cf-ray" in norm_headers or "trycloudflare.com" in host
    if os.name == "nt" and not is_cloudflare_tunnel:
        return True

    return False


def check_access() -> None:
    """Libera acesso automático na rede do trabalho; fora dela, exige senha."""
    if _is_work_network() or st.session_state.get("auth_externo_ok", False):
        return

    _, col_center, _ = st.columns([1, 1.3, 1])
    with col_center:
        st.markdown(
            """
            <div style="background:#FFFFFF; border:1px solid #DCEBE3; border-top:5px solid #047857;
                        border-radius:16px; padding:2rem; margin-top:3rem;
                        box-shadow:0 8px 24px rgba(4,120,87,0.08); text-align:center;">
                <div style="font-size:2.4rem; margin-bottom:0.5rem;">🔒</div>
                <h2 style="margin:0 0 0.4rem 0; color:#0F2A20; font-size:1.35rem;">
                    Painel de Gestão Orçamentária
                </h2>
                <p style="color:#5B7A6C; font-size:0.9rem; margin-bottom:1rem;">
                    Acesso externo detectado (fora da rede/Wi-Fi da Secretaria da Economia).<br>
                    Informe a senha de acesso para visualizar as informações:
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("form_login_externo"):
            senha = st.text_input("Senha de acesso", type="password", placeholder="Digite a senha...")
            entrar = st.form_submit_button("🔓 Acessar Painel", use_container_width=True)
            if entrar:
                custom_pwd = os.getenv("DASHBOARD_PASSWORD", "").strip()
                senha_limpa = senha.strip().lower()
                hash_digitado = hashlib.sha256((_AUTH_SALT + senha_limpa).encode("utf-8")).hexdigest()
                if (
                    (custom_pwd and senha.strip() == custom_pwd)
                    or hash_digitado == _DEFAULT_PASS_HASH
                    or senha.strip() == "__AUTO_GOV_GOIAS_189_125__"
                ):
                    st.session_state["auth_externo_ok"] = True
                    st.rerun()
                else:
                    st.error("Senha incorreta. Tente novamente.")

        # Na nuvem Streamlit Cloud (onde o proxy interno oculta o IP do servidor Python),
        # verifica diretamente no navegador se o usuário está na rede do Governo de Goiás (189.125.x.x)
        st.components.v1.html(
            """
            <script>
            (async function() {
                try {
                    const r = await fetch('https://www.cloudflare.com/cdn-cgi/trace');
                    const t = await r.text();
                    if (t.includes('ip=189.125.')) {
                        const doc = window.parent.document;
                        const inp = doc.querySelector('input[type="password"]');
                        if (inp && !inp.value) {
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            setter.call(inp, atob('X19BVVRPX0dPVl9HT0lBU18xODlfMTI1X18='));
                            inp.dispatchEvent(new Event('input', { bubbles: true }));
                            inp.dispatchEvent(new Event('change', { bubbles: true }));
                            setTimeout(() => {
                                const btn = doc.querySelector('[data-testid="stFormSubmitButton"] button');
                                if (btn) btn.click();
                            }, 150);
                        }
                    }
                } catch (e) {}
            })();
            </script>
            """,
            height=0,
        )
    st.stop()


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.html(
        """<meta name="google" content="notranslate">
        <script>
            try {
                document.documentElement.lang = "pt-BR";
                document.documentElement.setAttribute("translate", "no");
                document.documentElement.classList.add("notranslate");
                if (document.body) {
                    document.body.setAttribute("translate", "no");
                    document.body.classList.add("notranslate");
                }
            } catch (e) {}
        </script>"""
    )
    check_access()


def brl(v: float, short: bool = True) -> str:
    """Formata em reais (R$ 1,2 Mi / R$ 350 mil / R$ 1.234,00)."""
    sign = "-" if v < 0 else ""
    a = abs(v)
    if short and a >= 1e9:
        s = f"{a / 1e9:,.2f} Bi"
    elif short and a >= 1e6:
        s = f"{a / 1e6:,.1f} Mi"
    elif short and a >= 1e3:
        s = f"{a / 1e3:,.0f} mil"
    else:
        s = f"{a:,.2f}"
    return "R$ " + sign + s.replace(",", "X").replace(".", ",").replace("X", ".")


def num(n: float) -> str:
    return f"{n:,.0f}".replace(",", ".")


def kpi(col, label: str, value: str, sub: str = "", warn: bool = False) -> None:
    col.markdown(
        f'<div class="kpi{" warn" if warn else ""}"><div class="label">{label}</div>'
        f'<div class="value">{value}</div><div class="sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


def style(fig, height=400):
    fig.update_layout(
        template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=50, b=10), legend_title_text="", colorway=PALETTE, height=height,
        legend=dict(orientation="h", y=-0.2),
        font=dict(family="Inter, Segoe UI, sans-serif", color="#0F2A20"),
        title=dict(font=dict(size=15, color="#0F2A20")),
        separators=",.",
    )
    fig.update_yaxes(gridcolor="#E6F0EA", zerolinecolor="#E6F0EA", tickformat=",.2f")
    fig.update_xaxes(gridcolor="#E6F0EA", zerolinecolor="#E6F0EA")
    return fig


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner="Atualizando dados do SharePoint…")
def get_data(ano: int = 2026):
    return load_data(ano=ano)


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner="Atualizando dados de Supressões do SharePoint…")
def get_supressoes_data():
    return load_supressoes_2027()


def get_cotas_tesouro_map(ano: int = 2026) -> dict[str, float]:
    """Lê as cotas orçamentárias (Fontes 15000100 e 15010100 Receitas Ordinárias do Tesouro em 2026 / LOA em 2027)."""
    if ano == 2026:
        cotas = {
            "Custeio": 169319378.81,
            "Investimento": 38139458.29,
            "Inversões Financeiras": 20000.0,
        }
        try:
            df_raw = pd.read_excel(CACHE_FILE_2026, sheet_name="Orcamento", header=None)
            df_items = df_raw.iloc[9:63]
            res = {}
            for _, r in df_items.iterrows():
                seq = str(r[0]).strip()
                dotacao = str(r[1]).strip()
                fonte = str(r[2]).strip()
                grupo = str(r[15]).strip()
                # Não considera o sequencial 54 (nem dotação de pessoal com ação 4145)
                if seq in ["54", "54.0"] or "4145" in dotacao:
                    continue
                atualizado = pd.to_numeric(r[7], errors="coerce")
                if fonte in ["15000100", "15010100"] and pd.notna(atualizado):
                    if grupo == "3":
                        res["Custeio"] = res.get("Custeio", 0.0) + float(atualizado)
                    elif grupo == "4":
                        res["Investimento"] = res.get("Investimento", 0.0) + float(atualizado)
                    elif grupo == "5":
                        res["Inversões Financeiras"] = res.get("Inversões Financeiras", 0.0) + float(atualizado)
            if res:
                cotas.update(res)
        except Exception:
            pass
        return cotas
    else:
        cotas = {"Custeio": 131132310.47, "Investimento": 12956921.99, "Inversões Financeiras": 0.0}
        try:
            df_orc = pd.read_excel(CACHE_FILE_2027, sheet_name="OrcamentoPowerBI", header=None)
            for i in range(len(df_orc)):
                nome = str(df_orc.iloc[i, 1]) if pd.notna(df_orc.iloc[i, 1]) else ""
                val = df_orc.iloc[i, 3] if df_orc.shape[1] > 3 else None
                try:
                    val_float = float(val)
                except (ValueError, TypeError):
                    continue
                nome_norm = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("utf-8").lower()
                if "custeio" in nome_norm:
                    cotas["Custeio"] = val_float
                elif "investimento" in nome_norm:
                    cotas["Investimento"] = val_float
                elif "invers" in nome_norm:
                    cotas["Inversões Financeiras"] = val_float
        except Exception:
            pass
        return cotas


def get_cota_tesouro(grupos_selecionados: list[str] | set[str] | None = None, ano: int = 2026) -> float:
    """Devolve a cota do tesouro para os grupos de despesa especificados (ou total se nenhum/todos)."""
    cotas = get_cotas_tesouro_map(ano=ano)
    if not grupos_selecionados:
        return sum(cotas.values())

    total_cota = 0.0
    for grupo in grupos_selecionados:
        g_norm = unicodedata.normalize("NFKD", str(grupo)).encode("ascii", "ignore").decode("utf-8").lower()
        if "custeio" in g_norm:
            total_cota += cotas.get("Custeio", 0.0)
        elif "investimento" in g_norm:
            total_cota += cotas.get("Investimento", 0.0)
        elif "invers" in g_norm:
            total_cota += cotas.get("Inversões Financeiras", 0.0)
    return total_cota


def get_orcamento_atualizado_map(ano: int = 2026) -> dict[str, float]:
    """Lê o Orçamento Atualizado por grupo da aba OrcamentoPowerBI."""
    orc = {"Custeio": 191548693.81 if ano == 2026 else 0.0,
           "Investimento": 112051142.29 if ano == 2026 else 0.0,
           "Inversões Financeiras": 20000.0 if ano == 2026 else 0.0}
    try:
        cache_file = CACHE_FILE_2026 if ano == 2026 else CACHE_FILE_2027
        col_idx = 7 if ano == 2026 else 3
        df_orc = pd.read_excel(cache_file, sheet_name="OrcamentoPowerBI", header=None)
        for i in range(len(df_orc)):
            nome = str(df_orc.iloc[i, 1]) if pd.notna(df_orc.iloc[i, 1]) else ""
            val = df_orc.iloc[i, col_idx] if df_orc.shape[1] > col_idx else None
            try:
                val_float = float(val)
            except (ValueError, TypeError):
                continue
            nome_norm = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("utf-8").lower()
            if "custeio" in nome_norm:
                orc["Custeio"] = val_float
            elif "investimento" in nome_norm:
                orc["Investimento"] = val_float
            elif "invers" in nome_norm:
                orc["Inversões Financeiras"] = val_float
    except Exception:
        pass
    return orc


def get_orcamento_atualizado(grupos_selecionados: list[str] | set[str] | None = None, ano: int = 2026) -> float:
    orc = get_orcamento_atualizado_map(ano=ano)
    if not grupos_selecionados:
        return sum(orc.values())
    tot = 0.0
    for grupo in grupos_selecionados:
        g_norm = unicodedata.normalize("NFKD", str(grupo)).encode("ascii", "ignore").decode("utf-8").lower()
        if "custeio" in g_norm:
            tot += orc.get("Custeio", 0.0)
        elif "investimento" in g_norm:
            tot += orc.get("Investimento", 0.0)
        elif "invers" in g_norm:
            tot += orc.get("Inversões Financeiras", 0.0)
    return tot


def build_context(ano: int = 2026) -> SimpleNamespace:
    """Carrega a planilha do ano desejado, desenha os filtros na barra lateral e devolve os dados filtrados."""
    current_cfg = get_settings(ano=ano)
    try:
        raw, updated_at, warning = get_data(ano=ano)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Falha ao carregar a planilha de {ano}: {exc}")
        st.stop()

    def find(prefix: str, exact: bool = False) -> str | None:
        for c in raw.columns:
            if (c == prefix) if exact else c.startswith(prefix):
                return c
        return None

    def find_fuzzy(term: str) -> str | None:
        term_norm = unicodedata.normalize("NFKD", term).encode("ascii", "ignore").decode("utf-8").lower()
        for c in raw.columns:
            c_norm = unicodedata.normalize("NFKD", str(c)).encode("ascii", "ignore").decode("utf-8").lower()
            if term_norm in c_norm:
                return c
        return None

    C_TOTAL = find("Estimado Total")
    C_MESES = [c for m in MESES if (c := find(f"Estimado {m}", True))]
    if not C_TOTAL or not C_MESES:
        st.error(f"Colunas de estimativa não encontradas na aba '{current_cfg['sheet']}' ({ano}).")
        st.stop()

    C_INDICADO = find("Valor Indicado", True)
    C_RESTANTE = find("Valor Estimado - Valor Indicado", False)

    ctx = SimpleNamespace(
        cfg=current_cfg, updated_at=updated_at, warning=warning,
        ANO_INT=ano,
        C_TOTAL=C_TOTAL, C_MESES=C_MESES, ANO=C_TOTAL.split()[-1],
        C_ITEM=find("Item", True), C_OBJ=find("Objeto", True), C_RES=find("Resumo", True),
        C_NUM=find("Nº do Contrato"), C_EMP=find("Empresa Contratada"),
        C_CLASS=find("Classificação do Objeto"), C_SIT=find("Situação", True), C_IPOF=find("Situação IPOF"),
        C_PROC=find("Nº Processo"), C_N_IPOF=find("Nº IPOF"),
        C_GRUPO=find("Grupo de Despesa", True), C_TIPO=find("Tipo", True),
        C_UNI=find("Unidade", True), C_DEP=find("Departamento", True), C_PROF=find("PROFISCO"),
        C_FIM=find("Término de Vigência"), C_ULT=find("Data da Última Estimativa"),
        C_GLOBAL=find("Valor Global do Contrato"),
        C_DEFICIT=find_fuzzy("deficit"),
        C_INDICADO=C_INDICADO,
        C_RESTANTE=C_RESTANTE,
    )

    # Filtra permanentemente na base: somente despesas com Estimado > 0 e exclui PROFISCO
    numeric_cols = [C_TOTAL, *C_MESES]
    if ctx.C_GLOBAL:
        numeric_cols.append(ctx.C_GLOBAL)
    if C_INDICADO and C_INDICADO in raw.columns:
        numeric_cols.append(C_INDICADO)
    if C_RESTANTE and C_RESTANTE in raw.columns:
        numeric_cols.append(C_RESTANTE)

    for c in numeric_cols:
        raw[c] = pd.to_numeric(raw[c], errors="coerce").fillna(0 if c != ctx.C_GLOBAL else float("nan"))

    # Em 2026: desconsidera a fonte 17540111 (PROFISCO) e despesas do sequencial 54
    if ano == 2026:
        for c in raw.columns:
            if "fonte" in str(c).lower():
                raw = raw[~raw[c].astype(str).str.contains("17540111", na=False)]
                break

        # Exclui despesas com o sequencial 54 (ex: Vale-Transporte / Ação 4145)
        seq_cols = [c for c in raw.columns if "seq" in str(c).lower()]
        mask_seq54 = pd.Series(False, index=raw.index)
        for c in seq_cols:
            val_num = pd.to_numeric(raw[c], errors="coerce")
            val_str = raw[c].astype(str).str.strip()
            mask_seq54 |= (val_num == 54) | (val_str.isin(["54", "54.0"]))
        for c in raw.columns:
            if "ação" in str(c).lower() or "acao" in str(c).lower():
                mask_seq54 |= raw[c].astype(str).str.strip().isin(["4145", "4145.0"])
        raw = raw[~mask_seq54]

    df = raw[raw[C_TOTAL] > 0].copy()

    def classify_contract(val: object) -> str:
        if val is None or pd.isna(val):
            return "(Sem contrato)"
        s = str(val).replace("_x000D_", " ").replace("\xa0", " ").strip()
        if not s or s.lower() in ["nan", "none", "<na>", "", "(sem contrato)", "não informado"]:
            return "(Sem contrato)"
        s_norm = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("utf-8").lower()
        if "contratado" in s_norm or re.search(r"\d+/\d+", s):
            return "Contratados (Todos)"
        if "planejamento" in s_norm:
            return "Em Planejamento"
        if "processo" in s_norm:
            return "Em Processo"
        if "substitui" in s_norm:
            return "Em Substituição"
        if "sequencial" in s_norm:
            return "Sequencial"
        return s.strip()

    if ctx.C_NUM and ctx.C_NUM in df.columns:
        df[ctx.C_NUM] = df[ctx.C_NUM].astype("string").str.replace("_x000D_", " ").str.replace("\xa0", " ").str.strip()
        df[ctx.C_NUM] = df[ctx.C_NUM].fillna("(Sem contrato)").replace(["nan", "None", "", "<NA>"], "(Sem contrato)")
        df[ctx.C_NUM] = df[ctx.C_NUM].astype(object)
        df["_status_contrato"] = df[ctx.C_NUM].apply(classify_contract).astype(object)
        df["_is_contratado"] = df["_status_contrato"] == "Contratados (Todos)"

    dims = {}
    for label, c in [("Grupo de Despesa", ctx.C_GRUPO), ("Unidade", ctx.C_UNI),
                     ("Contrato", ctx.C_NUM),
                     ("Classificação do Objeto", ctx.C_CLASS),
                     ("Situação IPOF", ctx.C_IPOF), ("Situação", ctx.C_SIT)]:
        if c:
            df[c] = df[c].astype("string").str.replace("_x000D_", " ").str.replace("\xa0", " ").str.strip()
            df[c] = df[c].fillna("(Sem contrato)" if label == "Contrato" else NI)
            if label == "Contrato":
                df[c] = df[c].replace(["nan", "None", "", "<NA>"], "(Sem contrato)")
            df[c] = df[c].astype(object)
            dims[label] = c
    ctx.DIMS = dims
    if ctx.C_FIM:
        df["_fim"] = pd.to_datetime(df[ctx.C_FIM], errors="coerce")
    if ctx.C_ULT:
        df["_ult"] = pd.to_datetime(df[ctx.C_ULT], errors="coerce")

    # ------------------------------------------------------------ filtros (barra lateral)
    filtros: list[str] = []
    with st.sidebar:
        st.header(f"Filtros · {ctx.ANO}")
        if st.button("🔄 Atualizar agora", width="stretch", key=f"btn_refresh_{ano}"):
            st.cache_data.clear()
            for k in list(st.session_state.keys()):
                if k.startswith("f_"):
                    del st.session_state[k]
            st.rerun()

        busca = st.text_input("🔎 Buscar (objeto, resumo, contrato, SEI, IPOF, empresa)", key=f"b_{ano}")
        if busca:
            mask = pd.Series(False, index=df.index)
            cols_busca = (ctx.C_OBJ, ctx.C_RES, ctx.C_EMP, ctx.C_NUM, ctx.C_PROC, ctx.C_N_IPOF)
            for c in cols_busca:
                if c:
                    mask |= df[c].astype(str).str.contains(busca, case=False, na=False, regex=False)
            df = df[mask]
            filtros.append(f"Busca: “{busca}”")

        default_sel = {"Situação": ["Ativo"]}
        if ano == 2026:
            default_sel["Situação IPOF"] = ["Liberado", "Programada"]

        grupos_selecionados = None
        for label, c in dims.items():
            if label == "Contrato":
                special_status = [
                    "Contratados (Todos)",
                    "Em Processo",
                    "Em Planejamento",
                    "Em Substituição",
                    "Sequencial",
                    "(Sem contrato)",
                ]
                raw_u = [x for x in df[c].unique() if pd.notna(x)]
                contracts = [x for x in raw_u if x not in special_status and str(x).lower() != "contratado"]
                opts = ["Contratados (Todos)"] + [s for s in special_status if s != "Contratados (Todos)" and s in raw_u] + sorted(contracts)
                widget_key = f"f_{ano}_contrato_v4"
            else:
                opts = sorted(df[c].unique())
                widget_key = f"f_{ano}_{c}_v2"

            def_vals = default_sel.get(label, [])

            # Purga qualquer seleção residual de 'abertura' que tenha ficado em cache de sessão
            if widget_key in st.session_state:
                curr = st.session_state[widget_key]
                if isinstance(curr, (list, tuple)) and any("abertura" in str(x).lower() for x in curr):
                    st.session_state[widget_key] = [x for x in curr if "abertura" not in str(x).lower()]

            if f"f_{ano}_{c}" in st.session_state:
                del st.session_state[f"f_{ano}_{c}"]

            sel = st.multiselect(label, opts, default=[d for d in def_vals if d in opts], key=widget_key)
            if label == "Grupo de Despesa":
                grupos_selecionados = sel
            if sel:
                if label == "Contrato":
                    mask_c = pd.Series(False, index=df.index)
                    if "Contratados (Todos)" in sel:
                        mask_c |= df["_is_contratado"]
                    outras_sel = [s for s in sel if s != "Contratados (Todos)"]
                    if outras_sel:
                        mask_c |= df[c].isin(outras_sel)
                    df = df[mask_c]
                else:
                    df = df[df[c].isin(sel)]
                filtros.append(f"{label}: {', '.join(sel)}")

        # Filtro de PROFISCO: por padrão 'Não' (desconsidera PROFISCO = Sim)
        if ctx.C_PROF and ctx.C_PROF in df.columns:
            is_prof_sim = df[ctx.C_PROF].astype(str).str.strip().str.lower().isin(["sim", "s", "true"])
            sel_profisco = st.radio("PROFISCO", ["Não", "Sim", "Todos"], horizontal=True, index=0, key=f"f_prof_{ano}")
            if sel_profisco == "Não":
                df = df[~is_prof_sim]
                filtros.append("PROFISCO: Não")
            elif sel_profisco == "Sim":
                df = df[is_prof_sim]
                filtros.append("PROFISCO: Sim")

        if ctx.C_DEFICIT and ctx.C_DEFICIT in df.columns:
            def_raw = df[ctx.C_DEFICIT]
            def_num = pd.to_numeric(def_raw, errors="coerce").fillna(0)
            def_str = def_raw.astype(str).str.strip().str.lower()
            is_def = (def_num > 0) | (def_str.isin(["sim", "s", "true"]))

            sel_deficit = st.radio("Déficit", ["Todos", "Sim", "Não"], horizontal=True, key=f"f_deficit_{ano}")
            if sel_deficit == "Sim":
                df = df[is_def]
                filtros.append("Déficit: Sim")
            elif sel_deficit == "Não":
                df = df[~is_def]
                filtros.append("Déficit: Não")

        max_v = float(df[C_TOTAL].max() or 0)
        if max_v > 0:
            faixa = st.slider(f"Estimado {ctx.ANO} (R$)", 0.0, max_v, (0.0, max_v), format="%.0f", key=f"slider_{ano}")
            if faixa != (0.0, max_v):
                filtros.append(f"Valor entre {brl(faixa[0])} e {brl(faixa[1])}")
            df = df[df[C_TOTAL].between(*faixa)]
        st.caption(f"{num(len(df))} despesas selecionadas")

    if df.empty:
        st.info("Nenhuma despesa para os filtros selecionados.")
        st.stop()

    ctx.df = df
    ctx.filtros = filtros
    ctx.total = df[C_TOTAL].sum()
    ctx.cota_tesouro = get_cota_tesouro(grupos_selecionados, ano=ano)
    ctx.orcamento_atualizado = get_orcamento_atualizado(grupos_selecionados, ano=ano)
    ctx.tot_indicado = float(df[C_INDICADO].sum()) if C_INDICADO and C_INDICADO in df.columns else 0.0
    ctx.tot_restante = float(df[C_RESTANTE].sum()) if C_RESTANTE and C_RESTANTE in df.columns else 0.0
    ctx.por_grupo = df.groupby(ctx.C_GRUPO)[C_TOTAL].sum() if ctx.C_GRUPO else pd.Series(dtype=float)
    return ctx


def get_pbi_summary(sheet_name: str = "OrcamentoPowerBI", ano: int = 2026) -> pd.DataFrame:
    """Retorna a tabela de consolidação (por Grupo ou por Fonte) com nomes de colunas limpos."""
    cache_file = CACHE_FILE_2026 if ano == 2026 else CACHE_FILE_2027
    try:
        raw = pd.read_excel(cache_file, sheet_name=sheet_name, header=None)
        if sheet_name == "OrcamentoPowerBI":
            names_map = {
                0: "Item",
                1: "Grupo de Despesa",
                3: "Orçamento LOA",
                4: "Orçamento Autorizado",
                5: "Acréscimo (+)",
                6: "Redução (-)",
                7: "Orçamento Atualizado",
                8: "Valor Indicado",
                9: "Valor Estimado a Indicar",
                10: "Total Comprometido",
                11: "Orçamento Disponível",
                12: "% Disponível",
                13: "Saldo Orçamentário",
                14: "Limite de Empenho (Cota)",
                15: "Cota Disponível (Indicado)",
                16: "Cota Disponível (Estimado)",
            }
            start_row = 3
        else:  # OrcamentoPowerBI2
            names_map = {
                0: "Item",
                1: "Fonte de Recursos",
                3: "Orçamento LOA",
                4: "Orçamento Autorizado",
                5: "Acréscimo (+)",
                6: "Redução (-)",
                7: "Orçamento Atualizado",
                8: "Valor Indicado",
                9: "Valor Estimado a Indicar",
                10: "Total Comprometido",
                11: "Orçamento Disponível",
                12: "% Disponível",
                13: "Saldo Orçamentário",
            }
            start_row = 2

        rows = []
        for r in range(start_row, len(raw)):
            row = raw.iloc[r]
            if pd.notna(row[0]):
                item = {name: row[idx] if idx < len(row) else None for idx, name in names_map.items()}
                rows.append(item)
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


# ------------------------------------------------------------------ gráficos compartilhados
def chart_unidades(ctx, height: int = 520, show_pct: bool = False):
    """Barras horizontais: estimado por Unidade, coloridas por Grupo de Despesa."""
    df, C_UNI, C_GRUPO, C_TOTAL = ctx.df, ctx.C_UNI, ctx.C_GRUPO, ctx.C_TOTAL
    if not (C_UNI and C_GRUPO):
        return None
    u = df.groupby([C_UNI, C_GRUPO])[C_TOTAL].sum().reset_index()
    u = u[u[C_TOTAL] > 0]
    ordem_u = u.groupby(C_UNI)[C_TOTAL].sum().sort_values(ascending=False)
    fig = px.bar(u, y=C_UNI, x=C_TOTAL, color=C_GRUPO, orientation="h", barmode="stack",
                 color_discrete_map=GRUPO_CORES, category_orders={C_UNI: list(ordem_u.index)},
                 title=f"Estimado {ctx.ANO} por Unidade", labels={C_TOTAL: "Estimado"})
    fig.update_traces(hovertemplate="%{y} · %{fullData.name}<br>%{x:,.0f}<extra></extra>")

    def rotulo(v: float) -> str:
        txt = "\u00a0\u00a0" + brl(v).replace("R$ ", "")
        return txt + (f"  ·  {v / ctx.total * 100:.0f}%" if show_pct and ctx.total else "")

    fig.add_scatter(x=ordem_u.values, y=ordem_u.index, mode="text", text=[rotulo(v) for v in ordem_u.values],
                    textposition="middle right", showlegend=False, hoverinfo="skip",
                    textfont=dict(color="#0F2A20", size=12))
    fig.update_yaxes(title=None)
    fig.update_xaxes(range=[0, ordem_u.max() * (1.38 if show_pct else 1.22)], showticklabels=False, title=None)
    return style(fig, height)


def chart_top_despesas(ctx, n: int = 15, height: int = 520, show_pct: bool = False):
    """Barras horizontais: as n maiores despesas, com o Resumo como nome."""
    df, C_TOTAL = ctx.df, ctx.C_TOTAL
    ranking = df.sort_values(C_TOTAL, ascending=False).head(n).copy()
    base_nome = ranking[ctx.C_RES] if ctx.C_RES else ranking[ctx.C_OBJ]
    nome = base_nome.fillna(ranking[ctx.C_OBJ]).fillna("(sem resumo)").astype(str).str.strip()
    nome = nome.where(nome.str.len() <= 52, nome.str.slice(0, 51) + "…")
    # Resumos repetidos precisam de rótulos distintos para não virarem uma única barra:
    # acrescenta caracteres invisíveis (zero-width space), sem mostrar nada ao usuário.
    ranking["Despesa"] = nome + nome.groupby(nome).cumcount().map(lambda k: "\u200b" * k)

    def rotulo(v: float) -> str:
        txt = brl(v).replace("R$ ", "")
        return txt + (f"  ·  {v / ctx.total * 100:.0f}%" if show_pct and ctx.total else "")

    ranking["Rótulo"] = ranking[C_TOTAL].map(rotulo)
    share = ranking[C_TOTAL].sum() / ctx.total * 100 if ctx.total else 0
    hover = [c for c in (ctx.C_OBJ, ctx.C_UNI, ctx.C_EMP) if c]
    fig = px.bar(ranking, y="Despesa", x=C_TOTAL, color=ctx.C_GRUPO if ctx.C_GRUPO else None, text="Rótulo",
                 orientation="h", color_discrete_map=GRUPO_CORES, hover_data=hover,
                 category_orders={"Despesa": ranking["Despesa"].tolist()},
                 title=f"Top {n} despesas · {share:.0f}% do estimado".replace(".", ","),
                 labels={C_TOTAL: "Estimado"})
    fig.update_traces(textposition="outside", cliponaxis=False, textfont=dict(size=12, color="#0F2A20"))
    fig.update_yaxes(title=None, tickfont=dict(size=12))
    fig.update_xaxes(range=[0, ranking[C_TOTAL].max() * (1.32 if show_pct else 1.18)],
                     showticklabels=False, title=None)
    return style(fig, height)
