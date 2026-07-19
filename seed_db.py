"""
סקריפט הזרקת נתונים.
1. בונה קטלוג של כ-500 תרגילים (exercise_catalog_generator) וכותב אותו ל-data/exercises.json.
2. מזריק את התרגילים לטבלת exercises ב-SQLite (אם עדיין ריקה).
3. יוצר כמה תוכניות (Program) לדוגמה - כדי להדגים כמה נושאי-גג/חוקים במקביל.
4. יוצר משתמשות ברירת מחדל: מנהלת ומאמנת.

הרצה (לאחר שינוי סכמה, יש למחוק קודם את gym.db):
    python seed_db.py
"""
import json
from pathlib import Path

from database import Exercise, Program, User, init_db, get_session
from exercise_catalog_generator import build_catalog

DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "exercises.json"

DEFAULT_PROGRAMS = [
    {
        "name": "תוכנית יולי 2026 - גו",
        "month_theme": "גו",
        "theme_percentage": 80,
        "mandatory_note": "כל אימון מסתיים ב-2 דקות פלאנק",
        "mandatory_exercise_name": "פלאנק",
        "mandatory_duration_seconds": 120,
    },
    {
        "name": "תוכנית לדוגמה - רגליים",
        "month_theme": "רגליים",
        "theme_percentage": 70,
        "mandatory_note": "כל אימון כולל 3 דקות מתיחות רגליים בסיום",
        "mandatory_exercise_name": "מתיחת המסטרינגס בישיבה",
        "mandatory_duration_seconds": 180,
    },
]

# משתמשות ברירת מחדל להתחברות ראשונית. יש להחליף סיסמאות אלו בסביבת אמת.
DEFAULT_USERS = [
    {"username": "manager", "password": "admin123", "display_name": "מנהלת הסטודיו", "role": "מנהלת"},
    {"username": "trainer1", "password": "trainer123", "display_name": "מאמנת לדוגמה", "role": "מאמנת"},
]


def write_json_file() -> list[dict]:
    DATA_DIR.mkdir(exist_ok=True)
    catalog = build_catalog()
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    print(f"נכתבו {len(catalog)} תרגילים אל {DATA_FILE}")
    return catalog


def seed_database(catalog: list[dict]) -> None:
    init_db()
    session = get_session()
    try:
        existing_count = session.query(Exercise).count()
        if existing_count > 0:
            print(f"המאגר כבר מכיל {existing_count} תרגילים - מדלג על הזרקה כפולה.")
        else:
            for item in catalog:
                session.add(Exercise(**item))
            session.commit()
            print(f"הוזרקו {len(catalog)} תרגילים ל-DB בהצלחה.")

        if session.query(Program).count() == 0:
            for prog in DEFAULT_PROGRAMS:
                session.add(Program(**prog))
            session.commit()
            print(f"נוצרו {len(DEFAULT_PROGRAMS)} תוכניות לדוגמה.")

        if session.query(User).count() == 0:
            for u in DEFAULT_USERS:
                user = User(username=u["username"], display_name=u["display_name"], role=u["role"])
                user.set_password(u["password"])
                session.add(user)
            session.commit()
            print("נוצרו משתמשות ברירת מחדל:")
            for u in DEFAULT_USERS:
                print(f"  - {u['role']}: שם משתמש '{u['username']}' / סיסמה '{u['password']}'")
    finally:
        session.close()


if __name__ == "__main__":
    exercise_catalog = write_json_file()
    seed_database(exercise_catalog)
