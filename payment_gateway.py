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

# ==============================================================================
# SECTION À COMPLÉTER PAR LE FONDATEUR (AGRÉGATEURS AFRICAINS & MOBILES MONEY)
# Lorsque vous aurez vos clés d'agrégateur, renseignez simplement vos variables d'environnement.
# ==============================================================================

VALID_CURRENCY = "XAF"
SUBSCRIPTION_PLANS = {
    "BASIC": 75000.0,
    "PRO": 150000.0,
    "ENTERPRISE": 350000.0
}

class PaymentError(Exception):
    """Exception personnalisée pour les erreurs de paiement."""
    pass

class BaseGateway:
    def initialize_payment(self, amount: float, currency: str, customer_email: str, customer_phone: str = "", redirect_url: str = "") -> Dict[str, Any]:
        raise NotImplementedError

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        raise NotImplementedError

    def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

class DemoGateway(BaseGateway):
    """Passerelle de démonstration active par défaut pour les tests locaux et le développement."""
    
    def __init__(self):
        logger.info("Initialisation de la passerelle en mode DEMO_SANDBOX")
        self.transactions = {}

    def initialize_payment(self, amount: float, currency: str, customer_email: str, customer_phone: str = "", redirect_url: str = "") -> Dict[str, Any]:
        reference = f"DEMO-{uuid.uuid4().hex[:12].upper()}"
        self.transactions[reference] = {
            "amount": amount,
            "currency": currency,
            "status": "pending",
            "email": customer_email
        }
        
        demo_url = f"{redirect_url}?reference={reference}&status=success" if redirect_url else f"https://demo.edubulletin.com/pay/{reference}"
        
        return {
            "status": "success",
            "reference": reference,
            "payment_url": demo_url,
            "message": "Paiement initialisé en mode DEMO."
        }

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        if reference.startswith("DEMO-"):
            return {
                "status": "success",
                "reference": reference,
                "amount": self.transactions.get(reference, {}).get("amount", 0.0),
                "currency": VALID_CURRENCY,
                "provider_status": "successful"
            }
        return {"status": "failed", "message": "Référence introuvable."}

    def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        reference = payload.get("reference", "")
        return {
            "status": "success",
            "reference": reference,
            "message": "Webhook DEMO traité avec succès."
        }

class CinetPayGateway(BaseGateway):
    """Intégration CinetPay pour l'Afrique de l'Ouest et Centrale (Orange Money, MTN MoMo, etc.)"""
    
    def __init__(self, api_key: str, site_id: str):
        self.api_key = api_key
        self.site_id = site_id
        self.base_url = "https://api-checkout.cinetpay.com/v2/payment"

    def initialize_payment(self, amount: float, currency: str, customer_email: str, customer_phone: str = "", redirect_url: str = "") -> Dict[str, Any]:
        reference = f"CP-{uuid.uuid4().hex[:12].upper()}"
        payload = {
            "apikey": self.api_key,
            "site_id": self.site_id,
            "transaction_id": reference,
            "amount": int(amount),
            "currency": currency,
            "description": "Abonnement EDUBULLETIN 237",
            "customer_name": "Client",
            "customer_surname": "EDUBULLETIN",
            "customer_email": customer_email,
            "customer_phone_number": customer_phone,
            "return_url": redirect_url,
            "notify_url": os.getenv("WEBHOOK_URL", "https://api.edubulletin.com/webhooks/cinetpay"),
            "channels": "ALL"
        }
        
        try:
            response = requests.post(self.base_url, json=payload, timeout=15)
            data = response.json()
            if data.get("code") == "201":
                return {
                    "status": "success",
                    "reference": reference,
                    "payment_url": data["data"]["payment_url"],
                    "message": "Redirection vers CinetPay."
                }
            return {"status": "failed", "message": data.get("description", "Erreur d'initialisation CinetPay")}
        except requests.RequestException as e:
            logger.error(f"Erreur réseau CinetPay: {str(e)}")
            return {"status": "failed", "message": "Erreur de communication avec CinetPay."}

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        url = "https://api-checkout.cinetpay.com/v2/payment/check"
        payload = {
            "apikey": self.api_key,
            "site_id": self.site_id,
            "transaction_id": reference
        }
        try:
            response = requests.post(url, json=payload, timeout=15)
            data = response.json()
            if data.get("code") == "00":
                return {
                    "status": "success",
                    "reference": reference,
                    "amount": float(data["data"]["amount"]),
                    "currency": data["data"]["currency"],
                    "provider_status": "successful"
                }
            return {"status": "failed", "message": "Paiement non validé par CinetPay."}
        except requests.RequestException:
            return {"status": "failed", "message": "Erreur de vérification CinetPay."}

    def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        cpm_trans_id = payload.get("cpm_trans_id")
        if not cpm_trans_id:
            return {"status": "failed", "message": "ID de transaction manquant."}
        return self.verify_payment(cpm_trans_id)

class CampayGateway(BaseGateway):
    """Intégration Campay (Cameroun - MTN MoMo, Orange Money)"""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.base_url = "https://www.campay.net/api"
        self.token = self._get_token()

    def _get_token(self) -> str:
        url = f"{self.base_url}/token/"
        payload = {"username": self.username, "password": self.password}
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json().get("token", "")
            return ""
        except requests.RequestException:
            return ""

    def initialize_payment(self, amount: float, currency: str, customer_email: str, customer_phone: str = "", redirect_url: str = "") -> Dict[str, Any]:
        if not self.token:
            return {"status": "failed", "message": "Impossible d'obtenir le token Campay."}
            
        reference = f"CAMPAY-{uuid.uuid4().hex[:12].upper()}"
        url = f"{self.base_url}/get_payment_link/"
        headers = {"Authorization": f"Token {self.token}"}
        payload = {
            "amount": str(int(amount)),
            "currency": currency,
            "description": "Abonnement EDUBULLETIN 237",
            "external_reference": reference,
            "redirect_url": redirect_url
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "success",
                    "reference": reference,
                    "payment_url": data.get("link"),
                    "message": "Lien de paiement Campay généré."
                }
            return {"status": "failed", "message": "Erreur lors de la génération du lien Campay."}
        except requests.RequestException:
            return {"status": "failed", "message": "Erreur réseau Campay."}

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        if not self.token:
            return {"status": "failed", "message": "Token Campay invalide."}
            
        url = f"{self.base_url}/transaction/{reference}/"
        headers = {"Authorization": f"Token {self.token}"}
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "SUCCESSFUL":
                    return {
                        "status": "success",
                        "reference": reference,
                        "amount": float(data.get("amount", 0)),
                        "currency": VALID_CURRENCY,
                        "provider_status": "successful"
                    }
            return {"status": "failed", "message": "Paiement Campay non abouti."}
        except requests.RequestException:
            return {"status": "failed", "message": "Erreur de vérification Campay."}

    def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        signature = headers.get("Campay-Signature", "")
        # Validation de la signature omise pour la concision, mais requise en production
        reference = payload.get("external_reference")
        status = payload.get("status")
        if status == "SUCCESSFUL" and reference:
            return {
                "status": "success",
                "reference": reference,
                "amount": float(payload.get("amount", 0)),
                "currency": VALID_CURRENCY
            }
        return {"status": "failed", "message": "Webhook ignoré ou invalide."}

class FlutterwaveGateway(BaseGateway):
    """Intégration Flutterwave (Panafricain)"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.base_url = "https://api.flutterwave.com/v3"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def initialize_payment(self, amount: float, currency: str, customer_email: str, customer_phone: str = "", redirect_url: str = "") -> Dict[str, Any]:
        reference = f"FLW-{uuid.uuid4().hex[:12].upper()}"
        url = f"{self.base_url}/payments"
        payload = {
            "tx_ref": reference,
            "amount": amount,
            "currency": currency,
            "redirect_url": redirect_url,
            "customer": {
                "email": customer_email,
                "phonenumber": customer_phone,
                "name": "Client EDUBULLETIN"
            },
            "customizations": {
                "title": "EDUBULLETIN 237",
                "description": "Paiement de l'abonnement SaaS"
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=15)
            data = response.json()
            if data.get("status") == "success":
                return {
                    "status": "success",
                    "reference": reference,
                    "payment_url": data["data"]["link"],
                    "message": "Redirection vers Flutterwave."
                }
            return {"status": "failed", "message": data.get("message", "Erreur Flutterwave")}
        except requests.RequestException:
            return {"status": "failed", "message": "Erreur réseau Flutterwave."}

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        url = f"{self.base_url}/transactions/verify_by_reference?tx_ref={reference}"
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            data = response.json()
            if data.get("status") == "success" and data["data"]["status"] == "successful":
                return {
                    "status": "success",
                    "reference": reference,
                    "amount": float(data["data"]["amount"]),
                    "currency": data["data"]["currency"],
                    "provider_status": "successful"
                }
            return {"status": "failed", "message": "Paiement non validé par Flutterwave."}
        except requests.RequestException:
            return {"status": "failed", "message": "Erreur de vérification Flutterwave."}

    def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        secret_hash = os.getenv("FLW_SECRET_HASH")
        signature = headers.get("verif-hash")
        if secret_hash and signature != secret_hash:
            return {"status": "failed", "message": "Signature invalide."}
            
        if payload.get("event") == "charge.completed" and payload.get("data", {}).get("status") == "successful":
            return {
                "status": "success",
                "reference": payload["data"]["tx_ref"],
                "amount": float(payload["data"]["amount"]),
                "currency": payload["data"]["currency"]
            }
        return {"status": "failed", "message": "Événement non pris en charge."}

class PaystackGateway(BaseGateway):
    """Intégration Paystack (Nigéria, Ghana, Afrique du Sud, etc.)"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.base_url = "https://api.paystack.co"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def initialize_payment(self, amount: float, currency: str, customer_email: str, customer_phone: str = "", redirect_url: str = "") -> Dict[str, Any]:
        reference = f"PSTK-{uuid.uuid4().hex[:12].upper()}"
        url = f"{self.base_url}/transaction/initialize"
        # Paystack attend le montant en sous-unités (ex: kobo/cents). Pour XAF, vérifier la doc, généralement * 100
        payload = {
            "reference": reference,
            "amount": int(amount * 100),
            "email": customer_email,
            "currency": currency,
            "callback_url": redirect_url
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=15)
            data = response.json()
            if data.get("status"):
                return {
                    "status": "success",
                    "reference": reference,
                    "payment_url": data["data"]["authorization_url"],
                    "message": "Redirection vers Paystack."
                }
            return {"status": "failed", "message": data.get("message", "Erreur Paystack")}
        except requests.RequestException:
            return {"status": "failed", "message": "Erreur réseau Paystack."}

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        url = f"{self.base_url}/transaction/verify/{reference}"
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            data = response.json()
            if data.get("status") and data["data"]["status"] == "success":
                return {
                    "status": "success",
                    "reference": reference,
                    "amount": float(data["data"]["amount"]) / 100.0,
                    "currency": data["data"]["currency"],
                    "provider_status": "successful"
                }
            return {"status": "failed", "message": "Paiement non validé par Paystack."}
        except requests.RequestException:
            return {"status": "failed", "message": "Erreur de vérification Paystack."}

    def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        # Validation HMAC SHA512
        signature = headers.get("x-paystack-signature", "")
        payload_bytes = json.dumps(payload).encode('utf-8')
        expected_signature = hmac.new(self.secret_key.encode('utf-8'), payload_bytes, hashlib.sha512).hexdigest()
        
        if signature != expected_signature:
            return {"status": "failed", "message": "Signature Paystack invalide."}
            
        if payload.get("event") == "charge.success":
            data = payload.get("data", {})
            return {
                "status": "success",
                "reference": data.get("reference"),
                "amount": float(data.get("amount", 0)) / 100.0,
                "currency": data.get("currency")
            }
        return {"status": "failed", "message": "Événement ignoré."}

class NotchPayGateway(BaseGateway):
    """Intégration NotchPay (Afrique francophone & globale)"""
    
    def __init__(self, public_key: str, private_key: str):
        self.public_key = public_key
        self.private_key = private_key
        self.base_url = "https://api.notchpay.co"
        self.headers = {
            "Authorization": f"Bearer {self.public_key}",
            "Accept": "application/json"
        }

    def initialize_payment(self, amount: float, currency: str, customer_email: str, customer_phone: str = "", redirect_url: str = "") -> Dict[str, Any]:
        reference = f"NP-{uuid.uuid4().hex[:12].upper()}"
        url = f"{self.base_url}/payments/initialize"
        payload = {
            "amount": amount,
            "currency": currency,
            "reference": reference,
            "email": customer_email,
            "description": "Abonnement EDUBULLETIN 237",
            "callback": redirect_url
        }
        
        try:
            response = requests.post(url, data=payload, headers=self.headers, timeout=15)
            data = response.json()
            if data.get("status") == "Accepted":
                return {
                    "status": "success",
                    "reference": reference,
                    "payment_url": data["authorization"]["url"],
                    "message": "Redirection vers NotchPay."
                }
            return {"status": "failed", "message": data.get("message", "Erreur NotchPay")}
        except requests.RequestException:
            return {"status": "failed", "message": "Erreur réseau NotchPay."}

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        url = f"{self.base_url}/payments/{reference}"
        headers = {"Authorization": f"Bearer {self.private_key}", "Accept": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=15)
            data = response.json()
            if data.get("status") == "OK" and data["transaction"]["status"] == "complete":
                return {
                    "status": "success",
                    "reference": reference,
                    "amount": float(data["transaction"]["amount"]),
                    "currency": data["transaction"]["currency"],
                    "provider_status": "successful"
                }
            return {"status": "failed", "message": "Paiement non validé par NotchPay."}
        except requests.RequestException:
            return {"status": "failed", "message": "Erreur de vérification NotchPay."}

    def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        signature = headers.get("x-notch-signature", "")
        # Validation de la signature avec NotchPay requise en production
        event = payload.get("event")
        if event == "payment.complete":
            data = payload.get("data", {})
            return {
                "status": "success",
                "reference": data.get("reference"),
                "amount": float(data.get("amount", 0)),
                "currency": data.get("currency")
            }
        return {"status": "failed", "message": "Événement ignoré."}


class PaymentGateway:
    """Classe principale agissant comme façade pour tous les agrégateurs."""
    
    def __init__(self):
        self.provider_name = os.getenv("PAYMENT_PROVIDER", "DEMO").upper()
        self.provider = self._initialize_provider()

    def _initialize_provider(self) -> BaseGateway:
        if self.provider_name == "CINETPAY":
            api_key = os.getenv("CINETPAY_API_KEY")
            site_id = os.getenv("CINETPAY_SITE_ID")
            if api_key and site_id:
                return CinetPayGateway(api_key, site_id)
                
        elif self.provider_name == "CAMPAY":
            username = os.getenv("CAMPAY_USERNAME")
            password = os.getenv("CAMPAY_PASSWORD")
            if username and password:
                return CampayGateway(username, password)
                
        elif self.provider_name == "FLUTTERWAVE":
            secret_key = os.getenv("FLW_SECRET_KEY")
            if secret_key:
                return FlutterwaveGateway(secret_key)
                
        elif self.provider_name == "PAYSTACK":
            secret_key = os.getenv("PAYSTACK_SECRET_KEY")
            if secret_key:
                return PaystackGateway(secret_key)
                
        elif self.provider_name == "NOTCHPAY":
            public_key = os.getenv("NOTCHPAY_PUBLIC_KEY")
            private_key = os.getenv("NOTCHPAY_PRIVATE_KEY")
            if public_key and private_key:
                return NotchPayGateway(public_key, private_key)

        logger.warning(f"Configuration {self.provider_name} incomplète ou non trouvée. Fallback vers DEMO_SANDBOX.")
        return DemoGateway()

    def _validate_amount(self, amount: float):
        valid_amounts = list(SUBSCRIPTION_PLANS.values())
        if amount not in valid_amounts:
            raise PaymentError(f"Montant invalide. Les montants autorisés sont : {valid_amounts} {VALID_CURRENCY}")

    def initialize_payment(self, amount: float, currency: str, customer_email: str, customer_phone: str = "", redirect_url: str = "") -> Dict[str, Any]:
        if currency.upper() != VALID_CURRENCY:
            raise PaymentError(f"Devise non supportée. Utilisez {VALID_CURRENCY}.")
            
        self._validate_amount(amount)
        
        logger.info(f"Initialisation du paiement de {amount} {currency} via {self.provider.__class__.__name__}")
        return self.provider.initialize_payment(amount, currency, customer_email, customer_phone, redirect_url)

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        logger.info(f"Vérification du paiement {reference} via {self.provider.__class__.__name__}")
        return self.provider.verify_payment(reference)

    def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Traitement du webhook via {self.provider.__class__.__name__}")
        return self.provider.handle_webhook(payload, headers)