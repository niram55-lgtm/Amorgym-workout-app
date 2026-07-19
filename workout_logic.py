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

# מספר תרגילי הכוח בחלק המרכזי: קבוע לטווח ריאלי של אימון בפועל (לא נגזר מזמן),
# עם כמה סטים/חזרות על כל תרגיל כדי למלא את הזמן שהוקצה.
MAIN_EXERCISE_COUNT_CHOICES = [6, 7]

DEFAULT_NUM_WORKOUT_OPTIONS = 10


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


def _base_movement_name(exercise: Exercise) -> str:
    """שם תנועת הבסיס בלי הוריאציה (למשל 'מתח' מתוך 'מתח - בטמפו איטי ומבוקר')."""
    return exercise.name_he.split(" - ")[0]


def _pick_diverse(candidates: list[Exercise], count: int, used_bases: set[str]) -> list[Exercise]:
    """
    בוחרת עד count תרגילים מתוך candidates (כבר מעורבבים אקראית), תוך העדפה ברורה
    לתנועות בסיס שונות זו מזו (כדי לא לקבל למשל 3 וריאציות של "מתח" באותו אימון).
    חוזרת על תנועת בסיס רק אם ממש נגמרו האפשרויות השונות.
    """
    unique_first, fallback = [], []
    for ex in candidates:
        base = _base_movement_name(ex)
        (fallback if base in used_bases else unique_first).append(ex)
        if base not in used_bases:
            used_bases.add(base)

    chosen = []
    for ex in unique_first:
        if len(chosen) >= count:
            break
        chosen.append(ex)
    for ex in fallback:
        if len(chosen) >= count:
            break
        chosen.append(ex)
    return chosen


def _pick_main_exercises(
    session, theme_group: str, other_groups: list[str], theme_percentage: int,
    main_seconds: int, exclude_ids: set[int]
) -> list[tuple[Exercise, int]]:
    """
    בוחרת בין 6 ל-7 תרגילי כוח לחלק המרכזי: כ-theme_percentage% מהם מנושא הגג,
    השאר מפוזר בין שאר קבוצות השריר. מעדיפה תנועות בסיס שונות זו מזו (לא כמה
    וריאציות של אותה תנועה). הזמן הכולל של החלק המרכזי מתחלק שווה בשווה
    בין התרגילים שנבחרו (מייצג כמה סטים/חזרות על כל תרגיל, לא מעבר חד-פעמי).
    מחזירה רשימת (Exercise, duration_seconds).
    """
    count = random.choice(MAIN_EXERCISE_COUNT_CHOICES)
    theme_count = max(1, min(count, round(count * theme_percentage / 100)))
    other_count = count - theme_count
    used_bases: set[str] = set()

    theme_query = select(Exercise).where(Exercise.phase == "מרכזי", Exercise.muscle_group == theme_group)
    theme_candidates = [c for c in session.execute(theme_query).scalars() if c.id not in exclude_ids]
    random.shuffle(theme_candidates)
    chosen = _pick_diverse(theme_candidates, theme_count, used_bases)
    for ex in chosen:
        exclude_ids.add(ex.id)

    if other_count > 0 and other_groups:
        group_cycle = other_groups.copy()
        random.shuffle(group_cycle)
        attempts = 0
        idx = 0
        while len(chosen) - theme_count < other_count and attempts < other_count * 10:
            group = group_cycle[idx % len(group_cycle)]
            query = select(Exercise).where(Exercise.phase == "מרכזי", Exercise.muscle_group == group)
            candidates = [c for c in session.execute(query).scalars() if c.id not in exclude_ids]
            candidates = [c for c in candidates if c.id not in exclude_ids]
            random.shuffle(candidates)
            pick_list = _pick_diverse(candidates, 1, used_bases)
            if pick_list:
                pick = pick_list[0]
                chosen.append(pick)
                exclude_ids.add(pick.id)
            idx += 1
            attempts += 1

    random.shuffle(chosen)

    actual_count = len(chosen)
    if actual_count == 0:
        return []
    base_seconds = main_seconds // actual_count
    remainder = main_seconds - base_seconds * actual_count
    return [
        (ex, base_seconds + (remainder if i == actual_count - 1 else 0))
        for i, ex in enumerate(chosen)
    ]


def _generate_single_workout(session, program: Program, total_minutes: int) -> list[dict]:
    """
    בונה אימון מלא (חימום -> מרכזי -> שחרור) לפי התוכנית (Program) שנבחרה.
    מחזיר רשימת dict-ים בסדר ההופעה, כל אחד מוכן לתצוגה/עריכה ב-Streamlit.
    """
    total_seconds = total_minutes * 60
    mandatory_seconds = program.mandatory_duration_seconds
    body_seconds = max(total_seconds - mandatory_seconds, 0)

    warmup_seconds = int(body_seconds * WARMUP_RATIO)
    main_seconds = int(body_seconds * MAIN_RATIO)
    cooldown_seconds = body_seconds - warmup_seconds - main_seconds

    other_groups = [g for g in MUSCLE_GROUPS if g != program.month_theme and g != "אירובי"]

    exclude_ids: set[int] = set()
    workout_items: list[dict] = []
    order_index = 0

    def add_items(entries, phase: str, is_mandatory: bool = False):
        """entries: רשימת Exercise (משתמש במשך ברירת המחדל שלו) או (Exercise, duration_seconds)."""
        nonlocal order_index
        for entry in entries:
            ex, duration = entry if isinstance(entry, tuple) else (entry, entry.default_duration_seconds)
            workout_items.append(
                {
                    "order_index": order_index,
                    "phase": phase,
                    "exercise_id": ex.id,
                    "name_he": ex.name_he,
                    "muscle_group": ex.muscle_group,
                    "difficulty": ex.difficulty,
                    "equipment": ex.equipment,
                    "duration_seconds": duration,
                    "is_mandatory": is_mandatory,
                }
            )
            order_index += 1

    # 1. חימום
    warmup_exercises = _pick_exercises(session, None, "חימום", warmup_seconds, exclude_ids)
    add_items(warmup_exercises, "חימום")

    # 2. חלק מרכזי - 6-7 תרגילי כוח בסה"כ, כ-theme_percentage% מהם מנושא הגג החודשי
    main_exercises = _pick_main_exercises(
        session, program.month_theme, other_groups, program.theme_percentage, main_seconds, exclude_ids
    )
    add_items(main_exercises, "מרכזי")

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
            "equipment": mandatory_exercise.equipment if mandatory_exercise else "משקל גוף",
            "duration_seconds": program.mandatory_duration_seconds,
            "is_mandatory": True,
        }
    )

    return workout_items


def generate_workout(session, program_id: int, total_minutes: int) -> list[dict]:
    """בונה אימון בודד לפי התוכנית שנבחרה. שימושי בעיקר לבדיקות/שימוש ישיר בלוגיקה."""
    program = session.get(Program, program_id)
    if program is None:
        raise ValueError("התוכנית שנבחרה לא נמצאה. יש לבחור תוכנית תקפה מהרשימה.")
    return _generate_single_workout(session, program, total_minutes)


def generate_workout_options(
    session, program_id: int, total_minutes: int, num_options: int = DEFAULT_NUM_WORKOUT_OPTIONS
) -> list[list[dict]]:
    """
    בונה כמה הצעות אימון עצמאיות (ברירת מחדל 10) לפי אותה תוכנית ואורך אימון,
    כדי שהמאמנת תוכל לבחור את זו שהכי מתאימה לה. כל הצעה נבנית באופן עצמאי
    (לא "נועלות" תרגילים אחת מהשנייה), כך שיש גיוון אמיתי בין ההצעות.
    """
    program = session.get(Program, program_id)
    if program is None:
        raise ValueError("התוכנית שנבחרה לא נמצאה. יש לבחור תוכנית תקפה מהרשימה.")
    return [_generate_single_workout(session, program, total_minutes) for _ in range(num_options)]


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
