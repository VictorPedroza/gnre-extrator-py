"""
src/config/config.py
====================
Gerenciador central de configurações do serviço GNRE.

Responsabilidades:
  - Localizar a raiz do projeto independente de onde o script é chamado
  - Ler settings.ini e process.json
  - Criar pastas obrigatórias automaticamente
  - Expor configurações tipadas para os demais módulos
"""

import json
import logging
import configparser
import sys
import os
from pathlib import Path


def get_project_root() -> Path:
    """
    Detecta a raiz do projeto de forma robusta:
    - Quando executado como script Python normal
    - Quando executado como executável PyInstaller
    """
    if getattr(sys, 'frozen', False):
        # Estamos rodando como executável (PyInstaller)
        # sys.executable é o caminho do .exe
        executable_path = Path(sys.executable)
        # A raiz é a pasta onde está o executável
        return executable_path.parent
    else:
        # Estamos rodando como script Python
        # __file__ está em src/config/config.py
        # Subimos 2 níveis para chegar na raiz do projeto
        return Path(__file__).resolve().parents[2]


# Raiz do projeto (pasta onde estão config/, src/, dist/)
ROOT = get_project_root()


class Config:
    """Carrega e valida todas as configurações do serviço."""

    def __init__(self) -> None:
        self._ini = self._load_ini()
        self._proc = self._load_process()
        self._ensure_dirs()

    # ── Loaders ──────────────────────────────────────────────────────────────

    def _load_ini(self) -> configparser.ConfigParser:
        path = ROOT / "config" / "settings.ini"
        if not path.exists():
            # Tenta criar um arquivo default se não existir
            self._create_default_ini(path)
        
        ini = configparser.ConfigParser()
        ini.read(path, encoding="utf-8")
        return ini

    def _create_default_ini(self, path: Path) -> None:
        """Cria um arquivo settings.ini padrão se ele não existir."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        default_content = """[system]
name = GNRE Processor
version = 1.0.0
log_level = INFO

[paths]
entrada = entrada
saida = saida
backup = backup
temp = temp
logs = logs

[processing]
backup_after_process = True
move_on_error = True
extensions = .pdf

[csv]
delimiter = ;
encoding = utf-8-sig
output_prefix = importacao_senior

[erp]
transacao = GNRE
situacao = A
forma_pagamento = 
natureza = 
"""
        path.write_text(default_content, encoding="utf-8")
        print(f"📝  Arquivo de configuração padrão criado em: {path}")

    def _load_process(self) -> dict:
        path = ROOT / "config" / "process.json"
        if not path.exists():
            self._create_default_process(path)
        
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _create_default_process(self, path: Path) -> None:
        """Cria um arquivo process.json padrão se ele não existir."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        default_content = {
            "sefaz_cod_for": {
                "AC": "1001",
                "AL": "1002",
                "AP": "1003",
                "AM": "1004",
                "BA": "1005",
                "CE": "1006",
                "DF": "1007",
                "ES": "1008",
                "GO": "1009",
                "MA": "1010",
                "MT": "1011",
                "MS": "1012",
                "MG": "1013",
                "PA": "1014",
                "PB": "1015",
                "PR": "1016",
                "PE": "1017",
                "PI": "1018",
                "RJ": "1019",
                "RN": "1020",
                "RS": "1021",
                "RO": "1022",
                "RR": "1023",
                "SC": "1024",
                "SP": "1025",
                "SE": "1026",
                "TO": "1027"
            },
            "tipo_erp": {
                "100-6": "GNRE-ICMS",
                "101-3": "GNRE-FECP",
                "102-1": "GNRE-MULTA",
                "103-0": "GNRE-JUROS"
            },
            "campos_obrigatorios": [
                "uf_favorecida",
                "codigo_receita",
                "cnpj",
                "vencimento",
                "total_recolher"
            ],
            "layout_csv": [
                "Nº Título",
                "Tipo",
                "Cod For",
                "Transação",
                "Situação",
                "Natureza",
                "Data Emissão",
                "Data de Entrada",
                "Vencimento Original",
                "Valor Original",
                "Vencimento Prorrogado",
                "Forma de Pagamento",
                "Valor Multa Negociada",
                "Leitor"
            ]
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_content, f, indent=2, ensure_ascii=False)
        
        print(f"📝  Arquivo de regras padrão criado em: {path}")

    def _ensure_dirs(self) -> None:
        """Cria automaticamente as pastas de dados e logs se não existirem."""
        for key in ("entrada", "saida", "backup", "temp"):
            self.path(key).mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    # ── Atalhos de seção ─────────────────────────────────────────────────────

    def get(self, section: str, key: str, fallback: str = "") -> str:
        return self._ini.get(section, key, fallback=fallback)

    def getbool(self, section: str, key: str, fallback: bool = False) -> bool:
        return self._ini.getboolean(section, key, fallback=fallback)

    # ── Paths ─────────────────────────────────────────────────────────────────

    def path(self, name: str) -> Path:
        """Retorna o Path absoluto de uma pasta configurada em [paths]."""
        rel = self._ini.get("paths", name, fallback=f"data/{name}")
        return ROOT / rel

    @property
    def logs_dir(self) -> Path:
        return ROOT / self._ini.get("paths", "logs", fallback="logs")

    @property
    def root(self) -> Path:
        return ROOT

    # ── System ────────────────────────────────────────────────────────────────

    @property
    def system_name(self) -> str:
        return self.get("system", "name", "GNRE Processor")

    @property
    def version(self) -> str:
        return self.get("system", "version", "1.0.0")

    @property
    def log_level(self) -> int:
        level = self.get("system", "log_level", "INFO").upper()
        return getattr(logging, level, logging.INFO)

    # ── Processing ────────────────────────────────────────────────────────────

    @property
    def backup_after_process(self) -> bool:
        return self.getbool("processing", "backup_after_process", True)

    @property
    def move_on_error(self) -> bool:
        return self.getbool("processing", "move_on_error", True)

    @property
    def extensions(self) -> list[str]:
        raw = self.get("processing", "extensions", ".pdf")
        return [e.strip().lower() for e in raw.split(",")]

    # ── CSV ───────────────────────────────────────────────────────────────────

    @property
    def csv_delimiter(self) -> str:
        return self.get("csv", "delimiter", ";")

    @property
    def csv_encoding(self) -> str:
        return self.get("csv", "encoding", "utf-8-sig")

    @property
    def csv_output_prefix(self) -> str:
        return self.get("csv", "output_prefix", "importacao_senior")

    # ── ERP ───────────────────────────────────────────────────────────────────

    @property
    def erp_transacao(self) -> str:
        return self.get("erp", "transacao", "GNRE")

    @property
    def erp_situacao(self) -> str:
        return self.get("erp", "situacao", "A")

    @property
    def erp_forma_pagamento(self) -> str:
        return self.get("erp", "forma_pagamento", "")

    @property
    def erp_natureza(self) -> str:
        return self.get("erp", "natureza", "")

    # ── Process.json ─────────────────────────────────────────────────────────

    @property
    def sefaz_cod_for(self) -> dict[str, str]:
        return {k: v for k, v in self._proc.get("sefaz_cod_for", {}).items()
                if not k.startswith("_")}

    @property
    def tipo_erp(self) -> dict[str, str]:
        return {k: v for k, v in self._proc.get("tipo_erp", {}).items()
                if not k.startswith("_")}

    @property
    def campos_obrigatorios(self) -> list[str]:
        return self._proc.get("campos_obrigatorios", [])

    @property
    def layout_csv(self) -> list[str]:
        return self._proc.get("layout_csv", [])