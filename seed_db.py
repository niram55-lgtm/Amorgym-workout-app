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
import os
import secrets as pysecrets
from pathlib import Path

from database import Exercise, Program, User, init_db, get_session
from exercise_catalog_generator import build_catalog

DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "exercises.json"


def _resolve_password(secret_key: str, env_key: str, random_prefix: str) -> str:
    """
    קובעת את סיסמת ברירת המחדל למשתמשת ראשונית, לפי סדר עדיפות:
    1. st.secrets (מוגדר בממשק ה-Secrets של Streamlit Cloud - לא נשמר בקוד/git בכלל)
    2. משתנה סביבה (לפיתוח מקומי, למשל בקובץ .env שלא מחובר ל-git)
    3. סיסמה אקראית חד-פעמית (מודפסת לטרמינל בזמן ה-seed) - כדי שלעולם לא תהיה
       סיסמה קבועה בקוד המקור, גם אם ה-repo הופך ל-Public.
    """
    try:
        import streamlit as st
        if secret_key in st.secrets:
            return st.secrets[secret_key]
    except Exception:
        pass
    if os.environ.get(env_key):
        return os.environ[env_key]
    return f"{random_prefix}-{pysecrets.token_hex(4)}"


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

def _default_users() -> list[dict]:
    """
    נבנה בכל קריאה (לא קבוע מודול) כדי שהסיסמה האקראית תיקבע פעם אחת בזמן ה-seed בפועל,
    ולא תיחשף בקוד המקור עצמו.
    """
    return [
        {
            "username": "manager",
            "password": _resolve_password("GYM_MANAGER_PASSWORD", "GYM_MANAGER_PASSWORD", "manager"),
            "display_name": "מנהלת הסטודיו",
            "role": "מנהלת",
        },
        {
            "username": "trainer1",
            "password": _resolve_password("GYM_TRAINER_PASSWORD", "GYM_TRAINER_PASSWORD", "trainer"),
            "display_name": "מאמנת לדוגמה",
            "role": "מאמנת",
        },
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
            default_users = _default_users()
            for u in default_users:
                user = User(username=u["username"], display_name=u["display_name"], role=u["role"])
                user.set_password(u["password"])
                session.add(user)
            session.commit()
            print(
                "נוצרו משתמשות ברירת מחדל - שמרי את הסיסמאות האלו, הן לא נשמרות בשום מקום אחר:",
                flush=True,
            )
            for u in default_users:
                print(f"  - {u['role']}: שם משתמש '{u['username']}' / סיסמה '{u['password']}'", flush=True)
    finally:
        session.close()


if __name__ == "__main__":
    exercise_catalog = write_json_file()
    seed_database(exercise_catalog)
