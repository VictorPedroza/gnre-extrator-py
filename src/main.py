from pathlib import Path
from config.config import Config
from services.folder.controler import FolderController

def main():
    root = Path(__file__).parent.parent
    print("=" * 60)
    print("📁 Folder Organizer - By Victor Pedroza")
    print("=" * 60)
    print(f"📂 Raiz do projeto: {root}")
    
    # Inicializa configuração
    Config(root)
    
    # Inicializa controller
    controller = FolderController(root)
    
    # Mostra informações
    print(f"\n✅ Sistema inicializado com sucesso!")
    print(f"📅 Data atual: {controller.data_atual}")
    print(f"📁 Pasta entrada: {controller._caminhos['entrada']}")
    print(f"📁 Pasta saída: {controller._caminhos['saida']}/{controller.data_atual}")
    print(f"📁 Pasta backup: {controller._caminhos['backup']}/{controller.data_atual}")

if __name__ == "__main__":
    main()