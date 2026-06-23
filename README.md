---
title: Oreus
emoji: 🎬
colorFrom: orange
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

<p align="center">
  <img src="static/logo-master.png" alt="Oreus" width="220" />
</p>

# Oreus — AI Video Subtitle Generator

Oreus is a web application that automatically transcribes and translates video subtitles using AI. Upload a video, choose a target language and a subtitle style, and get a professionally subtitled video back — in minutes.

**Live:** [oreus.shadrakbessanh.me](https://oreus.shadrakbessanh.me)

---

## Features

- Transcription via [faster-whisper](https://github.com/guillaumeklebs/faster-whisper) (Whisper `base` model)
- Translation to 100+ languages including 39 African languages (Google Translate fallback for low-resource languages, DeepSeek API for the rest)
- 6 subtitle styles inspired by real web creators: YouTube, MrBeast, TikTok, Surlignage, Cinema, Pop
- Subtitle burned directly into the video with FFmpeg (ASS format, `BorderStyle=3` for box styles)
- Admin dashboard at `/admin` — traffic sources, job timings, language usage, live video inventory
- SQLite analytics (zero external dependency)
- Cloudflare Tunnel for HTTPS + DDoS protection

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask, Gunicorn |
| Transcription | faster-whisper (CUDA or CPU) |
| Translation | DeepSeek API + Google Translate |
| Subtitle burn | FFmpeg + libass (ASS format) |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| Analytics | SQLite (WAL mode) |
| Hosting | Azure VM + Cloudflare Named Tunnel |
| Process manager | systemd |

## Project Structure

```
oreus/
├── app.py              # Flask app — routes, job queue, file serving
├── worker.py           # Background worker — transcription, translation, burn
├── analytics.py        # SQLite analytics module (visits + jobs)
├── requirements.txt
│
├── static/
│   ├── index.html                          # Landing page
│   ├── upload.html                         # Upload flow
│   ├── languages.html                      # Language picker
│   ├── style.html                          # Subtitle style picker (6 styles + previews)
│   ├── processing.html                     # Real-time progress page
│   ├── result.html                         # Download result page
│   ├── admin.html                          # Admin dashboard (password-protected)
│   └── sous-titres-langues-africaines.html # SEO landing page
│
└── deploy/
    ├── oreus.service   # systemd unit file
    └── setup.sh        # Initial server setup script
```

## Setup

### Prerequisites

- Python 3.11+
- FFmpeg with libass (`sudo apt install ffmpeg`)
- A DeepSeek API key (for translation)
- Arial fonts (`arial.ttf`, `arialbd.ttf`) placed in `fonts/`

### Install

```bash
git clone https://github.com/yourusername/oreus.git
cd oreus
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env with your DeepSeek API key and admin password
```

### Run (development)

```bash
export DS2_API=your_key
export OREUS_ADMIN_KEY=your_admin_password
flask --app app run --debug
```

### Deploy (production)

```bash
bash deploy/setup.sh
# Then set secrets in /etc/systemd/system/oreus.service
sudo systemctl start oreus.service
```

## Subtitle Styles

| Key | Style | Description |
|---|---|---|
| `broadcast` | YouTube | White text on translucent black box |
| `mrbeast` | MrBeast | Bold yellow, thick black outline + shadow |
| `neon` | TikTok | Bold white, black outline + shadow |
| `highlight` | Surlignage | Black text on yellow box |
| `center` | Cinema | White, thin outline + soft shadow |
| `matrix` | Pop | Bold pink/rose, black outline |

Styles are defined once in `worker.py` (`_ASS_STYLES`) and preview videos are generated from the same values using FFmpeg `force_style`.

## Admin Dashboard

Visit `/admin` and enter your admin password (set via `OREUS_ADMIN_KEY` env var, default `oreus-admin-2026`).

- **Overview tab:** 14-day traffic charts, traffic sources, page views, job timings (transcription / translation / burn), language usage, subtitle style usage, recent jobs and visits tables
- **Online Videos tab:** Grid of videos currently available for download (not yet deleted by the 24h cleanup), with thumbnails, metadata, expiry countdown, and direct view/download links

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DS2_API` | — | DeepSeek API key (required for translation) |
| `OREUS_ADMIN_KEY` | `oreus-admin-2026` | Admin dashboard password |

## Notes

- The 24-hour cleanup is not a cron job — it runs lazily when a user visits `/result`. Old files in `outputs/` are deleted when they are accessed and found to be expired.
- Subtitle box color in ASS `BorderStyle=3` comes from `OutlineColour`, not `BackColour` (libass behavior).
- Do not install the `brotli` pip package on the server — it corrupts the video stream response.
- Cloudflare blocks the default Python `urllib` User-Agent; use `User-Agent: Mozilla/5.0` for any outbound HTTP requests.

## License

MIT
