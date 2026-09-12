import os
import io
import csv
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import uvicorn
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status, Form, File, UploadFile, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Modules internes
from database import (
    get_db, init_db, School, User, Classroom, Subject,
    TeacherAssignment, Student, Grade, SequencePublication,
    SubscriptionTransaction, verify_pw, hash_pw
)
from auth import (
    create_access_token, decode_access_token, get_current_user,
    get_current_user_optional, require_role, check_school_license
)
from payment_monetbil import monetbil_client, PACKS_CONFIG
from services.bulletin_engine import calculate_sequence_bulletins, get_minesec_appreciation
from services.excel_importer import import_students_from_file, generate_next_matricule

logger = logging.getLogger("EduBulletin237")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="EDUBULLETIN 237",
    description="SaaS d'automatisation des bulletins scolaires et gestion multi-tenant au Cameroun.",
    version="2.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

def render_template(request: Request, template_name: str, context: Optional[Dict[str, Any]] = None):
    ctx = context or {}
    ctx['request'] = request
    try:
        return templates.TemplateResponse(request=request, name=template_name, context=ctx)
    except TypeError:
        return templates.TemplateResponse(name=template_name, context=ctx)


# Démarrage & Initialisation BD
@app.on_event("startup")
def startup_event():
    try:
        init_db()
        logger.info("[EDUBULLETIN 237] Base de donnees initialisee et verifiee.")
    except Exception as exc:
        logger.error(f"[EDUBULLETIN 237] Erreur demarrage BD: {exc}")

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Redirige les requêtes de pages web non authentifiées directement vers /login."""
    if exc.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]:
        if not request.url.path.startswith("/api/"):
            return RedirectResponse(f"/login?next={request.url.path}", status_code=status.HTTP_302_FOUND)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# ==============================================================================
# ROUTE RACINE & REDIRECTION INTELLIGENTE
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def root_view(request: Request, db: Session = Depends(get_db)):
    """Redirige vers le tableau de bord approprie si connecte, sinon affiche la page d'accueil/connexion."""
    user = get_current_user_optional(request, db)
    if user:
        if user.role == "superadmin":
            return RedirectResponse("/superadmin/overview", status_code=status.HTTP_302_FOUND)
        elif user.role == "proviseur":
            return RedirectResponse("/admin/dashboard", status_code=status.HTTP_302_FOUND)
        elif user.role == "secretaire":
            return RedirectResponse("/secretaire/eleves", status_code=status.HTTP_302_FOUND)
        elif user.role == "professeur":
            return RedirectResponse("/prof/classes", status_code=status.HTTP_302_FOUND)
        elif user.role == "parent":
            school = db.query(School).filter(School.id == user.ecole_id).first()
            slug = school.slug if school else "led"
            return RedirectResponse(f"/e/{slug}", status_code=status.HTTP_302_FOUND)
    
    # Si non connecté, afficher la page de connexion directement avec sélecteur de rôle
    return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

@app.get("/health")
@app.get("/healthz")
@app.get("/api/health")
async def health_check():
    port = int(os.environ.get("PORT", "8080"))
    return {
        "status": "healthy",
        "app": "EDUBULLETIN 237",
        "version": "2.0.0",
        "port": port,
        "active_gateway": "Monetbil Widget v2.1"
    }

# ==============================================================================
# AUTHENTIFICATION & SESSIONS (JWT + COOKIES HTTP-ONLY)
# ==============================================================================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    return render_template(request, "login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login_form_post(
    request: Request,
    identifiant: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Gère la soumission directe du formulaire HTML de connexion."""
    if not identifiant or not password:
        return render_template(request, "login.html", {
            "request": request,
            "error": "Veuillez renseigner votre identifiant et votre mot de passe."
        })

    user = db.query(User).filter(User.identifiant == identifiant.strip()).first()
    if not user or not verify_pw(password.strip(), user.mot_de_passe_hash):
        return render_template(request, "login.html", {
            "request": request,
            "error": "Identifiant ou mot de passe incorrect.",
            "identifiant": identifiant
        })

    school = db.query(School).filter(School.id == user.ecole_id).first() if user.ecole_id else None
    check_school_license(school)

    redirect_map = {
        "superadmin": "/superadmin/overview",
        "proviseur": "/admin/dashboard",
        "secretaire": "/secretaire/eleves",
        "professeur": "/prof/classes",
        "parent": f"/e/{school.slug if school else 'led'}"
    }
    target_url = redirect_map.get(user.role, "/")

    token_data = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "ecole_id": user.ecole_id
    }
    token = create_access_token(token_data)

    resp = RedirectResponse(target_url, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax"
    )
    return resp

@app.get("/demo/{role_slug}")
async def demo_quick_login(role_slug: str, db: Session = Depends(get_db)):
    """Connexion immédiate en 1 clic pour tester chaque rôle sans saisir d'identifiant."""
    role_map = {
        "proviseur": ("+237699001122", "/admin/dashboard"),
        "secretaire": ("+237677112233", "/secretaire/eleves"),
        "prof": ("+237690112233", "/prof/classes"),
        "superadmin": ("admin@edubulletin237.cm", "/superadmin/overview")
    }

    if role_slug not in role_map:
        raise HTTPException(status_code=404, detail="Rôle de test introuvable.")

    identifiant, target_url = role_map[role_slug]
    user = db.query(User).filter(User.identifiant == identifiant).first()
    if not user:
        raise HTTPException(status_code=404, detail="Compte de test introuvable.")

    token_data = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "ecole_id": user.ecole_id
    }
    token = create_access_token(token_data)

    resp = RedirectResponse(target_url, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax"
    )
    return resp

class LoginPayload(BaseModel):
    identifiant: str
    mot_de_passe: str

@app.post("/api/auth/login")
async def api_login(payload: LoginPayload, response: Response, db: Session = Depends(get_db)):
    identifiant = payload.identifiant.strip()
    mot_de_passe = payload.mot_de_passe.strip()

    # Recherche par email ou par téléphone via identifiant unique
    user = db.query(User).filter(User.identifiant == identifiant).first()

    if not user or not verify_pw(mot_de_passe, user.mot_de_passe_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect."
        )

    if not user.est_actif:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte utilisateur a été désactivé par l'administration."
        )

    # Vérification de la licence pour les utilisateurs d'école
    school = db.query(School).filter(School.id == user.ecole_id).first() if user.ecole_id else None
    licence_statut = check_school_license(school)

    # Déterminer l'URL de redirection
    redirect_map = {
        "superadmin": "/superadmin/overview",
        "proviseur": "/admin/dashboard",
        "secretaire": "/secretaire/eleves",
        "professeur": "/prof/classes",
        "parent": f"/e/{school.slug if school else 'led'}"
    }
    redirect_url = redirect_map.get(user.role, "/")

    # Génération du token
    token_data = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "ecole_id": user.ecole_id
    }
    token = create_access_token(token_data)

    # Création de la réponse JSON avec cookie sécurisé
    json_resp = JSONResponse({
        "success": True,
        "token": token,
        "redirect_url": redirect_url,
        "user": {
            "id": user.id,
            "nom_complet": user.nom_complet,
            "role": user.role,
            "ecole_id": user.ecole_id,
            "licence_statut": licence_statut
        }
    })
    
    # Cookie valable 7 jours
    json_resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax"
    )
    return json_resp

@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie(key="access_token")
    return resp

@app.get("/api/auth/me")
async def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    school = db.query(School).filter(School.id == user.ecole_id).first() if user.ecole_id else None
    return {
        "id": user.id,
        "nom_complet": user.nom_complet,
        "role": user.role,
        "ecole": {
            "id": school.id if school else None,
            "nom": school.nom if school else "Administration Centrale",
            "statut_licence": school.statut_licence if school else "actif",
            "date_fin_licence": str(school.date_fin_licence) if school else None
        } if school else None
    }

# ==============================================================================
# TABLEAU DE BORD PROVISEUR (ADMIN SCOLAIRE)
# ==============================================================================
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user: User = Depends(require_role(["proviseur"])), db: Session = Depends(get_db)):
    school = db.query(School).filter(School.id == user.ecole_id).first()
    check_school_license(school)

    classes = db.query(Classroom).filter(Classroom.ecole_id == user.ecole_id).all()
    teachers = db.query(User).filter(User.ecole_id == user.ecole_id, User.role == "professeur").all()
    subjects = db.query(Subject).filter(Subject.ecole_id == user.ecole_id).all()
    assignments = db.query(TeacherAssignment).join(Classroom).filter(Classroom.ecole_id == user.ecole_id).all()
    publications = db.query(SequencePublication).filter(SequencePublication.ecole_id == user.ecole_id).all()

    # Effectif total
    total_students = db.query(Student).filter(Student.ecole_id == user.ecole_id).count()

    # Coefficients en attente
    pending_coeffs = [a for a in assignments if a.statut == "en_attente"]

    return render_template(request, "admin_dashboard.html", {
        "request": request,
        "user": user,
        "current_user": user,
        "school": school,
        "classes": classes,
        "teachers": teachers,
        "subjects": subjects,
        "assignments": assignments,
        "publications": publications,
        "total_students": total_students,
        "pending_coeffs": pending_coeffs,
        "packs": PACKS_CONFIG
    })

@app.post("/api/admin/valider-coeff/{assignment_id}")
async def valider_coeff(assignment_id: int, user: User = Depends(require_role(["proviseur"])), db: Session = Depends(get_db)):
    assignment = db.query(TeacherAssignment).filter(TeacherAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Affectation introuvable.")
    
    assignment.coeff_valide = assignment.coeff_propose or 1
    assignment.statut = "valide"
    db.commit()
    return {"success": True, "message": f"Coefficient validé à {assignment.coeff_valide} pour {assignment.subject.nom}."}

@app.post("/api/admin/rejeter-coeff/{assignment_id}")
async def rejeter_coeff(assignment_id: int, user: User = Depends(require_role(["proviseur"])), db: Session = Depends(get_db)):
    assignment = db.query(TeacherAssignment).filter(TeacherAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Affectation introuvable.")
    
    assignment.statut = "rejete"
    db.commit()
    return {"success": True, "message": "Proposition de coefficient rejetée. L'enseignant a été notifié."}

@app.post("/api/admin/assigner-prof")
async def assigner_prof(
    classe_id: int = Form(...),
    matiere_id: int = Form(...),
    enseignant_id: int = Form(...),
    coeff: int = Form(default=1),
    user: User = Depends(require_role(["proviseur"])),
    db: Session = Depends(get_db)
):
    existing = db.query(TeacherAssignment).filter(
        TeacherAssignment.classe_id == classe_id,
        TeacherAssignment.matiere_id == matiere_id
    ).first()

    if existing:
        existing.enseignant_id = enseignant_id
        existing.coeff_valide = coeff
        existing.coeff_propose = coeff
        existing.statut = "valide"
    else:
        new_aff = TeacherAssignment(
            classe_id=classe_id,
            matiere_id=matiere_id,
            enseignant_id=enseignant_id,
            coeff_propose=coeff,
            coeff_valide=coeff,
            statut="valide"
        )
        db.add(new_aff)
    
    db.commit()
    return {"success": True, "message": "Enseignant affecté avec succès."}

@app.post("/api/admin/publier-sequence")
async def publier_sequence(
    sequence: int = Form(...),
    classe_id: Optional[int] = Form(None),
    user: User = Depends(require_role(["proviseur"])),
    db: Session = Depends(get_db)
):
    """Publie officiellement les bulletins d'une séquence pour consultation par les parents."""
    if sequence < 1 or sequence > 6:
        raise HTTPException(status_code=400, detail="La séquence doit être comprise entre 1 et 6.")
    
    existing = db.query(SequencePublication).filter(
        SequencePublication.ecole_id == user.ecole_id,
        SequencePublication.sequence == sequence,
        SequencePublication.classe_id == classe_id
    ).first()

    if existing:
        existing.est_publiee = True
        existing.date_publication = datetime.utcnow()
    else:
        new_pub = SequencePublication(
            ecole_id=user.ecole_id,
            sequence=sequence,
            classe_id=classe_id,
            est_publiee=True,
            publie_par_id=user.id,
            date_publication=datetime.utcnow()
        )
        db.add(new_pub)
    
    db.commit()
    return {"success": True, "message": f"Séquence {sequence} publiée avec succès. Les parents peuvent consulter les bulletins."}

# ==============================================================================
# SECRÉTARIAT (GESTION DES ÉLÈVES & IMPORT EXCEL/CSV)
# ==============================================================================
@app.get("/secretaire/eleves", response_class=HTMLResponse)
async def secretaire_dashboard(request: Request, user: User = Depends(require_role(["secretaire", "proviseur"])), db: Session = Depends(get_db)):
    school = db.query(School).filter(School.id == user.ecole_id).first()
    check_school_license(school)

    classes = db.query(Classroom).filter(Classroom.ecole_id == user.ecole_id).all()
    students = db.query(Student).filter(Student.ecole_id == user.ecole_id).order_by(Student.id.desc()).all()

    return render_template(request, "secretaire.html", {
        "request": request,
        "user": user,
        "current_user": user,
        "school": school,
        "classes": classes,
        "students": students
    })

@app.post("/api/secretaire/ajouter-eleve")
async def ajouter_eleve(
    nom: str = Form(...),
    prenom: str = Form(""),
    date_naissance: str = Form(""),
    sexe: str = Form("M"),
    classe_id: int = Form(...),
    parent_phone: str = Form(""),
    matricule_manuel: Optional[str] = Form(None),
    user: User = Depends(require_role(["secretaire", "proviseur"])),
    db: Session = Depends(get_db)
):
    school = db.query(School).filter(School.id == user.ecole_id).first()
    matricule = matricule_manuel.strip().upper() if matricule_manuel else generate_next_matricule(db, school)

    # Vérification d'unicité
    existing = db.query(Student).filter(Student.ecole_id == user.ecole_id, Student.matricule == matricule).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Le matricule {matricule} est déjà attribué.")

    new_student = Student(
        ecole_id=user.ecole_id,
        classe_id=classe_id,
        matricule=matricule,
        nom=nom.strip().upper(),
        prenom=prenom.strip().title(),
        date_naissance=date_naissance.strip(),
        sexe=sexe.strip().upper(),
        parent_phone=parent_phone.strip()
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    return {"success": True, "message": f"Élève {new_student.nom_complet} enregistré sous le matricule {matricule}."}

@app.post("/api/secretaire/importer-fichier")
async def importer_fichier_eleves(
    file: UploadFile = File(...),
    classe_id: Optional[int] = Form(None),
    user: User = Depends(require_role(["secretaire", "proviseur"])),
    db: Session = Depends(get_db)
):
    """Importe un lot d'élèves depuis un fichier CSV ou Excel .xlsx."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide.")

    try:
        summary = import_students_from_file(
            db=db,
            school_id=user.ecole_id,
            file_bytes=content,
            filename=file.filename,
            default_class_id=classe_id
        )
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"Erreur import fichier: {e}")
        raise HTTPException(status_code=400, detail=f"Erreur lors du traitement du fichier: {str(e)}")

@app.get("/api/secretaire/modele-eleves.csv")
async def telecharger_modele_csv():
    """Fournit le modèle CSV officiel prêt à remplir."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Nom", "Prenom", "Date_Naissance", "Sexe", "Classe", "Telephone_Parent"])
    writer.writerow(["KAMGA", "Jean Paul", "15/04/2009", "M", "3ème B", "+237690123456"])
    writer.writerow(["NGONO", "Marie Claire", "22/11/2009", "F", "3ème B", "+237670987654"])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=modele_import_eleves_237.csv"}
    )

# ==============================================================================
# ENSEIGNANT (SAISIE DES NOTES & PROPOSITION DE COEFFICIENTS)
# ==============================================================================
@app.get("/prof/classes", response_class=HTMLResponse)
async def prof_dashboard(request: Request, user: User = Depends(require_role(["professeur"])), db: Session = Depends(get_db)):
    school = db.query(School).filter(School.id == user.ecole_id).first()
    check_school_license(school)

    assignments = db.query(TeacherAssignment).filter(TeacherAssignment.enseignant_id == user.id).all()

    return render_template(request, "prof.html", {
        "request": request,
        "user": user,
        "current_user": user,
        "school": school,
        "assignments": assignments
    })

@app.post("/api/prof/proposer-coeff")
async def proposer_coeff(
    assignment_id: int = Form(...),
    coeff: int = Form(...),
    user: User = Depends(require_role(["professeur"])),
    db: Session = Depends(get_db)
):
    assignment = db.query(TeacherAssignment).filter(
        TeacherAssignment.id == assignment_id,
        TeacherAssignment.enseignant_id == user.id
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Affectation introuvable.")

    assignment.coeff_propose = coeff
    assignment.statut = "en_attente"
    db.commit()
    return {"success": True, "message": f"Proposition de coefficient {coeff} transmise au Proviseur."}

@app.get("/api/prof/grille-notes/{assignment_id}/{sequence}")
async def get_grille_notes(assignment_id: int, sequence: int, user: User = Depends(require_role(["professeur", "proviseur"])), db: Session = Depends(get_db)):
    assignment = db.query(TeacherAssignment).filter(TeacherAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Affectation introuvable.")

    students = db.query(Student).filter(Student.classe_id == assignment.classe_id).order_by(Student.nom).all()
    grades_map = {
        g.eleve_id: g for g in db.query(Grade).filter(
            Grade.affectation_id == assignment_id,
            Grade.sequence == sequence
        ).all()
    }

    results = []
    for s in students:
        g = grades_map.get(s.id)
        results.append({
            "eleve_id": s.id,
            "matricule": s.matricule,
            "nom_complet": s.nom_complet,
            "note": g.note_sur_20 if g and not g.est_absent else None,
            "est_absent": g.est_absent if g else False,
            "statut_saisie": g.statut_saisie if g else "brouillon"
        })

    return {
        "assignment_id": assignment_id,
        "matiere": assignment.subject.nom,
        "classe": assignment.classroom.nom,
        "sequence": sequence,
        "coeff": assignment.coeff_valide or assignment.coeff_propose or 1,
        "students": results
    }

class NoteEntry(BaseModel):
    eleve_id: int
    note: Optional[float] = None
    est_absent: bool = False

class EnregistrerNotesPayload(BaseModel):
    assignment_id: int
    sequence: int
    statut_saisie: str = "brouillon"  # "brouillon" ou "soumis"
    notes: List[NoteEntry]

@app.post("/api/prof/enregistrer-notes")
async def enregistrer_notes(payload: EnregistrerNotesPayload, user: User = Depends(require_role(["professeur", "proviseur"])), db: Session = Depends(get_db)):
    assignment = db.query(TeacherAssignment).filter(TeacherAssignment.id == payload.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Affectation introuvable.")

    for item in payload.notes:
        existing_grade = db.query(Grade).filter(
            Grade.affectation_id == payload.assignment_id,
            Grade.eleve_id == item.eleve_id,
            Grade.sequence == payload.sequence
        ).first()

        val_note = None
        if not item.est_absent and item.note is not None:
            # Arrondi réglementaire au quart de point (0.25)
            val_note = round(round(float(item.note) * 4) / 4, 2)
            val_note = max(0.0, min(20.0, val_note))

        if existing_grade:
            existing_grade.note_sur_20 = val_note
            existing_grade.est_absent = item.est_absent
            existing_grade.statut_saisie = payload.statut_saisie
            existing_grade.saisi_par_id = user.id
            existing_grade.date_mise_a_jour = datetime.utcnow()
        else:
            new_grade = Grade(
                ecole_id=user.ecole_id,
                affectation_id=payload.assignment_id,
                eleve_id=item.eleve_id,
                sequence=payload.sequence,
                note_sur_20=val_note,
                est_absent=item.est_absent,
                statut_saisie=payload.statut_saisie,
                saisi_par_id=user.id
            )
            db.add(new_grade)

    db.commit()
    msg = "Notes soumises pour validation." if payload.statut_saisie == "soumis" else "Brouillon sauvegardé avec succès."
    return {"success": True, "message": msg}

# ==============================================================================
# SUPERADMIN (PLATEFORME KAPLO - GESTION DES ÉTABLISSEMENTS & LICENCES)
# ==============================================================================
@app.get("/superadmin/overview", response_class=HTMLResponse)
async def superadmin_overview(request: Request, user: User = Depends(require_role(["superadmin"])), db: Session = Depends(get_db)):
    schools = db.query(School).all()
    transactions = db.query(SubscriptionTransaction).order_by(SubscriptionTransaction.id.desc()).limit(30).all()
    total_users = db.query(User).count()
    total_students = db.query(Student).count()

    return render_template(request, "superadmin.html", {
        "request": request,
        "user": user,
        "current_user": user,
        "schools": schools,
        "transactions": transactions,
        "total_users": total_users,
        "total_students": total_students,
        "packs": PACKS_CONFIG
    })

@app.post("/api/superadmin/prolonger-licence")
async def prolonger_licence(
    ecole_id: int = Form(...),
    annees: int = Form(1),
    motif: str = Form("Renouvellement administratif"),
    user: User = Depends(require_role(["superadmin"])),
    db: Session = Depends(get_db)
):
    school = db.query(School).filter(School.id == ecole_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="Établissement introuvable.")

    school.date_fin_licence = school.date_fin_licence + timedelta(days=365 * annees)
    school.statut_licence = "actif"
    db.commit()

    return {"success": True, "message": f"Licence de '{school.nom}' prolongée jusqu'au {school.date_fin_licence.strftime('%d/%m/%Y')}."}

@app.post("/api/superadmin/creer-ecole")
async def creer_ecole(
    nom: str = Form(...),
    code: str = Form(...),
    ville: str = Form("Douala"),
    telephone: str = Form("+237690000000"),
    email_proviseur: str = Form(...),
    nom_proviseur: str = Form(...),
    mot_de_passe_proviseur: str = Form("edubulletin2026"),
    user: User = Depends(require_role(["superadmin"])),
    db: Session = Depends(get_db)
):
    # Création école
    code_clean = code.strip().upper()
    slug = code_clean.lower()
    
    new_school = School(
        nom=nom.strip(),
        code=code_clean,
        slug=slug,
        ville=ville.strip(),
        telephone=telephone.strip(),
        date_fin_licence=datetime.utcnow() + timedelta(days=365),
        statut_licence="actif"
    )
    db.add(new_school)
    db.commit()
    db.refresh(new_school)

    # Création compte Proviseur
    proviseur = User(
        ecole_id=new_school.id,
        email=email_proviseur.strip().lower(),
        telephone=telephone.strip(),
        mot_de_passe_hash=hash_pw(mot_de_passe_proviseur),
        nom_complet=nom_proviseur.strip(),
        role="proviseur",
        est_actif=True
    )
    db.add(proviseur)

    # Création classes de base
    classes_defaut = ["6ème A", "5ème A", "4ème Esp", "3ème B", "2nde C", "1ère D", "Tle C"]
    for c_nom in classes_defaut:
        db.add(Classroom(ecole_id=new_school.id, nom=c_nom, annee_scolaire=new_school.annee_scolaire))

    db.commit()
    return {"success": True, "message": f"Établissement {nom} et compte proviseur initialisés avec succès."}

# ==============================================================================
# PORTAIL PUBLIC PARENT (/e/{slug})
# ==============================================================================
@app.get("/e/{slug}", response_class=HTMLResponse)
async def parent_portal_view(slug: str, request: Request, db: Session = Depends(get_db)):
    clean_slug = slug.strip().lower()
    school = db.query(School).filter(
        (School.slug == clean_slug) | (School.code == clean_slug.upper())
    ).first()
    if not school:
        raise HTTPException(status_code=404, detail="Établissement scolaire introuvable.")

    return render_template(request, "parent_portal.html", {
        "request": request,
        "school": school,
        "resultat": None
    })

@app.post("/e/{slug}/consulter", response_class=HTMLResponse)
async def parent_consulter_bulletin(
    slug: str,
    request: Request,
    matricule: str = Form(...),
    date_naissance: str = Form(""),
    sequence: int = Form(1),
    db: Session = Depends(get_db)
):
    clean_slug = slug.strip().lower()
    school = db.query(School).filter(
        (School.slug == clean_slug) | (School.code == clean_slug.upper())
    ).first()
    if not school:
        raise HTTPException(status_code=404, detail="Établissement introuvable.")

    matricule_clean = matricule.strip().upper()
    student = db.query(Student).filter(
        Student.ecole_id == school.id,
        Student.matricule == matricule_clean
    ).first()

    error_msg = None
    bulletin_data = None

    if not student:
        error_msg = f"Aucun élève trouvé avec le matricule '{matricule_clean}' dans cet établissement."
    else:
        # Vérification date de naissance si fournie
        if date_naissance and student.date_naissance and date_naissance.strip() != student.date_naissance.strip():
            error_msg = "La date de naissance ne correspond pas au dossier de l'élève."
        else:
            # Vérifier si la séquence est publiée
            pub = db.query(SequencePublication).filter(
                SequencePublication.ecole_id == school.id,
                SequencePublication.sequence == sequence,
                SequencePublication.est_publie == True
            ).first()

            if not pub:
                error_msg = f"Le bulletin de la Séquence {sequence} n'a pas encore été publié officiellement par l'administration."
            else:
                # Calcul officiel MINESEC
                data = calculate_sequence_bulletins(db, school.id, student.classe_id, sequence)
                bulletin_data = next((b for b in data["bulletins"] if b["student"]["id"] == student.id), None)

    return render_template(request, "parent_portal.html", {
        "request": request,
        "school": school,
        "bulletin": bulletin_data,
        "classe_nom": student.classroom.nom if student and student.classroom else "",
        "sequence": sequence,
        "error": error_msg,
        "matricule": matricule_clean,
        "date_naissance": date_naissance
    })

# ==============================================================================
# IMPRESSION OFFICIELLE DU BULLETIN MINESEC (A4)
# ==============================================================================
@app.get("/bulletin/print/{student_id}/{sequence}", response_class=HTMLResponse)
async def imprimer_bulletin(
    student_id: int,
    sequence: int,
    request: Request,
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Élève introuvable.")

    school = db.query(School).filter(School.id == student.ecole_id).first()
    classroom = db.query(Classroom).filter(Classroom.id == student.classe_id).first()

    # Calcul officiel MINESEC
    calc = calculate_sequence_bulletins(db, school.id, student.classe_id, sequence)
    student_summary = next((b for b in calc["bulletins"] if b["student"]["id"] == student.id), None)

    if not student_summary:
        raise HTTPException(status_code=404, detail="Données du bulletin introuvables pour cet élève.")

    # Aplatir les résultats par matières
    all_subjects_flat = []
    grouped_results = {}
    for grp_key, grp_data in student_summary["groupes"].items():
        grouped_results[grp_data["titre"]] = grp_data["matieres"]

    rang_str = f"{student_summary['rang']}{'er' if student_summary['rang'] == 1 else 'ème'}"
    if student_summary.get("ex_aequo"):
        rang_str += " ex"

    student_summary_augmented = {
        "total_points": student_summary["total_points"],
        "total_coeff": student_summary["total_coefs"],
        "moyenne": student_summary["moyenne"],
        "rang_formate": rang_str,
        "mention": student_summary["appreciation"],
        "appreciation_generale": f"Travail {student_summary['appreciation']}. Poursuivre les efforts."
    }

    return render_template(request, "bulletin_print.html", {
        "request": request,
        "school": school,
        "student": student,
        "classroom": classroom,
        "sequence_num": sequence,
        "grouped_results": grouped_results,
        "student_summary": student_summary_augmented,
        "class_stats": {
            "effectif": calc["classe"]["effectif"],
            "moyenne_generale": calc["stats"]["moyenne_generale"],
            "moyenne_max": calc["stats"]["moyenne_max"],
            "moyenne_min": calc["stats"]["moyenne_min"],
            "taux_reussite": calc["stats"]["taux_reussite"],
            "nb_admis": sum(1 for b in calc["bulletins"] if b["moyenne"] >= 10.0)
        },
        "today_date": datetime.now().strftime("%d/%m/%Y")
    })

# ==============================================================================
# PAIEMENT MONETBIL WIDGET V2.1 & WEBHOOK (MOBILE MONEY XAF)
# ==============================================================================
class PaymentInitPayload(BaseModel):
    pack_id: str
    phone: str = ""
    return_url: Optional[str] = None

@app.post("/api/paiement/monetbil/initier")
async def initier_paiement_monetbil(
    payload: PaymentInitPayload,
    request: Request,
    user: User = Depends(require_role(["proviseur", "superadmin"])),
    db: Session = Depends(get_db)
):
    """
    Initie une transaction officielle via Monetbil Widget API v2.1.
    Génère le widget et l'URL de paiement Mobile Money (MTN MoMo & Orange Money).
    """
    pack = PACKS_CONFIG.get(payload.pack_id)
    if not pack:
        raise HTTPException(status_code=400, detail="Pack d'abonnement invalide.")

    school = db.query(School).filter(School.id == user.ecole_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="Établissement introuvable.")

    # Création référence unique
    import uuid
    payment_ref = f"EDU237-{school.id}-{int(datetime.utcnow().timestamp())}"

    # URLs de redirection et de notification
    base_domain = str(request.base_url).rstrip("/")
    # Si déployé sur Render
    if "onrender.com" in os.getenv("RENDER_EXTERNAL_URL", ""):
        base_domain = os.getenv("RENDER_EXTERNAL_URL").rstrip("/")

    return_url = payload.return_url or f"{base_domain}/paiement/succes?ref={payment_ref}"
    notify_url = f"{base_domain}/api/v1/webhooks/monetbil"

    # Enregistrement de la transaction en base
    transaction = SubscriptionTransaction(
        ecole_id=school.id,
        reference=payment_ref,
        pack=payload.pack_id,
        montant=pack["montant"],
        devise="XAF",
        statut="en_attente",
        telephone_payeur=payload.phone,
        nom_payeur=user.nom_complet
    )
    db.add(transaction)
    db.commit()

    # Appel Passerelle Monetbil Widget v2.1
    res = monetbil_client.create_payment_widget(
        amount=pack["montant"],
        payment_ref=payment_ref,
        item_ref=pack["nom"],
        phone=payload.phone,
        first_name=user.nom_complet.split(" ")[0],
        last_name=" ".join(user.nom_complet.split(" ")[1:]) or "Proviseur",
        email=user.email,
        return_url=return_url,
        notify_url=notify_url
    )

    return {
        "success": True,
        "payment_url": res.get("payment_url"),
        "payment_ref": payment_ref,
        "amount": pack["montant"],
        "pack": pack["nom"]
    }

@app.post("/api/v1/webhooks/monetbil")
async def webhook_monetbil(request: Request, db: Session = Depends(get_db)):
    """
    Webhook officiel Monetbil appelé automatiquement lors de la confirmation du paiement.
    Renouvelle automatiquement la licence de l'école (RG-FACT-01).
    """
    try:
        # Monetbil peut poster en JSON ou en Form-Urlencoded
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        else:
            form_data = await request.form()
            payload = dict(form_data)

        logger.info(f"Webhook Monetbil reçu: {payload}")

        # Vérification du statut
        payment_ref = payload.get("payment_ref")
        status_payment = str(payload.get("status", "")).lower()

        if not payment_ref:
            return JSONResponse({"status": "ignored", "message": "payment_ref manquant"})

        transaction = db.query(SubscriptionTransaction).filter(
            SubscriptionTransaction.reference == payment_ref
        ).first()

        if not transaction:
            logger.warning(f"Webhook Monetbil : Transaction {payment_ref} non trouvée.")
            return JSONResponse({"status": "ignored", "message": "Transaction non trouvée"})

        if status_payment == "success":
            transaction.statut = "succes"
            transaction.monetbil_transaction_id = str(payload.get("transaction_id", ""))
            transaction.date_validation = datetime.utcnow()

            # Renouvellement automatique de la licence de l'établissement
            school = db.query(School).filter(School.id == transaction.ecole_id).first()
            if school:
                now = datetime.utcnow()
                start_date = school.date_fin_licence if school.date_fin_licence > now else now
                school.date_fin_licence = start_date + timedelta(days=365)
                school.statut_licence = "actif"
                logger.info(f"Établissement {school.nom} : Licence renouvelée avec succès jusqu'au {school.date_fin_licence}.")

            db.commit()
            return JSONResponse({"status": "ok", "message": "Transaction validée et licence prolongée."})
        
        elif status_payment in ["failed", "cancelled"]:
            transaction.statut = "echec"
            db.commit()
            return JSONResponse({"status": "ok", "message": "Transaction marquée en échec."})

        return JSONResponse({"status": "received"})

    except Exception as e:
        logger.error(f"Erreur traitement Webhook Monetbil: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get("/paiement/succes", response_class=HTMLResponse)
async def page_paiement_succes(request: Request, ref: str = "", db: Session = Depends(get_db)):
    """Page de confirmation affichée après paiement."""
    tx = db.query(SubscriptionTransaction).filter(SubscriptionTransaction.reference == ref).first() if ref else None
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><title>Paiement Réussi - EDUBULLETIN 237</title><script src="https://cdn.tailwindcss.com"></script><meta charset="utf-8"></head>
    <body class="bg-slate-50 flex items-center justify-center min-h-screen p-4">
        <div class="max-w-md w-full bg-white rounded-xl shadow-xl p-8 text-center border border-slate-200">
            <div class="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4 text-3xl font-bold">
                ✓
            </div>
            <h2 class="text-2xl font-bold text-slate-900 mb-2">Paiement Validé !</h2>
            <p class="text-slate-600 text-sm mb-4">Votre souscription EDUBULLETIN 237 a été confirmée via Monetbil.</p>
            <div class="bg-slate-100 p-3 rounded text-left text-xs font-mono mb-6">
                <div>Référence : {ref or 'Non spécifiée'}</div>
                <div>Statut : Transaction Approuvée</div>
            </div>
            <a href="/admin/dashboard" class="inline-block w-full py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg transition shadow">
                Accéder au Tableau de Bord
            </a>
        </div>
    </body>
    </html>
    """)

# ==============================================================================
# POINT D'ENTRÉE SERVEUR
# ==============================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080").strip())
    print(f"[EDUBULLETIN 237] Démarrage du serveur uvicorn sur http://0.0.0.0:{port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
