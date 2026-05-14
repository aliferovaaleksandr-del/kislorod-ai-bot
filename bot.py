import os
import logging
import httpx
from datetime import time as dtime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
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

CHANNEL_KISLOROD = "@realtimeproductionn"
CHANNEL_ACTOR = "@actorsashapotapovv"

WEBAPP_URL = "https://aliferovaaleksandr-del.github.io/kislorod-ai-bot/menu.html"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# МЕНЮ
# ─────────────────────────────────────────────

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎭 Актёр", callback_data="role_actor"),
            InlineKeyboardButton("🎬 Режиссёр", callback_data="role_director"),
            InlineKeyboardButton("✍️ Сценарист", callback_data="role_screenwriter"),
        ],
        [
            InlineKeyboardButton("💼 Продюсер", callback_data="role_producer"),
            InlineKeyboardButton("🤝 Заказчик", callback_data="role_client"),
            InlineKeyboardButton("🌐 Общий", callback_data="role_general"),
        ],
    ])


def chat_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role"),
        InlineKeyboardButton("🗑 Очистить чат", callback_data="clear_chat"),
    ]])


def webapp_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📋 Меню", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


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
            "— Подготовка к роли\n"
            "— Примерка образа\n"
            "— Разбор видео-проб\n"
            "— Работа с текстом сцены\n\n"
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
            "— Концепция и визуальный стиль\n"
            "— Раскадровка и план съёмок\n"
            "— Цветовая палитра и атмосфера\n"
            "— Режиссёрский сценарий\n\n"
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
            "— Синопсис и структура истории\n"
            "— Характеры персонажей\n"
            "— Живые диалоги и сцены\n"
            "— Тритмент и питч-документ\n\n"
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
            "— Питч и презентация для инвесторов\n"
            "— Структура бюджета\n"
            "— Производственный план\n"
            "— Тритмент и лукбук\n\n"
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
            "— Техническое задание и бриф\n"
            "— Креативная концепция\n"
            "— Презентация проекта\n"
            "— Коммуникационная стратегия\n\n"
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
            "Выбери свою роль:"
        ),
    },
}


# ─────────────────────────────────────────────
# NEWSAPI — получение свежих новостей
# ─────────────────────────────────────────────

# Набор разных запросов, чтобы посты не повторялись
KISLOROD_QUERIES = [
    "кино фильм премьера",
    "режиссёр съёмки кинофестиваль",
    "мультфильм анимация студия",
    "актёр кастинг роль",
    "сериал продакшен производство",
    "реклама клип видео продакшен",
]

ACTOR_QUERIES = [
    "актёр кино новости",
    "ИИ искусственный интеллект актёры",
    "актёрское мастерство театр",
    "кастинг роль российское кино",
    "звезда кино интервью",
    "фестиваль кино наград",
]

# Счётчики для ротации запросов
_kislorod_query_index = 0
_actor_query_index = 0


async def fetch_news(query: str, language: str = "ru", page_size: int = 5) -> str:
    """Получает свежие новости через NewsAPI."""
    if not NEWS_API_KEY:
        logger.warning("NEWS_API_KEY не задан!")
        return ""

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": language,
        "sortBy": "publishedAt",
        "pageSize": page_size,
        "apiKey": NEWS_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)

        if response.status_code != 200:
            logger.error(f"NewsAPI вернул {response.status_code}: {response.text}")
            return ""

        articles = response.json().get("articles", [])

        # Если по-русски ничего нет — пробуем по-английски
        if not articles and language == "ru":
            params["language"] = "en"
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
            articles = response.json().get("articles", [])

        news_text = ""
        for i, a in enumerate(articles[:5], 1):
            title = a.get("title", "")
            desc = a.get("description", "")
            source = a.get("source", {}).get("name", "")
            published = a.get("publishedAt", "")[:10]  # только дата
            if title and title != "[Removed]":
                news_text += f"{i}. [{published}] {title}"
                if desc and desc != "[Removed]":
                    news_text += f"\n   {desc}"
                if source:
                    news_text += f"\n   Источник: {source}"
                news_text += "\n\n"

        return news_text.strip()

    except Exception as e:
        logger.error(f"NewsAPI exception: {e}")
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
        "completionOptions": {"stream": False, "temperature": 0.8, "maxTokens": 1000},
        "messages": messages,
    }
    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                json=payload,
                headers=headers,
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
        logger.error(f"YandexGPT exception {type(e).__name__}: {e}")
        return "Не удалось получить ответ. Попробуй снова."


# ─────────────────────────────────────────────
# ГЕНЕРАЦИЯ ПОСТОВ
# ─────────────────────────────────────────────

async def generate_kislorod_post() -> str:
    """Генерирует пост для канала @realtimeproductionn."""
    global _kislorod_query_index

    # Ротация запросов для разнообразия
    query = KISLOROD_QUERIES[_kislorod_query_index % len(KISLOROD_QUERIES)]
    _kislorod_query_index += 1

    logger.info(f"Ищу новости для Кислород по запросу: '{query}'")
    news = await fetch_news(query, language="ru")
    if not news:
        news = await fetch_news("cinema film production", language="en")

    if news:
        system = (
            "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. "
            "Студия создаёт мультфильмы, клипы, сериалы и рекламу с помощью AI. "
            "Пиши интересно, живо, с уважением к читателю. "
            "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown, без кавычек вокруг поста."
        )
        user_msg = (
            f"Свежие новости из мира кино и продакшена:\n\n{news}\n\n"
            "На основе этих новостей напиши один пост для Telegram-канала.\n"
            "Требования:\n"
            "— 150–250 слов\n"
            "— Живой, увлекательный стиль\n"
            "— 1–2 тематических эмодзи в начале\n"
            "— В конце хэштеги: #кино #кислородпродакшен #продакшен #актёрскоемастерство\n"
            "— Только текст поста на русском языке, без заголовка"
        )
    else:
        system = (
            "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН — творческой AI-студии. "
            "Отвечай ТОЛЬКО текстом поста."
        )
        user_msg = (
            "Напиши пост для Telegram-канала о трендах в кино и продакшене. "
            "150–250 слов, 1–2 эмодзи, хэштеги: #кино #кислородпродакшен #продакшен"
        )

    return await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])


async def generate_actor_post() -> str:
    """Генерирует пост для личного канала @actorsashapotapovv."""
    global _actor_query_index

    query = ACTOR_QUERIES[_actor_query_index % len(ACTOR_QUERIES)]
    _actor_query_index += 1

    logger.info(f"Ищу новости для актёрского канала по запросу: '{query}'")
    news = await fetch_news(query, language="ru")
    if not news:
        news = await fetch_news("actor film AI casting technology", language="en")

    if news:
        system = (
            "Ты помогаешь актёру Александру Потапову (1986 г.р.) вести его личный Telegram-канал. "
            "Александр — российский киноактёр и основатель студии КИСЛОРОД ПРОДАКШЕН. "
            "Пиши от его имени: искренне, по-человечески, с личным взглядом на профессию. "
            "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown."
        )
        user_msg = (
            f"Свежие новости из мира кино и актёрства:\n\n{news}\n\n"
            "Напиши личный пост от имени Александра Потапова.\n"
            "Требования:\n"
            "— 120–200 слов\n"
            "— От первого лица, искренний личный тон\n"
            "— Своё мнение о новостях или тема из профессиональной жизни\n"
            "— 1–2 эмодзи\n"
            "— Хэштеги в конце: #актёр #кино #александрпотапов #актёрскоемастерство\n"
            "— Только текст поста на русском языке"
        )
    else:
        system = (
            "Ты помогаешь актёру Александру Потапову вести его личный Telegram-канал. "
            "Отвечай ТОЛЬКО текстом поста."
        )
        user_msg = (
            "Напиши личный пост от имени актёра Александра Потапова об актёрском пути и профессии. "
            "120–200 слов, от первого лица, 1–2 эмодзи. "
            "Хэштеги: #актёр #кино #александрпотапов #актёрскоемастерство"
        )

    return await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])


async def generate_and_post(bot, channel: str, post_type: str):
    """Генерирует пост и отправляет в канал."""
    logger.info(f"Генерирую пост типа '{post_type}' для {channel}...")
    try:
        if post_type == "kislorod":
            text = await generate_kislorod_post()
        else:
            text = await generate_actor_post()

        if not text or text.startswith("Ошибка"):
            logger.error(f"Пост не сгенерирован: {text}")
            return

        await bot.send_message(chat_id=channel, text=text)
        logger.info(f"✅ Пост отправлен в {channel}")

    except Exception as e:
        logger.error(f"Не удалось отправить пост в {channel}: {e}")


# ─────────────────────────────────────────────
# JOB FUNCTIONS — расписание постов
# ─────────────────────────────────────────────
# Время UTC (Москва = UTC+3, поэтому вычитаем 3 часа)
#
# @realtimeproductionn — 3 поста в день:
#   10:00 МСК → 07:00 UTC
#   14:00 МСК → 11:00 UTC
#   19:00 МСК → 16:00 UTC
#
# @actorsashapotapovv — 2 поста в день:
#   11:00 МСК → 08:00 UTC
#   20:00 МСК → 17:00 UTC

async def job_kislorod_1(context: ContextTypes.DEFAULT_TYPE):
    await generate_and_post(context.bot, CHANNEL_KISLOROD, "kislorod")

async def job_kislorod_2(context: ContextTypes.DEFAULT_TYPE):
    await generate_and_post(context.bot, CHANNEL_KISLOROD, "kislorod")

async def job_kislorod_3(context: ContextTypes.DEFAULT_TYPE):
    await generate_and_post(context.bot, CHANNEL_KISLOROD, "kislorod")

async def job_actor_1(context: ContextTypes.DEFAULT_TYPE):
    await generate_and_post(context.bot, CHANNEL_ACTOR, "actor")

async def job_actor_2(context: ContextTypes.DEFAULT_TYPE):
    await generate_and_post(context.bot, CHANNEL_ACTOR, "actor")


# ─────────────────────────────────────────────
# ОБРАБОТЧИКИ TELEGRAM
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🎬 КИСЛОРОД ПРОДАКШЕН — AI АССИСТЕНТ\n\n"
        "Творческая AI-студия нового поколения.\n"
        "Мультфильмы • Клипы • Сериалы • Реклама\n\n"
        "Нажми кнопку 📋 Меню внизу экрана, чтобы выбрать роль:",
        reply_markup=webapp_keyboard(),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "change_role":
        context.user_data.clear()
        await query.edit_message_text(
            "🎬 Нажми кнопку 📋 Меню внизу, чтобы выбрать роль:",
            reply_markup=None,
        )
        return

    if action == "clear_chat":
        context.user_data["history"] = []
        role_key = context.user_data.get("role")
        if role_key and role_key in ROLE_PROMPTS:
            await query.edit_message_text(
                ROLE_PROMPTS[role_key]["welcome"] + "\n\n✅ История очищена",
                reply_markup=chat_keyboard(),
            )
        else:
            await query.answer("История очищена ✅", show_alert=True)
        return

    if action.startswith("role_"):
        role_key = action.replace("role_", "")
        if role_key not in ROLE_PROMPTS:
            return
        context.user_data["role"] = role_key
        context.user_data["history"] = []
        await query.edit_message_text(
            ROLE_PROMPTS[role_key]["welcome"],
            reply_markup=chat_keyboard(),
        )
        return


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.message.web_app_data.data.strip()
    role_key = data
    if role_key not in ROLE_PROMPTS:
        return
    context.user_data["role"] = role_key
    context.user_data["history"] = []
    await update.message.reply_text(
        ROLE_PROMPTS[role_key]["welcome"],
        reply_markup=chat_keyboard(),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if not user_text:
        return

    role_key = context.user_data.get("role")
    if not role_key:
        await update.message.reply_text(
            "Нажми кнопку 📋 Меню внизу, чтобы выбрать роль.",
            reply_markup=webapp_keyboard(),
        )
        return

    history = context.user_data.get("history", [])
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    history.append({"role": "user", "text": user_text})
    response = await ask_yandex_gpt(ROLE_PROMPTS[role_key]["system"], history)
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]
    await update.message.reply_text(response, reply_markup=chat_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 КИСЛОРОД AI — Справка\n\n"
        "/start — Начать и открыть меню\n"
        "/clear — Очистить историю чата\n"
        "/post_now — Опубликовать посты сейчас (тест)\n"
        "/schedule — Расписание автопостинга\n"
        "/help — Справка\n\n"
        "Контакты:\n"
        "📧 actorsashapotapov@gmail.com\n"
        "💬 @actorsashapotapov",
        reply_markup=webapp_keyboard(),
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text(
        "✅ История очищена. Нажми 📋 Меню чтобы выбрать роль:",
        reply_markup=webapp_keyboard(),
    )


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает расписание автопостинга."""
    await update.message.reply_text(
        "📅 Расписание автопостинга (МСК):\n\n"
        "📺 @realtimeproductionn — 3 поста в день:\n"
        "   🕙 10:00 — новости кино и продакшена\n"
        "   🕑 14:00 — тренды и индустрия\n"
        "   🕖 19:00 — вечерний дайджест\n\n"
        "🎭 @actorsashapotapovv — 2 поста в день:\n"
        "   🕚 11:00 — утренний пост от Александра\n"
        "   🕗 20:00 — вечерний пост от Александра\n\n"
        "Всего: 5 постов в день на основе свежих новостей NewsAPI 📰"
    )


async def post_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая публикация постов немедленно."""
    await update.message.reply_text(
        "⏳ Ищу свежие новости и генерирую посты...\n"
        "Это займёт ~15–30 секунд."
    )
    await generate_and_post(context.bot, CHANNEL_KISLOROD, "kislorod")
    await generate_and_post(context.bot, CHANNEL_ACTOR, "actor")
    await update.message.reply_text("✅ Посты опубликованы в оба канала!")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    logger.info("=== KISLOROD AI Bot starting ===")
    logger.info(f"BOT_TOKEN:       {'✅ задан' if BOT_TOKEN else '❌ НЕ ЗАДАН'}")
    logger.info(f"YANDEX_API_KEY:  {'✅ задан' if YANDEX_API_KEY else '❌ НЕ ЗАДАН'}")
    logger.info(f"YANDEX_FOLDER_ID: {YANDEX_FOLDER_ID or '❌ НЕ ЗАДАН'}")
    logger.info(f"NEWS_API_KEY:    {'✅ задан' if NEWS_API_KEY else '❌ НЕ ЗАДАН'}")

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("post_now", post_now_command))

    # Колбэки и сообщения
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ─── Расписание автопостинга (UTC) ───
    # @realtimeproductionn: 10:00, 14:00, 19:00 МСК → 07:00, 11:00, 16:00 UTC
    app.job_queue.run_daily(job_kislorod_1, time=dtime(7, 0))
    app.job_queue.run_daily(job_kislorod_2, time=dtime(11, 0))
    app.job_queue.run_daily(job_kislorod_3, time=dtime(16, 0))

    # @actorsashapotapovv: 11:00, 20:00 МСК → 08:00, 17:00 UTC
    app.job_queue.run_daily(job_actor_1, time=dtime(8, 0))
    app.job_queue.run_daily(job_actor_2, time=dtime(17, 0))

    logger.info("=== Расписание: Кислород 07/11/16 UTC | Актёр 08/17 UTC ===")
    logger.info("=== Bot запущен! ===")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
