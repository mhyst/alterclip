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

def get_streaming_history(limit: int = 10, no_limit: bool = False) -> List[Tuple[int, str, str, str, str]]:
    """Obtiene el historial de URLs de streaming
    Si no_limit es True, muestra todo el historial
    Si no_limit es False y limit es None, muestra 10 entradas por defecto"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        if no_limit:
            cursor.execute('SELECT id, url, title, platform, timestamp FROM streaming_history ORDER BY timestamp DESC')
        else:
            cursor.execute('SELECT id, url, title, platform, timestamp FROM streaming_history ORDER BY timestamp DESC LIMIT ?', (limit,))
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"Error al obtener historial: {e}", file=sys.stderr)
        return []

def play_streaming_url(url_id: int) -> None:
    """Reproduce una URL de streaming por su ID (absoluto o relativo)
    Si el ID es negativo, se interpreta como un índice relativo desde el final
    (ejemplo: -1 = último, -2 = penúltimo, etc.)"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # Si el ID es negativo, lo convertimos a un ID absoluto
        if url_id < 0:
            # Obtener el total de entradas
            cursor.execute('SELECT COUNT(*) FROM streaming_history')
            total_entries = cursor.fetchone()[0]
            if total_entries == 0:
                print("No hay entradas en el historial", file=sys.stderr)
                return
                
            # Convertir ID relativo a absoluto
            abs_id = total_entries + url_id + 1
            if abs_id <= 0:
                print(f"No se puede reproducir una entrada más allá del inicio del historial", file=sys.stderr)
                return
            url_id = abs_id
        
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

def copy_streaming_url(url_id: int) -> None:
    """Copia una URL de streaming al portapapeles con prefijo share.only/ usando su ID"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # Si el ID es negativo, lo convertimos a un ID absoluto
        if url_id < 0:
            # Obtener el total de entradas
            cursor.execute('SELECT COUNT(*) FROM streaming_history')
            total_entries = cursor.fetchone()[0]
            if total_entries == 0:
                print("No hay entradas en el historial", file=sys.stderr)
                return
                
            # Convertir ID relativo a absoluto
            abs_id = total_entries + url_id + 1
            if abs_id <= 0:
                print(f"No se puede reproducir una entrada más allá del inicio del historial", file=sys.stderr)
                return
            url_id = abs_id
        
        cursor.execute('SELECT url FROM streaming_history WHERE id = ?', (url_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print(f"No se encontró URL con ID {url_id}", file=sys.stderr)
            return
            
        url = result[0]
        # Añadir prefijo share.only/ a la URL
        share_url = f"share.only/{url}"
        # Usar xclip para copiar al portapapeles
        subprocess.run(['xclip', '-selection', 'clipboard'], input=share_url, text=True)
        print(f"URL copiada al portapapeles: {share_url}")
    except Exception as e:
        print(f"Error al copiar URL: {e}", file=sys.stderr)

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

    history [--limit N] [--no-limit]
        Muestra el historial de URLs de streaming reproducidas
        Opciones:
            --limit N    Número de entradas a mostrar (por defecto: 10)
            --no-limit   Muestra todo el historial sin límite

    play [ID]
        Reproduce una URL de streaming guardada usando su ID
        ID: Identificador numérico de la URL en el historial. Si no se especifica, se reproducirá el último video (-1)

    copy [ID]
        Copia una URL de streaming al portapapeles con prefijo share.only/
        ID: Identificador numérico de la URL en el historial. Si no se especifica, se copiará el último video (-1)

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
    alterclip-cli history --no-limit

    # Ver solo las últimas 5 entradas
    alterclip-cli history --limit 5

    # Reproducir una URL con ID 123
    alterclip-cli play 123

    # Reproducir el último video
    alterclip-cli play

    # Copiar una URL con ID 123 al portapapeles
    alterclip-cli copy 123

    # Copiar el último video al portapapeles
    alterclip-cli copy

    # Cambiar el modo de alterclip
    alterclip-cli toggle
""")

def main() -> None:
    parser = argparse.ArgumentParser(description='Interfaz de línea de comandos para alterclip')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # Subparser para historial
    history_parser = subparsers.add_parser('history', help='Ver historial de URLs de streaming')
    history_parser.add_argument('--limit', type=int, default=10, help='Número de entradas a mostrar')
    history_parser.add_argument('--no-limit', action='store_true', help='Muestra todo el historial sin límite')
    
    # Subparser para reproducir
    play_parser = subparsers.add_parser('play', help='Reproducir URL de streaming por ID')
    play_parser.add_argument('id', type=int, default=-1, nargs='?', help='ID de la URL a reproducir. Si no se especifica, se reproducirá el último video (-1)')
    
    # Subparser para copiar
    copy_parser = subparsers.add_parser('copy', help='Copiar URL de streaming al portapapeles con prefijo share.only/')
    copy_parser.add_argument('id', type=int, default=-1, nargs='?', help='ID de la URL a copiar. Si no se especifica, se copiará el último video (-1)')
    
    # Subparser para toggle
    subparsers.add_parser('toggle', help='Cambiar modo entre streaming y offline')
    
    # Subparser para help
    subparsers.add_parser('help', help='Muestra esta ayuda detallada')
    
    args = parser.parse_args()
    
    if args.command == 'history':
        history = get_streaming_history(args.limit, args.no_limit)
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
    
    elif args.command == 'copy':
        copy_streaming_url(args.id)
    
    elif args.command == 'toggle':
        toggle_mode()
    
    elif args.command == 'help':
        show_help()
    
    
if __name__ == "__main__":
    main()
