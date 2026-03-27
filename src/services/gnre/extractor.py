"""
src/services/gnre/extractor.py
================================
Etapas 1 e 2 — Extração e validação dos campos da guia GNRE.

Responsabilidades:
  - Abrir o PDF e extrair o texto da 1ª via (descarta 2ª e 3ª via)
  - Mapear cada campo do layout GNRE pelo número da linha
  - Aplicar fallback: buscar Nº Documento na chave de acesso NF-e
  - Retornar um GnreCampos (dataclass) e uma lista de erros de validação
"""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    raise ImportError("Execute:  pip install pdfplumber")

logger = logging.getLogger(__name__)


# ─── Dataclass de campos extraídos ───────────────────────────────────────────

@dataclass
class GnreCampos:
    """Representa todos os campos extraídos de uma guia GNRE."""

    arquivo:            str  = ""

    # Cabeçalho
    uf_favorecida:      str  = ""
    codigo_receita:     str  = ""
    num_controle:       str  = ""

    # Contribuinte emitente
    razao_social:       str  = ""
    cnpj:               str  = ""
    uf_emitente:        str  = ""

    # Dados da guia
    vencimento:         str  = ""
    n_doc_origem:       str  = ""
    periodo_referencia: str  = ""

    # Valores
    valor_principal:    str  = "0,00"
    atualizacao_monet:  str  = "0,00"
    juros:              str  = "0,00"
    multa:              str  = "0,00"
    total_recolher:     str  = "0,00"

    # Pagamento
    doc_valido:         str  = ""
    linha_digitavel:    str  = ""

    # Chave NF-e
    chave_nf:           str  = ""

    # Meta
    erros:              list = field(default_factory=list)
    avisos:             list = field(default_factory=list)

    @property
    def valido(self) -> bool:
        return len(self.erros) == 0


# ─── Extractor ────────────────────────────────────────────────────────────────

class GnreExtractor:
    """
    Extrai campos de uma guia GNRE a partir de um PDF.

    Mapeamento de linhas do layout padrão GNRE:
      L00  UF Favorecida  Código da Receita
      L01  Guia Nacional de Recolhimento de Tributos Estaduais - GNRE
      L02  <UF> <CodReceita>
      L03  Dados do Contribuinte Emitente  Nº de Controle
      L04  Razão Social:  CNPJ/CPF/Insc. Est.:  <NºControle>
      L05  <Razão Social>  <CNPJ>  Data de Vencimento
      L06  Endereço: <end>  <Vencimento>
      L07  Município: <mun>  UF: <UF>  Nº Documento de Origem
      L08  CEP: <cep>  Telefone: <tel>  <NºDocOrigem>
      L09  Dados do Destinatário  Período de Referência  Parcela
      L10  CPF/CNPJ/Insc. Est.:  <periodo>
      L11  Município:  Valor Principal
      L12  Reservado à Fiscalização  R$ <ValorPrincipal>
      L13  A   (letra inicial de "Autenticação" — ignore)
      L14  Convênio/Protocolo:  Atualização Monetária  u
      L15  Produto:  R$ <AtualizMonet>  t
      L16  e
      L17  Juros  n
      L18  Informações Complementares:  R$ <Juros>  t i
      L19  Chave: <chave44>.  PIX: <pix>  Multa  c
      L20  R$ <Multa>  a
      L21  ç
      L22  Total a Recolher  ã
      L23  Documento Válido para pagamento <data>  R$ <Total>  o
      L24  <linha_digitável>
    """

    def extrair(self, caminho: Path) -> GnreCampos:
        campos = GnreCampos(arquivo=caminho.name)

        texto = self._texto_1a_via(caminho)
        if not texto:
            campos.erros.append("Nenhum texto extraído do PDF — verifique se é escaneado.")
            return campos

        linhas = texto.strip().split("\n")
        self._parse_linhas(linhas, campos)
        self._fallback_n_doc(campos)
        self._validar(campos)

        return campos

    # ── Extração de texto ─────────────────────────────────────────────────────

    def _texto_1a_via(self, caminho: Path) -> str:
        blocos: list[str] = []
        try:
            with pdfplumber.open(caminho) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        blocos.append(t)
        except Exception as exc:
            logger.error(f"Erro ao abrir PDF '{caminho.name}': {exc}")
            return ""

        texto = "\n".join(blocos)

        for marcador in ("1ª via", "1a via", "PRIMEIRA VIA"):
            if marcador in texto:
                return texto[: texto.index(marcador)]

        return texto

    # ── Parser linha a linha ──────────────────────────────────────────────────

    def _parse_linhas(self, linhas: list[str], c: GnreCampos) -> None:

        def L(i: int) -> str:
            return linhas[i].strip() if 0 <= i < len(linhas) else ""

        # L02 — UF Favorecida + Código Receita
        m = re.match(r"([A-Z]{2})\s+(\d+)", L(2))
        if m:
            c.uf_favorecida  = m.group(1)
            c.codigo_receita = m.group(2)

        # L04 — Nº de Controle (último token)
        tokens_l04 = L(4).split()
        c.num_controle = tokens_l04[-1] if tokens_l04 else ""

        # L05 — Razão Social + CNPJ
        l05 = L(5)
        m_cnpj = re.search(r"([\d]{2}\.[\d]{3}\.[\d]{3}/[\d]{4}-[\d]{2})", l05)
        if m_cnpj:
            c.cnpj      = m_cnpj.group(1)
            c.razao_social = l05[: l05.index(c.cnpj)].strip()

        # L06 — Vencimento (último token, formato DD/MM/AAAA)
        l06_tokens = L(6).split()
        candidato  = l06_tokens[-1] if l06_tokens else ""
        if re.match(r"\d{2}/\d{2}/\d{4}", candidato):
            c.vencimento = candidato

        # L07 — UF Emitente
        m_uf = re.search(r"UF:\s+([A-Z]{2})", L(7))
        if m_uf:
            c.uf_emitente = m_uf.group(1)

        # L08 — Nº Documento de Origem (último token numérico)
        l08_tokens = L(8).split()
        if l08_tokens and l08_tokens[-1].isdigit():
            c.n_doc_origem = l08_tokens[-1]

        # L10 — Período de Referência (último token)
        l10_tokens = L(10).split()
        c.periodo_referencia = l10_tokens[-1] if l10_tokens else ""

        # Valores R$ — captura todos em ordem de aparição no texto
        texto = "\n".join(linhas)
        valores = re.findall(r"R\$\s*([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})", texto)

        def _v(i: int) -> str:
            return valores[i] if i < len(valores) else "0,00"

        c.valor_principal   = _v(0)
        c.atualizacao_monet = _v(1)
        c.juros             = _v(2)
        c.multa             = _v(3)
        c.total_recolher    = _v(4)

        # L23 — Data Documento Válido
        m_dv = re.search(r"Documento V[áa]lido.*?(\d{2}/\d{2}/\d{4})", L(23))
        if m_dv:
            c.doc_valido = m_dv.group(1)

        # L24 — Linha digitável / código de barras
        c.linha_digitavel = L(24).strip()

        # L19 — Chave de acesso NF-e (44 dígitos)
        m_chave = re.search(r"Chave:\s*(\d{44})", L(19))
        if m_chave:
            c.chave_nf = m_chave.group(1)

    # ── Fallback: Nº Documento via chave NF-e ────────────────────────────────

    @staticmethod
    def _fallback_n_doc(c: GnreCampos) -> None:
        """
        Quando o campo 'Nº Documento de Origem' está vazio na guia,
        extrai o nNF da chave de acesso NF-e (posições 26-34, base 1).
        """
        if not c.n_doc_origem and c.chave_nf:
            try:
                c.n_doc_origem = str(int(c.chave_nf[25:34]))
                c.avisos.append(
                    f"Nº Documento extraído da chave NF-e: {c.n_doc_origem}"
                )
                logger.debug(
                    f"{c.arquivo}: nDoc via chave NF-e → {c.n_doc_origem}"
                )
            except (ValueError, IndexError):
                pass

    # ── Validação de campos obrigatórios ─────────────────────────────────────

    OBRIGATORIOS = {
        "uf_favorecida":  "UF Favorecida",
        "codigo_receita": "Código da Receita",
        "cnpj":           "CNPJ do Emitente",
        "vencimento":     "Data de Vencimento",
        "total_recolher": "Total a Recolher",
    }

    def _validar(self, c: GnreCampos) -> None:
        for campo, label in self.OBRIGATORIOS.items():
            val = getattr(c, campo, "")
            if not val or val == "0,00":
                c.erros.append(f"Campo obrigatório ausente ou zerado: {label}")

        if not c.n_doc_origem:
            c.avisos.append(
                "Nº Documento de Origem não encontrado "
                "(nem via chave NF-e) — o Nº Título usará o Nº de Controle."
            )
