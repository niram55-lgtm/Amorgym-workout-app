"""
בונה את מאגר התרגילים המלא (~500 תרגילים) משילוב תנועות בסיס (exercise_catalog_data)
עם וריאציות ציוד/סגנון אמיתיות. כל שילוב מקבל קושי, משך ותיאור באופן עקבי.
"""
from exercise_catalog_data import (
    MODIFIER_SETS,
    BACK_MAIN,
    LEGS_MAIN,
    CHEST_MAIN,
    CORE_MAIN,
    SHOULDERS_MAIN,
    ARMS_MAIN,
    CARDIO_WARMUP,
    CARDIO_MAIN,
    STRETCH_BACK,
    STRETCH_LEGS,
    STRETCH_CHEST,
    STRETCH_CORE,
    STRETCH_SHOULDERS,
    STRETCH_ARMS,
)

DIFFICULTY_ORDER = ["קל", "בינוני", "קשה"]

# כמה רמות להזיז את הקושי הבסיסי בהתאם לוריאציה הספציפית (יוצר גיוון אמיתי)
DIFFICULTY_SHIFT = {
    "קלאסי": 0,
    "גרסה מקלה (טווח/עומס מופחת)": -1,
    "גרסה מאתגרת (טווח/קצב מוגבר)": 1,
    "בטמפו איטי ומבוקר": 1,
    "עם הפסקה בשיא התנועה": 1,
    "דו-צדדי": -1,
    "חד-צדדי - צד ימין": 0,
    "חד-צדדי - צד שמאל": 0,
    "עם תמיכה בקיר/כיסא": -1,
    "בעמידה לא יציבה (אתגר שיווי משקל)": 1,
    "בקצב נמוך": -1,
    "בקצב בינוני": 0,
    "בקצב גבוה (אינטרוולים)": 1,
    "בוריאציית תנועת זרועות": 0,
    "עם קפיצה נוספת": 1,
    "לפרק זמן ממושך": 0,
}

BASE_DURATION = {"קל": 35, "בינוני": 45, "קשה": 55}

# ציוד לפי הוריאציה עצמה, כשהיא מייצגת ציוד באופן ישיר (סט "weighted")
EQUIPMENT_BY_WEIGHTED_MODIFIER = {
    "עם משקולות יד": "משקולות יד",
    "עם מוט": "מוט",
    "בגומיית התנגדות": "גומיית התנגדות",
    "עם קטלבל": "קטלבל",
    "במכונה": "מכונה / פולי",
}

# תנועות "unilateral" לא נגזרות מהוריאציה (זו רק שאלת צד/יציבות) - צריך ציוד מפורש לכל תנועה
UNILATERAL_EQUIPMENT = {
    "חתירה חד-ידנית": "משקולות יד",
    "לאנג'": "משקל גוף",
    "מכרעים בולגרים": "משקל גוף / משקולות יד",
    "עליות מדרגה": "משקל גוף",
    "גשר רגל אחת": "משקל גוף",
    "לחיצת חזה חד-ידנית": "משקולות יד",
    "הרחקת כתף חד-ידנית": "משקולות יד",
    "לחיצת כתפיים חד-ידנית": "משקולות יד",
    "כפיפת מרפקים בריכוז (Concentration Curl)": "משקולות יד",
    "פשיטת מרפק חד-ידנית בכבל": "מכונה / פולי",
    "כפיפת מרפקים חד-ידנית": "משקולות יד",
}

STRETCH_EQUIPMENT = {
    "מתיחה סטטית 20 שניות": "ללא ציוד",
    "מתיחה סטטית 30 שניות": "ללא ציוד",
    "מתיחה דינמית": "ללא ציוד",
    "מתיחה עם רצועה/גומייה": "רצועה / גומייה",
    "מתיחה משולבת נשימה עמוקה": "ללא ציוד",
}


def _shift_difficulty(base_difficulty: str, modifier: str) -> str:
    idx = DIFFICULTY_ORDER.index(base_difficulty) + DIFFICULTY_SHIFT.get(modifier, 0)
    idx = max(0, min(len(DIFFICULTY_ORDER) - 1, idx))
    return DIFFICULTY_ORDER[idx]


def _derive_equipment(base_name: str, modifier_key: str, modifier: str) -> str:
    if modifier_key == "weighted":
        equipment = EQUIPMENT_BY_WEIGHTED_MODIFIER[modifier]
        if equipment == "מכונה / פולי" and "כבל" in base_name:
            return "מכונה / פולי (כבל)"
        return equipment
    if modifier_key == "unilateral":
        return UNILATERAL_EQUIPMENT.get(base_name, "משקולות יד")
    if modifier_key in ("bodyweight", "cardio"):
        return "משקל גוף"
    return "ללא ציוד"


def _build_main_group(movements: list[tuple[str, str, str]], muscle_group: str, phase: str) -> list[dict]:
    items = []
    for base_name, modifier_key, base_difficulty in movements:
        for modifier in MODIFIER_SETS[modifier_key]:
            difficulty = _shift_difficulty(base_difficulty, modifier)
            equipment = _derive_equipment(base_name, modifier_key, modifier)
            items.append(
                {
                    "name_he": f"{base_name} - {modifier}",
                    "muscle_group": muscle_group,
                    "difficulty": difficulty,
                    "phase": phase,
                    "equipment": equipment,
                    "default_duration_seconds": BASE_DURATION[difficulty],
                    "description": f"{base_name} ({modifier}) - תרגיל ל{muscle_group}, רמת קושי {difficulty}, ציוד: {equipment}.",
                }
            )
    return items


def _build_stretch_group(stretch_names: list[str], muscle_group: str) -> list[dict]:
    items = []
    for base_name in stretch_names:
        for modifier in MODIFIER_SETS["stretch"]:
            equipment = STRETCH_EQUIPMENT[modifier]
            items.append(
                {
                    "name_he": f"{base_name} - {modifier}",
                    "muscle_group": muscle_group,
                    "difficulty": "קל",
                    "phase": "שחרור",
                    "equipment": equipment,
                    "default_duration_seconds": 30,
                    "description": f"{base_name} ({modifier}) - מתיחת שחרור ל{muscle_group}, ציוד: {equipment}.",
                }
            )
    return items


def build_catalog() -> list[dict]:
    catalog: list[dict] = []
    catalog += _build_main_group(BACK_MAIN, "גו", "מרכזי")
    catalog += _build_main_group(LEGS_MAIN, "רגליים", "מרכזי")
    catalog += _build_main_group(CHEST_MAIN, "חזה", "מרכזי")
    catalog += _build_main_group(CORE_MAIN, "ליבה", "מרכזי")
    catalog += _build_main_group(SHOULDERS_MAIN, "כתפיים", "מרכזי")
    catalog += _build_main_group(ARMS_MAIN, "ידיים", "מרכזי")
    catalog += _build_main_group(CARDIO_WARMUP, "אירובי", "חימום")
    catalog += _build_main_group(CARDIO_MAIN, "אירובי", "מרכזי")
    catalog += _build_stretch_group(STRETCH_BACK, "גו")
    catalog += _build_stretch_group(STRETCH_LEGS, "רגליים")
    catalog += _build_stretch_group(STRETCH_CHEST, "חזה")
    catalog += _build_stretch_group(STRETCH_CORE, "ליבה")
    catalog += _build_stretch_group(STRETCH_SHOULDERS, "כתפיים")
    catalog += _build_stretch_group(STRETCH_ARMS, "ידיים")

    names = [item["name_he"] for item in catalog]
    assert len(names) == len(set(names)), "נמצאו שמות תרגילים כפולים בקטלוג"
    return catalog


if __name__ == "__main__":
    result = build_catalog()
    print(f"נבנו {len(result)} תרגילים.")
