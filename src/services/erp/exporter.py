"""
src/services/erp/exporter.py
==============================
Etapa 4 — Geração do arquivo CSV no layout de importação do ERP Senior.

Responsabilidades:
  - Escrever o CSV com cabeçalho, delimitador e encoding corretos
  - Garantir que apenas as colunas do layout_csv (process.json) sejam gravadas
  - Registrar o caminho e quantidade de registros exportados
"""

import csv
import logging
from pathlib import Path

from ...config.config import Config

logger = logging.getLogger(__name__)


class ErpExporter:
    """Grava linhas mapeadas em CSV no formato de importação do Senior."""

    def __init__(self, config: Config) -> None:
        self.cfg = config

    def exportar(self, linhas: list[dict], caminho_saida: Path) -> Path:
        """
        Grava o CSV de saída.

        Args:
            linhas:        Lista de dicionários mapeados pelo ErpMapper.
            caminho_saida: Caminho completo do arquivo CSV a gerar.

        Returns:
            Caminho do arquivo gerado.
        """
        if not linhas:
            logger.warning("Nenhuma linha para exportar — CSV não gerado.")
            return caminho_saida

        colunas = self.cfg.layout_csv

        caminho_saida.parent.mkdir(parents=True, exist_ok=True)

        with open(caminho_saida, "w", newline="", encoding=self.cfg.csv_encoding) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=colunas,
                extrasaction="ignore",
                delimiter=self.cfg.csv_delimiter,
            )
            writer.writerows(linhas)

        logger.info(
            f"CSV gerado: {caminho_saida.name}  "
            f"({len(linhas)} registro(s))"
        )
        return caminho_saida
