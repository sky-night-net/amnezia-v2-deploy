<p align="center">
  <img src="https://github.com/user-attachments/assets/901ec8a8-eb42-485b-a0f3-828e78e79501" alt="Amnezia VPN CLI Banner" width="800">
</p>

# 🛡️ Amnezia VPN CLI v2 — Premium Deployment Suite

**Продвинутый комплекс для управления VPN на базе AmneziaWG (v1.5+). Включает в себя Premium Dashboard, систему аналитики трафика и кроссплатформенный Automator.**

---

## 🚀 Что нового в v2?

В отличие от классической версии, **v2** предлагает полноценную инфраструктуру:
- **Premium Dashboard**: Современный Glassmorphism Web-интерфейс для управления сервером.
- **Automator App**: macOS Desktop приложение для развертывания серверов в 1 клик.
- **Live Statistics**: Нативный `statsCollector` с базой SQLite для мониторинга живого трафика (RX/TX) каждого клиента.
- **Smart Obfuscation**: Продвинутая обфускация (JC, JMIN, JMAX, S1, S2, H1-H4 + **I1/I2 токены**).

---

## ⚡ Быстрая установка (Terminal App)

Просто вставьте эту команду в терминал на вашем локальном компьютере:
```bash
curl -sL https://raw.githubusercontent.com/sky-night-net/amnezia-v2-deploy/main/install.sh | bash
```

---

## ⚡ Ручная установка
Если вы предпочитаете ручной контроль:
```bash
# Клонируйте репозиторий
git clone https://github.com/sky-night-net/amnezia-v2-deploy.git
cd amnezia-v2-deploy

# Запустите мастер настройки
python3 amnezia-cli.py
```

### 2. macOS Automator App
Если вы используете macOS, воспользуйтесь готовым приложением:
1. Зайдите в директорию `Automator_App`.
2. Запустите скрипт сборки: `./build_macos.sh`.
3. Готовое приложение `SkyKnightAutomator.app` появится в папке `dist/`.

---

## 📊 Premium Dashboard и Статистика
Панель управления будет доступна по указанному вами при установке порту (по умолчанию `4466`).
Аналитика трафика собирается нативно напрямую из пространства ядра WireGuard и доступна по API на порту `9191`.

---

## 🛠️ Структура проекта
- `amnezia-cli.py` — Интерактивный мастер развертывания.
- `amnezia-deploy.py` — Ядро развертывания Docker контейнера.
- `Automator_App/` — Исходный код macOS интерфейса (Tkinter).
- `Amnezia_Premium_Dashboard/` — Frontend (Glassmorphism JS/CSS) и Backend сборщика статистики.
- `stats/` — Автономный скрипт сбора статистики в SQLite базу данных.

---

## 📚 Источники и благодарности

Этот проект был собран и доработан на базе следующих открытых решений:

*   **[Amnezia Project](https://amnezia.org)** — Разработка и поддержка протокола AmneziaWG.
*   **[amnezia-wg-easy](https://github.com/w0rng/amnezia-wg-easy)** (by w0rng) — Docker-образ, используемый в качестве ядра сервера.
*   **[WireGuard Easy](https://github.com/wg-easy/wg-easy)** — Основа для оригинального веб-интерфейса.
*   **SkyKnight Network** — Дизайн Premium Dashboard (Glassmorphism), разработка Automator App и системы аналитики.

---

<p align="center">
  Сделано с ❤️ для обеспечения максимальной приватности.
</p>
