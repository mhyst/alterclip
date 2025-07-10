#!/usr/bin/env python3

from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
from pathlib import Path
import unicodedata
from datetime import datetime
from platformdirs import user_log_dir
from urllib.parse import unquote  # Para decodificar URLs

app = Flask(__name__)

# Añadir la fecha actual al contexto de todas las plantillas
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

def get_db_path() -> Path:
    """Obtiene la ruta de la base de datos"""
    return Path(user_log_dir("alterclip")) / "streaming_history.db"

def get_connection():
    """Crea y devuelve una conexión a la base de datos"""
    return sqlite3.connect(get_db_path())

def remove_accents(text):
    """Elimina los acentos de una cadena de texto"""
    if not isinstance(text, str):
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    ).lower()

def get_streaming_history(limit=50, search=None, tag=None, platform=None):
    """Obtiene el historial de streaming con filtros opcionales"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row  # Para acceder a las columnas por nombre
    cursor = conn.cursor()
    
    # Primero obtenemos los IDs de las URLs que coinciden con los filtros
    query = """
    SELECT DISTINCT sh.id
    FROM streaming_history sh
    """
    
    where_conditions = []
    params = []
    
    if tag:
        # Primero obtenemos el ID del tag
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag,))
        tag_row = cursor.fetchone()
        
        if tag_row:
            tag_id = tag_row[0]
            
            # Obtenemos todos los IDs de tags hijos (incluyendo el propio tag)
            cursor.execute("""
                WITH RECURSIVE child_tags(id) AS (
                    SELECT id FROM tags WHERE id = ?
                    UNION ALL
                    SELECT th.child_id 
                    FROM tag_hierarchy th
                    JOIN child_tags ct ON th.parent_id = ct.id
                )
                SELECT id FROM child_tags
            """, (tag_id,))
            
            child_tag_ids = [row[0] for row in cursor.fetchall()]
            
            # Modificamos la consulta para buscar cualquiera de los tags hijos
            query += """
            JOIN url_tags ut ON sh.id = ut.url_id
            """
            placeholders = ','.join(['?'] * len(child_tag_ids))
            where_conditions.append(f"ut.tag_id IN ({placeholders})")
            params.extend(child_tag_ids)
        else:
            # Si el tag no existe, no devolvemos resultados
            return []
    
    if search:
        where_conditions.append("(LOWER(sh.title) LIKE ? OR LOWER(sh.url) LIKE ?)")
        search_term = f"%{search.lower()}%"
        params.extend([search_term, search_term])
    
    if platform:
        where_conditions.append("LOWER(sh.platform) = LOWER(?)")
        params.append(platform)
    
    if where_conditions:
        query += " WHERE " + " AND ".join(where_conditions)
    
    query += " ORDER BY sh.timestamp DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    url_ids = [row[0] for row in cursor.fetchall()]
    
    if not url_ids:
        return []
    
    # Ahora obtenemos los detalles completos de las URLs y sus etiquetas
    placeholders = ','.join(['?'] * len(url_ids))
    
    # Obtenemos los detalles de las URLs
    cursor.execute(f"""
        SELECT id, url, title, platform, timestamp, visto
        FROM streaming_history
        WHERE id IN ({placeholders})
        ORDER BY timestamp DESC
    """, url_ids)
    
    results = []
    for row in cursor.fetchall():
        result = dict(row)
        result['tags'] = []
        results.append(result)
    
    # Obtenemos todas las etiquetas para las URLs seleccionadas
    cursor.execute(f"""
        SELECT ut.url_id, t.id, t.name
        FROM url_tags ut
        JOIN tags t ON ut.tag_id = t.id
        WHERE ut.url_id IN ({placeholders})
    """, url_ids)
    
    # Asignamos las etiquetas a cada URL
    url_tags = {}
    for url_id, tag_id, tag_name in cursor.fetchall():
        if url_id not in url_tags:
            url_tags[url_id] = []
        url_tags[url_id].append({"id": tag_id, "name": tag_name})
    
    # Actualizamos los resultados con las etiquetas
    for result in results:
        result['tags'] = url_tags.get(result['id'], [])
    
    conn.close()
    return results

def get_tags():
    """Obtiene todos los tags únicos con su jerarquía"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Obtenemos todos los tags
    cursor.execute("""
        SELECT id, name, description 
        FROM tags
        ORDER BY name
    """)
    
    tags = []
    for row in cursor:
        tags.append({
            'id': row['id'],
            'name': row['name'],
            'description': row['description']
        })
    
    # Obtenemos las relaciones de jerarquía
    cursor.execute("""
        SELECT parent_id, child_id 
        FROM tag_hierarchy
    """)
    
    # Creamos un diccionario para mapear hijos a padres
    child_to_parent = {}
    for parent_id, child_id in cursor:
        child_to_parent[child_id] = parent_id
    
    # Construimos la jerarquía
    tag_by_id = {tag['id']: tag for tag in tags}
    for tag in tags:
        tag_id = tag['id']
        if tag_id in child_to_parent:
            parent_id = child_to_parent[tag_id]
            if parent_id in tag_by_id:
                parent_name = tag_by_id[parent_id]['name']
                tag['full_path'] = f"{parent_name} > {tag['name']}"
            else:
                tag['full_path'] = tag['name']
        else:
            tag['full_path'] = tag['name']
    
    # Ordenamos por el path completo
    tags.sort(key=lambda x: x['full_path'])
    
    conn.close()
    return tags

def get_platforms():
    """Obtiene todas las plataformas únicas"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT platform FROM streaming_history WHERE platform IS NOT NULL ORDER BY platform")
    platforms = [row[0] for row in cursor.fetchall()]
    conn.close()
    return platforms

@app.route('/')
def index():
    """Página principal que muestra el historial"""
    search = request.args.get('search', '')
    tag = request.args.get('tag')
    platform = request.args.get('platform')
    
    history = get_streaming_history(search=search, tag=tag, platform=platform)
    tags = get_tags()
    platforms = get_platforms()
    
    # Obtener todos los tags jerárquicamente
    def get_hierarchical_tags():
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener todos los tags
        cursor.execute("""
            SELECT id, name, COALESCE(description, '') as description 
            FROM tags 
            ORDER BY name
        """)
        all_tags = {row['id']: dict(row) for row in cursor.fetchall()}
        
        # Obtener las relaciones de jerarquía
        cursor.execute("""
            SELECT parent_id, child_id 
            FROM tag_hierarchy 
            ORDER BY parent_id, child_id
        """)
        
        # Construir la jerarquía
        hierarchy = {}
        for parent_id, child_id in cursor.fetchall():
            if parent_id not in hierarchy:
                hierarchy[parent_id] = []
            hierarchy[parent_id].append(child_id)
        
        # Encontrar los tags raíz (sin padres)
        all_child_ids = {child_id for children in hierarchy.values() for child_id in children}
        root_tag_ids = [tag_id for tag_id in all_tags if tag_id not in all_child_ids]
        
        # Construir la lista jerárquica
        def build_hierarchical_list(tag_id, level=0):
            tag = all_tags[tag_id].copy()
            tag['level'] = level
            result = [tag]
            
            if tag_id in hierarchy:
                for child_id in hierarchy[tag_id]:
                    result.extend(build_hierarchical_list(child_id, level + 1))
            
            return result
        
        # Construir la lista completa
        hierarchical_tags = []
        for root_id in root_tag_ids:
            hierarchical_tags.extend(build_hierarchical_list(root_id))
        
        conn.close()
        return hierarchical_tags
    
    all_tags = get_hierarchical_tags()
    
    return render_template('index.html', 
                         history=history, 
                         tags=tags,
                         all_tags=all_tags,
                         platforms=platforms,
                         current_search=search,
                         current_tag=tag,
                         current_platform=platform)

@app.route('/tag/<tag_name>')
def tag_view(tag_name):
    """Vista para mostrar contenido de un tag específico"""
    history = get_streaming_history(tag=tag_name)
    tags = get_tags()
    platforms = get_platforms()
    
    return render_template('index.html', 
                         history=history, 
                         tags=tags,
                         platforms=platforms,
                         current_tag=tag_name)

@app.route('/api/history')
def api_history():
    """API para obtener el historial en formato JSON"""
    search = request.args.get('search')
    tag = request.args.get('tag')
    platform = request.args.get('platform')
    limit = int(request.args.get('limit', 50))
    
    history = get_streaming_history(limit=limit, search=search, tag=tag, platform=platform)
    return jsonify(history)

@app.route('/api/tags')
def api_tags():
    """API para obtener todos los tags"""
    tags = get_tags()
    return jsonify(tags)

@app.route('/api/mark_as_viewed/<int:url_id>', methods=['POST'])
def mark_as_viewed(url_id):
    """Marca una URL como vista"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Incrementar el contador de visto
        cursor.execute("""
            UPDATE streaming_history 
            SET visto = COALESCE(visto, 0) + 1 
            WHERE id = ?
        """, (url_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": "Marcado como visto"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tag_hierarchy')
def api_tag_hierarchy():
    """API para obtener la jerarquía de tags en formato anidado"""
    def build_hierarchy():
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener todos los tags
        cursor.execute("""
            SELECT id, name, COALESCE(description, '') as description 
            FROM tags
        """)
        
        # Crear un diccionario con todos los tags
        tag_map = {}
        for row in cursor:
            tag_map[row['id']] = {
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'children': []
            }
        
        # Obtener las relaciones de jerarquía
        cursor.execute("""
            SELECT parent_id, child_id 
            FROM tag_hierarchy
        """)
        
        # Construir la jerarquía
        child_to_parent = {}
        for parent_id, child_id in cursor:
            child_to_parent[child_id] = parent_id
            
            # Si el padre existe, añadir el hijo a sus hijos
            if parent_id in tag_map and child_id in tag_map:
                tag_map[parent_id]['children'].append(tag_map[child_id])
        
        # Identificar los tags raíz (aquellos que no son hijos de nadie)
        root_tags = []
        for tag_id, tag in tag_map.items():
            if tag_id not in child_to_parent:
                root_tags.append(tag)
        
        # Función para calcular el nivel y ruta completa de cada tag
        def process_tag(tag, level=0, parent_path=None):
            path = f"{parent_path} > {tag['name']}" if parent_path else tag['name']
            tag['level'] = level
            tag['full_path'] = path
            
            # Procesar recursivamente los hijos
            for child in tag['children']:
                process_tag(child, level + 1, path)
        
        # Procesar todos los tags raíz
        for tag in root_tags:
            process_tag(tag)
        
        conn.close()
        return root_tags
    
    try:
        hierarchy = build_hierarchy()
        return jsonify(hierarchy)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete/<int:url_id>', methods=['DELETE'])
def delete_url(url_id):
    """Elimina una URL del historial"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Eliminar las relaciones de etiquetas primero
        cursor.execute("DELETE FROM url_tags WHERE url_id = ?", (url_id,))
        
        # Luego eliminar la URL del historial
        cursor.execute("DELETE FROM streaming_history WHERE id = ?", (url_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": "URL eliminada correctamente"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/manage-tags')
def manage_tags():
    """Página de gestión de etiquetas"""
    return render_template('manage_tags.html')

@app.route('/api/tags', methods=['POST'])
def create_tag():
    """Crea una nueva etiqueta"""
    try:
        data = request.get_json()
        name = data.get('name')
        parent_id = data.get('parent_id')
        
        if not name:
            return jsonify({"status": "error", "message": "El nombre de la etiqueta es obligatorio"}), 400
            
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar si la etiqueta ya existe
        cursor.execute("SELECT id FROM tags WHERE name = ?", (name,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"status": "error", "message": "Ya existe una etiqueta con ese nombre"}), 400
        
        # Insertar la nueva etiqueta
        cursor.execute("INSERT INTO tags (name, description) VALUES (?, ?)", 
                     (name, data.get('description', '')))
        tag_id = cursor.lastrowid
        
        # Si tiene padre, crear la relación de jerarquía
        if parent_id:
            cursor.execute("INSERT INTO tag_hierarchy (parent_id, child_id) VALUES (?, ?)", 
                         (parent_id, tag_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success", 
            "message": "Etiqueta creada correctamente",
            "tag": {"id": tag_id, "name": name}
        }), 201
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tags/<int:tag_id>', methods=['DELETE'])
def delete_tag(tag_id):
    """Elimina una etiqueta"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar si la etiqueta tiene hijos
        cursor.execute("SELECT COUNT(*) FROM tag_hierarchy WHERE parent_id = ?", (tag_id,))
        if cursor.fetchone()[0] > 0:
            return jsonify({
                "status": "error", 
                "message": "No se puede eliminar una etiqueta que tiene etiquetas hijas"
            }), 400
        
        # Verificar si la etiqueta está en uso
        cursor.execute("SELECT COUNT(*) FROM url_tags WHERE tag_id = ?", (tag_id,))
        if cursor.fetchone()[0] > 0:
            return jsonify({
                "status": "error", 
                "message": "No se puede eliminar una etiqueta que está en uso"
            }), 400
        
        # Eliminar relaciones de jerarquía
        cursor.execute("DELETE FROM tag_hierarchy WHERE child_id = ?", (tag_id,))
        
        # Eliminar la etiqueta
        cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": "Etiqueta eliminada correctamente"}), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/urls/<int:url_id>/tags', methods=['POST'])
def add_tag_to_url(url_id):
    """Añade una etiqueta existente a una URL"""
    try:
        data = request.get_json()
        tag_id = data.get('tag_id')
        
        if not tag_id:
            return jsonify({"status": "error", "message": "Se requiere el ID de la etiqueta"}), 400
            
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar si la URL existe
        cursor.execute("SELECT id FROM streaming_history WHERE id = ?", (url_id,))
        if not cursor.fetchone():
            return jsonify({"status": "error", "message": "URL no encontrada"}), 404
            
        # Verificar si la etiqueta existe
        cursor.execute("SELECT id FROM tags WHERE id = ?", (tag_id,))
        if not cursor.fetchone():
            return jsonify({"status": "error", "message": "Etiqueta no encontrada"}), 404
            
        # Verificar si la etiqueta ya está asignada
        cursor.execute("SELECT 1 FROM url_tags WHERE url_id = ? AND tag_id = ?", (url_id, tag_id))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "La etiqueta ya está asignada a esta URL"}), 400
            
        # Asignar la etiqueta a la URL
        cursor.execute("INSERT INTO url_tags (url_id, tag_id) VALUES (?, ?)", (url_id, tag_id))
        
        # Obtener información de la etiqueta para la respuesta
        cursor.execute("SELECT name FROM tags WHERE id = ?", (tag_id,))
        tag_name = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success", 
            "message": "Etiqueta asignada correctamente",
            "tag": {"id": tag_id, "name": tag_name}
        }), 201
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/mark_as_unseen/<int:url_id>', methods=['POST'])
def mark_as_unseen(url_id):
    """Marca una URL como no vista"""
    try:
        print(f"Intentando marcar URL {url_id} como no vista")
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar si la URL existe primero
        cursor.execute("SELECT id FROM streaming_history WHERE id = ?", (url_id,))
        if not cursor.fetchone():
            conn.close()
            print(f"Error: URL con ID {url_id} no encontrada")
            return jsonify({"status": "error", "message": "URL no encontrada"}), 404
        
        # Establecer el contador de visto a 0
        cursor.execute("""
            UPDATE streaming_history 
            SET visto = 0 
            WHERE id = ?
        """, (url_id,))
        
        # Verificar si se actualizó alguna fila
        if cursor.rowcount == 0:
            conn.close()
            print(f"Error: No se pudo actualizar la URL con ID {url_id}")
            return jsonify({"status": "error", "message": "No se pudo actualizar la URL"}), 500
        
        conn.commit()
        conn.close()
        
        print(f"URL {url_id} marcada como no vista correctamente")
        return jsonify({"status": "success", "message": "Marcado como no visto"}), 200
    except Exception as e:
        error_msg = f"Error al marcar como no visto: {str(e)}"
        print(error_msg)
        return jsonify({"status": "error", "message": error_msg}), 500

@app.route('/api/tags')
def get_tags_by_name():
    """Obtiene etiquetas por nombre (búsqueda)"""
    try:
        # Obtener y decodificar el parámetro 'name' de la URL
        name_encoded = request.args.get('name', '').strip()
        if not name_encoded:
            return jsonify({"status": "error", "message": "Se requiere el parámetro 'name'"}), 400
            
        # Decodificar el nombre de la etiqueta (maneja espacios y caracteres especiales)
        name = unquote(name_encoded)
        
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener todas las etiquetas para depuración
        cursor.execute("SELECT id, name FROM tags ORDER BY name")
        all_tags = [dict(row) for row in cursor.fetchall()]
        
        # Primero intentar búsqueda exacta
        cursor.execute("""
            SELECT id, name, description 
            FROM tags 
            WHERE LOWER(name) = LOWER(?)
            ORDER BY name
        """, (name,))
        
        exact_matches = [dict(row) for row in cursor.fetchall()]
        
        # Si no se encontraron resultados, intentar con búsqueda más flexible
        if not exact_matches:
            cursor.execute("""
                SELECT id, name, description 
                FROM tags 
                WHERE LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    name, 'á', 'a'), 'é', 'e'), 'í', 'i'), 'ó', 'o'), 'ú', 'u')) 
                LIKE LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    ?, 'á', 'a'), 'é', 'e'), 'í', 'i'), 'ó', 'o'), 'ú', 'u'))
                ORDER BY name
            """, (f"%{name}%",))
            
            flexible_matches = [dict(row) for row in cursor.fetchall()]
        else:
            flexible_matches = []
        
        conn.close()
        
        # Combinar resultados (primero coincidencias exactas, luego flexibles)
        tags = exact_matches + flexible_matches
        
        # Depuración adicional
        debug_info = {
            "received_name": name_encoded,
            "decoded_name": name,
            "all_tags_in_db": all_tags,
            "exact_matches_count": len(exact_matches),
            "flexible_matches_count": len(flexible_matches),
            "exact_query": f"SELECT id, name FROM tags WHERE LOWER(name) = LOWER('{name}')",
            "flexible_query": f"SELECT id, name FROM tags WHERE LOWER(REPLACE(...)) LIKE LOWER('%{name}%')"
        }
        
        return jsonify({
            "status": "success",
            "tags": tags,
            "debug": debug_info
        }), 200
        
    except Exception as e:
        print(f"Error al buscar etiquetas: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/urls/<int:url_id>/tags/<int:tag_id>', methods=['DELETE'])
def remove_tag_from_url(url_id, tag_id):
    """Elimina una etiqueta de una URL"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar si la relación existe
        cursor.execute("""
            SELECT 1 FROM url_tags 
            WHERE url_id = ? AND tag_id = ?
        """, (url_id, tag_id))
        
        if not cursor.fetchone():
            return jsonify({"status": "error", "message": "La etiqueta no está asignada a esta URL"}), 404
        
        # Eliminar la relación
        cursor.execute("""
            DELETE FROM url_tags 
            WHERE url_id = ? AND tag_id = ?
        """, (url_id, tag_id))
        
        # Obtener el nombre de la etiqueta para la respuesta
        cursor.execute("SELECT name FROM tags WHERE id = ?", (tag_id,))
        tag_name = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success", 
            "message": "Etiqueta eliminada correctamente",
            "tag": {"id": tag_id, "name": tag_name}
        }), 200
        
    except Exception as e:
        print(f"Error al eliminar etiqueta: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
