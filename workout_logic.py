"""
לוגיקת הליבה: הרכבת אימון אוטומטית לפי אחוזי הזמן שהגדירה המנהלת,
והחלפת תרגיל בודד בעורך החכם.
"""
from __future__ import annotations

import random
from typing import Optional

from sqlalchemy import select

from database import Program, Exercise, MUSCLE_GROUPS

# יחסי זמן קבועים בתוך חלק ה"גוף" של האימון (אחרי הפרשה לחוק החובה)
WARMUP_RATIO = 0.15
MAIN_RATIO = 0.70
COOLDOWN_RATIO = 0.15


def _pick_exercises(
    session, muscle_group: Optional[str], phase: str, seconds_needed: int, exclude_ids: set[int]
) -> list[Exercise]:
    """
    בוחר תרגילים ייחודיים (ללא חזרה) מהמאגר עד שמשך הזמן המצטבר מגיע ליעד.
    אם אין מספיק תרגילים שונים במאגר, מחזיר את כל מה שיש - בלי לשכפל תרגיל.
    """
    query = select(Exercise).where(Exercise.phase == phase)
    if muscle_group:
        query = query.where(Exercise.muscle_group == muscle_group)
    candidates = list(session.execute(query).scalars())
    candidates = [c for c in candidates if c.id not in exclude_ids]
    random.shuffle(candidates)

    chosen: list[Exercise] = []
    time_accum = 0
    for ex in candidates:
        if time_accum >= seconds_needed:
            return chosen
        chosen.append(ex)
        exclude_ids.add(ex.id)
        time_accum += ex.default_duration_seconds

    # המאגר הזמין קטן מדי כדי למלא את הזמן המבוקש בתרגילים ייחודיים בלבד.
    # ממלאים את היתרה בחזרה מבוקרת (עד פעם נוספת אחת לכל תרגיל) במקום להשאיר זמן ריק.
    random.shuffle(candidates)
    for ex in candidates:
        if time_accum >= seconds_needed:
            break
        chosen.append(ex)
        time_accum += ex.default_duration_seconds
    return chosen


def generate_workout(session, program_id: int, total_minutes: int) -> list[dict]:
    """
    בונה אימון מלא (חימום -> מרכזי -> שחרור) לפי התוכנית (Program) שנבחרה.
    מחזיר רשימת dict-ים בסדר ההופעה, כל אחד מוכן לתצוגה/עריכה ב-Streamlit.
    """
    program: Optional[Program] = session.get(Program, program_id)
    if program is None:
        raise ValueError("התוכנית שנבחרה לא נמצאה. יש לבחור תוכנית תקפה מהרשימה.")

    total_seconds = total_minutes * 60
    mandatory_seconds = program.mandatory_duration_seconds
    body_seconds = max(total_seconds - mandatory_seconds, 0)

    warmup_seconds = int(body_seconds * WARMUP_RATIO)
    main_seconds = int(body_seconds * MAIN_RATIO)
    cooldown_seconds = body_seconds - warmup_seconds - main_seconds

    # חלוקת "המרכזי" בין נושא הגג לשאר קבוצות השריר לפי האחוז שהוגדר
    theme_seconds = int(main_seconds * (program.theme_percentage / 100))
    other_seconds_total = main_seconds - theme_seconds

    other_groups = [g for g in MUSCLE_GROUPS if g != program.month_theme and g != "אירובי"]
    seconds_per_other_group = (
        other_seconds_total // len(other_groups) if other_groups else 0
    )

    exclude_ids: set[int] = set()
    workout_items: list[dict] = []
    order_index = 0

    def add_items(exercises: list[Exercise], phase: str, is_mandatory: bool = False):
        nonlocal order_index
        for ex in exercises:
            workout_items.append(
                {
                    "order_index": order_index,
                    "phase": phase,
                    "exercise_id": ex.id,
                    "name_he": ex.name_he,
                    "muscle_group": ex.muscle_group,
                    "difficulty": ex.difficulty,
                    "duration_seconds": ex.default_duration_seconds,
                    "is_mandatory": is_mandatory,
                }
            )
            order_index += 1

    # 1. חימום
    warmup_exercises = _pick_exercises(session, None, "חימום", warmup_seconds, exclude_ids)
    add_items(warmup_exercises, "חימום")

    # 2. חלק מרכזי - נושא הגג
    theme_exercises = _pick_exercises(
        session, program.month_theme, "מרכזי", theme_seconds, exclude_ids
    )
    add_items(theme_exercises, "מרכזי")

    # 2ב. חלק מרכזי - שאר קבוצות השריר (השלמה אוטומטית ל-100%)
    for group in other_groups:
        group_exercises = _pick_exercises(
            session, group, "מרכזי", seconds_per_other_group, exclude_ids
        )
        add_items(group_exercises, "מרכזי")

    # 3. שחרור
    cooldown_exercises = _pick_exercises(
        session, None, "שחרור", cooldown_seconds, exclude_ids
    )
    add_items(cooldown_exercises, "שחרור")

    # 4. חוק החובה של המנהלת - תמיד בסוף האימון.
    # אם שם התרגיל תואם תרגיל קיים במאגר, שואבים ממנו קבוצת שריר/קושי אמיתיים לתצוגה.
    mandatory_exercise = (
        session.query(Exercise).filter(Exercise.name_he == program.mandatory_exercise_name).first()
    )
    workout_items.append(
        {
            "order_index": order_index,
            "phase": "שחרור",
            "exercise_id": mandatory_exercise.id if mandatory_exercise else None,
            "name_he": program.mandatory_exercise_name,
            "muscle_group": mandatory_exercise.muscle_group if mandatory_exercise else "ליבה",
            "difficulty": mandatory_exercise.difficulty if mandatory_exercise else "בינוני",
            "duration_seconds": program.mandatory_duration_seconds,
            "is_mandatory": True,
        }
    )

    return workout_items


def find_alternative_exercise(
    session, muscle_group: str, difficulty: str, phase: str, exclude_ids: set[int]
) -> Optional[Exercise]:
    """
    מוצא תרגיל חלופי מאותה קבוצת שריר, אותה רמת קושי ואותו שלב אימון,
    לצורך "עורך האימונים החכם". מחזיר None אם אין חלופה זמינה.
    """
    query = select(Exercise).where(
        Exercise.muscle_group == muscle_group,
        Exercise.difficulty == difficulty,
        Exercise.phase == phase,
    )
    candidates = [
        ex for ex in session.execute(query).scalars() if ex.id not in exclude_ids
    ]
    if not candidates:
        return None
    return random.choice(candidates)
