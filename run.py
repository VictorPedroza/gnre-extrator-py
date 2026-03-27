#!/usr/bin/env python
"""
run.py
======
Ponto de entrada principal do serviço GNRE → ERP Senior.
Este arquivo é usado como entry point pelo PyInstaller.
"""

import sys
from src.main import main

if __name__ == "__main__":
    sys.exit(main())