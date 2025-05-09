#!/usr/bin/env python3
# Compatible con Termux en Android

import time
import os
import subprocess
import tempfile
import logging
import signal
import socket
import sys
import threading
from platformdirs import user_log_dir
from pathlib import Path

# Modificar para indicar tu reproductor favorito
REPRODUCTOR_VIDEO = os.getenv("ALTERCLIP_PLAYER", "am")  # usamos intent de Android
MODO_STREAMING = 0
MODO_OFFLINE = 1
modo = MODO_STREAMING

# Lista de dominios para streaming
streaming_sources = [
    "instagram.com", "youtube.com", "youtu.be",
    "facebook.com"
]

# Señales para alternar modo
def handler_streaming(signum, frame):
    global modo
    modo = MODO_STREAMING
    logging.info("¡Señal STREAMING recibida! Cambiando a modo STREAMING.")

def handler_offline(signum, frame):
    global modo
    modo = MODO_OFFLINE
    logging.info("¡Señal OFFLINE recibida! Cambiando a modo OFFLINE.")

# UDP server para cambiar modo
def handler_udp_server():
    global modo
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('0.0.0.0', 12345))

    while True:
        data, addr = server_socket.recvfrom(1024)
        mensaje = data.decode()
        logging.info(f"Mensaje de {addr}: {mensaje}")
        if modo == MODO_OFFLINE:
            modo = MODO_STREAMING
            respuesta = "Modo streaming"
        else:
            modo = MODO_OFFLINE
            respuesta = "Modo offline"
        server_socket.sendto(respuesta.encode(), addr)

# Cliente UDP
def udp_client(mensaje):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(mensaje.encode(), ("127.0.0.1", 12345))
    datos, _ = sock.recvfrom(1024)
    print(f"Respuesta del servidor: {datos.decode()}")
    sock.close()

# Mostrar notificación usando termux-api
def mostrar_error(mensaje):
    subprocess.run([
        'termux-notification',
        '--title', 'Error',
        '--content', mensaje
    ])

def reproducir_streaming(url):
    try:
        subprocess.run(['mpv', '--vo=x11', url], check=True)
    except subprocess.CalledProcessError as e:
        logging.info(f"Error al reproducir el vídeo: {e}")
    except FileNotFoundError:
        logging.info("mpv no está instalado o no se encuentra en el PATH.")


# Clipboard usando termux-api
def get_clipboard():
    return subprocess.check_output(['termux-clipboard-get']).decode().strip()

def set_clipboard(text):
    subprocess.run(['termux-clipboard-set'], input=text.encode())

# Es multilínea?
def es_multilinea(cadena):
    return '\n' in cadena

# Es URL?
def es_url(cadena):
    return cadena.startswith(('http://', 'https://'))

# Intercepta y modifica cadena del portapapeles
def interceptar_cambiar_url(cadena):
    global modo
    resultado = cadena

    if es_multilinea(cadena) or not es_url(cadena):
        return resultado

    if modo == MODO_STREAMING:
        if any(source in cadena for source in streaming_sources):
            reproducir_streaming(cadena)
            return cadena

    reemplazos = {
        "x.com": "fixupx.com",
        "tiktok.com": "tfxktok.com",
        "twitter.com": "fixupx.com",
        "fixupx.com": "twixtter.com",
        "reddit.com": "reddxt.com",
        "onlyfans.com": "0nlyfans.net",
        "patreon.com": "pxtreon.com",
        "pornhub.com": "pxrnhub.com",
        "nhentai.net": "nhentaix.net",
        "discord.gg": "disxcord.gg",
        "discord.com": "discxrd.com",
        "mediafire.com": "mediaf1re.com"
    }

    for original, nuevo in reemplazos.items():
        if original in cadena:
            resultado = cadena.replace(original, nuevo)
            break

    return resultado

if __name__ == "__main__":
    if len(sys.argv) > 1:
        udp_client("toggle")
        sys.exit(0)

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

    logging.info("Alterclip iniciado en Termux. PID: %d", os.getpid())
    logging.info("Envia USR1 o USR2 o usa UDP para cambiar de modo.")

    hilo_udp = threading.Thread(target=handler_udp_server)
    hilo_udp.start()

    prev = ""
    while True:
        try:
            text = get_clipboard()
            if text != prev:
                modified = interceptar_cambiar_url(text)
                set_clipboard(modified)
                prev = modified
            time.sleep(0.2)
        except Exception as e:
            logging.error(f"Error en bucle principal: {e}")
            time.sleep(1)

    hilo_udp.join()

