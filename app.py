"""
אפליקציית Streamlit לניהול אימוני חדר כושר.
כוללת התחברות עם הרשאות (מנהלת/מאמנת), פאנל מנהלת (ניהול כמה תוכניות/חוקים
במקביל), פאנל מאמנת (יצירה, עריכה חכמה ושמירה של אימונים) והיסטוריית אימונים.
כל הממשק בעברית וב-RTL.
"""
import streamlit as st

from database import (
    Exercise,
    Program,
    User,
    Workout,
    WorkoutExercise,
    MUSCLE_GROUPS,
    ROLES,
    init_db,
    get_session,
    authenticate,
)
from workout_logic import generate_workout, find_alternative_exercise
from exercise_catalog_generator import build_catalog
from seed_db import seed_database

THEME_GROUPS = [g for g in MUSCLE_GROUPS if g != "אירובי"]
PHASE_LABELS = ["חימום", "מרכזי", "שחרור"]


# ---------------------------------------------------------------------------
# הגדרות עמוד + עיצוב RTL
# ---------------------------------------------------------------------------
st.set_page_config(page_title="ניהול אימוני חדר כושר", page_icon="🏋️", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stSidebarContent"],
    [data-testid="stMarkdownContainer"],
    [data-testid="stHeading"] {
        direction: RTL;
        text-align: right;
    }
    .stButton button {
        width: 100%;
    }
    div[data-testid="stMetricValue"] {
        direction: ltr;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_resource
def bootstrap_database() -> None:
    """
    יוצר טבלאות ומזריק נתוני ברירת מחדל (תרגילים/תוכניות/משתמשות) בהפעלה ראשונה בלבד.
    חשוב בפריסה בענן שבה אין הזדמנות להריץ seed_db.py בנפרד לפני עליית האפליקציה.
    """
    init_db()
    seed_database(build_catalog())


bootstrap_database()


def fmt_duration(seconds: int) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


# ---------------------------------------------------------------------------
# התחברות
# ---------------------------------------------------------------------------
def login_screen():
    st.title("🏋️ ניהול אימוני חדר כושר")
    st.subheader("התחברות")
    with st.form("login_form"):
        username = st.text_input("שם משתמש")
        password = st.text_input("סיסמה", type="password")
        submitted = st.form_submit_button("התחברות", type="primary")

    if submitted:
        session = get_session()
        try:
            user = authenticate(session, username.strip(), password)
        finally:
            session.close()
        if user is None:
            st.error("שם משתמש או סיסמה שגויים.")
        else:
            st.session_state["user"] = {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
            }
            st.rerun()

    st.caption("משתמשות ברירת מחדל לדוגמה: manager / admin123 (מנהלת), trainer1 / trainer123 (מאמנת).")


# ---------------------------------------------------------------------------
# פאנל מנהלת
# ---------------------------------------------------------------------------
def admin_panel():
    st.title("📋 פאנל מנהלת - ניהול תוכניות וחוקים")

    session = get_session()
    try:
        programs = session.query(Program).order_by(Program.name).all()
        program_options = {p.name: p.id for p in programs}
        choice_labels = ["➕ תוכנית חדשה"] + list(program_options.keys())
        selected_label = st.selectbox("בחרו תוכנית לעריכה, או צרו חדשה", choice_labels)

        is_new = selected_label == "➕ תוכנית חדשה"
        program = None if is_new else session.get(Program, program_options[selected_label])

        with st.form("program_form"):
            st.subheader("נושא גג ואחוז זמן")
            name = st.text_input("שם התוכנית", value="" if is_new else program.name)
            col1, col2 = st.columns(2)
            with col1:
                month_theme = st.selectbox(
                    "החודש מתמקדים ב:",
                    options=THEME_GROUPS,
                    index=0 if is_new else THEME_GROUPS.index(program.month_theme),
                )
            with col2:
                theme_percentage = st.slider(
                    "אחוז זמן האימון המוקדש לנושא הגג",
                    min_value=0,
                    max_value=100,
                    value=80 if is_new else program.theme_percentage,
                    step=5,
                )
            st.caption(
                f"המערכת תשלים אוטומטית את שאר האחוזים מזמן החלק המרכזי לקבוצות השריר הנותרות."
            )

            st.divider()
            st.subheader("חוק חובה")
            mandatory_note = st.text_input(
                "תיאור החוק (יוצג למאמנות)",
                value="כל אימון מסתיים ב-2 דקות פלאנק" if is_new else program.mandatory_note,
            )
            col3, col4 = st.columns(2)
            with col3:
                mandatory_exercise_name = st.text_input(
                    "שם התרגיל שיתווסף אוטומטית בסוף כל אימון",
                    value="פלאנק" if is_new else program.mandatory_exercise_name,
                    help="אם השם תואם תרגיל קיים במאגר, המערכת תציג את קבוצת השריר/הקושי האמיתיים שלו.",
                )
            with col4:
                mandatory_duration_seconds = st.number_input(
                    "משך התרגיל (בשניות)",
                    min_value=15,
                    max_value=900,
                    value=120 if is_new else program.mandatory_duration_seconds,
                    step=15,
                )

            save_clicked = st.form_submit_button("💾 שמור תוכנית", type="primary")

        if save_clicked:
            if not name.strip():
                st.error("יש להזין שם לתוכנית.")
            else:
                target = program if program else Program()
                target.name = name.strip()
                target.month_theme = month_theme
                target.theme_percentage = theme_percentage
                target.mandatory_note = mandatory_note
                target.mandatory_exercise_name = mandatory_exercise_name
                target.mandatory_duration_seconds = int(mandatory_duration_seconds)
                if is_new:
                    session.add(target)
                session.commit()
                st.success(f"התוכנית '{name}' נשמרה בהצלחה.")
                st.rerun()

        if not is_new:
            if st.button("🗑️ מחק תוכנית"):
                session.delete(program)
                session.commit()
                st.warning(f"התוכנית '{selected_label}' נמחקה.")
                st.rerun()

        st.divider()
        st.subheader("ניהול משתמשות")
        users = session.query(User).order_by(User.role, User.username).all()
        st.dataframe(
            [{"שם משתמש": u.username, "שם תצוגה": u.display_name, "תפקיד": u.role} for u in users],
            width="stretch",
            hide_index=True,
        )
        with st.expander("➕ הוספת משתמשת חדשה"):
            with st.form("new_user_form"):
                new_username = st.text_input("שם משתמש (לכניסה למערכת)")
                new_display_name = st.text_input("שם מלא לתצוגה")
                new_role = st.selectbox("תפקיד", options=ROLES)
                new_password = st.text_input("סיסמה זמנית", type="password")
                add_user_submitted = st.form_submit_button("➕ הוסף משתמשת")
            if add_user_submitted:
                if not new_username.strip() or not new_password:
                    st.error("יש למלא שם משתמש וסיסמה.")
                elif session.query(User).filter(User.username == new_username.strip()).first():
                    st.error("שם המשתמש כבר קיים.")
                else:
                    new_user = User(
                        username=new_username.strip(),
                        display_name=new_display_name.strip() or new_username.strip(),
                        role=new_role,
                    )
                    new_user.set_password(new_password)
                    session.add(new_user)
                    session.commit()
                    st.success(f"המשתמשת '{new_username}' נוצרה בהצלחה.")
                    st.rerun()

        st.divider()
        st.subheader("מאגר התרגילים")
        exercise_count = session.query(Exercise).count()
        st.write(f"סה\"כ **{exercise_count}** תרגילים במאגר.")
        exercises = session.query(Exercise).order_by(Exercise.muscle_group, Exercise.name_he).all()
        st.dataframe(
            [
                {
                    "שם": ex.name_he,
                    "קבוצת שריר": ex.muscle_group,
                    "קושי": ex.difficulty,
                    "שלב": ex.phase,
                    "משך (שניות)": ex.default_duration_seconds,
                }
                for ex in exercises
            ],
            width="stretch",
            hide_index=True,
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# פאנל מאמנת
# ---------------------------------------------------------------------------
def trainer_panel():
    st.title("💪 פאנל מאמנת - יצירת אימון")

    session = get_session()
    try:
        programs = session.query(Program).order_by(Program.name).all()
        if not programs:
            st.error("לא הוגדרו תוכניות במערכת. יש לפנות למנהלת הסטודיו.")
            return

        program_options = {p.name: p.id for p in programs}
        selected_program_name = st.selectbox("תוכנית", options=list(program_options.keys()))
        program: Program = session.get(Program, program_options[selected_program_name])

        st.info(
            f"נושא גג: **{program.month_theme}** ({program.theme_percentage}% מהחלק המרכזי) · "
            f"חוק חובה: {program.mandatory_note}"
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            total_minutes = st.number_input(
                "אורך האימון (דקות)", min_value=10, max_value=120, value=45, step=5
            )
            generate_clicked = st.button("⚡ ייצר אימון", type="primary")

        if generate_clicked:
            try:
                workout_items = generate_workout(session, program.id, int(total_minutes))
                st.session_state["workout"] = workout_items
                st.session_state["workout_minutes"] = int(total_minutes)
                st.session_state["workout_program_id"] = program.id
                st.session_state["workout_program_name"] = program.name
                st.session_state["workout_theme"] = program.month_theme
                st.session_state["workout_saved"] = False
            except ValueError as e:
                st.error(str(e))

        if "workout" not in st.session_state:
            st.warning("טרם נוצר אימון. בחרו תוכנית ואורך אימון ולחצו על 'ייצר אימון'.")
            return

        workout_items: list[dict] = st.session_state["workout"]
        total_planned = sum(item["duration_seconds"] for item in workout_items)

        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("זמן מתוכנן בפועל", fmt_duration(total_planned))
        m2.metric("זמן מבוקש", fmt_duration(st.session_state["workout_minutes"] * 60))
        if m3.button("💾 שמור אימון להיסטוריה", type="primary"):
            user = st.session_state["user"]
            workout = Workout(
                trainer_id=user["id"],
                program_id=st.session_state["workout_program_id"],
                total_minutes=st.session_state["workout_minutes"],
                month_theme=st.session_state["workout_theme"],
                program_name=st.session_state["workout_program_name"],
            )
            for item in workout_items:
                workout.items.append(
                    WorkoutExercise(
                        order_index=item["order_index"],
                        phase=item["phase"],
                        exercise_id=item["exercise_id"],
                        name_he=item["name_he"],
                        muscle_group=item["muscle_group"],
                        difficulty=item["difficulty"],
                        duration_seconds=item["duration_seconds"],
                        is_mandatory=item["is_mandatory"],
                    )
                )
            session.add(workout)
            session.commit()
            st.session_state["workout_saved"] = True
            st.success("האימון נשמר בהיסטוריה בהצלחה.")

        used_ids = {item["exercise_id"] for item in workout_items if item["exercise_id"]}

        for phase in PHASE_LABELS:
            phase_items = [it for it in workout_items if it["phase"] == phase]
            if not phase_items:
                continue
            phase_seconds = sum(it["duration_seconds"] for it in phase_items)
            st.subheader(f"{phase} · {fmt_duration(phase_seconds)}")

            for item in phase_items:
                idx = workout_items.index(item)
                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
                c1.markdown(f"**{item['name_he']}**" + (" 🔒" if item["is_mandatory"] else ""))
                c2.write(item["muscle_group"])
                c3.write(item["difficulty"])
                c4.write(fmt_duration(item["duration_seconds"]))
                with c5:
                    if not item["is_mandatory"]:
                        if st.button("🔄 החלף", key=f"swap_{idx}"):
                            alt = find_alternative_exercise(
                                session,
                                item["muscle_group"],
                                item["difficulty"],
                                item["phase"],
                                used_ids,
                            )
                            if alt is None:
                                st.toast("אין תרגיל חלופי זמין באותה קבוצת שריר, קושי ושלב.", icon="⚠️")
                            else:
                                used_ids.discard(item["exercise_id"])
                                item["exercise_id"] = alt.id
                                item["name_he"] = alt.name_he
                                item["duration_seconds"] = alt.default_duration_seconds
                                used_ids.add(alt.id)
                                st.session_state["workout"] = workout_items
                                st.session_state["workout_saved"] = False
                                st.rerun()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# היסטוריית אימונים
# ---------------------------------------------------------------------------
def history_panel():
    st.title("🗂️ היסטוריית אימונים")

    session = get_session()
    try:
        user = st.session_state["user"]
        query = session.query(Workout).order_by(Workout.created_at.desc())
        if user["role"] == "מאמנת":
            query = query.filter(Workout.trainer_id == user["id"])
        workouts = query.all()

        if not workouts:
            st.info("עדיין לא נשמרו אימונים.")
            return

        for workout in workouts:
            trainer_name = workout.trainer.display_name if workout.trainer else "לא ידוע"
            header = (
                f"{workout.created_at.strftime('%d/%m/%Y %H:%M')} · "
                f"{trainer_name} · {workout.program_name} ({workout.total_minutes} דק')"
            )
            with st.expander(header):
                st.dataframe(
                    [
                        {
                            "שלב": item.phase,
                            "תרגיל": item.name_he + (" 🔒" if item.is_mandatory else ""),
                            "קבוצת שריר": item.muscle_group,
                            "קושי": item.difficulty,
                            "משך": fmt_duration(item.duration_seconds),
                        }
                        for item in workout.items
                    ],
                    width="stretch",
                    hide_index=True,
                )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# ניווט ראשי
# ---------------------------------------------------------------------------
if "user" not in st.session_state:
    login_screen()
else:
    user = st.session_state["user"]
    st.sidebar.title("🏋️ ניהול חדר כושר")
    st.sidebar.caption(f"מחוברת: {user['display_name']} ({user['role']})")
    if st.sidebar.button("🚪 התנתקות"):
        del st.session_state["user"]
        st.session_state.pop("workout", None)
        st.rerun()

    if user["role"] == "מנהלת":
        pages = ["פאנל מנהלת", "פאנל מאמנת", "היסטוריית אימונים"]
    else:
        pages = ["פאנל מאמנת", "היסטוריית אימונים"]

    page = st.sidebar.radio("ניווט", pages, label_visibility="collapsed")

    if page == "פאנל מנהלת":
        admin_panel()
    elif page == "פאנל מאמנת":
        trainer_panel()
    else:
        history_panel()
