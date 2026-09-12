import os
import json
import base64
import hmac
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db, User, School

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "EDUBULLETIN_237_SUPER_SECRET_KEY_PROD_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Support pour tokens Bearer ou Cookies
security = HTTPBearer(auto_error=False)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Génère un JWT universel (compatible pyjwt ou fallback natif)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": int(expire.timestamp())})
    
    try:
        import jwt
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception:
        # Fallback natif sans dépendance externe
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps(to_encode).encode()).decode().rstrip("=")
        signature = base64.urlsafe_b64encode(
            hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")
        return f"{header}.{payload}.{signature}"

def decode_access_token(token: str) -> Optional[dict]:
    """Décode et vérifie un token JWT."""
    if not token:
        return None
    try:
        import jwt
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header, payload, sig = parts
            expected_sig = base64.urlsafe_b64encode(
                hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
            ).decode().rstrip("=")
            if not hmac.compare_digest(sig, expected_sig):
                return None
            
            # Ajouter padding base64
            padded = payload + "=" * ((4 - len(payload) % 4) % 4)
            data = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
            if data.get("exp") and time.time() > data["exp"]:
                return None
            return data
        except Exception:
            return None

def get_token_from_request(request: Request) -> Optional[str]:
    """Extrait le token depuis l'en-tête Authorization ou les cookies de session."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1].strip()
    return request.cookies.get("access_token")

def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Renvoie l'utilisateur connecté s'il existe, sans lever d'exception."""
    token = get_token_from_request(request)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    user_id = payload["sub"]
    return db.query(User).filter(User.id == user_id).first()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Exige un utilisateur connecté."""
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée ou non authentifiée. Veuillez vous connecter."
        )
    return user

def require_role(allowed_roles: List[str]):
    """Dépendance RBAC pour filtrer selon les rôles autorisés."""
    def role_checker(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles and user.role != "superadmin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôles autorisés : {', '.join(allowed_roles)}"
            )
        return user
    return role_checker

def check_school_license(school: Optional[School]) -> str:
    """Vérifie l'état de la licence et applique la période de grâce de 7 jours (RG-FACT-02)."""
    if not school:
        return "actif"
    
    now = datetime.utcnow()
    if now > school.date_fin_licence:
        if now <= school.date_fin_licence + timedelta(days=7):
            school.statut_licence = "en_grace"
        else:
            school.statut_licence = "bloque"
    else:
        school.statut_licence = "actif"
        
    return school.statut_licence
