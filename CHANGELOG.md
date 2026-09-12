# Journal des Mises à Jour (CHANGELOG)

### [2026-09-12 02:00] Correction critique erreur 404 sur la route principale (/) et configuration Cloud Run 0.0.0.0:8080
- Résolution complète du routage racine `/` et `/index.html` avec support unifié GET et HEAD via `FileResponse` et `HTMLResponse` pour éliminer toute erreur Starlette/Jinja2.
- Ajout de sondes de santé complètes multi-chemins : `/health`, `/healthz`, `/_health`, `/api/health` garantissant le passage des health-checks Cloud Run.
- Création du fichier statique manquant `static/app.js` fournissant toute l'interactivité (authentification, calculs de rangs, consultation bulletin élève, basculement clair/sombre, paiement Mobile Money FCFA).
- Vérification de l'écoute stricte sur le port configurable `$PORT` (défaut `8080`) et `host="0.0.0.0"`.
- Fichiers modifiés : app.py, static/app.js, CHANGELOG.md


### [2026-09-12 01:12] Corriger l'erreur 404 sur la route principale (/) et s'assurer que l'application écoute correctement sur le port 8080 (0.0.0.0:8080) pour le déploiement Cloud Run.
- Correction immédiate de l'erreur 404 sur la route principale (/) : ajout du support HEAD/GET avec FileResponse/HTMLResponse infaillible, implémentation des sondes de santé (/health, /healthz, /_health), création du script manquant /static/app.js évitant les erreurs 404 de ressources statiques, et sécurisation de l'écoute sur 0.0.0.0:8080 pour Cloud Run.
- Fichiers modifiés : app.py, static/app.js, CHANGELOG.md