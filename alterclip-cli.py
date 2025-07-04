#!/usr/bin/env python3

import argparse
import sys
import socket
import sqlite3
from pathlib import Path
from platformdirs import user_log_dir
import subprocess
from typing import List, Tuple
import argcomplete
import os
from termcolor import colored
import unicodedata
from datetime import datetime
import openai
import json

REPRODUCTOR_VIDEO = "mpv"

conn = None

def print_error(message: str, file=sys.stderr) -> None:
    """Muestra un mensaje de error con formato mejorado"""
    print(colored("Error:", 'red', attrs=['bold']), 
          colored(message, 'yellow'), 
          file=file)

def print_separator(char='─', length=80, style='thin') -> None:
    """Muestra una línea separadora con formato mejorado usando caracteres Unicode
    Estilos disponibles: 'thin', 'thick', 'double'"""
    styles = {
        'thin': '─',
        'thick': '━',
        'double': '═'
    }
    separator = styles.get(style, char) * length
    print(colored(separator, 'white', attrs=['dark']))

def get_db_path() -> Path:
    """Obtiene la ruta de la base de datos"""
    return Path(user_log_dir("alterclip")) / "streaming_history.db"

# Crear la conexión a la base de datos
def create_connection() -> sqlite3.Connection:
    """Crea una conexión a la base de datos"""
    conn = sqlite3.connect(get_db_path())

    #Añadimos la función remove_accents para que pueda ser usada en las consultas
    conn.create_function("remove_accents", 1, remove_accents)

    #Vamos a realizar migración para añadir la nueva columna "visto" a streaming_history
    cursor = conn.cursor()

    # Comprobar si ya existe la columna 'visto'
    cursor.execute("PRAGMA table_info(streaming_history);")
    columnas = [fila[1] for fila in cursor.fetchall()]

    if 'visto' not in columnas:
        cursor.execute("ALTER TABLE streaming_history ADD COLUMN visto INTEGER DEFAULT 0;")

    conn.commit()
    return conn

def get_db_connection() -> sqlite3.Connection:
    """Obtiene la conexión a la base de datos, asegurándose de que esté establecida"""
    global conn
    if conn is None:
        conn = create_connection()
    return conn

def remove_accents(text):
    """Elimina los acentos de una cadena de texto"""
    if not isinstance(text, str):
        return ""

    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    ).lower()

def format_history_entry(entry: Tuple[int, str, str, str, str, List[str]]) -> str:
    """Formatea una entrada del historial para mostrar en la salida"""
    id, url, title, platform, timestamp, tags = entry
    
    # Convertir cada tag a su jerarquía completa
    formatted_tags = []
    for tag in tags:
        hierarchy = get_tag_hierarchy(tag)
        formatted_tags.append(hierarchy)
    
    # Unir las jerarquías con comas
    tags_str = ', '.join(formatted_tags)
    
    # Formatear la fecha de manera más legible
    from datetime import datetime
    date = datetime.fromisoformat(timestamp)
    formatted_date = date.strftime('%Y-%m-%d %H:%M:%S')
    
    return f"""
{colored('ID:', 'yellow')} {id}
{colored('URL:', 'cyan')} {url}
{colored('Título:', 'blue')} {title}
{colored('Plataforma:', 'magenta')} {platform}
{colored('Fecha:', 'green')} {formatted_date}
{colored('Tags:', 'yellow')} {tags_str}
{colored('─' * 80, 'white', attrs=['dark'])}"""

def get_streaming_history(limit: int = 10, no_limit: bool = False, search: str = None, tags: List[str] = None, no_tags: bool = False, platform: str = None, since: str = None, visto: int = None) -> Tuple[str, list]:
    """Obtiene el historial de URLs de streaming con sus tags asociados
    Si no_limit es True, muestra todo el historial
    Si no_limit es False y limit es None, muestra 10 entradas por defecto
    Si search no es None, muestra solo las entradas que contengan la cadena de búsqueda en el título o URL
    Si tags no es None, muestra solo las entradas que tengan al menos uno de los tags especificados
    Si --no-tags está especificado, muestra solo las URLs sin tags asociados
    También muestra URLs relacionadas con tags hijos y padres de los especificados
    Si since no es None, muestra solo las entradas que tengan una fecha posterior a la especificada
    
    Devuelve una tupla (error_code, entries) donde:
    - error_code: None si no hay error, o una cadena con el mensaje de error
    - entries: lista de entradas si no hay error, o None si hay error
    """
    try:
        cursor = conn.cursor()
        
        # Build the WHERE clause
        where_clause = "WHERE 1=1"
        params = []
        
        # Add search filter
        if search:
            where_clause += " AND (remove_accents(sh.title) LIKE ? OR remove_accents(sh.url) LIKE ?)"
            search_param = f"%{remove_accents(search)}%"
            params.extend([search_param, search_param])
            
        # Add visto filter
        if visto is not None:
            where_clause += " AND sh.visto = ?"
            params.append(visto)
            
        # Add tags filter
        if tags:
            tag_ids = []
            for tag in tags:
                tag_id = get_tag_id(tag)
                if tag_id:
                    tag_ids.append(tag_id)
                    
                    # Get IDs of child tags
                    cursor.execute('''
                        WITH RECURSIVE descendant_tags(id) AS (
                            SELECT child_id FROM tag_hierarchy WHERE parent_id = ?
                            UNION ALL
                            SELECT th.child_id FROM tag_hierarchy th
                            JOIN descendant_tags dt ON th.parent_id = dt.id
                        )
                        SELECT id FROM descendant_tags
                    ''', (tag_id,))
                    child_ids = cursor.fetchall()
                    tag_ids.extend([child[0] for child in child_ids])
                    
                    # Get IDs of parent tags
                    cursor.execute('''
                        WITH RECURSIVE parent_tags(id) AS (
                            SELECT parent_id FROM tag_hierarchy WHERE child_id = ?
                            UNION ALL
                            SELECT th.parent_id FROM tag_hierarchy th
                            JOIN parent_tags pt ON th.child_id = pt.id
                        )
                        SELECT id FROM parent_tags
                    ''', (tag_id,))
                    parent_ids = cursor.fetchall()
                    tag_ids.extend([parent[0] for parent in parent_ids])
            
            if tag_ids:
                tag_ids_str = ','.join(map(str, tag_ids))
                where_clause += f" AND sh.id IN (SELECT DISTINCT url_id FROM url_tags WHERE tag_id IN ({tag_ids_str}))"
                
        # Add no_tags filter
        if no_tags:
            where_clause += " AND sh.id NOT IN (SELECT DISTINCT url_id FROM url_tags)"
            
        # Add platform filter
        if platform:
            where_clause += " AND remove_accents(sh.platform) = ?"
            params.append(remove_accents(platform))

        if since:
            try:
                # Intenta convertir la fecha a formato YYYY-MM-DD
                datetime.strptime(since, '%Y-%m-%d')
            except ValueError:
                return "Formato de fecha inválido. Use YYYY-MM-DD", None

            where_clause += " AND sh.timestamp >= ?"
            since = since + " 00:00:00"
            params.append(since)
            
        # Handle limit parameter
        if no_limit:
            limit_clause = ""
        elif limit is None:
            limit_clause = "LIMIT 10"
        else:
            limit_clause = "LIMIT ?"
            params.append(limit)
        
        # Build the final query with all filters combined
        query = f'''
            SELECT 
                sh.id, 
                sh.url, 
                sh.title, 
                sh.platform, 
                sh.timestamp,
                GROUP_CONCAT(t.name) as tags
            FROM streaming_history sh
            LEFT JOIN url_tags ut ON sh.id = ut.url_id
            LEFT JOIN tags t ON ut.tag_id = t.id
            {where_clause}
            GROUP BY sh.id, sh.url, sh.title, sh.platform, sh.timestamp
            ORDER BY sh.timestamp DESC
            {limit_clause}
        '''
        
        cursor.execute(query, params)
        entries = cursor.fetchall()
        
        if not entries:
            return "No se encontraron coincidencias con la búsqueda", None
            
        # Convertir tags a lista para todas las entradas
        entries = [(entry[0], entry[1], entry[2], entry[3], entry[4], entry[5].split(',') if entry[5] else [])
                  for entry in entries]
            
        return None, entries
    except sqlite3.Error as e:
        return f"Error en la base de datos: {e}", None
    except Exception as e:
        return f"Error inesperado: {e}", None

def show_streaming_history(limit: int = 10, no_limit: bool = False, search: str = None, tags: List[str] = None, no_tags: bool = False, visto: int = None, platform: str = None, since: str = None) -> None:
    """Muestra el historial de streaming con formato mejorado
    
    Args:
        limit: Número máximo de entradas a mostrar (10 por defecto)
        no_limit: Si es True, muestra todas las entradas
        search: Cadena de búsqueda para filtrar por título o URL
        tags: Lista de tags para filtrar
        no_tags: Si es True, muestra solo las entradas sin tags
        visto: Filtra por número máximo de reproducciones (ej: 0 para no vistos)
        platform: Filtra por plataforma (YouTube, Instagram, etc.)
        since: Filtra por fecha mínima (formato YYYY-MM-DD)
    """
    error_code, entries = get_streaming_history(limit, no_limit, search, tags, no_tags, visto=visto, platform=platform, since=since)
    
    if error_code:
        print_error(error_code)
        return
    
    if not entries:
        print_error("No se encontraron entradas")
        return
    
    # Mostrar cabecera con el número total de entradas
    total_entries = len(entries)
    print(f"\n{colored('Total entradas encontradas:', 'yellow')} {total_entries}")
    print_separator(char='=', style='double')
    
    # Mostrar las entradas
    for entry in entries:
        print(format_history_entry(entry))
        print()  # Línea en blanco entre entradas

def add_tag(name: str, parent_name: str = None, description: str = None) -> int:
    """Añade un nuevo tag y devuelve su ID
    name: Nombre del tag (se mantendrá exactamente como se ingresa)
    parent_name: Nombre del tag padre (opcional)
    description: Descripción del tag (opcional)"""
    try:
        cursor = conn.cursor()
        
        # Insertar el tag
        cursor.execute('''
            INSERT INTO tags (name, description)
            VALUES (?, ?)
        ''', (name, description))
        tag_id = cursor.lastrowid
        
        # Si se especifica un tag padre, crear la relación
        if parent_name:
            cursor.execute('''
                SELECT id FROM tags WHERE name = ?
            ''', (parent_name,))
            parent = cursor.fetchone()
            if parent:
                cursor.execute('''
                    INSERT INTO tag_hierarchy (parent_id, child_id)
                    VALUES (?, ?)
                ''', (parent[0], tag_id))
            else:
                print(f"Error: El tag padre '{parent_name}' no existe")
                conn.rollback()
                return None
        
        conn.commit()
        return tag_id
    except sqlite3.IntegrityError:
        print(f"Error: El tag '{name}' ya existe")
        return None

def get_tag_id(name: str) -> int:
    """Obtiene el ID de un tag por su nombre
    La búsqueda es sensible a mayúsculas/minúsculas y acentos"""
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM tags WHERE name = ?', (name,))
    result = cursor.fetchone()
    
    return result[0] if result else None

def add_tag_to_url(url_id: int, tag_name: str):
    """Asocia un tag con una URL específica"""
    try:
        cursor = conn.cursor()
        
        tag_id = get_tag_id(tag_name)
        if not tag_id:
            print(f"Error: El tag '{tag_name}' no existe")
            return False
        
        cursor.execute('''
            INSERT INTO url_tags (url_id, tag_id)
            VALUES (?, ?)
        ''', (url_id, tag_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        print(f"Error: La URL ya tiene el tag '{tag_name}'")
        return False

def reproduce_with_visto(url_id: int, url: str) -> None:
    """Reproduce una URL y actualiza el contador visto
    
    Args:
        url_id: ID de la entrada en streaming_history
        url: URL a reproducir
    """
    try:
        cursor = conn.cursor()
        
        # Incrementar el contador visto
        cursor.execute('UPDATE streaming_history SET visto = visto + 1 WHERE id = ?', (url_id,))
        conn.commit()
        
        print(f"\nReproduciendo: {url}")
        
        # Verificar si mpv está instalado
        try:
            subprocess.run(['which', REPRODUCTOR_VIDEO], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            print(f"Error: {REPRODUCTOR_VIDEO} no está instalado. Instálalo con: sudo apt install {REPRODUCTOR_VIDEO}")
            return
            
        # Intentar reproducir con mpv
        try:
            # Usar subprocess.run en lugar de Popen para mejor control
            # y capturar cualquier error de salida
            resultado = subprocess.run(
                [REPRODUCTOR_VIDEO, url],
                capture_output=True,
                text=True
            )
            
            # Mostrar errores si los hay
            if resultado.returncode != 0:
                print(f"Error al reproducir con {REPRODUCTOR_VIDEO}:")
                print(f"Salida de error: {resultado.stderr}")
                print(f"Código de salida: {resultado.returncode}")
                
        except Exception as e:
            print(f"Error al ejecutar {REPRODUCTOR_VIDEO}: {e}")
            
    except Exception as e:
        print(f"Error al reproducir URL: {e}", file=sys.stderr)

def remove_tag_from_url(url_id: int, tag_name: str) -> bool:
    """Elimina la asociación entre una URL y un tag específico"""
    try:
        cursor = conn.cursor()
        
        tag_id = get_tag_id(tag_name)
        if not tag_id:
            print(f"Error: El tag '{tag_name}' no existe")
            return False
            
        # Eliminar la asociación
        cursor.execute('''
            DELETE FROM url_tags 
            WHERE url_id = ? AND tag_id = ?
        ''', (url_id, tag_id))
        
        if cursor.rowcount == 0:
            print(f"La URL con ID {url_id} no tiene el tag '{tag_name}'")
            return False
            
        conn.commit()
        print(f"Tag '{tag_name}' eliminado de la URL con ID {url_id}")
        return True
    except Exception as e:
        print(f"Error al eliminar tag de URL: {e}", file=sys.stderr)
        return False

def play_streaming_url(url_id: int) -> None:
    """Reproduce una URL de streaming por su ID (absoluto o relativo)
    Si el ID es negativo, se interpreta como un índice relativo desde el final
    """
    try:
        cursor = conn.cursor()
        
        # Si el ID es negativo, lo convertimos a un ID absoluto
        if url_id < 0:
            # Obtener la entrada que buscamos de forma relativa
            cursor.execute('SELECT url FROM streaming_history ORDER BY id DESC LIMIT 1 OFFSET ABS(?)-1', (url_id,))
            result = cursor.fetchone()
        else:
            #Obtenemos la entrada que buscamos de forma absoluta
            cursor.execute('SELECT url FROM streaming_history WHERE id = ?', (url_id,))
            result = cursor.fetchone()
        
        if not result:
            print(f"No se encontró URL con ID {url_id}", file=sys.stderr)
            return
            
        url = result[0]
        reproduce_with_visto(url_id, url)
    except Exception as e:
        print(f"Error al reproducir URL: {e}", file=sys.stderr)

def get_title_by_id(url_id: int) -> str:
    """Obtiene el título de una entrada del historial por su ID
    
    Args:
        url_id: ID de la entrada en streaming_history
        
    Returns:
        str: El título de la entrada o None si no se encuentra
    """
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT title FROM streaming_history WHERE id = ?', (url_id,))
        result = cursor.fetchone()
        
        if not result:
            print(f"No se encontró ninguna entrada con ID {url_id}", file=sys.stderr)
            return None
            
        return result[0]
    except Exception as e:
        print(f"Error al obtener el título: {e}", file=sys.stderr)
        return None


def copy_streaming_url(url_id: int) -> None:
    """Copia una URL de streaming al portapapeles con prefijo share.only/ usando su ID"""
    try:
        cursor = conn.cursor()
        
        # Si el ID es negativo, lo convertimos a un ID absoluto
        if url_id < 0:
            # Obtener la entrada que buscamos de forma relativa
            cursor.execute('SELECT url FROM streaming_history ORDER BY id DESC LIMIT 1 OFFSET ABS(?)-1', (url_id,))
            result = cursor.fetchone()
        else:
            #Obtenemos la entrada que buscamos de forma absoluta
            cursor.execute('SELECT url FROM streaming_history WHERE id = ?', (url_id,))
            result = cursor.fetchone()
        
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

def playall(args) -> None:
    """Maneja la reproducción múltiple de URLs según los filtros especificados"""
    try:
        print("Buscando URLs que coincidan con los criterios...")
        
        # Obtener el historial filtrado usando get_streaming_history
        error_code, history = get_streaming_history(
            limit=args.limit,
            no_limit=True,
            search=args.search,
            tags=args.tags,
            no_tags=False,  # No aplicar filtro de no_tags en playall
            platform=args.platform,
            since=args.since,
            visto=args.visto
        )
        
        if error_code:
            print(f"Error al obtener el historial: {error_code}", file=sys.stderr)
            return
            
        if not history:
            print("No se encontraron URLs que coincidan con los criterios de búsqueda", file=sys.stderr)
            print(f"Criterios de búsqueda:")
            print(f"- Límite: {args.limit if args.limit is None else 'sin límite'}")
            print(f"- Búsqueda: {args.search or 'ninguna'}")
            print(f"- Tags: {', '.join(args.tags) if args.tags else 'ninguno'}")
            print(f"- Plataforma: {args.platform or 'cualquiera'}")
            print(f"- Desde: {args.since or 'cualquier fecha'}")
            return
            
        print(f"\nEncontradas {len(history)} URLs que coinciden con los criterios")
        
        # Aplicar ordenamiento según las opciones
        if args.reverse:
            print("\nReproduciendo en orden inverso...")
            history.reverse()
        elif args.shuffle:
            print("\nReproduciendo en orden aleatorio...")
            import random
            random.shuffle(history)
        else:
            print("\nReproduciendo en orden normal...")
        
        # Reproducir las URLs
        print("\nIniciando reproducción...")
        for i, entry in enumerate(history, 1):
            url = entry[1]  # La URL está en el índice 1 de cada tupla
            print(f"\nReproduciendo video {i}/{len(history)}: {url}")
            reproduce_with_visto(entry[0], url)
    except Exception as e:
        print(f"Error en playall: {e}", file=sys.stderr)

def remove_streaming_url(url_id: int) -> None:
    """Elimina una URL de streaming del historial usando su ID"""
    try:
        cursor = conn.cursor()
        
        # Primero obtenemos la URL para mostrar un mensaje de confirmación
        cursor.execute('SELECT url, title FROM streaming_history WHERE id = ?', (url_id,))
        result = cursor.fetchone()
        
        if not result:
            print(f"No se encontró URL con ID {url_id}", file=sys.stderr)
            return
            
        url = result[0]
        titulo = result[1]
        print(f"¡Advertencia! Se va a eliminar la siguiente URL del historial:")
        print(f"ID: {url_id}")
        print(f"URL: {url}")
        print(f"Título: {titulo}")
        
        # Preguntar confirmación
        confirm = input("¿Estás seguro que quieres eliminar esta entrada? (s/n): ").lower()
        if confirm != 's':
            print("Operación cancelada")
            return
            
        # Eliminar la entrada
        cursor.execute('DELETE FROM streaming_history WHERE id = ?', (url_id,))
        conn.commit()
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
    print(colored("""
alterclip-cli - Interfaz de línea de comandos para alterclip
""", 'cyan', attrs=['bold']))
    
    print(colored("\nUso:", 'yellow', attrs=['bold']))
    print(colored("    alterclip-cli [comando] [opciones]", 'white'))
    
    print(colored("\nComandos disponibles:", 'yellow', attrs=['bold']))
    print_separator(style='double')
    print(colored("""
    hist [--limit N] [--no-limit] [--search [TÉRMINO]] [--tags [TAGS]] [--platform [PLATAFORMA]]
        Muestra el historial de URLs de streaming reproducidas

        Opciones de filtrado:
            --search     Filtro de búsqueda en el título o URL
            --tags       Filtro de búsqueda por tags
            --no-tags    Muestra solo las URLs sin tags asociados
            --platform   Filtra por plataforma (YouTube, Instagram, etc.)

        Opciones de visualización:
            --limit N    Número de entradas a mostrar (por defecto: 10)
            --no-limit   Muestra todo el historial sin límite
""", 'white'))
    
    print(colored("""
    play [ID]
        Reproduce una URL de streaming guardada usando su ID
        ID: Identificador numérico de la URL en el historial. Si no se especifica, se reproducirá el último video (-1)
""", 'white'))
    
    print(colored("""
    copy [ID]
        Copia una URL de streaming al portapapeles con prefijo share.only/
        ID: Identificador numérico de la URL en el historial. Si no se especifica, se copiará el último video (-1)
""", 'white'))
    
    print(colored("""
    rm [ID]
        Elimina una entrada del historial
        ID: Identificador numérico de la entrada a eliminar
""", 'white'))
    
    print(colored("""
    toggle
        Cambia el modo de alterclip entre streaming y offline
        En modo streaming: alterclip reproducirá automáticamente las URLs de streaming
        En modo offline: alterclip solo guardará las URLs para futura referencia
""", 'white'))
    
    print(colored("""
    search [TÉRMINO] [--platform [PLATAFORMA]]
        Busca URLs en el historial por título
        TÉRMINO: Término de búsqueda
        --platform: Filtra por plataforma (YouTube, Instagram, etc.)
""", 'white'))
    
    print(colored("""
    tag [acción] [opciones]
        Gestiona tags para organizar el historial
        Acciones disponibles:
            add [nombre] [--parent [padre]] [--description [descripción]]
                Añade un nuevo tag
                nombre: Nombre del tag
                padre: Nombre del tag padre (opcional)
                descripción: Descripción del tag (opcional)
            url [ID] [nombre]
                Asocia un tag con una URL
                ID: Identificador numérico de la URL
                nombre: Nombre del tag a asociar
            list
                Lista todos los tags
            hierarchy
                Muestra la jerarquía completa de tags
            rm [nombre]
                Elimina un tag
                nombre: Nombre del tag a eliminar
            update [nombre] [--new-name [nuevo_nombre]] [--description [nueva_descripción]]
                Actualiza un tag
                nombre: Nombre actual del tag
                nuevo_nombre: Nuevo nombre para el tag
                nueva_descripción: Nueva descripción del tag
            auto [ID]
                Asigna automáticamente etiquetas a una URL usando IA
                ID: Identificador numérico de la URL a etiquetar
""", 'white'))
    
    print(colored("""
    man
        Muestra esta ayuda detallada
""", 'white'))
    
    print(colored("\nInformación adicional:", 'yellow', attrs=['bold']))
    print(colored("""
- alterclip guarda automáticamente todas las URLs de streaming en su base de datos
  incluso cuando está en modo offline
- Las URLs se pueden reproducir más tarde usando el comando 'play' y su ID
- El historial muestra el título del contenido, la plataforma (YouTube, Instagram, etc.)
  y la fecha de reproducción
- La base de datos se almacena en el directorio de configuración del usuario
""", 'white'))
    
    print(colored("\nEjemplos:", 'yellow', attrs=['bold']))
    print(colored("""
    # Ver el historial completo
    alterclip-cli hist --no-limit

    # Ver solo las URLs sin tags
    alterclip-cli hist --no-tags

    # Ver solo las últimas 5 entradas
    alterclip-cli hist --limit 5

    # Ver el historial filtrado por título
    alterclip-cli hist --search "título de búsqueda"

    # Ver el historial filtrado por tags
    alterclip-cli hist --tags "tag1 tag2"

    # Reproducir una URL con ID 123
    alterclip-cli play 123

    # Reproducir el último video
    alterclip-cli play -1

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

    # Añadir un nuevo tag
    alterclip-cli tag add "Arqueología" --description "Contenido relacionado con arqueología"

    # Crear un tag hijo
    alterclip-cli tag add "Antiguas Civilizaciones" --parent "Arqueología"

    # Asociar un tag con una URL
    alterclip-cli tag url add 123 "Arqueología"

    # Eliminar una asociación entre URL y tag
    alterclip-cli tag url rm 123 "Arqueología"
    
    # Asignar automáticamente etiquetas con IA
    alterclip-cli tag auto 123

    # Reproducir múltiples URLs en secuencia
    alterclip-cli playall --tags "Filosofía" --shuffle
    alterclip-cli playall --search "música" --limit 5
    alterclip-cli playall --platform "YouTube" --reverse
    alterclip-cli playall --visto 0  # Reproduce solo URLs no vistas
    alterclip-cli playall --visto 3   # Reproduce URLs vistas 3 veces o menos

    # Buscar URLs con un tag específico
    alterclip-cli hist --tags "Arqueología"

    # Actualizar un tag
    alterclip-cli tag update "Arqueología" --new-name "Arqueología y Antigüedad"

    # Eliminar un tag
    alterclip-cli tag rm "Arqueología"

    # Ver la ayuda completa
    alterclip-cli man
    """, 'white'))

def list_tags() -> None:
    """Lista todos los tags con información adicional"""
    try:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.name, t.description, 
                   (SELECT COUNT(*) 
                    FROM url_tags ut 
                    WHERE ut.tag_id = t.id) as url_count
            FROM tags t
            ORDER BY t.name
        ''')
        
        tags = cursor.fetchall()
        
        if not tags:
            print_error("No hay tags disponibles")
            return
            
        print(colored("\nTags disponibles:", 'yellow', attrs=['bold']))
        print(colored(f"{'Nombre':<30} {'Descripción':<40} {'URLs':>8}", 'white', attrs=['bold']))
        print_separator(style='double')
        for name, description, url_count in tags:
            print(f"{colored(name, 'cyan'):<30} {description[:40]:<40} {colored(str(url_count), 'yellow'):<8}")
        print_separator(style='thick')
    except Exception as e:
        print_error(f"Error al listar tags: {e}")

def show_tag_hierarchy() -> None:
    """Muestra la jerarquía completa de tags con formato mejorado"""
    try:
        cursor = conn.cursor()
        
        def get_children(tag_id):
            cursor.execute('''
                SELECT t.name, t.id
                FROM tags t
                JOIN tag_hierarchy th ON t.id = th.child_id
                WHERE th.parent_id = ?
                ORDER BY t.name
            ''', (tag_id,))
            return cursor.fetchall()
        
        cursor.execute('''
            SELECT t.name, t.id,
                   (SELECT COUNT(*) 
                    FROM url_tags ut 
                    WHERE ut.tag_id = t.id) as url_count
            FROM tags t
            LEFT JOIN tag_hierarchy th ON t.id = th.child_id
            WHERE th.parent_id IS NULL
            ORDER BY t.name
        ''')
        root_tags = cursor.fetchall()
        
        def print_hierarchy(tag_name, tag_id, level=0):
            cursor.execute('''
                SELECT COUNT(*) 
                FROM url_tags ut 
                WHERE ut.tag_id = ?
            ''', (tag_id,))
            url_count = cursor.fetchone()[0]
            
            # Usar colores diferentes para diferentes niveles
            colors = ['cyan', 'yellow', 'green', 'magenta']
            color = colors[level % len(colors)]
            indent = '  ' * level
            print(f"{indent}{colored(f'- {tag_name}', color)} ({colored(str(url_count), 'yellow')})")
            
            children = get_children(tag_id)
            for child_name, child_id in children:
                print_hierarchy(child_name, child_id, level + 1)
        
        print(colored("\nJerarquía de tags:", 'yellow', attrs=['bold']))
        print_separator(style='double')
        for tag_name, tag_id, _ in root_tags:
            print_hierarchy(tag_name, tag_id)
        print_separator(style='double')
    except Exception as e:
        print_error(f"Error al mostrar jerarquía de tags: {e}")

def remove_tag(name: str) -> None:
    """Elimina un tag"""
    try:
        cursor = conn.cursor()
        
        # Primero obtenemos el ID del tag
        cursor.execute('SELECT id FROM tags WHERE name = ?', (name,))
        result = cursor.fetchone()
        
        if not result:
            print(f"No se encontró tag con nombre '{name}'")
            return
            
        tag_id = result[0]
        
        # Eliminar el tag
        cursor.execute('DELETE FROM tags WHERE id = ?', (tag_id,))
        conn.commit()
        print(f"Tag '{name}' eliminado")
    except Exception as e:
        print(f"Error al eliminar tag: {e}", file=sys.stderr)

def update_tag(name: str, new_name: str = None, description: str = None) -> None:
    """Actualiza un tag"""
    try:
        cursor = conn.cursor()
        
        # Primero obtenemos el ID del tag
        cursor.execute('SELECT id FROM tags WHERE name = ?', (name,))
        result = cursor.fetchone()
        
        if not result:
            print(f"No se encontró tag con nombre '{name}'")
            return
            
        tag_id = result[0]
        
        # Actualizar el tag
        if new_name:
            cursor.execute('UPDATE tags SET name = ? WHERE id = ?', (new_name, tag_id))
        if description:
            cursor.execute('UPDATE tags SET description = ? WHERE id = ?', (description, tag_id))
        conn.commit()
        print(f"Tag '{name}' actualizado")
    except Exception as e:
        print(f"Error al actualizar tag: {e}", file=sys.stderr)

def get_tag_hierarchy(tag_name: str) -> str:
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
        result = cursor.fetchone()
        if not result:
            return tag_name
            
        tag_id = result[0]
        hierarchy = []
        current_id = tag_id
        
        while True:
            cursor.execute('SELECT parent_id FROM tag_hierarchy WHERE child_id = ?', (current_id,))
            result = cursor.fetchone()
            if not result:
                break
                
            parent_id = result[0]
            cursor.execute('SELECT name FROM tags WHERE id = ?', (parent_id,))
            parent_name = cursor.fetchone()[0]
            hierarchy.append(parent_name)
            current_id = parent_id
        
        hierarchy.reverse()
        hierarchy.append(tag_name)
        
        return ' > '.join(hierarchy)
        
    except Exception as e:
        print(f"Error al obtener jerarquía del tag: {e}", file=sys.stderr)
        return tag_name


def get_hierarchy_json() -> dict:
    """Obtiene la jerarquía completa de etiquetas como un diccionario JSON anidado
    
    Returns:
        dict: Diccionario con la estructura jerárquica de etiquetas
    """
    cursor = conn.cursor()
    
    # Obtener todos los tags
    cursor.execute('SELECT id, name FROM tags')
    tags = cursor.fetchall()
    
    # Obtener todas las relaciones jerárquicas
    cursor.execute('SELECT parent_id, child_id FROM tag_hierarchy')
    relationships = cursor.fetchall()
    
    # Crear un diccionario para mapear IDs a nombres
    id_to_name = {tag_id: name for tag_id, name in tags}
    
    # Inicializar el grafo de jerarquía
    hierarchy = {}
    children = {}
    
    # Primero identificamos todos los nodos raíz (sin padres)
    all_children = set()
    parent_to_children = {}
    
    # Construir el mapeo de padres a hijos
    for parent_id, child_id in relationships:
        if parent_id not in parent_to_children:
            parent_to_children[parent_id] = []
        parent_to_children[parent_id].append(child_id)
        all_children.add(child_id)
    
    # Identificar nodos raíz (aquellos que no son hijos de nadie)
    root_nodes = [tag_id for tag_id, _ in tags if tag_id not in all_children]
    
    # Función recursiva para construir la jerarquía
    def build_hierarchy(node_id):
        node_name = id_to_name.get(node_id, str(node_id))
        if node_id not in parent_to_children:
            return {}
            
        children = {}
        for child_id in parent_to_children.get(node_id, []):
            child_name = id_to_name.get(child_id, str(child_id))
            children[child_name] = build_hierarchy(child_id)
            
        return children
    
    # Construir la jerarquía completa
    result = {}
    for root_id in root_nodes:
        root_name = id_to_name.get(root_id, str(root_id))
        result[root_name] = build_hierarchy(root_id)
    
    return result


def show_hierarchy_json() -> None:
    """Muestra por pantalla la jerarquía de etiquetas en formato JSON
    
    Muestra la estructura jerárquica completa de las etiquetas formateada
    de manera legible con indentación.
    """
    try:
        import json
        hierarchy = get_hierarchy_json()
        print(json.dumps(hierarchy, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error al mostrar la jerarquía: {e}", file=sys.stderr)

def get_suggest_IA_tags(title: str):
    """Obtiene sugerencias de etiquetas IA para un título dado.
    
    Args:
        title: Título para el que se desean sugerencias de etiquetas
        
    Returns:
        dict: Objeto JSON con la sugerencia de etiqueta o None en caso de error
    """
    hierarchy = get_hierarchy_json()
    
    prompt = f"""
Taxonomía actual (jerarquía de etiquetas):
{json.dumps(hierarchy, indent=2, ensure_ascii=False)}

Nuevo título:
"{title}"

Devuelve un objeto JSON con una de estas dos opciones:

1. Si el título encaja en una etiqueta existente, responde con:
{{
  "acción": "asignar",
  "etiqueta": "Ruta/De/Etiquetas",
  "motivo": "Breve explicación"
}}

2. Si el título necesita una nueva etiqueta, responde con:
{{
  "acción": "añadir",
  "etiqueta": "Ruta/Nueva/Etiqueta",
  "motivo": "Breve explicación"
}}
No expliques nada fuera del objeto JSON y asegúrate de que el campo "etiqueta" incluya toda la jerarquía (separada por "/").
"""
    # Cargar la API key de OpenAI desde variable de entorno
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        print("Advertencia: No se encontró la variable de entorno OPENAI_API_KEY. "
            "La funcionalidad de sugerencias de IA no estará disponible.", file=sys.stderr)
        return None
        
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print("⚠️ La respuesta no fue JSON válido:")
            print(content)
            return None
    except Exception as e:
        print(f"Error al contactar con la API: {e}")
        return None

def show_suggest_IA_tags(title: str):
    """Muestra por pantalla las sugerencias de etiquetas IA para un título.
    
    Args:
        title: Título para el que se desean mostrar sugerencias de etiquetas
        
    Returns:
        dict: Objeto JSON con la sugerencia de etiqueta o None en caso de error
    """
    suggestion = get_suggest_IA_tags(title)
    if suggestion is not None:
        print(json.dumps(suggestion, indent=2, ensure_ascii=False))
    return suggestion



def assign_IA_suggestion(url_id: int) -> bool:
    """Asigna etiquetas a una URL basándose en sugerencias de IA.
    
    Args:
        url_id: ID de la URL a la que asignar etiquetas
        
    Returns:
        bool: True si se asignó la etiqueta correctamente, False en caso contrario
    """
    try:
        # Obtener el título de la URL
        title = get_title_by_id(url_id)
        if not title:
            print(f"No se encontró la URL con ID {url_id}", file=sys.stderr)
            return False
            
        # Obtener sugerencia de la IA
        suggestion = get_suggest_IA_tags(title)
        if not suggestion:
            print("No se pudo obtener una sugerencia de la IA", file=sys.stderr)
            return False
            
        print(f"Sugerencia de IA: {suggestion}")
        
        # Verificar que la acción sea 'añadir' o 'asignar'
        if suggestion.get("acción") not in ["añadir", "asignar"]:
            print(f"AcciÃ³n no vÃ¡lida en la sugerencia de IA: {suggestion.get('acciÃ³n')}", file=sys.stderr)
            return False
            
        # Obtener la ruta de etiquetas y dividirla por '/', manteniendo los espacios en los nombres
        etiqueta_path = suggestion.get("etiqueta", "")
        if not etiqueta_path:
            print("No se especificó una etiqueta en la sugerencia", file=sys.stderr)
            return False
            
        # Dividir la ruta por '/' para obtener los niveles de jerarquía
        tags = etiqueta_path.split('/')
        if not tags:
            print("La ruta de etiquetas está vacía", file=sys.stderr)
            return False
            
        # Construir la jerarquía de etiquetas
        parent_tag = None
        for tag in tags:
            # Si el tag está vacío, lo saltamos
            if not tag.strip():
                continue
                
            tag = tag.strip()  # Limpiar espacios en blanco
            
            # Verificar si el tag ya existe
            tag_id = get_tag_id(tag)
            if not tag_id:
                # Si el tag no existe, lo creamos
                print(f"Añadiendo etiqueta faltante: {tag}")
                
                # Añadir el tag con su padre correspondiente
                add_tag(tag, parent_name=parent_tag)
                
            # Actualizar el padre para la siguiente iteración
            parent_tag = tag
            
        # La última etiqueta es la que asignaremos a la URL
        last_tag = parent_tag
            
        # Asignar la Ãºltima etiqueta a la URL
        last_tag = tags[-1]
        print(f"Asignando etiqueta '{last_tag}' a la URL ID {url_id}")
        return add_tag_to_url(url_id, last_tag)
        
    except Exception as e:
        print(f"Error al asignar etiquetas con IA: {e}", file=sys.stderr)
        return False


def get_available_tags() -> List[str]:
    """Obtiene la lista de tags disponibles en la base de datos"""
    try:
        cursor = get_db_connection().cursor()
        cursor.execute('SELECT name FROM tags ORDER BY name')
        return [row[0] for row in cursor.fetchall()]
    except:
        return []

def get_tag_parents(tag_name: str) -> List[str]:
    """Obtiene los posibles padres para un tag"""
    try:
        cursor = get_db_connection().cursor()
        cursor.execute('''
            SELECT t.name
            FROM tags t
            WHERE t.id NOT IN (
                SELECT parent_id FROM tag_hierarchy WHERE child_id = 
                (SELECT id FROM tags WHERE name = ?)
            )
            ORDER BY t.name
        ''', (tag_name,))
        return [row[0] for row in cursor.fetchall()]
    except:
        return []

def autocomplete_tags(prefix, parsed_args, **kwargs):
    """Función de autocompletado para tags"""
    return [tag for tag in get_available_tags() if tag.startswith(prefix)]

def autocomplete_tag_parents(prefix, parsed_args, **kwargs):
    """Función de autocompletado para padres de tags"""
    if parsed_args.name:
        return [tag for tag in get_tag_parents(parsed_args.name) if tag.startswith(prefix)]
    return []

def main() -> None:
    # Descripción del programa
    description = '''
    Gestiona el historial de URLs de streaming y sus tags

    Comandos principales:
      play [ID]           Reproduce una URL de streaming
      copy [ID]          Copia una URL de streaming al portapapeles
      rm [ID]            Elimina una URL del historial
      search [TÉRMINO]   Busca URLs en el historial
      toggle             Alterna entre modo normal y modo alterclip
      hist               Muestra el historial de URLs
      hist --no-tags     Muestra solo URLs sin tags
      playall            Reproduce múltiples URLs en secuencia
      tag                Gestiona tags para organizar el historial
    '''

    # Detalles adicionales sobre el comando tag
    tag_details = '''
    Comandos de tag:
      tag add [NOMBRE]     Añade un nuevo tag
      tag rm [NOMBRE]      Elimina un tag
      tag list             Lista todos los tags
      tag hierarchy        Muestra la jerarquía completa de tags
      tag update [NOMBRE]  Actualiza un tag
      tag auto [ID]        Asigna automáticamente etiquetas con IA
      tag url add [ID] [TAG]   Asocia un tag con una URL
      tag url rm [ID] [TAG]   Elimina la asociación entre una URL y un tag
    '''

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True
    )
    
    # Configurar autocompletado
    if '_ARGCOMPLETE' in os.environ:
        argcomplete.autocomplete(parser)
        sys.exit(0)
    
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comandos existentes
    parser_man = subparsers.add_parser('man', help='Muestra la ayuda completa')
    parser_play = subparsers.add_parser('play', help='Reproduce una URL de streaming')
    parser_play.add_argument('id', type=int, help='ID de la URL a reproducir')
    
    parser_copy = subparsers.add_parser('copy', help='Copia una URL de streaming al portapapeles')
    parser_copy.add_argument('id', type=int, help='ID de la URL a copiar')
    
    parser_rm = subparsers.add_parser('rm', help='Elimina una URL del historial')
    parser_rm.add_argument('id', type=int, help='ID de la URL a eliminar')
    
    parser_search = subparsers.add_parser('search', help='Busca URLs en el historial')
    parser_search.add_argument('term', help='Término de búsqueda')
    parser_search.add_argument('--visto', type=int, help='Filtrar por número máximo de reproducciones (ej: 0 para no vistos)')
    parser_search.add_argument('--platform', help='Filtrar por plataforma (YouTube, Instagram, etc.)')
    parser_search.add_argument('--since', help='Filtrar por fecha mínima (formato YYYY-MM-DD)')
    parser_search.set_defaults(command='search')
    
    parser_toggle = subparsers.add_parser('toggle', help='Alterna entre modo normal y modo alterclip')
    
    parser_hist = subparsers.add_parser('hist', help='Muestra el historial de URLs')
    parser_hist.add_argument('--limit', type=int, help='Número de entradas a mostrar')
    parser_hist.add_argument('--no-limit', action='store_true', help='Muestra todo el historial')
    parser_hist.add_argument('--search', help='Filtro de búsqueda en el título o URL')
    parser_hist.add_argument('--tags', nargs='*', help='Filtro de búsqueda por tags')
    parser_hist.add_argument('--no-tags', action='store_true', help='Muestra solo las URLs sin tags')
    parser_hist.add_argument('--visto', type=int, help='Filtrar por número máximo de reproducciones (ej: 0 para no vistos)')
    parser_hist.add_argument('--platform', help='Filtrar por plataforma (YouTube, Instagram, etc.)')
    parser_hist.add_argument('--since', help='Filtrar por fecha mínima (formato YYYY-MM-DD)')
    parser_hist.set_defaults(command='hist')

    # Comando playall
    parser_playall = subparsers.add_parser('playall', help='Reproduce múltiples URLs en secuencia')
    parser_playall.add_argument('--limit', type=int, help='Número máximo de URLs a reproducir')
    parser_playall.add_argument('--visto', type=int, help='Filtrar por número máximo de reproducciones (ej: 0 para no vistos)')
    parser_playall.add_argument('--search', help='Filtro de búsqueda en el título o URL')
    parser_playall.add_argument('--tags', nargs='*', help='Filtro de búsqueda por tags')
    parser_playall.add_argument('--reverse', action='store_true', help='Reproducir en orden inverso')
    parser_playall.add_argument('--shuffle', action='store_true', help='Reproducir en orden aleatorio')
    parser_playall.add_argument('--platform', help='Filtrar por plataforma (YouTube, Instagram, etc.)')
    parser_playall.add_argument('--since', help='Filtrar por fecha mínima (formato YYYY-MM-DD)')
    
    # Comandos para gestionar tags
    parser_tag = subparsers.add_parser('tag', help='Gestiona tags para organizar el historial')
    tag_subparsers = parser_tag.add_subparsers(dest='tag_command', help='Comandos de tag')

    # Comando tag add
    add_parser = tag_subparsers.add_parser('add', help='Añade un nuevo tag')
    add_parser.add_argument('name', help='Nombre del tag').completer = autocomplete_tags
    add_parser.add_argument('--parent', help='Tag padre').completer = autocomplete_tag_parents
    add_parser.add_argument('--description', help='Descripción del tag')

    # Comando tag rm
    rm_parser = tag_subparsers.add_parser('rm', help='Elimina un tag')
    rm_parser.add_argument('name', help='Nombre del tag a eliminar').completer = autocomplete_tags

    # Comando tag list
    list_parser = tag_subparsers.add_parser('list', help='Lista todos los tags')

    # Comando tag hierarchy
    hierarchy_parser = tag_subparsers.add_parser('hierarchy', help='Muestra la jerarquía de tags')
    
    # Comando tag json
    json_parser = tag_subparsers.add_parser('json', help='Muestra la jerarquía de tags en formato JSON')

    # Comando tag suggest
    suggest_parser = tag_subparsers.add_parser('suggest', help='Sugiere tags para un título usando IA')
    suggest_parser.add_argument('title', help='Título para el que se desean sugerencias de tags')

    # Comando tag update
    update_parser = tag_subparsers.add_parser('update', help='Actualiza un tag')
    update_parser.add_argument('name', help='Nombre actual del tag').completer = autocomplete_tags
    update_parser.add_argument('--new-name', help='Nuevo nombre para el tag')
    update_parser.add_argument('--description', help='Nueva descripción para el tag')

    # Comando tag auto (asignación automática con IA)
    auto_parser = tag_subparsers.add_parser('auto', help='Asigna automáticamente etiquetas a una URL usando IA')
    auto_parser.add_argument('url_id', type=int, help='ID de la URL a etiquetar')
    
    # Comandos para gestionar tags de URLs
    url_parser = tag_subparsers.add_parser('url', help='Gestiona tags de URLs')
    url_subparsers = url_parser.add_subparsers(dest='url_command', help='Comandos de tags de URLs')

    # Comando tag url add
    url_add_parser = url_subparsers.add_parser('add', help='Añade un tag a una URL')
    url_add_parser.add_argument('url_id', type=int, help='ID de la URL')
    url_add_parser.add_argument('tag_name', help='Nombre del tag a añadir').completer = autocomplete_tags

    # Comando tag url rm
    url_rm_parser = url_subparsers.add_parser('rm', help='Elimina un tag de una URL')
    url_rm_parser.add_argument('url_id', type=int, help='ID de la URL')
    url_rm_parser.add_argument('tag_name', help='Nombre del tag a eliminar').completer = autocomplete_tags
    
    # Manejar el caso de no argumentos
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    
    # Ejecutar el comando
    args = parser.parse_args()
    
    try:
        if args.command == 'man':
            show_help()
        elif args.command == 'play':
            play_streaming_url(args.id)
        elif args.command == 'copy':
            copy_streaming_url(args.id)
        elif args.command == 'rm':
            remove_streaming_url(args.id)
        elif args.command == 'search':
            show_streaming_history(search=args.term, visto=args.visto, platform=args.platform, since=args.since)
        elif args.command == 'toggle':
            toggle_mode()
        elif args.command == 'hist':
            show_streaming_history(
                limit=args.limit,
                no_limit=args.no_limit,
                search=args.search,
                tags=args.tags,
                no_tags=args.no_tags,
                visto=args.visto,
                platform=args.platform,
                since=args.since
            )
        elif args.command == 'playall':
            playall(args)
        elif args.command == 'tag':
            if args.tag_command == 'add':
                add_tag(args.name, args.parent, args.description)
            elif args.tag_command == 'rm':
                remove_tag(args.name)
            elif args.tag_command == 'list':
                list_tags()
            elif args.tag_command == 'hierarchy':
                show_tag_hierarchy()
            elif args.tag_command == 'json':
                show_hierarchy_json()
            elif args.tag_command == 'suggest':
                show_suggest_IA_tags(args.title)
            elif args.tag_command == 'update':
                update_tag(args.name, args.new_name, args.description)
            elif args.tag_command == 'auto':
                if assign_IA_suggestion(args.url_id):
                    print("Etiquetas asignadas correctamente")
                else:
                    print("No se pudieron asignar las etiquetas", file=sys.stderr)
            elif args.tag_command == 'url':
                if args.url_command == 'add':
                    add_tag_to_url(args.url_id, args.tag_name)
                elif args.url_command == 'rm':
                    remove_tag_from_url(args.url_id, args.tag_name)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    try:
        conn = create_connection()
        main()
    except Exception as e:
        print_error(f"Error al iniciar el programa: {e}")
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()
