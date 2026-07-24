/* ── Base path (set from template) ───────────────────────────────── */
const BP = window.BP || "";

/* ── SSE Console ─────────────────────────────────────────────────── */
const consoleEl = document.getElementById("console-output");
let lastTs      = 0;
let evtSource   = null;

function connectSSE() {
  if (evtSource) evtSource.close();
  evtSource = new EventSource(BP + "/panel/stream?since=" + lastTs);

  evtSource.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      if (d.ping) return;
      if (d.line !== undefined) {
        appendLine(d.line);
        lastTs = Math.max(lastTs, d.ts || 0);
      }
    } catch (_) {}
  };

  evtSource.onerror = () => {
    evtSource.close();
    setTimeout(connectSSE, 2000);
  };
}

function appendLine(line) {
  if (!consoleEl) return;
  const span = document.createElement("span");
  span.textContent = line + "\n";
  if      (line.startsWith("[T10]"))   span.className = "log-bdx";
  else if (line.startsWith("[ERROR]") || line.includes("Error") || line.includes("Traceback"))
                                        span.className = "log-err";
  else if (line.startsWith("[INFO]"))   span.className = "log-info";
  else if (line.startsWith("[PROCESS")) span.className = "log-exit";
  consoleEl.appendChild(span);
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

connectSSE();

/* ── Stats polling ───────────────────────────────────────────────── */
let statsTimer = null;

function startStats() {
  if (statsTimer) return;
  statsTimer = setInterval(async () => {
    try {
      const j = await (await fetch(BP + "/panel/stats")).json();
      setStatUI(j);
      if (j.status !== "running") { stopStats(); setLiveUrlUI(false); }
    } catch (_) {}
  }, 2500);
}

function stopStats() {
  clearInterval(statsTimer); statsTimer = null;
}

function setStatUI(j) {
  setEl("uptime-val",  j.uptime);
  setEl("cpu-ram-val", `${j.cpu}% / ${j.ram}MB`);
  const sv = document.getElementById("status-val");
  if (sv) sv.innerHTML = j.status === "running"
    ? '<span class="green">RUNNING</span>'
    : '<span class="gray">STOPPED</span>';
}

/* ── Live/Public URL ─────────────────────────────────────────────── */
let _liveUrl = "";

async function loadLiveUrl() {
  try {
    const j = await (await fetch(BP + "/panel/live_url")).json();
    if (j.ok) {
      _liveUrl = j.url;
      setLiveUrlUI(j.running);
    }
  } catch (_) {}
}

function setLiveUrlUI(running) {
  const dot  = document.getElementById("live-dot");
  const link = document.getElementById("live-url-val");
  const card = document.getElementById("live-url-card");
  if (!link) return;
  if (_liveUrl) {
    link.textContent = _liveUrl;
    link.href = _liveUrl;
  }
  if (dot) {
    dot.className = "live-dot " + (running ? "live-dot-on" : "live-dot-off");
    dot.title = running ? "App is running" : "App is stopped";
  }
  if (card) card.className = "live-url-card " + (running ? "live-url-running" : "live-url-stopped");
}

function copyLiveUrl() {
  if (!_liveUrl) return;
  navigator.clipboard.writeText(_liveUrl).then(() => {
    const btn = document.getElementById("btn-copy-live");
    if (btn) { btn.innerHTML = '<i class="fa fa-check"></i> Copied!'; setTimeout(() => { btn.innerHTML = '<i class="fa fa-copy"></i> Copy'; }, 2000); }
  }).catch(() => {});
}

loadLiveUrl();

function setEl(id, text) {
  const el = document.getElementById(id); if (el) el.textContent = text;
}

if (window.PANEL_STATUS === "running") startStats();

/* ── Controls ────────────────────────────────────────────────────── */
async function startPanel() {
  lockBtn("starting");
  const j = await post(BP + "/panel/start");
  if (j.ok) { lockBtn("running"); startStats(); setTimeout(loadLiveUrl, 1500); }
  else       { unlockBtn(); appendLine("[ERROR] " + j.msg); }
}

async function stopPanel() {
  const j = await post(BP + "/panel/stop");
  unlockBtn(); stopStats();
  setStatUI({ status:"stopped", uptime:"0m 0s", cpu:"0.0", ram:"0" });
  setLiveUrlUI(false);
}

async function restartPanel() {
  lockBtn("starting");
  stopStats(); setLiveUrlUI(false);
  const j = await post(BP + "/panel/restart");
  if (j.ok) { lockBtn("running"); startStats(); setTimeout(loadLiveUrl, 1500); }
  else       { unlockBtn(); appendLine("[ERROR] " + (j.msg||"restart failed")); }
}

async function clearConsole() {
  await post(BP + "/panel/clear");
  if (consoleEl) consoleEl.innerHTML = "";
  lastTs = 0;
  connectSSE();
}

function lockBtn(state) {
  btn("btn-start").disabled   = true;
  btn("btn-stop").disabled    = (state !== "running");
  btn("btn-restart").disabled = false;
  const sv = document.getElementById("status-val");
  if (sv) sv.innerHTML = state === "running"
    ? '<span class="green">RUNNING</span>'
    : '<span class="yellow">STARTING...</span>';
}

function unlockBtn() {
  btn("btn-start").disabled   = false;
  btn("btn-stop").disabled    = true;
  btn("btn-restart").disabled = false;
}

function btn(id) { return document.getElementById(id) || {disabled:false}; }

if (window.PANEL_STATUS === "running") {
  btn("btn-start").disabled = true;
  btn("btn-stop").disabled  = false;
}

/* ── Terminal input ──────────────────────────────────────────────── */
function handleCmd(e) {
  if (e.key !== "Enter") return;
  const inp = document.getElementById("cmd-input");
  const cmd = inp.value.trim();
  if (!cmd) return;
  appendLine("$ " + cmd);
  inp.value = "";
}

/* ── Tabs ────────────────────────────────────────────────────────── */
function switchTab(name, el) {
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("tab-" + name)?.classList.add("active");
  el.classList.add("active");
  if (name === "files") loadFiles();
}

/* ── Files ───────────────────────────────────────────────────────── */
async function uploadFiles(files) {
  if (!files?.length) return;
  const msg = document.getElementById("upload-msg");
  setMsg(msg, "Uploading ...", "info");
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  const j = await (await fetch(BP + "/panel/upload", {method:"POST", body:fd})).json();
  if (j.ok) {
    let txt = "Uploaded: " + j.uploaded.join(", ");
    if (j.auto_install) txt += "  |  pip: " + j.auto_install;
    if (j.errors.length) txt += "  |  Errors: " + j.errors.join(", ");
    setMsg(msg, txt, "success");
    loadFiles();
  } else {
    setMsg(msg, j.msg, "error");
  }
  document.getElementById("file-input").value = "";
}

async function loadFiles() {
  const j = await (await fetch(BP + "/panel/files")).json();
  const tb = document.getElementById("file-tbody");
  if (!tb) return;
  if (!j.files.length) {
    tb.innerHTML = '<tr><td colspan="4" class="empty-td">No files uploaded yet.</td></tr>';
    return;
  }
  tb.innerHTML = j.files.map(f => `
    <tr data-name="${esc(f.name)}">
      <td><i class="fa fa-file-code"></i> ${esc(f.name)}</td>
      <td>${(f.size/1024).toFixed(1)} KB</td>
      <td>${esc(f.modified)}</td>
      <td>
        <button class="btn-sm btn-view"  onclick="viewFile('${esc(f.name)}')"><i class="fa fa-eye"></i></button>
        <button class="btn-sm btn-share" onclick="shareFile('${esc(f.name)}', this)" title="Get public URL"><i class="fa fa-link"></i></button>
        <button class="btn-sm btn-del"   onclick="deleteFile('${esc(f.name)}')"><i class="fa fa-trash"></i></button>
      </td>
    </tr>`).join("");
}

async function deleteFile(name) {
  if (!confirm(`Delete "${name}"?`)) return;
  const j = await post(BP + "/panel/file/delete", {name});
  if (j.ok) { document.querySelector(`[data-name="${name}"]`)?.remove(); loadFiles(); }
}

/* ── File sharing ────────────────────────────────────────────────── */
let _currentShareName = "";

async function shareFile(name, btn) {
  btn.disabled = true;
  const j = await post(BP + "/panel/file/share", {name});
  btn.disabled = false;
  if (!j.ok) { alert(j.msg || "Share failed"); return; }
  _currentShareName = name;
  document.getElementById("share-url-input").value = j.url;
  document.getElementById("share-popup").classList.remove("hidden");
  document.getElementById("btn-copy-url").textContent = "Copy";
  document.getElementById("btn-copy-url").innerHTML = '<i class="fa fa-copy"></i> Copy';
}

function closeSharePopup() {
  document.getElementById("share-popup").classList.add("hidden");
  _currentShareName = "";
}

function copyShareUrl() {
  const inp = document.getElementById("share-url-input");
  navigator.clipboard.writeText(inp.value).then(() => {
    const btn = document.getElementById("btn-copy-url");
    btn.innerHTML = '<i class="fa fa-check"></i> Copied!';
    setTimeout(() => { btn.innerHTML = '<i class="fa fa-copy"></i> Copy'; }, 2000);
  }).catch(() => {
    inp.select(); document.execCommand("copy");
  });
}

async function unshareFile() {
  if (!_currentShareName) return;
  if (!confirm("Revoke this public link? It will stop working.")) return;
  await post(BP + "/panel/file/unshare", {name: _currentShareName});
  closeSharePopup();
}

// Close share popup on backdrop click
document.addEventListener("click", e => {
  const popup = document.getElementById("share-popup");
  if (popup && !popup.classList.contains("hidden") && e.target === popup) closeSharePopup();
});

async function viewFile(name) {
  const j = await (await fetch(BP + "/panel/file/view?name=" + encodeURIComponent(name))).json();
  if (j.ok) {
    document.getElementById("modal-filename").textContent = name;
    document.getElementById("modal-content").textContent  = j.content;
    document.getElementById("file-modal").classList.remove("hidden");
  } else { alert(j.msg); }
}

function closeModal() { document.getElementById("file-modal").classList.add("hidden"); }
document.getElementById("file-modal")?.addEventListener("click", e => {
  if (e.target === e.currentTarget) closeModal();
});

/* ── Startup ─────────────────────────────────────────────────────── */
async function saveStartup() {
  const cmd = document.getElementById("startup-cmd")?.value.trim();
  const msg = document.getElementById("startup-msg");
  if (!cmd) { setMsg(msg, "Command cannot be empty", "error"); return; }
  const j = await post(BP + "/panel/startup", {command: cmd});
  setMsg(msg, j.ok ? "Startup command saved!" : j.msg, j.ok ? "success" : "error");
  setTimeout(() => { msg.textContent = ""; msg.className = "startup-msg"; }, 3000);
}

/* ── Drag & drop ─────────────────────────────────────────────────── */
const zone = document.getElementById("upload-zone");
if (zone) {
  ["dragenter","dragover"].forEach(ev =>
    zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add("dragover"); }));
  ["dragleave","drop"].forEach(ev =>
    zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove("dragover"); }));
  zone.addEventListener("drop", e => uploadFiles(e.dataTransfer.files));
}

/* ── Helpers ─────────────────────────────────────────────────────── */
async function post(url, body) {
  const opts = { method: "POST" };
  if (body) {
    opts.headers = {"Content-Type":"application/json"};
    opts.body    = JSON.stringify(body);
  }
  try { return await (await fetch(url, opts)).json(); }
  catch (e) { return {ok: false, msg: String(e)}; }
}

function setMsg(el, txt, cls) {
  if (!el) return;
  el.textContent = txt;
  el.className   = "upload-msg " + cls;
}

function esc(s) {
  return String(s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
