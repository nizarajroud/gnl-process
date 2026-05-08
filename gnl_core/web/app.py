"""GNL Web UI — FastAPI + HTMX dashboard with scheduler."""

import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv(Path(__file__).parent.parent.parent / '.env')

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

ws_clients: list[WebSocket] = []
scheduler = AsyncIOScheduler()


def _deliver_all_sync():
    """Run deliver for all active parents (called by scheduler)."""
    from gnl_core.db import get_active_parents, parent_status
    from gnl_core.generate import generate
    from gnl_core.download import download
    from gnl_core.convert import convert

    for pid in get_active_parents():
        s = parent_status(pid)
        if s['generated'] < s['total']:
            generate(pid)
            s = parent_status(pid)
        if s['downloaded'] < s['generated']:
            download(pid)
            s = parent_status(pid)
        if s['downloaded'] == s['total'] and s['converted'] < s['total']:
            convert(pid)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start scheduler with configured time
    schedule_time = os.getenv('GNL_SCHEDULE_TIME', '08:00')
    hour, minute = schedule_time.split(':')
    scheduler.add_job(_deliver_all_sync, CronTrigger(hour=int(hour), minute=int(minute)), id='daily_deliver', replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="GNL Process", lifespan=lifespan)


async def broadcast_log(msg: str):
    for ws in ws_clients[:]:
        try:
            await ws.send_text(msg)
        except Exception:
            ws_clients.remove(ws)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    from gnl_core.db import get_db, parent_status

    with get_db() as conn:
        rows = conn.execute("SELECT id, podcast_subtheme, parent_file FROM parent_configuration").fetchall()

    parents = []
    for row in rows:
        s = parent_status(row['id'])
        parents.append({'id': row['id'], 'subtheme': row['podcast_subtheme'], 'parent_file': row['parent_file'], **s})

    schedule_time = os.getenv('GNL_SCHEDULE_TIME', '08:00')
    jobs = scheduler.get_jobs()
    next_run = str(jobs[0].next_run_time.strftime('%Y-%m-%d %H:%M')) if jobs else "Not scheduled"

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "parents": parents,
        "schedule_time": schedule_time, "next_run": next_run
    })


@app.post("/action/{action}/{parent_id}")
async def run_action(action: str, parent_id: int):
    asyncio.create_task(_run_action(action, parent_id))
    return {"status": "started", "action": action, "parent_id": parent_id}


async def _run_action(action: str, parent_id: int):
    await broadcast_log(f"▶ {action} (parent_id={parent_id})")
    try:
        if action == "generate":
            from gnl_core.generate import generate
            s, f = generate(parent_id)
            await broadcast_log(f"✓ Generated {len(s)}, failed {len(f)}")
        elif action == "download":
            from gnl_core.download import download
            s, f = download(parent_id)
            await broadcast_log(f"✓ Downloaded {len(s)}, failed {len(f)}")
        elif action == "convert":
            from gnl_core.convert import convert
            s, f = convert(parent_id)
            await broadcast_log(f"✓ Converted {len(s)}, failed {len(f)}")
        elif action == "deliver":
            from gnl_core.generate import generate
            from gnl_core.download import download
            from gnl_core.convert import convert
            from gnl_core.db import parent_status

            s = parent_status(parent_id)
            if s['generated'] < s['total']:
                await broadcast_log("▶ GENERATE")
                generate(parent_id)
            s = parent_status(parent_id)
            if s['downloaded'] < s['generated']:
                await broadcast_log("▶ DOWNLOAD")
                download(parent_id)
            s = parent_status(parent_id)
            if s['downloaded'] == s['total'] and s['converted'] < s['total']:
                await broadcast_log("▶ CONVERT")
                convert(parent_id)
            s = parent_status(parent_id)
            await broadcast_log(f"✓ Deliver done: {s['converted']}/{s['total']} converted")
        elif action == "clean":
            from gnl_core.clean import clean
            d, f = clean(str(parent_id))
            await broadcast_log(f"✓ Cleaned {d} notebooks")
    except Exception as e:
        await broadcast_log(f"⚠ Error: {str(e)[:100]}")


@app.post("/prepare")
async def prepare_pdf(request: Request):
    """Upload PDF, split, collect, generate titles."""
    from fastapi import UploadFile, Form
    import tempfile

    form = await request.form()
    pdf_file = form.get("pdf")
    pages = int(form.get("pages", 3))
    name = form.get("name", "")
    theme = form.get("theme", "")
    subtheme = form.get("subtheme", "")

    # Save uploaded file to temp
    tmp = os.path.join(tempfile.gettempdir(), pdf_file.filename)
    with open(tmp, "wb") as f:
        f.write(await pdf_file.read())

    await broadcast_log(f"▶ Preparing {pdf_file.filename} ({pages}p/chunk)")

    try:
        from gnl_core.split import split
        from gnl_core.collect import collect
        from gnl_core.titles import generate_titles

        result = split(tmp, pages, name, podcast_theme=theme, podcast_subtheme=subtheme)
        parent_id = collect(result)
        count = generate_titles(parent_id)
        os.unlink(tmp)
        await broadcast_log(f"✓ Prepared: {len(result['files'])} chunks, parent_id={parent_id}, {count} titles")
        return {"status": "ok", "parent_id": parent_id}
    except Exception as e:
        await broadcast_log(f"⚠ Prepare failed: {str(e)[:100]}")
        return {"status": "error", "error": str(e)}


@app.post("/schedule")
async def update_schedule(request: Request):
    """Update daily schedule time."""
    form = await request.form()
    new_time = form.get("time", "08:00")
    hour, minute = new_time.split(':')
    scheduler.reschedule_job('daily_deliver', trigger=CronTrigger(hour=int(hour), minute=int(minute)))
    os.environ['GNL_SCHEDULE_TIME'] = new_time
    return {"status": "updated", "time": new_time}


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_clients.remove(websocket)
