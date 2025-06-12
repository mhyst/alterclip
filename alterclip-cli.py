#!/usr/bin/env python3

import argparse
import sys
import socket
import sqlite3
from pathlib import Path
from platformdirs import user_log_dir
import subprocess
from typing import List, Tuple
from unidecode import unidecode

def get_db_path() -> Path:
    """Obtiene la ruta de la base de datos"""
    return Path(user_log_dir("alterclip")) / "streaming_history.db"

def remove_accents(input_str: str) -> str:
    """Elimina los acentos de una cadena de texto"""
    replacements = {
        'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a', 'å': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'ô': 'o', 'ö': 'o', 'õ': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ñ': 'n', 'ç': 'c',
        'Á': 'A', 'À': 'A', 'Â': 'A', 'Ä': 'A', 'Ã': 'A', 'Å': 'A',
        'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
        'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
        'Ó': 'O', 'Ò': 'O', 'Ô': 'O', 'Ö': 'O', 'Õ': 'O',
        'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
        'Ñ': 'N', 'Ç': 'C'
    }
    return ''.join(replacements.get(c, c) for c in input_str)

def get_streaming_history(limit: int = 10, no_limit: bool = False, search: str = None) -> List[Tuple[int, str, str, str, str]]:
    """Obtiene el historial de URLs de streaming
    Si no_limit es True, muestra todo el historial
    Si no_limit es False y limit es None, muestra 10 entradas por defecto
    Si search no es None, muestra solo las entradas que contengan la cadena de búsqueda en el título
    La búsqueda es insensible a acentos y mayúsculas/minúsculas"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        query = '''
            SELECT id, url, title, platform, timestamp 
            FROM streaming_history 
            WHERE 1=1
        '''
        params = []
        
        if search:
            # Eliminar acentos y convertir a minúsculas del término de búsqueda
            search_term = remove_accents(search.lower())
            # Eliminar acentos y convertir a minúsculas del título en la base de datos
            query += ' AND LOWER(REPLACE(title, "á", "a")) LIKE ?'
            params.append(f'%{search_term}%')
        
        if not no_limit:
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
        
        cursor.execute(query, params)
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

def remove_streaming_url(url_id: int) -> None:
    """Elimina una URL de streaming del historial usando su ID"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # Primero obtenemos la URL para mostrar un mensaje de confirmación
        cursor.execute('SELECT url FROM streaming_history WHERE id = ?', (url_id,))
        result = cursor.fetchone()
        
        if not result:
            print(f"No se encontró URL con ID {url_id}", file=sys.stderr)
            return
            
        url = result[0]
        print(f"¡Advertencia! Se va a eliminar la siguiente URL del historial:")
        print(f"ID: {url_id}")
        print(f"URL: {url}")
        
        # Preguntar confirmación
        confirm = input("¿Estás seguro que quieres eliminar esta entrada? (s/n): ").lower()
        if confirm != 's':
            print("Operación cancelada")
            return
            
        # Eliminar la entrada
        cursor.execute('DELETE FROM streaming_history WHERE id = ?', (url_id,))
        conn.commit()
        conn.close()
        print(f"Entrada con ID {url_id} eliminada del historial")
    except Exception as e:
        print(f"Error al eliminar URL: {e}", file=sys.stderr)

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

    rm [ID]
        Elimina una entrada del historial
        ID: Identificador numérico de la entrada a eliminar

    toggle
        Cambia el modo de alterclip entre streaming y offline
        En modo streaming: alterclip reproducirá automáticamente las URLs de streaming
        En modo offline: alterclip solo guardará las URLs para futura referencia

    search [TERM]
        Busca URLs en el historial por título
        TERM: Término de búsqueda

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

    # Eliminar una entrada con ID 123
    alterclip-cli rm 123

    # Cambiar el modo de alterclip
    alterclip-cli toggle

    # Buscar URLs en el historial por título
    alterclip-cli search "título de búsqueda"
""")

def search_streaming_history(search_term: str) -> None:
    """Busca URLs de streaming en el historial que contengan la cadena de búsqueda en el título"""
    try:
        results = get_streaming_history(search=search_term)
        if not results:
            print(f"No se encontraron resultados para '{search_term}'")
            return
            
        print(f"\nResultados de búsqueda para '{search_term}':")
        print("-" * 80)
        for id, url, title, platform, timestamp in results:
            print(f"ID: {id}")
            print(f"URL: {url}")
            print(f"Título: {title}")
            print(f"Plataforma: {platform}")
            print(f"Fecha: {timestamp}")
            print("-" * 80)
    except Exception as e:
        print(f"Error al buscar en el historial: {e}", file=sys.stderr)

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
    
    # Subparser para eliminar
    rm_parser = subparsers.add_parser('rm', help='Eliminar una entrada del historial')
    rm_parser.add_argument('id', type=int, help='ID de la entrada a eliminar')
    
    # Subparser para buscar
    search_parser = subparsers.add_parser('search', help='Buscar URLs en el historial por título')
    search_parser.add_argument('term', type=str, help='Término de búsqueda')
    
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
    
    elif args.command == 'rm':
        remove_streaming_url(args.id)
    
    elif args.command == 'search':
        search_streaming_history(args.term)
    
    elif args.command == 'toggle':
        toggle_mode()
    
    elif args.command == 'help':
        show_help()
    
    
if __name__ == "__main__":
    main()
