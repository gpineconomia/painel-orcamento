"""Sincronizador automático do Painel Orçamentário (SharePoint + Código -> GitHub -> Streamlit Cloud)."""
from __future__ import annotations

import base64
import hashlib
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

import data_source

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "gpineconomia/painel-orcamento").strip()
BRANCH = "main"

FILES_TO_SYNC = [
    "app.py",
    "common.py",
    "data_source.py",
    "requirements.txt",
    ".gitignore",
    ".streamlit/config.toml",
    ".streamlit/index.html",
    "paginas/despesas_unidade.py",
    "paginas/execucao_2026.py",
    "paginas/supressoes_2027.py",
    "paginas/visao_2026.py",
    "paginas/visao_analitica.py",
    "paginas/liquidacao_contrato.py",
    "paginas/pca_2027.py",
    "paginas/oraculo_ia.py",
    "oraculo.py",
    "pca_data.py",
    "liquidado_mensal_data.py",
    "teste_sap_bo.py",
    "sync_github.py",
    "data/planilha_2026_cache.xlsx",
    "data/planilha_cache.xlsx",
    "data/supressoes_2027_cache.xlsx",
    "data/pca_2027_cache.xlsx",
    "data/liquidado_mensal_sap.csv",
    "atualizar_siafic_07h30.vbs",
    "iniciar_segundo_plano.vbs",
]


def git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("utf-8")
    return hashlib.sha1(header + content).hexdigest()


def should_refresh_sap_bo() -> bool:
    """Verifica se o relatório do SIAFIC (SAP BO) precisa ser baixado hoje (1x ao dia, a partir das 7h30)."""
    now = datetime.now()
    hoje_7h30 = now.replace(hour=7, minute=30, second=0, microsecond=0)
    if now < hoje_7h30:
        return False

    last_sync_file = BASE_DIR / "data" / ".last_sap_sync.txt"
    if not last_sync_file.exists():
        return True

    try:
        last_sync_str = last_sync_file.read_text(encoding="utf-8").strip()
        last_sync_dt = datetime.fromisoformat(last_sync_str)
        # Se a última sincronização foi antes de hoje às 07:30, precisa atualizar
        return last_sync_dt < hoje_7h30
    except Exception:
        return True


def refresh_sap_bo() -> bool:
    """Extrai os relatórios oficiais do SIAFIC (SAP BO) para a pasta data/."""
    try:
        import liquidado_mensal_data

        print(f"[{datetime.now():%H:%M:%S}] Iniciando extração do SIAFIC (SAP BO - ConsultaLiquidadoMensal ID: 32115483)...")
        ok = liquidado_mensal_data.download_liquidado_mensal_csv()
        if ok:
            last_sync_file = BASE_DIR / "data" / ".last_sap_sync.txt"
            last_sync_file.write_text(datetime.now().isoformat(), encoding="utf-8")
            print(f"[{datetime.now():%H:%M:%S}] SIAFIC atualizado com sucesso.")
            return True
        else:
            print(f"[{datetime.now():%H:%M:%S}] Falha na extração do SIAFIC.")
            return False
    except Exception as exc:  # noqa: BLE001
        print(f"[{datetime.now():%H:%M:%S}] Erro ao atualizar SIAFIC: {exc}")
        return False


def refresh_sharepoint_caches() -> None:
    """Baixa as planilhas mais recentes do SharePoint e do Google Sheets para a pasta data/."""
    try:
        import pca_data
        pca_data.download_pca_workbook()
        print(f"[{datetime.now():%H:%M:%S}] Google Sheets atualizado: PCA 2027")
    except Exception as exc:
        print(f"[{datetime.now():%H:%M:%S}] Falha ao baixar PCA 2027: {exc}")

    for fn, label in [
        (lambda: data_source.load_data(2026), "Orçamento 2026"),
        (lambda: data_source.load_data(2027), "PLOA 2027"),
        (lambda: data_source.load_supressoes_2027(), "Supressões 2027"),
    ]:
        try:
            _, _, warn = fn()
            if warn:
                print(f"[{datetime.now():%H:%M:%S}] Aviso ({label}): {warn}")
            else:
                print(f"[{datetime.now():%H:%M:%S}] SharePoint atualizado: {label}")
        except Exception as exc:  # noqa: BLE001
            print(f"[{datetime.now():%H:%M:%S}] Falha ao baixar {label}: {exc}")


def sync_to_github(refresh_sp: bool = True, force_sap: bool = False) -> list[str]:
    """Compara os arquivos locais com o GitHub e envia apenas o que mudou em um único commit."""
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN não configurado no arquivo .env")

    # Atualização do SIAFIC (SAP BO): apenas 1x ao dia às 06:00 (ou forçado por flag)
    if force_sap or should_refresh_sap_bo():
        refresh_sap_bo()

    if refresh_sp:
        refresh_sharepoint_caches()

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    api_base = f"https://api.github.com/repos/{GITHUB_REPO}"

    # 1. Obter referência atual da branch main
    ref_resp = requests.get(f"{api_base}/git/ref/heads/{BRANCH}", headers=headers, timeout=20)
    ref_resp.raise_for_status()
    latest_commit_sha = ref_resp.json()["object"]["sha"]

    # 2. Obter árvore atual recursiva
    tree_resp = requests.get(f"{api_base}/git/trees/{latest_commit_sha}?recursive=1", headers=headers, timeout=20)
    tree_resp.raise_for_status()
    remote_shas = {
        item["path"]: item["sha"]
        for item in tree_resp.json().get("tree", [])
        if item.get("type") == "blob"
    }

    # 3. Verificar quais arquivos mudaram
    changed_files: list[tuple[str, bytes]] = []
    for rel_path in FILES_TO_SYNC:
        local_file = BASE_DIR / rel_path
        if not local_file.exists():
            continue
        content = local_file.read_bytes()
        local_sha = git_blob_sha(content)
        if remote_shas.get(rel_path) != local_sha:
            changed_files.append((rel_path, content))

    if not changed_files:
        print(f"[{datetime.now():%H:%M:%S}] GitHub já está 100% sincronizado (nenhuma alteração).")
        return []

    print(f"[{datetime.now():%H:%M:%S}] Enviando {len(changed_files)} arquivo(s) atualizado(s) para {GITHUB_REPO}:")
    new_tree_items = []
    for rel_path, content in changed_files:
        print(f"  -> {rel_path}")
        blob_resp = requests.post(
            f"{api_base}/git/blobs",
            headers=headers,
            json={
                "content": base64.b64encode(content).decode("ascii"),
                "encoding": "base64",
            },
            timeout=60,
        )
        blob_resp.raise_for_status()
        new_tree_items.append({
            "path": rel_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob_resp.json()["sha"],
        })

    # 4. Criar nova árvore
    create_tree_resp = requests.post(
        f"{api_base}/git/trees",
        headers=headers,
        json={"base_tree": latest_commit_sha, "tree": new_tree_items},
        timeout=30,
    )
    create_tree_resp.raise_for_status()
    new_tree_sha = create_tree_resp.json()["sha"]

    # 5. Criar commit
    nomes = ", ".join(p for p, _ in changed_files)
    commit_msg = f"Atualização automática ({datetime.now():%d/%m/%Y %H:%M}): {nomes}"
    create_commit_resp = requests.post(
        f"{api_base}/git/commits",
        headers=headers,
        json={
            "message": commit_msg,
            "tree": new_tree_sha,
            "parents": [latest_commit_sha],
        },
        timeout=30,
    )
    create_commit_resp.raise_for_status()
    new_commit_sha = create_commit_resp.json()["sha"]

    # 6. Atualizar ponteiro da branch main
    update_ref_resp = requests.patch(
        f"{api_base}/git/refs/heads/{BRANCH}",
        headers=headers,
        json={"sha": new_commit_sha, "force": False},
        timeout=20,
    )
    update_ref_resp.raise_for_status()
    print(f"[{datetime.now():%H:%M:%S}] Sucesso! Commit {new_commit_sha[:7]} publicado no GitHub.")
    return [p for p, _ in changed_files]


if __name__ == "__main__":
    force_sap = "--force-sap" in sys.argv
    no_sp = "--no-sp" in sys.argv

    if "--loop" in sys.argv:
        interval_min = int(os.getenv("SYNC_MINUTES", "60"))
        print(f"[{datetime.now():%H:%M:%S}] Iniciando sincronização contínua a cada {interval_min} minutos...")
        print("  - Planilhas SharePoint: a cada ciclo (60 minutos)")
        print("  - Relatório SIAFIC (SAP BO): 1x ao dia às 07:30")
        while True:
            try:
                sync_to_github(refresh_sp=not no_sp, force_sap=force_sap)
                force_sap = False  # Só força na primeira rodada se tiver flag
            except Exception as e:  # noqa: BLE001
                print(f"[{datetime.now():%H:%M:%S}] Erro na sincronização: {e}")
            time.sleep(interval_min * 60)
    else:
        sync_to_github(refresh_sp=not no_sp, force_sap=force_sap)
