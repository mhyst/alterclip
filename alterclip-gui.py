#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from platformdirs import user_log_dir
import sqlite3

class AlterclipGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Alterclip - Gestión de Tags")
        self.root.geometry("1000x600")
        
        # Variables
        self.selected_url_id = None
        self.selected_tags = set()
        
        # Configurar el grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Configurar el grid principal
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Frame para la lista de URLs
        self.urls_frame = ttk.LabelFrame(root, text="Historial de URLs", padding="5")
        self.urls_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Configurar el grid del frame de URLs
        self.urls_frame.grid_columnconfigure(0, weight=1)
        self.urls_frame.grid_rowconfigure(0, weight=1)
        
        # Treeview para las URLs
        self.urls_list = ttk.Treeview(self.urls_frame, columns=('ID', 'URL', 'Título', 'Plataforma', 'Tags'), show='headings')
        self.urls_list.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configurar las columnas
        self.urls_list.column('ID', width=50)
        self.urls_list.column('URL', width=300)
        self.urls_list.column('Título', width=200)
        self.urls_list.column('Plataforma', width=100)
        self.urls_list.column('Tags', width=200)
        
        # Configurar las cabeceras
        self.urls_list.heading('ID', text='ID')
        self.urls_list.heading('URL', text='URL')
        self.urls_list.heading('Título', text='Título')
        self.urls_list.heading('Plataforma', text='Plataforma')
        self.urls_list.heading('Tags', text='Tags')
        
        # Scrollbar para las URLs
        self.urls_scroll = ttk.Scrollbar(self.urls_frame, orient="vertical", command=self.urls_list.yview)
        self.urls_scroll.grid(row=0, column=1, sticky="ns")
        self.urls_list.configure(yscrollcommand=self.urls_scroll.set)
        
        # Frame para la lista de tags
        self.tags_frame = ttk.LabelFrame(root, text="Tags", padding="5")
        self.tags_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        
        # Configurar el grid del frame de tags
        self.tags_frame.grid_columnconfigure(0, weight=1)
        self.tags_frame.grid_rowconfigure(0, weight=1)
        
        # Treeview para los tags
        self.tags_list = ttk.Treeview(self.tags_frame, columns=('Tag',), show='headings')
        self.tags_list.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configurar la columna
        self.tags_list.column('Tag', width=300)
        
        # Configurar la cabecera
        self.tags_list.heading('Tag', text='Tag')
        
        # Scrollbar para los tags
        self.tags_scroll = ttk.Scrollbar(self.tags_frame, orient="vertical", command=self.tags_list.yview)
        self.tags_scroll.grid(row=0, column=1, sticky="ns")
        self.tags_list.configure(yscrollcommand=self.tags_scroll.set)
        
        # Configurar estilos para el Treeview de tags
        style = ttk.Style()
        style.configure('Treeview', rowheight=25)  # Aumentar la altura de las filas
        
        # Aplicar estilos al Treeview de tags
        self.tags_list.tag_configure('highlight', background='#FFCCCC', foreground='black')
        self.tags_list.tag_configure('normal', background='white', foreground='black')
        
        # Botones
        button_frame = ttk.Frame(root)
        button_frame.grid(row=1, column=0, columnspan=2, pady=10)
        
        self.add_button = ttk.Button(button_frame, text="Agregar Tags", command=self.add_selected_tags)
        self.add_button.grid(row=0, column=0, padx=5)
        
        self.remove_button = ttk.Button(button_frame, text="Remover Tags", command=self.remove_selected_tags)
        self.remove_button.grid(row=0, column=1, padx=5)
        
        # Cargar datos
        self.load_urls()
        self.load_tags()
        
        # Eventos
        self.urls_list.bind('<<TreeviewSelect>>', self.on_url_select)
        self.tags_list.bind('<<TreeviewSelect>>', self.on_tag_select)

    def load_urls(self):
        """Cargar las URLs y sus tags en la lista"""
        conn = self.create_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sh.id, sh.url, sh.title, sh.platform, 
                       GROUP_CONCAT(t.name, ', ') as tags
                FROM streaming_history sh
                LEFT JOIN url_tags ut ON sh.id = ut.url_id
                LEFT JOIN tags t ON ut.tag_id = t.id
                GROUP BY sh.id, sh.url, sh.title, sh.platform
                ORDER BY sh.timestamp DESC
            ''')
            
            # Limpiar la lista actual
            for item in self.urls_list.get_children():
                self.urls_list.delete(item)
            
            # Insertar los nuevos datos
            for row in cursor.fetchall():
                url_id = row[0]
                url = row[1]
                title = row[2]
                platform = row[3]
                tags = row[4] if row[4] else ''
                self.urls_list.insert('', 'end', values=(url_id, url, title, platform, tags))
            
        finally:
            conn.close()

    def load_tags(self):
        """Cargar los tags en la lista"""
        # Obtener la jerarquía de tags
        tags = self.get_tag_hierarchy()
        
        # Limpiar la lista actual
        for item in self.tags_list.get_children():
            self.tags_list.delete(item)
        
        # Insertar los tags con su jerarquía
        self._insert_tags_recursive(tags)
        
        # Expandir todos los tags que tienen hijos
        for item in self.tags_list.get_children():
            if self.tags_list.item(item)['open']:
                self.tags_list.item(item, open=True)
        
        # Obtener la jerarquía de tags
        tags = self.get_tag_hierarchy()
        
        # Limpiar la lista actual
        for item in self.tags_list.get_children():
            self.tags_list.delete(item)
        
        # Insertar los tags con su jerarquía
        self._insert_tags_recursive(tags)
        
        # Expandir todos los tags que tienen hijos
        for item in self.tags_list.get_children():
            if self.tags_list.item(item)['open']:
                self.tags_list.item(item, open=True)

    def _insert_tags_recursive(self, tags, parent=''):
        """Insertar tags recursivamente manteniendo la jerarquía"""
        for tag in tags:
            if tag['level'] == 0:
                formatted_tag = tag['name']
            else:
                formatted_tag = '└─ ' + '  ' * (tag['level'] - 1) + tag['name']
            # Insertar el tag con el estilo por defecto
            item = self.tags_list.insert(parent, 'end', values=(formatted_tag,), tags=('normal',))
            if tag['children']:
                self._insert_tags_recursive(tag['children'], item)
                self.tags_list.item(item, open=True)
                # Expandir automáticamente los tags con hijos
                self.tags_list.item(item, open=True)

    def get_db_path(self):
        """Obtiene la ruta de la base de datos"""
        db_path = Path(user_log_dir("alterclip")) / "streaming_history.db"
        # Asegurarse de que el directorio exista
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    def create_connection(self):
        """Crea una conexión a la base de datos"""
        conn = sqlite3.connect(str(self.get_db_path()))
        return conn
                
        # Configurar el estilo para los ítems de flecha

    def get_tag_id(self, tag_name):
        """Obtiene el ID de un tag por su nombre"""
        # Limpiar el nombre del tag eliminando prefijos como '└─ '
        clean_tag_name = tag_name.strip()
        if clean_tag_name.startswith('└─ '):
            clean_tag_name = clean_tag_name[3:].strip()
        
        conn = self.create_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tags WHERE name = ?', (clean_tag_name,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def get_url_tags(self, url_id):
        """Obtiene los tags asociados a una URL"""
        conn = self.create_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT t.name FROM tags t JOIN url_tags ut ON t.id = ut.tag_id WHERE ut.url_id = ?', (url_id,))
            tags = [row[0].strip() for row in cursor.fetchall()]
            return tags
        finally:
            conn.close()

    def get_tag_hierarchy(self, tag_name=None, level=0):
        """Obtiene la jerarquía de tags, opcionalmente desde un tag específico"""
        conn = self.create_connection()
        cursor = conn.cursor()
        
        # Obtener todos los tags y su jerarquía
        cursor.execute('''
            SELECT t1.name as parent_name, t1.id as parent_id,
                   t2.name as child_name, t2.id as child_id
            FROM tags t1
            LEFT JOIN tag_hierarchy th ON t1.id = th.parent_id
            LEFT JOIN tags t2 ON th.child_id = t2.id
            WHERE t1.id NOT IN (
                SELECT child_id FROM tag_hierarchy
            )
            ORDER BY t1.name, t2.name
        ''')
        
        # Crear estructura de jerarquía
        hierarchy = {}
        for row in cursor.fetchall():
            parent_name = row[0]
            parent_id = row[1]
            child_name = row[2]
            child_id = row[3]
            
            if parent_name not in hierarchy:
                hierarchy[parent_name] = {
                    'name': parent_name,
                    'id': parent_id,
                    'level': 0,
                    'children': []
                }
            
            if child_name and child_name != parent_name:
                child = {
                    'name': child_name,
                    'id': child_id,
                    'level': 1,
                    'children': []
                }
                hierarchy[parent_name]['children'].append(child)
        
        # Convertir la jerarquía a lista
        tags = []
        for tag_data in hierarchy.values():
            tags.append(tag_data)
        
        conn.close()
        return tags

    def update_tag_visualization(self, url_id):
        """Actualizar la visualización de los tags según su asociación con la URL"""
        # Configurar el estilo para los tags asociados
        self.tags_list.tag_configure('associated', foreground='red')
        
        # Limpiar la lista actual
        for item in self.tags_list.get_children():
            self.tags_list.delete(item)
        
        # Obtener los tags asociados
        associated_tags = self.get_url_tags(url_id)
        
        # Obtener la jerarquía de tags
        tags = self.get_tag_hierarchy()
        
        # Insertar los tags en la lista con su jerarquía
        for tag in tags:
            # Formatear el tag con su jerarquía
            formatted_tag = '└─ ' + '  ' * tag['level'] + tag['name']
            
            # Insertar el tag en la lista
            self.tags_list.insert('', 'end', values=(formatted_tag,))
            
            # Marcar los tags asociados con rojo
            if tag['name'] in associated_tags:
                # Buscar el tag en la lista
                found = False
                for item in self.tags_list.get_children():
                    values = self.tags_list.item(item)['values']
                    if values and values[0].strip() == formatted_tag.strip():
                        # Cambiar el color a rojo
                        self.tags_list.item(item, tags=('associated',))
                        found = True
                        break
                
                if not found:
                    print(f"Advertencia: No se encontró el tag '{tag['name']}' en la lista")
        
        # Configurar el estilo para los tags asociados
        self.tags_list.tag_configure('associated', foreground='red')

    def on_url_select(self, event):
        """Manejar la selección de una URL"""
        selection = self.urls_list.selection()
        if selection:
            item = self.urls_list.item(selection[0])
            # Obtener el ID de la URL (primera columna)
            url_id = item['values'][0]
            if url_id:
                self.selected_url_id = url_id
                
                # Actualizar los colores de los tags asociados
                # Primero obtener los tags asociados
                associated_tags = self.get_url_tags(url_id)
                print(f"Tags asociados a la URL: {associated_tags}")  # Para debugging
                
                # Limpiar todos los estilos existentes
                for item in self.tags_list.get_children():
                    # Restaurar el estilo normal y deseleccionar
                    self.tags_list.item(item, tags=('normal',))
                    self.tags_list.selection_remove(item)
                
                # Aplicar el estilo a los tags asociados
                for item in self.tags_list.get_children():
                    # Obtener el nombre del tag
                    values = self.tags_list.item(item)['values']
                    if values:
                        tag_name = values[0]
                        # Limpiar el nombre del tag eliminando prefijos como '└─ '
                        clean_tag_name = tag_name.strip()
                        if clean_tag_name.startswith('└─ '):
                            clean_tag_name = clean_tag_name[3:].strip()
                        
                        # Buscar el tag en la base de datos para obtener su nombre original
                        tag_id = self.get_tag_id(tag_name)
                        if tag_id:
                            conn = self.create_connection()
                            cursor = conn.cursor()
                            cursor.execute('SELECT name FROM tags WHERE id = ?', (tag_id,))
                            original_tag_name = cursor.fetchone()[0]
                            conn.close()
                            
                            # Comparar con el nombre original del tag
                            if original_tag_name in associated_tags:
                                # Seleccionar visualmente el tag y aplicar estilo highlight
                                self.tags_list.selection_add(item)
                                self.tags_list.item(item, tags=('highlight',))
                                print(f"Se resaltará: {tag_name} (original: {original_tag_name})")  # Para debugging
                            else:
                                print(f"No se resaltará: {tag_name} (original: {original_tag_name})")  # Para debugging
                        else:
                            print(f"No se encontró ID para el tag: {tag_name}")  # Para debugging
            else:
                print("ID de URL no válido")  # Para debugging

    def on_tag_select(self, event):
        """Manejar la selección de tags"""
        selection = self.tags_list.selection()
        if selection:
            # Obtener el nombre del tag
            tag = self.tags_list.item(selection[0])['values'][0]
            
            # Limpiar el nombre eliminando prefijos como '└─ '
            clean_tag = tag.strip()
            if clean_tag.startswith('└─ '):
                clean_tag = clean_tag[3:].strip()
            
            # Actualizar la selección
            if clean_tag not in self.selected_tags:
                self.selected_tags.add(clean_tag)
            else:
                self.selected_tags.remove(clean_tag)
            
            self.update_buttons()

    
    def update_buttons(self):
        """Actualizar el estado de los botones"""
        url_selected = self.selected_url_id is not None
        tags_selected = len(self.selected_tags) > 0
        
        self.add_button.config(state='normal' if url_selected and tags_selected else 'disabled')
        self.remove_button.config(state='normal' if url_selected and tags_selected else 'disabled')
    
    def add_selected_tags(self):
        """Agregar los tags seleccionados a la URL"""
        if not self.selected_url_id:
            messagebox.showwarning("Advertencia", "Por favor, seleccione una URL")
            return
        
        if not self.selected_tags:
            messagebox.showwarning("Advertencia", "Por favor, seleccione al menos un tag")
            return
        
        conn = self.create_connection()
        cursor = conn.cursor()
        
        for tag in self.selected_tags:
            # Obtener el ID del tag
            tag_id = self.get_tag_id(tag)
            if not tag_id:
                messagebox.showerror("Error", f"El tag '{tag}' no existe")
                conn.close()
                return
            
            # Verificar si la asociación ya existe
            cursor.execute('SELECT 1 FROM url_tags WHERE url_id = ? AND tag_id = ?', (self.selected_url_id, tag_id))
            if cursor.fetchone():
                messagebox.showwarning("Advertencia", f"La URL ya tiene el tag '{tag}'")
                conn.close()
                return
            
            # Crear la asociación
            cursor.execute('INSERT INTO url_tags (url_id, tag_id) VALUES (?, ?)', (self.selected_url_id, tag_id))
            
        conn.commit()
        conn.close()
        
        messagebox.showinfo("Éxito", "Tags agregados correctamente")
        self.load_urls()  # Refrescar la lista de URLs
        self.selected_tags.clear()
        self.update_buttons()
    
    def remove_selected_tags(self):
        """Remover los tags seleccionados de la URL"""
        if not self.selected_url_id:
            messagebox.showwarning("Advertencia", "Por favor, seleccione una URL")
            return
        
        if not self.selected_tags:
            messagebox.showwarning("Advertencia", "Por favor, seleccione al menos un tag")
            return
        
        conn = self.create_connection()
        cursor = conn.cursor()
        
        for tag in self.selected_tags:
            # Obtener el ID del tag
            tag_id = self.get_tag_id(tag)
            if not tag_id:
                messagebox.showerror("Error", f"El tag '{tag}' no existe")
                conn.close()
                return
            
            # Eliminar la asociación
            cursor.execute('DELETE FROM url_tags WHERE url_id = ? AND tag_id = ?', (self.selected_url_id, tag_id))
            
            if cursor.rowcount == 0:
                messagebox.showwarning("Advertencia", f"La URL no tiene el tag '{tag}'")
                conn.close()
                return
            
        conn.commit()
        conn.close()
        
        messagebox.showinfo("Éxito", "Tags removidos correctamente")
        self.load_urls()  # Refrescar la lista de URLs
        self.selected_tags.clear()
        self.update_buttons()

if __name__ == "__main__":
    root = tk.Tk()
    app = AlterclipGUI(root)
    root.mainloop()
