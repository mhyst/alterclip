#!/usr/bin/env python3

import argparse
import sys
import socket
import sqlite3
from pathlib import Path
from platformdirs import user_log_dir
import subprocess
from typing import List, Tuple

def get_db_path() -> Path:
    """Obtiene la ruta de la base de datos"""
    return Path(user_log_dir("alterclip")) / "streaming_history.db"

def get_streaming_history(limit: int = 10) -> List[Tuple[int, str, str, str, str]]:
    """Obtiene el historial de URLs de streaming"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute('SELECT id, url, title, platform, timestamp FROM streaming_history ORDER BY timestamp DESC LIMIT ?', (limit,))
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"Error al obtener historial: {e}", file=sys.stderr)
        return []

def play_streaming_url(url_id: int) -> None:
    """Reproduce una URL de streaming por su ID"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute('SELECT url FROM streaming_history WHERE id = ?', (url_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print(f"No se encontró URL con ID {url_id}", file=sys.stderr)
            return
            
        url = result[0]
        # Usar el reproductor por defecto (mpv)
        subprocess.run(['mpv', url], check=True)
    except Exception as e:
        print(f"Error al reproducir URL: {e}", file=sys.stderr)

def udp_client(mensaje: str):
    dest_ip = "127.0.0.1"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(mensaje.encode(), (dest_ip, 12345))
        print(f"Enviando mensaje: {mensaje}")
        datos, _ = sock.recvfrom(1024)
        print(f"Respuesta del servidor: {datos.decode()}")
    finally:
        sock.close()

def toggle_mode() -> None:
    udp_client("toggle")
   

def show_help() -> None:
    """Muestra información detallada sobre el uso de alterclip-cli"""
    print("""
alterclip-cli - Interfaz de línea de comandos para alterclip

Uso:
    alterclip-cli [comando] [opciones]

Comandos disponibles:

    history [--limit N]
        Muestra el historial de URLs de streaming reproducidas
        Opciones:
            --limit N    Número de entradas a mostrar (por defecto: 10)

    play ID
        Reproduce una URL de streaming guardada usando su ID
        ID: Identificador numérico de la URL en el historial

    toggle
        Cambia el modo de alterclip entre streaming y offline
        En modo streaming: alterclip reproducirá automáticamente las URLs de streaming
        En modo offline: alterclip solo guardará las URLs para futura referencia

    help
        Muestra esta ayuda detallada

Información adicional:
- alterclip guarda automáticamente todas las URLs de streaming en su base de datos
  incluso cuando está en modo offline
- Las URLs se pueden reproducir más tarde usando el comando 'play' y su ID
- El historial muestra el título del contenido, la plataforma (YouTube, Instagram, etc.)
  y la fecha de reproducción
- La base de datos se almacena en el directorio de configuración del usuario

Ejemplos:
    # Ver el historial completo
    alterclip-cli history

    # Ver solo las últimas 5 entradas
    alterclip-cli history --limit 5

    # Reproducir una URL con ID 123
    alterclip-cli play 123

    # Cambiar el modo de alterclip
    alterclip-cli toggle
""")

def main() -> None:
    parser = argparse.ArgumentParser(description='Interfaz de línea de comandos para alterclip')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # Subparser para historial
    history_parser = subparsers.add_parser('history', help='Ver historial de URLs de streaming')
    history_parser.add_argument('--limit', type=int, default=10, help='Número de entradas a mostrar')
    
    # Subparser para reproducir
    play_parser = subparsers.add_parser('play', help='Reproducir URL de streaming por ID')
    play_parser.add_argument('id', type=int, help='ID de la URL a reproducir')
    
    # Subparser para toggle
    subparsers.add_parser('toggle', help='Cambiar modo entre streaming y offline')
    
    # Subparser para help
    subparsers.add_parser('help', help='Muestra esta ayuda detallada')
    
    args = parser.parse_args()
    
    if args.command == 'history':
        history = get_streaming_history(args.limit)
        if history:
            print("\nHistorial de URLs de streaming:")
            print("-" * 80)
            for id, url, title, platform, timestamp in history:
                print(f"ID: {id}")
                print(f"URL: {url}")
                print(f"Título: {title}")
                print(f"Plataforma: {platform}")
                print(f"Fecha: {timestamp}")
                print("-" * 80)
        else:
            print("No hay historial disponible")
    
    elif args.command == 'play':
        play_streaming_url(args.id)
    
    elif args.command == 'toggle':
        toggle_mode()
    
    elif args.command == 'help':
        show_help()
    
    if args.command == 'history':
        history = get_streaming_history(args.limit)
        if history:
            print("\nHistorial de URLs de streaming:")
            print("-" * 80)
            for id, url, title, platform, timestamp in history:
                print(f"ID: {id}")
                print(f"URL: {url}")
                print(f"Título: {title}")
                print(f"Plataforma: {platform}")
                print(f"Fecha: {timestamp}")
                print("-" * 80)
        else:
            print("No hay historial disponible")
    
    elif args.command == 'play':
        play_streaming_url(args.id)
    
if __name__ == "__main__":
    main()
