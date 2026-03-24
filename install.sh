#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==============================================${NC}"
echo -e "${GREEN}   AMNEZIA v2 — AUTO INSTALLER (Terminal App)${NC}"
echo -e "${BLUE}==============================================${NC}"

# 1. Проверка окружения
echo -e "[*] Проверка зависимостей..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[!] Python3 не найден. Устанавливаю...${NC}"
    sudo apt-get update && sudo apt-get install -y python3 python3-pip
fi

if ! command -v git &> /dev/null; then
    echo -e "${RED}[!] Git не найден. Устанавливаю...${NC}"
    sudo apt-get install -y git
fi

# 2. Клонирование репозитория во временную папку
echo -e "[*] Подготовка файлов..."
REPO_DIR="/tmp/amnezia-v2-setup"
rm -rf "$REPO_DIR"
git clone https://github.com/sky-night-net/amnezia-v2-deploy.git "$REPO_DIR"
cd "$REPO_DIR"

# 3. Установка Python-библиотек
echo -e "[*] Установка необходимых модулей (paramiko, bcrypt)..."
pip3 install -r requirements.txt --break-system-packages &> /dev/null

# 4. Запуск основного Terminal App
echo -e "${GREEN}[+] Запуск интерактивного мастера...${NC}"
python3 amnezia-cli.py </dev/tty
