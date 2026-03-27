
"""
src/services/erp/mapper.py
===========================
Etapa 3 — De-Para e montagem do layout ERP Senior.

Responsabilidades:
  - Converter UF Favorecida → Código Fornecedor SEFAZ
  - Converter Código Receita → Tipo do Título no ERP
  - Compor o Nº Título
  - Montar o dicionário final com as colunas do CSV de importação
"""

import logging
from datetime import datetime

from src.config.config import Config
from src.services.gnre.extractor import GnreCampos

logger = logging.getLogger(__name__)


class ErpMapper:
    """Transforma GnreCampos no layout de importação do ERP Senior."""

    def __init__(self, config: Config) -> None:
        self.cfg = config

    # ── Interface pública ────────────────────────────────────────────────────

    def mapear(
        self,
        campos: GnreCampos,
        data_emissao: str | None = None,
    ) -> dict[str, str]:
        """
        Recebe os campos extraídos da guia e retorna o dicionário
        com as colunas exatas do layout CSV do Senior.

        Args:
            campos:       Resultado do GnreExtractor.
            data_emissao: Data de Emissão/Entrada no formato DD/MM/AAAA.
                          Se None, usa a data de hoje.
        """
        data_ref = data_emissao or datetime.today().strftime("%d/%m/%Y")

        num_titulo  = self._num_titulo(campos)
        tipo        = self._tipo_erp(campos.codigo_receita)
        cod_for     = self._cod_for(campos.uf_favorecida)

        logger.debug(
            f"{campos.arquivo}: "
            f"Título={num_titulo}  Tipo={tipo}  CodFor={cod_for}"
        )

        return {
            "Nº Título":             num_titulo,
            "Tipo":                  tipo,
            "Cod For":               cod_for,
            "Transação":             self.cfg.erp_transacao,
            "Situação":              self.cfg.erp_situacao,
            "Natureza":              self.cfg.erp_natureza,
            "Data Emissão":          data_ref,
            "Data de Entrada":       data_ref,
            "Vencimento Original":   campos.vencimento,
            "Valor Original":        campos.total_recolher,
            "Vencimento Prorrogado": campos.vencimento,
            "Forma de Pagamento":    self.cfg.erp_forma_pagamento,
            "Valor Multa Negociada": campos.multa,
            "Leitor":                campos.linha_digitavel,
        }

    # ── De-Para ──────────────────────────────────────────────────────────────

    def _num_titulo(self, c: GnreCampos) -> str:
        """
        Regra: <n_doc_origem>-GNRE-<uf_favorecida>
        Fallback: usa Nº de Controle quando n_doc_origem está vazio.
        """
        base = c.n_doc_origem or c.num_controle
        return f"{base}-GNRE-{c.uf_favorecida}" if base and c.uf_favorecida else base

    def _tipo_erp(self, codigo_receita: str) -> str:
        """De-Para Código Receita → Tipo ERP (process.json)."""
        tipo = self.cfg.tipo_erp.get(codigo_receita)
        if not tipo:
            tipo = f"GNRE-{codigo_receita}"
            logger.warning(
                f"Código de Receita '{codigo_receita}' não mapeado em process.json. "
                f"Usando '{tipo}' — adicione o De-Para se necessário."
            )
        return tipo

    def _cod_for(self, uf: str) -> str:
        """De-Para UF Favorecida → Código Fornecedor SEFAZ (process.json)."""
        cod = self.cfg.sefaz_cod_for.get(uf, "")
        if not cod:
            logger.warning(
                f"UF '{uf}' não encontrada no De-Para sefaz_cod_for (process.json)."
            )
        return cod
