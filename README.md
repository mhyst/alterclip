# 🧠 Alterclip

**Alterclip** es una herramienta en segundo plano que monitoriza tu portapapeles y modifica automáticamente los enlaces que copias, para hacerlos más seguros o aptos para compartir en plataformas como Telegram. Además, en modo streaming, abre directamente vídeos de YouTube, Instagram y Archive.org con tu reproductor multimedia favorito.

---

## ✨ Características

- 🔁 Reemplaza dominios por versiones alternativas (más compartibles).
- 📋 Monitoriza el portapapeles de forma continua.
- 🎬 Abre automáticamente vídeos de YouTube, Instagram, Facebook y Archive.org con tu reproductor multimedia favorito.
- 📚 Almacena el historial de vídeos reproducidos con título y plataforma.
- 📦 Compatible con Linux, macOS y Windows (con pequeñas adaptaciones).
- 🔧 Dos modos de funcionamiento con cambio dinámico mediante señales.
- 🌐 Aplicación web integrada para consultar y gestionar el historial de forma visual.
- 📊 Interfaz de línea de comandos para gestionar el historial y reproducir vídeos guardados.
- 🔍 Búsqueda avanzada en el historial con soporte para acentos y mayúsculas/minúsculas.
- 📋 Copia de URLs al portapapeles con prefijo share.only/ para compartir fácilmente.
- 🗑️ Eliminación de entradas del historial.
- 🔄 Soporte para índices relativos al reproducir vídeos (ejemplo: -1 = último, -2 = penúltimo).
- 🏷️ Sistema de tags jerárquicos para organizar el historial.
- 📊 Búsqueda por tags y sus relaciones (padres e hijos).
- 📈 Visualización de jerarquía completa de tags.

---

## ⚙️ Instalación

### Opción 1: Instalación desde PyPI (recomendado)

1. Instala el paquete con pip:
   ```bash
   pip install alterclip
   ```

Nota: Este método de instalación estará equiparado con los cambios publicados en la última release, aunque es posible que haya algunos cambios menores en el repositorio que aún no hayan sido liberados. En cualquier caso, utilizar la versión de la última release es más seguro de cara a posibles errores.

### Opción 2: Instalación desde el repositorio de GitHub

1. Clona el repositorio:
   ```bash
   git clone https://github.com/tuusuario/alterclip.git
   cd alterclip
   ```

2. Crea y activa un entorno virtual (recomendado):
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Opcional: Instala en modo desarrollo para realizar ediciones:
   ```bash
   pip install -e .
   ```

## 🔧 Requisitos

- **Python 3.8** o superior

### Dependencias principales
Instala las dependencias con:

```bash
pip install -r requirements.txt
```

O manualmente:
- `pyperclip>=1.8.2` - Para el manejo del portapapeles
- `platformdirs>=3.9.0` - Para rutas de configuración multiplataforma
- `plyer>=2.1.0` - Para notificaciones del sistema
- `termcolor>=2.3.0` - Para salida de colores en la terminal

### Dependencias opcionales
- **Reproductor multimedia**: `mpv` (recomendado), `vlc` o similar para reproducción de vídeos
- **Interfaz web**: `flask` para la interfaz web de consulta del historial
  ```bash
  pip install flask
  ```
- **API de YouTube** (recomendado para mejor precisión):
  - Crea un proyecto en Google Cloud Platform
  - Activa YouTube Data API v3
  - Configura la variable de entorno `YOUTUBE_API_KEY` con tu clave

- **Sugerencias y taxonomía por IA** (opcional):
  - Requiere una clave de API de OpenAI
  - Se necesita un pago inicial mínimo de $5 USD en la cuenta de OpenAI
  - Configura la variable de entorno `OPENAI_API_KEY` con tu clave
  - Permite sugerencias automáticas de tags y categorización de contenido

### Notas del sistema
- **Linux**: Compatibilidad completa, incluyendo señales POSIX (`SIGUSR1`/`SIGUSR2`)
- **Windows**: Compatible, pero sin soporte para señales POSIX
- **macOS**: Compatible con algunas limitaciones en notificaciones
- Nota: Alternativamente ofrece el comando alterclip-cli toggle que envía un paquete UDP al demonio para cambiar el modo de funcionamiento. Esta alternativa sí funciona en cualquier sistema.

---

## 🚀 Uso

### Ejecutar el daemon

1. Ejecuta el daemon principal:

   ```bash
   python3 alterclip.py
   ```

2. Copia una URL al portapapeles. Si es una de las compatibles, se transformará automáticamente y reemplazará el contenido del portapapeles.

3. En modo **streaming**, si copias un enlace de YouTube, Instagram, Facebook y Archive.org, se abrirá automáticamente con tu reproductor.

### Usar la interfaz de línea de comandos

El CLI (`alterclip-cli.py`) te permite:

- Ver el historial de vídeos reproducidos con búsqueda avanzada
- Ver solo URLs sin tags usando `hist --no-tags`
- Reproducir cualquier vídeo guardado usando índices absolutos o relativos
- Reproducir múltiples vídeos en secuencia
- Copiar URLs al portapapeles con prefijo share.only/ para compartir
- Eliminar entradas del historial
- Cambiar el modo de funcionamiento
- Gestionar tags jerárquicos para organizar el historial
- Generar sugerencias de tags y taxonomía por IA

Ejemplos de uso:

```bash
# Ver historial completo
./alterclip-cli hist

# Ver solo URLs sin tags
./alterclip-cli hist --no-tags

# Ver solo las últimas 5 entradas
./alterclip-cli hist --limit 5

# Ver solo contenido de YouTube
./alterclip-cli hist --platform YouTube

# Buscar vídeos en el historial que contengan "música"
./alterclip-cli search música

# Buscar vídeos de Instagram
./alterclip-cli search música --platform Instagram

# Reproducir el último vídeo guardado
./alterclip-cli play -1

# Reproducir múltiples vídeos en secuencia
./alterclip-cli playall --tags "Filosofía" --shuffle
./alterclip-cli playall --search "música" --limit 5
./alterclip-cli playall --platform "YouTube" --reverse
./alterclip-cli playall --visto 0  # Reproduce solo URLs no vistas
./alterclip-cli playall --visto 3   # Reproduce URLs vistas 3 veces o menos

# Copiar la URL del penúltimo vídeo al portapapeles
./alterclip-cli copy -2

# Eliminar el vídeo con ID 123
./alterclip-cli rm 123

# Cambiar el modo de alterclip
./alterclip-cli toggle

# Añadir un nuevo tag
./alterclip-cli tag add "Arqueología" --description "Contenido relacionado con arqueología"

# Crear un tag hijo
./alterclip-cli tag add "Antiguas Civilizaciones" --parent "Arqueología"

# Asociar un tag con una URL
./alterclip-cli tag url add 1 "Arqueología"

# Eliminar una asociación de tag
./alterclip-cli tag url rm 1 "Arqueología"

# Asignar automáticamente etiquetas con IA
./alterclip-cli tag auto 1  # Etiqueta automáticamente la URL con ID 1

# Buscar URLs con un tag específico
./alterclip-cli hist --tags "Arqueología"

# Actualizar un tag
./alterclip-cli tag update "Arqueología" --new-name "Arqueología y Antigüedad"

# Eliminar un tag
./alterclip-cli tag rm "Arqueología"

# Ver ayuda completa
./alterclip-cli man
```

---

## 🔁 Modos de funcionamiento

Alterclip tiene dos modos:

- 🟢 **Modo Streaming (por defecto)**:  
  Reproduce enlaces compatibles como YouTube, Instagram o Facebook.

- 🔴 **Modo Offline**:  
  Solo reescribe URLs y las guarda en el historial para futura referencia.

Puedes cambiar entre modos de dos formas:

1. Usando señales (solo en sistemas POSIX):

   ```bash
   kill -USR1 <pid>  # Activa modo streaming
   kill -USR2 <pid>  # Activa modo offline
   ```

2. Usando el CLI:

   ```bash
   ./alterclip-cli toggle
   ```

El PID aparece al inicio en los logs, o puedes obtenerlo con:

```bash
ps aux | grep alterclip
```

---

## 📄 Dominios reescritos

Algunos ejemplos de reemplazos automáticos de enlaces:

| Original          | Reemplazo        |
|------------------|------------------|
| x.com            | fixupx.com       |
| tiktok.com       | tfxktok.com      |
| twitter.com      | fixupx.com       |
| pornhub.com      | pxrnhub.com      |
| nhentai.net      | nhentaix.net     |

## 📚 Historial de vídeos

Alterclip guarda automáticamente todas las URLs de streaming en su base de datos, incluso cuando está en modo offline. Para cada vídeo se almacena:

- URL original
- Título del contenido (cuando está disponible)
- Plataforma (YouTube, Instagram, Facebook)
- Fecha y hora de reproducción
- Tags asociados
- Visto (cuantas veces se ha reproducido)

Puedes acceder al historial usando el CLI o mediante la aplicación web proporcionada en la carpeta web.

---

## 🗂️ Logs y Base de datos

### Logs

Los logs se guardan en:

```
~/.local/state/alterclip/alterclip.log
```

Contienen información útil como el PID, cambios de modo, errores de reproducción y actividad reciente.

### Base de datos

La base de datos de historial se almacena en:

```
~/.local/state/alterclip/streaming_history.db
```

---

## 🧪 Ejecución como servicio

Puedes usar `nohup`, `systemd`, `tmux` o `screen` para mantener Alterclip ejecutándose en segundo plano:

```bash
nohup python3 alterclip.py &
```

También puedes crear un servicio `systemd` como este (guarda como `~/.config/systemd/user/alterclip.service`):

```ini
[Unit]
Description=Alterclip Clipboard Monitor
After=network.target

[Service]
ExecStart=/usr/bin/python3 /ruta/a/alterclip.py
Restart=always

[Install]
WantedBy=default.target
```

Y luego habilítalo con:

```bash
systemctl --user daemon-reexec
systemctl --user daemon-reload
systemctl --user enable --now alterclip.service
```
---

## 🟢 Ejecutar Alterclip con `gtk-launch`

Para lanzar **Alterclip** utilizando `gtk-launch`, es necesario tener un archivo `.desktop` correctamente configurado en tu sistema. Este método es útil si quieres integrar Alterclip con entornos gráficos o lanzadores de aplicaciones.

### 1. Crear el archivo `.desktop`

Crea un archivo llamado `alterclip.desktop` en `~/.local/share/applications/` con el siguiente contenido:

```ini
[Desktop Entry]
Name=Alterclip
Exec=python3 /ruta/completa/a/alterclip.py
Terminal=false
Type=Application
Icon=utilities-terminal
Categories=Utility;
```

> 🔧 **Importante**: Asegúrate de reemplazar `/ruta/completa/a/alterclip.py` con la ruta real al script principal de Alterclip.

### 2. Dar permisos de ejecución

Dale permisos de ejecución al archivo `.desktop`:

```bash
chmod +x ~/.local/share/applications/alterclip.desktop
```

### 3. Ejecutar Alterclip con `gtk-launch`

Una vez creado el archivo `.desktop`, puedes lanzar Alterclip desde la terminal con:

```bash
gtk-launch alterclip
```

> 🧠 **Nota**: El argumento que se pasa a `gtk-launch` debe coincidir con el valor de `Name=` en el archivo `.desktop`, en minúsculas y sin espacios. Si tienes dudas, también puedes usar el nombre del archivo sin la extensión: `gtk-launch alterclip`.

---

## 📝 Licencia

Este proyecto está licenciado bajo la [GNU GPL v3](https://www.gnu.org/licenses/gpl-3.0.html).

---

## 🙌 Créditos

Creado por [mhyst].  
Inspirado en la necesidad de compartir enlaces sin bloqueos ni rastreadores.
