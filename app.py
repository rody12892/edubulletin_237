import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

# Importation des modules du projet (supposés existants selon le contexte)
from database import get_db, Student, Grade, Subject, School
from payment_gateway import initiate_mobile_money_payment, verify_mobile_money_payment

app = FastAPI(
    title="EDUBULLETIN 237",
    description="SaaS d'automatisation des bulletins scolaires et gestion multi-tenant.",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montage des fichiers statiques et configuration des templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- SCHÉMAS PYDANTIC ---

class PaymentInitiateRequest(BaseModel):
    ecole_id: int = Field(..., description="ID de l'école (Multi-tenant)")
    amount: float = Field(..., gt=0, description="Montant en FCFA")
    phone_number: str = Field(..., description="Numéro de téléphone Mobile Money")
    payer_name: str = Field(..., description="Nom du payeur")

class GradeInput(BaseModel):
    student_id: int = Field(..., description="ID de l'élève")
    subject_id: int = Field(..., description="ID de la matière")
    sequence: int = Field(..., ge=1, le=6, description="Séquence d'évaluation (1 à 6)")
    note: float = Field(..., ge=0, le=20, description="Note sur 20")
    coefficient: int = Field(default=1, gt=0, description="Coefficient de la matière")

class StudentCreate(BaseModel):
    ecole_id: int = Field(..., description="ID de l'école (Multi-tenant)")
    nom: str = Field(..., min_length=1)
    prenom: str = Field(..., min_length=1)
    matricule: str = Field(..., min_length=3)
    classe: str = Field(..., min_length=2)

class StudentResponse(StudentCreate):
    id: int

    class Config:
        orm_mode = True

# --- ROUTES DE BASE ---

@app.get("/")
async def serve_homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "EDUBULLETIN 237 - Accueil"})

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "EDUBULLETIN 237"}

# --- ROUTES DE PAIEMENT (MOBILE MONEY FCFA) ---

@app.post("/api/pay/initiate", status_code=status.HTTP_200_OK)
async def initiate_payment(payload: PaymentInitiateRequest):
    result = initiate_mobile_money_payment(
        amount=payload.amount,
        phone=payload.phone_number,
        name=payload.payer_name,
        metadata={"ecole_id": payload.ecole_id}
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=result.get("message", "Échec de l'initialisation du paiement.")
        )
    return result

@app.get("/api/pay/verify/{reference}", status_code=status.HTTP_200_OK)
async def verify_payment(reference: str):
    result = verify_mobile_money_payment(reference)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Transaction introuvable ou référence invalide."
        )
    return result

# --- ROUTES SAAS : GESTION SCOLAIRE ---

@app.post("/api/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(student: StudentCreate, db: Session = Depends(get_db)):
    existing_student = db.query(Student).filter(
        Student.matricule == student.matricule, 
        Student.ecole_id == student.ecole_id
    ).first()
    
    if existing_student:
        raise HTTPException(status_code=400, detail="Un élève avec ce matricule existe déjà dans cette école.")
    
    new_student = Student(**student.dict())
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    return new_student

@app.post("/api/grades", status_code=status.HTTP_201_CREATED)
def add_grade(grade: GradeInput, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == grade.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Élève introuvable.")

    existing_grade = db.query(Grade).filter(
        Grade.student_id == grade.student_id,
        Grade.subject_id == grade.subject_id,
        Grade.sequence == grade.sequence
    ).first()

    if existing_grade:
        existing_grade.note = grade.note
        existing_grade.coefficient = grade.coefficient
    else:
        new_grade = Grade(**grade.dict())
        db.add(new_grade)
    
    db.commit()
    return {"message": "Note enregistrée avec succès.", "sequence": grade.sequence}

@app.post("/api/calculate-ranks/{ecole_id}/{classe}/{sequence}")
def calculate_class_ranks(ecole_id: int, classe: str, sequence: int, db: Session = Depends(get_db)):
    if sequence < 1 or sequence > 6:
        raise HTTPException(status_code=400, detail="La séquence doit être comprise entre 1 et 6.")

    students = db.query(Student).filter(Student.ecole_id == ecole_id, Student.classe == classe).all()
    if not students:
        raise HTTPException(status_code=404, detail="Aucun élève trouvé pour cette classe et cette école.")

    results = []
    for s in students:
        grades = db.query(Grade).filter(Grade.student_id == s.id, Grade.sequence == sequence).all()
        total_points = sum(g.note * g.coefficient for g in grades)
        total_coef = sum(g.coefficient for g in grades)
        moyenne = total_points / total_coef if total_coef > 0 else 0.0
        
        results.append({
            "student_id": s.id,
            "matricule": s.matricule,
            "nom": s.nom,
            "prenom": s.prenom,
            "moyenne": round(moyenne, 2)
        })

    results.sort(key=lambda x: x["moyenne"], reverse=True)
    
    for idx, res in enumerate(results):
        res["rang"] = idx + 1

    return {
        "ecole_id": ecole_id,
        "classe": classe,
        "sequence": sequence,
        "effectif": len(results),
        "classement": results
    }

# --- PORTAIL PARENT PUBLIC ---

@app.get("/api/bulletin/{matricule}/{sequence}")
def get_student_bulletin(matricule: str, sequence: int, db: Session = Depends(get_db)):
    if sequence < 1 or sequence > 6:
        raise HTTPException(status_code=400, detail="La séquence doit être comprise entre 1 et 6.")

    student = db.query(Student).filter(Student.matricule == matricule).first()
    if not student:
        raise HTTPException(status_code=404, detail="Élève introuvable avec ce matricule.")

    grades = db.query(Grade).filter(
        Grade.student_id == student.id,
        Grade.sequence == sequence
    ).all()

    total_points = sum(g.note * g.coefficient for g in grades)
    total_coef = sum(g.coefficient for g in grades)
    moyenne = total_points / total_coef if total_coef > 0 else 0.0

    class_students = db.query(Student).filter(
        Student.ecole_id == student.ecole_id,
        Student.classe == student.classe
    ).all()

    student_averages = []
    for s in class_students:
        s_grades = db.query(Grade).filter(Grade.student_id == s.id, Grade.sequence == sequence).all()
        s_total_points = sum(g.note * g.coefficient for g in s_grades)
        s_total_coef = sum(g.coefficient for g in s_grades)
        s_moy = s_total_points / s_total_coef if s_total_coef > 0 else 0.0
        student_averages.append({"id": s.id, "moyenne": s_moy})

    student_averages.sort(key=lambda x: x["moyenne"], reverse=True)

    rank = 1
    for idx, sa in enumerate(student_averages):
        if sa["id"] == student.id:
            rank = idx + 1
            break

    return {
        "ecole_id": student.ecole_id,
        "etudiant": {
            "nom": student.nom,
            "prenom": student.prenom,
            "matricule": student.matricule,
            "classe": student.classe
        },
        "sequence": sequence,
        "notes": [
            {
                "matiere_id": g.subject_id,
                "note": g.note,
                "coefficient": g.coefficient,
                "total": round(g.note * g.coefficient, 2)
            } for g in grades
        ],
        "statistiques": {
            "total_points": round(total_points, 2),
            "total_coefficients": total_coef,
            "moyenne": round(moyenne, 2),
            "rang": rank,
            "effectif_classe": len(class_students)
        }
    }

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)