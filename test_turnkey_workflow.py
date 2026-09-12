import sys
from fastapi.testclient import TestClient

from app import app
from database import get_db, User, School, Classroom, Subject, TeacherAssignment

client = TestClient(app, follow_redirects=False)

def run_tests():
    print("=== STARTING TURNKEY SAAS WORKFLOW TEST SUITE ===")

    # 1. Vérifier la page d'inscription enseignant
    res = client.get("/inscription-prof")
    assert res.status_code == 200, f"Expected 200 on /inscription-prof, got {res.status_code}"
    print("[TEST 1/8] GET /inscription-prof -> 200 OK")

    # 2. Inscription d'un nouveau professeur (qui doit être placé en_attente)
    test_phone = "+237699998877"
    signup_data = {
        "ecole_id": 1,
        "nom_complet": "M. TCHOUANKEU Marcel (Test)",
        "identifiant": test_phone,
        "matiere_souhaitee": "Physique-Chimie",
        "mot_de_passe": "TestProf2026"
    }
    # Nettoyage préalable si existe
    with next(get_db()) as db:
        old_u = db.query(User).filter(User.identifiant == test_phone).first()
        if old_u:
            db.delete(old_u)
            db.commit()

    res = client.post("/inscription-prof", data=signup_data)
    assert res.status_code == 302, f"Expected 302 redirect, got {res.status_code}"
    assert "/prof/en-attente" in res.headers["location"]
    print("[TEST 2/8] POST /inscription-prof -> 302 Redirect to /prof/en-attente")

    # 3. Vérifier la page de statut d'attente
    res = client.get(res.headers["location"])
    assert res.status_code == 200
    assert "Demande transmise au Proviseur" in res.text
    print("[TEST 3/8] GET /prof/en-attente -> 200 OK (Explication claire affichée)")

    # 4. Tentative de connexion par le professeur non encore approuvé
    res = client.post("/login", data={"identifiant": test_phone, "password": "TestProf2026"})
    assert res.status_code == 302
    assert "/prof/en-attente" in res.headers["location"]
    print("[TEST 4/8] POST /login (Prof en attente) -> Interception et redirection vers /prof/en-attente")

    # 5. Connexion Proviseur et consultation de /admin/enseignants
    client_prov = TestClient(app)
    res_login = client_prov.get("/demo/proviseur")
    assert res_login.status_code == 200
    res_ens = client_prov.get("/admin/enseignants")
    assert res_ens.status_code == 200
    assert "TCHOUANKEU Marcel" in res_ens.text
    print("[TEST 5/8] Proviseur -> GET /admin/enseignants -> 200 OK (Demande visible avec badge)")

    # 6. Approbation par le Proviseur avec affectation classe + matière
    with next(get_db()) as db:
        new_prof = db.query(User).filter(User.identifiant == test_phone).first()
        prof_id = new_prof.id
        classe = db.query(Classroom).first()
        subject = db.query(Subject).filter(Subject.code == "PHY").first() or db.query(Subject).first()

    res_approuver = client_prov.post("/api/admin/approuver-prof", data={
        "prof_id": prof_id,
        "classe_id": classe.id,
        "matiere_id": subject.id,
        "coeff": 3
    })
    assert res_approuver.status_code == 200
    res_json = res_approuver.json()
    assert res_json["success"] is True
    print(f"[TEST 6/8] POST /api/admin/approuver-prof -> {res_json['message']}")

    # 7. Connexion réussie du Professeur désormais approuvé
    client_prof = TestClient(app)
    res_login_prof = client_prof.post("/login", data={"identifiant": test_phone, "password": "TestProf2026"}, follow_redirects=True)
    assert res_login_prof.status_code == 200
    assert "/prof/classes" in str(res_login_prof.url)
    print("[TEST 7/8] Connexion du Professeur approuvé -> Accès direct accordé à /prof/classes 200 OK")

    # 8. Impression groupée des bulletins de toute la classe
    with next(get_db()) as db:
        classe_with_students = db.query(Classroom).filter(Classroom.nom.contains("3ème")).first() or classe
    res_classe_print = client_prov.get(f"/bulletin/print/classe/{classe_with_students.id}/1")
    assert res_classe_print.status_code == 200
    assert "Impression Groupée" in res_classe_print.text
    assert "bulletin-container page-break" in res_classe_print.text
    print(f"[TEST 8/8] GET /bulletin/print/classe/{classe_with_students.id}/1 -> 200 OK (Multi-bulletins A4 avec page-break prêts)")

    print("\n=======================================================")
    print(">>> TOUS LES TESTS DE WORKFLOW SONT VALIDES A 100% ! <<<")
    print("=======================================================")

if __name__ == "__main__":
    run_tests()
