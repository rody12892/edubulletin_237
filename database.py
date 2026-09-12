import os
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, func, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from contextlib import contextmanager
from typing import Generator

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "edubulletin.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

# Activation du mode WAL pour SQLite
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODÈLES SQLALCHEMY MULTI-TENANT ---

class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    contact = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    students = relationship("Student", back_populates="school", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="school", cascade="all, delete-orphan")

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ecole_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    matricule = Column(String(50), nullable=False, index=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    classe = Column(String(50), nullable=False, index=True)
    parent_phone = Column(String(30), nullable=True, default="")
    created_at = Column(DateTime, server_default=func.now())

    school = relationship("School", back_populates="students")
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ecole_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    nom = Column(String(100), nullable=False)
    code = Column(String(20), nullable=True)

    school = relationship("School", back_populates="subjects")
    grades = relationship("Grade", back_populates="subject", cascade="all, delete-orphan")

class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False) # 1 à 6
    note = Column(Float, nullable=False, default=0.0)
    coefficient = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, server_default=func.now())

    student = relationship("Student", back_populates="grades")
    subject = relationship("Subject", back_populates="grades")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(30), nullable=False, default="PENDING")
    reference = Column(String(100), unique=True, nullable=False, index=True)
    phone_number = Column(String(30), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


def init_db() -> None:
    """Initialise le schéma de la base de données et peuple les données par défaut si vide."""
    Base.metadata.create_all(bind=engine)
    
    with SessionLocal() as db:
        if db.query(School).count() == 0:
            default_school = School(name="Collège Bilingue de l'Excellence 237", contact="+237690000000")
            db.add(default_school)
            db.commit()
            db.refresh(default_school)

            # Matières standard MINESEC
            matieres = ["Mathématiques", "Français", "Anglais", "Physique-Chimie", "SVT", "Histoire-Géo"]
            for m in matieres:
                db.add(Subject(ecole_id=default_school.id, nom=m, code=m[:4].upper()))
            
            # Élèves de démo
            s1 = Student(ecole_id=default_school.id, matricule="237-0014", nom="ABANDA", prenom="Jean", classe="3ème A", parent_phone="+237699112233")
            s2 = Student(ecole_id=default_school.id, matricule="237-0015", nom="BILO'O", prenom="Marie", classe="3ème A", parent_phone="+237677445566")
            db.add_all([s1, s2])
            db.commit()

def get_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI fournissant une session SQLAlchemy."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    print("Base de données EDUBULLETIN 237 initialisée avec succès.")
