"""
src/services/folder/controller.py
==================================
Controlador de pastas — localiza, move e organiza os arquivos do serviço.

Responsabilidades:
  - Listar PDFs na pasta de entrada
  - Mover arquivos processados para saída/backup
  - Mover arquivos com erro para subpasta de erros
  - Limpar pasta temporária
"""

import shutil
import logging
from pathlib import Path
from datetime import datetime

from src.config.config import Config

logger = logging.getLogger(__name__)


class FolderController:
    """Gerencia movimentação e organização dos arquivos do serviço."""

    def __init__(self, config: Config) -> None:
        self.cfg     = config
        self.entrada = config.path("entrada")
        self.saida   = config.path("saida")
        self.backup  = config.path("backup")
        self.temp    = config.path("temp")
        self._error_dir: Path | None = None

    # ── Listagem ──────────────────────────────────────────────────────────────

    def listar_pdfs(self) -> list[Path]:
        """Retorna todos os PDFs válidos na pasta de entrada, ordenados por nome."""
        pdfs = sorted(
            f for f in self.entrada.iterdir()
            if f.is_file() and f.suffix.lower() in self.cfg.extensions
        )
        logger.info(f"Encontrado(s) {len(pdfs)} arquivo(s) em '{self.entrada}'")
        return pdfs

    # ── Movimentação ─────────────────────────────────────────────────────────

    def mover_para_backup(self, arquivo: Path) -> Path | None:
        """Move o PDF para backup/<AAAA-MM-DD>/. Retorna o novo caminho."""
        if not self.cfg.backup_after_process:
            return None
        destino_dir = self.backup / datetime.today().strftime("%Y-%m-%d")
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = self._destino_unico(destino_dir, arquivo.name)
        shutil.move(str(arquivo), destino)
        logger.debug(f"Backup: {arquivo.name} → {destino}")
        return destino

    def mover_para_erro(self, arquivo: Path, motivo: str = "") -> Path:
        """Move o PDF para saida/erros/<AAAA-MM-DD>/ com log do motivo."""
        if not self.cfg.move_on_error:
            return arquivo
        dir_erro = self.saida / "erros" / datetime.today().strftime("%Y-%m-%d")
        dir_erro.mkdir(parents=True, exist_ok=True)
        destino = self._destino_unico(dir_erro, arquivo.name)
        shutil.move(str(arquivo), destino)

        if motivo:
            log_path = destino.with_suffix(".log.txt")
            log_path.write_text(
                f"Arquivo: {arquivo.name}\n"
                f"Data   : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"Motivo : {motivo}\n",
                encoding="utf-8",
            )
        logger.warning(f"Erro: {arquivo.name} → {destino}  |  {motivo}")
        return destino

    # ── CSV de saída ─────────────────────────────────────────────────────────

    def caminho_csv_saida(self, prefixo: str = "") -> Path:
        """
        Gera o caminho do CSV de saída com data/hora no nome para evitar
        sobrescrita em execuções consecutivas.
        """
        prefixo  = prefixo or self.cfg.csv_output_prefix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome      = f"{prefixo}_{timestamp}.csv"
        return self.saida / nome

    # ── Temp ─────────────────────────────────────────────────────────────────

    def limpar_temp(self) -> None:
        """Remove todos os arquivos da pasta temporária."""
        count = 0
        for f in self.temp.iterdir():
            if f.is_file():
                f.unlink()
                count += 1
        if count:
            logger.debug(f"Temp: {count} arquivo(s) removido(s)")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _destino_unico(diretorio: Path, nome: str) -> Path:
        """Evita colisão de nomes adicionando sufixo incremental se necessário."""
        destino = diretorio / nome
        if not destino.exists():
            return destino
        stem, suffix = Path(nome).stem, Path(nome).suffix
        i = 1
        while True:
            destino = diretorio / f"{stem}_{i}{suffix}"
            if not destino.exists():
                return destino
            i += 1
