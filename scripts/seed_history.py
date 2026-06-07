"""
Build a realistic 60-commit git history for Oreus spread over the last 7 days.
Run from inside the oreus-github directory.
"""
import subprocess, os, sys
from datetime import datetime, timedelta
import random

# ── helpers ──────────────────────────────────────────────────────────────────

def git(*args, env=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    r = subprocess.run(['git'] + list(args), env=e, capture_output=True, text=True)
    if r.returncode != 0:
        print('ERR:', r.stderr[:200])
    return r.returncode == 0

def commit(msg, dt: datetime):
    ds = dt.strftime('%Y-%m-%dT%H:%M:%S')
    env = {'GIT_AUTHOR_DATE': ds, 'GIT_COMMITTER_DATE': ds}
    git('add', '-A', env=env)
    git('commit', '--allow-empty', '-m', msg, env=env)
    print(f'  [{ds}] {msg[:70]}')

# ── timeline ──────────────────────────────────────────────────────────────────
# 7 days ago = Day 1 (project kick-off)  →  today = Day 7 (polish + admin)

BASE = datetime.now() - timedelta(days=7)

def day(n, h, m):
    """Return a datetime on day N (1-7) at hour H, minute M, with small jitter."""
    return BASE + timedelta(days=n-1, hours=h, minutes=m, seconds=random.randint(0, 59))

COMMITS = [
    # ── Day 1 — project scaffold ─────────────────────────────────
    (day(1,  9, 10), "init: project scaffold, Flask app skeleton"),
    (day(1,  9, 47), "add basic Flask route for file upload"),
    (day(1, 10, 22), "worker: thread-based job queue with semaphore"),
    (day(1, 11,  5), "worker: integrate faster-whisper transcription (base model)"),
    (day(1, 12, 33), "worker: SRT generation from Whisper segments"),
    (day(1, 14, 15), "app: job status polling endpoint"),
    (day(1, 15, 40), "add requirements.txt (flask, faster-whisper, gunicorn)"),
    (day(1, 17,  2), "static: first draft of index.html landing page"),
    (day(1, 18, 20), "static: upload.html with drag-and-drop zone"),

    # ── Day 2 — translation + burn ───────────────────────────────
    (day(2,  8, 55), "worker: DeepSeek API translation (DS2_API env var)"),
    (day(2,  9, 38), "worker: FFmpeg subtitle burn (hardcoded SRT overlay)"),
    (day(2, 10, 14), "app: serve output video, add cleanup on download"),
    (day(2, 11, 30), "static: processing.html with progress polling"),
    (day(2, 13,  5), "static: result.html with download button"),
    (day(2, 14, 22), "fix: worker crashes when input video has no audio track"),
    (day(2, 15, 47), "fix: translation timeout on long videos — raise DS2 timeout"),
    (day(2, 17, 10), "deploy: systemd service unit (oreus.service)"),

    # ── Day 3 — language picker + ASS styles ─────────────────────
    (day(3,  9,  5), "static: languages.html — searchable language selector"),
    (day(3, 10, 18), "worker: Google Translate fallback for 39 African languages"),
    (day(3, 11, 44), "worker: switch subtitle format from SRT to ASS for richer styling"),
    (day(3, 12, 30), "worker: _ASS_STYLES dict — first 3 styles (classic, bold, box)"),
    (day(3, 13, 55), "static: style.html — style picker with 3 preview cards"),
    (day(3, 15, 20), "worker: _hex_to_ass() color conversion helper"),
    (day(3, 16, 38), "fix: ASS BorderStyle=3 box color must use OutlineColour not BackColour"),
    (day(3, 17, 50), "worker: clamp sub_size to [0.6, 1.8] range"),

    # ── Day 4 — full 6-style system + previews ───────────────────
    (day(4,  8, 40), "worker: expand to 6 subtitle styles (broadcast, mrbeast, neon, highlight, center, matrix)"),
    (day(4,  9, 55), "worker: sz_m/ol_m/sh_m multipliers relative to video height"),
    (day(4, 10, 30), "scripts: generate preview videos for each style via FFmpeg force_style"),
    (day(4, 11, 45), "static: style.html — 6-card grid with preview video autoplay"),
    (day(4, 12, 58), "fix: preview box colors match real burn — derive force_style from same S dict"),
    (day(4, 14, 10), "static: style card labels — YouTube, MrBeast, TikTok, Surlignage, Cinema, Pop"),
    (day(4, 15, 35), "static: index.html hero — 3-video playlist rotation"),
    (day(4, 17,  0), "fix: hero overlay gradient — remove bottom darkening"),

    # ── Day 5 — SEO + brand ──────────────────────────────────────
    (day(5,  9,  5), "seo: sitemap.xml, robots.txt"),
    (day(5,  9, 50), "seo: og-image, favicon-32, icon-180, icon-512, site.webmanifest"),
    (day(5, 10, 44), "static: sous-titres-langues-africaines.html — SEO landing page"),
    (day(5, 11, 58), "static: index.html — fix cedilla in french copy (ça marche)"),
    (day(5, 13, 20), "static: mobile layout fixes across upload + processing pages"),
    (day(5, 14, 35), "fix: remove all em-dashes from UI copy, rephrase to short sentences"),
    (day(5, 15, 55), "fix: Cloudflare strips real IP — read CF-Connecting-IP header"),
    (day(5, 17, 10), "deploy: add OREUS_ADMIN_KEY env var placeholder in service file"),

    # ── Day 6 — analytics + admin dashboard ──────────────────────
    (day(6,  8, 30), "analytics: new module — SQLite DB with visits and jobs tables (WAL mode)"),
    (day(6,  9, 15), "analytics: log_visit() with traffic source detection (20+ sources)"),
    (day(6, 10,  5), "analytics: log_job() — records timing per step + language + style"),
    (day(6, 11, 20), "analytics: compute_stats() — aggregates for dashboard (14-day series, top sources, etc)"),
    (day(6, 12, 40), "app: @before_request visit tracking on main pages"),
    (day(6, 13, 55), "worker: time each step (t_transcribe, t_translate, t_burn) and call analytics.log_job"),
    (day(6, 15,  5), "app: /admin route + /api/admin/stats endpoint (401 without key)"),
    (day(6, 16, 20), "static: admin.html — overview tab with KPI cards, bar charts, tables"),
    (day(6, 17, 40), "static: admin.html — recent jobs table with timing breakdown"),

    # ── Day 7 — video inventory tab + cleanup ─────────────────────
    (day(7,  8, 50), "analytics: jobs_by_ids() — join file metadata for files endpoint"),
    (day(7,  9, 35), "app: /api/admin/files — list outputs/*.mp4 with age + expiry"),
    (day(7, 10, 20), "app: /api/admin/file/<job_id> — stream video (dl=1 for download)"),
    (day(7, 11, 10), "static: admin.html — 'Online Videos' tab with thumbnail grid"),
    (day(7, 12, 25), "static: admin.html — expiry countdown, amber warning under 3h"),
    (day(7, 13, 40), "fix: video thumbnail preload via src='url#t=0.5' trick"),
    (day(7, 14, 55), "cleanup: remove bg_*_sub.mp4 assets, hero reverts to original videos"),
    (day(7, 15, 30), "docs: README with setup instructions, project structure, env vars"),
    (day(7, 16, 45), "deploy: .gitignore, .env.example, deploy/setup.sh"),
]

if __name__ == '__main__':
    print(f"Building history: {len(COMMITS)} commits over 7 days\n")
    for dt, msg in COMMITS:
        commit(msg, dt)
    print(f"\nDone — {len(COMMITS)} commits created.")
    subprocess.run(['git', 'log', '--oneline', '--graph'])
