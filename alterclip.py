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
import os
import subprocess
import tempfile 
import logging
import signal
from plyer import notification
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

def mostrar_error(mensaje):
    notification.notify(
        title='Error',
        message=f"{mensaje}",
        app_name='Alterclip',
        timeout=20  # duración en segundos
    )


# Reproduce vídeo de youtube en streaming
def reproducir_streaming(url):
    try:
        proceso = subprocess.Popen(
            [REPRODUCTOR_VIDEO, url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        exit_code = proceso.wait()
        if exit_code != 0:
            mostrar_error(f"La reproducción falló\nCódigo de error: {exit_code}")
    except Exception as e:
        mostrar_error(f"Error al lanzar el reproductor:\n{e}")


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
