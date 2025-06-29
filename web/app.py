#!/usr/bin/env python3

from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
from pathlib import Path
import unicodedata
from datetime import datetime

app = Flask(__name__)

# Añadir la fecha actual al contexto de todas las plantillas
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

def get_db_path() -> Path:
    """Obtiene la ruta de la base de datos"""
    # Ruta relativa al directorio de la aplicación web
    db_path = Path(__file__).parent / "data" / "streaming_history.db"
    # Crear el directorio si no existe
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path

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
        query += """
        JOIN url_tags ut ON sh.id = ut.url_id
        JOIN tags t ON ut.tag_id = t.id
        """
        where_conditions.append("t.name = ?")
        params.append(tag)
    
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
        SELECT ut.url_id, t.name
        FROM url_tags ut
        JOIN tags t ON ut.tag_id = t.id
        WHERE ut.url_id IN ({placeholders})
    """, url_ids)
    
    # Asignamos las etiquetas a cada URL
    url_tags = {}
    for url_id, tag_name in cursor.fetchall():
        if url_id not in url_tags:
            url_tags[url_id] = []
        url_tags[url_id].append(tag_name)
    
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
    
    return render_template('index.html', 
                         history=history, 
                         tags=tags,
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

@app.route('/api/tag_hierarchy')
def api_tag_hierarchy():
    """API para obtener la jerarquía de tags en formato anidado"""
    def build_hierarchy():
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener todos los tags
        cursor.execute("""
            SELECT id, name, description 
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
