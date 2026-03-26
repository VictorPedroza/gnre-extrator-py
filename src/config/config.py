import os
import configparser
import json
from datetime import datetime
from pathlib import Path

class Config:
    """Configuração de Pastas"""
    
    def __init__(self, root_folder):
        self.root_folder = str(root_folder) if isinstance(root_folder, Path) else root_folder
        # Config folder agora é na raiz mesmo, fora do src
        self.config_folder = os.path.join(self.root_folder, 'config')

        self.settings_ini = os.path.join(self.config_folder, "settings.ini")
        self.default_rules = os.path.join(self.config_folder, "proccess.json")

        self._settings = None
        self._proccess = None

        self._ensure_config_folder()
        print(f"⚙️  Configuração carregada de: {self.config_folder}")

    def _ensure_config_folder(self):
        """Garante que a pasta de configuração existe"""
        if not os.path.exists(self.config_folder):
            os.makedirs(self.config_folder)
            print(f"📁 Pasta de configuração criada: {self.config_folder}")

        self._create_default_configs()

    def _create_default_configs(self):
        """Cria arquivos de configuração padrão se não existirem"""
        if not os.path.exists(self.settings_ini):
            config = configparser.ConfigParser()

            config["DEFAULT"] = {
                'pasta_base': os.path.join(self.root_folder, 'data'),
                'formato_data': 'DD-MM-YYYY',
                'processar_inicio': 'true'
            }

            config["PASTAS"] = {
                'entrada': 'entrada',
                'saida': 'saida',
                'backup': 'backup',
                'temp': 'temp'
            }

            config["LOGS"] = {
                'nivel_log': 'INFO',
                'salvar_log': 'true',
                'pasta_logs': os.path.join(self.root_folder, 'logs')
            }

            with open(self.settings_ini, 'w', encoding='utf-8') as file:
                config.write(file)
            print(f"✅ settings.ini criado: {self.settings_ini}")
        
        if not os.path.exists(self.default_rules):
            process_config = {
                "versao": "1.0.0",
                "processamento": {
                    "extensoes_permitidas": [".txt", ".pdf", ".jpg", ".png", ".csv", ".xlsx", ".docx"],
                    "tamanho_maximo_mb": 100,
                    "criar_subpastas_por_tipo": True,
                    "manter_originais": False
                },
                "backup": {
                    "antes_processar": True,
                    "compactar": False,
                    "dias_manter": 30
                },
                "nomenclatura": {
                    "padrao": "{data}_{nome}",
                    "remover_espacos": True,
                    "max_tamanho": 100
                },
                "mapeamento_extensoes": {
                    ".jpg": "imagens",
                    ".jpeg": "imagens",
                    ".png": "imagens",
                    ".gif": "imagens",
                    ".pdf": "documentos/pdf",
                    ".doc": "documentos/word",
                    ".docx": "documentos/word",
                    ".xls": "documentos/excel",
                    ".xlsx": "documentos/excel",
                    ".txt": "documentos/texto",
                    ".csv": "dados",
                    ".mp4": "videos",
                    ".mp3": "audios"
                }
            }

            with open(self.default_rules, 'w', encoding='utf-8') as file:
                json.dump(process_config, file, indent=4, ensure_ascii=False)
            print(f"✅ proccess.json criado: {self.default_rules}")

    def _load_settings(self):
        """Carrega o arquivo 'settings.ini'"""
        if self._settings is None:
            self._settings = configparser.ConfigParser()
            self._settings.read(self.settings_ini, encoding='utf-8')
        return self._settings
    
    def get_ini(self, section, key, default=None):
        """Obtem os valores de 'settings.ini'"""
        try:
            settings = self._load_settings()

            if section in settings and key in settings[section]:
                value = settings[section][key]
            elif "DEFAULT" in settings and key in settings["DEFAULT"]:
                value = settings["DEFAULT"][key]
            else: 
                return default
            
            if isinstance(value, str):
                if value.lower() in ['true', 'false']:
                    return value.lower() == 'true'
                if value.isdigit():
                    return int(value)
                try: 
                    return float(value)
                except:
                    return value
            return value
            
        except Exception:
            return default

    def _load_process_rules(self):
        """Carrega o arquivo 'proccess.json'"""
        if self._proccess is None:
            try:
                with open(self.default_rules, 'r', encoding='utf-8') as file:
                    self._proccess = json.load(file)
            except:
                self._proccess = {}
        return self._proccess

    def get_json(self, *keys, default=None):
        """Obtém valor aninhado do process.json"""
        try:
            data = self._load_process_rules()
            for key in keys:
                data = data[key]
            return data
        except (KeyError, TypeError):
            return default

    def get_pasta_base(self):
        """Retorna a pasta base configurada"""
        return self.get_ini('DEFAULT', 'pasta_base', os.path.join(self.root_folder, 'data'))

    def get_nome_pasta(self, tipo):
        """Retorna o nome configurado para um tipo de pasta"""
        return self.get_ini('PASTAS', tipo, tipo)

    def get_formato_data(self):
        """Retorna o formato de data configurado"""
        return self.get_ini('DEFAULT', 'formato_data', 'DD-MM-YYYY')

    def get_data_atual(self):
        """Retorna a data atual no formato configurado"""
        hoje = datetime.now()
        formato = self.get_formato_data()
        
        mapa_formatos = {
            'DD-MM-YYYY': '%d-%m-%Y',
            'YYYY-MM-DD': '%Y-%m-%d',
            'DD/MM/YYYY': '%d/%m/%Y',
            'YYYY/MM/DD': '%Y/%m/%d',
            'DDMMYYYY': '%d%m%Y',
            'YYYYMMDD': '%Y%m%d'
        }
        
        formato_python = mapa_formatos.get(formato, '%d-%m-%Y')
        return hoje.strftime(formato_python)

    def get_extensoes_permitidas(self):
        """Retorna lista de extensões permitidas"""
        return self.get_json('processamento', 'extensoes_permitidas', default=['.txt', '.pdf'])

    def get_mapeamento_extensoes(self):
        """Retorna mapeamento de extensões para pastas"""
        return self.get_json('mapeamento_extensoes', default={})

    def get_pasta_por_extensao(self, extensao):
        """Retorna a pasta destino para uma extensão"""
        mapeamento = self.get_mapeamento_extensoes()
        return mapeamento.get(extensao.lower())

    def deve_fazer_backup_antes(self):
        """Verifica se deve fazer backup antes de processar"""
        return self.get_json('backup', 'antes_processar', default=True)