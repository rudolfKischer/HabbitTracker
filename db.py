import random
from datetime import datetime, timedelta

from sqlalchemy import select, func, case, cast, Integer
from sqlalchemy.orm import Session

from models import SessionLocal, Habit, HabitLog, User, Todo, Category, Tracker, TrackerEntry, ScheduleBlock, create_tables, engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    create_tables()
    _migrate_category_columns()
    _migrate_start_date()
    _migrate_metric_goal()


def _migrate_category_columns():
    """Add category_id columns to habits/todos if they don't exist yet."""
    import sqlite3
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        for table in ("habits", "todos"):
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
            if "category_id" not in cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN category_id INTEGER REFERENCES categories(id)")
        raw.commit()
    finally:
        raw.close()


def _migrate_start_date():
    """Add start_date column to habits and backfill from created_at."""
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cols = [r[1] for r in cur.execute("PRAGMA table_info(habits)").fetchall()]
        if "start_date" not in cols:
            cur.execute("ALTER TABLE habits ADD COLUMN start_date TEXT")
            # Backfill existing habits: use created_at date (or earliest log date)
            cur.execute("""
                UPDATE habits SET start_date = date(created_at)
                WHERE start_date IS NULL AND created_at IS NOT NULL
            """)
            # Fallback for any remaining nulls
            cur.execute("""
                UPDATE habits SET start_date = (
                    SELECT MIN(log_date) FROM habit_logs WHERE habit_logs.habit_id = habits.id
                )
                WHERE start_date IS NULL
            """)
            # Last resort: use today
            cur.execute(f"""
                UPDATE habits SET start_date = '{datetime.now().date().isoformat()}'
                WHERE start_date IS NULL
            """)
        raw.commit()
    finally:
        raw.close()


def _migrate_metric_goal():
    """Add metric_goal column to habit_logs and backfill from habit's current metric_default."""
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cols = [r[1] for r in cur.execute("PRAGMA table_info(habit_logs)").fetchall()]
        if "metric_goal" not in cols:
            cur.execute("ALTER TABLE habit_logs ADD COLUMN metric_goal REAL")
            # Backfill: set metric_goal to the habit's current metric_default
            cur.execute("""
                UPDATE habit_logs SET metric_goal = (
                    SELECT metric_default FROM habits WHERE habits.id = habit_logs.habit_id
                )
                WHERE metric_goal IS NULL
            """)
        raw.commit()
    finally:
        raw.close()


# ── User queries ──────────────────────────────────────────────────────────────

def get_or_create_user(db: Session, email: str, name: str, google_id: str = None) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, name=name, google_id=google_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: int) -> User:
    return db.get(User, user_id)


# ── Habit queries ─────────────────────────────────────────────────────────────

def get_habits(db: Session, user_id: int, active_only: bool = True):
    q = db.query(Habit).filter(Habit.user_id == user_id)
    if active_only:
        q = q.filter(Habit.active == True)
    return q.order_by(Habit.order_index, Habit.id).all()


def get_habit(db: Session, habit_id: int, user_id: int) -> Habit:
    return (
        db.query(Habit)
        .filter(Habit.id == habit_id, Habit.user_id == user_id)
        .first()
    )


def create_habit(db: Session, user_id: int, name: str, description: str,
                 metric_enabled: bool, metric_unit: str, metric_default,
                 metric_max, metric_step) -> Habit:
    max_order = (
        db.query(func.coalesce(func.max(Habit.order_index), 0))
        .filter(Habit.user_id == user_id)
        .scalar()
    )
    habit = Habit(
        user_id=user_id,
        name=name,
        description=description or None,
        metric_enabled=metric_enabled,
        metric_unit=metric_unit or None,
        metric_default=float(metric_default) if metric_default else None,
        metric_max=float(metric_max) if metric_max else None,
        metric_step=float(metric_step) if metric_step else 0.5,
        order_index=max_order + 1,
        start_date=datetime.now().date().isoformat(),
    )
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit


def update_habit(db: Session, habit_id: int, user_id: int, name: str, description: str,
                 metric_enabled: bool, metric_unit: str, metric_default,
                 metric_max, metric_step, viewing_date: str = None) -> Habit:
    habit = get_habit(db, habit_id, user_id)
    if not habit:
        return None
    habit.name = name
    habit.description = description or None
    habit.metric_enabled = metric_enabled
    habit.metric_unit = metric_unit or None
    new_default = float(metric_default) if metric_default else None
    habit.metric_default = new_default
    habit.metric_max = float(metric_max) if metric_max else None
    habit.metric_step = float(metric_step) if metric_step else 0.5

    # Update the snapshot for the day being viewed so the page reflects the change
    if viewing_date and new_default is not None:
        log = get_log(db, habit_id, viewing_date)
        if log:
            log.metric_goal = new_default
            # Re-evaluate auto-complete against the new goal
            if metric_enabled and log.metric_value is not None:
                log.completed = log.metric_value >= new_default

    db.commit()
    db.refresh(habit)
    return habit


def delete_habit(db: Session, habit_id: int, user_id: int):
    habit = get_habit(db, habit_id, user_id)
    if habit:
        db.delete(habit)
        db.commit()


def reorder_habit(db: Session, habit_id: int, user_id: int, direction: str):
    habit = get_habit(db, habit_id, user_id)
    if not habit:
        return

    if direction == "up":
        swap = (
            db.query(Habit)
            .filter(Habit.user_id == user_id, Habit.order_index < habit.order_index)
            .order_by(Habit.order_index.desc())
            .first()
        )
    else:
        swap = (
            db.query(Habit)
            .filter(Habit.user_id == user_id, Habit.order_index > habit.order_index)
            .order_by(Habit.order_index.asc())
            .first()
        )

    if swap:
        habit.order_index, swap.order_index = swap.order_index, habit.order_index
        db.commit()


def reorder_habits(db: Session, user_id: int, ordered_ids: list[int]):
    """Batch reorder habits by setting order_index from the given list."""
    for idx, habit_id in enumerate(ordered_ids):
        habit = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == user_id).first()
        if habit:
            habit.order_index = idx
    db.commit()


# ── Log queries ───────────────────────────────────────────────────────────────

def get_log(db: Session, habit_id: int, log_date: str) -> HabitLog:
    return (
        db.query(HabitLog)
        .filter(HabitLog.habit_id == habit_id, HabitLog.log_date == log_date)
        .first()
    )


def toggle_habit(db: Session, habit_id: int, log_date: str) -> HabitLog:
    habit = db.get(Habit, habit_id)
    log = get_log(db, habit_id, log_date)

    if log:
        log.completed = not log.completed
    else:
        log = HabitLog(habit_id=habit_id, log_date=log_date, completed=True)
        db.add(log)

    # Snapshot the goal only on first creation; don't overwrite past snapshots
    if habit.metric_enabled and habit.metric_default is not None:
        if log.metric_goal is None:
            log.metric_goal = habit.metric_default
        goal = log.metric_goal
        log.metric_value = goal if log.completed else 0

    db.commit()
    db.refresh(log)
    return log


def save_log_detail(db: Session, habit_id: int, log_date: str,
                    rating, metric_value, notes) -> HabitLog:
    habit = db.get(Habit, habit_id)
    log = get_log(db, habit_id, log_date)
    if log:
        log.rating = int(rating) if rating else None
        log.metric_value = float(metric_value) if metric_value else None
        log.notes = notes or None
        # Don't overwrite the snapshotted goal — it belongs to the day it was created
    else:
        log = HabitLog(
            habit_id=habit_id,
            log_date=log_date,
            completed=False,
            rating=int(rating) if rating else None,
            metric_value=float(metric_value) if metric_value else None,
            metric_goal=habit.metric_default if habit and habit.metric_enabled else None,
            notes=notes or None,
        )
        db.add(log)

    # Auto-complete when metric value meets/exceeds the goal that was in effect
    if habit and habit.metric_enabled and log.metric_value is not None:
        goal = log.metric_goal if log.metric_goal else habit.metric_default
        if goal:
            log.completed = log.metric_value >= goal

    db.commit()
    db.refresh(log)
    return log


# ── Aggregation queries ──────────────────────────────────────────────────────

def get_today_summary(db: Session, user_id: int, log_date: str) -> dict:
    habits = db.query(Habit).filter(
        Habit.user_id == user_id, Habit.active == True,
        (Habit.start_date == None) | (Habit.start_date <= log_date),
    ).all()
    total = len(habits)
    habit_ids = [h.id for h in habits]
    done = (
        db.query(func.count(HabitLog.id))
        .filter(HabitLog.habit_id.in_(habit_ids), HabitLog.log_date == log_date, HabitLog.completed == True)
        .scalar()
    ) if habit_ids else 0
    return {"total": total, "done": done}


def get_habits_with_logs(db: Session, user_id: int, log_date: str) -> list[dict]:
    habits = [h for h in get_habits(db, user_id)
              if not h.start_date or h.start_date <= log_date]
    result = []
    for h in habits:
        log = get_log(db, h.id, log_date)
        completed = log.completed if log else False
        metric_value = log.metric_value if log else None

        # Compute completion percentage for color coding.
        # Use the snapshotted goal (metric_goal) so changing the goal doesn't affect past entries.
        goal = log.metric_goal if log and log.metric_goal else h.metric_default
        if completed:
            completion_pct = 100
        elif h.metric_enabled and goal and metric_value is not None:
            completion_pct = min(round(metric_value / goal * 100), 100)
        else:
            completion_pct = 0

        result.append({
            "id": h.id,
            "name": h.name,
            "description": h.description,
            "category_id": h.category_id,
            "metric_enabled": h.metric_enabled,
            "metric_unit": h.metric_unit,
            "metric_default": goal,  # effective goal: snapshot if available, else current default
            "metric_max": h.metric_max,
            "completed": completed,
            "metric_value": metric_value,
            "completion_pct": completion_pct,
        })
    return result


def get_week_overview(db: Session, user_id: int, current_date: str) -> dict:
    """Return per-habit completion data for the calendar week (Mon-Sun) containing current_date."""
    from datetime import date as date_cls
    d = date_cls.fromisoformat(current_date)
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    dates = [(monday + timedelta(days=i)).isoformat() for i in range(7)]
    # Only include habits that started on or before the last day of the week
    habits = [h for h in get_habits(db, user_id)
              if not h.start_date or h.start_date <= sunday.isoformat()]
    rows = []
    for h in habits:
        logs = (
            db.query(HabitLog)
            .filter(
                HabitLog.habit_id == h.id,
                HabitLog.log_date.in_(dates),
            )
            .all()
        )
        log_map = {l.log_date: l for l in logs}
        days = []
        for dt in dates:
            # If habit didn't exist yet on this day, mark as N/A
            if h.start_date and dt < h.start_date:
                days.append({"date": dt, "pct": None, "metric_value": None})
                continue
            log = log_map.get(dt)
            if log and log.completed:
                pct = 100
            elif log and not log.completed and h.metric_enabled and log.metric_value is not None:
                goal = log.metric_goal if log.metric_goal else h.metric_default
                pct = min(round(log.metric_value / goal * 100), 100) if goal else 0
            else:
                pct = 0
            metric_val = log.metric_value if log else None
            days.append({"date": dt, "pct": pct, "metric_value": metric_val})
        rows.append({"id": h.id, "name": h.name, "metric_enabled": h.metric_enabled,
                      "metric_unit": h.metric_unit, "metric_default": h.metric_default,
                      "days": days})
    prev_week = (monday - timedelta(days=7)).isoformat()
    next_week = (monday + timedelta(days=7)).isoformat() if sunday < date_cls.today() else None
    return {"dates": dates, "habits": rows, "monday": monday.isoformat(),
            "prev_week": prev_week, "next_week": next_week}


def get_heatmap_data(db: Session, user_id: int, start_date: str, end_date: str) -> dict:
    habits = db.query(Habit).filter(Habit.user_id == user_id, Habit.active == True).all()
    if not habits:
        return {}
    habit_ids = [h.id for h in habits]
    # Build a map of start_dates for per-day totals
    habit_start_dates = [h.start_date for h in habits]
    rows = (
        db.query(
            HabitLog.log_date,
            func.sum(case((HabitLog.completed == True, 1), else_=0)).label("done"),
        )
        .filter(
            HabitLog.habit_id.in_(habit_ids),
            HabitLog.log_date.between(start_date, end_date),
        )
        .group_by(HabitLog.log_date)
        .all()
    )
    result = {}
    for row in rows:
        # Count how many habits existed on this specific date
        total_on_day = sum(1 for sd in habit_start_dates if not sd or sd <= row.log_date)
        pct = round(row.done / total_on_day * 100) if total_on_day > 0 else 0
        result[row.log_date] = pct
    return result


def get_stats_data(db: Session, habit_id: int, start_date: str) -> list[dict]:
    logs = (
        db.query(HabitLog)
        .filter(HabitLog.habit_id == habit_id, HabitLog.log_date >= start_date)
        .order_by(HabitLog.log_date)
        .all()
    )
    return [
        {
            "log_date": l.log_date,
            "completed": l.completed,
            "rating": l.rating,
            "metric_value": l.metric_value,
        }
        for l in logs
    ]


# ── Category queries ──────────────────────────────────────────────────────────

def get_categories(db: Session, user_id: int):
    return (
        db.query(Category)
        .filter(Category.user_id == user_id)
        .order_by(Category.order_index, Category.id)
        .all()
    )


def get_category(db: Session, category_id: int, user_id: int):
    return (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user_id)
        .first()
    )


def create_category(db: Session, user_id: int, name: str):
    max_order = (
        db.query(func.coalesce(func.max(Category.order_index), 0))
        .filter(Category.user_id == user_id)
        .scalar()
    )
    cat = Category(user_id=user_id, name=name, order_index=max_order + 1)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def rename_category(db: Session, category_id: int, user_id: int, name: str):
    cat = get_category(db, category_id, user_id)
    if not cat:
        return None
    cat.name = name
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, category_id: int, user_id: int):
    cat = get_category(db, category_id, user_id)
    if not cat:
        return
    # Unassign habits and todos from this category
    db.query(Habit).filter(Habit.category_id == category_id).update({"category_id": None})
    db.query(Todo).filter(Todo.category_id == category_id).update({"category_id": None})
    db.delete(cat)
    db.commit()


def reorder_categories(db: Session, user_id: int, ordered_ids: list[int]):
    """Set category order based on a list of category IDs."""
    cats = get_categories(db, user_id)
    cat_map = {c.id: c for c in cats}
    for i, cid in enumerate(ordered_ids):
        if cid in cat_map:
            cat_map[cid].order_index = i
    db.commit()


def set_habit_category(db: Session, habit_id: int, user_id: int, category_id: int = None):
    habit = get_habit(db, habit_id, user_id)
    if not habit:
        return None
    habit.category_id = category_id
    db.commit()
    db.refresh(habit)
    return habit


def set_todo_category(db: Session, todo_id: int, user_id: int, category_id: int = None):
    todo = get_todo(db, todo_id, user_id)
    if not todo:
        return None
    todo.category_id = category_id
    db.commit()
    db.refresh(todo)
    return todo


def get_habits_with_logs_grouped(db: Session, user_id: int, log_date: str):
    """Return habits grouped by category: [{"category": cat_or_none, "habits": [...]}, ...]"""
    habits = get_habits_with_logs(db, user_id, log_date)
    categories = get_categories(db, user_id)

    # Build a map from habit_id to category_id
    all_habits = get_habits(db, user_id)
    habit_cat_map = {h.id: h.category_id for h in all_habits}

    # Group habits by category
    cat_map = {c.id: c for c in categories}
    groups = {}
    for h in habits:
        cat_id = habit_cat_map.get(h["id"])
        if cat_id not in groups:
            groups[cat_id] = []
        groups[cat_id].append(h)

    result = []
    # Uncategorized first
    if None in groups:
        result.append({"category": None, "habits": groups[None]})
    # Then categories in order
    for cat in categories:
        if cat.id in groups:
            result.append({"category": {"id": cat.id, "name": cat.name}, "habits": groups[cat.id]})

    return result


def get_todo_tree_grouped(db: Session, user_id: int):
    """Return todos grouped by category, each group having active/completed tree."""
    all_todos = (
        db.query(Todo)
        .filter(Todo.user_id == user_id)
        .order_by(Todo.order_index, Todo.id)
        .all()
    )
    categories = get_categories(db, user_id)

    # Only group top-level todos by category; children inherit from parent
    todo_map = {}
    for t in all_todos:
        todo_map[t.id] = {
            "id": t.id,
            "title": t.title,
            "completed": t.completed,
            "parent_id": t.parent_id,
            "category_id": t.category_id,
            "children": [],
        }

    # Build tree
    roots = []
    for t in all_todos:
        d = todo_map[t.id]
        if t.parent_id and t.parent_id in todo_map:
            todo_map[t.parent_id]["children"].append(d)
        else:
            roots.append(d)

    # Group roots by category
    cat_map = {c.id: c for c in categories}
    groups = {}
    for r in roots:
        cat_id = r.get("category_id")
        if cat_id not in groups:
            groups[cat_id] = []
        groups[cat_id].append(r)

    result = []
    # Uncategorized first
    if None in groups:
        todos_uncat = groups[None]
        active = [r for r in todos_uncat if not _is_fully_completed(r)]
        completed = [r for r in todos_uncat if _is_fully_completed(r)]
        result.append({
            "category": None,
            "todos": {"active": active, "completed": completed},
        })
    # Then categories in order
    for cat in categories:
        if cat.id in groups:
            todos_in_cat = groups[cat.id]
            active = [r for r in todos_in_cat if not _is_fully_completed(r)]
            completed = [r for r in todos_in_cat if _is_fully_completed(r)]
            result.append({
                "category": {"id": cat.id, "name": cat.name},
                "todos": {"active": active, "completed": completed},
            })

    return result


# ── Todo queries ─────────────────────────────────────────────────────────────

def get_todos(db: Session, user_id: int):
    """Return all top-level todos with their children loaded."""
    return (
        db.query(Todo)
        .filter(Todo.user_id == user_id, Todo.parent_id == None)
        .order_by(Todo.order_index, Todo.id)
        .all()
    )


def get_todo(db: Session, todo_id: int, user_id: int):
    return (
        db.query(Todo)
        .filter(Todo.id == todo_id, Todo.user_id == user_id)
        .first()
    )


def create_todo(db: Session, user_id: int, title: str, parent_id: int = None, category_id: int = None):
    # Validate parent belongs to same user
    if parent_id:
        parent = get_todo(db, parent_id, user_id)
        if not parent:
            return None
    max_order = (
        db.query(func.coalesce(func.max(Todo.order_index), 0))
        .filter(Todo.user_id == user_id, Todo.parent_id == parent_id)
        .scalar()
    )
    todo = Todo(user_id=user_id, title=title, parent_id=parent_id,
                category_id=category_id, order_index=max_order + 1)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo


def toggle_todo(db: Session, todo_id: int, user_id: int):
    todo = get_todo(db, todo_id, user_id)
    if not todo:
        return None
    todo.completed = not todo.completed
    # If completing a parent, complete all children too
    if todo.completed:
        _complete_children(db, todo)
    # If uncompleting, uncheck parent if it was completed
    if not todo.completed and todo.parent_id:
        parent = db.get(Todo, todo.parent_id)
        if parent and parent.completed:
            parent.completed = False
    db.commit()
    db.refresh(todo)
    return todo


def _complete_children(db: Session, todo):
    for child in todo.children:
        child.completed = True
        _complete_children(db, child)


def update_todo(db: Session, todo_id: int, user_id: int, title: str):
    todo = get_todo(db, todo_id, user_id)
    if not todo:
        return None
    todo.title = title
    db.commit()
    db.refresh(todo)
    return todo


def delete_todo(db: Session, todo_id: int, user_id: int):
    todo = get_todo(db, todo_id, user_id)
    if todo:
        db.delete(todo)
        db.commit()


def reparent_todo(db: Session, todo_id: int, user_id: int,
                  parent_id: int = None, before_id: int = None):
    """Move a todo to a new parent (or root). Optionally place before a sibling."""
    todo = get_todo(db, todo_id, user_id)
    if not todo:
        return None
    # Prevent parenting to self or own descendant
    if parent_id:
        if parent_id == todo_id:
            return None
        # Walk up from parent to check for cycles
        check = db.get(Todo, parent_id)
        while check:
            if check.id == todo_id:
                return None
            check = db.get(Todo, check.parent_id) if check.parent_id else None
    todo.parent_id = parent_id
    # Reorder: place before `before_id` if given, otherwise at the end
    siblings = (
        db.query(Todo)
        .filter(Todo.user_id == user_id, Todo.parent_id == parent_id, Todo.id != todo_id)
        .order_by(Todo.order_index, Todo.id)
        .all()
    )
    new_order = []
    placed = False
    for s in siblings:
        if before_id and s.id == before_id and not placed:
            new_order.append(todo)
            placed = True
        new_order.append(s)
    if not placed:
        new_order.append(todo)
    for i, t in enumerate(new_order):
        t.order_index = i
    db.commit()
    db.refresh(todo)
    return todo


def _is_fully_completed(todo_dict):
    """A todo is fully completed if it and all descendants are completed."""
    if not todo_dict["completed"]:
        return False
    return all(_is_fully_completed(c) for c in todo_dict["children"])


def get_todo_tree(db: Session, user_id: int):
    """Return {'active': [...], 'completed': [...]} with nested tree structures."""
    all_todos = (
        db.query(Todo)
        .filter(Todo.user_id == user_id)
        .order_by(Todo.order_index, Todo.id)
        .all()
    )
    todo_map = {}
    for t in all_todos:
        todo_map[t.id] = {
            "id": t.id,
            "title": t.title,
            "completed": t.completed,
            "parent_id": t.parent_id,
            "category_id": t.category_id,
            "children": [],
        }
    roots = []
    for t in all_todos:
        d = todo_map[t.id]
        if t.parent_id and t.parent_id in todo_map:
            todo_map[t.parent_id]["children"].append(d)
        else:
            roots.append(d)
    active = [r for r in roots if not _is_fully_completed(r)]
    completed = [r for r in roots if _is_fully_completed(r)]
    return {"active": active, "completed": completed}


# ── Tracker queries ──────────────────────────────────────────────────────────

def get_trackers(db: Session, user_id: int, active_only: bool = True):
    q = db.query(Tracker).filter(Tracker.user_id == user_id)
    if active_only:
        q = q.filter(Tracker.active == True)
    return q.order_by(Tracker.order_index, Tracker.id).all()


def get_tracker(db: Session, tracker_id: int, user_id: int):
    return db.query(Tracker).filter(Tracker.id == tracker_id, Tracker.user_id == user_id).first()


def create_tracker(db: Session, user_id: int, name: str, unit: str):
    max_idx = db.query(func.max(Tracker.order_index)).filter(Tracker.user_id == user_id).scalar() or 0
    tracker = Tracker(user_id=user_id, name=name, unit=unit, order_index=max_idx + 1)
    db.add(tracker)
    db.commit()
    db.refresh(tracker)
    return tracker


def update_tracker(db: Session, tracker_id: int, user_id: int, name: str, unit: str):
    tracker = get_tracker(db, tracker_id, user_id)
    if not tracker:
        return None
    tracker.name = name
    tracker.unit = unit
    db.commit()
    return tracker


def delete_tracker(db: Session, tracker_id: int, user_id: int):
    tracker = get_tracker(db, tracker_id, user_id)
    if tracker:
        db.delete(tracker)
        db.commit()


def save_tracker_entry(db: Session, tracker_id: int, entry_date: str, value: float, notes: str = None):
    entry = db.query(TrackerEntry).filter(
        TrackerEntry.tracker_id == tracker_id,
        TrackerEntry.entry_date == entry_date,
    ).first()
    if entry:
        entry.value = value
        entry.notes = notes
    else:
        entry = TrackerEntry(tracker_id=tracker_id, entry_date=entry_date, value=value, notes=notes)
        db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def delete_tracker_entry(db: Session, entry_id: int, tracker_id: int):
    entry = db.query(TrackerEntry).filter(
        TrackerEntry.id == entry_id,
        TrackerEntry.tracker_id == tracker_id,
    ).first()
    if entry:
        db.delete(entry)
        db.commit()


def get_tracker_entries(db: Session, tracker_id: int, start_date: str = None):
    q = db.query(TrackerEntry).filter(TrackerEntry.tracker_id == tracker_id)
    if start_date:
        q = q.filter(TrackerEntry.entry_date >= start_date)
    return q.order_by(TrackerEntry.entry_date).all()


# ── Schedule block queries ────────────────────────────────────────────────────

def get_schedule_blocks(db: Session, user_id: int):
    return db.query(ScheduleBlock).filter(
        ScheduleBlock.user_id == user_id
    ).order_by(ScheduleBlock.start_time, ScheduleBlock.id).all()


def get_schedule_block(db: Session, block_id: int, user_id: int):
    return db.query(ScheduleBlock).filter(
        ScheduleBlock.id == block_id, ScheduleBlock.user_id == user_id
    ).first()


def create_schedule_block(db: Session, user_id: int, label: str, start_time: str, end_time: str, color: str = None):
    block = ScheduleBlock(user_id=user_id, label=label, start_time=start_time, end_time=end_time, color=color)
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


def update_schedule_block(db: Session, block_id: int, user_id: int, label: str, start_time: str, end_time: str, color: str = None):
    block = get_schedule_block(db, block_id, user_id)
    if block:
        block.label = label
        block.start_time = start_time
        block.end_time = end_time
        block.color = color
        db.commit()
        db.refresh(block)
    return block


def delete_schedule_block(db: Session, block_id: int, user_id: int):
    block = get_schedule_block(db, block_id, user_id)
    if block:
        db.delete(block)
        db.commit()


# ── Seed data (demo only) ────────────────────────────────────────────────────

def seed_demo_habits(db: Session, user_id: int):
    """Seed demo habits for a new user (only if they have none)."""
    existing = db.query(Habit).filter(Habit.user_id == user_id).count()
    if existing > 0:
        return

    # (name, desc, metric_enabled, unit, default, max, step)
    demo_habits = [
        ("Brushed teeth", None, False, None, None, None, None),
        ("Showered", None, False, None, None, None, None),
        ("Read for 30 min", None, True, "pages", 20.0, 100.0, 5),
        ("Row", None, True, "km", 3.0, 10.0, 0.5),
        ("Exercised", None, False, None, None, None, None),
        ("Applied to jobs", None, True, "applications", 10.0, 20.0, 1),
        ("Leetcode", None, True, "problems", 1.0, 5.0, 1),
        ("Slept 7 hours", None, False, None, None, None, None),
        ("Bed before midnight", None, False, None, None, None, None),
        ("Wake before 7am", None, False, None, None, None, None),
    ]

    for i, (name, desc, metric, unit, default, mx, step) in enumerate(demo_habits):
        db.add(Habit(
            user_id=user_id, name=name, description=desc,
            metric_enabled=metric, metric_unit=unit,
            metric_default=default, metric_max=mx,
            metric_step=step or 0.5, order_index=i,
        ))
    db.commit()


def seed_demo_data(db: Session, user_id: int):
    """Seed demo habits + randomized historical log data."""
    seed_demo_habits(db, user_id)
    habits = get_habits(db, user_id)
    if not habits:
        return

    # Skip if there's already log data
    any_logs = (
        db.query(HabitLog)
        .filter(HabitLog.habit_id.in_([h.id for h in habits]))
        .first()
    )
    if any_logs:
        return

    today = datetime.now().date()

    # Each habit has a base adherence rate
    habit_tendencies = {h.id: random.uniform(0.35, 0.85) for h in habits}

    for day_offset in range(120):
        d = (today - timedelta(days=day_offset)).isoformat()
        # Day-level modifier: some days you do more, some less
        day_modifier = random.gauss(0, 0.2)

        for h in habits:
            chance = min(max(habit_tendencies[h.id] + day_modifier, 0.05), 0.95)
            if random.random() < chance:
                completed = random.random() < 0.85
                log = HabitLog(
                    habit_id=h.id,
                    log_date=d,
                    completed=completed,
                )
                if h.metric_enabled and h.metric_default and completed:
                    log.metric_value = round(
                        h.metric_default * random.uniform(0.3, 1.4), 1
                    )
                db.add(log)

    db.commit()


def clear_user_data(db: Session, user_id: int):
    """Delete all habits and logs for a user."""
    habits = db.query(Habit).filter(Habit.user_id == user_id).all()
    for h in habits:
        db.delete(h)
    db.commit()


def reseed_demo_data(db: Session, user_id: int):
    """Clear everything and re-seed fresh demo data."""
    clear_user_data(db, user_id)
    seed_demo_data(db, user_id)
