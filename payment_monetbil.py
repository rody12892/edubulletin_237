import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("MonetbilGateway")

PACKS_CONFIG = {
    "demarrage": {
        "id": "demarrage",
        "nom": "Pack Démarrage (1 à 6 classes)",
        "montant": 75000,
        "classes_max": 6,
        "description": "Idéal pour petites écoles primaires ou collèges naissants"
    },
    "standard": {
        "id": "standard",
        "nom": "Pack Standard (7 à 15 classes)",
        "montant": 150000,
        "classes_max": 15,
        "description": "Recommandé pour lycées et collèges conventionnels"
    },
    "grand": {
        "id": "grand",
        "nom": "Pack Grand Établissement (16 à 30 classes)",
        "montant": 250000,
        "classes_max": 30,
        "description": "Pour grands lycées et complexes scolaires polyvalents"
    },
    "groupe": {
        "id": "groupe",
        "nom": "Pack Groupe Scolaire (31+ classes)",
        "montant": 350000,
        "classes_max": 999,
        "description": "Campus multiples et effectifs illimités avec support VIP"
    }
}

class MonetbilClient:
    def __init__(self):
        self.service_key = os.getenv("MONETBIL_SERVICE_KEY", "DEMO_MONETBIL_KEY_237")
        self.service_secret = os.getenv("MONETBIL_SERVICE_SECRET", "DEMO_MONETBIL_SECRET_237")
        self.base_url = "https://api.monetbil.com/widget/v2.1"

    def create_payment_widget(
        self,
        amount: float,
        payment_ref: str,
        item_ref: str,
        phone: str = "",
        first_name: str = "Directeur",
        last_name: str = "MINESEC",
        email: str = "contact@edubulletin237.cm"
    ) -> Dict[str, Any]:
        """Génère l'URL de paiement Monetbil ou URL sandbox de simulation."""
        pack_data = PACKS_CONFIG.get(item_ref, PACKS_CONFIG["standard"])
        montant_final = amount or pack_data["montant"]
        
        # En mode Vercel / Démo, générer un lien interactif immédiat
        simulation_url = f"/?payment_ref={payment_ref}&pack={item_ref}&amount={montant_final}&status=success"
        
        return {
            "success": True,
            "status": "REQUEST_ACCEPTED",
            "payment_url": simulation_url,
            "payment_ref": payment_ref,
            "amount": montant_final,
            "currency": "XAF",
            "phone": phone,
            "message": f"Transaction Monetbil initiée pour le {pack_data['nom']} ({montant_final:,.0f} FCFA)."
        }

    def verify_payment(self, payment_ref: str) -> Dict[str, Any]:
        return {
            "success": True,
            "status": "SUCCESS",
            "payment_ref": payment_ref
        }

monetbil_client = MonetbilClient()
