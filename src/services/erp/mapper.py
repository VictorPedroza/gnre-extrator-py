"""
src/services/erp/mapper.py
===========================
Etapa 3 — De-Para e montagem do layout ERP Senior.

Regras de negócio aplicadas:
  1.  Nº Título             → <nDoc sem zeros à esquerda>_F01   ex: 000008407 → 8407_F01
  2.  Tipo                  → De-Para Código Receita            100129=FCP / 100102=DIF
  3.  Cod For               → De-Para UF Favorecida SEFAZ (process.json)
  4.  Situação              → Fixo AB (settings.ini → [erp] situacao)
  5.  Data Emissão          → Data de Vencimento da guia (mesmo campo)
  6.  Data de Entrada       → Movimento padrão (process.json → data_entrada_padrao)
  7.  Vencimento Original   → Data de Vencimento da guia
  8.  Vencimento Prorrogado → "Documento Válido para pagamento" da guia
  9.  Valor Multa Negociada → Multa + Juros (soma dos dois campos da guia)
  10. CODEMP                → De-Para Razão Social (process.json → codemp_razao_social)
  11. CODFIL                → Fixo (settings.ini → [erp] codfil)
"""

import logging
from datetime import datetime

from ...config.config import Config
from ..gnre.extractor import GnreCampos

logger = logging.getLogger(__name__)


# ─── Helpers de conversão monetária ──────────────────────────────────────────

def _valor_para_float(valor: str) -> float:
    """Converte string monetária BR (ex: '1.234,56') para float."""
    try:
        return float(valor.replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return 0.0


def _float_para_valor(numero: float) -> str:
    """Converte float para string monetária BR (ex: 1234.56 → '1.234,56')."""
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ─── Mapper ──────────────────────────────────────────────────────────────────

class ErpMapper:
    """Transforma GnreCampos no layout de importação do ERP Senior."""

    def __init__(self, config: Config) -> None:
        self.cfg = config

    # ── Interface pública ────────────────────────────────────────────────────

    def mapear(self, campos: GnreCampos) -> dict[str, str]:
        """
        Recebe os campos extraídos da guia e retorna o dicionário
        com as colunas exatas do layout CSV do Senior.
        """
        num_titulo      = self._num_titulo(campos)                   # Regra 1
        tipo            = self._tipo_erp(campos.codigo_receita)      # Regra 2
        cod_for         = self._cod_for(campos.uf_favorecida)        # Regra 3
        # Regra 4: situacao = AB fixo via settings.ini
        data_emissao    = campos.vencimento                          # Regra 5
        data_entrada    = self._data_entrada()                       # Regra 6
        venc_original   = campos.vencimento                          # Regra 7
        venc_prorrogado = campos.doc_valido or campos.vencimento     # Regra 8
        multa_negociada = self._multa_mais_juros(campos)             # Regra 9
        codemp          = self._codemp(campos.razao_social)          # Regra 10
        codfil          = self.cfg.erp_codfil                        # Regra 11

        logger.debug(
            f"{campos.arquivo}: Título={num_titulo}  Tipo={tipo}  "
            f"CodFor={cod_for}  Emissão={data_emissao}  "
            f"VencOrig={venc_original}  VencProrrog={venc_prorrogado}  "
            f"MultaNeg={multa_negociada}  CODEMP={codemp}  CODFIL={codfil}"
        )

        return {
            "Nº Título":             num_titulo,
            "Tipo":                  tipo,
            "Cod For":               cod_for,
            "Transação":             self.cfg.erp_transacao,
            "Situação":              self.cfg.erp_situacao,
            "Natureza":              self.cfg.erp_natureza,
            "Data Emissão":          data_emissao,
            "Data de Entrada":       data_entrada,
            "Vencimento Original":   venc_original,
            "Valor Original":        campos.total_recolher,
            "Vencimento Prorrogado": venc_prorrogado,
            "Forma de Pagamento":    self.cfg.erp_forma_pagamento,
            "Valor Multa Negociada": multa_negociada,
            "Leitor":                campos.linha_digitavel,
            "CODEMP":                codemp,
            "CODFIL":                codfil,
        }

    # ── Regra 1 — Nº Título ──────────────────────────────────────────────────

    def _num_titulo(self, c: GnreCampos) -> str:
        """
        Formato : <nDoc sem zeros à esquerda>_F01
        Exemplo : '000008407' → '8407_F01'
        Fallback: usa Nº de Controle quando n_doc_origem estiver vazio.
        """
        base = c.n_doc_origem or c.num_controle
        if not base:
            return ""
        numero = str(int(base)) if base.isdigit() else base
        return f"{numero}_F01"

    # ── Regra 2 — Tipo ERP ───────────────────────────────────────────────────

    def _tipo_erp(self, codigo_receita: str) -> str:
        """
        De-Para Código Receita → Tipo ERP (process.json → tipo_erp).
        Mapeamentos vigentes:
          100129 → FCP
          100102 → DIF
        Fallback: GNRE-<cod> com aviso no log.
        """
        tipo = self.cfg.tipo_erp.get(codigo_receita)
        if not tipo:
            tipo = f"GNRE-{codigo_receita}"
            logger.warning(
                f"Código de Receita '{codigo_receita}' não mapeado em process.json "
                f"(tipo_erp). Usando '{tipo}' como fallback."
            )
        return tipo

    # ── Regra 3 — Cod For ────────────────────────────────────────────────────

    def _cod_for(self, uf: str) -> str:
        """De-Para UF Favorecida → Código Fornecedor SEFAZ (process.json → sefaz_cod_for)."""
        cod = self.cfg.sefaz_cod_for.get(uf, "")
        if not cod:
            logger.warning(f"UF '{uf}' não encontrada em sefaz_cod_for (process.json).")
        return cod

    # ── Regra 6 — Data de Entrada ────────────────────────────────────────────

    def _data_entrada(self) -> str:
        """
        Retorna a Data de Entrada conforme process.json → data_entrada_padrao.
          'hoje'       → data de execução do serviço  (DD/MM/AAAA)
          'DD/MM/AAAA' → data fixa informada no JSON
        """
        valor = self.cfg.data_entrada_padrao.strip().lower()
        if valor == "hoje":
            return datetime.today().strftime("%d/%m/%Y")
        try:
            datetime.strptime(valor, "%d/%m/%Y")
            return valor
        except ValueError:
            logger.warning(
                f"data_entrada_padrao inválido ('{valor}') — usando data de hoje."
            )
            return datetime.today().strftime("%d/%m/%Y")

    # ── Regra 9 — Valor Multa Negociada ──────────────────────────────────────

    def _multa_mais_juros(self, c: GnreCampos) -> str:
        """
        Valor Multa Negociada = Multa + Juros extraídos da guia.
        Soma os dois e retorna no formato monetário BR (ex: '1.234,56').
        """
        total = _valor_para_float(c.multa) + _valor_para_float(c.juros)
        return _float_para_valor(total)

    # ── Regra 10 — CODEMP ────────────────────────────────────────────────────

    def _codemp(self, razao_social: str) -> str:
        """
        De-Para Razão Social → CODEMP (process.json → codemp_razao_social).

        Percorre as chaves em ordem e retorna o CODEMP do primeiro trecho
        encontrado na razão social (case-insensitive).

        Exemplo:
          razao_social = "ULTRA SPORTS COMERCIO DIGITAL LTDA"
          chaves       = {"ULTRA": "2", "NAUTIKA": "2"}
          → retorna "2"

        Fallback: string vazia com aviso no log.
        """
        rs_upper = razao_social.upper()
        for trecho, codemp in self.cfg.codemp_razao_social.items():
            if trecho.upper() in rs_upper:
                return codemp

        logger.warning(
            f"Razão Social '{razao_social}' não encontrada em "
            f"codemp_razao_social (process.json) — CODEMP ficará vazio."
        )
        return ""