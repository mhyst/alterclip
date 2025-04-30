# 🧠 Alterclip

**Alterclip** es una herramienta en segundo plano que monitoriza tu portapapeles y modifica automáticamente los enlaces que copias, para hacerlos más seguros o aptos para compartir en plataformas como Telegram. Además, en modo streaming, abre directamente vídeos de YouTube o contenido de Instagram con tu reproductor multimedia favorito.

---

## ✨ Características

- 🔁 Reemplaza dominios por versiones alternativas (más seguras o compartibles).
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
  pip install pyperclip instaloader platformdirs
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
  Solo reescribe URLs, sin descargar ni abrir contenido.

Puedes cambiar entre modos sin reiniciar el script:

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

Contienen información útil como el PID, cambios de modo, errores de reproducción o descarga, y actividad reciente.

---

## ⚠️ Consideraciones de seguridad

- Este script intercepta todo lo que copies. No lo uses si estás copiando datos sensibles.
- Algunos de los dominios reescritos pueden no estar bajo tu control. Verifica antes de compartir.
- Instagram puede cambiar su API y romper la funcionalidad de descarga.

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

## 📝 Licencia

Este proyecto está licenciado bajo la [GNU GPL v3](https://www.gnu.org/licenses/gpl-3.0.html).

---

## 🙌 Créditos

Creado por [Tu Nombre o Alias Aquí].  
Inspirado en la necesidad de compartir enlaces sin bloqueos ni rastreadores.


