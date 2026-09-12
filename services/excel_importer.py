import io
import csv
import re
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from database import Student, Classroom, School

def generate_next_matricule(db: Session, school: School) -> str:
    """Génère le matricule automatique officiel : [CODE_ECOLE][ANNEE_DEBUT][AUTO_INCREMENT_4_CHIFFRES] (RG-SEC-01)."""
    current_year = datetime.now().year % 100  # ex: 26 pour 2026
    prefix = f"{school.code.strip().upper()}{current_year:02d}"
    
    # Trouver le dernier matricule avec ce préfixe
    last_student = db.query(Student).filter(
        Student.ecole_id == school.id,
        Student.matricule.like(f"{prefix}%")
    ).order_by(Student.id.desc()).first()

    next_seq = 1
    if last_student and last_student.matricule:
        match = re.search(r"(\d{4})$", last_student.matricule)
        if match:
            next_seq = int(match.group(1)) + 1

    return f"{prefix}{next_seq:04d}"

def import_students_from_file(
    db: Session,
    school_id: int,
    file_bytes: bytes,
    filename: str,
    default_class_id: int = None
) -> Dict[str, Any]:
    """
    Importe les élèves depuis un fichier Excel (.xlsx) ou CSV (RG-SEC-02).
    Structure attendue : Nom, Prenom, Date_Naissance (JJ/MM/AAAA), Sexe (M/F), Classe (optionnel si default_class_id fourni).
    """
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise ValueError("Établissement introuvable.")

    rows = []
    lower_filename = filename.lower()

    if lower_filename.endswith(".xlsx"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            sheet = wb.active
            for r in sheet.iter_rows(values_only=True):
                if any(r):
                    rows.append([str(c).strip() if c is not None else "" for c in r])
        except ImportError:
            # Fallback si openpyxl non dispo
            raise RuntimeError("Le module openpyxl est requis pour lire les fichiers Excel .xlsx.")
    else:
        # Traitement CSV
        try:
            text = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1")
            
        delimiter = ";" if ";" in text else ","
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        for r in reader:
            if any(r):
                rows.append([c.strip() for c in r])

    if not rows:
        return {"success": False, "message": "Le fichier est vide.", "imported": 0, "errors": []}

    # Recherche de l'en-tête
    headers = [h.lower() for h in rows[0]]
    col_nom = -1
    col_prenom = -1
    col_dnaiss = -1
    col_sexe = -1
    col_classe = -1

    for idx, h in enumerate(headers):
        if "nom" in h:
            col_nom = idx
        elif "prenom" in h:
            col_prenom = idx
        elif "naissance" in h or "date" in h:
            col_dnaiss = idx
        elif "sexe" in h or "genre" in h:
            col_sexe = idx
        elif "classe" in h:
            col_classe = idx

    start_idx = 1
    if col_nom == -1:
        # Pas d'en-tête explicite : mapping par position par défaut
        col_nom = 0
        col_prenom = 1 if len(rows[0]) > 1 else -1
        col_dnaiss = 2 if len(rows[0]) > 2 else -1
        col_sexe = 3 if len(rows[0]) > 3 else -1
        col_classe = 4 if len(rows[0]) > 4 else -1
        start_idx = 0

    imported_count = 0
    duplicate_count = 0
    errors = []

    classes_cache = {c.nom.lower(): c.id for c in db.query(Classroom).filter(Classroom.ecole_id == school_id).all()}

    for line_num, row in enumerate(rows[start_idx:], start=start_idx + 1):
        if not row or not any(row):
            continue

        nom = row[col_nom] if col_nom < len(row) else ""
        prenom = row[col_prenom] if col_prenom != -1 and col_prenom < len(row) else ""
        dnaiss = row[col_dnaiss] if col_dnaiss != -1 and col_dnaiss < len(row) else "01/01/2010"
        sexe = row[col_sexe].upper() if col_sexe != -1 and col_sexe < len(row) else "M"
        sexe = "F" if sexe.startswith("F") else "M"

        if not nom:
            errors.append(f"Ligne {line_num} : Le champ Nom est obligatoire.")
            continue

        # Résolution de la classe
        target_class_id = default_class_id
        if col_classe != -1 and col_classe < len(row) and row[col_classe]:
            cls_name = row[col_classe].strip()
            cls_key = cls_name.lower()
            if cls_key in classes_cache:
                target_class_id = classes_cache[cls_key]
            else:
                # Vérifier quota de classes
                total_classes = db.query(Classroom).filter(Classroom.ecole_id == school_id).count()
                if total_classes >= school.classes_max:
                    errors.append(f"Ligne {line_num} : Quota de classes atteint ({school.classes_max} max pour le pack {school.pack_actuel}).")
                    continue
                new_cls = Classroom(ecole_id=school_id, nom=cls_name)
                db.add(new_cls)
                db.commit()
                db.refresh(new_cls)
                classes_cache[cls_key] = new_cls.id
                target_class_id = new_cls.id

        if not target_class_id:
            # Assigner à la première classe existante
            first_cls = db.query(Classroom).filter(Classroom.ecole_id == school_id).first()
            if not first_cls:
                first_cls = Classroom(ecole_id=school_id, nom="Classe Générale")
                db.add(first_cls)
                db.commit()
                db.refresh(first_cls)
            target_class_id = first_cls.id

        # Détection des doublons stricts (RG-SEC-03)
        existing = db.query(Student).filter(
            Student.ecole_id == school_id,
            Student.nom.ilike(nom),
            Student.prenom.ilike(prenom),
            Student.date_naissance == dnaiss
        ).first()

        if existing:
            duplicate_count += 1
            errors.append(f"Ligne {line_num} : Doublon ignoré ({nom} {prenom}, né(e) le {dnaiss}).")
            continue

        # Création de l'élève
        matricule = generate_next_matricule(db, school)
        student = Student(
            ecole_id=school_id,
            classe_id=target_class_id,
            matricule=matricule,
            nom=nom.upper(),
            prenom=prenom.title(),
            date_naissance=dnaiss,
            sexe=sexe,
            parent_phone=""
        )
        db.add(student)
        db.commit()
        imported_count += 1

    return {
        "success": True,
        "imported": imported_count,
        "duplicates": duplicate_count,
        "errors": errors,
        "message": f"{imported_count} élèves importés avec succès. {duplicate_count} doublons ignorés."
    }
