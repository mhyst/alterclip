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
        self.root.grid_rowconfigure(1, weight=0)
        
        # Frame para la lista de URLs
        self.urls_frame = ttk.LabelFrame(root, text="Historial de URLs", padding="5")
        self.urls_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Configurar el grid del frame de URLs
        self.urls_frame.grid_columnconfigure(0, weight=1)
        self.urls_frame.grid_rowconfigure(0, weight=1)
        
        # Treeview para las URLs
        self.urls_list = ttk.Treeview(self.urls_frame, columns=('ID', 'Título', 'Plataforma'), show='headings')
        self.urls_list.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configurar las columnas
        self.urls_list.column('ID', width=50)
        self.urls_list.column('Título', width=500)
        self.urls_list.column('Plataforma', width=100)
        
        # Configurar las cabeceras
        self.urls_list.heading('ID', text='ID')
        self.urls_list.heading('Título', text='Título')
        self.urls_list.heading('Plataforma', text='Plataforma')
        
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
        self.tags_list = ttk.Treeview(self.tags_frame, show='tree')
        self.tags_list.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Deshabilitar la interacción con los triángulos de expansión
        self.tags_list.bind('<Button-1>', self.on_tree_click)
        
        # Scrollbar para los tags
        self.tags_scroll = ttk.Scrollbar(self.tags_frame, orient="vertical", command=self.tags_list.yview)
        self.tags_scroll.grid(row=0, column=1, sticky="ns")
        self.tags_list.configure(yscrollcommand=self.tags_scroll.set)
        
        # Frame para botones
        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        # Configurar el grid del frame de botones
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)
        button_frame.grid_columnconfigure(3, weight=1)
        
        # Botones
        self.add_button = ttk.Button(button_frame, text="Agregar Tags", command=self.add_selected_tags)
        self.add_button.grid(row=0, column=0, padx=5)
        
        self.remove_button = ttk.Button(button_frame, text="Remover Tags", command=self.remove_selected_tags)
        self.remove_button.grid(row=0, column=1, padx=5)
        
        # Botones de recarga
        self.reload_urls_button = ttk.Button(button_frame, text="Recargar URLs", command=self.reload_urls)
        self.reload_urls_button.grid(row=0, column=2, padx=5)
        
        self.reload_tags_button = ttk.Button(button_frame, text="Recargar Tags", command=self.reload_tags)
        self.reload_tags_button.grid(row=0, column=3, padx=5)
        
        # Variable para controlar la carga inicial
        self.loading_initial = False
        
        # Eventos
        self.urls_list.bind('<<TreeviewSelect>>', self.on_url_select)
        # Solo necesitamos el evento de clic para el Treeview
        self.tags_list.bind('<Button-1>', self.on_tree_click)
        
        # Cargar datos
        self.loading_initial = True
        self.load_urls()
        self.load_tags()
        self.loading_initial = False

    def add_selected_tags(self):
        """Agregar los tags seleccionados a la URL"""
        if not self.selected_url_id:
            messagebox.showwarning("Advertencia", "Por favor, seleccione una URL")
            return
            
        if not self.selected_tags:
            messagebox.showwarning("Advertencia", "Por favor, seleccione al menos un tag")
            return
            
        conn = self.create_connection()
        try:
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
            messagebox.showinfo("Éxito", "Tags agregados correctamente")
            self.update_tag_visualization(self.selected_url_id)  # Refrescar la visualización
            self.selected_tags.clear()
            self.update_buttons()
            
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Error al agregar tags: {str(e)}")
            conn.rollback()
        finally:
            conn.close()

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
        self.update_tag_visualization(self.selected_url_id)  # Refrescar la visualización
        self.selected_tags.clear()
        self.update_buttons()

    def add_selected_tags(self):
        """Agregar los tags seleccionados a la URL"""
        if not self.selected_url_id:
            messagebox.showwarning("Advertencia", "Por favor, seleccione una URL")
            return
            
        if not self.selected_tags:
            messagebox.showwarning("Advertencia", "Por favor, seleccione al menos un tag")
            return
            
        conn = self.create_connection()
        try:
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
            messagebox.showinfo("Éxito", "Tags agregados correctamente")
            self.update_tag_visualization(self.selected_url_id)  # Refrescar la visualización
            self.selected_tags.clear()
            self.update_buttons()
            
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Error al agregar tags: {str(e)}")
            conn.rollback()
        finally:
            conn.close()

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
        """Obtener los tags asociados a una URL"""
        conn = self.create_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.name
                FROM tags t
                JOIN url_tags ut ON t.id = ut.tag_id
                WHERE ut.url_id = ?
            ''', (url_id,))
            
            # Obtener los nombres de los tags
            return {row[0] for row in cursor.fetchall()}
            
        except sqlite3.Error as e:
            print(f"Error al obtener tags de URL: {str(e)}")
            return set()
        finally:
            conn.close()

    def get_tag_hierarchy(self):
        """Obtiene la jerarquía de tags desde la base de datos"""
        conn = self.create_connection()
        try:
            cursor = conn.cursor()
            
            # Obtener todos los tags y sus relaciones
            cursor.execute('''
                SELECT t1.id, t1.name, th.parent_id
                FROM tags t1
                LEFT JOIN tag_hierarchy th ON t1.id = th.child_id
            ''')
            
            # Crear la estructura jerárquica
            def build_hierarchy(tags):
                # Primero, obtener todos los tags raíz (sin padre)
                roots = [tag for tag in tags if tag[2] is None]
                
                # Función auxiliar para obtener hijos directos
                def get_children(tags, parent_id):
                    return [tag for tag in tags if tag[2] == parent_id]
                
                # Función recursiva para construir la jerarquía
                def build_tree(tag_id):
                    children = get_children(tags, tag_id)
                    return [{
                        'id': child[0],
                        'name': child[1],
                        'children': build_tree(child[0]) if child[0] != tag_id else []
                    } for child in children]
                
                # Construir la jerarquía a partir de las raíces
                return [{
                    'id': root[0],
                    'name': root[1],
                    'children': build_tree(root[0])
                } for root in roots]
            
            tags = cursor.fetchall()
            return build_hierarchy(tags)
            
        except sqlite3.Error as e:
            print(f"Error al obtener jerarquía de tags: {str(e)}")
            messagebox.showerror("Error", f"Error al obtener jerarquía de tags: {str(e)}")
            return []
        finally:
            conn.close()

    def load_urls(self):
        """Cargar las URLs y sus tags en la lista"""
        conn = self.create_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sh.id, sh.title, sh.platform
                FROM streaming_history sh
                ORDER BY sh.timestamp DESC
            ''')
            
            # Limpiar la lista actual
            for item in self.urls_list.get_children():
                self.urls_list.delete(item)
            
            # Insertar los nuevos datos
            for row in cursor.fetchall():
                url_id = row[0]
                title = row[1]
                platform = row[2]
                self.urls_list.insert('', 'end', values=(url_id, title, platform))
            
        except sqlite3.Error as e:
            print(f"Error al cargar URLs: {str(e)}")
            messagebox.showerror("Error", f"Error al cargar URLs: {str(e)}")
        finally:
            conn.close()

    def load_tags(self):
        """Cargar los tags en la lista"""
        try:
            # Establecer bandera de carga
            self.loading_initial = True
            
            # Obtener la jerarquía de tags
            tags = self.get_tag_hierarchy()
            
            # Limpiar la lista actual
            for item in self.tags_list.get_children():
                self.tags_list.delete(item)
            
            # Insertar los tags con su jerarquía
            self._insert_tags_recursive(tags)
            
            # Expandir todos los tags que tienen hijos
            for item in self.tags_list.get_children():
                self.tags_list.item(item, open=True)
            
            # Deshabilitar la expansión de nodos
            for item in self.tags_list.get_children():
                self.tags_list.item(item, open=True, tags=('no_expand',))
            
            # No llamamos a update_tag_visualization aquí porque no hay URL seleccionada
            print("Tags cargados exitosamente")  # Debug
            
        except Exception as e:
            print(f"Error al cargar tags: {str(e)}")
            messagebox.showerror("Error", f"Error al cargar los tags: {str(e)}")
        finally:
            # Restaurar bandera de carga
            self.loading_initial = False
            # Asegurarse de que los eventos estén habilitados
            self.tags_list.bind('<Button-1>', self.on_tree_click)

    def _insert_tags_recursive(self, tags, parent='', level=0):

        """Insertar tags recursivamente manteniendo la jerarquía"""
        for tag in tags:
            original_name = tag['name']
            
            # Insertar el tag con el estilo por defecto y el nombre original
            item = self.tags_list.insert(parent, 'end', 
                                        tags=('normal',), 
                                        text=tag['name'])
            
            if tag['children']:
                # Expandir los nodos que tienen hijos
                self._insert_tags_recursive(tag['children'], item, level + 1)
                self.tags_list.item(item, open=True)

        if self.loading_initial:
            return

        if not self.selected_url_id:
            messagebox.showwarning("Advertencia", "Selecciona una URL primero")
            return
        
        if not self.selected_tags:
            messagebox.showwarning("Advertencia", "Selecciona al menos un tag")
            return
        
        conn = self.create_connection()
        try:
            cursor = conn.cursor()
            
            # Eliminar cada tag seleccionado
            for tag in self.selected_tags:
                tag_id = self.get_tag_id(tag)
                if tag_id:
                    # Eliminar la asociación
                    cursor.execute('DELETE FROM url_tags WHERE url_id = ? AND tag_id = ?', 
                                 (self.selected_url_id, tag_id))
                    
                    if cursor.rowcount == 0:
                        messagebox.showwarning("Advertencia", f"La URL no tiene el tag '{tag}'")
                        continue
            
            conn.commit()
            
            messagebox.showinfo("Éxito", "Tags removidos correctamente")
            self.update_tag_visualization(self.selected_url_id)  # Refrescar la visualización
            self.selected_tags.clear()
            self.update_buttons()
            
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("Error", f"Error al remover tags: {str(e)}")
        finally:
            conn.close()

    def on_url_select(self, event):
        """Manejar la selección de una URL"""
        selected_item = self.urls_list.selection()
        if selected_item:
            item = selected_item[0]
            try:
                url_id = self.urls_list.item(item)['values'][0]
                self.selected_url_id = url_id
                
                # Actualizar la visualización de los tags
                self.update_tag_visualization(url_id)
                
                # Actualizar los botones
                self.update_buttons()
            except Exception as e:
                print(f"Error al seleccionar URL: {str(e)}")
                messagebox.showerror("Error", f"Error al seleccionar URL: {str(e)}")

    def reload_urls(self):
        """Recargar la lista de URLs"""
        try:
            # Limpiar la lista actual
            for item in self.urls_list.get_children():
                self.urls_list.delete(item)
            
            # Cargar las URLs nuevamente
            self.load_urls()
            messagebox.showinfo("Éxito", "URLs recargadas correctamente")
        except Exception as e:
            print(f"Error al recargar URLs: {str(e)}")
            messagebox.showerror("Error", f"Error al recargar URLs: {str(e)}")

    def reload_tags(self):
        """Recargar la lista de tags"""
        try:
            # Limpiar la lista actual
            for item in self.tags_list.get_children():
                self.tags_list.delete(item)
            
            # Cargar los tags nuevamente
            self.load_tags()
            messagebox.showinfo("Éxito", "Tags recargados correctamente")
        except Exception as e:
            print(f"Error al recargar tags: {str(e)}")
            messagebox.showerror("Error", f"Error al recargar tags: {str(e)}")

    def on_tree_click(self, event):
        """Manejar clics en el Treeview para evitar la expansión de nodos"""
        # Ignorar eventos durante la carga inicial
        if self.loading_initial:
            return
            
        # Obtener el item que recibió el clic
        item = self.tags_list.identify_row(event.y)
        
        # Si se hizo clic en un triángulo de expansión, evitar la expansión
        bbox = self.tags_list.bbox(item)
        if bbox and bbox[0] <= event.x <= bbox[0] + 20:  # 20px es el ancho aproximado del triángulo
            return "break"  # Evitar la expansión
            
        # Manejar la selección del tag
        self.on_tag_select(event)

    def on_tag_select(self, event):
        """Manejar la selección de un tag"""
        # Ignorar eventos durante la carga inicial
        if self.loading_initial:
            return
            
        selection = self.tags_list.selection()
        if selection:
            item = self.tags_list.item(selection[0])
            # Obtener el nombre del tag (usando text en lugar de values)
            tag = item['text']
            
            if not self.selected_url_id:
                messagebox.showwarning("Advertencia", "Selecciona una URL primero")
                return
            
            # Si el tag ya está seleccionado, deseleccionarlo
            if tag in self.selected_tags:
                self.selected_tags.remove(tag)
            else:
                self.selected_tags.add(tag)
            
            self.update_buttons()

    def update_tag_visualization(self, url_id):
        """Actualizar la visualización de los tags según su asociación con la URL"""
        # Configurar el estilo para los tags asociados
        self.tags_list.tag_configure('associated', foreground='red')
        
        # Obtener los tags asociados
        associated_tags = self.get_url_tags(url_id)
        print(f"Tags asociados obtenidos: {associated_tags}")  # Debug
        
        # Limpiar todos los estilos actuales
        for item in self.tags_list.get_children():
            self.tags_list.item(item, tags=('normal',))
            for child in self.tags_list.get_children(item):
                self.tags_list.item(child, tags=('normal',))
        
        # Función auxiliar para recorrer todos los items recursivamente
        def process_item(item_id):
            # Obtener el nombre del tag (usando text en lugar de values)
            tag_name = self.tags_list.item(item_id)['text']
            print(f"Comparando tag: {tag_name} con tags asociados")  # Debug
            
            # Verificar si el tag está en la lista de tags asociados
            if tag_name in associated_tags:
                print(f"¡Encontrado! Tag {tag_name} está en los asociados")  # Debug
                # Aplicar el estilo asociado
                self.tags_list.item(item_id, tags=('associated',))
            
            # Procesar los hijos
            children = self.tags_list.get_children(item_id)
            for child in children:
                process_item(child)
        
        # Iniciar el procesamiento desde la raíz
        root_items = self.tags_list.get_children()
        for item in root_items:
            process_item(item)
        
        # Expandir todos los tags que tienen hijos
        for item in self.tags_list.get_children():
            self.tags_list.item(item, open=True)
        
        print("Visualización de tags actualizada")  # Debug

    def update_buttons(self):
        """Actualizar el estado de los botones"""
        self.add_button['state'] = 'normal' if self.selected_url_id and self.selected_tags else 'disabled'
        self.remove_button['state'] = 'normal' if self.selected_url_id and self.selected_tags else 'disabled'

if __name__ == "__main__":
    root = tk.Tk()
    app = AlterclipGUI(root)
    root.mainloop()
