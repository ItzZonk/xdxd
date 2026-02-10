from typing import Optional
from sqlalchemy import BigInteger, String, Integer, Time, Boolean, ForeignKey, Index
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
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    selected_class: Mapped[Optional["Class"]] = relationship(back_populates="users")
    selected_teacher: Mapped[Optional["Teacher"]] = relationship()

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
