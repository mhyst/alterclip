#!/usr/bin/env python3
#
# This file is part of alterclip

# Alterclip is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.

# Alterclip is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.

# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>. 
#

import pyperclip
import time
import re
import instaloader
import threading
import os
import platform
import subprocess
import tempfile 
import logging
import builtins
import pathlib
import signal
from platformdirs import user_log_dir
from pathlib import Path

# Modificar para indicar tu reproductor favorito
REPRODUCTOR_VIDEO="mpv"

# Modos de funcionamiento por señales
MODO_STREAMING=0        # Reproduce vídeos de youtube y descarga y abre contenido de
                        # Instagram
MODO_OFFLINE=1          # No intenta reproducir ni descargar
modo=MODO_STREAMING

#Intercepta señal USR1 y activa modo streaming
def handler_streaming(signum, frame):
    global modo
    modo = MODO_STREAMING
    logging.info("¡Señal STREAMING recibida! Cambiando a modo STREAMING.")

#Intercepta señal USR2 y activa modo offline
def handler_offline(signum, frame):
    global modo
    modo = MODO_OFFLINE
    logging.info("¡Señal OFFLINE recibida! Volviendo al modo OFFLINE.")


# Abre archivos en el sistema
def abrir_archivo(ruta):
    sistema = platform.system()
    try:
        if sistema == "Windows":
            os.startfile(ruta)
        elif sistema == "Darwin":  # macOS
            subprocess.run(["open", ruta])
        else:  # Linux
            subprocess.run(["xdg-open", ruta])
    except Exception as e:
        logging.info(f"No se pudo abrir el archivo: {e}")

# Descarga y a continuación reproduce vídeos o fotos de instagram
def descargar_y_reproducir(url):
    loader = instaloader.Instaloader(save_metadata=False, download_comments=False)

    match = re.search(r"instagram\.com/(p|reel|tv)/([a-zA-Z0-9_-]+)", url)
    if not match:
        logging.info("URL de instagram no válida o formato no reconocido.")
        return

    shortcode = match.group(2)

    try:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)

        # Cambiar temporalmente al directorio /tmp
        tmp_dir = tempfile.gettempdir()
        cwd_original = os.getcwd()
        os.chdir(tmp_dir)

        # Descargar en carpeta con nombre del shortcode dentro de /tmp
        loader.download_post(post, target=shortcode)

        # Volver al directorio original
        os.chdir(cwd_original)

        # Ahora revisamos la carpeta
        carpeta_post = os.path.join(tmp_dir, shortcode)
        archivos = os.listdir(carpeta_post)
        archivos_media = [f for f in archivos if f.endswith(('.mp4', '.jpg'))]

        if not archivos_media:
            logging.info("No se encontró contenido multimedia.")
            return

        # Priorizar vídeo si hay
        archivo_video = next((f for f in archivos_media if f.endswith('.mp4')), None)
        if archivo_video:
            ruta_media = os.path.join(carpeta_post, archivo_video)
        else:
            ruta_media = os.path.join(carpeta_post, archivos_media[0])

        logging.info(f"Abrir archivo: {ruta_media}")
        abrir_archivo(ruta_media)

    except Exception as e:
        logging.info(f"Error al procesar el post: {e}")


# Descarga un archivo de instagram en un hilo separado
def descargar_en_hilo(url):
    hilo = threading.Thread(target=descargar_y_reproducir, args=(url,))
    hilo.start()
    return hilo

# Reproduce vídeo de youtube en streaming
def reproducir_streaming(url):
    subprocess.Popen([REPRODUCTOR_VIDEO, url])


# ¿La cadena contiene varias líneas?
def esMultiLinea(cadena: str) -> bool:
	return '\n' in cadena


# ¿La cadena es una URL?
def esURL(cadena: str) -> bool:
    return cadena.startswith(('http://', 'https://'))


#Intercepta una cadena del portapapeles y decide si debe cambiarla o no
def interceptarCambiarURL(cadena: str) -> str:
    global modo

    resultado = cadena

    # Si es multilínea, no se modifica
    if esMultiLinea(cadena):
        return resultado

    # Si no es una URL, no se modifica
    if not esURL(cadena):
        return resultado

    # Si el modo streaming se encuentra activo se intenta reproducir si procede
    if modo == MODO_STREAMING:

        # Fuentes de streaming compatibles
        streaming_sources = [ "instagram.com",
                              "youtube.com", "youtu.be",
                              "facebook.com" ]

        for streaming_source in streaming_sources:
            if streaming_source in cadena:
                reproducir_streaming(cadena)
                return cadena

    # Diccionario de dominios a reemplazar
    reemplazos = {
        "x.com": "fixupx.com",
        "tiktok.com": "tfxktok.com",
        # "instagram.com": "ixxstagram.com",
        # "facebook.com": "facebxxk.com",
        "twitter.com": "fixupx.com",  # Para revertir links antiguos
        "fixupx.com": "twixtter.com",  # Si prefieres no usar el nuevo dominio
        "reddit.com": "reddxt.com",
        # "youtube.com": "youtubefixupx.com",
        # "youtu.be": "youx.tube",
        "onlyfans.com": "0nlyfans.net",  # Muy útil si compartes contenido oculto
        "patreon.com": "pxtreon.com",
        "pornhub.com": "pxrnhub.com",  # Si estás compartiendo material NSFW
        "nhentai.net": "nhentaix.net",
        "discord.gg": "disxcord.gg",  # Enlaces de invitación
        "discord.com": "discxrd.com",
        "mediafire.com": "mediaf1re.com"  # Enlaces de descargas
    }

    # Aplicamos el primer reemplazo que coincida
    for original, nuevo in reemplazos.items():
        if original in cadena:
            resultado = cadena.replace(original, nuevo)
            break

    return resultado


#Programa principal
if __name__ == "__main__":
    # Configurar logging
    app_name = "alterclip"
    log_dir = Path(user_log_dir(app_name))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "alterclip.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    signal.signal(signal.SIGUSR1, handler_streaming)
    signal.signal(signal.SIGUSR2, handler_offline)

    logging.info("Programa iniciado. PID: %d", os.getpid())
    logging.info("Envíale la señal USR1 con `kill -USR1 <pid>` para cambiar el modo streaming.")
    logging.info("Envíale la señal USR2 con `kill -USR1 <pid>` para cambiar el modo offline.")
    logging.info("Por defecto se encuentra en el modo streaming")

    prev = ""
    while True:
        text = pyperclip.paste()
        if text != prev:
            modified = interceptarCambiarURL(text)
            pyperclip.copy(modified)
            prev = modified
        time.sleep(0.2)
