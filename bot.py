import os
import logging
import httpx
from datetime import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Каналы для автопостинга
CHANNEL_KISLOROD = "@realtimeproductionn"
CHANNEL_ACTOR = "@actorsashapotapovv"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# ПОСТОЯННОЕ МЕНЮ СНИЗУ
# ─────────────────────────────────────────────

MENU_BUTTONS = {
    "🎭 Актёр": "actor",
    "🎬 Режиссёр": "director",
    "✍️ Сценарист": "screenwriter",
    "💼 Продюсер": "producer",
    "🤝 Заказчик": "client",
    "🌐 Общий": "general",
}

def main_menu_keyboard():
    """Постоянная клавиатура снизу экрана."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🎭 Актёр"), KeyboardButton("🎬 Режиссёр"), KeyboardButton("✍️ Сценарист")],
            [KeyboardButton("💼 Продюсер"), KeyboardButton("🤝 Заказчик"), KeyboardButton("🌐 Общий")],
        ],
        resize_keyboard=True,
        persistent=True,
    )

def inline_role_keyboard():
    """Инлайн-кнопки для выбора роли (используется при /start)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎭 Актёр", callback_data="role_actor"),
         InlineKeyboardButton("🎬 Режиссёр", callback_data="role_director")],
        [InlineKeyboardButton("✍️ Сценарист", callback_data="role_screenwriter"),
         InlineKeyboardButton("💼 Продюсер", callback_data="role_producer")],
        [InlineKeyboardButton("🤝 Заказчик", callback_data="role_client"),
         InlineKeyboardButton("🌐 Общий", callback_data="role_general")],
    ])

def back_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role"),
        InlineKeyboardButton("🗑 Очистить чат", callback_data="clear_chat"),
    ]])


# ─────────────────────────────────────────────
# РОЛИ
# ─────────────────────────────────────────────

ROLE_PROMPTS = {
    "actor": {
        "system": (
            "Ты — опытный театральный и киноактёр-наставник студии КИСЛОРОД ПРОДАКШЕН. "
            "Помогаешь актёрам готовиться к ролям: разбираешь характер персонажа, биографию, "
            "мотивацию, физические и эмоциональные состояния. "
            "Для примерки образа предлагаешь детальное описание внешнего вида, костюма, грима. "
            "Когда актёр описывает видео-пробу словами — даёшь конкретный разбор: что сильно, "
            "что слабо, как улучшить. "
            "Отвечай на русском языке. Будь вдохновляющим и точным."
        ),
        "welcome": (
            "🎭 Привет, актёр!\n\n"
            "Я твой личный AI-наставник студии КИСЛОРОД ПРОДАКШЕН.\n\n"
            "Чем могу помочь:\n"
            "- Подготовка к роли\n"
            "- Примерка образа\n"
            "- Разбор видео-проб\n"
            "- Работа с текстом сцены\n\n"
            "Над какой ролью ты сейчас работаешь?"
        ),
    },
    "director": {
        "system": (
            "Ты — креативный режиссёр-наставник студии КИСЛОРОД ПРОДАКШЕН. "
            "Помогаешь режиссёрам разрабатывать концепции, раскадровки, визуальный стиль. "
            "Предлагаешь идеи для сцен, переходов, ракурсов, цветовых решений. "
            "Отвечай на русском языке. Будь дерзким и кинематографически мыслящим."
        ),
        "welcome": (
            "🎬 Привет, режиссёр!\n\n"
            "Я твой AI-ассистент для режиссёрской работы.\n\n"
            "Помогу с:\n"
            "- Концепция и визуальный стиль\n"
            "- Раскадровка и план съёмок\n"
            "- Цветовая палитра и атмосфера\n"
            "- Режиссёрский сценарий\n\n"
            "Какой проект в работе?"
        ),
    },
    "screenwriter": {
        "system": (
            "Ты — сценарист студии КИСЛОРОД ПРОДАКШЕН. "
            "Помогаешь писать сценарии, диалоги, синопсисы. "
            "Разрабатываешь характеры персонажей и их арки развития. "
            "Предлагаешь структуры историй, конфликты, повороты. "
            "Пишешь живые кинематографические диалоги. "
            "Отвечай на русском языке. Будь литературным и глубоким."
        ),
        "welcome": (
            "✍️ Привет, сценарист!\n\n"
            "Я твой AI-соавтор для работы над историями.\n\n"
            "Создадим вместе:\n"
            "- Синопсис и структура истории\n"
            "- Характеры персонажей\n"
            "- Живые диалоги и сцены\n"
            "- Тритмент и питч-документ\n\n"
            "Какая идея требует воплощения?"
        ),
    },
    "producer": {
        "system": (
            "Ты — продюсер студии КИСЛОРОД ПРОДАКШЕН. "
            "Помогаешь с питчингом, бюджетами, тайм-менеджментом производства. "
            "Разрабатываешь тритменты, лукбуки, презентации для инвесторов. "
            "Отвечай на русском языке. Будь чётким и структурированным."
        ),
        "welcome": (
            "💼 Привет, продюсер!\n\n"
            "Я твой AI-ассистент для производственных задач.\n\n"
            "Помогу с:\n"
            "- Питч и презентация для инвесторов\n"
            "- Структура бюджета\n"
            "- Производственный план\n"
            "- Тритмент и лукбук\n\n"
            "Что за проект?"
        ),
    },
    "client": {
        "system": (
            "Ты — клиентский менеджер студии КИСЛОРОД ПРОДАКШЕН. "
            "Помогаешь заказчикам сформулировать ТЗ, бриф, креативную концепцию. "
            "Создаёшь структурированные концепт-документы и презентации. "
            "Контакты студии: actorsashapotapov@gmail.com | @actorsashapotapov. "
            "Отвечай на русском языке. Будь дружелюбным и профессиональным."
        ),
        "welcome": (
            "🤝 Привет!\n\n"
            "Я помогу воплотить вашу идею в готовый проект.\n\n"
            "Вместе создадим:\n"
            "- Техническое задание и бриф\n"
            "- Креативная концепция\n"
            "- Презентация проекта\n"
            "- Коммуникационная стратегия\n\n"
            "Расскажите о вашей задаче."
        ),
    },
    "general": {
        "system": (
            "Ты — AI-ассистент студии КИСЛОРОД ПРОДАКШЕН — творческой AI-студии, "
            "создающей мультфильмы, клипы, сериалы и рекламу. "
            "Помогаешь всем: актёрам, режиссёрам, сценаристам, продюсерам и заказчикам. "
            "Сайт: https://aliferovaaleksandr-del.github.io/kislorod-production/ "
            "Email: actorsashapotapov@gmail.com | Telegram: @actorsashapotapov. "
            "Отвечай на русском языке."
        ),
        "welcome": (
            "🌐 Добро пожаловать в КИСЛОРОД ПРОДАКШЕН!\n\n"
            "Я AI-ассистент творческой студии нового поколения.\n\n"
            "Используй кнопки меню внизу чтобы выбрать роль!"
        ),
    },
}


# ─────────────────────────────────────────────
# NEWSAPI
# ─────────────────────────────────────────────

async def fetch_news(query: str, language: str = "ru", page_size: int = 5) -> str:
    if not NEWS_API_KEY:
        return ""
    url = "https://newsapi.org/v2/everything"
    params = {"q": query, "language": language, "sortBy": "publishedAt",
               "pageSize": page_size, "apiKey": NEWS_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
        if response.status_code == 200:
            articles = response.json().get("articles", [])
            if not articles:
                params["language"] = "en"
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(url, params=params)
                articles = response.json().get("articles", [])
            news_text = ""
            for i, a in enumerate(articles[:5], 1):
                title = a.get("title", "")
                desc = a.get("description", "")
                source = a.get("source", {}).get("name", "")
                if title and title != "[Removed]":
                    news_text += f"{i}. {title}"
                    if desc and desc != "[Removed]":
                        news_text += f"\n   {desc}"
                    if source:
                        news_text += f"\n   Источник: {source}"
                    news_text += "\n\n"
            return news_text.strip()
        return ""
    except Exception as e:
        logger.error(f">>> NewsAPI exception: {e}")
        return ""


# ─────────────────────────────────────────────
# YANDEX GPT
# ─────────────────────────────────────────────

async def ask_yandex_gpt(system_prompt: str, conversation: list) -> str:
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        return "Ошибка конфигурации: не заданы переменные окружения."
    messages = [{"role": "system", "text": system_prompt}]
    for msg in conversation[-20:]:
        messages.append({"role": msg["role"], "text": msg["text"]})
    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": 1000},
        "messages": messages,
    }
    headers = {"Authorization": f"Api-Key {YANDEX_API_KEY}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                json=payload, headers=headers,
            )
        data = response.json()
        if response.status_code == 200:
            return data["result"]["alternatives"][0]["message"]["text"]
        elif response.status_code == 401:
            return "Ошибка авторизации (401). Проверь YANDEX_API_KEY."
        elif response.status_code == 403:
            return "Нет доступа (403). Проверь права сервисного аккаунта и биллинг."
        elif response.status_code == 404:
            return "Модель не найдена (404). Проверь YANDEX_FOLDER_ID."
        else:
            return f"Ошибка AI ({response.status_code}). Попробуй снова."
    except httpx.ConnectError:
        return "Не удалось подключиться к Яндекс API."
    except httpx.TimeoutException:
        return "Яндекс API не ответил за 30 секунд."
    except Exception as e:
        logger.error(f">>> EXCEPTION {type(e).__name__}: {e}")
        return "Не удалось получить ответ. Попробуй снова."


# ─────────────────────────────────────────────
# ГЕНЕРАЦИЯ ПОСТОВ
# ─────────────────────────────────────────────

async def generate_kislorod_post() -> str:
    news = await fetch_news("кино фильм актёр режиссёр кастинг", language="ru")
    if not news:
        news = await fetch_news("cinema film actor director AI movie", language="en")
    if news:
        prompt = (
            "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН (кино, искусство, актёрское мастерство).\n\n"
            f"Свежие новости из мира кино:\n{news}\n\n"
            "На основе этих новостей напиши один увлекательный пост.\n"
            "Требования: 150-250 слов, живой стиль, 1-2 эмодзи в начале, "
            "хэштеги в конце: #кино #кислородпродакшен #актёрскоемастерство\n"
            "Только текст поста на русском языке."
        )
    else:
        prompt = (
            "Напиши пост для канала КИСЛОРОД ПРОДАКШЕН о тенденциях в кино. "
            "150-250 слов, 1-2 эмодзи, хэштеги: #кино #кислородпродакшен\nТолько текст."
        )
    return await ask_yandex_gpt(prompt, [{"role": "user", "text": "Напиши пост"}])


async def generate_actor_post() -> str:
    news = await fetch_news("ИИ актёры кино искусственный интеллект", language="ru")
    if not news:
        news = await fetch_news("AI actors film casting technology", language="en")
    if news:
        prompt = (
            "Ты помогаешь актёру Александру Потапову (1986 г.р., российский киноактёр, "
            "студия КИСЛОРОД ПРОДАКШЕН) вести его личный Telegram-канал.\n\n"
            f"Свежие новости:\n{news}\n\n"
            "Напиши личный пост от имени Александра. "
            "120-200 слов, от первого лица, искренний тон, 1-2 эмодзи, "
            "хэштеги: #актёр #кино #александрпотапов #актёрскоемастерство\n"
            "Только текст поста."
        )
    else:
        prompt = (
            "Напиши личный пост от имени актёра Александра Потапова об актёрском пути. "
            "120-200 слов, от первого лица, 1-2 эмодзи. "
            "Хэштеги: #актёр #кино #александрпотапов\nТолько текст."
        )
    return await ask_yandex_gpt(prompt, [{"role": "user", "text": "Напиши пост"}])


async def generate_and_post(bot, channel: str, post_type: str):
    logger.info(f">>> Generating {post_type} post for {channel}...")
    try:
        text = await generate_kislorod_post() if post_type == "kislorod" else await generate_actor_post()
        await bot.send_message(chat_id=channel, text=text)
        logger.info(f">>> Post sent to {channel} ✅")
    except Exception as e:
        logger.error(f">>> Failed to post to {channel}: {e}")


async def job_kislorod(context: ContextTypes.DEFAULT_TYPE):
    await generate_and_post(context.bot, CHANNEL_KISLOROD, "kislorod")

async def job_actor(context: ContextTypes.DEFAULT_TYPE):
    await generate_and_post(context.bot, CHANNEL_ACTOR, "actor")


# ─────────────────────────────────────────────
# ОБРАБОТЧИКИ
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🎬 КИСЛОРОД ПРОДАКШЕН — AI АССИСТЕНТ\n\n"
        "Творческая AI-студия нового поколения.\n"
        "Мультфильмы • Клипы • Сериалы • Реклама\n\n"
        "Выбери свою роль в меню снизу 👇",
        reply_markup=main_menu_keyboard(),
    )


async def select_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик инлайн-кнопок."""
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "change_role":
        context.user_data.clear()
        await query.edit_message_text(
            "Выбери роль в меню снизу 👇",
            reply_markup=None,
        )
        return

    if action == "clear_chat":
        context.user_data["history"] = []
        await query.answer("История очищена ✅", show_alert=True)
        return

    role_key = action.replace("role_", "")
    if role_key not in ROLE_PROMPTS:
        return

    context.user_data["role"] = role_key
    context.user_data["history"] = []
    await query.edit_message_text(
        ROLE_PROMPTS[role_key]["welcome"],
        reply_markup=back_keyboard(),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if not user_text:
        return

    # Проверяем нажата ли кнопка меню
    if user_text in MENU_BUTTONS:
        role_key = MENU_BUTTONS[user_text]
        context.user_data["role"] = role_key
        context.user_data["history"] = []
        await update.message.reply_text(
            ROLE_PROMPTS[role_key]["welcome"],
            reply_markup=main_menu_keyboard(),
        )
        return

    # Обычное сообщение — отвечаем через AI
    role_key = context.user_data.get("role")
    if not role_key:
        await update.message.reply_text(
            "Выбери роль в меню снизу 👇",
            reply_markup=main_menu_keyboard(),
        )
        return

    history = context.user_data.get("history", [])
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    history.append({"role": "user", "text": user_text})
    response = await ask_yandex_gpt(ROLE_PROMPTS[role_key]["system"], history)
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]

    await update.message.reply_text(response, reply_markup=main_menu_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 КИСЛОРОД AI — Справка\n\n"
        "/start — Начать\n"
        "/clear — Очистить историю\n"
        "/post_now — Опубликовать посты сейчас (тест)\n"
        "/help — Справка\n\n"
        "Или используй кнопки меню снизу 👇\n\n"
        "Контакты:\n"
        "📧 actorsashapotapov@gmail.com\n"
        "💬 @actorsashapotapov",
        reply_markup=main_menu_keyboard(),
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("История очищена ✅", reply_markup=main_menu_keyboard())


async def post_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу свежие новости и генерирую посты...")
    await generate_and_post(context.bot, CHANNEL_KISLOROD, "kislorod")
    await generate_and_post(context.bot, CHANNEL_ACTOR, "actor")
    await update.message.reply_text("✅ Посты опубликованы в оба канала!", reply_markup=main_menu_keyboard())


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    logger.info("=== KISLOROD AI Bot starting ===")
    logger.info(f"=== BOT_TOKEN set: {bool(BOT_TOKEN)} ===")
    logger.info(f"=== YANDEX_API_KEY set: {bool(YANDEX_API_KEY)} ===")
    logger.info(f"=== YANDEX_FOLDER_ID: {YANDEX_FOLDER_ID} ===")
    logger.info(f"=== NEWS_API_KEY set: {bool(NEWS_API_KEY)} ===")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("post_now", post_now_command))
    app.add_handler(CallbackQueryHandler(select_role))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Расписание (UTC, Москва = UTC+3)
    # Кислород: 09:00, 13:00, 18:00 МСК
    app.job_queue.run_daily(job_kislorod, time=time(6, 0))
    app.job_queue.run_daily(job_kislorod, time=time(10, 0))
    app.job_queue.run_daily(job_kislorod, time=time(15, 0))
    # Александр: 10:00, 19:00 МСК
    app.job_queue.run_daily(job_actor, time=time(7, 0))
    app.job_queue.run_daily(job_actor, time=time(16, 0))

    logger.info("=== Bot running with persistent menu & NewsAPI autoposting ===")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
