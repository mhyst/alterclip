# 🧠 Alterclip

**Alterclip** es una herramienta en segundo plano que monitoriza tu portapapeles y modifica automáticamente los enlaces que copias, para hacerlos más seguros o aptos para compartir en plataformas como Telegram. Además, en modo streaming, abre directamente vídeos de YouTube o contenido de Instagram con tu reproductor multimedia favorito.

---

## ✨ Características

- 🔁 Reemplaza dominios por versiones alternativas (más compartibles).
- 📋 Monitoriza el portapapeles de forma continua.
- 🎬 Abre automáticamente vídeos de YouTube o Instagram en modo streaming.
- 🧠 Decide automáticamente si cambiar o no un texto según su contenido.
- 📦 Compatible con Linux, macOS y Windows (con pequeñas adaptaciones).
- 🔧 Dos modos de funcionamiento con cambio dinámico mediante señales.

---

## 🔧 Requisitos

- Python 3.6 o superior
- Paquetes Python:

  ```bash
  pip install pyperclip platformdirs
  ```

- Reproductor multimedia como `mpv`, `vlc`, etc. (por defecto usa `mpv`).
- Linux (uso de señales POSIX como `SIGUSR1`/`SIGUSR2`; no compatible con Windows para eso).

---

## 🚀 Uso

1. Ejecuta el script:

   ```bash
   python3 alterclip.py
   ```

2. Copia una URL al portapapeles. Si es una de las compatibles, se transformará automáticamente y reemplazará el contenido del portapapeles.

3. En modo **streaming**, si copias un enlace de YouTube o Instagram, se abrirá automáticamente con tu reproductor.

---

## 🔁 Modos de funcionamiento

Alterclip tiene dos modos:

- 🟢 **Modo Streaming (por defecto)**:  
  Reproduce enlaces compatibles como Instagram o YouTube.

- 🔴 **Modo Offline**:  
  Solo reescribe URLs, sin abrir contenido.

En sistemas POSIX puedes cambiar entre modos sin reiniciar el script:

```bash
kill -USR1 <pid>  # Activa modo streaming
kill -USR2 <pid>  # Activa modo offline
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
| fixupx.com       | twixtter.com     |
| reddit.com       | reddxt.com       |
| onlyfans.com     | 0nlyfans.net     |
| patreon.com      | pxtreon.com      |
| pornhub.com      | pxrnhub.com      |
| nhentai.net      | nhentaix.net     |
| discord.gg       | disxcord.gg      |
| discord.com      | discxrd.com      |
| mediafire.com    | mediaf1re.com    |

---

## 🗂️ Logs

Los logs se guardan en:

```
~/.local/state/alterclip/alterclip.log
```

Contienen información útil como el PID, cambios de modo, errores de reproducción y actividad reciente.

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


---

## 📝 Licencia

Este proyecto está licenciado bajo la [GNU GPL v3](https://www.gnu.org/licenses/gpl-3.0.html).

---

## 🙌 Créditos

Creado por [mhyst].  
Inspirado en la necesidad de compartir enlaces sin bloqueos ni rastreadores.


