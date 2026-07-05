import os, sys, json, time, uuid, shutil, hashlib, zipfile
import sqlite3, threading, subprocess
from datetime import datetime, timedelta
from functools import wraps

import psutil
from flask import (Flask, render_template, request, session,
                   redirect, url_for, jsonify, Response, stream_with_context)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data", "panels")
DB_PATH   = os.path.join(BASE_DIR, "data", "bdx.db")
os.makedirs(DATA_DIR, exist_ok=True)

# Base path prefix (set via env on Replit, empty string on bare VPS)
BP = os.environ.get("BASE_PATH", "").rstrip("/")   # e.g. "/bdx" or ""

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bdx-hosting-secret-2025")
app.config["SESSION_COOKIE_PATH"] = BP + "/" if BP else "/"
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB upload limit

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
            expires_at    TEXT NOT NULL,
            created_at    TEXT NOT NULL
        );
        """)
        pw = hashlib.sha256("admin".encode()).hexdigest()
        db.execute("DELETE FROM admins WHERE username=?", ("admin",))
        db.execute("INSERT OR IGNORE INTO admins (username,password) VALUES (?,?)", ("mehedi", pw))
        db.commit()

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def panel_dir(pid): d = os.path.join(DATA_DIR, pid); os.makedirs(d, exist_ok=True); return d
def is_expired(exp):
    try: return datetime.fromisoformat(exp) < datetime.now()
    except: return True

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
        p   = psutil.Process(info["proc"].pid)
        cpu = p.cpu_percent(interval=0.1)
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
        # Process exited on its own (not via manual STOP) — treat as a crash and
        # auto-restart so 24/7-hosted bots stay online.
        n = CRASH_COUNT.get(pid, 0) + 1
        CRASH_COUNT[pid] = n
        if n <= 20:
            delay = min(30, 2 * n)
            push_log(pid, f"[T10] Unexpected exit — auto-restarting in {delay}s (attempt {n})...")
            def _delayed_restart():
                time.sleep(delay)
                with get_db() as db:
                    row = db.execute("SELECT expires_at FROM panels WHERE id=?", (pid,)).fetchone()
                if row and not is_expired(row["expires_at"]) and pid not in PROCESSES:
                    _start(pid)
            threading.Thread(target=_delayed_restart, daemon=True).start()
            return
        else:
            push_log(pid, "[T10] Too many crashes — giving up auto-restart. Check your code and press START manually.")
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
            if is_expired(row["expires_at"]):
                return render_template("login.html", error="Your panel has expired.")
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
            time.sleep(0.7)
    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

# ── Process control ─────────────────────────────────────────────────────────────
def _start(pid):
    with get_db() as db:
        panel = db.execute("SELECT * FROM panels WHERE id=?", (pid,)).fetchone()
    if not panel: return False, "Panel not found"
    if is_expired(panel["expires_at"]): return False, "Panel expired"
    pdir = panel_dir(pid); cmd = panel["start_command"]
    req = os.path.join(pdir, "requirements.txt")
    if os.path.exists(req):
        push_log(pid, "[T10] Installing requirements.txt ...")
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", req, "-q"],
                               capture_output=True, text=True, cwd=pdir, timeout=120)
            push_log(pid, "[T10] Done." if r.returncode == 0 else f"[T10] pip: {r.stderr[:200]}")
        except subprocess.TimeoutExpired:
            push_log(pid, "[T10] pip timed out — starting anyway.")
    push_log(pid, f"[T10] Starting: {cmd}")
    try:
        proc = subprocess.Popen(cmd, shell=True, cwd=pdir,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        threading.Thread(target=stream_proc, args=(pid, proc), daemon=True).start()
        PROCESSES[pid] = {"proc": proc, "start_time": time.time()}
        with get_db() as db:
            db.execute("UPDATE panels SET status='running' WHERE id=?", (pid,)); db.commit()
        return True, "Started"
    except Exception as e: return False, str(e)

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
    auto_msg = None
    req = os.path.join(pdir, "requirements.txt")
    if os.path.exists(req) and (any("requirements.txt" in u for u in uploaded) or
                                 any("(extracted)" in u for u in uploaded)):
        try:
            r = subprocess.run([sys.executable,"-m","pip","install","-r",req,"-q"],
                               capture_output=True, text=True, cwd=pdir, timeout=180)
            auto_msg = "requirements.txt installed" if r.returncode==0 else f"pip: {r.stderr[:200]}"
        except subprocess.TimeoutExpired:
            auto_msg = "pip install timed out — try installing manually via startup command"
        except Exception as e: auto_msg = f"pip error: {e}"
    return jsonify({"ok":True,"uploaded":uploaded,"errors":errors,"auto_install":auto_msg})

@app.route(BP + "/panel/files")
@login_required
def list_files():
    pdir = panel_dir(session["panel_id"]); files = []
    for name in sorted(os.listdir(pdir)):
        fp = os.path.join(pdir, name)
        if os.path.isfile(fp):
            files.append({"name":name,"size":os.path.getsize(fp),
                          "modified":datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M")})
    return jsonify({"files":files})

@app.route(BP + "/panel/file/delete", methods=["POST"])
@login_required
def delete_file():
    pdir = panel_dir(session["panel_id"])
    name = (request.json or {}).get("name","")
    path = os.path.join(pdir, os.path.basename(name))
    if os.path.isfile(path): os.remove(path); return jsonify({"ok":True})
    return jsonify({"ok":False,"msg":"Not found"})

@app.route(BP + "/panel/file/view")
@login_required
def view_file():
    pdir = panel_dir(session["panel_id"])
    name = request.args.get("name","")
    path = os.path.join(pdir, os.path.basename(name))
    if not os.path.isfile(path): return jsonify({"ok":False,"msg":"Not found"})
    try:
        with open(path,"r",errors="replace") as fh: content = fh.read(60000)
        return jsonify({"ok":True,"content":content})
    except Exception as e: return jsonify({"ok":False,"msg":str(e)})

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
    plist = [{**dict(p),"runtime_status":proc_stats(p["id"])["status"]} for p in panels]
    return render_template("admin.html", page="dashboard", panels=plist, admin=session.get("admin_name"))

@app.route(BP + "/admin/create", methods=["POST"])
@admin_required
def admin_create():
    data = request.get_json() or request.form
    u = (data.get("username") or "").strip(); p = (data.get("password") or "").strip()
    days = int(data.get("days") or 15); ram = int(data.get("ram") or 512)
    disk = int(data.get("disk") or 1024); cmd = (data.get("start_command") or "python main.py").strip()
    if not u or not p: return jsonify({"ok":False,"msg":"Username and password required"})
    pid = uuid.uuid4().hex; sid = uuid.uuid4().hex[:8]
    exp = (datetime.now()+timedelta(days=days)).isoformat()
    try:
        with get_db() as db:
            db.execute("""INSERT INTO panels
                (id,username,password,server_id,type,ram_limit,disk_limit,start_command,status,expires_at,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (pid,u,hash_pw(p),sid,"python",ram,disk,cmd,"stopped",exp,datetime.now().isoformat()))
            db.commit()
        panel_dir(pid)
        return jsonify({"ok":True,"panel_id":pid,"server_id":sid,"username":u,"password":p,"expires":exp[:10]})
    except sqlite3.IntegrityError: return jsonify({"ok":False,"msg":"Username already exists"})

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

# ── Boot ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"[T10-MEHEDI] Listening on :{port}  base={BP or '/'}")
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
