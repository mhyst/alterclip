#!/usr/bin/env python
import json
import uuid
import time
import sqlite3
from pathlib import Path
import subprocess
import re

# Rutas
ALTERCLIP_DB = Path.home() / ".local/state/alterclip/log/streaming_history.db"
FREETUBE_PLAYLIST = Path.home() / ".config/FreeTube/playlists.db"
BACKUP_FILE = FREETUBE_PLAYLIST.with_suffix(".db.bak")

def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    return match.group(1) if match else None

def fetch_metadata(video_id):
    try:
        result = subprocess.run(
            ["yt-dlp", f"https://www.youtube.com/watch?v={video_id}", "--dump-json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10
        )
        data = json.loads(result.stdout)
        return {
            "videoId": video_id,
            "title": data.get("title", ""),
            "author": data.get("channel", data.get("uploader", "")),
            "authorId": data.get("channel_id", ""),
            "lengthSeconds": data.get("duration", 0),
            "published": int(data.get("timestamp", time.time()) * 1000),
            "timeAdded": int(time.time() * 1000),
            "playlistItemId": str(uuid.uuid4()),
            "type": "video"
        }
    except Exception as e:
        print(f"Error obteniendo metadatos de {video_id}: {e}")
        return None

def cargar_urls_alterclip():
    conn = sqlite3.connect(ALTERCLIP_DB)
    cur = conn.cursor()
    cur.execute("SELECT url FROM streaming_history WHERE platform = 'YouTube' AND visto = 0")
    urls = [row[0] for row in cur.fetchall()]
    conn.close()
    return urls

# Paso 1: cargar todas las entradas del archivo playlists.json
lines = FREETUBE_PLAYLIST.read_text(encoding="utf-8").splitlines()
entries = [json.loads(line) for line in lines]

# Paso 2: localizar la última versión de la playlist 'Watch Later'
watch_later_entries = [e for e in entries if e.get("playlistName") == "Watch Later"]
if not watch_later_entries:
    print("No se encontró la playlist 'Watch Later'")
    exit(1)

last_entry = watch_later_entries[-1]
video_ids_existentes = {v["videoId"] for v in last_entry.get("videos", [])}
nuevos_videos = []

# Paso 3: cargar URLs desde la base de datos de Alterclip
urls = cargar_urls_alterclip()
print(f"Obtenidas {len(urls)} URLs desde Alterclip.")

for url in urls:
    vid = extract_video_id(url)
    if not vid or vid in video_ids_existentes:
        continue
    info = fetch_metadata(vid)
    if info:
        nuevos_videos.append(info)

if not nuevos_videos:
    print("No hay vídeos nuevos para añadir.")
    exit(0)

# Paso 4: generar nueva entrada
updated_entry = dict(last_entry)
updated_entry["videos"] = last_entry.get("videos", []) + nuevos_videos
updated_entry["lastUpdatedAt"] = int(time.time() * 1000)

# Copia de seguridad
BACKUP_FILE.write_text(FREETUBE_PLAYLIST.read_text(encoding="utf-8"), encoding="utf-8")

# Escribir nueva línea
with open(FREETUBE_PLAYLIST, "a", encoding="utf-8") as f:
    f.write(json.dumps(updated_entry, ensure_ascii=False) + "\n")

print(f"{len(nuevos_videos)} vídeos añadidos a la playlist 'Watch Later'.")

