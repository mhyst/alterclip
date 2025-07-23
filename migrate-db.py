#!/usr/bin/env python
#
# Ejecutar si tu base de datos necesita añadir la columna visto en
# la tabla streaming_history.
#
# Solo se necesita ejecutar una vez
#
#
import sqlite3
from pathlib import Path
from platformdirs import user_log_dir

def get_db_path() -> Path:
    """Obtiene la ruta de la base de datos"""
    return Path(user_log_dir("alterclip")) / "streaming_history.db"

conn = sqlite3.connect(get_db_path())

#Vamos a realizar migración para añadir la nueva columna "visto" a streaming_history
cursor = conn.cursor()

# Comprobar si ya existe la columna 'visto'
cursor.execute("PRAGMA table_info(streaming_history);")
columnas = [fila[1] for fila in cursor.fetchall()]

if 'visto' not in columnas:
    cursor.execute("ALTER TABLE streaming_history ADD COLUMN visto INTEGER DEFAULT 0;")
    print("Tabla modificada!")
else:
    print("La tabla ya trae la columna visto. No es necesario hacer nada")

conn.commit()
