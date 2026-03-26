import os
import shutil
import logging
from datetime import datetime
from pathlib import Path

from config.config import Config

class FolderController:
    """Controlador de Pastas e Arquivos"""
    
    def __init__(self, root_folder):
        """
        Inicializa o controlador de pastas
        
        Args:
            root_folder: Pasta raiz do projeto
        """
        self.config = Config(root_folder)
        self.root_folder = str(root_folder) if isinstance(root_folder, Path) else root_folder
        self.pasta_base = self.config.get_pasta_base()
        self.data_atual = self.config.get_data_atual()
        
        # Configura logger
        self.logger = self._configurar_logger()
        
        # Cache de caminhos
        self._caminhos = {}
        
        # Cria estrutura base
        self._criar_estrutura_base()
        self.logger.info(f"📁 Controller inicializado - Data: {self.data_atual}")
    
    def _configurar_logger(self):
        """Configura o sistema de logs"""
        logger = logging.getLogger('FolderController')
        
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            
            # Handler para console
            console = logging.StreamHandler()
            console.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(console)
        
        return logger
    
    def _criar_estrutura_base(self):
        """Cria a estrutura base de pastas"""
        for pasta in ['entrada', 'saida', 'backup', 'temp']:
            nome = self.config.get_nome_pasta(pasta)
            caminho = os.path.join(self.pasta_base, nome)
            os.makedirs(caminho, exist_ok=True)
            self._caminhos[pasta] = caminho
    
    def _obter_caminho_com_data(self, tipo):
        """
        Obtém caminho com subpasta de data
        
        Args:
            tipo: 'saida' ou 'backup'
        """
        pasta_base = self._caminhos.get(tipo)
        if not pasta_base:
            pasta_base = os.path.join(self.pasta_base, tipo)
        
        caminho_com_data = os.path.join(pasta_base, self.data_atual)
        os.makedirs(caminho_com_data, exist_ok=True)
        
        return caminho_com_data
    
    def _normalizar_nome(self, nome):
        """
        Normaliza nome do arquivo conforme configurações
        
        Args:
            nome: Nome original do arquivo
        """
        nome_path = Path(nome)
        nome_arquivo = nome_path.stem
        extensao = nome_path.suffix
        
        # Remove caracteres inválidos
        caracteres_invalidos = '<>:"/\\|?*'
        for char in caracteres_invalidos:
            nome_arquivo = nome_arquivo.replace(char, '_')
        
        return f"{self.data_atual}_{nome_arquivo}{extensao}"
    
    def _obter_pasta_destino(self, arquivo):
        """
        Determina a pasta de destino baseado no tipo do arquivo
        
        Args:
            arquivo: Caminho do arquivo
        """
        extensao = Path(arquivo).suffix.lower()
        
        # Verifica mapeamento
        pasta_sub = self.config.get_pasta_por_extensao(extensao)
        
        pasta_saida = self._obter_caminho_com_data('saida')
        
        if pasta_sub:
            destino = os.path.join(pasta_saida, pasta_sub)
        else:
            destino = pasta_saida
        
        os.makedirs(destino, exist_ok=True)
        return destino
    
    # ========== FUNÇÕES PÚBLICAS ==========
    
    def listar_arquivos(self, pasta='entrada'):
        """
        Lista arquivos em uma pasta
        
        Args:
            pasta: Nome da pasta (entrada, saida, backup, temp)
        """
        caminho_pasta = self._caminhos.get(pasta)
        if not caminho_pasta or not os.path.exists(caminho_pasta):
            return []
        
        arquivos = []
        for root, dirs, files in os.walk(caminho_pasta):
            for file in files:
                arquivos.append(os.path.join(root, file))
        
        return arquivos
    
    def processar_entrada(self):
        """
        Processa todos os arquivos da pasta de entrada
        
        Returns:
            Dicionário com estatísticas
        """
        stats = {
            'processados': 0,
            'erros': 0,
            'backups': 0,
            'ignorados': 0
        }
        
        # Lista arquivos da entrada
        arquivos = self.listar_arquivos('entrada')
        
        if not arquivos:
            self.logger.info("📂 Pasta de entrada vazia")
            return stats
        
        self.logger.info(f"🔄 Processando {len(arquivos)} arquivos...")
        
        for arquivo in arquivos:
            try:
                # Verifica extensão permitida
                extensao = Path(arquivo).suffix.lower()
                extensoes = self.config.get_extensoes_permitidas()
                
                if extensoes and extensao not in extensoes:
                    self.logger.warning(f"⏭️ Extensão não permitida: {Path(arquivo).name}")
                    stats['ignorados'] += 1
                    continue
                
                # Gera backup antes (se configurado)
                if self.config.deve_fazer_backup_antes():
                    self._gerar_backup(arquivo)
                    stats['backups'] += 1
                
                # Determina pasta destino
                pasta_destino = self._obter_pasta_destino(arquivo)
                
                # Move o arquivo
                destino = self._mover_arquivo(arquivo, pasta_destino)
                
                if destino:
                    stats['processados'] += 1
                
            except Exception as e:
                self.logger.error(f"❌ Erro processando {Path(arquivo).name}: {e}")
                stats['erros'] += 1
        
        self.logger.info(f"✅ Processamento concluído: {stats['processados']} arquivos")
        return stats
    
    def _mover_arquivo(self, origem, pasta_destino):
        """Move um arquivo para a pasta de destino"""
        try:
            origem = Path(origem)
            nome_normalizado = self._normalizar_nome(origem.name)
            destino = os.path.join(pasta_destino, nome_normalizado)
            
            shutil.move(str(origem), destino)
            self.logger.info(f"✅ Movido: {origem.name} → {os.path.basename(pasta_destino)}")
            
            return destino
        except Exception as e:
            self.logger.error(f"❌ Erro ao mover: {e}")
            return None
    
    def _gerar_backup(self, origem):
        """Gera backup de um arquivo"""
        try:
            origem = Path(origem)
            pasta_backup = self._obter_caminho_com_data('backup')
            
            timestamp = datetime.now().strftime("%H%M%S")
            nome_backup = f"{origem.stem}_backup_{self.data_atual}_{timestamp}{origem.suffix}"
            destino = os.path.join(pasta_backup, nome_backup)
            
            shutil.copy2(origem, destino)
            self.logger.info(f"🔄 Backup: {origem.name}")
            
            return destino
        except Exception as e:
            self.logger.error(f"❌ Erro no backup: {e}")
            return None