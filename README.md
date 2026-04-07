# GNRE → ERP Senior  |  Serviço de Importação

Converte guias GNRE em PDF para o formato CSV de importação em lote do ERP Senior.

---

## Estrutura do Projeto

```
├── src/
│   ├── config/
│   │   └── config.py              # Gerenciador central de configurações
│   ├── services/
│   │   ├── folder/
│   │   │   └── controller.py      # Movimentação de arquivos (entrada/backup/erro)
│   │   ├── gnre/
│   │   │   └── extractor.py       # Extração de campos do PDF (Etapas 1 e 2)
│   │   └── erp/
│   │       ├── mapper.py          # De-Para e montagem do layout Senior (Etapa 3)
│   │       └── exporter.py        # Geração do CSV (Etapa 4)
│   └── main.py                    # Orquestrador principal (Etapa 5)
│
├── config/
│   ├── settings.ini               # Configurações gerais do serviço
│   └── process.json               # De-Para: UF→CodFor, CodReceita→Tipo, layout CSV
│
├── data/
│   ├── entrada/                   ← Coloque as GNREs em PDF aqui
│   ├── saida/                     ← CSV de importação gerado aqui
│   │   └── erros/                 ← PDFs com problema ficam aqui
│   ├── backup/                    ← PDFs processados com sucesso
│   └── temp/                      ← Uso interno (limpo ao final)
│
└── logs/
    └── gnre_AAAAMMDD.log          ← Log diário de execução
```

---

## Instalação

```bash
pip install -r requirements.txt
```

---

## Uso

```bash
# Execução padrão (lê data de hoje como Data Emissão)
python -m src.main

# Informar data de emissão manualmente
python -m src.main --data-emissao 27/03/2026

# Pasta de entrada alternativa
python -m src.main --entrada /outro/caminho

# Arquivo CSV de saída específico
python -m src.main --saida /caminho/importacao.csv
```

---

## Fluxo de Processamento

```
data/entrada/*.pdf
       │
       ▼
[1] Validação dos campos da guia
       │
       ▼
[2] Extração dos dados (GnreExtractor)
    ├─ Lê apenas a 1ª via do PDF
    ├─ Mapeia campos por linha (layout GNRE padrão)
    └─ Fallback: Nº Doc via chave NF-e quando campo está vazio
       │
       ▼
[3] De-Para ERP (ErpMapper)
    ├─ UF Favorecida → Cód. Fornecedor SEFAZ
    └─ Código Receita → Tipo do Título
       │
       ▼
[4] Geração do CSV (ErpExporter)  →  data/saida/importacao_senior_AAAAMMDD_HHMMSS.csv
       │
       ▼
[5] Movimentação
    ├─ Sucesso → data/backup/AAAA-MM-DD/
    └─ Erro    → data/saida/erros/AAAA-MM-DD/  +  arquivo .log.txt com motivo
```

---

## Layout CSV — ERP Senior

| Coluna                | Origem                              |
|-----------------------|-------------------------------------|
| Nº Título             | `<nDocOrigem>-GNRE-<UF>`            |
| Tipo                  | De-Para `process.json` → `tipo_erp` |
| Cod For               | De-Para `process.json` → `sefaz_cod_for` |
| Transação             | `settings.ini` → `[erp] transacao`  |
| Situação              | `settings.ini` → `[erp] situacao`   |
| Natureza              | `settings.ini` → `[erp] natureza`   |
| Data Emissão          | Argumento `--data-emissao` ou hoje  |
| Data de Entrada       | Idem                                |
| Vencimento Original   | Campo da guia                       |
| Valor Original        | Total a Recolher                    |
| Vencimento Prorrogado | Idem Vencimento Original            |
| Forma de Pagamento    | `settings.ini` → `[erp] forma_pagamento` |
| Valor Multa Negociada | Multa da guia                       |
| Leitor                | Linha digitável / código de barras  |

---

## Configuração

### `config/settings.ini`
Ajuste paths, comportamento de backup, encoding do CSV e valores fixos do ERP.

### `config/process.json`
Edite os De-Para sem tocar no código:
- `sefaz_cod_for` — adicione UFs novas ou corrija códigos
- `tipo_erp` — adicione novos Códigos de Receita
- `layout_csv` — reordene ou adicione colunas

---

## Ponto de Atenção — Nº Documento Ausente

Algumas guias não possuem o campo **Nº Documento de Origem** preenchido.
Nesse caso, o serviço extrai automaticamente o `nNF` da **chave de acesso NF-e**
(posições 26–34 da chave de 44 dígitos) e registra um aviso no log.

Se a chave também não estiver disponível, o **Nº de Controle** da guia é usado
como base do Nº Título, com aviso no log.
