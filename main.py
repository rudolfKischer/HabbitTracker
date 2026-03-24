import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from typing import Optional

import db as database
from models import SessionLocal
from auth import oauth, is_google_configured, get_current_user_id

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"),
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.filters["weekday"] = lambda s: date.fromisoformat(s).weekday()

database.init_db()


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def display_date_label(date_str: str) -> str:
    """Return 'Today', 'Yesterday', or the formatted date."""
    d = date.fromisoformat(date_str)
    t = date.today()
    if d == t:
        return "Today"
    if d == t - timedelta(days=1):
        return "Yesterday"
    return d.strftime("%A, %B %-d")


def clamp_date(date_str: str) -> str:
    """Ensure date doesn't go into the future."""
    d = date.fromisoformat(date_str)
    t = date.today()
    if d > t:
        return t.isoformat()
    return date_str


def prev_date(date_str: str) -> str:
    return (date.fromisoformat(date_str) - timedelta(days=1)).isoformat()


def next_date(date_str: str) -> str | None:
    n = date.fromisoformat(date_str) + timedelta(days=1)
    if n > date.today():
        return None
    return n.isoformat()


def is_dev_mode() -> bool:
    return not is_google_configured()


def _todo_list_ctx(request: Request, db: Session, user_id: int) -> dict:
    """Common context for rendering todo_list.html partial."""
    return {
        "request": request,
        "todos": database.get_todo_tree(db, user_id),
        "todo_groups": database.get_todo_tree_grouped(db, user_id),
        "categories": database.get_categories(db, user_id),
    }


async def get_or_create_guest(request: Request, db: Session) -> int:
    """Get or create a guest user tied to the session cookie."""
    user = database.get_or_create_user(db, "guest@local", "Guest")
    request.session["user_id"] = user.id
    request.session["is_guest"] = True
    return user.id


async def require_user(request: Request, db: Session) -> int | None:
    """Returns user_id from session, or None if not logged in."""
    user_id = get_current_user_id(request)
    if user_id:
        user = database.get_user_by_id(db, user_id)
        if user:
            return user_id
    return None


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "google_enabled": is_google_configured(),
        "dev_mode": is_dev_mode(),
    })


@app.get("/auth/google")
async def auth_google(request: Request):
    if not is_google_configured():
        return RedirectResponse("/")
    redirect_uri = request.url_for("auth_google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})
    email = userinfo.get("email", "")
    name = userinfo.get("name", email)
    google_id = userinfo.get("sub", "")

    user = database.get_or_create_user(db, email, name, google_id)
    request.session["user_id"] = user.id
    request.session["is_guest"] = False
    return RedirectResponse("/app")


@app.get("/auth/dev-login")
async def dev_login(request: Request, db: Session = Depends(get_db)):
    """Dev mode: login as a test user."""
    if not is_dev_mode():
        return RedirectResponse("/login")
    user = database.get_or_create_user(db, "dev@test", "Test User")
    request.session["user_id"] = user.id
    request.session["is_guest"] = False
    return RedirectResponse("/app")


@app.get("/auth/guest")
async def guest_login(request: Request, db: Session = Depends(get_db)):
    """Start as guest — data stored in cookie session."""
    await get_or_create_guest(request, db)
    return RedirectResponse("/app")


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")


# ── Landing page ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    # If already logged in, redirect to app
    user_id = get_current_user_id(request)
    if user_id:
        return RedirectResponse("/app")
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "google_enabled": is_google_configured(),
        "dev_mode": is_dev_mode(),
    })


# ── App pages ─────────────────────────────────────────────────────────────────

@app.get("/app", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db),
                date: Optional[str] = None):
    user_id = await require_user(request, db)
    if not user_id:
        return RedirectResponse("/")

    log_date = clamp_date(date) if date else today_str()
    habit_groups = database.get_habits_with_logs_grouped(db, user_id, log_date)
    summary = database.get_today_summary(db, user_id, log_date)
    week = database.get_week_overview(db, user_id, log_date)
    recent_days = database.get_recent_days_overview(db, user_id, log_date, n=3)
    categories = database.get_categories(db, user_id)
    user = database.get_user_by_id(db, user_id)
    # Flat list for backward compat (progress bar, week grid, etc.)
    habits = []
    for g in habit_groups:
        habits.extend(g["habits"])
    return templates.TemplateResponse("index.html", {
        "request": request,
        "habits": habits,
        "habit_groups": habit_groups,
        "summary": summary,
        "log_date": log_date,
        "display_date": display_date_label(log_date),
        "prev_date": prev_date(log_date),
        "next_date": next_date(log_date),
        "is_today": log_date == today_str(),
        "user": user,
        "is_guest": request.session.get("is_guest", False),
        "week": week,
        "recent_days": recent_days,
        "categories": categories,
        "today": today_str(),
    })


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return RedirectResponse("/")

    habits = database.get_habits(db, user_id)
    user = database.get_user_by_id(db, user_id)
    return templates.TemplateResponse("stats.html", {
        "request": request,
        "habits": habits,
        "display_date": display_date_label(today_str()),
        "user": user,
        "is_guest": request.session.get("is_guest", False),
    })


@app.get("/trackers", response_class=HTMLResponse)
async def trackers_page(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    trackers = database.get_trackers(db, user_id)
    user = database.get_user_by_id(db, user_id)
    return templates.TemplateResponse("trackers.html", {
        "request": request,
        "trackers": trackers,
        "display_date": display_date_label(today_str()),
        "user": user,
        "is_guest": request.session.get("is_guest", False),
    })


@app.get("/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    blocks = database.get_schedule_blocks(db, user_id)
    user = database.get_user_by_id(db, user_id)
    return templates.TemplateResponse("schedule.html", {
        "request": request,
        "blocks": blocks,
        "display_date": display_date_label(today_str()),
        "user": user,
        "is_guest": request.session.get("is_guest", False),
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return RedirectResponse("/")

    habits = database.get_habits(db, user_id)
    categories = database.get_categories(db, user_id)
    user = database.get_user_by_id(db, user_id)
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "habits": habits,
        "categories": categories,
        "display_date": display_date_label(today_str()),
        "user": user,
        "is_guest": request.session.get("is_guest", False),
    })


# ── Week view ────────────────────────────────────────────────────────────────

@app.get("/app/week", response_class=HTMLResponse)
async def week_view(request: Request, db: Session = Depends(get_db),
                    week: Optional[str] = None):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)

    ref_date = clamp_date(week) if week else today_str()
    week_data = database.get_week_overview(db, user_id, ref_date)
    # Use the page's current log_date from referer, or today
    log_date = today_str()
    return templates.TemplateResponse("partials/week_grid.html", {
        "request": request,
        "week": week_data,
        "log_date": log_date,
        "today": today_str(),
    })


@app.post("/habits/{habit_id}/week-toggle", response_class=HTMLResponse)
async def week_toggle(request: Request, habit_id: int,
                      db: Session = Depends(get_db),
                      log_date: Optional[str] = Form(None),
                      week: Optional[str] = Form(None)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)

    log_date = clamp_date(log_date) if log_date else today_str()
    habit = database.get_habit(db, habit_id, user_id)
    if not habit:
        return HTMLResponse(status_code=404)

    database.toggle_habit(db, habit_id, log_date)
    ref_date = week if week else log_date
    week_data = database.get_week_overview(db, user_id, ref_date)
    # Determine the page's current log_date from query params
    page_date = today_str()
    return templates.TemplateResponse("partials/week_grid.html", {
        "request": request,
        "week": week_data,
        "log_date": page_date,
        "today": today_str(),
    })


@app.post("/habits/{habit_id}/recent-toggle", response_class=HTMLResponse)
async def recent_toggle(request: Request, habit_id: int,
                        db: Session = Depends(get_db),
                        log_date: Optional[str] = Form(None)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    log_date = clamp_date(log_date) if log_date else today_str()
    habit = database.get_habit(db, habit_id, user_id)
    if not habit:
        return HTMLResponse(status_code=404)
    database.toggle_habit(db, habit_id, log_date)
    recent_days = database.get_recent_days_overview(db, user_id, today_str(), n=3)
    return templates.TemplateResponse("partials/recent_grid.html", {
        "request": request,
        "recent_days": recent_days,
        "log_date": today_str(),
    })


# ── Single habit row (GET, for syncing after week-toggle) ─────────────────────

@app.get("/habits/{habit_id}/row", response_class=HTMLResponse)
async def habit_row_get(request: Request, habit_id: int,
                        db: Session = Depends(get_db),
                        log_date: Optional[str] = None):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    log_date = clamp_date(log_date) if log_date else today_str()
    habits = database.get_habits_with_logs(db, user_id, log_date)
    habit_data = next((h for h in habits if h["id"] == habit_id), None)
    if not habit_data:
        return HTMLResponse(status_code=404)
    return templates.TemplateResponse("partials/habit_row.html", {
        "request": request,
        "habit": habit_data,
        "log_date": log_date,
    })


# ── Habit toggle ──────────────────────────────────────────────────────────────

@app.post("/habits/{habit_id}/toggle", response_class=HTMLResponse)
async def toggle_habit_route(request: Request, habit_id: int,
                             db: Session = Depends(get_db),
                             log_date: Optional[str] = Form(None)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)

    log_date = clamp_date(log_date) if log_date else today_str()
    habit = database.get_habit(db, habit_id, user_id)
    if not habit:
        return HTMLResponse(status_code=404)

    database.toggle_habit(db, habit_id, log_date)
    habits = database.get_habits_with_logs(db, user_id, log_date)
    habit_data = next((h for h in habits if h["id"] == habit_id), None)
    summary = database.get_today_summary(db, user_id, log_date)
    return templates.TemplateResponse("partials/habit_row.html", {
        "request": request,
        "habit": habit_data,
        "log_date": log_date,
        "summary": summary,
    })


# ── Habit detail ──────────────────────────────────────────────────────────────

@app.get("/habits/{habit_id}/detail", response_class=HTMLResponse)
async def get_habit_detail(request: Request, habit_id: int,
                           db: Session = Depends(get_db),
                           log_date: Optional[str] = None):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)

    log_date = clamp_date(log_date) if log_date else today_str()
    habit = database.get_habit(db, habit_id, user_id)
    if not habit:
        return HTMLResponse(status_code=404)

    log = database.get_log(db, habit_id, log_date)
    return templates.TemplateResponse("partials/habit_detail.html", {
        "request": request,
        "habit": habit,
        "log": log,
        "log_date": log_date,
    })


@app.post("/habits/{habit_id}/log", response_class=HTMLResponse)
async def save_log(
    request: Request,
    habit_id: int,
    db: Session = Depends(get_db),
    rating: Optional[str] = Form(None),
    metric_value: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    log_date: Optional[str] = Form(None),
):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)

    log_date = clamp_date(log_date) if log_date else today_str()
    habit = database.get_habit(db, habit_id, user_id)
    if not habit:
        return HTMLResponse(status_code=404)

    database.save_log_detail(db, habit_id, log_date, rating, metric_value, notes)
    log = database.get_log(db, habit_id, log_date)
    return templates.TemplateResponse("partials/habit_detail.html", {
        "request": request,
        "habit": habit,
        "log": log,
        "log_date": log_date,
        "saved": True,
    })


# ── Habit CRUD ────────────────────────────────────────────────────────────────

@app.post("/habits", response_class=HTMLResponse)
async def create_habit_route(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    metric_enabled: Optional[str] = Form(None),
    metric_unit: Optional[str] = Form(None),
    metric_default: Optional[str] = Form(None),
    metric_max: Optional[str] = Form(None),
    metric_step: Optional[str] = Form(None),
):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)

    habit = database.create_habit(
        db, user_id, name, description,
        metric_enabled in ("on", "1", "true"),
        metric_unit, metric_default, metric_max, metric_step,
    )
    return templates.TemplateResponse("partials/settings_row.html", {
        "request": request,
        "habit": habit,
    })


@app.put("/habits/{habit_id}", response_class=HTMLResponse)
async def update_habit_route(
    request: Request,
    habit_id: int,
    db: Session = Depends(get_db),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    metric_enabled: Optional[str] = Form(None),
    metric_unit: Optional[str] = Form(None),
    metric_default: Optional[str] = Form(None),
    metric_max: Optional[str] = Form(None),
    metric_step: Optional[str] = Form(None),
    log_date: Optional[str] = Form(None),
):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)

    viewing_date = clamp_date(log_date) if log_date else today_str()
    habit = database.update_habit(
        db, habit_id, user_id, name, description,
        metric_enabled in ("on", "1", "true"),
        metric_unit, metric_default, metric_max, metric_step,
        viewing_date=viewing_date,
    )
    return templates.TemplateResponse("partials/settings_row.html", {
        "request": request,
        "habit": habit,
    })


@app.delete("/habits/{habit_id}")
async def delete_habit_route(request: Request, habit_id: int, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)

    database.delete_habit(db, habit_id, user_id)
    return HTMLResponse("")


@app.post("/habits/{habit_id}/reorder", response_class=HTMLResponse)
async def reorder_habit_route(
    request: Request,
    habit_id: int,
    db: Session = Depends(get_db),
    direction: str = Form(...),
):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)

    database.reorder_habit(db, habit_id, user_id, direction)
    habits = database.get_habits(db, user_id)
    categories = database.get_categories(db, user_id)
    return templates.TemplateResponse("partials/settings_list.html", {
        "request": request,
        "habits": habits,
        "categories": categories,
    })


@app.post("/habits/quick")
async def quick_create_habit(request: Request, db: Session = Depends(get_db),
                              name: str = Form(...),
                              category_id: Optional[str] = Form(None)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    habit = database.create_habit(
        db, user_id, name.strip(), "", False, "", None, None, 0.5,
    )
    if category_id and category_id.isdigit():
        database.set_habit_category(db, habit.id, user_id, int(category_id))
    return RedirectResponse("/app", status_code=303)


@app.post("/habits/reorder")
async def reorder_habits_batch(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    form = await request.form()
    ordered_ids = [int(x) for x in form.getlist("order[]") if x.isdigit()]
    database.reorder_habits(db, user_id, ordered_ids)
    return JSONResponse({"ok": True})


# ── Theme ─────────────────────────────────────────────────────────────────────

VALID_THEMES = {"green", "teal", "cyan", "blue", "purple", "pink", "orange", "yellow"}

@app.post("/settings/theme")
async def set_theme(request: Request, db: Session = Depends(get_db),
                    color: str = Form(...)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    if color not in VALID_THEMES:
        return HTMLResponse(status_code=400)
    user = database.get_user_by_id(db, user_id)
    user.theme_color = color
    db.commit()
    return HTMLResponse("")


# ── Demo data ─────────────────────────────────────────────────────────────────

@app.post("/settings/load-demo", response_class=HTMLResponse)
async def load_demo_data(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.reseed_demo_data(db, user_id)
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/clear-data", response_class=HTMLResponse)
async def clear_data(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.clear_user_data(db, user_id)
    return RedirectResponse("/settings", status_code=303)


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/heatmap")
async def api_heatmap(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({})

    end = datetime.now().date()
    start = end - timedelta(days=364)
    data = database.get_heatmap_data(db, user_id, start.isoformat(), end.isoformat())
    return JSONResponse(content=data)


@app.get("/api/stats/overview")
async def api_stats_overview(request: Request, db: Session = Depends(get_db),
                             window: str = "month"):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({})

    habits = database.get_habits(db, user_id)
    today = datetime.now().date()
    if window == "week":
        start_d = today - timedelta(days=6)
    elif window == "month":
        start_d = today.replace(day=1)
    elif window == "quarter":
        start_d = today - timedelta(days=90)
    elif window == "year":
        start_d = today - timedelta(days=365)
    elif window == "all":
        start_d = today - timedelta(days=365 * 10)
    else:
        legacy = {"7d": 7, "30d": 30, "90d": 90}
        start_d = today - timedelta(days=legacy.get(window, 30))
    start = start_d.isoformat()

    habit_rates = []
    for h in habits:
        data = database.get_stats_data(db, h.id, start)
        done = sum(1 for d in data if d["completed"])
        # Use all days from earliest record (or window start) to today
        if data:
            earliest = date.fromisoformat(data[0]["log_date"])
            effective_start = max(start_d, earliest)
        else:
            effective_start = start_d
        total_days = (today - effective_start).days + 1
        rate = round(done / total_days * 100) if total_days > 0 else 0
        habit_rates.append({
            "id": h.id,
            "name": h.name,
            "rate": rate,
            "done": done,
            "total_days": total_days,
        })

    habit_rates.sort(key=lambda x: x["rate"], reverse=True)

    total_done = sum(h["done"] for h in habit_rates)
    total_all_days = sum(h["total_days"] for h in habit_rates)
    overall_rate = round(total_done / total_all_days * 100) if total_all_days else 0

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_totals = [0] * 7
    day_done = [0] * 7
    for h in habits:
        data = database.get_stats_data(db, h.id, start)
        for d in data:
            wd = date.fromisoformat(d["log_date"]).weekday()
            day_totals[wd] += 1
            if d["completed"]:
                day_done[wd] += 1
    day_rates = [round(day_done[i] / day_totals[i] * 100) if day_totals[i] else 0 for i in range(7)]

    return JSONResponse({
        "overall_rate": overall_rate,
        "habit_rates": habit_rates,
        "day_of_week": {"labels": day_names, "rates": day_rates},
    })


@app.get("/api/stats/{habit_id}")
async def api_stats(request: Request, habit_id: int, db: Session = Depends(get_db), window: str = "30d"):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({})

    habit = database.get_habit(db, habit_id, user_id)
    if not habit:
        return JSONResponse({"error": "not found"}, status_code=404)

    today = datetime.now().date()
    if window == "week":
        start_d = today - timedelta(days=6)
    elif window == "month":
        start_d = today.replace(day=1)
    elif window == "quarter":
        start_d = today - timedelta(days=90)
    elif window == "year":
        start_d = today - timedelta(days=365)
    elif window == "all":
        start_d = today - timedelta(days=365 * 10)
    else:
        # Legacy support
        legacy = {"7d": 7, "30d": 30, "90d": 90}
        start_d = today - timedelta(days=legacy.get(window, 30))
    start = start_d.isoformat()
    data = database.get_stats_data(db, habit_id, start)

    # Compute summary stats
    # Completion rate: count all days from the later of (window start, earliest record) to today
    completed_days = sum(1 for d in data if d["completed"])
    total_logged = len(data)
    if data:
        earliest_record = date.fromisoformat(data[0]["log_date"])
        effective_start = max(start_d, earliest_record)
    else:
        effective_start = start_d
    total_days = (today - effective_start).days + 1
    completion_rate = round(completed_days / total_days * 100) if total_days > 0 else 0

    # Current streak & best streak
    # Build a dict of date_str -> truly completed
    today = datetime.now().date()
    completed_dates = {}
    for d_entry in data:
        ds = d_entry["log_date"]
        if d_entry["completed"]:
            # For metric habits, only count if metric meets goal
            if habit.metric_enabled and d_entry.get("metric_value") is not None:
                goal = habit.metric_default or 0
                if goal and d_entry["metric_value"] < goal:
                    completed_dates[ds] = False
                    continue
            completed_dates[ds] = True
        else:
            completed_dates[ds] = False

    # Current streak: walk backwards from today
    current_streak = 0
    current_streak_end = None
    d = today
    while True:
        ds = d.isoformat()
        if ds in completed_dates:
            if completed_dates[ds]:
                if current_streak == 0:
                    current_streak_end = ds
                current_streak += 1
            else:
                break
        elif d == today:
            pass
        else:
            break
        d -= timedelta(days=1)

    current_streak_start = None
    if current_streak_end and current_streak > 0:
        end_date = date.fromisoformat(current_streak_end)
        current_streak_start = (end_date - timedelta(days=current_streak - 1)).isoformat()

    # Best streak: walk all calendar days in range
    # Only break streak on days that have a log with completed=False
    # or days with no log (user didn't track that day)
    best_streak = 0
    best_streak_end = None
    streak = 0
    all_days_in_range = (today - start_d).days + 1
    for i in range(all_days_in_range):
        ds = (start_d + timedelta(days=i)).isoformat()
        if completed_dates.get(ds, False):
            streak += 1
            if streak > best_streak:
                best_streak = streak
                best_streak_end = ds
        else:
            streak = 0

    best_streak_start = None
    if best_streak_end and best_streak > 0:
        end_date = date.fromisoformat(best_streak_end)
        best_streak_start = (end_date - timedelta(days=best_streak - 1)).isoformat()

    # Per-habit day-of-week stats
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_totals = [0] * 7
    day_done = [0] * 7
    # Count all calendar days in the effective range, not just logged days
    for i in range((today - effective_start).days + 1):
        d_date = effective_start + timedelta(days=i)
        wd = d_date.weekday()
        day_totals[wd] += 1
    for d_entry in data:
        d_date = date.fromisoformat(d_entry["log_date"])
        wd = d_date.weekday()
        if d_entry["completed"]:
            day_done[wd] += 1
    day_rates = [round(day_done[i] / day_totals[i] * 100) if day_totals[i] else 0 for i in range(7)]

    # Metric stats
    metric_values = [d["metric_value"] for d in data if d["metric_value"] is not None]
    metric_summary = None
    if habit.metric_enabled and metric_values:
        metric_summary = {
            "avg": round(sum(metric_values) / len(metric_values), 1),
            "best": round(max(metric_values), 1),
            "total": round(sum(metric_values), 1),
            "count": len(metric_values),
        }

    return JSONResponse(content={
        "data": data,
        "habit": {
            "id": habit.id,
            "name": habit.name,
            "metric_enabled": habit.metric_enabled,
            "metric_unit": habit.metric_unit,
            "metric_default": habit.metric_default,
            "metric_max": habit.metric_max,
        },
        "summary": {
            "total_days": total_days,
            "completed_days": completed_days,
            "completion_rate": completion_rate,
            "current_streak": current_streak,
            "current_streak_start": current_streak_start,
            "current_streak_end": current_streak_end,
            "best_streak": best_streak,
            "best_streak_start": best_streak_start,
            "best_streak_end": best_streak_end,
            "metric": metric_summary,
            "day_of_week": {"labels": day_names, "rates": day_rates},
        },
    })


@app.get("/api/habits/{habit_id}")
async def api_habit(request: Request, habit_id: int, db: Session = Depends(get_db),
                    log_date: Optional[str] = None):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({}, status_code=401)
    habit = database.get_habit(db, habit_id, user_id)
    if not habit:
        return JSONResponse({"error": "not found"}, status_code=404)
    # Use the snapshotted goal for the viewed day if available
    effective_goal = habit.metric_default
    if log_date:
        log = database.get_log(db, habit.id, log_date)
        if log and log.metric_goal is not None:
            effective_goal = log.metric_goal
    return JSONResponse({
        "id": habit.id,
        "name": habit.name,
        "description": habit.description or "",
        "category_id": habit.category_id or "",
        "metric_enabled": habit.metric_enabled,
        "metric_unit": habit.metric_unit or "",
        "metric_default": effective_goal or "",
        "metric_max": habit.metric_max or "",
        "metric_step": habit.metric_step or 0.5,
    })


@app.get("/api/summary")
async def api_summary(request: Request, db: Session = Depends(get_db),
                      log_date: Optional[str] = None):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({"total": 0, "done": 0})

    log_date = log_date or today_str()
    summary = database.get_today_summary(db, user_id, log_date)
    return JSONResponse(content=summary)


# ── Todo routes ──────────────────────────────────────────────────────────────

@app.get("/todos", response_class=HTMLResponse)
async def todos_page(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    user = database.get_user_by_id(db, user_id)
    todos = database.get_todo_tree(db, user_id)
    todo_groups = database.get_todo_tree_grouped(db, user_id)
    categories = database.get_categories(db, user_id)
    return templates.TemplateResponse("todos.html", {
        "request": request,
        "user": user,
        "todos": todos,
        "todo_groups": todo_groups,
        "categories": categories,
        "display_date": display_date_label(today_str()),
        "is_guest": request.session.get("is_guest", False),
    })


@app.post("/todos", response_class=HTMLResponse)
async def create_todo_route(request: Request, db: Session = Depends(get_db),
                            title: str = Form(""),
                            parent_id: Optional[int] = Form(None),
                            category_id: Optional[int] = Form(None)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.create_todo(db, user_id, title or "New todo", parent_id=parent_id or None,
                         category_id=category_id or None)
    return templates.TemplateResponse("partials/todo_list.html", _todo_list_ctx(request, db, user_id))


@app.post("/todos/{todo_id}/toggle", response_class=HTMLResponse)
async def toggle_todo(request: Request, todo_id: int, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.toggle_todo(db, todo_id, user_id)
    return templates.TemplateResponse("partials/todo_list.html", _todo_list_ctx(request, db, user_id))


@app.patch("/todos/{todo_id}", response_class=HTMLResponse)
async def update_todo_route(request: Request, todo_id: int,
                            db: Session = Depends(get_db),
                            title: str = Form("")):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    if title.strip():
        database.update_todo(db, todo_id, user_id, title.strip())
    return templates.TemplateResponse("partials/todo_list.html", _todo_list_ctx(request, db, user_id))


@app.post("/todos/{todo_id}/move", response_class=HTMLResponse)
async def move_todo(request: Request, todo_id: int,
                    db: Session = Depends(get_db),
                    parent_id: Optional[int] = Form(None),
                    before_id: Optional[int] = Form(None)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.reparent_todo(db, todo_id, user_id, parent_id=parent_id or None, before_id=before_id or None)
    return templates.TemplateResponse("partials/todo_list.html", _todo_list_ctx(request, db, user_id))


@app.delete("/todos/{todo_id}", response_class=HTMLResponse)
async def delete_todo(request: Request, todo_id: int, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.delete_todo(db, todo_id, user_id)
    return templates.TemplateResponse("partials/todo_list.html", _todo_list_ctx(request, db, user_id))


# ── Category routes ──────────────────────────────────────────────────────────

@app.post("/categories", response_class=HTMLResponse)
async def create_category_route(request: Request, db: Session = Depends(get_db),
                                 name: str = Form(...)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.create_category(db, user_id, name.strip())
    return RedirectResponse("/settings", status_code=303)


@app.patch("/categories/{category_id}", response_class=HTMLResponse)
async def rename_category_route(request: Request, category_id: int,
                                 db: Session = Depends(get_db),
                                 name: str = Form(...)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.rename_category(db, category_id, user_id, name.strip())
    categories = database.get_categories(db, user_id)
    return templates.TemplateResponse("partials/category_list.html", {
        "request": request,
        "categories": categories,
    })


@app.delete("/categories/{category_id}", response_class=HTMLResponse)
async def delete_category_route(request: Request, category_id: int,
                                 db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.delete_category(db, category_id, user_id)
    categories = database.get_categories(db, user_id)
    return templates.TemplateResponse("partials/category_list.html", {
        "request": request,
        "categories": categories,
    })


@app.post("/categories/reorder", response_class=HTMLResponse)
async def reorder_categories_route(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    form = await request.form()
    ordered_ids = [int(x) for x in form.getlist("order[]") if x.isdigit()]
    database.reorder_categories(db, user_id, ordered_ids)
    categories = database.get_categories(db, user_id)
    return templates.TemplateResponse("partials/category_list.html", {
        "request": request,
        "categories": categories,
    })


@app.post("/habits/{habit_id}/category", response_class=HTMLResponse)
async def set_habit_category_route(request: Request, habit_id: int,
                                    db: Session = Depends(get_db),
                                    category_id: Optional[int] = Form(None)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.set_habit_category(db, habit_id, user_id, category_id or None)
    habits = database.get_habits(db, user_id)
    categories = database.get_categories(db, user_id)
    return templates.TemplateResponse("partials/settings_list.html", {
        "request": request,
        "habits": habits,
        "categories": categories,
    })


@app.post("/todos/{todo_id}/category", response_class=HTMLResponse)
async def set_todo_category_route(request: Request, todo_id: int,
                                   db: Session = Depends(get_db),
                                   category_id: Optional[int] = Form(None)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.set_todo_category(db, todo_id, user_id, category_id or None)
    return templates.TemplateResponse("partials/todo_list.html", _todo_list_ctx(request, db, user_id))


# ── Tracker routes ──────────────────────────────────────────────────────────

@app.post("/trackers", response_class=HTMLResponse)
async def create_tracker_route(request: Request, db: Session = Depends(get_db),
                                name: str = Form(...), unit: str = Form(...)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.create_tracker(db, user_id, name.strip(), unit.strip())
    return RedirectResponse("/trackers", status_code=303)


@app.put("/trackers/{tracker_id}", response_class=HTMLResponse)
async def update_tracker_route(request: Request, tracker_id: int,
                                db: Session = Depends(get_db),
                                name: str = Form(...), unit: str = Form(...)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.update_tracker(db, tracker_id, user_id, name.strip(), unit.strip())
    return RedirectResponse("/trackers", status_code=303)


@app.delete("/trackers/{tracker_id}")
async def delete_tracker_route(request: Request, tracker_id: int,
                                db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return HTMLResponse(status_code=401)
    database.delete_tracker(db, tracker_id, user_id)
    return RedirectResponse("/trackers", status_code=303)


@app.post("/trackers/{tracker_id}/entry")
async def save_tracker_entry_route(request: Request, tracker_id: int,
                                    db: Session = Depends(get_db),
                                    entry_date: str = Form(...),
                                    value: float = Form(...)):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    tracker = database.get_tracker(db, tracker_id, user_id)
    if not tracker:
        return JSONResponse({"error": "not found"}, status_code=404)
    entry = database.save_tracker_entry(db, tracker_id, entry_date, value)
    return JSONResponse({"id": entry.id, "entry_date": entry.entry_date, "value": entry.value})


@app.delete("/trackers/{tracker_id}/entry/{entry_id}")
async def delete_tracker_entry_route(request: Request, tracker_id: int, entry_id: int,
                                      db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    tracker = database.get_tracker(db, tracker_id, user_id)
    if not tracker:
        return JSONResponse({"error": "not found"}, status_code=404)
    database.delete_tracker_entry(db, entry_id, tracker_id)
    return JSONResponse({"ok": True})


@app.get("/api/trackers/{tracker_id}")
async def api_tracker_data(request: Request, tracker_id: int,
                            db: Session = Depends(get_db), window: str = "30d"):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({})
    tracker = database.get_tracker(db, tracker_id, user_id)
    if not tracker:
        return JSONResponse({"error": "not found"}, status_code=404)
    windows = {"7d": 7, "30d": 30, "90d": 90, "all": 365 * 10}
    days = windows.get(window, 30)
    start = (datetime.now().date() - timedelta(days=days)).isoformat()
    entries = database.get_tracker_entries(db, tracker_id, start)
    return JSONResponse({
        "tracker": {"id": tracker.id, "name": tracker.name, "unit": tracker.unit},
        "entries": [{"entry_date": e.entry_date, "value": e.value, "notes": e.notes, "id": e.id} for e in entries],
    })


# ── Schedule ─────────────────────────────────────────────────────────────────

@app.get("/api/schedule")
async def api_schedule(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse([])
    blocks = database.get_schedule_blocks(db, user_id)
    return JSONResponse([{
        "id": b.id, "label": b.label,
        "start_time": b.start_time, "end_time": b.end_time,
        "color": b.color,
    } for b in blocks])


@app.post("/api/schedule")
async def api_schedule_create(request: Request, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    form = await request.form()
    label = form.get("label", "").strip()
    start_time = form.get("start_time", "").strip()
    end_time = form.get("end_time", "").strip()
    color = form.get("color", "").strip() or None
    if not label or not start_time or not end_time:
        return JSONResponse({"error": "missing fields"}, status_code=400)
    if end_time <= start_time:
        return JSONResponse({"error": "end must be after start"}, status_code=400)
    block = database.create_schedule_block(db, user_id, label, start_time, end_time, color)
    return JSONResponse({"id": block.id, "label": block.label,
                         "start_time": block.start_time, "end_time": block.end_time,
                         "color": block.color})


@app.put("/api/schedule/{block_id}")
async def api_schedule_update(request: Request, block_id: int, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    form = await request.form()
    label = form.get("label", "").strip()
    start_time = form.get("start_time", "").strip()
    end_time = form.get("end_time", "").strip()
    color = form.get("color", "").strip() or None
    if not label or not start_time or not end_time:
        return JSONResponse({"error": "missing fields"}, status_code=400)
    if end_time <= start_time:
        return JSONResponse({"error": "end must be after start"}, status_code=400)
    block = database.update_schedule_block(db, block_id, user_id, label, start_time, end_time, color)
    if not block:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({"id": block.id, "label": block.label,
                         "start_time": block.start_time, "end_time": block.end_time,
                         "color": block.color})


@app.delete("/api/schedule/{block_id}")
async def api_schedule_delete(request: Request, block_id: int, db: Session = Depends(get_db)):
    user_id = await require_user(request, db)
    if not user_id:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    database.delete_schedule_block(db, block_id, user_id)
    return JSONResponse({"ok": True})
