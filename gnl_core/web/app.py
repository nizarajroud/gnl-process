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
def _deliver_all_sync(loop=None):
    """Run deliver for all active parents (called by scheduler/startup)."""
    from gnl_core.db import get_active_parents, parent_status
    from gnl_core.generate import generate
    from gnl_core.download import download
    from gnl_core.convert import convert

    if loop is None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()

    def notify(msg):
        asyncio.run_coroutine_threadsafe(broadcast_log(msg), loop)
        asyncio.run_coroutine_threadsafe(broadcast_status(), loop)

    for pid in get_active_parents():
        s = parent_status(pid)
        if s['generated'] < s['total']:
            notify(f"▶ AUTO: GENERATE (parent {pid})")
            generate(pid, on_progress=lambda rec: asyncio.run_coroutine_threadsafe(broadcast_status(), loop))
            notify(f"✓ AUTO: Generate done (parent {pid})")
        s = parent_status(pid)
        if s['downloaded'] < s['generated']:
            notify(f"▶ AUTO: DOWNLOAD (parent {pid})")
            download(pid)
            notify(f"✓ AUTO: Download done (parent {pid})")
        s = parent_status(pid)
        if s['downloaded'] > 0 and s['converted'] < s['downloaded']:
            notify(f"▶ AUTO: CONVERT (parent {pid})")
            convert(pid)
            notify(f"✓ AUTO: Convert done (parent {pid})")
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Mount Google Drive if not available
    import subprocess
    if not os.path.ismount('/mnt/g'):
        subprocess.run(['sudo', 'mount', '-t', 'drvfs', 'G:', '/mnt/g'], capture_output=True)

    # Start scheduler with configured time
    schedule_time = os.getenv('GNL_SCHEDULE_TIME', '08:00')
    hour, minute = schedule_time.split(':')
    scheduler.add_job(_deliver_all_sync, CronTrigger(hour=int(hour), minute=int(minute)), id='daily_deliver', replace_existing=True, args=[asyncio.get_event_loop()])
    scheduler.start()

    # Run on startup if there's pending work
    from gnl_core.db import get_active_parents
    if get_active_parents():
        import threading
        _startup_loop = asyncio.get_event_loop()
        def _startup_deliver():
            _deliver_all_sync(_startup_loop)
        threading.Thread(target=_startup_deliver, daemon=True).start()

    yield
    scheduler.shutdown()

app = FastAPI(title="GNL Process", lifespan=lifespan)
def _get_quota():
    """Calculate remaining quota from DB. Works in both test and real mode."""
    from gnl_core.db import get_db
    from datetime import datetime, timezone as tz, timedelta
    max_quota = int(os.environ.get('TEST_QUOTA', '20')) if os.environ.get('TEST_MODE', '0') == '1' else 20
    pt = tz(timedelta(hours=-7))
    now_pt = datetime.now(pt)
    midnight_pt_str = now_pt.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d')
    with get_db() as conn:
        used = conn.execute("SELECT COUNT(*) as c FROM podcast_download WHERE generation_state=1 AND date=?", (midnight_pt_str,)).fetchone()['c']
    return max(0, max_quota - used)
async def broadcast_log(msg: str):
    for ws in ws_clients[:]:
        try:
            await ws.send_text(json.dumps({"type": "log", "msg": msg}))
        except Exception:
            ws_clients.remove(ws)
async def broadcast_status():
    """Push updated editions HTML to all clients."""
    from gnl_core.db import get_db, parent_status

    quota_remaining = _get_quota()

    with get_db() as conn:
        rows = conn.execute("SELECT id, podcast_subtheme, parent_file FROM parent_configuration").fetchall()

    html = ""
    for row in rows:
        s = parent_status(row['id'])
        pid = row['id']
        sub = row['podcast_subtheme']
        total = s['total']
        gen = s['generated']
        dl = s['downloaded']
        conv = s['converted']

        # Button
        if s['combined'] == 1:
            btn = '<span class="px-3 py-1 bg-green-900 text-green-300 rounded-full text-xs font-medium">✅ Terminé</span>'
        elif conv == total and total > 0:
            btn = f'<button hx-post="/action/deliver/{pid}" hx-swap="none" onclick="this.disabled=true;this.textContent=\'...\'" class="px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-medium">▶ Combiner</button>'
        elif gen == 0:
            btn = f'<button hx-post="/action/deliver/{pid}" hx-swap="none" onclick="this.disabled=true;this.textContent=\'...\'" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium">▶ Lancer</button>'
        elif dl < total:
            btn = f'<button hx-post="/action/deliver/{pid}" hx-swap="none" onclick="this.disabled=true;this.textContent=\'...\'" class="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 rounded-lg text-sm font-medium">▶ Reprendre</button>'
        else:
            btn = f'<button hx-post="/action/deliver/{pid}" hx-swap="none" onclick="this.disabled=true;this.textContent=\'...\'" class="px-4 py-2 bg-orange-600 hover:bg-orange-500 rounded-lg text-sm font-medium">▶ Finaliser</button>'

        clean_btn = f'<button hx-post="/action/clean/{pid}" hx-swap="none" hx-confirm="Supprimer cette édition ?" onclick="this.disabled=true" class="px-2 py-1 text-red-400 hover:text-red-300 text-xs">🗑</button>'

        # Timeline steps
        steps = [("Préparé", total, total), ("Généré", gen, total), ("Téléchargé", dl, total), ("Converti", conv, total), ("Combiné", s['combined'], 1)]
        timeline = '<div class="flex items-center justify-between">'
        for i, (label, done, t) in enumerate(steps):
            if done == t:
                dot_cls = "bg-green-500 border-green-500"
                txt_cls = "text-green-400"
            elif done > 0:
                dot_cls = "bg-yellow-500 border-yellow-500 animate-pulse"
                txt_cls = "text-yellow-400"
            else:
                dot_cls = "bg-gray-700 border-gray-600"
                txt_cls = "text-gray-500"
            timeline += f'<div class="flex flex-col items-center z-10" style="width:20px"><div class="w-4 h-4 rounded-full border-2 {dot_cls}"></div><span class="text-xs mt-1 {txt_cls}">{label}</span><span class="text-xs text-gray-500">{done}/{t}</span></div>'
            if i < 4:
                next_done = steps[i+1][1]
                next_total = steps[i+1][2]
                pct = int(next_done / next_total * 100) if next_total > 0 else 0
                current_complete = (done == t)
                if current_complete:
                    bar_cls = "bg-green-500"
                    bar_pct = 100
                elif pct > 0:
                    bar_cls = "bg-yellow-500"
                    bar_pct = pct
                else:
                    bar_cls = ""
                    bar_pct = 0
                timeline += f'<div class="flex-1 h-1.5 -mt-6 bg-gray-700 rounded-full overflow-hidden mx-1"><div class="h-full rounded-full transition-all duration-500 {bar_cls}" style="width:{bar_pct}%"></div></div>'
        timeline += '</div>'

        quota_msg = f'<p class="text-xs text-gray-400 mt-3">⏳ Quota — reprend automatiquement demain</p>' if 0 < gen < total else ''

        html += f'''<div class="bg-gray-800 rounded-lg p-5">
            <div class="flex justify-between items-start mb-4">
                <div><h3 class="font-semibold text-lg">{row['parent_file']}</h3><span class="text-xs text-gray-400">{total} épisodes</span></div>
                <div class="flex items-center gap-2">{btn}{clean_btn}</div>
            </div>
            <div class="relative">{timeline}</div>{quota_msg}
        </div>'''

    if not html:
        html = '<div class="bg-gray-800 rounded-lg p-8 text-center text-gray-500">Aucune édition.</div>'

    for ws in ws_clients[:]:
        try:
            await ws.send_text(json.dumps({"type": "status_update", "html": html, "quota": quota_remaining}))
        except Exception:
            ws_clients.remove(ws)
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    from gnl_core.db import get_db, parent_status
    from datetime import datetime, timezone, timedelta

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

    quota_remaining = _get_quota()

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "parents": parents,
        "schedule_time": schedule_time, "next_run": next_run, "test_mode": test_mode,
        "quota_remaining": quota_remaining
    })
@app.get("/api/catalog")
async def get_catalog():
    """Return series catalog for form dropdowns."""
    from gnl_core.db import get_db
    with get_db() as conn:
        rows = conn.execute("SELECT theme, subtheme FROM series_catalog ORDER BY theme, id").fetchall()
    catalog = {}
    for r in rows:
        catalog.setdefault(r['theme'], []).append(r['subtheme'])
    return catalog
@app.post("/refresh")
async def refresh():
    """Force UI refresh."""
    await broadcast_status()
    return {"status": "ok"}


@app.get("/api/quota-check/{parent_id}")
async def quota_check(parent_id: int):
    """Check if quota is sufficient for this edition."""
    from gnl_core.db import parent_status, get_db
    from datetime import datetime, timezone, timedelta

    s = parent_status(parent_id)
    to_generate = s['total'] - s['generated']

    if to_generate == 0:
        return {"sufficient": True, "to_generate": 0, "remaining": 0}

    remaining = _get_quota()

    sufficient = to_generate <= remaining
    pct = int(remaining / s['total'] * 100) if not sufficient else 100

    return {
        "sufficient": sufficient,
        "to_generate": to_generate,
        "remaining": remaining,
        "total": s['total'],
        "pct": pct
    }
@app.post("/action/{action}/{parent_id}")
async def run_action(action: str, parent_id: int, request: Request = None):
    asyncio.create_task(_run_action(action, parent_id))
    return {"status": "started", "action": action, "parent_id": parent_id}
async def _run_action(action: str, parent_id: int):
    await broadcast_log(f"▶ {action} (parent_id={parent_id})")
    try:
        loop = asyncio.get_event_loop()
        if action == "generate":
            from gnl_core.generate import generate
            def on_progress(rec):
                asyncio.run_coroutine_threadsafe(broadcast_status(), loop)
            s, f = await loop.run_in_executor(None, lambda: generate(parent_id, on_progress=on_progress))
            await broadcast_log(f"✓ Generated {len(s)}, failed {len(f)}")
        elif action == "download":
            from gnl_core.download import download
            s, f = await loop.run_in_executor(None, lambda: download(parent_id))
            await broadcast_log(f"✓ Downloaded {len(s)}, failed {len(f)}")
        elif action == "convert":
            from gnl_core.convert import convert
            s, f = await loop.run_in_executor(None, lambda: convert(parent_id))
            await broadcast_log(f"✓ Converted {len(s)}, failed {len(f)}")
        elif action == "deliver":
            from gnl_core.generate import generate
            from gnl_core.download import download
            from gnl_core.convert import convert
            from gnl_core.db import parent_status, resolve_parent, get_db
            from gnl_core.combine import combine
            from datetime import datetime, timezone as tz, timedelta

            s = parent_status(parent_id)

            # Generate phase (quota-aware)
            if s['generated'] < s['total']:
                remaining_quota = _get_quota()
                to_generate = s['total'] - s['generated']
                max_count = min(to_generate, remaining_quota) if remaining_quota < to_generate else None
                await broadcast_log(f"▶ GENERATE ({max_count or to_generate} épisodes)")

                def on_episode_generated(rec):
                    asyncio.run_coroutine_threadsafe(broadcast_status(), loop)

                await loop.run_in_executor(None, lambda: generate(parent_id, max_count=max_count, on_progress=on_episode_generated))
                await broadcast_status()

            s = parent_status(parent_id)
            if s['downloaded'] < s['generated']:
                await broadcast_log("▶ DOWNLOAD")
                await loop.run_in_executor(None, lambda: download(parent_id))
                await broadcast_status()

            s = parent_status(parent_id)
            if s['downloaded'] > 0 and s['converted'] < s['downloaded']:
                await broadcast_log("▶ CONVERT")
                await loop.run_in_executor(None, lambda: convert(parent_id))
                await broadcast_status()

            # Combine: full or partial
            s = parent_status(parent_id)
            if s['converted'] > 0 and s['combined'] == 0:
                with get_db() as conn:
                    pf = conn.execute("SELECT parent_file FROM parent_configuration WHERE id=?", (parent_id,)).fetchone()['parent_file']
                if s['converted'] == s['total']:
                    await broadcast_log("▶ COMBINE (complet)")
                    await broadcast_log("⏳ Combinaison en cours...")
                    await loop.run_in_executor(None, lambda: combine(parent_id, pf))
                else:
                    pct = int(s['converted'] / s['total'] * 100)
                    await broadcast_log(f"▶ COMBINE (partiel {pct}%)")
                    await broadcast_log("⏳ Combinaison en cours...")
                    await loop.run_in_executor(None, lambda: combine(parent_id, pf, suffix=str(pct)))
                await broadcast_status()

            s = parent_status(parent_id)
            await broadcast_log(f"✓ Deliver done: {s['converted']}/{s['total']} converted, combined={'✓' if s['combined'] else '✗'}")
        elif action == "clean":
            from gnl_core.clean import clean
            d, f = clean(str(parent_id))
            await broadcast_log(f"✓ Cleaned {d} notebooks")
        elif action == "reset":
            from gnl_core.clean import clean
            from gnl_core.db import get_db
            # Clean all notebooks
            d, f = clean("all")
            # Wipe DB
            with get_db() as conn:
                conn.execute("DELETE FROM podcast_download")
                conn.execute("DELETE FROM parent_configuration")
                conn.commit()
            await broadcast_log(f"🔄 Reset done")
            # Pre-fill the form will be handled client-side
    except Exception as e:
        await broadcast_log(f"⚠ Error: {str(e)[:100]}")
    finally:
        await broadcast_log("__done__")
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
