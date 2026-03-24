#!/bin/bash

# Скрипт сборки SkyKnight Automator для macOS
echo "[*] Начинаю сборку Sky Night VPN Automator..."

# 1. Создание виртуального окружения
if [ ! -d "venv_build" ]; then
    echo "[*] Создание виртуального окружения..."
    python3 -m venv venv_build
fi

source venv_build/bin/activate

# 2. Установка зависимостей
echo "[*] Установка зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. Сборка через PyInstaller
echo "[*] Запуск PyInstaller..."

# Определяем пути
DASHBOARD_DIR="../Amnezia_Premium_Dashboard"
ICON_FILE="app_icon.png" # Это должен быть .icns для иконки приложения, но пока используем .png для ресурсов

# Команда сборки
# --add-data "SOURCE:DEST" (в macOS DEST это относительный путь внутри бандла)
pyinstaller --noconfirm --onefile --windowed \
    --name "SkyKnightAutomator" \
    --icon "app_icon.png" \
    --add-data "$DASHBOARD_DIR:Amnezia_Premium_Dashboard" \
    --add-data "logo_sk.png:." \
    --add-data "app_icon.png:." \
    AmneziaAutomator.py

echo "[+] Сборка завершена! Приложение находится в папке dist/SkyKnightAutomator.app"
deactivate
