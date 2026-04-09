"""
src/services/gnre/extractor.py
================================
Etapas 1 e 2 — Extração e validação dos campos da guia GNRE.

Responsabilidades:
  - Abrir o PDF e extrair o texto da 1ª via (descarta 2ª e 3ª via)
  - Mapear cada campo do layout GNRE pelo número da linha
  - Aplicar fallback: buscar Nº Documento nas informações complementares
    via chave de acesso NF-e (prefixos: "Chave:", "CHAVE DFE", "CHAVE NF-E" etc.)
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

    # Nº Documento extraído de "Documento: XXXX" nas informações complementares (ex: PB)
    n_doc_complementar: str  = ""

    # Meta
    erros:              list = field(default_factory=list)
    avisos:             list = field(default_factory=list)

    @property
    def valido(self) -> bool:
        return len(self.erros) == 0


# ─── Regex para chave de acesso NF-e nas Informações Complementares ──────────
#
# O campo "Informações Complementares" pode conter a chave em formatos variados:
#   - "Chave: 35260326760956000185550030000084071834406611. PIX: ..."   (BA - com n_doc)
#   - "CHAVE DFE 35260326760956000185550030000083511832983371"           (MS - sem n_doc)
#   - "CHAVE NF-E 35260326..."                                           (outros)
#
# A regex captura 44 dígitos precedidos por qualquer um desses prefixos.
_RE_CHAVE_NF = re.compile(
    r"(?:Chave\s*[:\-]?\s*|CHAVE\s+(?:DFE|NF-?E)\s+)(\d{44})",
    re.IGNORECASE,
)

# ─── Regex para "Documento: XXXX" nas Informações Complementares (ex: PB) ────
#
# A PB inclui nas informações complementares uma tag "Documento:" que pode ter
# dois formatos:
#
#   Formato A — chave NF-e de 44 dígitos contíguos (sem espaço interno):
#     "Documento: 35260326760956000185550600000021561797078878 Multa c"
#     O nNF está nas posições 25-34 da chave (int → sem zeros à esquerda).
#
#   Formato B — número curto (nNF direto, ≤ 9 dígitos):
#     "Documento: 20315745"
#     O valor já é o nNF e é usado diretamente.
#
# A regex tenta primeiro capturar exatamente 44 dígitos (grupo 1),
# e como fallback captura qualquer sequência numérica mais curta (grupo 2).
_RE_DOC_COMPLEMENTAR = re.compile(
    r"Documento\s*:\s*(\d{44})(?!\d)"   # Formato A: exatamente 44 dígitos
    r"|Documento\s*:\s*(\d{1,9})(?!\d)",  # Formato B: número curto ≤ 9 dígitos
    re.IGNORECASE,
)


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
      L08  CEP: <cep>  Telefone: [<NºDocOrigem>]   ← ausente quando vazio
      L09  Dados do Destinatário  Período de Referência  Parcela
      L10  CPF/CNPJ/Insc. Est.:  [<periodo>]
      L11  Município:  Valor Principal
      L12  Reservado à Fiscalização  R$ <ValorPrincipal>
      L13  A
      L14  Convênio/Protocolo:  Atualização Monetária  u
      L15  Produto:  R$ <AtualizMonet>  t
      L16  e
      L17  Juros  n
      L18  Informações Complementares:  R$ <Juros>  t i
      L19  [<chave_ou_conteudo>]  Multa  c          ← chave NF-e aqui quando presente
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
            c.cnpj         = m_cnpj.group(1)
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

        # L08 — Nº Documento de Origem: último token numérico após "Telefone:"
        # Quando presente, o número aparece colado ao final da linha (ex: "CEP: 07220-010 Telefone: 8452")
        # Quando ausente, a linha termina em "Telefone:" sem valor.
        l08 = L(8)
        m_ndoc = re.search(r"Telefone:\s*(\d+)\s*$", l08)
        if m_ndoc:
            c.n_doc_origem = m_ndoc.group(1)

        # L10 — Período de Referência: busca padrão MM/AAAA no final da linha
        # (quando ausente o período, o token final pode ser apenas parte do texto)
        l10 = L(10)
        m_per = re.search(r"(\d{2}/\d{4})\s*$", l10)
        if m_per:
            c.periodo_referencia = m_per.group(1)
        else:
            # Fallback: último token
            l10_tokens = l10.split()
            c.periodo_referencia = l10_tokens[-1] if l10_tokens else ""

        # Chave NF-e — busca no texto completo das "Informações Complementares"
        # A chave pode aparecer em L19 (com chave) ou não existir (sem chave).
        # Varremos todo o bloco de texto para robustez máxima.
        texto_completo = "\n".join(linhas)
        m_chave = _RE_CHAVE_NF.search(texto_completo)
        if m_chave:
            c.chave_nf = m_chave.group(1)
            logger.debug(f"{c.arquivo}: Chave NF-e encontrada → {c.chave_nf}")

        # "Documento: XXXX" nas informações complementares (ex: PB)
        # Capturado apenas dentro do bloco após "Informações Complementares:"
        m_inf = re.search(r"Informa[çc][oõ]es Complementares:(.+?)(?:Documento V[áa]lido|$)",
                          texto_completo, re.DOTALL | re.IGNORECASE)
        if m_inf:
            m_doc_comp = _RE_DOC_COMPLEMENTAR.search(m_inf.group(1))
            if m_doc_comp:
                # grupo 1 = chave 44 dígitos; grupo 2 = número curto
                c.n_doc_complementar = m_doc_comp.group(1) or m_doc_comp.group(2)
                logger.debug(f"{c.arquivo}: Documento complementar encontrado → {c.n_doc_complementar}")

        # Valores R$ — captura todos em ordem de aparição no texto
        valores = re.findall(r"R\$\s*([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})", texto_completo)

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

    # ── Fallback: Nº Documento via informações complementares ou chave NF-e ───

    # Alguns estados (ex: PB) preenchem o campo "Nº Documento de Origem" com o
    # número de protocolo SEFAZ (tipicamente 16 dígitos) em vez do nNF da nota.
    # O nNF na chave NF-e ocupa 9 posições (máximo 999.999.999), portanto
    # qualquer n_doc_origem com mais de 9 dígitos é tratado como protocolo e
    # substituído. A ordem de prioridade do fallback é:
    #   1. "Documento: XXXX" nas informações complementares  (mais explícito)
    #   2. nNF extraído da chave NF-e  (posições 25-34)
    _MAX_NNF_DIGITS = 9

    @staticmethod
    def _fallback_n_doc(c: GnreCampos) -> None:
        """
        Garante que n_doc_origem contenha o nNF real da NF-e.

        Aciona o fallback em dois casos:
          1. n_doc_origem está vazio.
          2. n_doc_origem tem mais de 9 dígitos — protocolo SEFAZ (ex: PB).

        Ordem de preferência para preencher:
          a. n_doc_complementar — "Documento: XXXX" nas informações complementares.
          b. nNF da chave NF-e  — posições 25-34 da chave de 44 dígitos.

        Estrutura da chave NF-e (44 dígitos):
          UF(2) AAMM(4) CNPJ(14) Modelo(2) Serie(3) nNF(9) tpEmit(1) cNF(8) cDV(1)
          → nNF = chave[25:34]
        """
        precisa_fallback = (
            not c.n_doc_origem
            or (c.n_doc_origem.isdigit()
                and len(c.n_doc_origem) > GnreExtractor._MAX_NNF_DIGITS)
        )

        if not precisa_fallback:
            return

        motivo_original = (
            "ausente no campo"
            if not c.n_doc_origem
            else f"protocolo SEFAZ ({c.n_doc_origem}) substituído"
        )

        # Prioridade 1: "Documento: XXXX" das informações complementares
        if c.n_doc_complementar:
            valor = c.n_doc_complementar

            if len(valor) == 44 and valor.isdigit():
                # Formato A: valor é a chave NF-e completa → extrai nNF das pos 25-34
                try:
                    n_doc = str(int(valor[25:34]))
                    c.n_doc_origem = n_doc
                    c.avisos.append(
                        f"Nº Documento extraído da chave em 'Documento:' nas informações "
                        f"complementares (pos 25-34) — {motivo_original}: {c.n_doc_origem}"
                    )
                    logger.debug(
                        f"{c.arquivo}: nDoc via Documento:/chave [{motivo_original}] → {c.n_doc_origem}"
                    )
                except (ValueError, IndexError):
                    logger.warning(
                        f"{c.arquivo}: 'Documento:' contém chave mas nNF inválido "
                        f"(valor={valor!r})"
                    )
            else:
                # Formato B: valor é o nNF direto (número curto ≤ 9 dígitos)
                c.n_doc_origem = str(int(valor)) if valor.isdigit() else valor
                c.avisos.append(
                    f"Nº Documento extraído de 'Documento:' nas informações "
                    f"complementares — {motivo_original}: {c.n_doc_origem}"
                )
                logger.debug(
                    f"{c.arquivo}: nDoc via Documento:/direto [{motivo_original}] → {c.n_doc_origem}"
                )
            return

        # Prioridade 2: nNF da chave NF-e
        if c.chave_nf:
            try:
                n_doc = str(int(c.chave_nf[25:34]))
                c.n_doc_origem = n_doc
                c.avisos.append(
                    f"Nº Documento extraído da chave NF-e "
                    f"— {motivo_original}: {c.n_doc_origem}"
                )
                logger.debug(
                    f"{c.arquivo}: nDoc via chave NF-e [{motivo_original}] → {c.n_doc_origem}"
                )
            except (ValueError, IndexError):
                logger.warning(
                    f"{c.arquivo}: Chave NF-e encontrada mas nNF inválido "
                    f"(chave={c.chave_nf!r})"
                )

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