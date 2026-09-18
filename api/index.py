import sys
import os
from pathlib import Path

# Ajout de la racine au PYTHONPATH pour importer app et database
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from app import app

# Point d'entrée WSGI / ASGI pour Vercel (@vercel/python)
# FastAPI s'exécute directement via l'instance app
