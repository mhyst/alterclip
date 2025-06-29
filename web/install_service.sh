#!/bin/bash

# Script de instalación para el servicio AlterClip Web

# Variables
SERVICE_NAME="alterclip-web"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
APP_DIR="/home/mhyst/Proyectos/alterclip/web"

# Verificar si se ejecuta como root
if [ "$EUID" -ne 0 ]; then 
    echo "Por favor, ejecuta este script como root (usando sudo)"
    exit 1
fi

echo "=== Instalando servicio AlterClip Web ==="

# Instalar dependencias del sistema
echo "Instalando dependencias del sistema..."
apt-get update
apt-get install -y python3 python3-pip python3-flask

# Configurar el servicio systemd
echo "Configurando el servicio systemd..."

# Crear el archivo de servicio
cat > "$SERVICE_FILE" <<EOL
[Unit]
Description=AlterClip Web Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
# Usar el intérprete de Python del sistema
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=10

# Configuración de seguridad
PrivateTmp=true
ProtectSystem=full
NoNewPrivileges=true

# Configuración de logs
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOL

# Recargar systemd
echo "Recargando systemd..."
systemctl daemon-reload

# Habilitar e iniciar el servicio
echo "Iniciando el servicio $SERVICE_NAME..."
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

# Mostrar estado del servicio
echo "Estado del servicio:"
systemctl status "$SERVICE_NAME"

echo "\n¡Instalación completada!"
echo "El servicio está configurado para iniciarse automáticamente al arrancar el sistema."
echo "Puedes gestionar el servicio con los siguientes comandlos:"
echo "  - Iniciar:    sudo systemctl start $SERVICE_NAME"
echo "  - Detener:     sudo systemctl stop $SERVICE_NAME"
echo "  - Reiniciar:  sudo systemctl restart $SERVICE_NAME"
echo "  - Ver estado: sudo systemctl status $SERVICE_NAME"
echo "  - Ver logs:    journalctl -u $SERVICE_NAME -f"
