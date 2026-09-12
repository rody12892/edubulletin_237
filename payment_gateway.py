import os
import uuid
import json
import logging
import hmac
import hashlib
import requests
from datetime import datetime
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PaymentGateway")

VALID_CURRENCY = "XAF"
SUBSCRIPTION_PLANS = {
    "BASIC": 75000.0,
    "PRO": 150000.0,
    "ENTERPRISE": 350000.0
}

class PaymentError(Exception):
    pass

class BaseGateway:
    def initialize_payment(self, amount: float, currency: str, customer_email: str, customer_phone: str = "", redirect_url: str = "", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        raise NotImplementedError

    def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

class DemoGateway(BaseGateway):
    def __init__(self):
        logger.info("Initialisation de la passerelle en mode DEMO_SANDBOX")
        self.transactions = {}

    def initialize_payment(self, amount: float, currency: str, customer_email: str, customer_phone: str = "", redirect_url: str = "", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        reference = f"DEMO-{uuid.uuid4().hex[:12].upper()}"
        self.transactions[reference] = {
            "amount": amount,
            "currency": currency,
            "status": "SUCCESSFUL",
            "phone": customer_phone,
            "metadata": metadata or {}
        }
        
        demo_url = f"{redirect_url}?reference={reference}&status=success" if redirect_url else f"https://pay.edubulletin237.cm/demo/{reference}"
        
        return {
            "success": True,
            "status": "success",
            "reference": reference,
            "transaction_id": reference,
            "payment_url": demo_url,
            "message": "Paiement Mobile Money simulé avec succès (Mode Démo 237)."
        }

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        if reference.startswith("DEMO-") or reference in self.transactions:
            tx = self.transactions.get(reference, {})
            return {
                "success": True,
                "status": "SUCCESS",
                "reference": reference,
                "amount": tx.get("amount", 50000.0),
                "currency": VALID_CURRENCY,
                "provider_status": "successful"
            }
        return {"success": False, "status": "FAILED", "message": "Référence introuvable."}

    def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "success", "reference": payload.get("reference", "")}

class CinetPayGateway(BaseGateway):
    def __init__(self, api_key: str, site_id: str):
        self.api_key = api_key
        self.site_id = site_id
        self.base_url = "https://api-checkout.cinetpay.com/v2/payment"

    def initialize_payment(self, amount: float, currency: str, customer_email: str, customer_phone: str = "", redirect_url: str = "", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        reference = f"CP-{uuid.uuid4().hex[:12].upper()}"
        payload = {
            "apikey": self.api_key,
            "site_id": self.site_id,
            "transaction_id": reference,
            "amount": int(amount),
            "currency": currency,
            "description": "Paiement Scolarite / Abonnement EDUBULLETIN 237",
            "customer_name": "Client",
            "customer_surname": "237",
            "customer_email": customer_email or "client@edubulletin.cm",
            "customer_phone_number": customer_phone,
            "return_url": redirect_url,
            "channels": "MOBILE_MONEY"
        }
        try:
            response = requests.post(self.base_url, json=payload, timeout=15)
            data = response.json()
            if data.get("code") == "201":
                return {
                    "success": True,
                    "status": "success",
                    "reference": reference,
                    "transaction_id": reference,
                    "payment_url": data["data"]["payment_url"],
                    "message": "Redirection vers le portail Mobile Money."
                }
            return {"success": False, "message": data.get("description", "Erreur CinetPay")}
        except Exception as e:
            logger.error(f"Erreur CinetPay: {e}")
            return {"success": False, "message": "Impossible de joindre le service de paiement."}

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        url = "https://api-checkout.cinetpay.com/v2/payment/check"
        payload = {"apikey": self.api_key, "site_id": self.site_id, "transaction_id": reference}
        try:
            res = requests.post(url, json=payload, timeout=15).json()
            if res.get("code") == "00":
                return {"success": True, "status": "SUCCESS", "reference": reference, "amount": float(res["data"]["amount"])}
            return {"success": False, "status": "FAILED"}
        except Exception:
            return {"success": False, "status": "FAILED"}

class PaymentGateway:
    def __init__(self):
        self.provider_name = os.getenv("PAYMENT_PROVIDER", "DEMO").upper()
        self.provider = self._init_provider()

    def _init_provider(self) -> BaseGateway:
        if self.provider_name == "CINETPAY":
            api_key = os.getenv("CINETPAY_API_KEY")
            site_id = os.getenv("CINETPAY_SITE_ID")
            if api_key and site_id:
                return CinetPayGateway(api_key, site_id)
        return DemoGateway()

    def initiate(self, amount: float, phone: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.provider.initialize_payment(
            amount=amount,
            currency=VALID_CURRENCY,
            customer_email=f"{name.lower().replace(' ', '')}@edubulletin.cm",
            customer_phone=phone,
            metadata=metadata
        )

    def verify(self, reference: str) -> Dict[str, Any]:
        return self.provider.verify_payment(reference)

# Instance singleton
global_gateway = PaymentGateway()

def initiate_mobile_money_payment(amount: float, phone_number: str = "", payer_name: str = "Client", metadata: Optional[Dict[str, Any]] = None, phone: str = "", name: str = "") -> Dict[str, Any]:
    final_phone = phone or phone_number
    final_name = name or payer_name
    return global_gateway.initiate(amount=amount, phone=final_phone, name=final_name, metadata=metadata)

def verify_mobile_money_payment(reference: str) -> Dict[str, Any]:
    return global_gateway.verify(reference)
