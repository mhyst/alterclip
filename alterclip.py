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
import sqlite3
from plyer import notification
from platformdirs import user_log_dir
from pathlib import Path
from typing import Optional
import shlex
import requests
import re
from urllib.parse import urlparse, urlunparse, parse_qs

# Constantes
REPRODUCTOR_VIDEO = os.getenv("ALTERCLIP_PLAYER", "mpv")
INVIDIOUS_INSTANCE = os.getenv("ALTERCLIP_INVIDIOUS_INSTANCE", "inv.nadeko.net")
MODO_STREAMING = 0
MODO_OFFLINE = 1
SIGNAL_STREAMING = signal.SIGUSR1
SIGNAL_OFFLINE = signal.SIGUSR2
UDP_PORT = 12345

class Alterclip:
    def __init__(self):
        # Inicializar la base de datos
        self.db_path = Path(user_log_dir("alterclip")) / "streaming_history.db"
        self._initialize_db()
        
        self.modo = MODO_OFFLINE
        self.prev_clipboard = ""
        self.reemplazos = {
            "x.com": "fixupx.com",
            "tiktok.com": "tfxktok.com",
            "twitter.com": "fixupx.com",
            "pornhub.com": "pxrnhub.com",
            "nhentai.net": "nhentaix.net",
            "actualidad.rt.com": "esrt.space",
            "www.youtube.com": INVIDIOUS_INSTANCE,
            "youtube.com": INVIDIOUS_INSTANCE,
            "youtu.be": INVIDIOUS_INSTANCE
        }
        self.streaming_sources = [
            "instagram.com",
            "youtube.com", "youtu.be",
            "facebook.com",
            "archive.org"
        ]

    def resolve_share_google(self, url: str) -> str:
        """
        Dada una URL de share.google, sigue las redirecciones y devuelve la URL final.
        """
        try:
            response = requests.get(url, allow_redirects=True, timeout=10)
            return response.url  # la URL final tras seguir todas las redirecciones
        except requests.RequestException as e:
            raise RuntimeError(f"Error resolviendo la URL: {e}")

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
    
    def is_video_archive_url(self,url):
        if not url.startswith("https://archive.org/details/"):
            return False
        
        identifier = url.split("/details/")[-1]
        api_url = f"https://archive.org/metadata/{identifier}"
        
        response = requests.get(api_url)
        if response.status_code != 200:
            return False
        
        data = response.json()
        video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".ogv"}
        
        for file in data.get("files", []):
            if file.get("source") != "original":
                continue

            name = file.get("name", "").lower()
            if any(name.endswith(ext) for ext in video_extensions):
                return True
        
        return False

    def get_archive_title(self,url):
        if not url.startswith("https://archive.org/details/"):
            return None
        
        identifier = url.split("/details/")[-1]
        api_url = f"https://archive.org/metadata/{identifier}"
        
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            return data.get("metadata", {}).get("title")
        except Exception:
            return None

    def reproducir_streaming(self, url: str):
        def reproducir_en_hilo(url):
            try:
                proceso = subprocess.Popen(
                    [REPRODUCTOR_VIDEO] + shlex.split(url),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                exit_code = proceso.wait()
                if exit_code != 0:
                    self.mostrar_error(f"La reproducción falló\nCódigo de error: {exit_code}")
            except Exception as e:
                self.mostrar_error(f"Error al lanzar el reproductor:\n{e}")

        # Crear y lanzar un nuevo hilo para la reproducción
        hilo = threading.Thread(target=reproducir_en_hilo, args=(url,), daemon=True)
        hilo.start()

    def es_streaming_compatible(self, url: str) -> bool:
        return any(source in url for source in self.streaming_sources)

    def interceptar_cambiar_url(self, cadena: str) -> str:
        """Intercepta y modifica las URLs según sea necesario"""
        if '\n' in cadena or not cadena.startswith(('http://', 'https://', 'share.only/')):
            return cadena

        # Si es una URL con prefijo share.only/, devolver la URL sin el prefijo
        if cadena.startswith('share.only/'):  # Prefijo para URLs de copia
            return cadena[11:]  # Eliminamos el prefijo share.only/

        if cadena.startswith('https://share.google'):
            return self.resolve_share_google(cadena)

        # Si es una URL de streaming, la guardamos en la base de datos
        if self.es_streaming_compatible(cadena):
            self._save_streaming_url(cadena)
            
            # Solo reproducimos si estamos en modo streaming
            if self.modo == MODO_STREAMING:
                self.reproducir_streaming(cadena)
                return cadena

        # Si no es streaming ni de copia, aplicamos los reemplazos normales
        #for original, nuevo in self.reemplazos.items():
        #    if original in cadena:
        #        return cadena.replace(original, nuevo)
        # Reemplazos seguros por dominio
        parsed = urlparse(cadena)
        if parsed.netloc in self.reemplazos:
            nuevo_netloc = self.reemplazos[parsed.netloc]
            parsed = parsed._replace(netloc=nuevo_netloc)
            return urlunparse(parsed)

        return cadena

    def udp_server(self):
        estados = {
            MODO_STREAMING: "Estado: Streaming",
            MODO_OFFLINE: "Estado: Offline"
        }
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind(('0.0.0.0', UDP_PORT))
            while True:
                data, addr = server_socket.recvfrom(1024)
                mensaje = data.decode()
                logging.info(f"Mensaje de {addr}: {mensaje}")
                if mensaje.lower() == "status":
                    respuesta = estados.get(self.modo, "Desconocido")
                else:
                    if self.modo == MODO_OFFLINE:
                        self.modo = MODO_STREAMING
                        respuesta = "Modo streaming"
                    else:
                        self.modo = MODO_OFFLINE
                        respuesta = "Modo offline"
                logging.info(f"Respuesta enviada: {respuesta}")
                server_socket.sendto(respuesta.encode(), addr)

    def _initialize_db(self):
        """Inicializa la base de datos y crea la tabla si no existe"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS streaming_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    platform TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla para tags
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    UNIQUE(name)
                )
            ''')
            
            # Tabla para la jerarquía de tags
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tag_hierarchy (
                    parent_id INTEGER,
                    child_id INTEGER,
                    FOREIGN KEY (parent_id) REFERENCES tags(id),
                    FOREIGN KEY (child_id) REFERENCES tags(id),
                    UNIQUE(parent_id, child_id)
                )
            ''')
            
            # Tabla para asociar URLs con tags
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS url_tags (
                    url_id INTEGER,
                    tag_id INTEGER,
                    FOREIGN KEY (url_id) REFERENCES streaming_history(id),
                    FOREIGN KEY (tag_id) REFERENCES tags(id),
                    UNIQUE(url_id, tag_id)
                )
            ''')
            
            # Crear índices para optimizar las búsquedas recursivas
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tag_hierarchy_parent ON tag_hierarchy(parent_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tag_hierarchy_child ON tag_hierarchy(child_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_url_tags_url ON url_tags(url_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_url_tags_tag ON url_tags(tag_id)
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error al inicializar la base de datos: {e}")

    def _get_content_title(self, url: str) -> tuple[str, str]:
        """Obtiene el título del contenido y la plataforma"""
        try:
            # Determinar la plataforma
            if 'youtube.com' in url or 'youtu.be' in url:
                platform = 'YouTube'
                # Para YouTube, usamos la API o parseamos el título del HTML
                try:
                    # Intentar usar la API de YouTube
                    youtube_api_key = os.getenv('YOUTUBE_API_KEY')
                    if youtube_api_key:
                        video_id = self._extract_youtube_id(url)
                        if video_id:
                            api_url = f'https://www.googleapis.com/youtube/v3/videos?id={video_id}&key={youtube_api_key}&part=snippet'
                            response = requests.get(api_url)
                            data = response.json()
                            if 'items' in data and data['items']:
                                return data['items'][0]['snippet']['title'], platform
                except:
                    pass
                
                # Si falla la API, parseamos el HTML
                response = requests.get(url)
                title_match = re.search(r'<title>(.*?)</title>', response.text)
                if title_match:
                    title = title_match.group(1).split(' - ')[0]
                    return title, platform

            elif 'instagram.com' in url:
                platform = 'Instagram'
                response = requests.get(url)
                title_match = re.search(r'"description" content="(.*?)"', response.text)
                if title_match:
                    return title_match.group(1), platform

            elif 'facebook.com' in url or 'fb.watch' in url:
                platform = 'Facebook'
                try:
                    # Intentar obtener el título usando metadatos Open Graph
                    response = requests.get(url)
                    # Buscar el título usando diferentes patrones
                    title_match = re.search(r'property="og:title" content="(.*?)"', response.text)
                    if not title_match:
                        title_match = re.search(r'"title" content="(.*?)"', response.text)
                    if not title_match:
                        title_match = re.search(r'<title>(.*?)</title>', response.text)
                    
                    if title_match:
                        title = title_match.group(1).strip()
                        # Eliminar el sufijo " | Facebook" si existe
                        title = title.replace(' | Facebook', '').strip()
                        return title, platform
                except Exception as e:
                    logging.error(f"Error al obtener título de Facebook: {e}")
                    return "Título no disponible", platform
            elif 'archive.org' in url:
                platform = 'Archive.org'
                title = self.get_archive_title(url)
                if title:
                    return title, platform

            return "Título no disponible", "Desconocido"
        except Exception as e:
            logging.error(f"Error al obtener título: {e}")
            return "Título no disponible", "Desconocido"

    def _extract_youtube_id(self, url: str) -> str:
        """Extrae el ID de video de una URL de YouTube"""
        try:
            if 'youtu.be' in url:
                return url.split('/')[-1]
            
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            if 'v' in query_params:
                return query_params['v'][0]
            
            return ''
        except:
            return ''

    def get_id_by_url(self,url: str) -> int:
        """Obtiene el id de una entrada del historial por su url
        
        Args:
            url: URL de la entrada en streaming_history
            
        Returns:
            int: El id de la entrada o None si no se encuentra
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM streaming_history WHERE url = ?', (url,))
            result = cursor.fetchone()
            
            if not result:
                #print(f"No se encontró ninguna entrada con url {url}", file=sys.stderr)
                return None
                
            return result[0]
        except Exception as e:
            print(f"Error al obtener el id: {e}", file=sys.stderr)
            return None


    def _save_streaming_url(self, url: str):
        """Guarda una URL de streaming en la base de datos"""
        try:
            title, platform = self._get_content_title(url)
            id = self.get_id_by_url(url)
            if id:
                logging.info(f"URL {url} ya existe en la base de datos con id {id}")
            else:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('INSERT INTO streaming_history (url, title, platform) VALUES (?, ?, ?)', 
                            (url, title, platform))
                conn.commit()
                conn.close()
        except Exception as e:
            logging.error(f"Error al guardar URL en la base de datos: {e}")

    def get_streaming_history(self, limit: int = 10):
        """Obtiene el historial de URLs de streaming"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, url, timestamp FROM streaming_history ORDER BY timestamp DESC LIMIT ?', (limit,))
            results = cursor.fetchall()
            conn.close()
            return results
        except Exception as e:
            logging.error(f"Error al obtener historial: {e}")
            return []

    def iniciar(self):
        signal.signal(SIGNAL_STREAMING, self.handler_streaming)
        signal.signal(SIGNAL_OFFLINE, self.handler_offline)

        logging.info("Programa iniciado. PID: %d", os.getpid())
        logging.info("Envia USR1 (kill -USR1 <pid>) para STREAMING, USR2 para OFFLINE")

        hilo_udp = threading.Thread(target=self.udp_server, daemon=True)
        hilo_udp.start()

        # Limpiar el portapapeles
        pyperclip.copy("")

        try:
            while True:
                try:
                    text = pyperclip.paste()
                except Exception as e:
                    logging.warning(f"Error al leer del portapapeles: {e}")
                    continue

                if text.strip():  # Solo procesar si hay contenido significativo
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





if __name__ == "__main__":
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
