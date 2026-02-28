"""
server.py
---------
Flask web server that exposes the CVS coupon strategy pipeline via a
mobile-optimised web UI.

Open the URL on your iPhone, enter your CVS credentials, and tap a button.
The pipeline runs on the server; the phone polls for progress and then
loads the finished HTML report.

Routes:
    GET  /        → Control panel (mobile UI)
    POST /run     → Start pipeline; body: {email, password, deals_only}
    GET  /status  → Poll for progress; returns JSON
    GET  /report  → Serve completed HTML report

Usage (local, same Wi-Fi as iPhone):
    python server.py
    # then open http://<your-mac-ip>:5000 on iPhone

Usage (production via gunicorn):
    gunicorn server:app --workers 1 --threads 4 --timeout 300 --bind 0.0.0.0:$PORT
"""

import logging
import os
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file

import coupon_clipper
import weekly_specials
import strategy as strategy_module
import report as report_module

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
REPORT_PATH = Path(__file__).parent / "cvs_coupon_report.html"

# ---------------------------------------------------------------------------
# Shared job state (single-worker; protected by a lock)
# ---------------------------------------------------------------------------

_job: dict = {
    "state": "idle",        # idle | running | done | error
    "message": "",
    "progress_pct": 0,
    "error": None,
}
_job_lock = threading.Lock()


def _update_job(**kwargs) -> None:
    with _job_lock:
        _job.update(kwargs)


def _job_snapshot() -> dict:
    with _job_lock:
        return dict(_job)


# ---------------------------------------------------------------------------
# Background pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(email: str, password: str, deals_only: bool) -> None:
    """Execute the full coupon pipeline in a background thread."""
    coupons: list[dict] = []

    try:
        # Step 1 — clip coupons
        if not deals_only:
            _update_job(state="running", message="Logging in and clipping coupons…", progress_pct=10)
            logger.info("Pipeline: clipping coupons")
            coupons = coupon_clipper.clip_all_coupons(
                email=email,
                password=password,
                headless=True,
            )
            for c in coupons:
                c.pop("_clip_button", None)
            logger.info("Pipeline: %d coupons clipped", len(coupons))
        else:
            _update_job(state="running", message="Skipping coupon clipping (deals-only mode)…", progress_pct=10)

        # Step 2 — weekly specials
        _update_job(message="Fetching weekly specials…", progress_pct=40)
        logger.info("Pipeline: fetching weekly specials")
        deals = weekly_specials.fetch_weekly_specials(headless=True)
        logger.info("Pipeline: %d deals found", len(deals))

        # Step 3 — build strategy
        _update_job(message="Building savings strategy…", progress_pct=75)
        logger.info("Pipeline: building strategy")
        items, summary = strategy_module.build_strategy(coupons, deals)

        # Step 4 — generate report
        _update_job(message="Generating report…", progress_pct=90)
        logger.info("Pipeline: generating HTML report")
        report_module.generate_html_report(
            strategy_items=items,
            summary=summary,
            output_path=str(REPORT_PATH),
        )

        _update_job(
            state="done",
            message=(
                f"Done! {summary['items_with_both']} items have both a sale and a coupon. "
                f"Estimated savings: ${summary['estimated_total_savings']:.2f}"
            ),
            progress_pct=100,
        )
        logger.info("Pipeline: complete")

    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed")
        _update_job(state="error", message="An error occurred — see server logs.", error=str(exc))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def index() -> Response:
    """Mobile-optimised control panel."""
    return Response(_CONTROL_PANEL_HTML, mimetype="text/html")


@app.post("/run")
def run() -> Response:
    """Start the pipeline. Expects JSON body."""
    snapshot = _job_snapshot()
    if snapshot["state"] == "running":
        return jsonify({"error": "A job is already running."}), 409

    data = request.get_json(silent=True) or {}
    deals_only: bool = bool(data.get("deals_only", False))
    email: str = (data.get("email") or "").strip()
    password: str = (data.get("password") or "").strip()

    if not deals_only and (not email or not password):
        return jsonify({"error": "Email and password are required for full run."}), 400

    # Reset state
    _update_job(state="running", message="Starting…", progress_pct=0, error=None)

    # Launch pipeline in background (credentials stay in-memory, never logged)
    t = threading.Thread(
        target=_run_pipeline,
        args=(email, password, deals_only),
        daemon=True,
    )
    t.start()

    return jsonify({"ok": True})


@app.get("/status")
def status() -> Response:
    """Return current job state for polling."""
    return jsonify(_job_snapshot())


@app.get("/report")
def serve_report() -> Response:
    """Serve the generated HTML report file."""
    if not REPORT_PATH.exists():
        return Response("Report not yet generated.", status=404, mimetype="text/plain")
    return send_file(str(REPORT_PATH), mimetype="text/html")


# ---------------------------------------------------------------------------
# Embedded mobile UI
# ---------------------------------------------------------------------------

_CONTROL_PANEL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="CVS Deals">
<title>CVS Coupon Strategy</title>
<style>
  :root {
    --red:    #cc0000;
    --dark:   #1a1a2e;
    --mid:    #2d2d44;
    --card:   #252540;
    --border: #3d3d5c;
    --green:  #00b894;
    --yellow: #fdcb6e;
    --accent: #e94560;
    --text:   #f0f0f0;
    --muted:  #a0a0b0;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--dark);
    color: var(--text);
    min-height: 100dvh;
    padding-bottom: env(safe-area-inset-bottom, 16px);
  }

  /* Header */
  header {
    background: var(--red);
    padding: 18px 20px 14px;
    padding-top: calc(18px + env(safe-area-inset-top, 0px));
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  header h1 { font-size: 1.2rem; font-weight: 700; letter-spacing: 0.5px; }
  .cvs-badge {
    background: #fff;
    color: var(--red);
    font-weight: 900;
    font-size: 0.85rem;
    padding: 3px 8px;
    border-radius: 4px;
    letter-spacing: 1px;
  }

  /* Main content */
  main { padding: 20px 16px; max-width: 480px; margin: 0 auto; }

  /* Status card */
  .status-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 20px;
  }
  .status-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }
  .status-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--muted);
    flex-shrink: 0;
    transition: background 0.3s;
  }
  .status-dot.running { background: var(--yellow); animation: pulse 1.2s infinite; }
  .status-dot.done    { background: var(--green); }
  .status-dot.error   { background: var(--accent); }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.35; }
  }
  .status-text { font-size: 0.9rem; color: var(--muted); flex: 1; }
  .progress-bar-wrap {
    background: var(--border);
    border-radius: 99px;
    height: 6px;
    overflow: hidden;
  }
  .progress-bar {
    height: 100%;
    background: var(--green);
    border-radius: 99px;
    width: 0%;
    transition: width 0.5s ease;
  }

  /* Form */
  .form-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
  }
  .form-card label {
    display: block;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--muted);
    margin-bottom: 6px;
  }
  .form-card input {
    width: 100%;
    background: var(--mid);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-size: 16px; /* prevent iOS auto-zoom */
    padding: 11px 12px;
    margin-bottom: 14px;
    outline: none;
  }
  .form-card input:focus { border-color: var(--green); }
  .form-card input:last-of-type { margin-bottom: 0; }

  /* Buttons */
  .btn {
    display: block;
    width: 100%;
    padding: 14px 12px;
    border: none;
    border-radius: 10px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    margin-bottom: 10px;
    transition: opacity 0.2s, transform 0.1s;
    -webkit-tap-highlight-color: transparent;
  }
  .btn:active { transform: scale(0.97); opacity: 0.85; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
  .btn-green  { background: var(--green);  color: #0d2b24; }
  .btn-yellow { background: var(--yellow); color: #2b2000; }
  .btn-report {
    background: var(--mid);
    border: 1px solid var(--green);
    color: var(--green);
    display: none;
    text-decoration: none;
    line-height: 1;
  }

  .note {
    font-size: 0.75rem;
    color: var(--muted);
    text-align: center;
    margin-top: 8px;
    line-height: 1.4;
  }
  .error-msg {
    background: rgba(233,69,96,0.12);
    border: 1px solid var(--accent);
    color: var(--accent);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 0.85rem;
    margin-top: 12px;
    display: none;
  }
</style>
</head>
<body>

<header>
  <h1>CVS Coupon Strategy</h1>
  <span class="cvs-badge">CVS</span>
</header>

<main>

  <!-- Status card -->
  <div class="status-card">
    <div class="status-header">
      <div class="status-dot" id="dot"></div>
      <div class="status-text" id="statusText">Ready to run</div>
    </div>
    <div class="progress-bar-wrap">
      <div class="progress-bar" id="progressBar"></div>
    </div>
  </div>

  <!-- Credentials form (hidden in deals-only mode) -->
  <div class="form-card" id="credsForm">
    <label for="emailInput">CVS Account Email</label>
    <input type="email" id="emailInput" autocomplete="email" placeholder="you@example.com">
    <label for="passInput">Password</label>
    <input type="password" id="passInput" autocomplete="current-password" placeholder="••••••••">
  </div>

  <!-- Action buttons -->
  <button class="btn btn-green"  id="btnFull"   onclick="startRun(false)">Clip All &amp; Analyze</button>
  <button class="btn btn-yellow" id="btnDeals"  onclick="startRun(true)">Weekly Deals Only</button>
  <a     class="btn btn-report"  id="btnReport" href="/report" target="_blank">View Report →</a>

  <p class="note">Credentials are sent over HTTPS and never stored on the server.</p>
  <div class="error-msg" id="errorMsg"></div>

</main>

<script>
let pollTimer = null;

async function startRun(dealsOnly) {
  const email    = document.getElementById('emailInput').value.trim();
  const password = document.getElementById('passInput').value;
  hideError();

  if (!dealsOnly && (!email || !password)) {
    showError('Please enter your CVS email and password, or use "Weekly Deals Only".');
    return;
  }

  setButtons(true);
  setStatus('running', 'Starting…', 0);

  try {
    const res = await fetch('/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email, password, deals_only: dealsOnly}),
    });
    const data = await res.json();
    if (!res.ok) {
      showError(data.error || 'Failed to start job.');
      setButtons(false);
      return;
    }
  } catch (e) {
    showError('Could not reach the server. Is it running?');
    setButtons(false);
    return;
  }

  // Start polling
  pollTimer = setInterval(poll, 2000);
}

async function poll() {
  try {
    const res  = await fetch('/status');
    const data = await res.json();
    setStatus(data.state, data.message, data.progress_pct);

    if (data.state === 'done') {
      clearInterval(pollTimer);
      setButtons(false);
      document.getElementById('btnReport').style.display = 'block';
    } else if (data.state === 'error') {
      clearInterval(pollTimer);
      setButtons(false);
      showError(data.error || 'An error occurred on the server.');
    }
  } catch (e) {
    // Network blip — keep polling
  }
}

function setStatus(state, message, pct) {
  const dot  = document.getElementById('dot');
  const text = document.getElementById('statusText');
  const bar  = document.getElementById('progressBar');

  dot.className = 'status-dot ' + (state || '');
  text.textContent = message || 'Ready to run';
  bar.style.width  = (pct || 0) + '%';
}

function setButtons(running) {
  document.getElementById('btnFull').disabled  = running;
  document.getElementById('btnDeals').disabled = running;
}

function showError(msg) {
  const el = document.getElementById('errorMsg');
  el.textContent = msg;
  el.style.display = 'block';
}

function hideError() {
  document.getElementById('errorMsg').style.display = 'none';
}

// On load, check if a job is already in progress (e.g. page refresh)
(async () => {
  try {
    const res  = await fetch('/status');
    const data = await res.json();
    if (data.state === 'running') {
      setButtons(true);
      setStatus(data.state, data.message, data.progress_pct);
      pollTimer = setInterval(poll, 2000);
    } else if (data.state === 'done') {
      setStatus(data.state, data.message, 100);
      document.getElementById('btnReport').style.display = 'block';
    }
  } catch (e) { /* ignore */ }
})();
</script>

</body>
</html>
"""

# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    logger.info("Starting CVS coupon server on http://%s:%d", host, port)
    app.run(host=host, port=port, debug=False, threaded=True)
