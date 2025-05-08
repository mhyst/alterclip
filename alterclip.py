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
import logging
import signal
import socket
import sys
import threading
from plyer import notification
from platformdirs import user_log_dir
from pathlib import Path
from typing import Optional
import shlex

# Constantes
REPRODUCTOR_VIDEO = os.getenv("ALTERCLIP_PLAYER", "mpv")
MODO_STREAMING = 0
MODO_OFFLINE = 1
SIGNAL_STREAMING = signal.SIGUSR1
SIGNAL_OFFLINE = signal.SIGUSR2
UDP_PORT = 12345

class Alterclip:
    def __init__(self):
        self.modo = MODO_STREAMING
        self.prev_clipboard = ""
        self.reemplazos = {
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
        self.streaming_sources = [
            "instagram.com",
            "youtube.com", "youtu.be",
            "facebook.com"
        ]

    def handler_streaming(self, signum, frame):
        self.modo = MODO_STREAMING
        logging.info("\u00a1Se\u00f1al STREAMING recibida! Cambiando a modo STREAMING.")

    def handler_offline(self, signum, frame):
        self.modo = MODO_OFFLINE
        logging.info("\u00a1Se\u00f1al OFFLINE recibida! Cambiando a modo OFFLINE.")

    def mostrar_error(self, mensaje: str):
        notification.notify(
            title='Error',
            message=mensaje,
            app_name='Alterclip',
            timeout=20
        )

    def reproducir_streaming(self, url: str):
        try:
            proceso = subprocess.Popen(
                [REPRODUCTOR_VIDEO] + shlex.split(url),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            exit_code = proceso.wait()
            if exit_code != 0:
                self.mostrar_error(f"La reproducci\u00f3n fall\u00f3\nC\u00f3digo de error: {exit_code}")
        except Exception as e:
            self.mostrar_error(f"Error al lanzar el reproductor:\n{e}")

    def es_streaming_compatible(self, url: str) -> bool:
        return any(source in url for source in self.streaming_sources)

    def interceptar_cambiar_url(self, cadena: str) -> str:
        if '\n' in cadena or not cadena.startswith(('http://', 'https://')):
            return cadena

        if self.modo == MODO_STREAMING and self.es_streaming_compatible(cadena):
            self.reproducir_streaming(cadena)
            return cadena

        for original, nuevo in self.reemplazos.items():
            if original in cadena:
                return cadena.replace(original, nuevo)

        return cadena

    def udp_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind(('0.0.0.0', UDP_PORT))
            while True:
                data, addr = server_socket.recvfrom(1024)
                mensaje = data.decode()
                logging.info(f"Mensaje de {addr}: {mensaje}")
                if self.modo == MODO_OFFLINE:
                    self.modo = MODO_STREAMING
                    respuesta = "Modo streaming"
                else:
                    self.modo = MODO_OFFLINE
                    respuesta = "Modo offline"
                logging.info(f"Respuesta enviada: {respuesta}")
                server_socket.sendto(respuesta.encode(), addr)

    def iniciar(self):
        signal.signal(SIGNAL_STREAMING, self.handler_streaming)
        signal.signal(SIGNAL_OFFLINE, self.handler_offline)

        logging.info("Programa iniciado. PID: %d", os.getpid())
        logging.info("Envia USR1 (kill -USR1 <pid>) para STREAMING, USR2 para OFFLINE")

        hilo_udp = threading.Thread(target=self.udp_server, daemon=True)
        hilo_udp.start()

        try:
            while True:
                try:
                    text = pyperclip.paste()
                except Exception as e:
                    logging.warning(f"Error al leer del portapapeles: {e}")
                    continue

                if text != self.prev_clipboard:
                    modified = self.interceptar_cambiar_url(text)
                    if modified != text:
                        pyperclip.copy(modified)
                        self.prev_clipboard = modified
                    else:
                        self.prev_clipboard = text

                time.sleep(0.2)
        except KeyboardInterrupt:
            logging.info("Programa terminado por el usuario.")


# Cliente UDP para cambiar el modo
def udp_client(mensaje: str):
    dest_ip = "127.0.0.1"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(mensaje.encode(), (dest_ip, UDP_PORT))
        print(f"Enviando mensaje: {mensaje}")
        datos, _ = sock.recvfrom(1024)
        print(f"Respuesta del servidor: {datos.decode()}")
    finally:
        sock.close()


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

    app = Alterclip()
    app.iniciar()
