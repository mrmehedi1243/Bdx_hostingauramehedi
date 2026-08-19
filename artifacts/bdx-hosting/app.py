import os, sys, json, time, uuid, shutil, hashlib, zipfile, secrets, mimetypes
import sqlite3, threading, subprocess, socket
import urllib.request, urllib.error, urllib.parse, posixpath
from datetime import datetime, timedelta
from functools import wraps

import psutil
from flask import (Flask, render_template, request, session,
                   redirect, url_for, jsonify, Response, stream_with_context,
                   send_file, abort)
from flask_compress import Compress

import bot_engine

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
# Keep mutable panel data outside code paths and allow deployments to provide a
# persistent mount. The workspace path remains the safe local default.
PERSISTENT_DATA_ROOT = os.environ.get(
    "PANEL_DATA_ROOT", os.path.join(BASE_DIR, "data")
)
DATA_DIR  = os.path.join(PERSISTENT_DATA_ROOT, "panels")
DB_PATH   = os.path.join(PERSISTENT_DATA_ROOT, "bdx.db")
os.makedirs(DATA_DIR, exist_ok=True)
bot_engine.init(DB_PATH, DATA_DIR)
LIFETIME_EXPIRY = "2300-01-01T00:00:00"

# Base path prefix (set via env on Replit, empty string on bare VPS)
BP = os.environ.get("BASE_PATH", "").rstrip("/")   # e.g. "/bdx" or ""

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bdx-hosting-secret-2025")
app.config["SESSION_COOKIE_PATH"] = BP + "/" if BP else "/"
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB upload limit

# ── Gzip compression (makes pages 60-80% smaller, much faster) ──────────────
app.config["COMPRESS_MIMETYPES"] = [
    "text/html", "text/css", "application/javascript",
    "application/json", "text/plain"
]
app.config["COMPRESS_LEVEL"] = 6
app.config["COMPRESS_MIN_SIZE"] = 500
Compress(app)

# ── In-memory process & log stores ─────────────────────────────────────────────
PROCESSES = {}   # panel_id -> {"proc": Popen, "start_time": float}
LOG_STORE  = {}  # panel_id -> [{"ts": float, "line": str}, ...]
LOG_LOCK   = threading.Lock()
MAX_LINES  = 600

# ── Template context ────────────────────────────────────────────────────────────
@app.context_processor
def inject_bp():
    return {"bp": BP}   # use {{ bp }}/dashboard in templates

# ── DB ──────────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS admins (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS panels (
            id            TEXT PRIMARY KEY,
            username      TEXT UNIQUE NOT NULL,
            password      TEXT NOT NULL,
            server_id     TEXT UNIQUE NOT NULL,
            type          TEXT NOT NULL DEFAULT 'python',
            ram_limit     INTEGER NOT NULL DEFAULT 512,
            disk_limit    INTEGER NOT NULL DEFAULT 1024,
            start_command TEXT NOT NULL DEFAULT 'python main.py',
            status        TEXT NOT NULL DEFAULT 'stopped',
            banned        INTEGER NOT NULL DEFAULT 0,
            expires_at    TEXT NOT NULL,
            created_at    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tg_bots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            token           TEXT UNIQUE NOT NULL,
            owner_admin_id  TEXT NOT NULL,
            owner_admin_username TEXT,
            bot_username    TEXT,
            status          TEXT NOT NULL DEFAULT 'stopped',
            force_channel   TEXT,
            created_at      TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tg_bot_users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id          INTEGER NOT NULL,
            tg_user_id      TEXT NOT NULL,
            tg_username     TEXT,
            referred_by     TEXT,
            ref_count       INTEGER NOT NULL DEFAULT 0,
            panels_created  INTEGER NOT NULL DEFAULT 0,
            balance         INTEGER NOT NULL DEFAULT 0,
            lang            TEXT NOT NULL DEFAULT 'en',
            created_at      TEXT NOT NULL,
            UNIQUE(bot_id, tg_user_id)
        );
        CREATE TABLE IF NOT EXISTS shared_files (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            panel_id   TEXT NOT NULL,
            filename   TEXT NOT NULL,
            token      TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        # Lightweight migrations for DBs created before these columns existed
        existing_panel_cols = {r["name"] for r in db.execute("PRAGMA table_info(panels)").fetchall()}
        if "banned" not in existing_panel_cols:
            db.execute("ALTER TABLE panels ADD COLUMN banned INTEGER NOT NULL DEFAULT 0")
        existing_bot_cols = {r["name"] for r in db.execute("PRAGMA table_info(tg_bots)").fetchall()}
        if "owner_admin_username" not in existing_bot_cols:
            db.execute("ALTER TABLE tg_bots ADD COLUMN owner_admin_username TEXT")
        if "force_channel" not in existing_bot_cols:
            db.execute("ALTER TABLE tg_bots ADD COLUMN force_channel TEXT")
        existing_user_cols = {r["name"] for r in db.execute("PRAGMA table_info(tg_bot_users)").fetchall()}
        if "balance" not in existing_user_cols:
            db.execute("ALTER TABLE tg_bot_users ADD COLUMN balance INTEGER NOT NULL DEFAULT 0")
        if "lang" not in existing_user_cols:
            db.execute("ALTER TABLE tg_bot_users ADD COLUMN lang TEXT NOT NULL DEFAULT 'en'")
        pw = hashlib.sha256("admin".encode()).hexdigest()
        db.execute("DELETE FROM admins WHERE username=?", ("admin",))
        db.execute("INSERT OR IGNORE INTO admins (username,password) VALUES (?,?)", ("mehedi", pw))
        db.commit()

# Gunicorn imports `app` instead of executing this module as a script.
# Initialize the persistent schema on import as well as on direct startup.
init_db()

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def panel_dir(pid): d = os.path.join(DATA_DIR, pid); os.makedirs(d, exist_ok=True); return d
def is_expired(exp):
    try: return datetime.fromisoformat(exp) < datetime.now()
    except: return True

def panel_is_active(panel):
    """Panels are admin-managed now; expiry is informational only.

    Existing panels created with the old trial expiry must not suddenly
    disappear or stop after a restart. Ban/delete are the explicit controls.
    """
    return bool(panel) and not bool(panel["banned"])

def repair_panel_storage():
    """Recreate missing panel directories after a managed app restart.

    A missing directory must never make the panel record look deleted. Files
    that were already persisted remain untouched; this only repairs the
    container directory itself.
    """
    try:
        with get_db() as db:
            rows = db.execute("SELECT id FROM panels").fetchall()
        for row in rows:
            os.makedirs(os.path.join(DATA_DIR, row["id"]), exist_ok=True)
    except Exception as exc:
        print(f"[T10] storage repair warning: {exc}", flush=True)

repair_panel_storage()

# ── Auth decorators ─────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if "panel_id" not in session: return redirect(BP + "/")
        return f(*a, **kw)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not session.get("is_admin"): return redirect(BP + "/admin")
        return f(*a, **kw)
    return w

# ── Logging ─────────────────────────────────────────────────────────────────────
def push_log(pid, line):
    with LOG_LOCK:
        if pid not in LOG_STORE: LOG_STORE[pid] = []
        LOG_STORE[pid].append({"ts": time.time(), "line": line})
        if len(LOG_STORE[pid]) > MAX_LINES:
            LOG_STORE[pid] = LOG_STORE[pid][-MAX_LINES:]

def get_logs_since(pid, since):
    with LOG_LOCK:
        return [l for l in LOG_STORE.get(pid, []) if l["ts"] > since]

def clear_logs(pid):
    with LOG_LOCK: LOG_STORE[pid] = []

# ── Process helpers ─────────────────────────────────────────────────────────────
def fmt_up(sec):
    s=int(sec); h,r=divmod(s,3600); m,s2=divmod(r,60)
    return f"{h}h {m}m {s2}s" if h else f"{m}m {s2}s"

def proc_stats(pid):
    info = PROCESSES.get(pid)
    if not info: return {"status":"stopped","uptime":"0m 0s","cpu":"0.0","ram":"0"}
    try:
        p = psutil.Process(info["proc"].pid)
        if "psutil_handle" not in info or info.get("psutil_pid") != p.pid:
            p.cpu_percent(interval=None)  # prime the internal counter, non-blocking
            info["psutil_handle"] = p; info["psutil_pid"] = p.pid
        cpu = info["psutil_handle"].cpu_percent(interval=None)  # non-blocking, delta since last call
        ram = int(p.memory_info().rss/1024/1024)
        return {"status":"running","uptime":fmt_up(time.time()-info["start_time"]),"cpu":f"{cpu:.1f}","ram":str(ram)}
    except: return {"status":"stopped","uptime":"0m 0s","cpu":"0.0","ram":"0"}

CRASH_COUNT = {}  # pid -> consecutive-crash counter, resets on manual start/stop

def stream_proc(pid, proc):
    for raw in iter(proc.stdout.readline, b""):
        push_log(pid, raw.decode("utf-8", errors="replace").rstrip())
    proc.wait()
    still_tracked = PROCESSES.get(pid, {}).get("proc") is proc
    push_log(pid, f"\n[PROCESS EXITED — code {proc.returncode}]")
    if still_tracked:
        PROCESSES.pop(pid, None)
    if still_tracked:
        # Process exited on its own (not via manual STOP). Keep retrying so a
        # temporary dependency/network failure cannot permanently take a panel
        # offline. A manual STOP removes the process from PROCESSES first.
        n = CRASH_COUNT.get(pid, 0) + 1
        CRASH_COUNT[pid] = n
        delay = min(60, max(2, 2 * n))
        push_log(pid, f"[T10] Unexpected exit — auto-restarting in {delay}s (attempt {n})...")
        def _delayed_restart():
            time.sleep(delay)
            with get_db() as db:
                row = db.execute("SELECT * FROM panels WHERE id=?", (pid,)).fetchone()
            if row and panel_is_active(row) and pid not in PROCESSES:
                _start(pid)
        threading.Thread(target=_delayed_restart, daemon=True).start()
        return
    with get_db() as db:
        db.execute("UPDATE panels SET status='stopped' WHERE id=?", (pid,)); db.commit()

# ── User Login / Logout ─────────────────────────────────────────────────────────
@app.route(BP + "/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","").strip()
        with get_db() as db:
            row = db.execute("SELECT * FROM panels WHERE username=? AND password=?",
                             (u, hash_pw(p))).fetchone()
        if row:
            if row["banned"]:
                return render_template("login.html", error="Your account has been banned. Contact admin.")
            session.update(panel_id=row["id"], username=row["username"], server_id=row["server_id"])
            return redirect(BP + "/dashboard")
        return render_template("login.html", error="Invalid username or password.")
    return render_template("login.html")

@app.route(BP + "/logout")
def logout():
    session.clear(); return redirect(BP + "/")

# ── Dashboard ───────────────────────────────────────────────────────────────────
@app.route(BP + "/dashboard")
@login_required
def dashboard():
    pid = session["panel_id"]
    with get_db() as db:
        panel = db.execute("SELECT * FROM panels WHERE id=?", (pid,)).fetchone()
    if not panel: session.clear(); return redirect(BP + "/")
    stats = proc_stats(pid)
    files = []
    pdir  = panel_dir(pid)
    for name in sorted(os.listdir(pdir)):
        if name == ".requirements_installed": continue
        fp = os.path.join(pdir, name)
        if os.path.isfile(fp):
            files.append({"name":name, "size":os.path.getsize(fp),
                          "modified":datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M")})
    return render_template("dashboard.html", panel=dict(panel), stats=stats,
                           files=files, expires=panel["expires_at"][:10], host=request.host)

# ── SSE ─────────────────────────────────────────────────────────────────────────
@app.route(BP + "/panel/stream")
@login_required
def console_stream():
    pid   = session["panel_id"]
    since = float(request.args.get("since", 0))
    def generate():
        last = since
        for log in get_logs_since(pid, last):
            last = max(last, log["ts"])
            yield f"data: {json.dumps({'ts':log['ts'],'line':log['line']})}\n\n"
        deadline = time.time() + 55
        while time.time() < deadline:
            logs = get_logs_since(pid, last)
            for log in logs:
                last = max(last, log["ts"])
                yield f"data: {json.dumps({'ts':log['ts'],'line':log['line']})}\n\n"
            if not logs: yield 'data: {"ping":1}\n\n'
            time.sleep(1.5)
    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

# ── Process control ─────────────────────────────────────────────────────────────
import shlex

def _find_missing_script(cmd, pdir):
    """If cmd looks like `python(3) <script>` / `node <script>` and that script
    doesn't exist in pdir, return its name — else None. Lets us fail fast instead
    of endlessly crash-looping on a missing entry file."""
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return None
    if len(parts) < 2: return None
    interpreter = os.path.basename(parts[0]).lower()
    if interpreter not in ("python", "python3", "node", "nodejs"): return None
    for tok in parts[1:]:
        if tok.startswith("-"): continue
        script = tok
        if not os.path.isabs(script) and not os.path.exists(os.path.join(pdir, script)):
            return script
        return None
    return None

def _find_free_port():
    """Return an unused local TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def _get_public_url(server_id):
    """Build the public proxy URL for a panel."""
    host_url = os.environ.get("HOST_URL", "").rstrip("/")
    return f"{host_url}{BP}/live/{server_id}"

def _stream_pip(pid, req, pdir):
    """Install requirements.txt and stream each pip output line to the console."""
    req_hash = hashlib.sha256(open(req, "rb").read()).hexdigest()
    marker   = os.path.join(pdir, ".requirements_installed")
    prev     = open(marker).read().strip() if os.path.exists(marker) else None
    if req_hash == prev:
        push_log(pid, "[T10] requirements.txt unchanged — skipping reinstall (fast start).")
        return req_hash
    push_log(pid, "[T10] Installing requirements.txt …")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "-r", req,
             "--break-system-packages", "--no-input", "--no-color"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=pdir
        )
        for raw in iter(proc.stdout.readline, ""):
            line = raw.rstrip()
            if line: push_log(pid, f"[pip] {line}")
        proc.wait(timeout=180)
        if proc.returncode == 0:
            push_log(pid, "[T10] ✓ Requirements installed successfully.")
            with open(marker, "w") as mf: mf.write(req_hash)
            return req_hash
        push_log(pid, f"[T10] ✗ pip exited with code {proc.returncode} — check output above.")
    except subprocess.TimeoutExpired:
        push_log(pid, "[T10] pip timed out — starting anyway.")
    except Exception as e:
        push_log(pid, f"[T10] pip error: {e}")
    return None

def _start(pid):
    with get_db() as db:
        panel = db.execute("SELECT * FROM panels WHERE id=?", (pid,)).fetchone()
    if not panel: return False, "Panel not found"
    if panel["banned"]: return False, "This panel is banned"
    pdir = panel_dir(pid); cmd = panel["start_command"]
    missing = _find_missing_script(cmd, pdir)
    if missing:
        push_log(pid, f"[T10] ERROR: '{missing}' not found in your files. Upload it (or fix the Startup command) before pressing START.")
        return False, f"{missing} not found — upload your files first"
    req = os.path.join(pdir, "requirements.txt")
    if os.path.exists(req):
        _stream_pip(pid, req, pdir)
    # Assign a free port so the user's app can listen on it
    app_port = _find_free_port()
    env = os.environ.copy()
    env["PORT"] = str(app_port)
    env["HOST"] = "0.0.0.0"
    push_log(pid, f"[T10] Starting: {cmd}  (PORT={app_port})")
    push_log(pid, f"[T10] Public URL: {request.host_url.rstrip('/')}{BP}/live/{panel['server_id']}" if _request_ctx() else _get_public_url(panel['server_id']))
    push_log(pid, "[T10] For web apps: listen on host='0.0.0.0', port=int(os.environ.get('PORT',5000))")
    try:
        proc = subprocess.Popen(
            cmd, shell=True, cwd=pdir, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        threading.Thread(target=stream_proc, args=(pid, proc), daemon=True).start()
        PROCESSES[pid] = {"proc": proc, "start_time": time.time(), "port": app_port}
        with get_db() as db:
            db.execute("UPDATE panels SET status='running' WHERE id=?", (pid,)); db.commit()
        return True, "Started"
    except Exception as e: return False, str(e)

def _request_ctx():
    try:
        from flask import has_request_context
        return has_request_context()
    except: return False

@app.route(BP + "/panel/start", methods=["POST"])
@login_required
def start_panel():
    pid = session["panel_id"]
    if pid in PROCESSES: return jsonify({"ok":False,"msg":"Already running"})
    CRASH_COUNT.pop(pid, None)
    ok, msg = _start(pid)
    return jsonify({"ok":ok,"msg":msg})

@app.route(BP + "/panel/stop", methods=["POST"])
@login_required
def stop_panel():
    pid = session["panel_id"]
    CRASH_COUNT.pop(pid, None)
    info = PROCESSES.pop(pid, None)
    if info:
        try: info["proc"].terminate(); info["proc"].wait(timeout=5)
        except:
            try: info["proc"].kill()
            except: pass
    with get_db() as db:
        db.execute("UPDATE panels SET status='stopped' WHERE id=?", (pid,)); db.commit()
    push_log(pid, "[T10] Process stopped.")
    return jsonify({"ok":True})

@app.route(BP + "/panel/restart", methods=["POST"])
@login_required
def restart_panel():
    pid = session["panel_id"]
    CRASH_COUNT.pop(pid, None)
    info = PROCESSES.pop(pid, None)
    if info:
        try: info["proc"].terminate(); info["proc"].wait(timeout=5)
        except: pass
    push_log(pid, "[T10] Restarting ...")
    time.sleep(0.3)
    ok, msg = _start(pid)
    return jsonify({"ok":ok,"msg":msg})

@app.route(BP + "/panel/clear", methods=["POST"])
@login_required
def clear_console():
    pid = session["panel_id"]
    clear_logs(pid); push_log(pid, "[INFO] Logs cleared. Click START to begin...")
    return jsonify({"ok":True})

@app.route(BP + "/panel/stats")
@login_required
def panel_stats():
    return jsonify(proc_stats(session["panel_id"]))

# ── Files ────────────────────────────────────────────────────────────────────────
# Only truly dangerous / meaningless names are blocked; bot projects need almost
# any extension (.py, .pyc, .bak, .proto, .db, .session, no-extension files, etc).
BLOCKED_NAMES = {"", ".", ".."}

def _safe_extract(zf, pdir):
    base = os.path.realpath(pdir)
    for member in zf.infolist():
        target = os.path.realpath(os.path.join(pdir, member.filename))
        if not (target == base or target.startswith(base + os.sep)):
            continue  # skip zip-slip / path traversal entries
        zf.extract(member, pdir)

def _panel_relative_name(name):
    """Normalize a panel file path and reject traversal attempts."""
    raw = str(name or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/"):
        return None
    normalized = posixpath.normpath(raw)
    if normalized in ("", ".", "..") or normalized.startswith("../"):
        return None
    return normalized

def _panel_file_path(pid, name):
    """Return a safe (relative_name, absolute_path) pair."""
    rel = _panel_relative_name(name)
    if not rel:
        return None, None
    pdir = os.path.realpath(panel_dir(pid))
    path = os.path.realpath(os.path.join(pdir, *rel.split("/")))
    if path != pdir and not path.startswith(pdir + os.sep):
        return None, None
    return rel, path

def _maybe_detect_start_command(pid, pdir):
    """Auto-select the only root Python script when main.py is absent."""
    with get_db() as db:
        panel = db.execute("SELECT start_command FROM panels WHERE id=?", (pid,)).fetchone()
    if not panel or (panel["start_command"] or "").strip() != "python main.py":
        return None
    if os.path.isfile(os.path.join(pdir, "main.py")):
        return None
    candidates = sorted(
        name for name in os.listdir(pdir)
        if name.lower().endswith(".py")
        and os.path.isfile(os.path.join(pdir, name))
        and name != "__init__.py"
    )
    if len(candidates) != 1:
        return None
    command = f"python {candidates[0]}"
    with get_db() as db:
        db.execute("UPDATE panels SET start_command=? WHERE id=?", (command, pid))
        db.commit()
    push_log(pid, f"[T10] Auto-selected startup command: {command}")
    return command

@app.route(BP + "/panel/upload", methods=["POST"])
@login_required
def upload_file():
    pid = session["panel_id"]; pdir = panel_dir(pid)
    files = request.files.getlist("files")
    if not files: return jsonify({"ok":False,"msg":"No files selected"})
    uploaded, errors = [], []
    for f in files:
        name = (f.filename or "").strip()
        base = os.path.basename(name)
        if base in BLOCKED_NAMES:
            errors.append(f"{name or '(empty)'}: invalid filename"); continue
        ext = os.path.splitext(base)[1].lower()
        dest = os.path.join(pdir, base)
        try:
            f.save(dest)
        except Exception as e:
            errors.append(f"{name}: save failed — {e}"); continue
        if ext == ".zip":
            try:
                with zipfile.ZipFile(dest, "r") as zf:
                    _safe_extract(zf, pdir)
                os.remove(dest)
                uploaded.append(f"{name} (extracted)")
            except zipfile.BadZipFile:
                errors.append(f"{name}: not a valid ZIP file")
            except Exception as e:
                errors.append(f"{name} ZIP error: {e}")
        else:
            uploaded.append(name)
    req = os.path.join(pdir, "requirements.txt")
    auto_msg = None
    if os.path.exists(req) and (any("requirements.txt" in u for u in uploaded) or
                                 any("(extracted)" in u for u in uploaded)):
        # Run pip in a background thread so upload response returns immediately;
        # output streams to the panel console if the panel is open.
        def _bg_install():
            _stream_pip(pid, req, pdir)
        threading.Thread(target=_bg_install, daemon=True).start()
        auto_msg = "Installing requirements.txt in background — watch the Console tab for progress."
    startup_command = _maybe_detect_start_command(pid, pdir)
    return jsonify({"ok":True,"uploaded":uploaded,"errors":errors,
                    "auto_install":auto_msg,"startup_command":startup_command})

@app.route(BP + "/panel/files")
@login_required
def list_files():
    pdir = panel_dir(session["panel_id"]); files = []
    for root, _, names in os.walk(pdir):
        for name in sorted(names):
            fp = os.path.join(root, name)
            rel = os.path.relpath(fp, pdir).replace(os.sep, "/")
            if rel == ".requirements_installed" or not os.path.isfile(fp):
                continue
            files.append({"name":rel,"size":os.path.getsize(fp),
                          "modified":datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M")})
    files.sort(key=lambda item: item["name"].lower())
    return jsonify({"files":files})

@app.route(BP + "/panel/file/delete", methods=["POST"])
@login_required
def delete_file():
    pid = session["panel_id"]
    name = (request.json or {}).get("name","")
    rel, path = _panel_file_path(pid, name)
    if not rel:
        return jsonify({"ok":False,"msg":"Invalid file path"})
    if os.path.isfile(path):
        os.remove(path)
        with get_db() as db:
            db.execute("DELETE FROM shared_files WHERE panel_id=? AND filename=?", (pid, rel))
            db.commit()
        return jsonify({"ok":True})
    return jsonify({"ok":False,"msg":"Not found"})

@app.route(BP + "/panel/file/view")
@login_required
def view_file():
    pid = session["panel_id"]
    name = request.args.get("name","")
    rel, path = _panel_file_path(pid, name)
    if not rel or not os.path.isfile(path): return jsonify({"ok":False,"msg":"Not found"})
    try:
        with open(path,"r",errors="replace") as fh: content = fh.read(60000)
        return jsonify({"ok":True,"content":content})
    except Exception as e: return jsonify({"ok":False,"msg":str(e)})

@app.route(BP + "/panel/file/download")
@login_required
def download_file():
    pid = session["panel_id"]
    rel, path = _panel_file_path(pid, request.args.get("name", ""))
    if not rel or not os.path.isfile(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=os.path.basename(rel))

@app.route(BP + "/panel/file/share", methods=["POST"])
@login_required
def share_file():
    pid  = session["panel_id"]
    name = (request.json or {}).get("name","")
    rel, path = _panel_file_path(pid, name)
    if not rel or not os.path.isfile(path):
        return jsonify({"ok":False,"msg":"File not found"})
    # Return existing token if already shared
    with get_db() as db:
        row = db.execute("SELECT token FROM shared_files WHERE panel_id=? AND filename=?",
                         (pid, rel)).fetchone()
        if row:
            token = row["token"]
        else:
            token = secrets.token_urlsafe(24)
            db.execute("INSERT INTO shared_files (panel_id,filename,token,created_at) VALUES (?,?,?,?)",
                       (pid, rel, token, datetime.now().isoformat()))
            db.commit()
    host = request.host_url.rstrip("/")
    public_url = f"{host}{BP}/share/{token}/{rel}"
    return jsonify({"ok":True,"url":public_url,"token":token})

@app.route(BP + "/panel/file/unshare", methods=["POST"])
@login_required
def unshare_file():
    pid  = session["panel_id"]
    name, _ = _panel_file_path(pid, (request.json or {}).get("name",""))
    if not name:
        return jsonify({"ok":False,"msg":"Invalid file path"})
    with get_db() as db:
        db.execute("DELETE FROM shared_files WHERE panel_id=? AND filename=?", (pid, name))
        db.commit()
    return jsonify({"ok":True})

# ── Public file serving (no auth required) ──────────────────────────────────
@app.route(BP + "/share/<token>/<path:filename>")
def public_share(token, filename):
    requested_name = _panel_relative_name(filename)
    with get_db() as db:
        row = db.execute("SELECT panel_id, filename FROM shared_files WHERE token=?", (token,)).fetchone()
    if not row or not requested_name or row["filename"] != requested_name:
        abort(404)
    _, filepath = _panel_file_path(row["panel_id"], row["filename"])
    if not filepath or not os.path.isfile(filepath):
        abort(404)
    mime, _ = mimetypes.guess_type(row["filename"])
    mime = mime or "application/octet-stream"
    response = send_file(filepath, mimetype=mime, as_attachment=False,
                         download_name=row["filename"])
    # Cache public files for 5 minutes
    response.headers["Cache-Control"] = "public, max-age=300"
    return response

# ── Live proxy — public URL for hosted Flask/Node apps ─────────────────────────
# Accessible at /live/<server_id>  and  /live/<server_id>/<path>
# No auth required — the URL itself is the access key.

_PROXY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
    "content-encoding",   # let urllib handle this
}

def _proxy_request(target_url: str) -> Response:
    """Forward the current Flask request to target_url and stream back the response."""
    method  = request.method.upper()
    body    = request.get_data() or None
    # Build forwarded headers (skip hop-by-hop)
    fwd_headers = {k: v for k, v in request.headers if k.lower() not in _PROXY_HOP_HEADERS}
    fwd_headers["X-Forwarded-For"]   = request.remote_addr or "unknown"
    fwd_headers["X-Forwarded-Proto"] = request.scheme
    try:
        req = urllib.request.Request(target_url, data=body, headers=fwd_headers, method=method)
        resp = urllib.request.urlopen(req, timeout=30)
        raw_body = resp.read()
        status = resp.status
        resp_headers = {}
        for k, v in resp.headers.items():
            if k.lower() not in _PROXY_HOP_HEADERS:
                resp_headers[k] = v
        flask_resp = Response(raw_body, status=status, headers=resp_headers)
        return flask_resp
    except urllib.error.HTTPError as e:
        raw = e.read()
        resp_headers = {k: v for k, v in e.headers.items()
                        if k.lower() not in _PROXY_HOP_HEADERS}
        return Response(raw, status=e.code, headers=resp_headers)
    except urllib.error.URLError as e:
        reason = str(e.reason)
        html = f"""<!DOCTYPE html><html><head>
<title>Panel Not Ready</title>
<style>body{{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#0d1117;color:#c9d1d9}}
.box{{text-align:center;padding:40px;border:1px solid #30363d;border-radius:12px;max-width:420px}}
h2{{color:#f85149;margin-bottom:10px}}p{{color:#8b949e;line-height:1.6}}</style></head>
<body><div class='box'><h2>⚠ App Not Ready</h2>
<p>Your hosted app isn't responding yet.<br>Make sure it's <b>running</b> and listening on<br>
<code>host='0.0.0.0', port=int(os.environ.get('PORT',5000))</code></p>
<p style='margin-top:16px;font-size:12px;color:#6e7681'>Error: {reason}</p></div></body></html>"""
        return Response(html, status=502, mimetype="text/html")

@app.route(BP + "/live/<server_id>", defaults={"path": ""})
@app.route(BP + "/live/<server_id>/", defaults={"path": ""})
@app.route(BP + "/live/<server_id>/<path:path>")
def proxy_live(server_id, path):
    with get_db() as db:
        panel = db.execute("SELECT id FROM panels WHERE server_id=?", (server_id,)).fetchone()
    if not panel:
        return "Panel not found", 404
    pid = panel["id"]
    proc_info = PROCESSES.get(pid)

    # ── If a process is running, proxy to it ────────────────────────
    if proc_info and "port" in proc_info:
        port   = proc_info["port"]
        qs     = ("?" + request.query_string.decode()) if request.query_string else ""
        target = f"http://127.0.0.1:{port}/{path}{qs}"
        return _proxy_request(target)

    # ── No running process: try to serve static files directly ──────
    pdir = panel_dir(pid)
    # Resolve the requested path to a file
    req_path  = path.lstrip("/") if path else ""
    candidates = []
    if req_path:
        candidates.append(req_path)
        # try appending index.html for directory-style URLs
        candidates.append(req_path.rstrip("/") + "/index.html")
    # Always try index.html as the fallback root
    candidates.append("index.html")

    for candidate in candidates:
        safe = os.path.normpath(candidate)
        if safe.startswith(".."):
            continue
        fpath = os.path.join(pdir, safe)
        if os.path.isfile(fpath):
            mime, _ = mimetypes.guess_type(fpath)
            mime = mime or "application/octet-stream"
            resp = send_file(fpath, mimetype=mime)
            resp.headers["Cache-Control"] = "no-cache"
            return resp

    # ── Nothing to serve ────────────────────────────────────────────
    html = """<!DOCTYPE html><html><head><title>Panel Stopped</title>
<style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;
min-height:100vh;margin:0;background:#0d1117;color:#c9d1d9}
.box{text-align:center;padding:40px;border:1px solid #30363d;border-radius:12px;max-width:420px}
h2{color:#d29922;margin-bottom:10px}p{color:#8b949e;line-height:1.7}code{background:#161b22;
padding:2px 6px;border-radius:4px;font-size:13px}</style></head>
<body><div class='box'><h2>⏸ Panel is stopped</h2>
<p>Log in and press <b>START</b> to bring your app online.</p>
<p style="font-size:13px">Or upload an <code>index.html</code> to serve a static site — no START needed.</p>
</div></body></html>"""
    return Response(html, status=503, mimetype="text/html")

@app.route(BP + "/panel/live_url")
@login_required
def panel_live_url():
    pid = session["panel_id"]
    with get_db() as db:
        row = db.execute("SELECT server_id FROM panels WHERE id=?", (pid,)).fetchone()
    if not row: return jsonify({"ok": False})
    host_url = request.host_url.rstrip("/")
    url = f"{host_url}{BP}/live/{row['server_id']}"
    running = pid in PROCESSES and "port" in PROCESSES.get(pid, {})
    return jsonify({"ok": True, "url": url, "running": running})

@app.route(BP + "/panel/change_username", methods=["POST"])
@login_required
def change_username():
    pid  = session["panel_id"]
    data = request.get_json() or {}
    new_username = (data.get("new_username") or "").strip()
    password     = (data.get("password") or "").strip()
    if not new_username or not password:
        return jsonify({"ok": False, "msg": "Fill in all fields"})
    if len(new_username) < 3:
        return jsonify({"ok": False, "msg": "Username must be at least 3 characters"})
    if not new_username.replace("_","").replace("-","").isalnum():
        return jsonify({"ok": False, "msg": "Username: only letters, numbers, - and _ allowed"})
    with get_db() as db:
        row = db.execute("SELECT password FROM panels WHERE id=?", (pid,)).fetchone()
        if not row or row["password"] != hash_pw(password):
            return jsonify({"ok": False, "msg": "Password is incorrect"})
        try:
            db.execute("UPDATE panels SET username=? WHERE id=?", (new_username, pid))
            db.commit()
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "msg": "That username is already taken"})
    session["username"] = new_username
    return jsonify({"ok": True, "username": new_username})

@app.route(BP + "/panel/change_password", methods=["POST"])
@login_required
def change_password():
    pid  = session["panel_id"]
    data = request.get_json() or {}
    old  = (data.get("old_password") or "").strip()
    new  = (data.get("new_password") or "").strip()
    if not old or not new:
        return jsonify({"ok": False, "msg": "Fill in both fields"})
    if len(new) < 4:
        return jsonify({"ok": False, "msg": "New password must be at least 4 characters"})
    with get_db() as db:
        row = db.execute("SELECT password FROM panels WHERE id=?", (pid,)).fetchone()
        if not row or row["password"] != hash_pw(old):
            return jsonify({"ok": False, "msg": "Current password is wrong"})
        db.execute("UPDATE panels SET password=? WHERE id=?", (hash_pw(new), pid))
        db.commit()
    return jsonify({"ok": True})

@app.route(BP + "/panel/startup", methods=["GET","POST"])
@login_required
def startup():
    pid = session["panel_id"]
    if request.method == "POST":
        cmd = (request.json or {}).get("command","").strip()
        if not cmd: return jsonify({"ok":False,"msg":"Empty command"})
        with get_db() as db:
            db.execute("UPDATE panels SET start_command=? WHERE id=?", (cmd, pid)); db.commit()
        return jsonify({"ok":True})
    with get_db() as db:
        row = db.execute("SELECT start_command FROM panels WHERE id=?", (pid,)).fetchone()
    return jsonify({"command": row["start_command"] if row else "python main.py"})

# ── Admin ────────────────────────────────────────────────────────────────────────
@app.route(BP + "/admin", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        u = request.form.get("username","").strip(); p = request.form.get("password","").strip()
        with get_db() as db:
            row = db.execute("SELECT * FROM admins WHERE username=? AND password=?",
                             (u,hash_pw(p))).fetchone()
        if row:
            session["is_admin"] = True; session["admin_name"] = row["username"]
            return redirect(BP + "/admin/dashboard")
        return render_template("admin.html", page="login", error="Invalid credentials")
    return render_template("admin.html", page="login")

@app.route(BP + "/admin/dashboard")
@admin_required
def admin_dashboard():
    with get_db() as db:
        panels = db.execute("SELECT * FROM panels ORDER BY created_at DESC").fetchall()
    plist = [{**dict(p),"runtime_status":proc_stats(p["id"])["status"],"banned":bool(p["banned"])} for p in panels]
    return render_template("admin.html", page="dashboard", panels=plist, admin=session.get("admin_name"))

@app.route(BP + "/admin/create", methods=["POST"])
@admin_required
def admin_create():
    data = request.get_json() or request.form
    u = (data.get("username") or "").strip(); p = (data.get("password") or "").strip()
    ram = int(data.get("ram") or 512)
    disk = int(data.get("disk") or 1024); cmd = (data.get("start_command") or "python main.py").strip()
    if not u or not p: return jsonify({"ok":False,"msg":"Username and password required"})
    pid = uuid.uuid4().hex; sid = uuid.uuid4().hex[:8]
    # Hosting is lifetime/24-7. Admin ban or delete are the only controls that
    # should disable or remove a panel.
    exp = LIFETIME_EXPIRY
    try:
        os.makedirs(os.path.join(DATA_DIR, pid), exist_ok=False)
        with get_db() as db:
            db.execute("""INSERT INTO panels
                (id,username,password,server_id,type,ram_limit,disk_limit,start_command,status,expires_at,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (pid,u,hash_pw(p),sid,"python",ram,disk,cmd,"stopped",exp,datetime.now().isoformat()))
            db.commit()
        return jsonify({"ok":True,"panel_id":pid,"server_id":sid,"username":u,"password":p,"expires":"Lifetime"})
    except sqlite3.IntegrityError:
        shutil.rmtree(os.path.join(DATA_DIR, pid), ignore_errors=True)
        return jsonify({"ok":False,"msg":"Username already exists"})
    except Exception as exc:
        shutil.rmtree(os.path.join(DATA_DIR, pid), ignore_errors=True)
        return jsonify({"ok":False,"msg":f"Panel storage error: {exc}"})

@app.route(BP + "/admin/ban", methods=["POST"])
@admin_required
def admin_ban():
    data = request.get_json() or {}
    pid  = data.get("panel_id")
    if not pid: return jsonify({"ok": False, "msg": "Missing panel_id"})
    # Stop process if running
    info = PROCESSES.pop(pid, None)
    if info:
        try: info["proc"].terminate(); info["proc"].wait(timeout=5)
        except: pass
    with get_db() as db:
        db.execute("UPDATE panels SET banned=1, status='stopped' WHERE id=?", (pid,))
        db.commit()
    return jsonify({"ok": True})

@app.route(BP + "/admin/unban", methods=["POST"])
@admin_required
def admin_unban():
    pid = (request.get_json() or {}).get("panel_id")
    if not pid: return jsonify({"ok": False, "msg": "Missing panel_id"})
    with get_db() as db:
        db.execute("UPDATE panels SET banned=0 WHERE id=?", (pid,))
        db.commit()
    return jsonify({"ok": True})

@app.route(BP + "/admin/reset_password", methods=["POST"])
@admin_required
def admin_reset_password():
    data = request.get_json() or {}
    pid  = data.get("panel_id")
    new_pw = (data.get("password") or "").strip()
    if not pid or not new_pw:
        return jsonify({"ok": False, "msg": "Missing fields"})
    with get_db() as db:
        db.execute("UPDATE panels SET password=? WHERE id=?", (hash_pw(new_pw), pid))
        db.commit()
    return jsonify({"ok": True})

@app.route(BP + "/admin/delete", methods=["POST"])
@admin_required
def admin_delete():
    pid = (request.get_json() or {}).get("panel_id")
    if not pid: return jsonify({"ok":False,"msg":"Missing panel_id"})
    info = PROCESSES.pop(pid, None)
    if info:
        try: info["proc"].terminate()
        except: pass
    pdir = os.path.join(DATA_DIR, pid)
    if os.path.isdir(pdir): shutil.rmtree(pdir)
    with get_db() as db:
        db.execute("DELETE FROM panels WHERE id=?", (pid,)); db.commit()
    return jsonify({"ok":True})

@app.route(BP + "/admin/extend", methods=["POST"])
@admin_required
def admin_extend():
    data = request.get_json() or {}
    pid = data.get("panel_id"); days = int(data.get("days") or 15)
    with get_db() as db:
        row = db.execute("SELECT expires_at FROM panels WHERE id=?", (pid,)).fetchone()
        if not row: return jsonify({"ok":False,"msg":"Not found"})
        try: base = datetime.fromisoformat(row["expires_at"])
        except: base = datetime.now()
        if base < datetime.now(): base = datetime.now()
        new_exp = (base+timedelta(days=days)).isoformat()
        db.execute("UPDATE panels SET expires_at=? WHERE id=?", (new_exp, pid)); db.commit()
    return jsonify({"ok":True,"expires":new_exp[:10]})

@app.route(BP + "/admin/logout")
def admin_logout():
    session.pop("is_admin",None); session.pop("admin_name",None)
    return redirect(BP + "/admin")

# ── Telegram Bot fleet management (admin) ─────────────────────────────────────────
@app.route(BP + "/admin/tgbots")
@admin_required
def admin_tgbots():
    with get_db() as db:
        rows = db.execute("SELECT * FROM tg_bots ORDER BY created_at DESC").fetchall()
    bots = []
    for r in rows:
        d = dict(r)
        d["live"] = r["id"] in bot_engine.BOT_INSTANCES
        bots.append(d)
    return jsonify({"ok": True, "bots": bots})

@app.route(BP + "/admin/tgbots/add", methods=["POST"])
@admin_required
def admin_tgbots_add():
    data = request.get_json() or request.form
    token = (data.get("token") or "").strip()
    owner_admin_id = (data.get("owner_admin_id") or "").strip()
    owner_admin_username = (data.get("owner_admin_username") or "").strip().lstrip("@")
    force_channel = (data.get("force_channel") or "").strip() or None
    if not token or (not owner_admin_id and not owner_admin_username):
        return jsonify({"ok": False, "msg": "Bot token and admin username or Telegram ID are required"})
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO tg_bots (token, owner_admin_id, owner_admin_username, status, force_channel, created_at) VALUES (?,?,?,?,?,?)",
                (token, owner_admin_id or "", owner_admin_username or None, "stopped", force_channel, datetime.now().isoformat()),
            )
            db.commit()
            row = db.execute("SELECT * FROM tg_bots WHERE token=?", (token,)).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "msg": "This bot token is already added"})
    ok, msg = bot_engine.start_bot(
        row["id"], token, owner_admin_id, force_channel,
        owner_admin_username=row["owner_admin_username"],
    )
    if not ok:
        with get_db() as db:
            db.execute("DELETE FROM tg_bots WHERE id=?", (row["id"],)); db.commit()
        return jsonify({"ok": False, "msg": msg})
    return jsonify({"ok": True, "bot_username": msg})

@app.route(BP + "/admin/tgbots/toggle", methods=["POST"])
@admin_required
def admin_tgbots_toggle():
    data = request.get_json() or {}
    bot_id = data.get("bot_id")
    with get_db() as db:
        row = db.execute("SELECT * FROM tg_bots WHERE id=?", (bot_id,)).fetchone()
    if not row: return jsonify({"ok": False, "msg": "Not found"})
    if bot_id in bot_engine.BOT_INSTANCES:
        bot_engine.stop_bot(bot_id)
        return jsonify({"ok": True, "status": "stopped"})
    ok, msg = bot_engine.start_bot(
        bot_id, row["token"], row["owner_admin_id"], row["force_channel"],
        owner_admin_username=row["owner_admin_username"],
    )
    return jsonify({"ok": ok, "status": "running" if ok else "stopped", "msg": msg})

@app.route(BP + "/admin/tgbots/setchannel", methods=["POST"])
@admin_required
def admin_tgbots_setchannel():
    data = request.get_json() or {}
    bot_id = data.get("bot_id")
    force_channel = (data.get("force_channel") or "").strip() or None
    with get_db() as db:
        row = db.execute("SELECT * FROM tg_bots WHERE id=?", (bot_id,)).fetchone()
        if not row: return jsonify({"ok": False, "msg": "Not found"})
        db.execute("UPDATE tg_bots SET force_channel=? WHERE id=?", (force_channel, bot_id))
        db.commit()
    if bot_id in bot_engine.BOT_INSTANCES:
        bot_engine.stop_bot(bot_id)
        ok, msg = bot_engine.start_bot(
            bot_id, row["token"], row["owner_admin_id"], force_channel,
            owner_admin_username=row["owner_admin_username"],
        )
        if not ok:
            return jsonify({"ok": False, "msg": msg})
    return jsonify({"ok": True})

@app.route(BP + "/admin/tgbots/delete", methods=["POST"])
@admin_required
def admin_tgbots_delete():
    bot_id = (request.get_json() or {}).get("bot_id")
    bot_engine.stop_bot(bot_id)
    with get_db() as db:
        db.execute("DELETE FROM tg_bots WHERE id=?", (bot_id,))
        db.execute("DELETE FROM tg_bot_users WHERE bot_id=?", (bot_id,))
        db.commit()
    return jsonify({"ok": True})

# ── Telegram Bot API ─────────────────────────────────────────────────────────────
BOT_SECRET = os.environ.get("BOT_SECRET", "bdx-bot-secret-key")

@app.route(BP + "/api/bot/create", methods=["POST"])
def bot_create():
    if request.headers.get("X-Bot-Secret","") != BOT_SECRET:
        return jsonify({"ok":False,"msg":"Unauthorized"}), 401
    data = request.get_json() or {}
    u = (data.get("username") or "").strip(); p = (data.get("password") or "").strip()
    days = int(data.get("days") or 15); ram = int(data.get("ram") or 512); disk = int(data.get("disk") or 1024)
    if not u or not p: return jsonify({"ok":False,"msg":"username and password required"})
    pid = uuid.uuid4().hex; sid = uuid.uuid4().hex[:8]
    exp = (datetime.now()+timedelta(days=days)).isoformat()
    try:
        with get_db() as db:
            db.execute("""INSERT INTO panels
                (id,username,password,server_id,type,ram_limit,disk_limit,start_command,status,expires_at,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (pid,u,hash_pw(p),sid,"python",ram,disk,"python main.py","stopped",exp,datetime.now().isoformat()))
            db.commit()
        panel_dir(pid)
        host = os.environ.get("HOST_URL", request.host_url.rstrip("/"))
        return jsonify({"ok":True,"panel_id":pid,"server_id":sid,"username":u,"password":p,
                        "expires":exp[:10],"login_url":f"{host}{BP}/"})
    except sqlite3.IntegrityError: return jsonify({"ok":False,"msg":"Username already taken"})

@app.route(BP + "/api/bot/panels", methods=["GET"])
def bot_panels():
    if request.headers.get("X-Bot-Secret","") != BOT_SECRET: return jsonify({"ok":False}), 401
    with get_db() as db:
        rows = db.execute("SELECT id,username,server_id,status,expires_at FROM panels").fetchall()
    return jsonify({"ok":True,"panels":[dict(r) for r in rows]})

# ── Static files (needed when running behind proxy) ──────────────────────────────
@app.route(BP + "/static/<path:filename>")
def custom_static(filename):
    from flask import send_from_directory
    return send_from_directory(os.path.join(BASE_DIR, "static"), filename)

# ── 24/7 keep-alive: resume-on-boot + periodic restart sweep ─────────────────────
RESTART_INTERVAL_SEC = 15 * 60  # 15 minutes, per user request

def _resume_running_panels():
    """Resume every non-banned panel marked running in the persistent DB."""
    try:
        with get_db() as db:
            rows = db.execute("SELECT * FROM panels WHERE status='running' AND banned=0").fetchall()
        for row in rows:
            pid = row["id"]
            if pid in PROCESSES:
                continue
            push_log(pid, "[T10] Server restarted — auto-resuming your bot...")
            CRASH_COUNT.pop(pid, None)
            _start(pid)
    except Exception as e:
        logger_print(f"[T10] resume-on-boot error: {e}")

def _periodic_restart_sweep():
    """Every 5 minutes: check panels that should be running and revive any that
    silently died. Does NOT force-kill healthy running processes."""
    while True:
        time.sleep(5 * 60)
        try:
            with get_db() as db:
                rows = db.execute("SELECT * FROM panels WHERE status='running' AND banned=0").fetchall()
            for row in rows:
                pid = row["id"]
                info = PROCESSES.get(pid)
                if info:
                    # Check if the process is still alive
                    try:
                        if info["proc"].poll() is None:
                            continue  # still running — leave it alone
                    except Exception:
                        pass
                    # Process object exists but process is dead — clean up
                    PROCESSES.pop(pid, None)
                # Not in PROCESSES or dead — needs restart
                push_log(pid, "[T10] Health check: process not running — auto-restarting...")
                CRASH_COUNT.pop(pid, None)
                _start(pid)
        except Exception as e:
            logger_print(f"[T10] health-check sweep error: {e}")

def logger_print(msg):
    print(msg, flush=True)

# ── Boot ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    repair_panel_storage()
    _resume_running_panels()
    threading.Thread(target=_periodic_restart_sweep, daemon=True).start()
    threading.Thread(target=bot_engine.resume_all, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    print(f"[T10-MEHEDI] Listening on :{port}  base={BP or '/'}")
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
