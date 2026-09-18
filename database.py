import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Generator, List, Dict, Any, Optional

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, 
    ForeignKey, DateTime, Text, func, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session, synonym
from sqlalchemy import event

raw_db_url = os.getenv("DATABASE_URL", "").strip()

# Détection environnement Serverless (Vercel ou AWS Lambda ou système en lecture seule)
is_serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or not os.access(".", os.W_OK))

if not raw_db_url or raw_db_url in ["sqlite://local.db", "sqlite://edubulletin.db", "sqlite:///./edubulletin.db"]:
    if is_serverless:
        db_path = Path("/tmp/edubulletin.db")
        DATABASE_URL = f"sqlite:///{db_path}"
    else:
        DATABASE_URL = "sqlite:///./edubulletin.db"
elif raw_db_url.startswith("sqlite://") and not raw_db_url.startswith("sqlite:///"):
    DATABASE_URL = raw_db_url.replace("sqlite://", "sqlite:///", 1)
else:
    DATABASE_URL = raw_db_url

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
except Exception:
    # Repli de secours absolu en mémoire
    engine = create_engine("sqlite:///:memory:", connect_args=connect_args, echo=False)

if "sqlite" in DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()
        except Exception:
            pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==============================================================================
# SCHÉMA MULTI-TENANT CONFORME AU CAHIER DES CHARGES
# ==============================================================================

class School(Base):
    """Établissement scolaire (Tenant)."""
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(10), nullable=False, default="ED237")
    ville = Column(String(100), default="Douala")
    contact_phone = Column(String(50), nullable=False)
    contact_email = Column(String(150), nullable=False)
    logo_url = Column(Text, nullable=True)
    
    # Abonnements & Licences
    statut_licence = Column(String(20), default="actif")
    date_fin_licence = Column(DateTime, nullable=False)
    pack_actuel = Column(String(50), default="demarrage")
    classes_max = Column(Integer, default=6)
    
    created_at = Column(DateTime, server_default=func.now())

    # Relations
    users = relationship("User", back_populates="school", cascade="all, delete-orphan")
    classes = relationship("Classroom", back_populates="school", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="school", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="school", cascade="all, delete-orphan")

    @property
    def nom(self):
        return self.name

    @nom.setter
    def nom(self, val):
        self.name = val

    @property
    def telephone(self):
        return self.contact_phone

    @property
    def adresse(self):
        return self.ville

    @property
    def annee_scolaire(self):
        return "2025-2026"


class User(Base):
    """Utilisateurs du système avec RBAC strict."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ecole_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    nom_complet = Column(String(255), nullable=False)
    identifiant = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False)
    statut = Column(String(20), default="actif")
    matiere_souhaitee = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    @property
    def email(self):
        return self.identifiant

    @property
    def telephone(self):
        return self.identifiant

    @property
    def mot_de_passe_hash(self):
        return self.password_hash

    @mot_de_passe_hash.setter
    def mot_de_passe_hash(self, val):
        self.password_hash = val

    @property
    def est_actif(self):
        return self.statut == "actif"

    school = relationship("School", back_populates="users")
    assignments = relationship("TeacherAssignment", back_populates="teacher", cascade="all, delete-orphan")


class Classroom(Base):
    """Classe d'un établissement."""
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ecole_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    nom = Column(String(50), nullable=False)
    annee_scolaire = Column(String(20), default="2025-2026")
    created_at = Column(DateTime, server_default=func.now())

    school = relationship("School", back_populates="classes")
    students = relationship("Student", back_populates="classroom", cascade="all, delete-orphan")
    assignments = relationship("TeacherAssignment", back_populates="classroom", cascade="all, delete-orphan")
    publications = relationship("SequencePublication", back_populates="classroom", cascade="all, delete-orphan")


class Subject(Base):
    """Matière enseignée rattachée à un groupe officiel MINESEC."""
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ecole_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    nom = Column(String(100), nullable=False)
    code = Column(String(20), nullable=False)
    groupe = Column(String(50), default="I_SCIENTIFIQUE")
    created_at = Column(DateTime, server_default=func.now())

    school = relationship("School", back_populates="subjects")
    assignments = relationship("TeacherAssignment", back_populates="subject", cascade="all, delete-orphan")


class TeacherAssignment(Base):
    """Affectation d'un professeur à une matière et une classe avec coefficient."""
    __tablename__ = "affectations_prof"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    utilisateur_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    enseignant_id = synonym("utilisateur_id")
    classe_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    matiere_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    coeff_propose = Column(Integer, nullable=False, default=2)
    coeff_valide = Column(Integer, nullable=True)
    statut = Column(String(20), default="attente")
    motif_rejet = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    teacher = relationship("User", back_populates="assignments")
    classroom = relationship("Classroom", back_populates="assignments")
    subject = relationship("Subject", back_populates="assignments")
    grades = relationship("Grade", back_populates="assignment", cascade="all, delete-orphan")


class Student(Base):
    """Élève inscrit."""
    __tablename__ = "eleves"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ecole_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    classe_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    matricule = Column(String(50), unique=True, nullable=False, index=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    date_naissance = Column(String(20), nullable=False)
    sexe = Column(String(1), default="M")
    parent_phone = Column(String(30), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    school = relationship("School", back_populates="students")
    classroom = relationship("Classroom", back_populates="students")
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")


class Grade(Base):
    """Note séquentielle d'un élève."""
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    eleve_id = Column(Integer, ForeignKey("eleves.id", ondelete="CASCADE"), nullable=False, index=True)
    affectation_id = Column(Integer, ForeignKey("affectations_prof.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    note_sur_20 = Column(Float, nullable=True)
    est_absent = Column(Boolean, default=False)
    statut = Column(String(20), default="brouillon")
    motif_rejet = Column(Text, nullable=True)
    date_maj = Column(DateTime, server_default=func.now(), onupdate=func.now())

    student = relationship("Student", back_populates="grades")
    assignment = relationship("TeacherAssignment", back_populates="grades")


class SequencePublication(Base):
    """Suivi de publication des séquences pour le portail parents."""
    __tablename__ = "sequence_publications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ecole_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    classe_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    est_publie = Column(Boolean, default=False)
    date_publication = Column(DateTime, nullable=True)

    classroom = relationship("Classroom", back_populates="publications")


class SubscriptionTransaction(Base):
    """Historique des transactions Mobile Money."""
    __tablename__ = "transactions_abonnement"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ecole_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    pack = Column(String(50), nullable=False)
    montant = Column(Float, nullable=False)
    reference = Column(String(100), unique=True, nullable=False, index=True)
    transaction_id = Column(String(100), nullable=True)
    statut = Column(String(30), default="PENDING")
    devise = Column(String(10), default="XAF")
    operateur = Column(String(50), nullable=True)
    phone = Column(String(30), nullable=True)
    nom_payeur = Column(String(150), nullable=True)
    telephone_payeur = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ==============================================================================
# SEEDING DE DÉMONSTRATION RÉALISTE POUR LE SYSTÈME MINESEC
# ==============================================================================

def hash_pw(password: str) -> str:
    import hashlib
    salt = "237_EDUBULLETIN_SALT_2026"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def verify_pw(password: str, hashed: str) -> bool:
    return hash_pw(password) == hashed

def init_db() -> None:
    """Crée les tables et initialise les données de démarrage complètes."""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[AVERTISSEMENT] create_all non bloquant: {e}", file=sys.stderr)

    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN statut VARCHAR(20) DEFAULT 'actif';"))
            conn.commit()
    except Exception:
        pass

    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN matiere_souhaitee VARCHAR(100);"))
            conn.commit()
    except Exception:
        pass

    try:
        with SessionLocal() as db:
            if db.query(School).count() == 0:
                print("[INFO] Initialisation des donnees initiales MINESEC EDUBULLETIN 237...")
                school = School(
                    name="Lycée Bilingue d'Excellence de Douala",
                    slug="lycee-excellence-douala",
                    code="LED",
                    ville="Douala (Akwa-Nord)",
                    contact_phone="+237699001122",
                    contact_email="proviseur@lycee-excellence.cm",
                    statut_licence="actif",
                    date_fin_licence=datetime.utcnow() + timedelta(days=365),
                    pack_actuel="standard",
                    classes_max=15
                )
                db.add(school)
                db.commit()
                db.refresh(school)

                superadmin = User(
                    ecole_id=None,
                    nom_complet="Kaplo SuperAdmin",
                    identifiant="admin@edubulletin237.cm",
                    password_hash=hash_pw("Admin237!"),
                    role="superadmin"
                )
                proviseur = User(
                    ecole_id=school.id,
                    nom_complet="Dr. ETOUNDI Joseph (Proviseur)",
                    identifiant="+237699001122",
                    password_hash=hash_pw("Proviseur2026"),
                    role="proviseur"
                )
                secretaire = User(
                    ecole_id=school.id,
                    nom_complet="Mme NGUEMENI Carine (Secrétariat)",
                    identifiant="+237677112233",
                    password_hash=hash_pw("Secretaire2026"),
                    role="secretaire"
                )
                prof_math = User(
                    ecole_id=school.id,
                    nom_complet="M. KAMGA Paul (Professeur Mathématiques)",
                    identifiant="+237690112233",
                    password_hash=hash_pw("Prof2026"),
                    role="professeur"
                )
                prof_fr = User(
                    ecole_id=school.id,
                    nom_complet="Mme BIHINA Rosine (Professeur Français)",
                    identifiant="+237655443322",
                    password_hash=hash_pw("Prof2026"),
                    role="professeur"
                )
                db.add_all([superadmin, proviseur, secretaire, prof_math, prof_fr])
                db.commit()
                db.refresh(prof_math)
                db.refresh(prof_fr)

                c_6a = Classroom(ecole_id=school.id, nom="6ème A", annee_scolaire="2025-2026")
                c_3b = Classroom(ecole_id=school.id, nom="3ème B (Allemand)", annee_scolaire="2025-2026")
                c_tle = Classroom(ecole_id=school.id, nom="Terminale C", annee_scolaire="2025-2026")
                db.add_all([c_6a, c_3b, c_tle])
                db.commit()
                db.refresh(c_3b)

                matieres_def = [
                    ("Mathématiques", "MATH", "I_SCIENTIFIQUE"),
                    ("Physique-Chimie", "PHY", "I_SCIENTIFIQUE"),
                    ("Sciences de la Vie et de la Terre", "SVT", "I_SCIENTIFIQUE"),
                    ("Informatique", "INFO", "I_SCIENTIFIQUE"),
                    ("Français", "FRAN", "II_LITTERAIRE"),
                    ("Anglais", "ANGL", "II_LITTERAIRE"),
                    ("Littérature", "LITT", "II_LITTERAIRE"),
                    ("Allemand", "ALL", "II_LITTERAIRE"),
                    ("Histoire-Géographie", "HG", "III_DIVERS"),
                    ("Éducation à la Citoyenneté (ECM)", "ECM", "III_DIVERS"),
                    ("Éducation Physique et Sportive (EPS)", "EPS", "III_DIVERS"),
                    ("Travail Manuel", "TM", "III_DIVERS"),
                ]
                saved_subjects = {}
                for nom, code, grp in matieres_def:
                    s = Subject(ecole_id=school.id, nom=nom, code=code, groupe=grp)
                    db.add(s)
                    db.commit()
                    db.refresh(s)
                    saved_subjects[code] = s

                aff_math = TeacherAssignment(
                    utilisateur_id=prof_math.id,
                    classe_id=c_3b.id,
                    matiere_id=saved_subjects["MATH"].id,
                    coeff_propose=4,
                    coeff_valide=4,
                    statut="valide"
                )
                aff_fr = TeacherAssignment(
                    utilisateur_id=prof_fr.id,
                    classe_id=c_3b.id,
                    matiere_id=saved_subjects["FRAN"].id,
                    coeff_propose=5,
                    coeff_valide=5,
                    statut="valide"
                )
                db.add_all([aff_math, aff_fr])
                db.commit()
                db.refresh(aff_math)
                db.refresh(aff_fr)

                eleves_def = [
                    ("LED260001", "ABANDA", "Jean-Pierre", "14/03/2010", "M", "+237699112233"),
                    ("LED260002", "BILO'O", "Marie-Claire", "02/07/2010", "F", "+237677445566"),
                    ("LED260003", "DJOMO", "Christian", "19/11/2009", "M", "+237694556677"),
                    ("LED260004", "FOTSO", "Kévine Audrey", "25/05/2010", "F", "+237651223344"),
                    ("LED260005", "MBARGA", "Alain Stéphane", "10/01/2010", "M", "+237678990011")
                ]
                saved_students = []
                for mat, nom, prenom, dnaiss, sexe, parent in eleves_def:
                    el = Student(
                        ecole_id=school.id,
                        classe_id=c_3b.id,
                        matricule=mat,
                        nom=nom,
                        prenom=prenom,
                        date_naissance=dnaiss,
                        sexe=sexe,
                        parent_phone=parent
                    )
                    db.add(el)
                    db.commit()
                    db.refresh(el)
                    saved_students.append(el)

                notes_math = [16.5, 14.0, 11.5, 8.0, 17.5]
                for idx, el in enumerate(saved_students):
                    g = Grade(
                        eleve_id=el.id,
                        affectation_id=aff_math.id,
                        sequence=1,
                        note_sur_20=notes_math[idx],
                        est_absent=False,
                        statut="valide"
                    )
                    db.add(g)

                notes_fr = [15.0, 16.5, 9.5, 12.0, 14.5]
                for idx, el in enumerate(saved_students):
                    g = Grade(
                        eleve_id=el.id,
                        affectation_id=aff_fr.id,
                        sequence=1,
                        note_sur_20=notes_fr[idx],
                        est_absent=False,
                        statut="valide"
                    )
                    db.add(g)

                pub1 = SequencePublication(
                    ecole_id=school.id,
                    classe_id=c_3b.id,
                    sequence=1,
                    est_publie=True,
                    date_publication=datetime.utcnow()
                )
                db.add(pub1)
                db.commit()
                print("[OK] Base de données initialisée.")
    except Exception as err:
        print(f"[AVERTISSEMENT] Erreur seed: {err}", file=sys.stderr)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
