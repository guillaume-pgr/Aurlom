"""Point d'entrée Vercel : expose l'app FastAPI (ASGI natif, sans Mangum).

Le runtime Python de Vercel (@vercel/python) détecte automatiquement la
variable ``app`` (application ASGI) et la sert directement — aucun adaptateur
n'est nécessaire.

On ajoute la racine du projet au ``sys.path`` afin de pouvoir importer les
modules situés au niveau supérieur (main, config, db, sync, …).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402  (import après ajustement du sys.path)

# ``app`` est exposé au runtime Vercel.
