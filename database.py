import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

DB_PATH = "edubulletin.db"

@contextmanager
def get_db_connection():
    """
    Gestionnaire de contexte pour la connexion SQLite.
    Active le mode WAL et l'intégrité référentielle (Foreign Keys).
    Utilise sqlite3.Row pour un accès par dictionnaire.
    """
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
    finally:
        conn.close()

def init_db() -> None:
    """
    Initialise la base de données et crée les tables nécessaires pour le SaaS multi-tenant.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS schools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL,
                matricule TEXT NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                parent_phone TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE,
                UNIQUE(school_id, matricule)
            );

            CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                seq1 REAL DEFAULT 0.0,
                seq2 REAL DEFAULT 0.0,
                seq3 REAL DEFAULT 0.0,
                seq4 REAL DEFAULT 0.0,
                seq5 REAL DEFAULT 0.0,
                seq6 REAL DEFAULT 0.0,
                average REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
                UNIQUE(student_id, subject)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                reference TEXT NOT NULL UNIQUE,
                phone_number TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (school_id) REFERENCES schools (id) ON DELETE CASCADE
            );
        """)
        conn.commit()

# --- CRUD SCHOOLS (TENANTS) ---

def create_school(name: str, contact: str) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO schools (name, contact) VALUES (?, ?)",
            (name, contact)
        )
        conn.commit()
        return cursor.lastrowid

def get_school(school_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM schools WHERE id = ?", (school_id,)).fetchone()
        return dict(row) if row else None

def get_all_schools() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM schools ORDER BY name ASC").fetchall()
        return [dict(row) for row in rows]

# --- CRUD STUDENTS ---

def create_student(school_id: int, matricule: str, first_name: str, last_name: str, class_name: str, parent_phone: str) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO students (school_id, matricule, first_name, last_name, class_name, parent_phone)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (school_id, matricule, first_name, last_name, class_name, parent_phone))
        conn.commit()
        return cursor.lastrowid

def get_students_by_school(school_id: int) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM students WHERE school_id = ? ORDER BY class_name ASC, last_name ASC",
            (school_id,)
        ).fetchall()
        return [dict(row) for row in rows]

def get_student(student_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        return dict(row) if row else None

# --- CRUD GRADES ---

def add_or_update_grade(student_id: int, subject: str, seq1: float = 0.0, seq2: float = 0.0, seq3: float = 0.0, seq4: float = 0.0, seq5: float = 0.0, seq6: float = 0.0) -> int:
    average = round((seq1 + seq2 + seq3 + seq4 + seq5 + seq6) / 6.0, 2)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO grades (student_id, subject, seq1, seq2, seq3, seq4, seq5, seq6, average)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id, subject) DO UPDATE SET
                seq1=excluded.seq1,
                seq2=excluded.seq2,
                seq3=excluded.seq3,
                seq4=excluded.seq4,
                seq5=excluded.seq5,
                seq6=excluded.seq6,
                average=excluded.average,
                created_at=CURRENT_TIMESTAMP
        """, (student_id, subject, seq1, seq2, seq3, seq4, seq5, seq6, average))
        conn.commit()
        return cursor.lastrowid

def get_student_report_card(student_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        student_row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if not student_row:
            return None
        
        grades_rows = conn.execute("SELECT * FROM grades WHERE student_id = ? ORDER BY subject ASC", (student_id,)).fetchall()
        
        student_data = dict(student_row)
        student_data['grades'] = [dict(row) for row in grades_rows]
        
        if student_data['grades']:
            total_avg = sum(g['average'] for g in student_data['grades']) / len(student_data['grades'])
            student_data['general_average'] = round(total_avg, 2)
        else:
            student_data['general_average'] = 0.0
            
        return student_data

# --- CRUD TRANSACTIONS (MOBILE MONEY) ---

def create_transaction(school_id: int, amount: float, reference: str, phone_number: str) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions (school_id, amount, reference, phone_number)
            VALUES (?, ?, ?, ?)
        """, (school_id, amount, reference, phone_number))
        conn.commit()
        return cursor.lastrowid

def update_transaction_status(reference: str, status: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE transactions
            SET status = ?
            WHERE reference = ?
        """, (status, reference))
        conn.commit()
        return cursor.rowcount > 0

def get_school_transactions(school_id: int) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE school_id = ? ORDER BY created_at DESC",
            (school_id,)
        ).fetchall()
        return [dict(row) for row in rows]

if __name__ == "__main__":
    init_db()