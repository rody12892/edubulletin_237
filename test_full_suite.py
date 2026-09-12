import os
import sys
import unittest
from fastapi.testclient import TestClient
from database import get_db, init_db, SessionLocal, School, User, Student, Classroom, Grade
from app import app
from payment_monetbil import monetbil_client, PACKS_CONFIG
from services.bulletin_engine import calculate_sequence_bulletins
from services.excel_importer import generate_next_matricule

client = TestClient(app)

class TestEduBulletinSaaS(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_health_check(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["app"], "EDUBULLETIN 237")
        print("[TEST] Health check OK")

    def test_02_login_proviseur(self):
        payload = {
            "identifiant": "+237699001122",
            "mot_de_passe": "Proviseur2026"
        }
        response = client.post("/api/auth/login", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["role"], "proviseur")
        self.assertEqual(data["redirect_url"], "/admin/dashboard")
        print("[TEST] Login Proviseur OK (token generated & cookie set)")

    def test_03_login_professeur(self):
        payload = {
            "identifiant": "+237690112233",
            "mot_de_passe": "Prof2026"
        }
        response = client.post("/api/auth/login", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["role"], "professeur")
        self.assertEqual(data["redirect_url"], "/prof/classes")
        print("[TEST] Login Professeur OK")

    def test_04_login_superadmin(self):
        payload = {
            "identifiant": "admin@edubulletin237.cm",
            "mot_de_passe": "Admin237!"
        }
        response = client.post("/api/auth/login", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["role"], "superadmin")
        self.assertEqual(data["redirect_url"], "/superadmin/overview")
        print("[TEST] Login Super Admin OK")

    def test_05_minesec_bulletin_calculation(self):
        db = SessionLocal()
        try:
            school = db.query(School).filter(School.code == "LED").first()
            self.assertIsNotNone(school)
            classe = db.query(Classroom).filter(Classroom.nom.like("%3ème B%")).first()
            self.assertIsNotNone(classe)

            res = calculate_sequence_bulletins(db, school.id, classe.id, 1)
            self.assertIn("bulletins", res)
            self.assertIn("stats", res)
            self.assertGreater(len(res["bulletins"]), 0)
            
            # Check ex-æquo and ranks
            for b in res["bulletins"]:
                self.assertIn("rang", b)
                self.assertIn("moyenne", b)
                self.assertIn("groupes", b)
                self.assertIn("I_SCIENTIFIQUE", b["groupes"])
                self.assertIn("II_LITTERAIRE", b["groupes"])
                self.assertIn("III_DIVERS", b["groupes"])
            
            print(f"[TEST] Calcul MINESEC 3ème B: {len(res['bulletins'])} élèves, Moy Générale = {res['stats']['moyenne_generale']}/20")
        finally:
            db.close()

    def test_06_matricule_generator(self):
        db = SessionLocal()
        try:
            school = db.query(School).filter(School.code == "LED").first()
            mat = generate_next_matricule(db, school)
            self.assertTrue(mat.startswith("LED"))
            print(f"[TEST] Générateur automatique matricule: {mat}")
        finally:
            db.close()

    def test_07_monetbil_widget_generation(self):
        res = monetbil_client.create_payment_widget(
            amount=75000.0,
            payment_ref="TEST-ED237-001",
            item_ref="Pack Démarrage",
            phone="+237690000000"
        )
        self.assertTrue(res.get("success"))
        self.assertIn("payment_url", res)
        print(f"[TEST] Monetbil Widget v2.1 URL: {res['payment_url']}")

    def test_08_monetbil_webhook_simulation(self):
        # Créer d'abord une transaction fictive pour tester le webhook
        import uuid
        db = SessionLocal()
        from database import SubscriptionTransaction
        test_ref = f"TEST-REF-WEBHOOK-{uuid.uuid4().hex[:8]}"
        school = db.query(School).filter(School.code == "LED").first()
        school_id = school.id
        tx = SubscriptionTransaction(
            ecole_id=school_id,
            reference=test_ref,
            pack="standard",
            montant=150000.0,
            devise="XAF",
            statut="en_attente"
        )
        db.add(tx)
        db.commit()
        db.close()

        # Envoi de la notification Webhook
        webhook_payload = {
            "status": "success",
            "payment_ref": test_ref,
            "transaction_id": "MNTB-TX-998877",
            "amount": 150000
        }
        resp = client.post("/api/v1/webhooks/monetbil", json=webhook_payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "ok")

        # Vérifier que la transaction est passée à 'succes' et la licence prolongée
        db2 = SessionLocal()
        tx_check = db2.query(SubscriptionTransaction).filter(SubscriptionTransaction.reference == test_ref).first()
        self.assertEqual(tx_check.statut, "succes")
        school_check = db2.query(School).filter(School.id == school_id).first()
        self.assertEqual(school_check.statut_licence, "actif")
        db2.close()
        print("[TEST] Webhook Monetbil & Prolongation automatique de licence OK")

    def test_09_bulletin_printable_html(self):
        db = SessionLocal()
        student = db.query(Student).first()
        self.assertIsNotNone(student)
        db.close()

        resp = client.get(f"/bulletin/print/{student.id}/1")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("RÉPUBLIQUE DU CAMEROUN", resp.text)
        self.assertIn("BULLETIN DE NOTES OFFICIEL", resp.text)
        self.assertIn("SÉQUENCE 1", resp.text)
        print(f"[TEST] Bulletin officiel imprimable A4 généré avec succès pour élève #{student.id}")

if __name__ == "__main__":
    unittest.main()
