from flask import Flask, request, jsonify, send_file, send_from_directory, Response
from flask_cors import CORS
import os, uuid, threading, json, shutil, tempfile, time as _time
from pathlib import Path
from worker import process_video

import mimetypes
mimetypes.add_type("application/octet-stream", ".riv")
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
CORS(app)

import analytics
analytics.init_db()
import guard
ADMIN_KEY = os.environ.get('OREUS_ADMIN_KEY', 'oreus-admin-2026')
TRACKED_PATHS = {'/', '/upload', '/languages', '/style', '/processing', '/result', '/sous-titres-langues-africaines'}

def _client_ip():
    xff = request.headers.get('X-Forwarded-For', '')
    return (request.headers.get('CF-Connecting-IP')
            or (xff.split(',')[0].strip() if xff else '')
            or request.remote_addr or '')


def _safe_id(v):
    # Keep only filesystem-safe chars — blocks path traversal via client ids.
    return ''.join(ch for ch in str(v or '') if ch.isalnum() or ch in '-_')

@app.before_request
def _track_visit():
    if request.method == 'GET' and request.path in TRACKED_PATHS:
        analytics.log_visit(request.path, request.headers.get('Referer', ''),
                            _client_ip(), request.headers.get('User-Agent', ''),
                            request.headers.get('Accept-Language', '')[:8])


# Endpoints that create work (CPU + Lewis quota). Guarded against bots/flooding.
_GUARD_BOT  = {'/api/upload', '/api/upload/init', '/api/upload/finalize', '/api/process'}
_GUARD_RATE = {'/api/upload': 'upload', '/api/upload/init': 'upload', '/api/process': 'process'}

@app.before_request
def _guard_request():
    if request.method != 'POST':
        return
    path = request.path
    if path in _GUARD_BOT and guard.is_bot_ua(request.headers.get('User-Agent', '')):
        return jsonify({'error': 'Automated access is not allowed.'}), 403
    bucket = _GUARD_RATE.get(path)
    if bucket:
        ok, retry = guard.check_rate(_client_ip(), bucket)
        if not ok:
            resp = jsonify({'error': 'Limite atteinte : 3 videos par jour en version gratuite. Reviens demain.'})
            resp.status_code = 429
            resp.headers['Retry-After'] = str(retry)
            return resp

UPLOAD_DIR = Path('uploads')
OUTPUT_DIR = Path('outputs')
JOBS_DIR   = Path('jobs')
for d in (UPLOAD_DIR, OUTPUT_DIR, JOBS_DIR):
    d.mkdir(exist_ok=True)

jobs = {}
lock = threading.Lock()


def _save_job(job_id):
    try:
        with open(JOBS_DIR / f'{job_id}.json', 'w') as f:
            json.dump(jobs[job_id], f)
    except Exception:
        pass


def _load_jobs():
    for p in JOBS_DIR.glob('*.json'):
        try:
            with open(p) as f:
                j = json.load(f)
            if j.get('status') in ('done', 'error') or Path(j.get('filepath', '')).exists():
                jobs[p.stem] = j
        except Exception:
            pass


_load_jobs()


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/upload')
def page_upload():
    return send_from_directory('static', 'upload.html')


@app.route('/languages')
def page_languages():
    return send_from_directory('static', 'languages.html')


@app.route('/processing')
def page_processing():
    return send_from_directory('static', 'processing.html')


@app.route('/style')
def page_style():
    return send_from_directory('static', 'style.html')

@app.route('/robots.txt')
def robots_txt():
    return send_from_directory('static', 'robots.txt', mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap_xml():
    return send_from_directory('static', 'sitemap.xml', mimetype='application/xml')

@app.route('/og-image.png')
def og_image():
    return send_from_directory('static', 'og-image.png', mimetype='image/png')

@app.route('/site.webmanifest')
def webmanifest():
    return send_from_directory('static', 'site.webmanifest', mimetype='application/manifest+json')

@app.route('/favicon-32.png')
def favicon32():
    return send_from_directory('static', 'favicon-32.png', mimetype='image/png')

@app.route('/favicon.ico')
def favicon_ico():
    return send_from_directory('static', 'favicon-32.png', mimetype='image/png')

@app.route('/icon-180.png')
def icon180():
    return send_from_directory('static', 'icon-180.png', mimetype='image/png')

@app.route('/icon-512.png')
def icon512():
    return send_from_directory('static', 'icon-512.png', mimetype='image/png')

@app.route('/sous-titres-langues-africaines')
def page_africa():
    return send_from_directory('static', 'sous-titres-langues-africaines.html')

@app.route('/result')
def page_result():
    return send_from_directory('static', 'result.html')


@app.route('/admin')
def page_admin():
    return send_from_directory('static', 'admin.html')

@app.route('/api/admin/stats')
def admin_stats():
    if request.args.get('key') != ADMIN_KEY:
        return jsonify({'error': 'unauthorized'}), 401
    return jsonify(analytics.compute_stats())

@app.route('/api/admin/files')
def admin_files():
    if request.args.get('key') != ADMIN_KEY:
        return jsonify({'error': 'unauthorized'}), 401
    now = _time.time()
    items = []
    for p in OUTPUT_DIR.glob('*_output.mp4'):
        jid = p.name[:-len('_output.mp4')]
        st = p.stat()
        age = now - st.st_mtime
        items.append({'job_id': jid, 'size_mb': round(st.st_size / (1024 * 1024), 2),
                      'created': st.st_mtime, 'age': age, 'expires_in': max(0, 86400 - age)})
    info = analytics.jobs_by_ids([i['job_id'] for i in items])
    for i in items:
        m = info.get(i['job_id'], {})
        i['filename'] = m.get('filename', '')
        i['src_lang'] = m.get('src_lang', '')
        i['tgt_lang'] = m.get('tgt_lang', '')
        i['sub_style'] = m.get('sub_style', '')
    items.sort(key=lambda x: -x['created'])
    return jsonify({'files': items, 'count': len(items)})

@app.route('/api/admin/file/<job_id>')
def admin_file(job_id):
    if request.args.get('key') != ADMIN_KEY:
        return jsonify({'error': 'unauthorized'}), 401
    safe = ''.join(ch for ch in job_id if ch.isalnum() or ch in '-_')
    path = OUTPUT_DIR / f'{safe}_output.mp4'
    if not path.exists():
        return jsonify({'error': 'not found'}), 404
    as_dl = bool(request.args.get('dl'))
    return send_file(str(path), mimetype='video/mp4', as_attachment=as_dl,
                     download_name=f'oreus_{safe}.mp4')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


@app.route('/api/upload', methods=['POST'])
def upload():
    f = request.files.get('video')
    if f is None and request.files:
        f = next(iter(request.files.values()))
    if f is None:
        return jsonify({'error': 'Aucun fichier reçu'}), 400
    job_id = str(uuid.uuid4())
    ext = Path(f.filename).suffix.lower() or '.mp4'
    path = UPLOAD_DIR / f'{job_id}{ext}'
    with open(str(path), 'wb') as out:
        shutil.copyfileobj(f.stream, out, length=1 << 20)
    with lock:
        jobs[job_id] = _new_job(f.filename, str(path), _client_ip())
        _save_job(job_id)
    return jsonify({'job_id': job_id})


@app.route('/api/process', methods=['POST'])
def process():
    data = request.get_json() or {}
    job_id = data.get('job_id')
    _free_disk_if_low()   # réagit vite à un afflux (no-op si le disque va bien)
    with lock:
        if job_id not in jobs:
            return jsonify({'error': 'Job not found'}), 404
        if jobs[job_id]['status'] not in ('uploaded',):
            return jsonify({'error': 'Already processing'}), 400
        if guard.count_active_global(jobs) >= guard.GLOBAL_ACTIVE_MAX:
            return jsonify({'error': 'Serveur occupe, reessaie dans une minute.'}), 503
        if guard.count_active_for_ip(jobs, jobs[job_id].get('ip', '')) >= guard.PER_IP_ACTIVE_MAX:
            return jsonify({'error': 'Tu as deja des videos en cours. Attends la fin.'}), 429
        jobs[job_id]['src_lang'] = data.get('src_lang', 'auto')
        jobs[job_id]['tgt_lang'] = data.get('tgt_lang', 'en')
        jobs[job_id]['sub_style'] = data.get('sub_style', 'mrbeast')
        jobs[job_id]['sub_lang']  = data.get('sub_lang', '')
        jobs[job_id]['sub_size']  = data.get('sub_size', 'medium')
        jobs[job_id]['sub_color'] = data.get('sub_color', '')
        jobs[job_id]['enhance']   = bool(data.get('enhance'))
        jobs[job_id]['mode']      = 'enhance' if data.get('mode') == 'enhance' else 'subtitle'
        _save_job(job_id)
    t = threading.Thread(target=process_video, args=(job_id, jobs, lock, OUTPUT_DIR), daemon=True)
    t.start()
    return jsonify({'job_id': job_id, 'status': 'queued'})


@app.route('/api/status/<job_id>')
def status(job_id):
    with lock:
        if job_id not in jobs:
            return jsonify({'error': 'Not found'}), 404
        j = dict(jobs[job_id])
    return jsonify({
        'status':    j['status'],
        'progress':  j['progress'],
        'step':      j['step'],
        'queue_pos': j.get('queue_pos', 0),
        'error':     j.get('error'),
    })


@app.route('/api/video/<job_id>')
def video_stream(job_id):
    with lock:
        if job_id not in jobs:
            return jsonify({'error': 'Not found'}), 404
        j = dict(jobs[job_id])
    if j['status'] != 'done' or not j['output']:
        return jsonify({'error': 'Not ready'}), 400
    path = os.path.abspath(j['output'])
    if not os.path.exists(path):
        return jsonify({'error': 'File missing'}), 404
    file_size = os.path.getsize(path)
    range_header = request.headers.get('Range')
    try:
        parts = range_header[6:].split('-') if (range_header and range_header.startswith('bytes=')) else None
        byte_start = int(parts[0]) if parts else 0
        byte_end = (int(parts[1]) if parts[1] else file_size - 1) if parts else file_size - 1
    except Exception:
        byte_start, byte_end = 0, file_size - 1
    byte_end = min(byte_end, file_size - 1)
    chunk_size = byte_end - byte_start + 1
    is_partial = range_header is not None
    def _stream(p, s, n):
        with open(p, 'rb') as _f:
            _f.seek(s)
            rem = n
            while rem > 0:
                data = _f.read(min(65536, rem))
                if not data:
                    break
                rem -= len(data)
                yield data
    hdrs = {
        'Content-Type': 'video/mp4',
        'Content-Length': str(chunk_size),
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'no-store, no-transform',
        'Content-Encoding': 'identity',
    }
    if is_partial:
        hdrs['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
    return Response(_stream(path, byte_start, chunk_size), 206 if is_partial else 200, hdrs)


@app.route('/api/download/<job_id>')
def download(job_id):
    with lock:
        if job_id not in jobs:
            return jsonify({'error': 'Not found'}), 404
        j = dict(jobs[job_id])
    if j['status'] != 'done' or not j['output']:
        return jsonify({'error': 'Not ready'}), 400
    # Marquer comme telecharge : ces videos sont nettoyees en priorite si le disque sature.
    with lock:
        if job_id in jobs:
            jobs[job_id]['downloaded'] = True
            _save_job(job_id)
    name = f"oreus_{Path(j['filename']).stem}_subtitled.mp4"
    return send_file(j['output'], as_attachment=True, download_name=name, mimetype='video/mp4')


# ── Chunked upload ─────────────────────────────────────────────────────────────
# Chemin relatif au répertoire de travail (portable : serveur, Docker/HF, etc.).
CHUNKS_BASE = Path('chunks')
CHUNKS_BASE.mkdir(parents=True, exist_ok=True)
# Nettoyer les sessions de chunks abandonnées (> 2h)
def _cleanup_old_chunks():
    import time as _t
    cutoff = _t.time() - 7200
    try:
        for d in CHUNKS_BASE.iterdir():
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(str(d), ignore_errors=True)
    except Exception:
        pass
threading.Thread(target=_cleanup_old_chunks, daemon=True).start()


@app.route('/api/upload/init', methods=['POST'])
def upload_init():
    data = request.get_json() or {}
    upload_id = str(uuid.uuid4())
    chunk_dir = CHUNKS_BASE / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    with open(chunk_dir / '_meta.json', 'w') as mf:
        json.dump({
            'filename':     data.get('filename', 'video.mp4'),
            'total_size':   data.get('total_size', 0),
            'total_chunks': data.get('total_chunks', 1),
        }, mf)
    return jsonify({'upload_id': upload_id})


@app.route('/api/upload/chunk', methods=['POST'])
def upload_chunk_part():
    upload_id  = request.form.get('upload_id')
    ci_raw     = request.form.get('chunk_index')
    chunk_file = request.files.get('chunk')
    try:
        chunk_index = int(ci_raw) if ci_raw is not None else None
    except (ValueError, TypeError):
        chunk_index = None
    upload_id = _safe_id(upload_id)
    if not upload_id or chunk_index is None or not chunk_file:
        return jsonify({'error': 'Paramètres manquants'}), 400
    chunk_dir = CHUNKS_BASE / upload_id
    if not chunk_dir.exists():
        return jsonify({'error': 'upload_id invalide'}), 400
    chunk_file.save(str(chunk_dir / f'chunk_{chunk_index:06d}'))
    return jsonify({'received': True, 'chunk_index': chunk_index})


@app.route('/api/upload/finalize', methods=['POST'])
def upload_finalize():
    data         = request.get_json() or {}
    upload_id    = data.get('upload_id')
    filename     = data.get('filename', 'video.mp4')
    total_chunks = data.get('total_chunks', 1)
    upload_id = _safe_id(upload_id)
    chunk_dir = CHUNKS_BASE / upload_id
    if not upload_id or not chunk_dir.exists():
        return jsonify({'error': 'upload_id invalide'}), 400
    job_id = str(uuid.uuid4())
    ext    = Path(filename).suffix.lower() or '.mp4'
    dest   = UPLOAD_DIR / f'{job_id}{ext}'
    try:
        with open(str(dest), 'wb') as out:
            for i in range(total_chunks):
                cp = chunk_dir / f'chunk_{i:06d}'
                if not cp.exists():
                    return jsonify({'error': f'Chunk {i} manquant'}), 400
                with open(str(cp), 'rb') as ch:
                    shutil.copyfileobj(ch, out, length=1 << 20)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        shutil.rmtree(str(chunk_dir), ignore_errors=True)
    with lock:
        jobs[job_id] = _new_job(filename, str(dest), _client_ip())
        _save_job(job_id)
    return jsonify({'job_id': job_id})


def _new_job(filename, filepath, ip=''):
    return {
        'status': 'uploaded', 'progress': 0, 'step': 0, 'queue_pos': 0,
        'filename': filename, 'filepath': filepath,
        'src_lang': None, 'tgt_lang': None, 'sub_lang': '', 'output': None, 'error': None,
        'ip': ip, 'size_mb': round((os.path.getsize(filepath) / (1024 * 1024)) if os.path.exists(filepath) else 0, 2),
    }


# ── Nettoyage piloté par l'espace disque (filet de sécurité) ───────────────────
# Quand le disque devient bas, on supprime tout de suite les vidéos finies —
# en priorité celles déjà téléchargées — sans attendre le nettoyage 24 h.
def _disk_free_gb():
    try:
        return shutil.disk_usage('/').free / (1024 ** 3)
    except Exception:
        return 999.0


def _free_disk_if_low():
    try:
        min_free = float(os.environ.get('OREUS_DISK_MIN_FREE_GB', 2.5))
        target   = float(os.environ.get('OREUS_DISK_TARGET_FREE_GB', 4.5))
    except (TypeError, ValueError):
        min_free, target = 2.5, 4.5
    if _disk_free_gb() >= min_free:
        return

    print(f'[disk] espace bas ({_disk_free_gb():.1f} GB libres), nettoyage...', flush=True)
    # Candidats = jobs finis dont l'output existe, triés par priorité de suppression :
    # téléchargés d'abord (clé 0), puis les plus anciens d'abord.
    with lock:
        candidates = []
        for jid, j in jobs.items():
            if j.get('status') not in ('done', 'error'):
                continue
            out = j.get('output')
            if not out or not os.path.exists(out):
                continue
            try:
                mtime = os.path.getmtime(out)
            except OSError:
                mtime = 0
            candidates.append((0 if j.get('downloaded') else 1, mtime, jid, out))
        candidates.sort()

    for prio, _, jid, out in candidates:
        if _disk_free_gb() >= target:
            break
        try:
            os.remove(out)
        except OSError:
            pass
        with lock:
            jobs.pop(jid, None)
        (JOBS_DIR / f'{jid}.json').unlink(missing_ok=True)
        print(f'[disk] supprime {jid} (telecharge={prio == 0})', flush=True)


def _disk_loop():
    while True:
        _time.sleep(120)
        try:
            _free_disk_if_low()
        except Exception as ex:
            print(f'[disk] {ex}', flush=True)


threading.Thread(target=_disk_loop, daemon=True).start()


# ── Nettoyage automatique toutes les heures ────────────────────────────────────
def _cleanup_loop():
    while True:
        _time.sleep(3600)
        now = _time.time()
        try:
            guard.prune()
            for p in list(UPLOAD_DIR.glob('*')) + list(OUTPUT_DIR.glob('*')):
                if now - p.stat().st_mtime > 86400:
                    p.unlink(missing_ok=True)
            with lock:
                dead = [jid for jid, j in jobs.items()
                        if j['status'] not in ('processing', 'queued')
                        and not Path(j.get('output') or j.get('filepath', '')).exists()]
                for jid in dead:
                    jobs.pop(jid, None)
                    (JOBS_DIR / f'{jid}.json').unlink(missing_ok=True)
        except Exception as ex:
            print(f'[cleanup] {ex}')


threading.Thread(target=_cleanup_loop, daemon=True).start()


@app.route('/api/rive-inspect', methods=['POST'])
def rive_inspect():
    data = request.get_json() or {}
    import json as _json
    print('[rive-inspect]', _json.dumps(data, ensure_ascii=False), flush=True)
    return jsonify({'ok': True})



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
