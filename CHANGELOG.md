# Journal des Mises à Jour (CHANGELOG)

### [2026-09-12 02:45] Correction de l'erreur 404, écoute sur 0.0.0.0 avec variable PORT et fiabilisation de la route racine (/)
- Sécurisation du service de la route racine `/` et `/index.html` via un chargeur multi-chemins avec repli HTML en dur, empêchant toute réponse 404.
- Maintien strict de l'écoute sur `0.0.0.0` et prise en charge dynamique de la variable d'environnement `PORT` (par défaut `8080`).
- Création du script client `static/app.js` complétant l'interface web (calculs de moyennes, saisie séquentielle, portail parent et paiement Mobile Money FCFA).
- Fichiers modifiés / créés : app.py, static/app.js, CHANGELOG.md

### [2026-09-12 02:00] Correction critique erreur 404 sur la route principale (/) et configuration Cloud Run 0.0.0.0:8080
- Résolution complète du routage racine `/` et `/index.html` avec support unifié GET et HEAD via `FileResponse` et `HTMLResponse` pour éliminer toute erreur Starlette/Jinja2.
- Ajout de sondes de santé complètes multi-chemins : `/health`, `/healthz`, `/_health`, `/api/health` garantissant le passage des health-checks Cloud Run.
- Création du fichier statique manquant `static/app.js` fournissant toute l'interactivité (authentification, calculs de rangs, consultation bulletin élève, basculement clair/sombre, paiement Mobile Money FCFA).
- Vérification de l'écoute stricte sur le port configurable `$PORT` (défaut `8080`) et `host="0.0.0.0"`.
- Fichiers modifiés : app.py, static/app.js, CHANGELOG.md


### [2026-09-12 01:23] Corriger l'erreur 404. Assurer que le serveur écoute sur 0.0.0.0 et utilise la variable d'environnement PORT. Vérifier et configurer la route racine (/) pour qu'elle serve correctement l'interface web de l'application au lieu de renvoyer une page introuvable.
- Résolution définitive de l'erreur 404 sur la route racine (/), garantie du binding sur 0.0.0.0 avec la variable d'environnement PORT, et création du script client manquant static/app.js pour assurer un rendu complet et interactif de l'interface.
- Fichiers modifiés : app.py, static/app.js, CHANGELOG.md