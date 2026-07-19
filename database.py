"""
הגדרת סכמת מסד הנתונים (SQLite) באמצעות SQLAlchemy ORM.
מכיל את המודלים: Exercise, Program (תוכנית/חוקי מנהלת), User, Workout, WorkoutExercise.
"""
from __future__ import annotations

import datetime
import hashlib
import secrets
from typing import Optional

from sqlalchemy import (
    create_engine,
    ForeignKey,
    String,
    Integer,
    Boolean,
    DateTime,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

DB_PATH = "gym.db"
DB_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DB_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


MUSCLE_GROUPS = ["גו", "רגליים", "חזה", "ליבה", "אירובי"]
DIFFICULTIES = ["קל", "בינוני", "קשה"]
PHASES = ["חימום", "מרכזי", "שחרור"]
ROLES = ["מנהלת", "מאמנת"]


class Exercise(Base):
    """תרגיל בודד במאגר התרגילים."""

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_he: Mapped[str] = mapped_column(String(150), nullable=False)
    muscle_group: Mapped[str] = mapped_column(String(30), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)  # חימום / מרכזי / שחרור
    default_duration_seconds: Mapped[int] = mapped_column(Integer, default=45)
    description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    def __repr__(self) -> str:
        return f"<Exercise {self.name_he} ({self.muscle_group}/{self.difficulty})>"


class Program(Base):
    """
    תוכנית/אג'נדה חודשית שהמנהלת מגדירה: נושא גג, אחוז זמן, וחוק חובה.
    ניתן להחזיק כמה תוכניות במקביל (למשל לפי סניף או תקופה), והמאמנת בוחרת מהן ביצירת אימון.
    """

    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    month_theme: Mapped[str] = mapped_column(String(120), default="גו")
    theme_percentage: Mapped[int] = mapped_column(Integer, default=80)  # 0-100
    mandatory_note: Mapped[str] = mapped_column(
        String(300), default="כל אימון מסתיים ב-2 דקות פלאנק"
    )
    mandatory_exercise_name: Mapped[str] = mapped_column(String(120), default="פלאנק")
    mandatory_duration_seconds: Mapped[int] = mapped_column(Integer, default=120)

    def __repr__(self) -> str:
        return f"<Program {self.name}>"


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()


class User(Base):
    """משתמשת מערכת: מנהלת או מאמנת. הסיסמה נשמרת כ-hash מסוננן (PBKDF2), לא כטקסט גלוי."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # מנהלת / מאמנת
    password_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    password_salt: Mapped[str] = mapped_column(String(32), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_salt = secrets.token_hex(16)
        self.password_hash = _hash_password(password, self.password_salt)

    def check_password(self, password: str) -> bool:
        return secrets.compare_digest(_hash_password(password, self.password_salt), self.password_hash)


class Workout(Base):
    """אימון שנוצר ונשמר על ידי מאמנת - היסטוריית אימונים."""

    __tablename__ = "workouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    trainer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    program_id: Mapped[Optional[int]] = mapped_column(ForeignKey("programs.id"), nullable=True)
    total_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    month_theme: Mapped[str] = mapped_column(String(120), nullable=False)
    program_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    trainer: Mapped[Optional["User"]] = relationship()
    items: Mapped[list["WorkoutExercise"]] = relationship(
        back_populates="workout", cascade="all, delete-orphan", order_by="WorkoutExercise.order_index"
    )


class WorkoutExercise(Base):
    """שורה בודדת בתוך אימון שמור: קישור בין אימון לתרגיל, כולל סדר ומשך."""

    __tablename__ = "workout_exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id"))
    exercise_id: Mapped[Optional[int]] = mapped_column(ForeignKey("exercises.id"), nullable=True)

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    name_he: Mapped[str] = mapped_column(String(150), nullable=False)
    muscle_group: Mapped[str] = mapped_column(String(30), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)

    workout: Mapped["Workout"] = relationship(back_populates="items")
    exercise: Mapped[Optional["Exercise"]] = relationship()


def init_db() -> None:
    """יוצר את כל הטבלאות אם אינן קיימות."""
    Base.metadata.create_all(engine)


def get_session():
    """מחזיר Session חדש לעבודה מול ה-DB."""
    return SessionLocal()


def authenticate(session, username: str, password: str) -> Optional[User]:
    """מאמת שם משתמש+סיסמה. מחזיר את המשתמשת אם תקין, אחרת None."""
    user = session.query(User).filter(User.username == username).first()
    if user is None or not user.check_password(password):
        return None
    return user
