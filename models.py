from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey,
    UniqueConstraint, create_engine, func,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "habits.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String)
    google_id = Column(String, unique=True)
    theme_color = Column(String, default="green")
    created_at = Column(DateTime, server_default=func.now())

    habits = relationship("Habit", back_populates="user", cascade="all, delete-orphan")
    todos = relationship("Todo", back_populates="user", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    trackers = relationship("Tracker", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="categories")
    habits = relationship("Habit", back_populates="category")
    todos = relationship("Todo", back_populates="category")


class Habit(Base):
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    name = Column(String, nullable=False)
    description = Column(String)
    metric_enabled = Column(Boolean, default=False)
    metric_unit = Column(String)
    metric_default = Column(Float)
    metric_max = Column(Float)
    metric_step = Column(Float, default=0.5)
    order_index = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    start_date = Column(String)  # ISO date — habit only counts from this day onward
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="habits")
    category = relationship("Category", back_populates="habits")
    logs = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan")


class HabitLog(Base):
    __tablename__ = "habit_logs"

    id = Column(Integer, primary_key=True)
    habit_id = Column(Integer, ForeignKey("habits.id"), nullable=False)
    log_date = Column(String, nullable=False)
    completed = Column(Boolean, default=False)
    rating = Column(Integer)
    metric_value = Column(Float)
    metric_goal = Column(Float)  # snapshot of metric_default at time of logging
    notes = Column(String)
    logged_at = Column(DateTime, server_default=func.now())

    habit = relationship("Habit", back_populates="logs")

    __table_args__ = (UniqueConstraint("habit_id", "log_date"),)


class Todo(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("todos.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    title = Column(String, nullable=False)
    completed = Column(Boolean, default=False)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="todos")
    category = relationship("Category", back_populates="todos")
    parent = relationship("Todo", back_populates="children", remote_side=[id])
    children = relationship("Todo", back_populates="parent", cascade="all, delete-orphan",
                            order_by="Todo.order_index, Todo.id")


class Tracker(Base):
    __tablename__ = "trackers"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    order_index = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="trackers")
    entries = relationship("TrackerEntry", back_populates="tracker", cascade="all, delete-orphan")


class TrackerEntry(Base):
    __tablename__ = "tracker_entries"

    id = Column(Integer, primary_key=True)
    tracker_id = Column(Integer, ForeignKey("trackers.id"), nullable=False)
    entry_date = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    notes = Column(String)
    logged_at = Column(DateTime, server_default=func.now())

    tracker = relationship("Tracker", back_populates="entries")

    __table_args__ = (UniqueConstraint("tracker_id", "entry_date"),)


def create_tables():
    Base.metadata.create_all(engine)
