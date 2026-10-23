"""Script de teste e integração com SAP BusinessObjects (BOE) via REST API (/biprws)."""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

import requests
import truststore
from dotenv import load_dotenv

# Injeta os certificados do sistema para garantir SSL seguro na intranet
truststore.inject_into_ssl()

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

BO_BASE_URL = os.getenv("SAP_BO_URL", "https://bo.intra.goias.gov.br/biprws").rstrip("/")
BO_CMS = os.getenv("SAP_BO_CMS", "sefaz-bo1.sefaz.go.gov.br:6400")
BO_AUTH_TYPE = os.getenv("SAP_BO_AUTH_TYPE", "secEnterprise")  # ou secWinAD, secLDAP


class SapBoClient:
    def __init__(self, base_url: str = BO_BASE_URL, cms: str = BO_CMS, auth_type: str = BO_AUTH_TYPE) -> None:
        self.base_url = base_url
        self.cms = cms
        self.auth_type = auth_type
        self.session = requests.Session()
        self.logon_token: str | None = None

    def login(self, username: str, password: str) -> bool:
        """Autentica no SAP BO e obtém o X-SAP-LogonToken."""
        url = f"{self.base_url}/logon/long"
        payload = {
            "userName": username,
            "password": password,
            "auth": self.auth_type,
            "cms": self.cms,
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        print(f"Tentando login no SAP BO ({self.cms}) com o usuário '{username}'...")
        try:
            resp = self.session.post(url, json=payload, headers=headers, timeout=20)
        except Exception as exc:
            print(f"Não foi possível conectar ao servidor SAP BO: {exc}")
            return False
        
        if resp.status_code == 200:
            token = resp.headers.get("X-SAP-LogonToken")
            if not token and resp.text:
                try:
                    token = resp.json().get("logonToken")
                except Exception:
                    pass

            if token:
                self.logon_token = token
                self.session.headers.update({
                    "X-SAP-LogonToken": token,
                    "Accept": "application/json",
                })
                print("Login realizado com sucesso! Token de sessão obtido.")
                return True
            else:
                print("Aviso: Resposta 200, mas o token não foi encontrado nos cabeçalhos.")
                print("Resposta:", resp.text[:300])
                return False
        else:
            print(f"Erro no login (HTTP {resp.status_code}): {resp.text[:400]}")
            return False

    def list_documents(self, search: str | None = None) -> list[dict]:
        """Consulta relatórios e documentos no repositório InfoStore."""
        if not self.logon_token:
            raise RuntimeError("Não autenticado. Execute login() primeiro.")

        query = "SELECT SI_ID, SI_NAME, SI_KIND, SI_UPDATE_TS FROM CI_INFOOBJECTS WHERE SI_INSTANCE=0 AND SI_KIND IN ('Webi', 'CrystalReport')"
        if search:
            query += f" AND SI_NAME LIKE '%{search}%'"
        query += " ORDER BY SI_NAME"

        url = f"{self.base_url}/infostore"
        resp = self.session.get(url, params={"query": query}, timeout=20)
        resp.raise_for_status()

        data = resp.json()
        entries = data.get("entries", [])
        return entries

    def export_webi_document(self, doc_id: int | str, output_path: Path | str) -> bool:
        """Exporta um relatório Webi diretamente para arquivo Excel (.xlsx)."""
        if not self.logon_token:
            raise RuntimeError("Não autenticado. Execute login() primeiro.")

        url = f"{self.base_url}/raylight/v1/documents/{doc_id}"
        headers = {"Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

        print(f"Exportando relatório ID {doc_id} para Excel...")
        resp = self.session.get(url, headers=headers, timeout=60)
        
        if resp.status_code == 200:
            dest = Path(output_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.content)
            print(f"Sucesso! Relatório salvo em: {dest.resolve()} ({len(resp.content)} bytes)")
            return True
        else:
            print(f"Erro ao exportar documento {doc_id} (HTTP {resp.status_code}): {resp.text[:300]}")
            return False

    def logout(self) -> None:
        """Encerra a sessão no SAP BO."""
        if self.logon_token:
            try:
                self.session.post(f"{self.base_url}/logoff", timeout=10)
                print("Sessão encerrada.")
            except Exception:
                pass


def main() -> None:
    print("=" * 65)
    print(" TESTE DE CONEXÃO E CONSULTA: SAP BUSINESSOBJECTS (BOE / BIPRWS)")
    print("=" * 65)

    user = os.getenv("SAP_BO_USER") or input("Digite seu usuário do SAP BO: ").strip()
    pwd = os.getenv("SAP_BO_PASS") or getpass.getpass("Digite sua senha do SAP BO: ")

    client = SapBoClient()
    if not client.login(user, pwd):
        print("Falha na autenticação. Verifique usuário, senha ou tipo de autenticação.")
        return

    try:
        termo = input("\nDigite um termo para buscar relatórios (ou deixe vazio para listar): ").strip()
        docs = client.list_documents(search=termo if termo else None)
        print(f"\nDocumentos encontrados ({len(docs)}):")
        for d in docs[:15]:
            doc_id = d.get("id") or d.get("SI_ID")
            nome = d.get("name") or d.get("SI_NAME")
            tipo = d.get("kind") or d.get("SI_KIND")
            print(f"  • [ID: {doc_id}] ({tipo}) {nome}")

        if docs:
            escolha = input("\nDigite o ID do relatório que deseja baixar em Excel (ou Enter para sair): ").strip()
            if escolha:
                saida = BASE_DIR / "data" / f"relatorio_bo_{escolha}.xlsx"
                client.export_webi_document(escolha, saida)
    finally:
        client.logout()


if __name__ == "__main__":
    main()
