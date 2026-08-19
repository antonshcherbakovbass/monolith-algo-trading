"""Internationalization: Russian and English translations."""
from __future__ import annotations

import json
from pathlib import Path

LANG_PATH = Path(__file__).resolve().parent.parent / "config" / "lang.json"


def _load_lang() -> str:
    try:
        if LANG_PATH.exists():
            with open(LANG_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("lang", "ru")
    except Exception:
        pass
    return "ru"


def _save_lang(lang: str) -> None:
    try:
        LANG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LANG_PATH, "w", encoding="utf-8") as f:
            json.dump({"lang": lang}, f)
    except Exception:
        pass


_TRANSLATIONS: dict[str, dict[str, str]] = {
    # ── Window ─────────────────────────────────────────────
    "window.title": {
        "ru": "◇ LUX NOX CAPITAL ◇ MONOLITH ◇",
        "en": "◇ LUX NOX CAPITAL ◇ MONOLITH ◇",
    },
    "window.subtitle": {
        "ru": "Настройте параметры торговли и запустите систему",
        "en": "Configure trading parameters and launch the system",
    },

    # ── Tab names ──────────────────────────────────────────
    "tab.help": {"ru": "❓ ПОМОЩЬ", "en": "❓ HELP"},
    "tab.broker": {"ru": "🏦 БРОКЕР", "en": "🏦 BROKER"},
    "tab.telegram": {"ru": "✉ TELEGRAM", "en": "✉ TELEGRAM"},
    "tab.curator": {"ru": "👁 КУРАТОР", "en": "👁 CURATOR"},
    "tab.ai": {"ru": "◎ AI / ML", "en": "◎ AI / ML"},
    "tab.risk": {"ru": "⚖ РИСКИ", "en": "⚖ RISK"},
    "tab.safety": {"ru": "🛡 ЗАЩИТА", "en": "🛡 SAFETY"},
    "tab.instruments": {"ru": "◆ ИНСТРУМЕНТЫ", "en": "◆ INSTRUMENTS"},
    "tab.mode": {"ru": "⚙ РЕЖИМ", "en": "⚙ MODE"},

    # ── Help tab ───────────────────────────────────────────
    "help.welcome": {
        "ru": "Добро пожаловать в LUX NOX Capital!",
        "en": "Welcome to LUX NOX Capital!",
    },
    "help.intro": {
        "ru": (
            "MONOLITH — ваш личный помощник для торговли на Московской бирже.\n"
            "Система анализирует рынок, покупает и продаёт акции и фьючерсы.\n"
            "Ниже — объяснение каждой вкладки простым языком."
        ),
        "en": (
            "MONOLITH is your personal assistant for trading on the Moscow Exchange.\n"
            "It analyzes the market, buys and sells stocks and futures automatically.\n"
            "Below is a plain-language explanation of each tab."
        ),
    },
    "help.quik.title": {"ru": "🏦 БРОКЕР", "en": "🏦 BROKER"},
    "help.quik.subtitle": {
        "ru": "Выбор брокера и подключение",
        "en": "Broker selection and connection",
    },
    "help.quik.description": {
        "ru": (
            "Здесь вы выбираете своего брокера и настраиваете подключение.\n\n"
            "Поддерживаемые брокеры:\n"
            "• Сбербанк — через программу QUIK (TCP-подключение)\n"
            "• Тинькофф Инвестиции — через API по интернету (без QUIK)\n"
            "• Алор Брокер — через Alor OpenAPI\n"
            "• Финам — через Finam Trade API\n\n"
            "Для Сбербанка нужна программа QUIK — есть автонастройка и диагностика.\n"
            "Для остальных брокеров достаточно API-токена из личного кабинета.\n"
            "Также здесь указываются номер счёта и комиссии (заполнены по умолчанию)."
        ),
        "en": (
            "Here you select your broker and configure the connection.\n\n"
            "Supported brokers:\n"
            "• Sberbank — via QUIK terminal (TCP connection)\n"
            "• Tinkoff Investments — via internet API (no QUIK needed)\n"
            "• Alor Broker — via Alor OpenAPI\n"
            "• Finam — via Finam Trade API\n\n"
            "Sberbank requires the QUIK terminal — auto-setup and diagnostics are available.\n"
            "For other brokers an API token from your personal account is sufficient.\n"
            "Account number and commissions are also configured here (defaults pre-filled)."
        ),
    },
    "help.broker.title": {"ru": "🏦 БРОКЕР", "en": "🏦 BROKER"},
    "help.broker.subtitle": {"ru": "Выбор брокера и подключение", "en": "Broker selection and connection"},
    "help.broker.description": {
        "ru": (
            "Здесь вы выбираете своего брокера и настраиваете подключение.\n\n"
            "Поддерживаемые брокеры:\n"
            "• Сбербанк — через программу QUIK (TCP-подключение)\n"
            "• Тинькофф Инвестиции — через API по интернету (без QUIK)\n"
            "• Алор Брокер — через Alor OpenAPI\n"
            "• Финам — через Finam Trade API\n\n"
            "Для Сбербанка нужна программа QUIK — есть автонастройка и диагностика.\n"
            "Для остальных брокеров достаточно API-токена из личного кабинета.\n"
            "Также здесь указываются номер счёта и комиссии (заполнены по умолчанию)."
        ),
        "en": (
            "Here you select your broker and configure the connection.\n\n"
            "Supported brokers:\n"
            "• Sberbank — via QUIK terminal (TCP connection)\n"
            "• Tinkoff Investments — via internet API (no QUIK needed)\n"
            "• Alor Broker — via Alor OpenAPI\n"
            "• Finam — via Finam Trade API\n\n"
            "Sberbank requires the QUIK terminal — auto-setup and diagnostics are available.\n"
            "For other brokers an API token from your personal account is sufficient.\n"
            "Account number and commissions are also configured here (defaults pre-filled)."
        ),
    },
    "help.telegram.title": {"ru": "✉ TELEGRAM", "en": "✉ TELEGRAM"},
    "help.telegram.subtitle": {"ru": "Уведомления в Телеграм", "en": "Telegram notifications"},
    "help.telegram.description": {
        "ru": (
            "Программа будет отправлять вам отчёты в Телеграм:\n"
            "что купила, что продала, сколько заработала за день.\n\n"
            "Для этого нужно:\n"
            "1. Написать боту @BotFather в Телеграм и создать своего бота\n"
            "2. Скопировать токен бота сюда\n"
            "3. Узнать свой Chat ID (написать боту @userinfobot)\n"
            "4. Вставить Chat ID сюда\n\n"
            "Если не хотите уведомления — можно пропустить."
        ),
        "en": (
            "The app will send you reports via Telegram:\n"
            "what was bought, sold, and how much was earned today.\n\n"
            "To set this up:\n"
            "1. Message @BotFather on Telegram and create your bot\n"
            "2. Copy the bot token here\n"
            "3. Find your Chat ID (message @userinfobot)\n"
            "4. Paste your Chat ID here\n\n"
            "If you don't want notifications — you can skip this."
        ),
    },
    "help.curator.title": {"ru": "👁 КУРАТОР", "en": "👁 CURATOR"},
    "help.curator.subtitle": {
        "ru": "Уведомления для вашего помощника",
        "en": "Notifications for your supervisor",
    },
    "help.curator.description": {
        "ru": (
            "Если вы настраиваете программу для родственника или друга,\n"
            "здесь можно добавить ВТОРОГО Телеграм-бота, который будет\n"
            "писать ВАМ (как наблюдателю), если что-то пойдёт не так:\n"
            "• большие потери\n"
            "• аварийная остановка\n"
            "• переход на реальные деньги\n\n"
            "Если ставите себе — можно не включать."
        ),
        "en": (
            "If you're setting up the app for a relative or friend,\n"
            "you can add a SECOND Telegram bot here that will message\n"
            "YOU (as a supervisor) if something goes wrong:\n"
            "• large losses\n"
            "• emergency stop\n"
            "• switching to live trading\n\n"
            "If it's for yourself — you can skip this."
        ),
    },
    "help.ai.title": {"ru": "◎ AI / ML", "en": "◎ AI / ML"},
    "help.ai.subtitle": {
        "ru": "Искусственный интеллект",
        "en": "Artificial Intelligence",
    },
    "help.ai.description": {
        "ru": (
            "Программа использует AI (искусственный интеллект) для анализа\n"
            "новостей и принятия торговых решений.\n\n"
            "Для этого нужна бесплатная программа Ollama — она запускает\n"
            "AI-модель прямо на вашем компьютере, без интернета.\n\n"
            "Установите Ollama с сайта ollama.com, а потом в командной строке\n"
            "напишите: ollama pull llama3.1\n\n"
            "Обычно настройки здесь менять не нужно."
        ),
        "en": (
            "The app uses AI (artificial intelligence) to analyze\n"
            "news and make trading decisions.\n\n"
            "This requires the free Ollama application — it runs\n"
            "an AI model directly on your computer, offline.\n\n"
            "Install Ollama from ollama.com, then in the command line\n"
            "run: ollama pull llama3.1\n\n"
            "Usually the default settings here are fine."
        ),
    },
    "help.risk.title": {"ru": "⚖ РИСКИ", "en": "⚖ RISK"},
    "help.risk.subtitle": {"ru": "Лимиты и ограничения", "en": "Limits and constraints"},
    "help.risk.description": {
        "ru": (
            "Это самая важная вкладка для вашей безопасности!\n\n"
            "Здесь устанавливаются ограничения:\n"
            "• Максимальная просадка — сколько % от капитала можно потерять\n"
            "• Максимум на одну акцию — чтобы не вложить всё в одно место\n"
            "• Дневной лимит потерь — если потеряно столько за день, торговля стоп\n"
            "• Стоп-лосс — автоматическая продажа при убытке\n\n"
            "Чем меньше цифры — тем безопаснее, но и заработок меньше.\n"
            "Для начинающих рекомендуем не менять стандартные значения."
        ),
        "en": (
            "This is the most important tab for your safety!\n\n"
            "It sets limits:\n"
            "• Max drawdown — how much % of capital can be lost\n"
            "• Max per position — to avoid putting everything in one place\n"
            "• Daily loss limit — trading stops if this much is lost in a day\n"
            "• Stop-loss — automatic selling at a loss\n\n"
            "Lower numbers = safer, but also lower potential profit.\n"
            "For beginners we recommend keeping the defaults."
        ),
    },
    "help.safety.title": {"ru": "🛡 ЗАЩИТА", "en": "🛡 SAFETY"},
    "help.safety.subtitle": {"ru": "Дополнительная защита", "en": "Additional protection"},
    "help.safety.description": {
        "ru": (
            "Здесь собраны функции безопасности:\n\n"
            "• Режим обучения — первые 14 дней торговля только виртуальная\n"
            "• Блокировка при потерях — если за день потеряно слишком много,\n"
            "  торговля останавливается до завтра\n"
            "• Подтверждение крупных сделок — программа спросит разрешение\n"
            "  перед большой покупкой/продажей\n"
            "• PIN-код — чтобы случайно не включить реальные деньги\n"
            "• Бэкап настроек — автосохранение, можно откатить изменения\n"
            "• Профиль риска — выберите 'Консервативный' если не уверены"
        ),
        "en": (
            "Safety features are collected here:\n\n"
            "• Training mode — first 14 days are virtual trading only\n"
            "• Loss lock — if too much is lost in a day,\n"
            "  trading stops until tomorrow\n"
            "• Large trade confirmation — the app asks permission\n"
            "  before a big buy/sell\n"
            "• PIN code — to prevent accidentally enabling real money\n"
            "• Settings backup — auto-save, you can roll back changes\n"
            "• Risk profile — choose 'Conservative' if unsure"
        ),
    },
    "help.instruments.title": {"ru": "◆ ИНСТРУМЕНТЫ", "en": "◆ INSTRUMENTS"},
    "help.instruments.subtitle": {
        "ru": "Что покупать и продавать",
        "en": "What to buy and sell",
    },
    "help.instruments.description": {
        "ru": (
            "Здесь выбираются акции и фьючерсы, которыми будет торговать\n"
            "программа. Поставьте галочки напротив нужных.\n\n"
            "Напротив каждого инструмента показаны:\n"
            "• ⚠ Риск % — вероятность потерь (красный = опасно)\n"
            "• ▲ Профит % — потенциал заработка (зелёный = хорошо)\n\n"
            "Для начинающих рекомендуем: SBER, LKOH, GAZP, YNDX, GMKN —\n"
            "это крупные надёжные компании ('голубые фишки').\n\n"
            "Фьючерсы — это более рискованные инструменты с плечом.\n"
            "Если не знаете что это — лучше их не включать."
        ),
        "en": (
            "Here you select stocks and futures the app will trade.\n"
            "Check the ones you want.\n\n"
            "Next to each instrument you'll see:\n"
            "• ⚠ Risk % — loss probability (red = dangerous)\n"
            "• ▲ Profit % — earning potential (green = good)\n\n"
            "For beginners we recommend: SBER, LKOH, GAZP, YNDX, GMKN —\n"
            "these are large reliable companies ('blue chips').\n\n"
            "Futures are higher-risk leveraged instruments.\n"
            "If you're unsure what they are — better skip them."
        ),
    },
    "help.mode.title": {"ru": "⚙ РЕЖИМ", "en": "⚙ MODE"},
    "help.mode.subtitle": {"ru": "Как запускать систему", "en": "How to launch the system"},
    "help.mode.description": {
        "ru": (
            "Два режима работы:\n\n"
            "📝 Paper Trading — ВИРТУАЛЬНАЯ торговля.\n"
            "Программа делает вид, что покупает и продаёт,\n"
            "но реальные деньги не используются. Идеально для обучения!\n\n"
            "💰 Live Trading — РЕАЛЬНАЯ торговля за настоящие деньги.\n"
            "⚠ Включайте ТОЛЬКО когда уверены в настройках!\n"
            "Потребуется PIN-код и принятие рисков.\n\n"
            "Также здесь включаются/выключаются AI-агенты:\n"
            "каждый отвечает за свою стратегию торговли."
        ),
        "en": (
            "Two operating modes:\n\n"
            "📝 Paper Trading — VIRTUAL trading.\n"
            "The app simulates buying and selling,\n"
            "but no real money is used. Perfect for learning!\n\n"
            "💰 Live Trading — REAL trading with real money.\n"
            "⚠ Only enable when you're sure of your settings!\n"
            "A PIN code and risk acceptance are required.\n\n"
            "AI agents are also enabled/disabled here:\n"
            "each one handles its own trading strategy."
        ),
    },
    "help.tip": {
        "ru": (
            "💡 Совет: Начните с Paper Trading (виртуальная торговля).\n"
            "Когда убедитесь, что всё работает правильно — можно переключить\n"
            "на реальные деньги. Не торопитесь!"
        ),
        "en": (
            "💡 Tip: Start with Paper Trading (virtual trading).\n"
            "Once you're sure everything works correctly — you can switch\n"
            "to real money. Don't rush!"
        ),
    },

    # ── Broker tab ─────────────────────────────────────────
    "broker.select": {"ru": "Выберите вашего брокера", "en": "Select your broker"},
    "broker.sber": {"ru": "🏦 Сбербанк (через QUIK)", "en": "🏦 Sberbank (via QUIK)"},
    "broker.sber.desc": {
        "ru": "Требуется программа QUIK. Подключение через TCP.",
        "en": "Requires QUIK terminal. TCP connection.",
    },
    "broker.tinkoff": {"ru": "💛 Тинькофф Инвестиции", "en": "💛 Tinkoff Investments"},
    "broker.tinkoff.desc": {
        "ru": "Без QUIK! Подключение через API по интернету. Бесплатно.",
        "en": "No QUIK needed! API connection via internet. Free.",
    },
    "broker.alor": {"ru": "🔵 Алор Брокер", "en": "🔵 Alor Broker"},
    "broker.finam": {"ru": "🟢 Финам", "en": "🟢 Finam"},
    "broker.account": {"ru": "Account ID:", "en": "Account ID:"},
    "broker.client_code": {"ru": "Client Code:", "en": "Client Code:"},
    "broker.api_token": {"ru": "API Токен:", "en": "API Token:"},
    "broker.auto_setup": {"ru": "🔧 Автонастройка QUIK", "en": "🔧 QUIK Auto-Setup"},
    "broker.diagnostics": {"ru": "🔍 Диагностика QUIK", "en": "🔍 QUIK Diagnostics"},
    "broker.commissions": {"ru": "Комиссии", "en": "Commissions"},
    "broker.account_commissions": {"ru": "Счёт и комиссии", "en": "Account & Commissions"},
    "broker.comm_stocks": {"ru": "Комиссии — Акции", "en": "Commissions — Stocks"},
    "broker.comm_futures": {"ru": "Комиссии — Фьючерсы", "en": "Commissions — Futures"},
    "broker.exchange_fee": {"ru": "Биржевая комиссия (%):", "en": "Exchange fee (%):"},
    "broker.broker_fee": {"ru": "Брокерская комиссия (%):", "en": "Broker fee (%):"},
    "broker.clearing_fee": {"ru": "Клиринговая комиссия (%):", "en": "Clearing fee (%):"},
    "broker.fut_exchange_fee": {"ru": "Биржевая (за контракт, руб):", "en": "Exchange (per contract, RUB):"},
    "broker.fut_broker_fee": {"ru": "Брокерская (за контракт, руб):", "en": "Broker (per contract, RUB):"},
    "broker.fut_clearing_fee": {"ru": "Клиринговая (за контракт, руб):", "en": "Clearing (per contract, RUB):"},
    "broker.quik_host": {"ru": "IP-адрес QUIK:", "en": "QUIK IP address:"},
    "broker.quik_port": {"ru": "TCP порт:", "en": "TCP port:"},
    "broker.quik_batch": {"ru": "Батчинг (мс):", "en": "Batching (ms):"},
    "broker.quik_rps": {"ru": "Макс. запросов/сек:", "en": "Max requests/sec:"},
    "broker.quik_reconnect": {"ru": "Реконнект (сек):", "en": "Reconnect (sec):"},
    "broker.tinkoff_sandbox": {"ru": "Sandbox (тестовый режим)", "en": "Sandbox (test mode)"},
    "broker.tinkoff_hint": {
        "ru": "💡 Токен можно получить в приложении Тинькофф → Настройки → API",
        "en": "💡 Get your token in the Tinkoff app → Settings → API",
    },
    "broker.alor_hint": {
        "ru": "💡 Получите токены на my.alor.ru → API",
        "en": "💡 Get your tokens at my.alor.ru → API",
    },
    "broker.finam_hint": {
        "ru": "💡 Получите токен на trading.finam.ru → API",
        "en": "💡 Get your token at trading.finam.ru → API",
    },

    # ── Telegram tab ───────────────────────────────────────
    "telegram.section": {"ru": "Telegram-бот для отчётов", "en": "Telegram bot for reports"},
    "telegram.token": {"ru": "Bot Token:", "en": "Bot Token:"},
    "telegram.chat_id": {"ru": "Chat ID:", "en": "Chat ID:"},
    "telegram.interval": {"ru": "Интервал отчётов (мин):", "en": "Report interval (min):"},
    "telegram.test": {"ru": "⟐  Проверить подключение  ⟐", "en": "⟐  Test connection  ⟐"},
    "telegram.hint": {
        "ru": "Создайте бота через @BotFather, получите chat_id через @userinfobot",
        "en": "Create a bot via @BotFather, get chat_id via @userinfobot",
    },
    "telegram.fill_fields": {
        "ru": "Заполните Token и Chat ID",
        "en": "Fill in Token and Chat ID",
    },
    "telegram.checking": {"ru": "Проверяю...", "en": "Checking..."},

    # ── Curator tab ────────────────────────────────────────
    "curator.title": {"ru": "👁 Уведомления куратору", "en": "👁 Curator Notifications"},
    "curator.hint": {
        "ru": (
            "Настройте второго Telegram-бота, который будет отправлять\n"
            "уведомления вашему доверенному лицу (родственнику, другу).\n"
            "Куратор получит алерты о крупных потерях, аварийных остановках\n"
            "и переключении на Live-режим."
        ),
        "en": (
            "Set up a second Telegram bot that will send notifications\n"
            "to your trusted person (relative, friend).\n"
            "The curator will receive alerts about large losses,\n"
            "emergency stops, and switching to Live mode."
        ),
    },
    "curator.enable": {
        "ru": "Включить уведомления куратору",
        "en": "Enable curator notifications",
    },
    "curator.token": {
        "ru": "Telegram Bot Token куратора",
        "en": "Curator's Telegram Bot Token",
    },
    "curator.chat_id": {"ru": "Chat ID куратора", "en": "Curator's Chat ID"},
    "curator.tip": {
        "ru": "💡 Создайте отдельного бота через @BotFather для куратора.\nКуратор получит уведомления на простом языке.",
        "en": "💡 Create a separate bot via @BotFather for the curator.\nThe curator will receive notifications in plain language.",
    },

    # ── AI tab ─────────────────────────────────────────────
    "ai.section_llm": {"ru": "LLM (Ollama)", "en": "LLM (Ollama)"},
    "ai.url": {"ru": "Ollama URL:", "en": "Ollama URL:"},
    "ai.model": {"ru": "Модель:", "en": "Model:"},
    "ai.temp": {"ru": "Temperature:", "en": "Temperature:"},
    "ai.retrain": {"ru": "Интервал обучения (час):", "en": "Retrain interval (hours):"},
    "ai.check": {"ru": "⟐  Проверить Ollama  ⟐", "en": "⟐  Check Ollama  ⟐"},
    "ai.section_ml": {"ru": "ML — Автообучение", "en": "ML — Auto-training"},
    "ai.min_samples": {"ru": "Мин. сэмплов:", "en": "Min. samples:"},
    "ai.features_window": {"ru": "Окно фич:", "en": "Feature window:"},
    "ai.checking": {"ru": "Проверяю...", "en": "Checking..."},

    # ── Risk tab ───────────────────────────────────────────
    "risk.section": {"ru": "⚖ Риск-менеджмент", "en": "⚖ Risk Management"},
    "risk.max_drawdown": {"ru": "Макс. просадка (%):", "en": "Max drawdown (%):"},
    "risk.max_position": {"ru": "Макс. позиция (% портфеля):", "en": "Max position (% portfolio):"},
    "risk.daily_loss": {"ru": "Макс. дневной убыток (%):", "en": "Daily loss limit (%):"},
    "risk.correlation": {"ru": "Макс. корреляция:", "en": "Max correlation:"},
    "risk.max_positions": {"ru": "Макс. позиций:", "en": "Max open positions:"},
    "risk.stop_loss": {"ru": "Стоп-лосс по умолчанию (%):", "en": "Default stop-loss (%):"},

    # ── Safety tab ─────────────────────────────────────────
    "safety.training": {"ru": "🛡 Режим обучения", "en": "🛡 Training Mode"},
    "safety.training_hint": {
        "ru": "Первые 14 дней система работает в Paper Trading.\nВы можете переключиться на Live раньше, приняв все риски.",
        "en": "The system runs in Paper Trading for the first 14 days.\nYou can switch to Live earlier by accepting all risks.",
    },
    "safety.training_days": {"ru": "Период обучения (дней)", "en": "Training period (days)"},
    "safety.loss_section": {"ru": "🔒 Защита от потерь", "en": "🔒 Loss Protection"},
    "safety.loss_lock": {
        "ru": "Блокировка торгов при превышении дневного лимита потерь",
        "en": "Lock trading when daily loss limit exceeded",
    },
    "safety.trade_threshold": {
        "ru": "Порог подтверждения крупных сделок (₽)",
        "en": "Large trade confirmation threshold (₽)",
    },
    "safety.pin_section": {"ru": "🔑 PIN-код для Live режима", "en": "🔑 PIN for Live Mode"},
    "safety.pin": {"ru": "PIN-код для Live режима", "en": "PIN for Live mode"},
    "safety.pin_required": {
        "ru": "Требовать PIN для переключения на Live",
        "en": "Require PIN to switch to Live",
    },
    "safety.pin_setup": {"ru": "Установить / Изменить PIN", "en": "Set / Change PIN"},
    "safety.backup_section": {"ru": "📦 Автобэкап настроек", "en": "📦 Auto-backup Settings"},
    "safety.backup": {"ru": "Автобэкап настроек", "en": "Auto-backup settings"},
    "safety.backup_auto": {
        "ru": "Автоматический бэкап при сохранении",
        "en": "Auto-backup on save",
    },
    "safety.backup_manage": {"ru": "Управление бэкапами", "en": "Manage Backups"},
    "safety.profile": {"ru": "📊 Профиль риска", "en": "📊 Risk Profile"},
    "safety.profile_hint": {
        "ru": "Выберите предустановленный профиль, который автоматически\nнастроит лимиты риска, допустимые инструменты и стоп-лоссы.",
        "en": "Choose a preset profile that will automatically\nconfigure risk limits, allowed instruments, and stop-losses.",
    },
    "safety.conservative": {"ru": "🛡 Консервативный", "en": "🛡 Conservative"},
    "safety.conservative.desc": {
        "ru": "Макс. просадка 2%, только голубые фишки, без фьючерсов",
        "en": "Max drawdown 2%, blue chips only, no futures",
    },
    "safety.moderate": {"ru": "⚖ Умеренный", "en": "⚖ Moderate"},
    "safety.moderate.desc": {
        "ru": "Макс. просадка 5%, все акции + индексные фьючерсы",
        "en": "Max drawdown 5%, all stocks + index futures",
    },
    "safety.aggressive": {"ru": "⚡ Агрессивный", "en": "⚡ Aggressive"},
    "safety.aggressive.desc": {
        "ru": "Макс. просадка 10%, все инструменты, максимум позиций",
        "en": "Max drawdown 10%, all instruments",
    },

    # ── Instruments tab ────────────────────────────────────
    "instruments.select_all": {"ru": "✦ Выбрать все", "en": "✦ Select All"},
    "instruments.deselect_all": {"ru": "✧ Снять все", "en": "✧ Deselect All"},
    "instruments.manual": {"ru": "✎ ДОБАВИТЬ ВРУЧНУЮ", "en": "✎ ADD MANUALLY"},
    "instruments.manual_hint": {
        "ru": "Введите тикеры через запятую (акции и фьючерсы).\nОни будут добавлены к выбранным выше.",
        "en": "Enter tickers separated by commas (stocks and futures).\nThey will be added to the selection above.",
    },
    "instruments.header_instrument": {"ru": "Инструмент", "en": "Instrument"},
    "instruments.risk": {"ru": "Риск", "en": "Risk"},
    "instruments.profit": {"ru": "Профит", "en": "Profit"},
    "instruments.note": {"ru": "Примечание", "en": "Note"},
    "instruments.risk_tooltip": {"ru": "Оценка риска: {}% — {}", "en": "Risk estimate: {}% — {}"},
    "instruments.profit_tooltip": {"ru": "Потенциал прибыли: {}% — {}", "en": "Profit potential: {}% — {}"},

    # Instrument notes (volatility descriptions)
    "instr.GAZP.note": {"ru": "высокая волатильность, зависит от газа/геополитики", "en": "high volatility, depends on gas/geopolitics"},
    "instr.LKOH.note": {"ru": "стабильные дивиденды, умеренный риск", "en": "stable dividends, moderate risk"},
    "instr.ROSN.note": {"ru": "госкомпания, привязка к нефти", "en": "state company, tied to oil"},
    "instr.NVTK.note": {"ru": "рост СПГ, высокий потенциал", "en": "LNG growth, high potential"},
    "instr.SNGS.note": {"ru": "валютная подушка, низкий риск", "en": "currency cushion, low risk"},
    "instr.SNGSP.note": {"ru": "высокие дивиденды при слабом рубле", "en": "high dividends with weak ruble"},
    "instr.TATN.note": {"ru": "стабильный дивидендный поток", "en": "stable dividend stream"},
    "instr.TATNP.note": {"ru": "дивидендная привилегированная", "en": "dividend preferred"},
    "instr.BANEP.note": {"ru": "дивиденды, умеренный рост", "en": "dividends, moderate growth"},
    "instr.SIBN.note": {"ru": "дочка Газпрома, стабильнее", "en": "Gazprom subsidiary, more stable"},
    "instr.SBER.note": {"ru": "голубая фишка №1, высокая ликвидность", "en": "blue chip #1, high liquidity"},
    "instr.SBERP.note": {"ru": "привилегированная, выше дивиденды", "en": "preferred, higher dividends"},
    "instr.VTBR.note": {"ru": "высокий риск, возможны допэмиссии", "en": "high risk, possible dilution"},
    "instr.TCSG.note": {"ru": "быстрый рост, высокая волатильность", "en": "fast growth, high volatility"},
    "instr.MOEX.note": {"ru": "монополия, стабильный доход", "en": "monopoly, stable income"},
    "instr.CBOM.note": {"ru": "средний банк, повышенный риск", "en": "mid-size bank, elevated risk"},
    "instr.BSPB.note": {"ru": "региональный банк", "en": "regional bank"},
    "instr.SFIN.note": {"ru": "высокая волатильность", "en": "high volatility"},
    "instr.GMKN.note": {"ru": "мировой лидер, никель/палладий", "en": "global leader, nickel/palladium"},
    "instr.NLMK.note": {"ru": "экспортёр стали, валютная выручка", "en": "steel exporter, FX revenue"},
    "instr.CHMF.note": {"ru": "дивидендный чемпион металлургии", "en": "metallurgy dividend champion"},
    "instr.MAGN.note": {"ru": "внутренний рынок стали", "en": "domestic steel market"},
    "instr.ALRS.note": {"ru": "монополия на алмазы, цикличность", "en": "diamond monopoly, cyclical"},
    "instr.RUAL.note": {"ru": "алюминий, высокая цикличность", "en": "aluminum, highly cyclical"},
    "instr.PLZL.note": {"ru": "защитный актив, золото", "en": "safe haven, gold"},
    "instr.POLY.note": {"ru": "золото/серебро, реструктуризация", "en": "gold/silver, restructuring"},
    "instr.MTLR.note": {"ru": "высокий долг = высокий риск/профит", "en": "high debt = high risk/reward"},
    "instr.MTLRP.note": {"ru": "спекулятивная, высокие дивиденды", "en": "speculative, high dividends"},
    "instr.VSMO.note": {"ru": "титан, стабильная ниша", "en": "titanium, stable niche"},
    "instr.IRAO.note": {"ru": "стабильная, низкая волатильность", "en": "stable, low volatility"},
    "instr.HYDR.note": {"ru": "госкомпания, предсказуемая", "en": "state company, predictable"},
    "instr.FEES.note": {"ru": "регулируемые тарифы", "en": "regulated tariffs"},
    "instr.MSNG.note": {"ru": "региональная энергетика", "en": "regional energy"},
    "instr.OGKB.note": {"ru": "дочка Газпром энергохолдинга", "en": "Gazprom Energoholding subsidiary"},
    "instr.TGKA.note": {"ru": "генерация, Северо-Запад", "en": "generation, Northwest"},
    "instr.UPRO.note": {"ru": "стабильные дивиденды, низкий рост", "en": "stable dividends, low growth"},
    "instr.LSNG.note": {"ru": "сетевая компания", "en": "grid company"},
    "instr.LSNGP.note": {"ru": "высокие дивиденды по уставу", "en": "high charter dividends"},
    "instr.YNDX.note": {"ru": "технологический лидер, высокий рост", "en": "tech leader, high growth"},
    "instr.MTSS.note": {"ru": "дивидендная корова, стабильно", "en": "dividend cow, stable"},
    "instr.RTKM.note": {"ru": "госоператор, медленный рост", "en": "state operator, slow growth"},
    "instr.RTKMP.note": {"ru": "дивидендная привилегированная", "en": "dividend preferred"},
    "instr.OZON.note": {"ru": "e-commerce рост, пока без прибыли", "en": "e-commerce growth, not yet profitable"},
    "instr.VKCO.note": {"ru": "соцсети, реструктуризация", "en": "social media, restructuring"},
    "instr.HHRU.note": {"ru": "монополия HR, рост", "en": "HR monopoly, growth"},
    "instr.CIAN.note": {"ru": "недвижимость онлайн", "en": "online real estate"},
    "instr.POSI.note": {"ru": "кибербезопасность, быстрый рост", "en": "cybersecurity, rapid growth"},
    "instr.MGNT.note": {"ru": "второй ритейлер, дивиденды", "en": "2nd retailer, dividends"},
    "instr.FIVE.note": {"ru": "лидер ритейла, стабильный рост", "en": "retail leader, steady growth"},
    "instr.FIXP.note": {"ru": "дискаунтер, экспансия", "en": "discounter, expansion"},
    "instr.LENT.note": {"ru": "гипермаркеты, трансформация", "en": "hypermarkets, transformation"},
    "instr.DSKY.note": {"ru": "детские товары, стабильно", "en": "children's goods, stable"},
    "instr.MVID.note": {"ru": "электроника, высокий долг", "en": "electronics, high debt"},
    "instr.AFLT.note": {"ru": "авиа, высокая цикличность", "en": "aviation, highly cyclical"},
    "instr.NMTP.note": {"ru": "порт, стабильный грузооборот", "en": "port, stable cargo turnover"},
    "instr.GLTR.note": {"ru": "ж/д перевозки, дивиденды", "en": "rail transport, dividends"},
    "instr.FLOT.note": {"ru": "танкерный флот", "en": "tanker fleet"},
    "instr.FESH.note": {"ru": "контейнерные перевозки", "en": "container shipping"},
    "instr.PIKK.note": {"ru": "лидер жилого строительства", "en": "housing construction leader"},
    "instr.SMLT.note": {"ru": "быстрый рост, высокий долг", "en": "fast growth, high debt"},
    "instr.LSRG.note": {"ru": "диверсифицированный застройщик", "en": "diversified developer"},
    "instr.ETLN.note": {"ru": "реструктуризация", "en": "restructuring"},
    "instr.PHOR.note": {"ru": "удобрения, мировой спрос", "en": "fertilizers, global demand"},
    "instr.AKRN.note": {"ru": "удобрения, экспорт", "en": "fertilizers, exports"},
    "instr.KAZT.note": {"ru": "химия, внутренний рынок", "en": "chemicals, domestic market"},
    "instr.NKNC.note": {"ru": "нефтехимия", "en": "petrochemicals"},
    "instr.AGRO.note": {"ru": "агросектор, экспорт", "en": "agro sector, exports"},
    "instr.RNFT.note": {"ru": "малая нефтянка", "en": "small oil company"},
    "instr.SGZH.note": {"ru": "лесопром, высокий долг", "en": "forestry, high debt"},
    "instr.TRNFP.note": {"ru": "монополия трубопроводов, стабильно", "en": "pipeline monopoly, stable"},
    "instr.RGSS.note": {"ru": "электросети", "en": "power grids"},
    "instr.IRKT.note": {"ru": "авиастроение, гособоронзаказ", "en": "aircraft, defense orders"},
    "instr.AQUA.note": {"ru": "аквакультура, рост рынка", "en": "aquaculture, market growth"},
    # Futures notes
    "instr.RIZ4.note": {"ru": "основной индексный фьючерс, высокое плечо", "en": "main index future, high leverage"},
    "instr.MXZ4.note": {"ru": "рублёвый индекс", "en": "ruble index"},
    "instr.MMZ4.note": {"ru": "мини-контракт, для малых депозитов", "en": "mini contract, for small deposits"},
    "instr.SiZ4.note": {"ru": "самый ликвидный фьючерс MOEX", "en": "most liquid MOEX future"},
    "instr.EuZ4.note": {"ru": "валютный хедж, средняя ликвидность", "en": "currency hedge, medium liquidity"},
    "instr.CNZ4.note": {"ru": "юань, растущая ликвидность", "en": "yuan, growing liquidity"},
    "instr.GUZ4.note": {"ru": "кросс-курс", "en": "cross rate"},
    "instr.EDZ4.note": {"ru": "кросс-курс, низкий спред", "en": "cross rate, low spread"},
    "instr.BRF5.note": {"ru": "нефть Brent, высокая волатильность", "en": "Brent oil, high volatility"},
    "instr.CLF5.note": {"ru": "нефть WTI", "en": "WTI oil"},
    "instr.NGF5.note": {"ru": "газ, экстремальная волатильность", "en": "gas, extreme volatility"},
    "instr.GDF5.note": {"ru": "дизельное топливо", "en": "diesel fuel"},
    "instr.GDZ4.note": {"ru": "защитный актив, тренд вверх", "en": "safe haven, upward trend"},
    "instr.SVZ4.note": {"ru": "промышленный + защитный металл", "en": "industrial + safe haven metal"},
    "instr.PTZ4.note": {"ru": "редкий, промышленный спрос", "en": "rare, industrial demand"},
    "instr.PDZ4.note": {"ru": "автопром, высокая волатильность", "en": "automotive, high volatility"},
    "instr.SRZ4.note": {"ru": "самый ликвидный фьючерс на акцию", "en": "most liquid stock future"},
    "instr.GZZ4.note": {"ru": "высокая волатильность", "en": "high volatility"},
    "instr.LKZ4.note": {"ru": "нефтяной сектор", "en": "oil sector"},
    "instr.RNZ4.note": {"ru": "госнефтянка", "en": "state oil company"},
    "instr.VBZ4.note": {"ru": "высокий риск, спекулятивный", "en": "high risk, speculative"},
    "instr.TRZ4.note": {"ru": "средняя волатильность", "en": "medium volatility"},
    "instr.NKZ4.note": {"ru": "металлургия", "en": "metallurgy"},
    "instr.YNZ4.note": {"ru": "IT-сектор, высокая бета", "en": "IT sector, high beta"},
    "instr.MGZ4.note": {"ru": "ритейл", "en": "retail"},
    "instr.ALZ4.note": {"ru": "алмазы", "en": "diamonds"},

    # Instrument section headers
    "instr.section.oil_gas": {"ru": "🛢 НЕФТЬ И ГАЗ", "en": "🛢 OIL & GAS"},
    "instr.section.banks": {"ru": "🏦 БАНКИ И ФИНАНСЫ", "en": "🏦 BANKS & FINANCE"},
    "instr.section.metals": {"ru": "⛏ МЕТАЛЛУРГИЯ И ДОБЫЧА", "en": "⛏ METALS & MINING"},
    "instr.section.energy": {"ru": "⚡ ЭНЕРГЕТИКА", "en": "⚡ ENERGY"},
    "instr.section.telecom": {"ru": "📡 ТЕЛЕКОМ И IT", "en": "📡 TELECOM & IT"},
    "instr.section.retail": {"ru": "🏬 РИТЕЙЛ И ПОТРЕБ.", "en": "🏬 RETAIL & CONSUMER"},
    "instr.section.transport": {"ru": "🚛 ТРАНСПОРТ", "en": "🚛 TRANSPORT"},
    "instr.section.construction": {"ru": "🏗 СТРОИТЕЛЬСТВО И НЕДВИЖ.", "en": "🏗 CONSTRUCTION & REAL ESTATE"},
    "instr.section.chemistry": {"ru": "🧪 ХИМИЯ И УДОБРЕНИЯ", "en": "🧪 CHEMISTRY & FERTILIZERS"},
    "instr.section.other": {"ru": "📦 ПРОЧИЕ АКЦИИ", "en": "📦 OTHER STOCKS"},
    "instr.section.index_futures": {"ru": "📈 ИНДЕКСНЫЕ ФЬЮЧЕРСЫ", "en": "📈 INDEX FUTURES"},
    "instr.section.fx_futures": {"ru": "💱 ВАЛЮТНЫЕ ФЬЮЧЕРСЫ", "en": "💱 FX FUTURES"},
    "instr.section.commodity_futures": {"ru": "🛢 ТОВАРНЫЕ ФЬЮЧЕРСЫ", "en": "🛢 COMMODITY FUTURES"},
    "instr.section.metal_futures": {"ru": "🥇 ДРАГ. МЕТАЛЛЫ (ФЬЮЧЕРСЫ)", "en": "🥇 PRECIOUS METALS (FUTURES)"},
    "instr.section.stock_futures": {"ru": "🏦 ФЬЮЧЕРСЫ НА АКЦИИ", "en": "🏦 STOCK FUTURES"},

    # ── Mode tab ───────────────────────────────────────────
    "mode.trading": {"ru": "Режим торговли", "en": "Trading Mode"},
    "mode.paper": {
        "ru": "Paper Trading — виртуальные сделки для тестирования",
        "en": "Paper Trading — virtual trades for testing",
    },
    "mode.live": {
        "ru": "Live Trading — реальные деньги через QUIK",
        "en": "Live Trading — real money via QUIK",
    },
    "mode.warning": {
        "ru": "⚠ ВНИМАНИЕ: Live-режим торгует на реальные деньги!\nУбедитесь, что все настройки верны и протестируйте в Paper-режиме.",
        "en": "⚠ WARNING: Live mode trades with real money!\nMake sure all settings are correct and test in Paper mode first.",
    },
    "mode.agents": {"ru": "AI-агенты", "en": "AI Agents"},
    "mode.extra": {"ru": "Дополнительно", "en": "Additional"},
    "mode.dashboard": {
        "ru": "Запустить веб-дашборд (порт 8080)",
        "en": "Launch web dashboard (port 8080)",
    },
    "mode.voice": {"ru": "Голосовые оповещения", "en": "Voice notifications"},

    # ── Buttons ────────────────────────────────────────────
    "btn.save": {"ru": "⟐  SAVE CONFIGURATION  ⟐", "en": "⟐  SAVE CONFIGURATION  ⟐"},
    "btn.launch": {"ru": "▶  LAUNCH SYSTEM  ▶", "en": "▶  LAUNCH SYSTEM  ▶"},
    "btn.cancel": {"ru": "CANCEL", "en": "CANCEL"},

    # ── Messages ───────────────────────────────────────────
    "msg.saved": {"ru": "Настройки сохранены в config/settings.yaml", "en": "Settings saved to config/settings.yaml"},
    "msg.saved_title": {"ru": "Сохранено", "en": "Saved"},
    "msg.no_telegram": {
        "ru": "Telegram-бот не настроен. Продолжить без отчётов?",
        "en": "Telegram bot not configured. Continue without reports?",
    },
    "msg.no_account": {
        "ru": "Для live-режима укажите Account ID и Client Code брокера",
        "en": "Account ID and Client Code are required for live mode",
    },
    "msg.risk_title": {"ru": "Принятие рисков", "en": "Risk Acceptance"},
    "msg.error": {"ru": "Ошибка", "en": "Error"},
    "msg.quik_wizard_fail": {
        "ru": "Не удалось запустить мастер: {}",
        "en": "Failed to launch wizard: {}",
    },
    "msg.quik_diag_title": {"ru": "Диагностика QUIK", "en": "QUIK Diagnostics"},
    "msg.quik_diag_fail": {
        "ru": "Диагностика не удалась: {}",
        "en": "Diagnostics failed: {}",
    },
    "msg.pin_fail": {
        "ru": "Не удалось настроить PIN: {}",
        "en": "Failed to set up PIN: {}",
    },
    "msg.backup_fail": {
        "ru": "Не удалось открыть менеджер бэкапов: {}",
        "en": "Failed to open backup manager: {}",
    },

    # ── Dashboard strings ──────────────────────────────────
    "dash.title": {"ru": "LUX NOX CAPITAL · MONOLITH", "en": "LUX NOX CAPITAL · MONOLITH"},
    "dash.mode": {"ru": "РЕЖИМ", "en": "MODE"},
    "dash.portfolio": {"ru": "ПОРТФЕЛЬ", "en": "PORTFOLIO"},
    "dash.positions": {"ru": "THE SACRED LEDGER — Scales of Judgement", "en": "THE SACRED LEDGER — Scales of Judgement"},
    "dash.trades": {"ru": "RECENT TRADES — The Eternal Record", "en": "RECENT TRADES — The Eternal Record"},
    "dash.agents": {"ru": "THE PANTHEON — Agent Council", "en": "THE PANTHEON — Agent Council"},
    "dash.events": {"ru": "THE ORACLE'S WHISPER — Event Chronicle", "en": "THE ORACLE'S WHISPER — Event Chronicle"},
    "dash.stop": {"ru": "⛔ СТОП", "en": "⛔ STOP"},
    "dash.health_ok": {"ru": "🟢 ЗДОРОВ", "en": "🟢 HEALTHY"},
    "dash.emergency_title": {"ru": "ЭКСТРЕННАЯ ОСТАНОВКА", "en": "EMERGENCY STOP"},
    "dash.emergency_msg": {"ru": "Все позиции будут закрыты!", "en": "All positions will be closed!"},

    # QUIK diagnostics labels
    "diag.quik_found": {"ru": "QUIK найден", "en": "QUIK found"},
    "diag.path": {"ru": "Путь", "en": "Path"},
    "diag.quik_running": {"ru": "QUIK запущен", "en": "QUIK running"},
    "diag.version": {"ru": "Версия", "en": "Version"},
    "diag.script_installed": {"ru": "Скрипт установлен", "en": "Script installed"},
    "diag.tcp_port": {"ru": "TCP порт открыт", "en": "TCP port open"},
    "diag.connection": {"ru": "Соединение", "en": "Connection"},
}


class I18n:
    """Simple i18n with RUS/ENG support."""

    _current_lang: str = _load_lang()

    @classmethod
    def set_lang(cls, lang: str) -> None:
        cls._current_lang = lang
        _save_lang(lang)

    @classmethod
    def get_lang(cls) -> str:
        return cls._current_lang

    @classmethod
    def t(cls, key: str) -> str:
        """Get translation for key. Falls back to key itself if not found."""
        entry = _TRANSLATIONS.get(key)
        if entry is None:
            return key
        return entry.get(cls._current_lang, entry.get("ru", key))


def t(key: str) -> str:
    """Shortcut for I18n.t()"""
    return I18n.t(key)
