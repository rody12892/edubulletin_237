# EDUBULLETIN 237 🇨🇲

**EDUBULLETIN 237** est une plateforme SaaS multi-tenant conçue spécifiquement pour le système éducatif camerounais. Elle permet l'automatisation de la production des bulletins scolaires, le calcul sans erreur des 6 séquences, et intègre un portail parent public avec paiement des frais de scolarité via Mobile Money (FCFA).

## 🚀 Lancement Rapide (En 1 clic)

Assurez-vous d'avoir Python 3.9+ installé, puis exécutez la commande suivante à la racine du projet :

```bash
pip install -r requirements.txt && uvicorn app:app --reload
```

L'application sera immédiatement accessible sur : **http://127.0.0.1:8000**

## ⚙️ Fonctionnalités Clés

* **Architecture Multi-Tenant** : Séparation stricte des données par établissement (`ecole_id`).
* **Gestion des 6 Séquences** : Saisie des notes, calcul automatique des moyennes, coefficients et rangs.
* **Portail Parent** : Accès public sécurisé pour la consultation des bulletins.
* **Passerelle de Paiement** : Intégration modulaire Mobile Money (MTN, Orange) en FCFA.

## 💳 Configuration des Paiements (Mobile Money FCFA)

Le système utilise une passerelle modulaire (`payment_gateway.py`) compatible avec les agrégateurs locaux comme **CinetPay** et **Campay**. 

Pour activer les paiements, vous devez configurer vos clés API. Créez un fichier `.env` à la racine du projet ou exportez ces variables d'environnement dans votre système :

### Option 1 : Configuration CinetPay (Recommandé)
1. Créez un marchand sur [CinetPay](https://cinetpay.com/).
2. Récupérez votre `API_KEY` et votre `SITE_ID` dans le back-office.
3. Ajoutez les variables suivantes :

```env
PAYMENT_PROVIDER=cinetpay
CINETPAY_API_KEY=votre_cle_api_cinetpay_ici
CINETPAY_SITE_ID=votre_site_id_ici
CINETPAY_NOTIFY_URL=https://votre-domaine.com/api/payments/notify
```

### Option 2 : Configuration Campay
1. Créez un compte développeur sur [Campay](https://www.campay.net/).
2. Générez vos clés d'application.
3. Ajoutez les variables suivantes :

```env
PAYMENT_PROVIDER=campay
CAMPAY_APP_KEY=votre_app_key_campay_ici
CAMPAY_APP_SECRET=votre_app_secret_campay_ici
CAMPAY_ENVIRONMENT=PRODUCTION
```

*Note : Le fichier `payment_gateway.py` détecte automatiquement le fournisseur configuré via la variable `PAYMENT_PROVIDER` et initialise les transactions Mobile Money en conséquence.*

## 📂 Structure du Projet

* `app.py` : Point d'entrée de l'application FastAPI, définition des routes et logique métier.
* `database.py` : Configuration SQLite optimisée en mode WAL et modèles de données.
* `payment_gateway.py` : Module de gestion des transactions Mobile Money (CinetPay/Campay).
* `templates/index.html` : Interface utilisateur moderne (HTML5 + Tailwind CSS).
* `static/app.js` : Logique front-end, requêtes asynchrones et interactivité.
* `requirements.txt` : Dépendances du projet (FastAPI, Uvicorn, SQLAlchemy, etc.).
* `README.md` : Documentation du projet.

## 🛡️ Sécurité et Bonnes Pratiques

* La base de données SQLite est configurée en mode WAL (Write-Ahead Logging) dans `database.py` pour garantir des performances optimales et la concurrence des lectures/écritures.
* Ne commitez jamais vos clés API en clair dans le code source. Utilisez toujours des variables d'environnement pour la production.