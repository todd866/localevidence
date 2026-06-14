// LocalEvidence PWA — vanilla JS, offline-first.
// Caches the ledger + opened answers in localStorage so previously-worked
// questions are instant and available with no connection. Novel questions hit
// the backend, return live evidence, and queue for the next home deep-run.

const $ = (id) => document.getElementById(id);
const LS = {
  get: (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};

// HTML-escape ALL untrusted text (corpus passages, paper titles, the user's
// questions) before it touches innerHTML. This is both an XSS guard and a
// correctness fix — clinical text is full of '<' and '>' (SpO2 <90%, pH <7.3,
// Z ≥2.5 and <5) that would otherwise be parsed as markup and vanish.
const esc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
// confidence -> safe CSS class (allowlist; never interpolate raw into an attribute)
const cls = (c) => ["high", "moderate", "low"].includes(c) ? c : "";

// ---- minimal markdown -> HTML (headers, bold/italic, lists, quotes, links, code, tables)
function md(src) {
  const inline = (s) => esc(s)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
  const lines = (src || "").split("\n");
  let out = [], i = 0;
  while (i < lines.length) {
    let l = lines[i];
    if (/^#{1,3}\s/.test(l)) { const n = l.match(/^#+/)[0].length; out.push(`<h${n}>${inline(l.replace(/^#+\s/, ""))}</h${n}>`); i++; continue; }
    if (/^>\s?/.test(l)) { let b = []; while (i < lines.length && /^>\s?/.test(lines[i])) { b.push(inline(lines[i].replace(/^>\s?/, ""))); i++; } out.push(`<blockquote>${b.join("<br>")}</blockquote>`); continue; }
    if (/^\s*[-*]\s/.test(l)) { let it = []; while (i < lines.length && /^\s*[-*]\s/.test(lines[i])) { it.push(`<li>${inline(lines[i].replace(/^\s*[-*]\s/, ""))}</li>`); i++; } out.push(`<ul>${it.join("")}</ul>`); continue; }
    if (/^\s*\|.*\|/.test(l)) { let rows = []; while (i < lines.length && /\|/.test(lines[i])) { rows.push(lines[i]); i++; }
      const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      let html = "<table>"; rows.forEach((r, ri) => { if (/^\s*\|?[\s:|-]+\|?\s*$/.test(r)) return; const tag = ri === 0 ? "th" : "td"; html += "<tr>" + cells(r).map(c => `<${tag}>${inline(c)}</${tag}>`).join("") + "</tr>"; }); out.push(html + "</table>"); continue; }
    if (l.trim() === "") { i++; continue; }
    let p = []; while (i < lines.length && lines[i].trim() !== "" && !/^[#>|]|^\s*[-*]\s/.test(lines[i])) { p.push(inline(lines[i])); i++; }
    out.push(`<p>${p.join(" ")}</p>`);
  }
  return out.join("\n");
}

function setOffline(on) { $("offline").classList.toggle("show", on); }

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error("http " + r.status);
  return r.json();
}

// ---- ledger list
async function loadLedger() {
  try {
    const data = await api("/api/ledger");
    LS.set("ledger", data.answers);
    LS.set("stats", data.stats);
    setOffline(false);
    renderList(data.answers, data.stats);
  } catch {
    setOffline(true);
    const cached = LS.get("ledger", []);
    renderList(cached, LS.get("stats", {}));
  }
}

function renderList(answers, stats) {
  $("stat").textContent = stats && stats.passages
    ? `${stats.answered ?? answers.length} answers · ${stats.papers ?? "?"} papers · ${stats.passages} passages`
    : `${answers.length} cached answers`;
  $("list").innerHTML = answers.length
    ? answers.map(a => `<a href="#a/${encodeURIComponent(a.id)}"><div class="q">${esc(a.question)}</div>
        <div class="meta"><span class="pill ${cls(a.confidence)}">${esc(a.confidence || "—")}</span>
        ${Number(a.n_cited) || 0} sources</div></a>`).join("")
    : `<div class="hint">No worked answers yet.</div>`;
}

// ---- answer reader
async function openAnswer(id) {
  const cacheKey = "ans:" + id;
  let e = LS.get(cacheKey, null);
  $("result").className = "result show";
  $("result").innerHTML = `<span class="back" onclick="location.hash=''">← back</span><div class="spin">loading…</div>`;
  try {
    e = await api("/api/answers/" + id);
    LS.set(cacheKey, e);
  } catch { if (!e) { $("result").innerHTML = `<span class="back" onclick="location.hash=''">← back</span><p>Not available offline.</p>`; return; } }
  const g = (e.grounding || {});
  $("result").innerHTML =
    `<span class="back" onclick="location.hash=''">← back</span>
     <div><span class="pill ${cls(e.confidence)}">${esc(e.confidence || "—")}</span>
       <span class="meta" style="color:var(--dim);font-size:12px">${Number(g.n_cited) || 0} sources</span></div>
     <div class="md">${md(e.answer || "_no answer text_")}</div>`;
  window.scrollTo(0, 0);
}

// ---- ask
async function ask() {
  const q = $("q").value.trim();
  if (!q) return;
  $("result").className = "result show";
  $("result").innerHTML = `<div class="spin">thinking…</div>`;
  try {
    const r = await api("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q }) });
    if (r.status === "answered") {
      const e = r.answer; LS.set("ans:" + e.id, e);
      $("result").innerHTML =
        `<div><span class="pill ${cls(e.confidence)}">${esc(e.confidence || "—")}</span>
          <span class="meta" style="color:var(--dim);font-size:12px">matched a worked answer (${Number(r.similarity) || ""})</span></div>
         <div class="md">${md(e.answer)}</div>`;
    } else {
      const rel = (r.related || []).length
        ? `<div class="src" style="margin-top:0">Related worked answers</div>` +
          r.related.map(x => `<a href="#a/${encodeURIComponent(x.id)}" style="display:block;margin:6px 0;color:var(--text);text-decoration:none">
              <span class="pill ${cls(x.confidence)}">${esc(x.confidence || "—")}</span> ${esc(x.question)}
              <span style="color:var(--dim);font-size:12px">(${Number(x.similarity) || ""})</span></a>`).join("")
        : "";
      const ev = (r.evidence || []).map(p =>
        `<div class="src">[${esc(p.tier || "—")}] ${esc(p.title || p.slug)}</div><div class="snip">${esc(p.text)}…</div>`).join("");
      $("result").innerHTML =
        `<div><span class="pill queued">queued</span>
          <span class="meta" style="color:var(--dim);font-size:12px">${esc(r.message)}</span></div>
         ${rel ? `<div class="ev">${rel}</div>` : ""}
         <div class="ev"><div class="hint" style="margin:0 0 6px">Live evidence retrieved now — full synthesis runs at the next home deep-run:</div>${ev}</div>`;
    }
  } catch {
    $("result").innerHTML = `<span class="pill queued">offline</span><p>Can't reach your LocalEvidence server. Try a cached answer below, or ask again when you're home.</p>`;
  }
  window.scrollTo(0, 0);
}

// ---- routing + boot
function route() {
  const m = location.hash.match(/^#a\/(\d+)/);
  if (m) openAnswer(+m[1]);
  else $("result").className = "result";
}
window.addEventListener("hashchange", route);
$("ask").addEventListener("click", ask);
$("q").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask(); });
window.addEventListener("online", () => loadLedger());
window.addEventListener("offline", () => setOffline(true));

loadLedger().then(route);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
