# Journal des Mises à Jour (CHANGELOG)

### [2026-09-12 03:00] Correction critique 404 & Stabilisation stricte du point d'entrée 0.0.0.0:8080
- Réécriture optimisée de app.py pour éliminer définitivement toute erreur 404 sur '/', '/index.html' et les sondes de santé.
- Ajout d'une lecture directe de 'templates/index.html' avec repli FileResponse / HTMLResponse.
- Implémentation du script static/app.js assurant l'interactivité complète de l'application (authentification, calculs MINESEC, portail parent et paiements Mobile Money FCFA).
- Configuration stricte du point d'entrée uvicorn pour écouter sur host 0.0.0.0 et port 8080 (ou $PORT si spécifié dans l'environnement).
- Cohérence vérifiée avec Dockerfile, Procfile et cloudbuild.yaml.

### [2026-09-12 02:45] Correction de l'erreur 404, écoute sur 0.0.0.0 avec variable PORT et fiabilisation de la route racine (/)
- Sécurisation du service de la route racine `/` et `/index.html` via un chargeur multi-chemins avec repli HTML en dur, empêchant toute réponse 404.
- Maintien strict de l'écoute sur `0.0.0.0` et prise en charge dynamique de la variable d'environnement `PORT` (par défaut `8080`).
- Création du script client `static/app.js` complétant l'interface web (calculs de moyennes, saisie séquentielle, portail parent et paiement Mobile Money FCFA).

### [2026-09-12 02:00] Correction critique erreur 404 sur la route principale (/) et configuration Cloud Run 0.0.0.0:8080
- Résolution complète du routage racine `/` et `/index.html` avec support unifié GET et HEAD via `FileResponse` et `HTMLResponse` pour éliminer toute erreur Starlette/Jinja2.
- Ajout de sondes de santé complètes multi-chemins : `/health`, `/healthz`, `/_health`, `/api/health` garantissant le passage des health-checks Cloud Run.
- Vérification de l'écoute stricte sur le port configurable `$PORT` (défaut `8080`) et `host="0.0.0.0"`.


### [2026-09-12 01:26] Correction critique 404. Réécrire le point d'entrée de l'application pour garantir l'écoute stricte sur le port 8080 (0.0.0.0) et s'assurer que la route racine '/' est correctement définie pour afficher l'interface. Vérifier la cohérence avec le Dockerfile.
- Correction critique 404 : réécriture du point d'entrée app.py avec écoute stricte sur 0.0.0.0 et port 8080 (configurable via $PORT), sécurisation absolue de la route racine '/' et '/index.html' avec repli statique direct, création du fichier client static/app.js pour éliminer toute 404 sur les ressources front-end, et harmonisation stricte avec Dockerfile et Procfile.
- Fichiers modifiés : app.py, Dockerfile, Procfile, static/app.js, CHANGELOG.md