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
import argcomplete

def get_db_path() -> Path:
    """Obtiene la ruta de la base de datos"""
    return Path(user_log_dir("alterclip")) / "streaming_history.db"

# Crear la conexión a la base de datos
def create_connection() -> sqlite3.Connection:
    """Crea una conexión a la base de datos"""
    conn = sqlite3.connect(get_db_path())
    return conn

# Función para obtener la conexión global
conn = create_connection()

def remove_accents(input_str: str) -> str:
    """Elimina los acentos de una cadena de texto"""
    replacements = {
        'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a', 'å': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'ô': 'o', 'ö': 'o', 'õ': 'o', 'ø': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ñ': 'n', 'ç': 'c',
        'Á': 'A', 'À': 'A', 'Â': 'A', 'Ä': 'A', 'Ã': 'A', 'Å': 'A',
        'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
        'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
        'Ó': 'O', 'Ò': 'O', 'Ô': 'O', 'Ö': 'O', 'Õ': 'O', 'Ø': 'O',
        'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
        'Ñ': 'N', 'Ç': 'C'
    }
    
    # Primero convertimos a minúsculas
    input_str = input_str.lower()
    
    # Luego reemplazamos los caracteres
    for original, replacement in replacements.items():
        input_str = input_str.replace(original, replacement)
    
    return input_str

def format_history_entry(entry: Tuple[int, str, str, str, str, List[str]]) -> str:
    """Formatea una entrada del historial para mostrar en la salida"""
    id, url, title, platform, timestamp, tags = entry
    
    # Convertir cada tag a su jerarquía completa
    formatted_tags = []
    for tag in tags:
        # Obtener la jerarquía completa del tag
        hierarchy = get_tag_hierarchy(tag)
        formatted_tags.append(hierarchy)
    
    # Unir las jerarquías con comas
    tags_str = ', '.join(formatted_tags)
    
    return f"""
ID: {id}
URL: {url}
Título: {title}
Plataforma: {platform}
Fecha: {timestamp}
Tags: {tags_str}
{'-' * 80}"""

def get_streaming_history(limit: int = 10, no_limit: bool = False, search: str = None, tags: List[str] = None) -> None:
    """Obtiene el historial de URLs de streaming con sus tags asociados
    Si no_limit es True, muestra todo el historial
    Si no_limit es False y limit es None, muestra 10 entradas por defecto
    Si search no es None, muestra solo las entradas que contengan la cadena de búsqueda en el título o URL
    Si tags no es None, muestra solo las entradas que tengan al menos uno de los tags especificados
    También muestra URLs relacionadas con tags hijos y padres de los especificados"""
    try:
        cursor = conn.cursor()
        
        # Primero obtenemos todas las URLs
        cursor.execute('''
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
            GROUP BY sh.id, sh.url, sh.title, sh.platform, sh.timestamp
            ORDER BY sh.timestamp DESC
        ''')
        
        all_entries = cursor.fetchall()
        
        if not all_entries:
            print("No hay historial disponible")
            return
            
        # Si hay búsqueda, filtramos los resultados
        if search:
            search_term = remove_accents(search.lower())
            search_term_upper = search.upper()
            
            results = []
            for entry in all_entries:
                url_id = entry[0]
                url = entry[1]
                title = entry[2]
                platform = entry[3]
                timestamp = entry[4]
                tags = entry[5]
                
                # Normalizar los campos para búsqueda
                title_lower = title.lower() if title else ""
                title_upper = title.upper() if title else ""
                title_no_accents = remove_accents(title) if title else ""
                url_lower = url.lower()
                url_upper = url.upper()
                url_no_accents = remove_accents(url)
                
                # Verificar si el término de búsqueda está en el título o URL
                if (search_term in title_lower or
                    search_term_upper in title_upper or
                    search_term in title_no_accents or
                    search_term in url_lower or
                    search_term_upper in url_upper or
                    search_term in url_no_accents):
                    # Convertir tags a lista
                    tags_list = tags.split(',') if tags else []
                    results.append((url_id, url, title, platform, timestamp, tags_list))
            
            if not results:
                print(f"No se encontraron resultados para '{search}'")
                return
                
            entries = results
        else:
            # Convertir tags a lista para todas las entradas
            entries = [(entry[0], entry[1], entry[2], entry[3], entry[4], entry[5].split(',') if entry[5] else [])
                      for entry in all_entries]
            
        # Si hay tags, filtramos por tags
        if tags:
            tag_ids = []
            for tag in tags:
                tag_id = get_tag_id(tag)
                if tag_id:
                    tag_ids.append(tag_id)
                    
                    # Obtener IDs de los tags hijos
                    cursor.execute('''
                        SELECT child_id 
                        FROM tag_hierarchy 
                        WHERE parent_id = ?
                    ''', (tag_id,))
                    child_ids = cursor.fetchall()
                    tag_ids.extend([child[0] for child in child_ids])
                    
                    # Obtener IDs de los tags padres
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
                # Convertir la lista de IDs a una cadena SQL
                tag_ids_str = ','.join('?' for _ in tag_ids)
                cursor.execute(f'''
                    SELECT DISTINCT sh.id
                    FROM streaming_history sh
                    JOIN url_tags ut ON sh.id = ut.url_id
                    WHERE ut.tag_id IN ({tag_ids_str})
                ''', tag_ids)
                
                tag_entries = cursor.fetchall()
                tag_entry_ids = {row[0] for row in tag_entries}
                
                entries = [entry for entry in entries if entry[0] in tag_entry_ids]
                
                if not entries:
                    print(f"No se encontraron resultados con los tags especificados")
                    return
        
        # Limitar el número de resultados si no se ha pedido todo el historial
        if not no_limit:
            entries = entries[:limit if limit else 10]
        
        print(f"\nHistorial de URLs de streaming ({len(entries)} resultados):")
        print("-" * 80)
        for entry in entries:
            print(format_history_entry(entry))
        
    except Exception as e:
        print(f"Error al obtener el historial: {e}")

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

def play_streaming_url(url_id: int) -> None:
    """Reproduce una URL de streaming por su ID (absoluto o relativo)
    Si el ID es negativo, se interpreta como un índice relativo desde el final
    (ejemplo: -1 = último, -2 = penúltimo, etc.)"""
    try:
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
                print(f"No se puede copiar una entrada más allá del inicio del historial", file=sys.stderr)
                return
            url_id = abs_id
        
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

def remove_streaming_url(url_id: int) -> None:
    """Elimina una URL de streaming del historial usando su ID"""
    try:
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
            get-hierarchy [nombre]
                Obtiene la jerarquía de un tag
                nombre: Nombre del tag

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

    # Añadir un nuevo tag
    alterclip-cli tag add "nombre del tag"

    # Asociar un tag con una URL
    alterclip-cli tag url 123 "nombre del tag"

    # Lista todos los tags
    alterclip-cli tag list

    # Muestra la jerarquía completa de tags
    alterclip-cli tag hierarchy

    # Elimina un tag
    alterclip-cli tag rm "nombre del tag"

    # Actualiza un tag
    alterclip-cli tag update "nombre del tag" --new-name "nuevo nombre del tag"

    # Obtiene la jerarquía de un tag
    alterclip-cli tag get-hierarchy "nombre del tag"
""")

def search_streaming_history(search_term: str) -> None:
    """Busca URLs de streaming en el historial que contengan la cadena de búsqueda en el título"""
    try:
        cursor = conn.cursor()
        
        # Normalizamos el término de búsqueda en Python
        search_term_lower = search_term.lower()
        search_term_upper = search_term.upper()
        search_term_no_accents = remove_accents(search_term)
        
        # Primero obtenemos todas las URLs
        cursor.execute('''
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
            GROUP BY sh.id
            ORDER BY sh.timestamp DESC
        ''')
        
        # Filtramos los resultados en Python
        results = []
        for row in cursor.fetchall():
            title = row[2].lower()
            title_no_accents = remove_accents(title)
            
            if (search_term_lower in title or
                search_term_upper in title or
                search_term_no_accents in title_no_accents):
                results.append(row)
        
        if not results:
            print(f"No se encontraron resultados para '{search_term}'")
            return
        
        print(f"Resultados para '{search_term}' ({len(results)} resultados): ")
        print("-" * 80)
        
        for row in results:
            # print(format_history_entry(row))
            url_id = row[0]
            url = row[1]
            title = row[2]
            platform = row[3]
            timestamp = row[4]
            tags = row[5]
            
            print(f"ID: {url_id}")
            print(f"URL: {url}")
            print(f"Título: {title}")
            print(f"Plataforma: {platform}")
            print(f"Fecha: {timestamp}")
            print(f"Tags: {', '.join(tags.split(',') if tags else [])}")
            print("-" * 80)
    except Exception as e:
        print(f"Error al buscar en el historial: {e}", file=sys.stderr)

def list_tags() -> None:
    """Lista todos los tags"""
    try:
        cursor = conn.cursor()
        
        cursor.execute('SELECT name FROM tags')
        
        tags = [row[0] for row in cursor.fetchall()]
        
        if not tags:
            print("No hay tags disponibles")
            return
            
        print("\nTags disponibles:")
        print("-" * 80)
        for tag in tags:
            print(tag)
        print("-" * 80)
    except Exception as e:
        print(f"Error al listar tags: {e}", file=sys.stderr)

def show_tag_hierarchy() -> None:
    """Muestra la jerarquía completa de tags con el número de URLs asociadas"""
    try:
        cursor = conn.cursor()
        
        # Función auxiliar para obtener los hijos de un tag
        def get_children(tag_id):
            cursor.execute('''
                SELECT t.name, t.id
                FROM tags t
                JOIN tag_hierarchy th ON t.id = th.child_id
                WHERE th.parent_id = ?
                ORDER BY t.name
            ''', (tag_id,))
            return cursor.fetchall()
        
        # Obtener todos los tags raíz
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
        
        # Función auxiliar para mostrar la jerarquía con espaciado
        def print_hierarchy(tag_name, tag_id, level=0):
            # Obtener el número de URLs asociadas
            cursor.execute('''
                SELECT COUNT(*) 
                FROM url_tags ut 
                WHERE ut.tag_id = ?
            ''', (tag_id,))
            url_count = cursor.fetchone()[0]
            
            print(f"{'  ' * level}- {tag_name} ({url_count})")
            children = get_children(tag_id)
            for child_name, child_id in children:
                print_hierarchy(child_name, child_id, level + 1)
        
        # Mostrar la jerarquía
        for tag_name, tag_id, _ in root_tags:
            print_hierarchy(tag_name, tag_id)
        
        print("-" * 80)
    except Exception as e:
        print(f"Error al mostrar jerarquía de tags: {e}", file=sys.stderr)

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

def get_available_tags() -> List[str]:
    """Obtiene la lista de tags disponibles en la base de datos"""
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM tags ORDER BY name')
        return [row[0] for row in cursor.fetchall()]
    except:
        return []

def get_tag_parents(tag_name: str) -> List[str]:
    """Obtiene los posibles padres para un tag"""
    try:
        cursor = conn.cursor()
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
      tag                Gestiona tags para organizar el historial
    '''

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True
    )
    
    # Configurar autocompletado
    argcomplete.autocomplete(parser)
    
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
    
    parser_toggle = subparsers.add_parser('toggle', help='Alterna entre modo normal y modo alterclip')
    
    parser_hist = subparsers.add_parser('hist', help='Muestra el historial de URLs')
    parser_hist.add_argument('--limit', type=int, help='Número de entradas a mostrar')
    parser_hist.add_argument('--no-limit', action='store_true', help='Muestra todo el historial')
    parser_hist.add_argument('--search', help='Filtro de búsqueda en el título o URL')
    parser_hist.add_argument('--tags', nargs='*', help='Filtro de búsqueda por tags')
    
    # Comandos para gestionar tags
    parser_tag = subparsers.add_parser('tag', help='Gestiona tags para organizar el historial')
    tag_subparsers = parser_tag.add_subparsers(dest='action', help='Acciones disponibles para tags')
    
    # Comando para crear un tag
    parser_tag_add = tag_subparsers.add_parser('add', help='Añade un nuevo tag')
    parser_tag_add.add_argument('name', help='Nombre del tag').completer = autocomplete_tags
    parser_tag_add.add_argument('--parent', help='Nombre del tag padre (opcional)').completer = autocomplete_tag_parents
    parser_tag_add.add_argument('--description', help='Descripción del tag (opcional)')
    
    # Comando para asociar un tag con una URL
    parser_tag_url = tag_subparsers.add_parser('url', help='Asocia un tag con una URL')
    parser_tag_url.add_argument('url_id', type=int, help='ID de la URL')
    parser_tag_url.add_argument('tag_name', help='Nombre del tag a asociar').completer = autocomplete_tags
    
    # Comando para listar tags
    parser_tag_list = tag_subparsers.add_parser('list', help='Lista todos los tags')
    
    # Comando para mostrar jerarquía de tags
    parser_tag_hierarchy = tag_subparsers.add_parser('hierarchy', help='Muestra la jerarquía completa de tags')
    
    # Comando para eliminar un tag
    parser_tag_rm = tag_subparsers.add_parser('rm', help='Elimina un tag')
    parser_tag_rm.add_argument('name', help='Nombre del tag a eliminar').completer = autocomplete_tags
    
    # Comando para actualizar un tag
    parser_tag_update = tag_subparsers.add_parser('update', help='Actualiza un tag')
    parser_tag_update.add_argument('name', help='Nombre actual del tag').completer = autocomplete_tags
    parser_tag_update.add_argument('--new-name', help='Nuevo nombre para el tag')
    parser_tag_update.add_argument('--description', help='Nueva descripción del tag')
    
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
            search_streaming_history(args.term)
        elif args.command == 'toggle':
            toggle_mode()
        elif args.command == 'hist':
            get_streaming_history(
                limit=args.limit,
                no_limit=args.no_limit,
                search=args.search,
                tags=args.tags
            )
        elif args.command == 'tag':
            if args.action == 'add':
                add_tag(args.name, args.parent, args.description)
            elif args.action == 'url':
                add_tag_to_url(args.url_id, args.tag_name)
            elif args.action == 'list':
                list_tags()
            elif args.action == 'hierarchy':
                show_tag_hierarchy()
            elif args.action == 'rm':
                remove_tag(args.name)
            elif args.action == 'update':
                update_tag(args.name, args.new_name, args.description)
            elif args.action == 'get-hierarchy':
                print(get_tag_hierarchy(args.name))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
    conn.close()
