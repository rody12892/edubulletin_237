import os
import sys
from pathlib import Path

# Ajout du répertoire racine au sys.path pour les imports dans l'environnement Vercel Serverless
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import app
