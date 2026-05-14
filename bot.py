import os
import logging
import random
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
KINOPOISK_API_KEY = os.getenv("KINOPOISK_API_KEY")  # токен с kinopoisk.dev

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


async def fetch_news(query: str, language: str = "ru", page_size: int = 5) -> tuple[str, str]:
    """
    Получает свежие новости через NewsAPI.
    Возвращает кортеж: (текст_новостей, url_картинки_или_пустая_строка).
    Картинка берётся из первой статьи у которой есть urlToImage.
    """
    if not NEWS_API_KEY:
        logger.warning("NEWS_API_KEY не задан!")
        return "", ""

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
            return "", ""

        articles = response.json().get("articles", [])

        # Если по-русски ничего нет — пробуем по-английски
        if not articles and language == "ru":
            params["language"] = "en"
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
            articles = response.json().get("articles", [])

        news_text = ""
        image_url = ""

        for i, a in enumerate(articles[:5], 1):
            title = a.get("title", "")
            desc = a.get("description", "")
            source = a.get("source", {}).get("name", "")
            published = a.get("publishedAt", "")[:10]
            img = a.get("urlToImage", "") or ""

            # Берём картинку из первой подходящей статьи
            if not image_url and img and img.startswith("http"):
                image_url = img

            if title and title != "[Removed]":
                news_text += f"{i}. [{published}] {title}"
                if desc and desc != "[Removed]":
                    news_text += f"\n   {desc}"
                if source:
                    news_text += f"\n   Источник: {source}"
                news_text += "\n\n"

        return news_text.strip(), image_url

    except Exception as e:
        logger.error(f"NewsAPI exception: {e}")
        return "", ""


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

async def generate_kislorod_post() -> tuple:
    """Возвращает (текст, image_url) для @realtimeproductionn."""
    global _kislorod_query_index
    query = KISLOROD_QUERIES[_kislorod_query_index % len(KISLOROD_QUERIES)]
    _kislorod_query_index += 1

    logger.info(f"Кислород: новости по запросу '{query}'")
    news, image_url = await fetch_news(query, language="ru")
    if not news:
        news, image_url = await fetch_news("cinema film production", language="en")

    if news:
        system = (
            "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. "
            "Студия создаёт мультфильмы, клипы, сериалы и рекламу с помощью AI. "
            "Пиши интересно, живо, с уважением к читателю. "
            "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown, без кавычек."
        )
        user_msg = (
            f"Свежие новости из мира кино и продакшена:\n\n{news}\n\n"
            "На основе этих новостей напиши один пост для Telegram-канала.\n"
            "Требования:\n"
            "— 150–250 слов\n"
            "— Живой, увлекательный стиль\n"
            "— 1–2 тематических эмодзи в начале\n"
            "— Хэштеги в конце: #кино #кислородпродакшен #продакшен #актёрскоемастерство\n"
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

    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, image_url


async def generate_actor_post() -> tuple:
    """Возвращает (текст, image_url) для @actorsashapotapovv."""
    global _actor_query_index
    query = ACTOR_QUERIES[_actor_query_index % len(ACTOR_QUERIES)]
    _actor_query_index += 1

    logger.info(f"Актёр: новости по запросу '{query}'")
    news, image_url = await fetch_news(query, language="ru")
    if not news:
        news, image_url = await fetch_news("actor film AI casting technology", language="en")

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
            "— Своё мнение или тема из профессиональной жизни\n"
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
            "Напиши личный пост от имени актёра Александра Потапова об актёрском пути. "
            "120–200 слов, от первого лица, 1–2 эмодзи. "
            "Хэштеги: #актёр #кино #александрпотапов #актёрскоемастерство"
        )

    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, image_url


async def fetch_kinopoisk_trailer() -> dict:
    """
    Получает случайный свежий фильм из Кинопоиска с трейлером.
    Возвращает: {title, description, poster_url, trailer_url, year, genres}
    или {} если ничего не нашёл.
    """
    if not KINOPOISK_API_KEY:
        logger.warning("KINOPOISK_API_KEY не задан!")
        return {}

    headers = {"X-API-KEY": KINOPOISK_API_KEY, "accept": "application/json"}
    base    = "https://api.kinopoisk.dev/v1.4"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # Чередуем подборки для разнообразия
            sort_options = [
                ("votes.imdb", "2024-2025"),
                ("rating.kp",  "2023-2025"),
                ("votes.kp",   "2025"),
            ]
            sort_field, year = random.choice(sort_options)

            r = await client.get(
                f"{base}/movie",
                params={
                    "type":          "movie",
                    "year":          year,
                    "sortField":     sort_field,
                    "sortType":      "-1",
                    "limit":         20,
                    "notNullFields": "videos.trailers.url",
                },
                headers=headers,
            )

            if r.status_code != 200:
                logger.error(f"Kinopoisk {r.status_code}: {r.text[:300]}")
                return {}

            movies = r.json().get("docs", [])
            if not movies:
                logger.warning("Кинопоиск: пустой список фильмов")
                return {}

            movie = random.choice(movies[:10])

            title       = movie.get("name") or movie.get("alternativeName") or "Без названия"
            description = movie.get("description") or movie.get("shortDescription") or ""
            year_val    = movie.get("year", "")
            poster_url  = (movie.get("poster") or {}).get("url", "")
            genres      = ", ".join(
                g["name"] for g in (movie.get("genres") or [])[:3] if g.get("name")
            )

            # Ищем трейлер (предпочитаем YouTube)
            trailer_url = ""
            trailers = (movie.get("videos") or {}).get("trailers") or []
            for t in trailers:
                url = t.get("url", "")
                if "youtube.com" in url or "youtu.be" in url:
                    trailer_url = url
                    break
            if not trailer_url and trailers:
                trailer_url = trailers[0].get("url", "")

            if not trailer_url:
                logger.warning(f"Для '{title}' нет трейлера")
                return {}

            return {
                "title":       title,
                "description": description,
                "poster_url":  poster_url,
                "trailer_url": trailer_url,
                "year":        year_val,
                "genres":      genres,
            }

    except Exception as e:
        logger.error(f"Kinopoisk exception: {e}")
        return {}


async def generate_trailer_post() -> tuple:
    """Возвращает (текст, poster_url) для поста с трейлером."""
    logger.info("Трейлер: запрашиваю фильм из Кинопоиска...")
    movie = await fetch_kinopoisk_trailer()

    if not movie:
        return "", ""

    system = (
        "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. "
        "Пишешь анонс трейлера — интригующе, с любовью к кино. "
        "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown."
    )
    user_msg = (
        f"Фильм: «{movie['title']}» ({movie['year']})\n"
        f"Жанры: {movie['genres']}\n"
        f"Описание: {movie['description']}\n\n"
        "Напиши анонс-пост для Telegram-канала.\n"
        "Требования:\n"
        "— 80–120 слов\n"
        "— Интригующий стиль, заинтересуй читателя\n"
        "— 1–2 эмодзи в начале\n"
        f"— В конце отдельной строкой: ▶️ Смотреть трейлер: {movie['trailer_url']}\n"
        "— Хэштеги: #трейлер #кино #кислородпродакшен\n"
        "— Только текст поста на русском языке"
    )

    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, movie["poster_url"]


async def send_post(bot, channel: str, text: str, image_url: str = ""):
    """Отправляет пост. С фото если есть image_url, иначе текст."""
    if not text or text.startswith("Ошибка"):
        logger.error(f"Некорректный текст поста: {text[:80]}")
        return
    try:
        if image_url:
            try:
                await bot.send_photo(chat_id=channel, photo=image_url, caption=text)
                logger.info(f"✅ Фото+текст → {channel}")
                return
            except Exception as e:
                logger.warning(f"Фото не отправилось ({e}), отправляю текст")
        await bot.send_message(chat_id=channel, text=text)
        logger.info(f"✅ Текст → {channel}")
    except Exception as e:
        logger.error(f"Ошибка отправки в {channel}: {e}")


# ─────────────────────────────────────────────
# JOB FUNCTIONS — расписание
# ─────────────────────────────────────────────
# МСК = UTC+3
# @realtimeproductionn: 10:00 (07 UTC) новости | 14:00 (11 UTC) трейлер | 19:00 (16 UTC) новости
# @actorsashapotapovv:  11:00 (08 UTC) актёр   | 20:00 (17 UTC) актёр

async def job_kislorod_morning(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_kislorod_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text, img)

async def job_kislorod_trailer(context: ContextTypes.DEFAULT_TYPE):
    text, poster = await generate_trailer_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, poster)
    else:
        # Fallback — обычный пост если Кинопоиск недоступен
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)

async def job_kislorod_evening(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_kislorod_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text, img)

async def job_actor_morning(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_actor_post()
    await send_post(context.bot, CHANNEL_ACTOR, text, img)

async def job_actor_evening(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_actor_post()
    await send_post(context.bot, CHANNEL_ACTOR, text, img)


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
        "/start        — Открыть меню\n"
        "/clear        — Очистить историю чата\n"
        "/post_now     — Опубликовать новостные посты (тест)\n"
        "/trailer_now  — Опубликовать трейлер (тест)\n"
        "/schedule     — Расписание автопостинга\n"
        "/help         — Справка\n\n"
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
    await update.message.reply_text(
        "📅 Расписание автопостинга (МСК):\n\n"
        "📺 @realtimeproductionn — 3 поста в день:\n"
        "   🕙 10:00 — новости кино и продакшена 📰\n"
        "   🕑 14:00 — трейлер фильма (Кинопоиск) 🎬\n"
        "   🕖 19:00 — вечерний дайджест 📰\n\n"
        "🎭 @actorsashapotapovv — 2 поста в день:\n"
        "   🕚 11:00 — утренний пост от Александра\n"
        "   🕗 20:00 — вечерний пост от Александра\n\n"
        "Всего: 5 постов в день\n"
        "Источники: NewsAPI 📰 + Кинопоиск 🎬"
    )


async def post_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Генерирую новостные посты (~20 сек)...")
    text1, img1 = await generate_kislorod_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text1, img1)
    text2, img2 = await generate_actor_post()
    await send_post(context.bot, CHANNEL_ACTOR, text2, img2)
    await update.message.reply_text("✅ Новостные посты опубликованы!")


async def trailer_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу свежий трейлер в Кинопоиске (~15 сек)...")
    text, poster = await generate_trailer_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, poster)
        await update.message.reply_text("✅ Трейлер опубликован в @realtimeproductionn!")
    else:
        await update.message.reply_text(
            "❌ Не удалось получить трейлер.\n"
            "Проверь KINOPOISK_API_KEY в переменных Railway."
        )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    logger.info("=== KISLOROD AI Bot starting ===")
    logger.info(f"BOT_TOKEN:         {'✅' if BOT_TOKEN        else '❌ НЕ ЗАДАН'}")
    logger.info(f"YANDEX_API_KEY:    {'✅' if YANDEX_API_KEY   else '❌ НЕ ЗАДАН'}")
    logger.info(f"YANDEX_FOLDER_ID:  {YANDEX_FOLDER_ID         or  '❌ НЕ ЗАДАН'}")
    logger.info(f"NEWS_API_KEY:      {'✅' if NEWS_API_KEY      else '❌ НЕ ЗАДАН'}")
    logger.info(f"KINOPOISK_API_KEY: {'✅' if KINOPOISK_API_KEY else '❌ НЕ ЗАДАН'}")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("help",        help_command))
    app.add_handler(CommandHandler("clear",       clear_command))
    app.add_handler(CommandHandler("schedule",    schedule_command))
    app.add_handler(CommandHandler("post_now",    post_now_command))
    app.add_handler(CommandHandler("trailer_now", trailer_now_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Расписание (UTC = МСК − 3)
    app.job_queue.run_daily(job_kislorod_morning, time=dtime(7,  0))  # 10:00 МСК
    app.job_queue.run_daily(job_kislorod_trailer, time=dtime(11, 0))  # 14:00 МСК
    app.job_queue.run_daily(job_kislorod_evening, time=dtime(16, 0))  # 19:00 МСК
    app.job_queue.run_daily(job_actor_morning,    time=dtime(8,  0))  # 11:00 МСК
    app.job_queue.run_daily(job_actor_evening,    time=dtime(17, 0))  # 20:00 МСК

    logger.info("=== Расписание: Кислород 07/11/16 UTC | Актёр 08/17 UTC ===")
    logger.info("=== Bot запущен! ===")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
