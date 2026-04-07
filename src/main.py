"""
src/main.py
============
Etapa 5 — Orquestrador principal do serviço GNRE → ERP Senior.

Fluxo de execução:
  1. Carrega configurações (Config)
  2. Lista PDFs na pasta de entrada (FolderController)
  3. Para cada PDF:
       a. Extrai campos da guia     (GnreExtractor)   — Etapas 1 e 2
       b. Mapeia para layout ERP    (ErpMapper)        — Etapa 3
       c. Move arquivo para backup ou erros
  4. Exporta CSV de importação      (ErpExporter)      — Etapa 4
  5. Exibe resumo no terminal

Uso:
    python -m src.main
    python -m src.main --entrada caminho/alternativo
    python -m src.main --saida /caminho/importacao.csv
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

from src.config.config import Config
from src.services.folder.controler import FolderController
from src.services.gnre.extractor import GnreExtractor
from src.services.erp.mapper import ErpMapper
from src.services.erp.exporter import ErpExporter


# ─── Logging ─────────────────────────────────────────────────────────────────

def _setup_logging(config: Config) -> None:
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = config.logs_dir / f"gnre_{datetime.now().strftime('%Y%m%d')}.log"

    fmt     = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    datefmt = "%d/%m/%Y %H:%M:%S"

    logging.basicConfig(
        level=config.log_level,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ─── Resumo no terminal ───────────────────────────────────────────────────────

def _imprimir_resumo(linhas_ok: list[dict], erros: list[str]) -> None:
    sep = "─" * 115
    print(f"\n{sep}")

    if linhas_ok:
        header = (
            f"{'Nº Título':<20} {'Tipo':<8} {'CodFor':<8} "
            f"{'Venc.Orig':<12} {'Venc.Prorrog':<14} "
            f"{'Valor Orig':<12} {'Multa+Juros':<13} Leitor"
        )
        print(header)
        print(sep)
        for r in linhas_ok:
            print(
                f"{r['Nº Título']:<20} "
                f"{r['Tipo']:<8} "
                f"{r['Cod For']:<8} "
                f"{r['Vencimento Original']:<12} "
                f"{r['Vencimento Prorrogado']:<14} "
                f"{r['Valor Original']:<12} "
                f"{r['Valor Multa Negociada']:<13} "
                f"{r['Leitor'][:40]}"
            )
        print(sep)

    total = len(linhas_ok) + len(erros)
    print(
        f"\n  ✅  Processados com sucesso : {len(linhas_ok)}/{total}\n"
        f"  ❌  Com erro                : {len(erros)}/{total}"
    )
    if erros:
        for e in erros:
            print(f"       • {e}")
    print()


# ─── Ponto de entrada ─────────────────────────────────────────────────────────

def main(args: argparse.Namespace | None = None) -> int:
    if args is None:
        parser = argparse.ArgumentParser(
            description="Serviço GNRE → ERP Senior  |  Converte guias PDF em CSV de importação."
        )
        parser.add_argument(
            "--entrada",
            default=None,
            metavar="CAMINHO",
            help="Pasta de entrada alternativa (substitui settings.ini)",
        )
        parser.add_argument(
            "--saida",
            default=None,
            metavar="ARQUIVO.CSV",
            help="Caminho completo do CSV de saída (substitui nome automático)",
        )
        args = parser.parse_args()

    # ── Inicialização ─────────────────────────────────────────────────────────
    cfg      = Config()
    _setup_logging(cfg)
    log      = logging.getLogger(__name__)

    folder   = FolderController(cfg)
    extrator = GnreExtractor()
    mapper   = ErpMapper(cfg)
    exporter = ErpExporter(cfg)

    if args.entrada:
        folder.entrada = Path(args.entrada)

    log.info(f"{'═'*60}")
    log.info(f"  {cfg.system_name}  v{cfg.version}")
    log.info(f"  Entrada         : {folder.entrada}")
    log.info(f"  Data de Entrada : {cfg.data_entrada_padrao}")
    log.info(f"{'═'*60}")

    # ── Listagem de arquivos ──────────────────────────────────────────────────
    pdfs = folder.listar_pdfs()
    if not pdfs:
        log.warning(f"Nenhum PDF encontrado em '{folder.entrada}'.")
        print(f"\n⚠️   Nenhum PDF encontrado em '{folder.entrada}'")
        print("     Coloque as guias GNRE na pasta e execute novamente.\n")
        return 1

    print(f"\n🔍  {len(pdfs)} guia(s) encontrada(s) — iniciando processamento...\n")

    # ── Processamento por arquivo ─────────────────────────────────────────────
    linhas_ok:     list[dict] = []
    arquivos_erro: list[str]  = []

    for pdf in pdfs:
        print(f"  📄  {pdf.name}", end="  ", flush=True)

        # Etapas 1 e 2 — Extração
        campos = extrator.extrair(pdf)

        for aviso in campos.avisos:
            log.warning(f"{pdf.name}: {aviso}")

        if not campos.valido:
            for erro in campos.erros:
                log.error(f"{pdf.name}: {erro}")
            print(f"❌  {len(campos.erros)} erro(s)")
            folder.mover_para_erro(pdf, "\n".join(campos.erros))
            arquivos_erro.append(pdf.name)
            continue

        # Etapa 3 — Mapeamento ERP
        linha_erp = mapper.mapear(campos)
        linhas_ok.append(linha_erp)
        log.info(
            f"{pdf.name}: OK → {linha_erp['Nº Título']}  "
            f"Emissão={linha_erp['Data Emissão']}  "
            f"VencProrrog={linha_erp['Vencimento Prorrogado']}  "
            f"MultaNeg={linha_erp['Valor Multa Negociada']}"
        )
        print(f"✅  → {linha_erp['Nº Título']}")

        folder.mover_para_backup(pdf)

    # ── Etapa 4 — Exportação CSV ──────────────────────────────────────────────
    if linhas_ok:
        caminho_csv = Path(args.saida) if args.saida else folder.caminho_csv_saida()
        exporter.exportar(linhas_ok, caminho_csv)
        print(f"\n✅  CSV gerado: {caminho_csv}")
    else:
        log.error("Nenhuma guia processada com sucesso — CSV não gerado.")

    # ── Limpeza e resumo ──────────────────────────────────────────────────────
    folder.limpar_temp()
    _imprimir_resumo(linhas_ok, arquivos_erro)

    return 0 if linhas_ok else 1


if __name__ == "__main__":
    sys.exit(main())
