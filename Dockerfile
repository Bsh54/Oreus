# Oreus — image pour Hugging Face Spaces (SDK: docker) ou tout hôte Docker.
FROM python:3.11-slim

# ffmpeg (extraction/débruitage/incrustation) + polices (le burn ASS utilise
# "Arial" → fontconfig de Debian l'alias automatiquement vers Liberation Sans).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-liberation fontconfig \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces exécute le conteneur en utilisateur non-root (uid 1000).
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /home/user/app

COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user:user . .

# HF Spaces attend le service sur le port 7860 (cf. app_port dans le README).
EXPOSE 7860

CMD ["gunicorn", "--workers", "1", "--threads", "8", \
     "--bind", "0.0.0.0:7860", "--timeout", "600", \
     "--access-logfile", "-", "app:app"]
