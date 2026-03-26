# 📁 Folder Organizer - Sistema Automatizado de Organização de Pastas

Um sistema inteligente e automatizado para organização de arquivos, com fluxo de entrada/saída e backup automático.

![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)
![License](https://img.shields.io/badge/license-MIT-orange)
![Status](https://img.shields.io/badge/status-production%20ready-brightgreen)

## ✨ Funcionalidades

- ✅ **Processamento Automático**: Monitora e processa arquivos da pasta de entrada
- ✅ **Organização por Data**: Estrutura automática com formato configurável (DD-MM-YYYY)
- ✅ **Backup Inteligente**: Backup automático antes do processamento
- ✅ **Classificação por Tipo**: Organiza arquivos em subpastas baseado na extensão
- ✅ **Configuração Flexível**: Arquivos INI e JSON para regras personalizadas
- ✅ **Validação de Arquivos**: Filtro por extensões permitidas e tamanho máximo
- ✅ **Sistema de Logs**: Registro detalhado de todas as operações
- ✅ **Normalização de Nomes**: Renomeia arquivos conforme padrão configurado

## 🚀 Tecnologias Utilizadas

- **Python 3.7+**: Linguagem de programação principal
- **ConfigParser**: Gerenciamento de arquivos INI
- **JSON**: Configurações avançadas e regras de processamento
- **Pathlib**: Manipulação moderna de caminhos de arquivos
- **Logging**: Sistema completo de logs

## 📋 Pré-requisitos

- Python 3.7 ou superior instalado
- pip (gerenciador de pacotes do Python)

## 🔧 Instalação

1. **Clone o repositório**
```bash
git clone https://github.com/VictorPedroza/folder-organizer-py.git
cd folder-organizer-py
```

2. **Crie o Ambiente Virtual (Recomendado)**
```
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

3. **Instale as dependências**
```
pip install -r requirements.txt
```
- Verifique as dependências [AQUI](requirements.txt)

4. **Execute o Projeto**
```
python src/main.py
```

## 📁 Estrutura do Projeto
```
folder-organizer-py/
│
├── src/                          # Código fonte principal
│   ├── config/                    # Configurações do sistema
│   │   └── config.py              # Classe de gerenciamento de config
│   ├── services/                  # Serviços e lógica de negócio
│   │   └── folder/                 
│   │       └── controler.py        # Controlador de pastas
│   └── main.py                     # Arquivo principal de execução
│
├── config/                        # Configurações do usuário (criado automaticamente)
│   ├── settings.ini                # Configurações gerais
│   └── proccess.json               # Regras de processamento
│
├── data/                          # Dados do sistema (criado automaticamente)
│   ├── entrada/                    # Coloque seus arquivos aqui
│   ├── saida/                      # Arquivos processados
│   ├── backup/                     # Backups automáticos
│   └── temp/                       # Arquivos temporários
│
├── logs/                          # Logs do sistema (criado automaticamente)
│
├── .gitignore                     # Arquivos ignorados pelo Git
├── LICENSE                        # Licença do projeto
├── README.md                      # Documentação
└── requirements.txt               # Dependências do projeto
```

## 🎯 Como Usar
### Configuração Inicial
1. Execute o programa uma vez para criar as pastas e arquivos de configuração padrão:
```
python src/main.py
```

2. Personalize as configurações editando os arquivos em `config/`:
### settings.ini
```
[DEFAULT]
pasta_base = ./data
formato_data = DD-MM-YYYY
processar_inicio = true

[PASTAS]
entrada = entrada
saida = saida
backup = backup
temp = temp

[LOGS]
nivel_log = INFO
salvar_log = true
pasta_logs = ./logs
```

### proccess.json
```
{
    "processamento": {
        "extensoes_permitidas": [".txt", ".pdf", ".jpg", ".png", ".csv"],
        "tamanho_maximo_mb": 100,
        "criar_subpastas_por_tipo": true
    },
    "backup": {
        "antes_processar": true,
        "dias_manter": 30
    }
}
```

## 📝 Utilização
Coloque os arquivos na pasta `data/entrada/`

Execute o programa:
```
python src/main.py

```
Arquivos serão automaticamente:

* 📦 Backups criados em data/backup/DD-MM-YYYY/
* 📂 Classificados por tipo (imagens, documentos, etc.)
* 📤 Movidos para data/saida/DD-MM-YYYY/
* 📝 Logs gerados em logs/


## ⚙️ Tipos de Personalização
1. Pastas
    * Nomes das pastas (entrada, saída, backup, temp)
    * Localização dos dados
    * Estrutura de diretórios

2. Data
    * Formato da data (DD-MM-YYYY, YYYY-MM-DD, etc.)
    * Separação por data nos diretórios

3. Arquivos*
    * Extensões permitidas
    * Tamanho máximo
    * Organização por tipo

4. Backup
    * Backup antes do processamento
    * Dias para manter backups
    * Compactação

5. Nomes
    * Padrão de nomenclatura
    * Remoção de espaços
    * Tamanho máximo do nome

6. Logs
    * Nível de detalhamento
    * Salvar em arquivo
    * Pasta de logs

7. Mapeamento
    * Extensão → Pasta destino
    * Regras de organização

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENCE](LICENSE) para mais detalhes.
