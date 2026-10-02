"""Lanzador para Python portatil (embeddable): anade la carpeta padre a sys.path.

Uso:  python.exe C:\\ruta\\pt601_mcp\\run.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pt601_mcp.app import main  # noqa: E402

sys.exit(main())
