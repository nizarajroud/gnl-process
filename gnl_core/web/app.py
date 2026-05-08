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
            await ws.send_text(json.dumps({"type": "log", "msg": msg}))
        except Exception:
            ws_clients.remove(ws)


async def broadcast_status():
    """Push updated status table HTML to all clients."""
    from gnl_core.db import get_db, parent_status
    with get_db() as conn:
        rows = conn.execute("SELECT id, podcast_subtheme, parent_file FROM parent_configuration").fetchall()
    
    html_rows = ""
    for row in rows:
        s = parent_status(row['id'])
        total = s['total'] or 1
        gen_pct = s['generated'] / total * 100
        dl_pct = s['downloaded'] / total * 100
        conv_pct = s['converted'] / total * 100
        launched_bar = max(0, gen_pct - dl_pct)
        dl_bar = max(0, dl_pct - conv_pct)

        html_rows += f"""<tr class="border-b border-gray-700">
            <td class="py-2">{row['id']}</td>
            <td class="py-2">{row['podcast_subtheme']}</td>
            <td class="py-3 w-1/3">
                <div class="flex items-center gap-1 text-xs">
                    <div class="flex-1">
                        <div class="flex justify-between text-gray-400 mb-1">
                            <span>Launched {s['generated']}/{s['total']}</span>
                            <span>Downloaded {s['downloaded']}/{s['total']}</span>
                            <span>Converted {s['converted']}/{s['total']}</span>
                        </div>
                        <div class="w-full bg-gray-700 rounded-full h-2 flex overflow-hidden">
                            <div class="bg-yellow-500 h-2" style="width: {launched_bar}%"></div>
                            <div class="bg-blue-500 h-2" style="width: {dl_bar}%"></div>
                            <div class="bg-green-500 h-2" style="width: {conv_pct}%"></div>
                        </div>
                    </div>
                </div>
            </td>
            <td class="py-2 space-x-1">
                <button hx-post="/action/generate/{row['id']}" hx-swap="none" class="px-2 py-1 bg-blue-600 hover:bg-blue-500 rounded text-xs">Gen</button>
                <button hx-post="/action/download/{row['id']}" hx-swap="none" class="px-2 py-1 bg-purple-600 hover:bg-purple-500 rounded text-xs">DL</button>
                <button hx-post="/action/convert/{row['id']}" hx-swap="none" class="px-2 py-1 bg-orange-600 hover:bg-orange-500 rounded text-xs">Conv</button>
                <button hx-post="/action/deliver/{row['id']}" hx-swap="none" class="px-2 py-1 bg-green-600 hover:bg-green-500 rounded text-xs">Deliver</button>
                <button hx-post="/action/clean/{row['id']}" hx-swap="none" class="px-2 py-1 bg-red-600 hover:bg-red-500 rounded text-xs">Clean</button>
            </td></tr>"""
    
    if not html_rows:
        html_rows = '<tr><td colspan="4" class="py-4 text-center text-gray-500">No parents in database</td></tr>'

    for ws in ws_clients[:]:
        try:
            await ws.send_text(json.dumps({"type": "status_update", "html": html_rows}))
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
    test_mode = os.environ.get('TEST_MODE', '0') == '1'

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "parents": parents,
        "schedule_time": schedule_time, "next_run": next_run, "test_mode": test_mode
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
    finally:
        await broadcast_status()


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
        await broadcast_status()
        return {"status": "ok", "parent_id": parent_id}
    except Exception as e:
        await broadcast_log(f"⚠ Prepare failed: {str(e)[:100]}")
        return {"status": "error", "error": str(e)}


@app.post("/toggle-test-mode")
async def toggle_test_mode():
    """Toggle TEST_MODE on/off."""
    current = os.environ.get('TEST_MODE', '0')
    new_val = '0' if current == '1' else '1'
    os.environ['TEST_MODE'] = new_val
    await broadcast_log(f"{'🧪 TEST MODE ON' if new_val == '1' else '🚀 TEST MODE OFF (real API)'}")
    return {"status": "ok", "test_mode": new_val == '1'}


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
