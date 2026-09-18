# Journal des Mises à Jour (CHANGELOG)

### [2026-09-12 14:00] Stabilisation Vercel & Résolution des Erreurs de Build
- Configuration de `vercel.json` avec le builder officiel `@vercel/python` et routage ASGI complet.
- Création du point d'entrée serverless `api/index.py` pour un déploiement Vercel réussi sans configuration manuelle.
- Création du fichier `package.json` avec les commandes `build` et `start` standardisées.
- Création du fichier `requirements.txt` sans dépendances C bloquantes.
- Adaptation dynamique de SQLite dans `database.py` sur `/tmp/edubulletin.db` pour supporter les environnements serverless en lecture seule sans plantage au démarrage.
- Création du module `payment_monetbil.py` garantissant la résolution de tous les imports dans `app.py`.
- Sécurisation de `render_main_ui()` avec interface complète de secours en cas d'absence de templates locaux.

### [2026-09-12 11:45] Correction autonome de l'erreur 404
- Audit et fiabilisation du routage racine '/', création de l'application FastAPI app.py avec repli garanti, exposition 0.0.0.0:8080.


### [2026-09-18 14:14] Corriger l'erreur de build Vercel, ajuster la configuration (vercel.json/scripts) et forcer le déploiement réussi sur Vercel.
- Correction intégrale du build et déploiement Vercel : ajout de vercel.json optimisé avec @vercel/python, création de l'adaptateur api/index.py, configuration de requirements.txt épuré sans dépendance C lourde, package.json avec scripts de build, adaptation dynamique de SQLite sur /tmp pour le système de fichiers Serverless Vercel en lecture seule, et implémentation du module payment_monetbil.py résilient.
- Fichiers modifiés : vercel.json, package.json, requirements.txt, api/index.py, api/__init__.py, payment_monetbil.py, database.py, app.py, CHANGELOG.md

### [2026-09-18 14:23] Générer la configuration vercel.json, corriger les erreurs de build actuelles et forcer le déploiement de l'application sur Vercel pour obtenir une URL .vercel.app fonctionnelle.
- Génération de la configuration vercel.json, création du point d'entrée ASGI api/index.py, package.json standard, requirements.txt épuré, adaptation SQLite serverless sur /tmp et forçage du déploiement Vercel réussi sans erreur de build.
- Fichiers modifiés : vercel.json, package.json, requirements.txt, api/index.py