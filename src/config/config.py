"""
src/config/config.py
====================
Gerenciador central de configurações do serviço GNRE.

Responsabilidades:
  - Localizar a raiz do projeto em desenvolvimento E no executável PyInstaller
  - Ler settings.ini e process.json
  - Criar pastas obrigatórias automaticamente
  - Expor configurações tipadas para os demais módulos
"""

import sys
import json
import logging
import configparser
from pathlib import Path


# ─── Localização da raiz do projeto ──────────────────────────────────────────
# Quando empacotado pelo PyInstaller (--onefile), os arquivos internos ficam
# em sys._MEIPASS, mas config/ e data/ devem estar ao lado do executável.
# Em desenvolvimento, a raiz é dois níveis acima de src/config/config.py.

def _resolve_root() -> Path:
    if getattr(sys, "frozen", False):
        # Executável PyInstaller: raiz = pasta onde o .exe está
        return Path(sys.executable).resolve().parent
    # Desenvolvimento: dois níveis acima de src/config/config.py
    return Path(__file__).resolve().parents[2]


ROOT = _resolve_root()


class Config:
    """Carrega e valida todas as configurações do serviço."""

    def __init__(self) -> None:
        self._ini  = self._load_ini()
        self._proc = self._load_process()
        self._ensure_dirs()

    # ── Loaders ──────────────────────────────────────────────────────────────

    def _load_ini(self) -> configparser.ConfigParser:
        path = ROOT / "config" / "settings.ini"
        if not path.exists():
            raise FileNotFoundError(
                f"Arquivo de configuração não encontrado: {path}\n"
                "Certifique-se de que a pasta config/ existe ao lado do executável."
            )
        ini = configparser.ConfigParser()
        ini.read(path, encoding="utf-8")
        return ini

    def _load_process(self) -> dict:
        path = ROOT / "config" / "process.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Arquivo de regras não encontrado: {path}"
            )
        with open(path, encoding="utf-8") as f:
            return json.load(f)

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
        return self.get("erp", "situacao", "AB")

    @property
    def erp_forma_pagamento(self) -> str:
        return self.get("erp", "forma_pagamento", "")

    @property
    def erp_natureza(self) -> str:
        return self.get("erp", "natureza", "")

    @property
    def erp_codfil(self) -> str:
        """Filial fixa para todos os registros (settings.ini → [erp] codfil)."""
        return self.get("erp", "codfil", "1")

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
    def codemp_razao_social(self) -> dict[str, str]:
        """
        De-Para: trecho da Razão Social → CODEMP.
        Chaves são trechos (case-insensitive) que serão buscados na razão social
        do PDF. Ex: {"ULTRA": "2", "NAUTIKA": "2"}
        """
        return {k: v for k, v in self._proc.get("codemp_razao_social", {}).items()
                if not k.startswith("_")}

    @property
    def campos_obrigatorios(self) -> list[str]:
        return self._proc.get("campos_obrigatorios", [])

    @property
    def layout_csv(self) -> list[str]:
        return self._proc.get("layout_csv", [])

    @property
    def data_entrada_padrao(self) -> str:
        """
        Valor do campo 'Data de Entrada' (movimento padrão).
        Retorna 'hoje' ou uma data fixa DD/MM/AAAA conforme process.json.
        """
        return self._proc.get("data_entrada_padrao", {}).get("valor", "hoje")