from typing import Optional
from sqlalchemy import BigInteger, String, Integer, Time, Boolean, ForeignKey, Index, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    grade_level: Mapped[int] = mapped_column(Integer, index=True)

    users: Mapped[list["User"]] = relationship(back_populates="selected_class")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="school_class", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Class(name='{self.name}', grade={self.grade_level})>"


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Teacher(name='{self.name}')>"


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    class_id: Mapped[Optional[int]] = mapped_column(ForeignKey("classes.id"), nullable=True)
    teacher_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teachers.id"), nullable=True)
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_active: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    
    selected_class: Mapped[Optional["Class"]] = relationship(back_populates="users")
    selected_teacher: Mapped[Optional["Teacher"]] = relationship()
    
    # New fields
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timezone_offset: Mapped[int] = mapped_column(Integer, default=0)
    gamification_stats: Mapped[Optional["GamificationStats"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.telegram_id}, role={self.role})>"


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_name: Mapped[str] = mapped_column(String, nullable=False)
    teacher_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    room_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    start_time: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    end_time: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    is_substitution: Mapped[bool] = mapped_column(Boolean, default=False)
    group_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # For class splits

    school_class: Mapped["Class"] = relationship(back_populates="schedules")
    
    __table_args__ = (
        Index("idx_class_day", "class_id", "day_of_week"),
    )

    def __repr__(self) -> str:
        return f"<Schedule(class={self.class_id}, day={self.day_of_week}, lesson={self.lesson_number})>"


class Substitution(Base):
    __tablename__ = "substitutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String, nullable=False, index=True)
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    subject_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    teacher_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    room_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    school_class: Mapped["Class"] = relationship()
    
    __table_args__ = (
        Index("idx_sub_class_date", "class_id", "date"),
    )

    def __repr__(self) -> str:
        return f"<Substitution(date={self.date}, class={self.class_id}, lesson={self.lesson_number})>"


class SystemMeta(Base):
    __tablename__ = "system_meta"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    color_hex: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Subject(name='{self.name}', color='{self.color_hex}')>"


class GamificationStats(Base):
    __tablename__ = "gamification_stats"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"), primary_key=True)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_checkin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)

    user: Mapped["User"] = relationship(back_populates="gamification_stats")

    def __repr__(self) -> str:
        return f"<GamificationStats(user={self.user_id}, lvl={self.level})>"


class AttendanceLog(Base):
    __tablename__ = "attendance_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"), index=True)
    timestamp: Mapped[str] = mapped_column(String, nullable=False)
    
    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<AttendanceLog(user={self.user_id}, time={self.timestamp})>"
