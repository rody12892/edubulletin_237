from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from database import Student, Classroom, School, Grade, TeacherAssignment, Subject

def get_minesec_appreciation(moyenne: float) -> str:
    """Appréciation officielle selon le barème officiel du MINESEC Cameroun (RG-BULL-03)."""
    if moyenne >= 18.0:
        return "Excellent"
    elif moyenne >= 16.0:
        return "Très Bien"
    elif moyenne >= 14.0:
        return "Bien"
    elif moyenne >= 12.0:
        return "Assez Bien"
    elif moyenne >= 10.0:
        return "Passable"
    elif moyenne >= 8.0:
        return "Insuffisant"
    else:
        return "Médiocre / Faible"

def calculate_sequence_bulletins(db: Session, ecole_id: int, classe_id: int, sequence: int) -> Dict[str, Any]:
    """
    Moteur officiel de calcul des bulletins séquentiels MINESEC (RG-BULL-01 & RG-BULL-02).
    - Calcule Note x Coeff par matière
    - Calcule la moyenne séquentielle pondérée Ms
    - Calcule le classement avec ex æquo officiel
    - Calcule les moyennes Min, Max et Générale de la classe
    - Regroupe les matières par Groupes I (Sciences), II (Lettres), III (Divers)
    """
    school = db.query(School).filter(School.id == ecole_id).first()
    classroom = db.query(Classroom).filter(Classroom.id == classe_id).first()
    if not classroom:
        raise ValueError("Classe introuvable.")

    students = db.query(Student).filter(Student.classe_id == classe_id).all()
    assignments = db.query(TeacherAssignment).filter(
        TeacherAssignment.classe_id == classe_id,
        TeacherAssignment.statut == "valide"
    ).all()

    # Si aucune affectation validée, prendre toutes les affectations actives pour test
    if not assignments:
        assignments = db.query(TeacherAssignment).filter(TeacherAssignment.classe_id == classe_id).all()

    # Préparer les données par élève
    student_results = []

    for student in students:
        total_points = 0.0
        total_coefs = 0.0
        
        groupes = {
            "I_SCIENTIFIQUE": {"titre": "GROUPE I : MATIÈRES SCIENTIFIQUES & TECHNOLOGIQUES", "matieres": [], "points": 0.0, "coefs": 0.0},
            "II_LITTERAIRE": {"titre": "GROUPE II : MATIÈRES LITTÉRAIRES & LANGUES", "matieres": [], "points": 0.0, "coefs": 0.0},
            "III_DIVERS": {"titre": "GROUPE III : DÉVELOPPEMENT PERSONNEL & DIVERS", "matieres": [], "points": 0.0, "coefs": 0.0}
        }

        for aff in assignments:
            subj = aff.subject
            if not subj:
                continue

            # Chercher la note
            grade_rec = db.query(Grade).filter(
                Grade.eleve_id == student.id,
                Grade.affectation_id == aff.id,
                Grade.sequence == sequence
            ).first()

            coeff = aff.coeff_valide or aff.coeff_propose or 1
            
            if grade_rec and grade_rec.est_absent:
                note = 0.0
                pts = 0.0
                mention = "ABS"
            elif grade_rec and grade_rec.note_sur_20 is not None:
                note = round(grade_rec.note_sur_20, 2)
                pts = round(note * coeff, 2)
                mention = get_minesec_appreciation(note)
            else:
                # Pas de note enregistrée
                note = 0.0
                pts = 0.0
                mention = "Non noté"

            total_points += pts
            total_coefs += coeff

            target_grp = subj.groupe if subj.groupe in groupes else "III_DIVERS"
            groupes[target_grp]["matieres"].append({
                "nom": subj.nom,
                "code": subj.code,
                "prof": aff.teacher.nom_complet if aff.teacher else "Enseignant",
                "coeff": coeff,
                "note": note,
                "points": pts,
                "appreciation": mention
            })
            groupes[target_grp]["points"] += pts
            groupes[target_grp]["coefs"] += coeff

        # Calcul moyenne des groupes
        for grp in groupes.values():
            grp["moyenne"] = round(grp["points"] / grp["coefs"], 2) if grp["coefs"] > 0 else 0.0

        moyenne_seq = round(total_points / total_coefs, 2) if total_coefs > 0 else 0.0

        student_results.append({
            "student": {
                "id": student.id,
                "nom": student.nom,
                "prenom": student.prenom,
                "matricule": student.matricule,
                "date_naissance": student.date_naissance,
                "sexe": student.sexe,
                "parent_phone": student.parent_phone or ""
            },
            "total_points": round(total_points, 2),
            "total_coefs": int(total_coefs),
            "moyenne": moyenne_seq,
            "appreciation": get_minesec_appreciation(moyenne_seq),
            "groupes": groupes
        })

    # Algorithme officiel de classement avec gestion stricte des ex æquo (RG-BULL-02)
    student_results.sort(key=lambda x: x["moyenne"], reverse=True)

    current_rank = 1
    for idx, item in enumerate(student_results):
        if idx > 0 and item["moyenne"] == student_results[idx - 1]["moyenne"]:
            # Même moyenne -> ex æquo
            item["rang"] = student_results[idx - 1]["rang"]
            item["ex_aequo"] = True
            student_results[idx - 1]["ex_aequo"] = True
        else:
            item["rang"] = idx + 1
            item["ex_aequo"] = False

    # Statistiques globales de la classe
    all_moyennes = [r["moyenne"] for r in student_results] if student_results else [0.0]
    moy_min = min(all_moyennes) if all_moyennes else 0.0
    moy_max = max(all_moyennes) if all_moyennes else 0.0
    moy_gen = round(sum(all_moyennes) / len(all_moyennes), 2) if all_moyennes else 0.0
    admis = sum(1 for m in all_moyennes if m >= 10.0)
    taux_reussite = round((admis / len(all_moyennes)) * 100, 1) if all_moyennes else 0.0

    return {
        "ecole": {
            "nom": school.name if school else "Établissement Scolaire",
            "code": school.code if school else "ED237",
            "ville": school.ville if school else "Douala",
            "contact": school.contact_phone if school else "+237",
            "logo_url": school.logo_url if school else None
        },
        "classe": {
            "id": classroom.id,
            "nom": classroom.nom,
            "annee": classroom.annee_scolaire,
            "effectif": len(student_results)
        },
        "sequence": sequence,
        "stats": {
            "moyenne_generale": moy_gen,
            "moyenne_max": moy_max,
            "moyenne_min": moy_min,
            "taux_reussite": taux_reussite
        },
        "bulletins": student_results
    }
