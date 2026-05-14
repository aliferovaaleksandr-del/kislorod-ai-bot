import os
import asyncio
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
KINOPOISK_API_KEY = os.getenv("KINOPOISK_API_KEY")

CHANNEL_KISLOROD = "@realtimeproductionn"
CHANNEL_ACTOR = "@actorsashapotapovv"

WEBAPP_URL = "https://aliferovaaleksandr-del.github.io/kislorod-ai-bot/menu.html"

# ─────────────────────────────────────────────
# ЗАЩИТА: только эти user_id могут использовать
# команды постинга и служебные команды
# ─────────────────────────────────────────────
ADMIN_IDS = {8780881836}


def admin_only(func):
    """Декоратор: ограничивает команду только для администраторов."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                "⛔ У вас нет доступа к этой команде."
            )
            logger.warning(f"Попытка доступа к admin-команде от user_id={user_id}")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


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


# Подсказки-кнопки для каждой роли
ROLE_HINTS = {
    "actor": [
        ("🎭 Подготовь меня к роли", "hint_actor_1"),
        ("🪞 Помоги примерить образ", "hint_actor_2"),
        ("🎬 Разбери мою видео-пробу", "hint_actor_3"),
        ("📄 Разбери текст сцены", "hint_actor_4"),
    ],
    "director": [
        ("🎨 Придумай визуальный стиль", "hint_director_1"),
        ("🎞 Помоги со раскадровкой", "hint_director_2"),
        ("🌈 Подбери цветовую палитру", "hint_director_3"),
        ("💡 Идеи для открывающей сцены", "hint_director_4"),
    ],
    "screenwriter": [
        ("📖 Придумай структуру истории", "hint_screen_1"),
        ("💬 Напиши живой диалог", "hint_screen_2"),
        ("🧠 Разработай характер героя", "hint_screen_3"),
        ("🔀 Придумай неожиданный поворот", "hint_screen_4"),
    ],
    "producer": [
        ("📊 Помоги составить бюджет", "hint_prod_1"),
        ("🎤 Напиши питч для инвестора", "hint_prod_2"),
        ("📅 Составь производственный план", "hint_prod_3"),
        ("📋 Сделай тритмент проекта", "hint_prod_4"),
    ],
    "client": [
        ("📝 Помоги написать ТЗ", "hint_client_1"),
        ("💡 Разработай креативную концепцию", "hint_client_2"),
        ("📣 Придумай коммуникационную стратегию", "hint_client_3"),
        ("🖼 Опиши идею для ролика", "hint_client_4"),
    ],
    "general": [
        ("🎬 Что умеет студия КИСЛОРОД?", "hint_gen_1"),
        ("📞 Как связаться со студией?", "hint_gen_2"),
        ("💼 Хочу заказать проект", "hint_gen_3"),
        ("🤖 Как AI помогает в кино?", "hint_gen_4"),
    ],
}

# Тексты подсказок — что отправить в GPT при нажатии кнопки
HINT_TEXTS = {
    "hint_actor_1": "Помоги мне подготовиться к новой роли. Спроси меня о персонаже и дай план подготовки.",
    "hint_actor_2": "Помоги примерить образ персонажа: опиши внешность, костюм, грим и манеру поведения.",
    "hint_actor_3": "Я хочу разобрать свою видео-пробу. Спроси меня что я делал в пробе и дай разбор.",
    "hint_actor_4": "Помоги разобрать текст сцены: мотивация персонажа, подтекст, как это сыграть.",
    "hint_director_1": "Помоги разработать визуальный стиль для моего проекта. Спроси о жанре и атмосфере.",
    "hint_director_2": "Помоги составить раскадровку для ключевой сцены. Спроси меня о сцене.",
    "hint_director_3": "Подбери цветовую палитру и операторские решения для моего проекта.",
    "hint_director_4": "Придумай варианты открывающей сцены для моего проекта. Спроси о жанре.",
    "hint_screen_1": "Помоги выстроить трёхактную структуру для моей истории. Спроси об идее.",
    "hint_screen_2": "Напиши живой диалог между двумя персонажами. Спроси меня о ситуации.",
    "hint_screen_3": "Помоги разработать детальный характер главного героя с арком развития.",
    "hint_screen_4": "Придумай неожиданный сюжетный поворот для моей истории. Спроси об идее.",
    "hint_prod_1": "Помоги составить примерный бюджет для короткометражного фильма.",
    "hint_prod_2": "Напиши убедительный питч для инвестора. Спроси о проекте.",
    "hint_prod_3": "Помоги составить производственный план и тайминг для съёмочного проекта.",
    "hint_prod_4": "Напиши тритмент проекта в профессиональном формате. Спроси об идее.",
    "hint_client_1": "Помоги написать техническое задание для видеопроекта. Спроси о задаче.",
    "hint_client_2": "Разработай креативную концепцию для моего проекта. Спроси о бренде и задаче.",
    "hint_client_3": "Придумай коммуникационную стратегию для продвижения проекта.",
    "hint_client_4": "Помоги описать идею для рекламного или имиджевого ролика.",
    "hint_gen_1": "Расскажи подробно что умеет студия КИСЛОРОД ПРОДАКШЕН и какие проекты делает.",
    "hint_gen_2": "Как связаться со студией КИСЛОРОД ПРОДАКШЕН чтобы обсудить проект?",
    "hint_gen_3": "Я хочу заказать проект в студии КИСЛОРОД ПРОДАКШЕН. С чего начать?",
    "hint_gen_4": "Как искусственный интеллект используется в современном кинопроизводстве?",
}


def hints_keyboard(role_key: str) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру с подсказками для конкретной роли + кнопки управления."""
    hints = ROLE_HINTS.get(role_key, [])
    rows = []
    # По 2 подсказки в ряд
    for i in range(0, len(hints), 2):
        row = [InlineKeyboardButton(hints[i][0], callback_data=hints[i][1])]
        if i + 1 < len(hints):
            row.append(InlineKeyboardButton(hints[i + 1][0], callback_data=hints[i + 1][1]))
        rows.append(row)
    # Кнопки управления внизу
    rows.append([
        InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role"),
        InlineKeyboardButton("🗑 Очистить чат", callback_data="clear_chat"),
    ])
    return InlineKeyboardMarkup(rows)


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
# NEWSAPI
# ─────────────────────────────────────────────

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

_kislorod_query_index = 0
_actor_query_index = 0


async def fetch_news(query: str, language: str = "ru", page_size: int = 5) -> tuple[str, str]:
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
# YANDEX GPT — с retry и backoff
# ─────────────────────────────────────────────

async def ask_yandex_gpt(system_prompt: str, conversation: list, retries: int = 3) -> str:
    """
    Отправляет запрос к Yandex GPT.
    При ошибках 429/500/503 делает до `retries` попыток с экспоненциальным backoff.
    Возвращает текст ответа или понятное сообщение об ошибке.
    """
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

    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                    json=payload,
                    headers=headers,
                )
            data = response.json()

            if response.status_code == 200:
                text = data["result"]["alternatives"][0]["message"]["text"].strip()
                if not text:
                    # Пустой ответ — возвращаем fallback
                    logger.warning("Yandex GPT вернул пустой ответ")
                    return "Не смог сформулировать ответ. Попробуй переформулировать вопрос."
                return text

            elif response.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"Yandex GPT 429, попытка {attempt}/{retries}, жду {wait}с")
                last_error = "Слишком много запросов — попробуй через минуту."
                await asyncio.sleep(wait)

            elif response.status_code in (500, 503):
                wait = 2 ** attempt
                logger.warning(f"Yandex GPT {response.status_code}, попытка {attempt}/{retries}, жду {wait}с")
                last_error = "Сервис временно недоступен."
                await asyncio.sleep(wait)

            elif response.status_code == 401:
                return "Ошибка авторизации (401). Проверь YANDEX_API_KEY."
            elif response.status_code == 403:
                return "Нет доступа (403). Проверь права сервисного аккаунта и биллинг."
            elif response.status_code == 404:
                return "Модель не найдена (404). Проверь YANDEX_FOLDER_ID."
            else:
                return f"Ошибка AI ({response.status_code}). Попробуй снова."

        except httpx.ConnectError:
            last_error = "Не удалось подключиться к Яндекс API."
            logger.error(f"ConnectError, попытка {attempt}/{retries}")
            await asyncio.sleep(2 ** attempt)
        except httpx.TimeoutException:
            last_error = "Яндекс API не ответил за 30 секунд."
            logger.error(f"TimeoutException, попытка {attempt}/{retries}")
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            logger.error(f"YandexGPT exception {type(e).__name__}: {e}")
            return "Не удалось получить ответ. Попробуй снова."

    # Все попытки исчерпаны
    logger.error(f"Yandex GPT: все {retries} попытки провалились. Последняя ошибка: {last_error}")
    return f"⚠️ {last_error} Попробуй чуть позже."


# ─────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНАЯ: продление индикатора "печатает"
# ─────────────────────────────────────────────

async def keep_typing(bot, chat_id: int, stop_event: asyncio.Event):
    """
    Каждые 4 секунды отправляет typing action пока не установлен stop_event.
    Запускать через asyncio.create_task().
    """
    from telegram.constants import ChatAction
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        await asyncio.sleep(4)


# ─────────────────────────────────────────────
# ГЕНЕРАЦИЯ ПОСТОВ — НОВОСТИ
# ─────────────────────────────────────────────

async def generate_kislorod_post() -> tuple:
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


# ─────────────────────────────────────────────
# ФИЛЬМОГРАФИЯ
# ─────────────────────────────────────────────

FILMOGRAPHY = [
    {"title": "Эльбрус", "year": "2026", "role": "Гога", "type": "сериал", "note": "последняя работа, 2-й сезон"},
    {"title": "Пять копеек", "year": "2024", "role": "сержант", "type": "сериал", "note": "комедийный сериал"},
    {"title": "Наш спецназ", "year": "2022", "role": "Сократ", "type": "сериал", "note": "рейтинг 8.0"},
    {"title": "Друг на час", "year": "2022", "role": "клиент Рокета", "type": "сериал", "note": "ТНТ, рейтинг 7.1"},
    {"title": "Казнь", "year": "2021", "role": "криминалист", "type": "сериал", "note": "детектив, рейтинг 7.4"},
    {"title": "Хорошие вещи", "year": "2021", "role": "", "type": "фильм", "note": "фестивальное кино"},
    {"title": "Мятеж", "year": "2020", "role": "мародёр", "type": "сериал", "note": "драма, рейтинг 8.4"},
    {"title": "Ваш Ваня", "year": "2020", "role": "", "type": "сериал", "note": "рейтинг 7.1"},
    {"title": "Фемида видит", "year": "2019", "role": "оперативник", "type": "сериал", "note": "рейтинг 6.7"},
    {"title": "Короче", "year": "2019–2021", "role": "", "type": "сериал", "note": "комедия, рейтинг 7.6"},
    {"title": "Полярный", "year": "2019", "role": "бармен", "type": "сериал", "note": "рейтинг 8.2, продолжается"},
    {"title": "Трудные подростки", "year": "2019–2024", "role": "Гарик", "type": "сериал", "note": "рейтинг 8.2"},
    {"title": "Ключи", "year": "2018", "role": "", "type": "фильм", "note": ""},
    {"title": "Полицейский с Рублёвки. Мы тебя найдём", "year": "2018", "role": "Степа", "type": "сериал", "note": "ТНТ, рейтинг 7.5"},
    {"title": "Оптимисты", "year": "2017", "role": "хулиган", "type": "сериал", "note": "Россия-1, рейтинг 7.9"},
    {"title": "Четвертая смена", "year": "2017", "role": "сотрудник аварийной службы", "type": "сериал", "note": "НТВ, рейтинг 7.4"},
    {"title": "Полицейский с Рублёвки в Бескудниково", "year": "2017", "role": "гопник", "type": "сериал", "note": "рейтинг 7.9"},
    {"title": "Охота на дьявола", "year": "2017", "role": "", "type": "сериал", "note": "рейтинг 7.8"},
]

_filmography_index = 0


async def generate_filmography_post() -> tuple:
    global _filmography_index
    project = FILMOGRAPHY[_filmography_index % len(FILMOGRAPHY)]
    _filmography_index += 1

    role_str = f", роль: {project['role']}" if project["role"] else ""
    note_str = f" ({project['note']})" if project["note"] else ""

    logger.info(f"Фильмография: пост о «{project['title']}» ({project['year']})")

    system = (
        "Ты помогаешь актёру Александру Потапову (19 декабря 1986 г.р.) вести его личный Telegram-канал. "
        "Александр — российский киноактёр, сыгравший в 18 проектах, и основатель студии КИСЛОРОД ПРОДАКШЕН. "
        "Пиши от его имени: искренне, по-человечески, с личным взглядом изнутри профессии. "
        "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown."
    )
    user_msg = (
        f"Напиши личный пост от имени Александра Потапова о его работе в проекте:\n\n"
        f"Название: «{project['title']}»\n"
        f"Год: {project['year']}\n"
        f"Тип: {project['type']}{note_str}\n"
        f"Роль{role_str}\n\n"
        "Требования:\n"
        "— 120–180 слов\n"
        "— От первого лица, живо и искренне\n"
        "— Расскажи что-то личное об этом проекте: что запомнилось, чему научил, "
        "какие эмоции были на съёмках, что было сложно или интересно\n"
        "— Если роль указана — упомяни её\n"
        "— 1–2 эмодзи\n"
        "— Хэштеги в конце: #актёр #александрпотапов #кино "
        f"#{project['title'].replace(' ', '').replace('–', '').replace('.', '').lower()}\n"
        "— Только текст поста на русском языке"
    )

    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, ""


# ─────────────────────────────────────────────
# КИНОПОИСК — вспомогательные функции
# ─────────────────────────────────────────────

KINOPOISK_BASE = "https://kinopoiskapiunofficial.tech"


def _kp_headers() -> dict:
    return {
        "X-API-KEY": KINOPOISK_API_KEY or "",
        "Content-Type": "application/json",
    }


async def _kp_get_film_detail(client: httpx.AsyncClient, film_id: int) -> dict:
    r = await client.get(f"{KINOPOISK_BASE}/api/v2.2/films/{film_id}", headers=_kp_headers())
    return r.json() if r.status_code == 200 else {}


async def _kp_get_videos(client: httpx.AsyncClient, film_id: int) -> str:
    rv = await client.get(f"{KINOPOISK_BASE}/api/v2.2/films/{film_id}/videos", headers=_kp_headers())
    if rv.status_code != 200:
        return ""
    videos = rv.json().get("items", [])
    for v in videos:
        url = v.get("url", "")
        site = v.get("site", "")
        name = (v.get("name") or "").lower()
        if site == "YOUTUBE" and "трейлер" in name:
            return url
    for v in videos:
        if v.get("site") == "YOUTUBE":
            return v.get("url", "")
    return videos[0].get("url", "") if videos else ""


async def _kp_fetch_top_films(client: httpx.AsyncClient, top_type: str, page: int) -> list:
    r = await client.get(
        f"{KINOPOISK_BASE}/api/v2.2/films/top",
        headers=_kp_headers(),
        params={"type": top_type, "page": page},
    )
    if r.status_code == 402:
        logger.error("Kinopoisk: лимит запросов (402)")
        return []
    if r.status_code != 200:
        logger.error(f"Kinopoisk top {r.status_code}: {r.text[:200]}")
        return []
    return r.json().get("films", [])


async def _kp_fetch_films_by_genre(
    client: httpx.AsyncClient,
    genre_id: int,
    order: str = "RATING",
    film_type: str = "FILM",
    page: int = 1,
) -> list:
    r = await client.get(
        f"{KINOPOISK_BASE}/api/v2.2/films",
        headers=_kp_headers(),
        params={
            "genres": genre_id,
            "order": order,
            "type": film_type,
            "ratingFrom": 6,
            "ratingTo": 10,
            "page": page,
        },
    )
    if r.status_code == 402:
        logger.error("Kinopoisk: лимит запросов (402)")
        return []
    if r.status_code != 200:
        logger.error(f"Kinopoisk films {r.status_code}: {r.text[:200]}")
        return []
    return r.json().get("items", [])


def _extract_film_base(film: dict) -> dict:
    film_id = film.get("filmId") or film.get("kinopoiskId")
    title = film.get("nameRu") or film.get("nameEn") or "Без названия"
    year = film.get("year", "")
    poster_url = film.get("posterUrlPreview") or film.get("posterUrl") or ""
    genres = ", ".join(g["genre"] for g in (film.get("genres") or [])[:3] if g.get("genre"))
    return {"id": film_id, "title": title, "year": year, "poster": poster_url, "genres": genres}


# ─────────────────────────────────────────────
# КИНОПОИСК — трейлер, сериал, новинка, мультфильм, постер
# ─────────────────────────────────────────────

async def fetch_kinopoisk_trailer() -> dict:
    if not KINOPOISK_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            top_type = random.choice(["TOP_250_BEST_FILMS", "TOP_100_POPULAR_FILMS"])
            page = random.randint(1, 5)
            films = await _kp_fetch_top_films(client, top_type, page)
            if not films:
                return {}
            random.shuffle(films)
            for film in films[:10]:
                base = _extract_film_base(film)
                if not base["id"]:
                    continue
                detail = await _kp_get_film_detail(client, base["id"])
                description = detail.get("description") or detail.get("shortDescription") or ""
                poster_url = detail.get("posterUrl") or base["poster"]
                trailer_url = await _kp_get_videos(client, base["id"])
                if not trailer_url:
                    continue
                return {
                    "title": base["title"], "description": description,
                    "poster_url": poster_url, "trailer_url": trailer_url,
                    "year": base["year"], "genres": base["genres"],
                }
        return {}
    except Exception as e:
        logger.error(f"Kinopoisk trailer exception: {e}")
        return {}


async def fetch_kinopoisk_series() -> dict:
    if not KINOPOISK_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            page = random.randint(1, 5)
            series_type = random.choice(["TV_SERIES", "MINI_SERIES"])
            items = await _kp_fetch_films_by_genre(client, genre_id=19, order="RATING", film_type=series_type, page=page)
            if len(items) < 3:
                items = await _kp_fetch_films_by_genre(client, genre_id=14, order="RATING", film_type=series_type, page=1)
            if not items:
                return {}
            random.shuffle(items)
            for item in items[:8]:
                base = _extract_film_base(item)
                if not base["id"]:
                    continue
                detail = await _kp_get_film_detail(client, base["id"])
                if not detail:
                    continue
                description = detail.get("description") or detail.get("shortDescription") or ""
                if not description:
                    continue
                return {
                    "title": base["title"], "description": description,
                    "poster_url": detail.get("posterUrl") or base["poster"],
                    "year": base["year"], "genres": base["genres"],
                    "rating": detail.get("ratingKinopoisk") or detail.get("ratingImdb") or "",
                    "seasons": detail.get("seasonsCount", ""), "is_series": True,
                }
        return {}
    except Exception as e:
        logger.error(f"Kinopoisk series exception: {e}")
        return {}


async def fetch_kinopoisk_new_film() -> dict:
    if not KINOPOISK_API_KEY:
        return {}
    import datetime
    current_year = datetime.datetime.now().year
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            films = await _kp_fetch_top_films(client, "TOP_AWAIT_FILMS", page=1)
            if not films:
                r = await client.get(
                    f"{KINOPOISK_BASE}/api/v2.2/films", headers=_kp_headers(),
                    params={"order": "YEAR", "type": "FILM", "ratingFrom": 6,
                            "yearFrom": current_year - 1, "yearTo": current_year,
                            "page": random.randint(1, 3)},
                )
                if r.status_code == 200:
                    films = r.json().get("items", [])
            if not films:
                return {}
            random.shuffle(films)
            for film in films[:10]:
                base = _extract_film_base(film)
                if not base["id"]:
                    continue
                detail = await _kp_get_film_detail(client, base["id"])
                description = detail.get("description") or detail.get("shortDescription") or ""
                if not description:
                    continue
                trailer_url = await _kp_get_videos(client, base["id"])
                return {
                    "title": base["title"], "description": description,
                    "poster_url": detail.get("posterUrl") or base["poster"],
                    "trailer_url": trailer_url, "year": base["year"], "genres": base["genres"],
                    "rating": detail.get("ratingKinopoisk") or detail.get("ratingImdb") or "",
                }
        return {}
    except Exception as e:
        logger.error(f"Kinopoisk new film exception: {e}")
        return {}


async def fetch_kinopoisk_cartoon() -> dict:
    if not KINOPOISK_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            page = random.randint(1, 5)
            film_type = random.choice(["FILM", "TV_SERIES", "MINI_SERIES"])
            items = await _kp_fetch_films_by_genre(client, genre_id=15, order="RATING", film_type=film_type, page=page)
            if not items:
                items = await _kp_fetch_films_by_genre(client, genre_id=15, order="NUM_VOTE", film_type="FILM", page=1)
            if not items:
                return {}
            random.shuffle(items)
            for item in items[:10]:
                base = _extract_film_base(item)
                if not base["id"]:
                    continue
                detail = await _kp_get_film_detail(client, base["id"])
                description = detail.get("description") or detail.get("shortDescription") or ""
                if not description:
                    continue
                trailer_url = await _kp_get_videos(client, base["id"])
                return {
                    "title": base["title"], "description": description,
                    "poster_url": detail.get("posterUrl") or base["poster"],
                    "trailer_url": trailer_url, "year": base["year"], "genres": base["genres"],
                    "rating": detail.get("ratingKinopoisk") or detail.get("ratingImdb") or "",
                }
        return {}
    except Exception as e:
        logger.error(f"Kinopoisk cartoon exception: {e}")
        return {}


async def fetch_kinopoisk_poster() -> dict:
    if not KINOPOISK_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            top_type = random.choice(["TOP_250_BEST_FILMS", "TOP_100_POPULAR_FILMS"])
            page = random.randint(1, 10)
            films = await _kp_fetch_top_films(client, top_type, page)
            if not films:
                return {}
            random.shuffle(films)
            for film in films[:15]:
                base = _extract_film_base(film)
                if not base["id"]:
                    continue
                detail = await _kp_get_film_detail(client, base["id"])
                poster_url = detail.get("posterUrl") or base["poster"]
                if not poster_url or "preview" in poster_url.lower():
                    poster_url = detail.get("posterUrl") or ""
                if not poster_url:
                    continue
                return {
                    "title": base["title"],
                    "description": detail.get("description") or detail.get("shortDescription") or "",
                    "poster_url": poster_url, "year": base["year"], "genres": base["genres"],
                    "rating": detail.get("ratingKinopoisk") or detail.get("ratingImdb") or "",
                }
        return {}
    except Exception as e:
        logger.error(f"Kinopoisk poster exception: {e}")
        return {}


# ─────────────────────────────────────────────
# ГЕНЕРАЦИЯ ПОСТОВ — КИНОПОИСК
# ─────────────────────────────────────────────

async def generate_trailer_post() -> tuple:
    movie = await fetch_kinopoisk_trailer()
    if not movie:
        return "", ""
    system = (
        "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. "
        "Пишешь анонс трейлера — интригующе, с любовью к кино. "
        "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown."
    )
    user_msg = (
        f"Фильм: «{movie['title']}» ({movie['year']})\nЖанры: {movie['genres']}\n"
        f"Описание: {movie['description']}\n\n"
        "Напиши анонс-пост для Telegram-канала.\n"
        "— 80–120 слов\n— Интригующий стиль\n— 1–2 эмодзи в начале\n"
        f"— В конце отдельной строкой: ▶️ Смотреть трейлер: {movie['trailer_url']}\n"
        "— Хэштеги: #трейлер #кино #кислородпродакшен\n— Только текст на русском"
    )
    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, movie["poster_url"]


async def generate_series_post() -> tuple:
    series = await fetch_kinopoisk_series()
    if not series:
        return "", ""
    rating_str = f"⭐ {series['rating']}" if series.get("rating") else ""
    seasons_str = f"• {series['seasons']} сезонов" if series.get("seasons") else ""
    system = (
        "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. "
        "Пишешь рекомендательный пост о сериале — увлекательно и по делу. "
        "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown."
    )
    user_msg = (
        f"Сериал: «{series['title']}» ({series['year']}) {rating_str} {seasons_str}\n"
        f"Жанры: {series['genres']}\nОписание: {series['description']}\n\n"
        "— 100–150 слов\n— Стиль: живой, как совет другу\n— Скажи, почему стоит смотреть\n"
        "— 1–2 эмодзи в начале\n— Хэштеги: #сериал #кино #рекомендация #кислородпродакшен"
    )
    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, series["poster_url"]


async def generate_new_film_post() -> tuple:
    film = await fetch_kinopoisk_new_film()
    if not film:
        return "", ""
    rating_str = f"⭐ {film['rating']}" if film.get("rating") else ""
    trailer_line = f"\n▶️ Трейлер: {film['trailer_url']}" if film.get("trailer_url") else ""
    system = (
        "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. "
        "Пишешь анонс новинки кино — с интригой и вдохновением. "
        "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown."
    )
    user_msg = (
        f"Новинка: «{film['title']}» ({film['year']}) {rating_str}\n"
        f"Жанры: {film['genres']}\nОписание: {film['description']}\n\n"
        "— 100–150 слов\n— Заинтригуй, не пересказывай сюжет полностью\n— 1–2 эмодзи в начале\n"
        f"— Если есть трейлер:{trailer_line}\n— Хэштеги: #новинка #кино #премьера #кислородпродакшен"
    )
    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, film["poster_url"]


async def generate_cartoon_post() -> tuple:
    cartoon = await fetch_kinopoisk_cartoon()
    if not cartoon:
        return "", ""
    rating_str = f"⭐ {cartoon['rating']}" if cartoon.get("rating") else ""
    trailer_line = f"\n▶️ Трейлер: {cartoon['trailer_url']}" if cartoon.get("trailer_url") else ""
    system = (
        "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН — студии, создающей мультфильмы с AI. "
        "Пишешь пост о мультфильме — с теплотой, вдохновляя любовь к анимации. "
        "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown."
    )
    user_msg = (
        f"Мультфильм: «{cartoon['title']}» ({cartoon['year']}) {rating_str}\n"
        f"Жанры: {cartoon['genres']}\nОписание: {cartoon['description']}\n\n"
        "— 100–150 слов\n— Тёплый, воодушевляющий стиль\n— 1–2 эмодзи (например 🎨✨)\n"
        f"— Если есть трейлер:{trailer_line}\n— Хэштеги: #мультфильм #анимация #кислородпродакшен #кино"
    )
    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, cartoon["poster_url"]


async def generate_poster_post() -> tuple:
    movie = await fetch_kinopoisk_poster()
    if not movie:
        return "", ""
    rating_str = f"⭐ {movie['rating']}" if movie.get("rating") else ""
    system = (
        "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. "
        "Пишешь короткую подпись к постеру фильма — лаконично и атмосферно. "
        "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown."
    )
    user_msg = (
        f"Фильм: «{movie['title']}» ({movie['year']}) {rating_str}\n"
        f"Жанры: {movie['genres']}\nОписание: {movie['description']}\n\n"
        "— 40–70 слов — КОРОТКО и атмосферно\n— Цепляющая первая строка\n— 1 эмодзи\n"
        "— Хэштеги: #постер #кино #кислородпродакшен"
    )
    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, movie["poster_url"]


# ─────────────────────────────────────────────
# ОТПРАВКА ПОСТА
# ─────────────────────────────────────────────

async def send_post(bot, channel: str, text: str, image_url: str = ""):
    """Отправляет пост. С фото если есть image_url, иначе текст."""
    if not text or text.startswith("Ошибка") or text.startswith("⚠️"):
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

async def job_kislorod_morning(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_kislorod_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text, img)

async def job_kislorod_new_film(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_new_film_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)

async def job_kislorod_trailer(context: ContextTypes.DEFAULT_TYPE):
    text, poster = await generate_trailer_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, poster)
        await send_post(context.bot, CHANNEL_ACTOR, text, poster)
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)

async def job_kislorod_cartoon(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_cartoon_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)

async def job_kislorod_evening(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_kislorod_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text, img)

async def job_kislorod_poster(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_poster_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)

async def job_actor_morning(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_actor_post()
    await send_post(context.bot, CHANNEL_ACTOR, text, img)

async def job_actor_series(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_series_post()
    if text:
        await send_post(context.bot, CHANNEL_ACTOR, text, img)
    else:
        text2, img2 = await generate_actor_post()
        await send_post(context.bot, CHANNEL_ACTOR, text2, img2)

async def job_actor_evening(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_actor_post()
    await send_post(context.bot, CHANNEL_ACTOR, text, img)

async def job_actor_filmography(context: ContextTypes.DEFAULT_TYPE):
    text, img = await generate_filmography_post()
    if text:
        await send_post(context.bot, CHANNEL_ACTOR, text, img)
    else:
        text2, img2 = await generate_actor_post()
        await send_post(context.bot, CHANNEL_ACTOR, text2, img2)


# ─────────────────────────────────────────────
# ОБРАБОТЧИКИ TELEGRAM
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🎬 КИСЛОРОД ПРОДАКШЕН — AI АССИСТЕНТ\n\n"
        "Творческая AI-студия нового поколения.\n"
        "Мультфильмы • Клипы • Сериалы • Реклама\n\n"
        "Здесь ты можешь общаться с AI-наставником в своей роли:\n"
        "🎭 Актёр — подготовка к ролям, разбор проб\n"
        "🎬 Режиссёр — концепции, раскадровки, визуальный стиль\n"
        "✍️ Сценарист — сюжеты, диалоги, персонажи\n"
        "💼 Продюсер — питч, бюджет, производственный план\n"
        "🤝 Заказчик — ТЗ, бриф, креативная концепция\n\n"
        "👇 Нажми кнопку 📋 Меню чтобы выбрать роль и начать:",
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
                reply_markup=hints_keyboard(role_key),
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
            reply_markup=hints_keyboard(role_key),
        )
        return

    # Обработка нажатия на подсказку
    if action in HINT_TEXTS:
        role_key = context.user_data.get("role", "general")
        hint_text = HINT_TEXTS[action]
        chat_id = query.message.chat_id

        await query.answer()
        # Показываем пользователю какую подсказку он выбрал
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"_{hint_text}_",
            parse_mode="Markdown",
        )

        history = context.user_data.get("history", [])
        stop_typing = asyncio.Event()
        typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))

        try:
            history.append({"role": "user", "text": hint_text})
            response = await ask_yandex_gpt(ROLE_PROMPTS[role_key]["system"], history)
        finally:
            stop_typing.set()
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass

        if not response or not response.strip():
            response = "Не смог сформулировать ответ. Попробуй переформулировать вопрос."

        history.append({"role": "assistant", "text": response})
        context.user_data["history"] = history[-30:]
        await context.bot.send_message(
            chat_id=chat_id,
            text=response,
            reply_markup=hints_keyboard(role_key),
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
        reply_markup=hints_keyboard(role_key),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if not user_text:
        return

    role_key = context.user_data.get("role")

    # Автороль: если роль не выбрана — назначаем "general" и сообщаем об этом
    if not role_key:
        role_key = "general"
        context.user_data["role"] = role_key
        context.user_data["history"] = []
        await update.message.reply_text(
            "🌐 Роль не выбрана — отвечаю как общий ассистент студии.\n"
            "Ты можешь выбрать конкретную роль через 📋 Меню.",
            reply_markup=webapp_keyboard(),
        )

    history = context.user_data.get("history", [])
    chat_id = update.effective_chat.id

    # Запускаем фоновый typing-индикатор
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))

    try:
        history.append({"role": "user", "text": user_text})
        response = await ask_yandex_gpt(ROLE_PROMPTS[role_key]["system"], history)
    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    # Fallback если ответ пустой или ошибка
    if not response or not response.strip():
        response = "Не смог сформулировать ответ. Попробуй переформулировать вопрос или очисти историю чата."

    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]
    await update.message.reply_text(response, reply_markup=hints_keyboard(role_key))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS

    base_text = (
        "🎬 КИСЛОРОД AI — Справка\n\n"
        "/start          — Открыть меню\n"
        "/clear          — Очистить историю чата\n"
        "/help           — Справка\n"
    )

    admin_text = (
        "\n── Только для администратора ──\n"
        "/schedule       — Расписание автопостинга\n\n"
        "📰 Новостные посты:\n"
        "/post_now       — Новости кино (оба канала)\n\n"
        "🎬 Кинопоиск:\n"
        "/trailer_now    — Трейлер фильма\n"
        "/film_now       — Новинка кино\n"
        "/series_now     — Рекомендация сериала\n"
        "/cartoon_now    — Пост о мультфильме\n"
        "/poster_now     — Красивый постер\n\n"
        "🎭 Личные посты Александра:\n"
        "/myfilm_now     — Пост о проекте из фильмографии\n"
    )

    footer = (
        "\nКонтакты:\n"
        "📧 actorsashapotapov@gmail.com\n"
        "💬 @actorsashapotapov"
    )

    full_text = base_text + (admin_text if is_admin else "") + footer
    await update.message.reply_text(full_text, reply_markup=webapp_keyboard())


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text(
        "✅ История очищена. Нажми 📋 Меню чтобы выбрать роль:",
        reply_markup=webapp_keyboard(),
    )


@admin_only
async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 Расписание автопостинга (МСК):\n\n"
        "📺 @realtimeproductionn — 6 постов в день:\n"
        "   🕙 10:00 — новости кино и продакшена 📰\n"
        "   🕛 12:00 — новинка кино 🎞\n"
        "   🕑 14:00 — трейлер фильма 🎬\n"
        "   🕓 16:00 — мультфильм 🎨\n"
        "   🕖 19:00 — вечерний дайджест 📰\n"
        "   🕘 21:00 — красивый постер 🖼\n\n"
        "🎭 @actorsashapotapovv — 4 поста в день:\n"
        "   🕚 11:00 — утренний пост от Александра\n"
        "   🕐 13:00 — пост о проекте из фильмографии 🎬\n"
        "   🕒 15:00 — рекомендация сериала 📺\n"
        "   🕗 20:00 — вечерний пост от Александра\n\n"
        "Всего: 10 постов в день\n"
        "Источники: NewsAPI 📰 + Кинопоиск 🎬 + фильмография Александра 🎭"
    )


@admin_only
async def post_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Генерирую новостные посты (~20 сек)...")
    text1, img1 = await generate_kislorod_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text1, img1)
    text2, img2 = await generate_actor_post()
    await send_post(context.bot, CHANNEL_ACTOR, text2, img2)
    await update.message.reply_text("✅ Новостные посты опубликованы!")


@admin_only
async def trailer_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу свежий трейлер в Кинопоиске (~15 сек)...")
    text, poster = await generate_trailer_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, poster)
        await send_post(context.bot, CHANNEL_ACTOR, text, poster)
        await update.message.reply_text("✅ Трейлер опубликован в оба канала!")
    else:
        await update.message.reply_text(
            "❌ Не удалось получить трейлер.\n"
            "Проверь KINOPOISK_API_KEY в переменных Railway."
        )


@admin_only
async def film_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу новинку кино (~15 сек)...")
    text, img = await generate_new_film_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
        await update.message.reply_text("✅ Новинка кино опубликована в @realtimeproductionn!")
    else:
        await update.message.reply_text("❌ Не удалось получить новинку кино.\nПроверь KINOPOISK_API_KEY.")


@admin_only
async def series_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу сериал (~15 сек)...")
    text, img = await generate_series_post()
    if text:
        await send_post(context.bot, CHANNEL_ACTOR, text, img)
        await update.message.reply_text("✅ Пост о сериале опубликован в @actorsashapotapovv!")
    else:
        await update.message.reply_text("❌ Не удалось получить сериал.\nПроверь KINOPOISK_API_KEY.")


@admin_only
async def cartoon_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу мультфильм (~15 сек)...")
    text, img = await generate_cartoon_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
        await update.message.reply_text("✅ Пост о мультфильме опубликован в @realtimeproductionn!")
    else:
        await update.message.reply_text("❌ Не удалось получить мультфильм.\nПроверь KINOPOISK_API_KEY.")


@admin_only
async def poster_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу красивый постер (~15 сек)...")
    text, img = await generate_poster_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
        await update.message.reply_text("✅ Постер опубликован в @realtimeproductionn!")
    else:
        await update.message.reply_text("❌ Не удалось получить постер.\nПроверь KINOPOISK_API_KEY.")


@admin_only
async def myfilm_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Пишу пост о твоём проекте (~15 сек)...")
    text, img = await generate_filmography_post()
    if text:
        await send_post(context.bot, CHANNEL_ACTOR, text, img)
        await update.message.reply_text("✅ Пост о проекте опубликован в @actorsashapotapovv!")
    else:
        await update.message.reply_text("❌ Не удалось сгенерировать пост. Попробуй снова.")


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
    logger.info(f"ADMIN_IDS:         {ADMIN_IDS}")

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды чата (для всех)
    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("help",         help_command))
    app.add_handler(CommandHandler("clear",        clear_command))

    # Команды только для админа
    app.add_handler(CommandHandler("schedule",     schedule_command))
    app.add_handler(CommandHandler("post_now",     post_now_command))
    app.add_handler(CommandHandler("trailer_now",  trailer_now_command))
    app.add_handler(CommandHandler("film_now",     film_now_command))
    app.add_handler(CommandHandler("series_now",   series_now_command))
    app.add_handler(CommandHandler("cartoon_now",  cartoon_now_command))
    app.add_handler(CommandHandler("poster_now",   poster_now_command))
    app.add_handler(CommandHandler("myfilm_now",   myfilm_now_command))

    # Callback и сообщения
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ── Расписание (UTC = МСК − 3) ──────────────────────────────────
    app.job_queue.run_daily(job_kislorod_morning,   time=dtime(7,  0))  # 10:00 МСК
    app.job_queue.run_daily(job_kislorod_new_film,  time=dtime(9,  0))  # 12:00 МСК
    app.job_queue.run_daily(job_kislorod_trailer,   time=dtime(11, 0))  # 14:00 МСК
    app.job_queue.run_daily(job_kislorod_cartoon,   time=dtime(13, 0))  # 16:00 МСК
    app.job_queue.run_daily(job_kislorod_evening,   time=dtime(16, 0))  # 19:00 МСК
    app.job_queue.run_daily(job_kislorod_poster,    time=dtime(18, 0))  # 21:00 МСК
    app.job_queue.run_daily(job_actor_morning,      time=dtime(8,  0))  # 11:00 МСК
    app.job_queue.run_daily(job_actor_filmography,  time=dtime(10, 0))  # 13:00 МСК
    app.job_queue.run_daily(job_actor_series,       time=dtime(12, 0))  # 15:00 МСК
    app.job_queue.run_daily(job_actor_evening,      time=dtime(17, 0))  # 20:00 МСК

    logger.info("=== Расписание ===")
    logger.info("@realtimeproductionn: 07/09/11/13/16/18 UTC")
    logger.info("@actorsashapotapovv:  08/10/12/17 UTC")
    logger.info("=== Bot запущен! ===")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
