import os
import asyncio
import logging
import random
import json
import httpx
import functools
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
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "29f8af604fmsh7f2433154c9fb3dp1c9f6ajsnf6ab497a500d")

CHANNEL_KISLOROD = "@realtimeproductionn"
CHANNEL_ACTOR = "@actorsashapotapovv"

WEBAPP_URL = "https://aliferovaaleksandr-del.github.io/kislorod-ai-bot/menu.html"

ADMIN_IDS = {380171031}

# ─────────────────────────────────────────────
# ГЛОБАЛЬНАЯ СТАТИСТИКА
# ─────────────────────────────────────────────
# Хранится в памяти. При перезапуске сбрасывается.
# Для персистентности — подключи БД или сохраняй в файл.
_stats = {
    "total_users": set(),       # уникальные user_id
    "total_messages": 0,
    "roles_chosen": {},         # role_key -> count
    "tools_used": {},           # tool_name -> count
    "saves_total": 0,
    "posts_sent": 0,
}


def _stats_inc_tool(tool_name: str):
    _stats["tools_used"][tool_name] = _stats["tools_used"].get(tool_name, 0) + 1


def _stats_inc_role(role_key: str):
    _stats["roles_chosen"][role_key] = _stats["roles_chosen"].get(role_key, 0) + 1


# ─────────────────────────────────────────────
# ДЕКОРАТОР: только для администраторов
# ─────────────────────────────────────────────

def admin_only(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("⛔ У вас нет доступа к этой команде.")
            logger.warning(f"Попытка доступа к admin-команде от user_id={user_id}")
            return
        return await func(update, context)
    return wrapper


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# ОНБОРДИНГ
# ─────────────────────────────────────────────

ONBOARDING_STEPS = [
    {
        "text": (
            "🎬 Добро пожаловать в КИСЛОРОД ПРОДАКШЕН AI!\n\n"
            "Я — твой творческий ассистент для кино, анимации и контента.\n\n"
            "За 3 шага покажу, что умею.\n\n"
            "👇 Шаг 1 из 3: Выбери свою роль в кино:"
        ),
        "buttons": [
            [InlineKeyboardButton("🎭 Я — Актёр", callback_data="onboard_actor"),
             InlineKeyboardButton("🎬 Я — Режиссёр", callback_data="onboard_director")],
            [InlineKeyboardButton("✍️ Я — Сценарист", callback_data="onboard_screenwriter"),
             InlineKeyboardButton("💼 Я — Продюсер", callback_data="onboard_producer")],
            [InlineKeyboardButton("🤝 Я — Заказчик", callback_data="onboard_client"),
             InlineKeyboardButton("🌐 Просто смотрю", callback_data="onboard_general")],
        ],
    },
]

ONBOARDING_STEP2 = {
    "text": (
        "✅ Отлично! Роль выбрана.\n\n"
        "📋 Шаг 2 из 3: Инструменты\n\n"
        "У меня есть мощные творческие инструменты:\n"
        "🎬 /storyboard — Раскадровка сцены\n"
        "🎭 /character — Карточка персонажа\n"
        "📝 /scene — Написать сцену в сценарном формате\n"
        "🎤 /monologue — Монолог для актёра\n"
        "🔁 /rewrite — Переписать текст в другом жанре\n"
        "💾 /saves — Твои сохранённые работы\n\n"
        "👇 Шаг 3 из 3: Как ты хочешь начать?"
    ),
    "buttons": [
        [InlineKeyboardButton("💬 Просто поговорить", callback_data="onboard_finish_chat"),
         InlineKeyboardButton("🛠 Попробовать инструмент", callback_data="onboard_finish_tool")],
    ],
}

ONBOARDING_STEP3_CHAT = (
    "🚀 Отлично! Я готов.\n\n"
    "Напиши мне что угодно — я отвечу как твой персональный AI-наставник.\n\n"
    "Или выбери подсказку ниже 👇"
)

ONBOARDING_STEP3_TOOL = (
    "🛠 Выбери инструмент:\n\n"
    "/storyboard — создать раскадровку\n"
    "/character — создать карточку персонажа\n"
    "/scene — написать сцену\n"
    "/monologue — написать монолог\n"
    "/rewrite — переписать в другом стиле\n\n"
    "Или нажми 📋 Меню, чтобы сменить роль."
)


# ─────────────────────────────────────────────
# МЕНЮ ПОДСКАЗОК
# ─────────────────────────────────────────────

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


def hints_keyboard(role_key: str, context: ContextTypes.DEFAULT_TYPE = None) -> InlineKeyboardMarkup:
    if context is not None:
        return hints_keyboard_with_count(role_key, context)
    hints = ROLE_HINTS.get(role_key, [])
    rows = []
    for i in range(0, len(hints), 2):
        row = [InlineKeyboardButton(hints[i][0], callback_data=hints[i][1])]
        if i + 1 < len(hints):
            row.append(InlineKeyboardButton(hints[i + 1][0], callback_data=hints[i + 1][1]))
        rows.append(row)
    rows.append([
        InlineKeyboardButton("🛠 Инструменты", callback_data="show_tools"),
        InlineKeyboardButton("💾 Сохранённые", callback_data="show_saves"),
    ])
    rows.append([
        InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role"),
        InlineKeyboardButton("🗑 Очистить чат", callback_data="clear_chat"),
    ])
    return InlineKeyboardMarkup(rows)


def tools_keyboard(context: ContextTypes.DEFAULT_TYPE = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("🎬 Раскадровка", callback_data="tool_storyboard"),
            InlineKeyboardButton("🎭 Персонаж", callback_data="tool_character"),
        ],
        [
            InlineKeyboardButton("📝 Сцена", callback_data="tool_scene"),
            InlineKeyboardButton("🎤 Монолог", callback_data="tool_monologue"),
        ],
        [
            InlineKeyboardButton("🔁 Переписать стиль", callback_data="tool_rewrite"),
            InlineKeyboardButton("💾 Мои сохранения", callback_data="show_saves"),
        ],
    ]
    # История последних запросов
    if context is not None:
        recent = context.user_data.get("recent_requests", [])
        if recent:
            rows.append([InlineKeyboardButton("📜 Последние запросы", callback_data="show_recent")])
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_hints")])
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
# YANDEX GPT
# ─────────────────────────────────────────────

async def ask_yandex_gpt(system_prompt: str, conversation: list, retries: int = 3) -> str:
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

    return f"⚠️ {last_error} Попробуй чуть позже."


# ─────────────────────────────────────────────
# TYPING INDICATOR
# ─────────────────────────────────────────────

async def keep_typing(bot, chat_id: int, stop_event: asyncio.Event):
    from telegram.constants import ChatAction
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        await asyncio.sleep(4)


# ─────────────────────────────────────────────
# ПРОГРЕСС-БАР
# ─────────────────────────────────────────────

PROGRESS_FRAMES = [
    "⬜⬜⬜⬜⬜  0%",
    "🟥⬜⬜⬜⬜  20%",
    "🟥🟥⬜⬜⬜  40%",
    "🟥🟥🟥⬜⬜  60%",
    "🟥🟥🟥🟥⬜  80%",
    "🟥🟥🟥🟥🟥  100% ✅",
]


async def send_progress(bot, chat_id: int, label: str) -> int:
    """Отправляет анимированный прогресс-бар. Возвращает message_id для последующего удаления."""
    msg = await bot.send_message(
        chat_id=chat_id,
        text=f"{label}\n\n{PROGRESS_FRAMES[0]}",
    )
    for frame in PROGRESS_FRAMES[1:]:
        await asyncio.sleep(0.9)
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.message_id,
                text=f"{label}\n\n{frame}",
            )
        except Exception:
            pass
    return msg.message_id


async def delete_progress(bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


# ─────────────────────────────────────────────
# СОХРАНЕНИЕ РАБОТ
# ─────────────────────────────────────────────

SAVE_TYPE_LABELS = {
    "storyboard": "🎬 Раскадровка",
    "character":  "🎭 Персонаж",
    "scene":      "📝 Сцена",
    "monologue":  "🎤 Монолог",
    "rewrite":    "🔁 Перезапись",
    "chat":       "💬 Ответ",
}

# Папки = типы сохранений
SAVE_FOLDERS = {
    "storyboard": "🎬 Раскадровки",
    "character":  "🎭 Персонажи",
    "scene":      "📝 Сцены",
    "monologue":  "🎤 Монологи",
    "rewrite":    "🔁 Перезаписи",
    "chat":       "💬 Ответы",
}


def _get_saves(context: ContextTypes.DEFAULT_TYPE) -> list:
    return context.user_data.get("saves", [])


def _saves_count(context: ContextTypes.DEFAULT_TYPE) -> int:
    return len(context.user_data.get("saves", []))


def _add_save(context: ContextTypes.DEFAULT_TYPE, save_type: str, title: str, content: str):
    saves = context.user_data.get("saves", [])
    if len(saves) >= 20:
        saves.pop(0)
    saves.append({"type": save_type, "title": title, "content": content})
    context.user_data["saves"] = saves
    _stats["saves_total"] += 1


def _add_to_history(context: ContextTypes.DEFAULT_TYPE, tool: str, description: str):
    """Сохраняет последние 3 запроса пользователя."""
    history = context.user_data.get("recent_requests", [])
    entry = {"tool": tool, "description": description[:60]}
    # Не дублировать одинаковые подряд
    if not history or history[-1]["description"] != entry["description"]:
        history.append(entry)
    if len(history) > 3:
        history.pop(0)
    context.user_data["recent_requests"] = history


def save_keyboard(save_type: str, title: str) -> InlineKeyboardButton:
    short_title = title[:30]
    return InlineKeyboardButton(
        "💾 Сохранить", callback_data=f"save|{save_type}|{short_title}"
    )


def make_save_row(save_type: str, title: str) -> list:
    return [save_keyboard(save_type, title)]


def hints_keyboard_with_count(role_key: str, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """hints_keyboard с счётчиком сохранений на кнопке."""
    hints = ROLE_HINTS.get(role_key, [])
    rows = []
    for i in range(0, len(hints), 2):
        row = [InlineKeyboardButton(hints[i][0], callback_data=hints[i][1])]
        if i + 1 < len(hints):
            row.append(InlineKeyboardButton(hints[i + 1][0], callback_data=hints[i + 1][1]))
        rows.append(row)
    count = _saves_count(context)
    save_label = f"💾 Сохранённые ({count})" if count > 0 else "💾 Сохранённые"
    rows.append([
        InlineKeyboardButton("🛠 Инструменты", callback_data="show_tools"),
        InlineKeyboardButton(save_label, callback_data="show_saves"),
    ])
    rows.append([
        InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role"),
        InlineKeyboardButton("🗑 Очистить чат", callback_data="clear_chat"),
    ])
    return InlineKeyboardMarkup(rows)


# ─────────────────────────────────────────────
# ГЕНЕРАЦИЯ ПОСТОВ — НОВОСТИ
# ─────────────────────────────────────────────

async def generate_kislorod_post() -> tuple:
    global _kislorod_query_index
    query = KISLOROD_QUERIES[_kislorod_query_index % len(KISLOROD_QUERIES)]
    _kislorod_query_index += 1

    news, image_url = await fetch_news(query, language="ru")
    if not news:
        news, image_url = await fetch_news("cinema film production", language="en")

    if news:
        system = (
            "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. "
            "Студия создаёт мультфильмы, клипы, сериалы и рекламу с помощью AI. "
            "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown, без кавычек."
        )
        user_msg = (
            f"Свежие новости из мира кино и продакшена:\n\n{news}\n\n"
            "На основе этих новостей напиши один пост для Telegram-канала.\n"
            "— 150–250 слов\n— Живой стиль\n— 1–2 эмодзи в начале\n"
            "— Хэштеги: #кино #кислородпродакшен #продакшен"
        )
    else:
        system = "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. Отвечай ТОЛЬКО текстом поста."
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

    news, image_url = await fetch_news(query, language="ru")
    if not news:
        news, image_url = await fetch_news("actor film AI casting technology", language="en")

    if news:
        system = (
            "Ты помогаешь актёру Александру Потапову вести его личный Telegram-канал. "
            "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown."
        )
        user_msg = (
            f"Свежие новости:\n\n{news}\n\n"
            "Напиши личный пост от имени Александра. "
            "120–200 слов, от первого лица, 1–2 эмодзи. "
            "Хэштеги: #актёр #кино #александрпотапов"
        )
    else:
        system = "Ты помогаешь актёру Александру Потапову. Отвечай ТОЛЬКО текстом поста."
        user_msg = (
            "Напиши личный пост об актёрском пути. "
            "120–200 слов, от первого лица, 1–2 эмодзи. "
            "Хэштеги: #актёр #кино #александрпотапов"
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
    {"title": "Полярный", "year": "2019", "role": "бармен", "type": "сериал", "note": "рейтинг 8.2"},
    {"title": "Трудные подростки", "year": "2019–2024", "role": "Гарик", "type": "сериал", "note": "рейтинг 8.2"},
    {"title": "Ключи", "year": "2018", "role": "", "type": "фильм", "note": ""},
    {"title": "Полицейский с Рублёвки. Мы тебя найдём", "year": "2018", "role": "Степа", "type": "сериал", "note": "ТНТ"},
    {"title": "Оптимисты", "year": "2017", "role": "хулиган", "type": "сериал", "note": "Россия-1"},
    {"title": "Четвертая смена", "year": "2017", "role": "сотрудник аварийной службы", "type": "сериал", "note": "НТВ"},
    {"title": "Полицейский с Рублёвки в Бескудниково", "year": "2017", "role": "гопник", "type": "сериал", "note": ""},
    {"title": "Охота на дьявола", "year": "2017", "role": "", "type": "сериал", "note": "рейтинг 7.8"},
]

_filmography_index = 0


async def generate_filmography_post() -> tuple:
    global _filmography_index
    project = FILMOGRAPHY[_filmography_index % len(FILMOGRAPHY)]
    _filmography_index += 1

    role_str = f", роль: {project['role']}" if project["role"] else ""
    note_str = f" ({project['note']})" if project["note"] else ""

    system = (
        "Ты помогаешь актёру Александру Потапову (19 декабря 1986 г.р.) вести его личный Telegram-канал. "
        "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown."
    )
    user_msg = (
        f"Напиши личный пост от имени Александра о проекте:\n\n"
        f"Название: «{project['title']}»\nГод: {project['year']}\n"
        f"Тип: {project['type']}{note_str}\nРоль{role_str}\n\n"
        "— 120–180 слов, от первого лица\n— 1–2 эмодзи\n"
        "— Хэштеги: #актёр #александрпотапов #кино"
    )

    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, ""


# ─────────────────────────────────────────────
# КИНОПОИСК
# ─────────────────────────────────────────────

KINOPOISK_BASE = "https://kinopoiskapiunofficial.tech"


def _kp_headers() -> dict:
    return {"X-API-KEY": KINOPOISK_API_KEY or "", "Content-Type": "application/json"}


async def _kp_get_film_detail(client, film_id):
    r = await client.get(f"{KINOPOISK_BASE}/api/v2.2/films/{film_id}", headers=_kp_headers())
    return r.json() if r.status_code == 200 else {}


async def _kp_get_videos(client, film_id):
    rv = await client.get(f"{KINOPOISK_BASE}/api/v2.2/films/{film_id}/videos", headers=_kp_headers())
    if rv.status_code != 200:
        return ""
    videos = rv.json().get("items", [])
    for v in videos:
        if v.get("site") == "YOUTUBE" and "трейлер" in (v.get("name") or "").lower():
            return v.get("url", "")
    for v in videos:
        if v.get("site") == "YOUTUBE":
            return v.get("url", "")
    return videos[0].get("url", "") if videos else ""


async def _kp_fetch_top_films(client, top_type, page):
    r = await client.get(
        f"{KINOPOISK_BASE}/api/v2.2/films/top",
        headers=_kp_headers(), params={"type": top_type, "page": page},
    )
    if r.status_code not in (200,):
        return []
    return r.json().get("films", [])


async def _kp_fetch_films_by_genre(client, genre_id, order="RATING", film_type="FILM", page=1):
    r = await client.get(
        f"{KINOPOISK_BASE}/api/v2.2/films", headers=_kp_headers(),
        params={"genres": genre_id, "order": order, "type": film_type,
                "ratingFrom": 6, "ratingTo": 10, "page": page},
    )
    if r.status_code != 200:
        return []
    return r.json().get("items", [])


def _extract_film_base(film):
    film_id = film.get("filmId") or film.get("kinopoiskId")
    title = film.get("nameRu") or film.get("nameEn") or "Без названия"
    year = film.get("year", "")
    poster_url = film.get("posterUrlPreview") or film.get("posterUrl") or ""
    genres = ", ".join(g["genre"] for g in (film.get("genres") or [])[:3] if g.get("genre"))
    return {"id": film_id, "title": title, "year": year, "poster": poster_url, "genres": genres}


async def fetch_kinopoisk_trailer() -> dict:
    if not KINOPOISK_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            films = await _kp_fetch_top_films(
                client, random.choice(["TOP_250_BEST_FILMS", "TOP_100_POPULAR_FILMS"]),
                random.randint(1, 5)
            )
            random.shuffle(films)
            for film in films[:10]:
                base = _extract_film_base(film)
                if not base["id"]:
                    continue
                detail = await _kp_get_film_detail(client, base["id"])
                trailer_url = await _kp_get_videos(client, base["id"])
                if not trailer_url:
                    continue
                return {
                    "title": base["title"],
                    "description": detail.get("description") or detail.get("shortDescription") or "",
                    "poster_url": detail.get("posterUrl") or base["poster"],
                    "trailer_url": trailer_url, "year": base["year"], "genres": base["genres"],
                }
        return {}
    except Exception as e:
        logger.error(f"Kinopoisk trailer: {e}")
        return {}


async def fetch_kinopoisk_series() -> dict:
    if not KINOPOISK_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            items = await _kp_fetch_films_by_genre(
                client, genre_id=19, order="RATING",
                film_type=random.choice(["TV_SERIES", "MINI_SERIES"]),
                page=random.randint(1, 5)
            )
            random.shuffle(items)
            for item in items[:8]:
                base = _extract_film_base(item)
                if not base["id"]:
                    continue
                detail = await _kp_get_film_detail(client, base["id"])
                description = detail.get("description") or detail.get("shortDescription") or ""
                if not description:
                    continue
                return {
                    "title": base["title"], "description": description,
                    "poster_url": detail.get("posterUrl") or base["poster"],
                    "year": base["year"], "genres": base["genres"],
                    "rating": detail.get("ratingKinopoisk") or "",
                    "seasons": detail.get("seasonsCount", ""),
                }
        return {}
    except Exception as e:
        logger.error(f"Kinopoisk series: {e}")
        return {}


async def fetch_kinopoisk_new_film() -> dict:
    import datetime
    if not KINOPOISK_API_KEY:
        return {}
    current_year = datetime.datetime.now().year
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            films = await _kp_fetch_top_films(client, "TOP_AWAIT_FILMS", 1)
            if not films:
                r = await client.get(
                    f"{KINOPOISK_BASE}/api/v2.2/films", headers=_kp_headers(),
                    params={"order": "YEAR", "type": "FILM", "ratingFrom": 6,
                            "yearFrom": current_year - 1, "yearTo": current_year,
                            "page": random.randint(1, 3)},
                )
                if r.status_code == 200:
                    films = r.json().get("items", [])
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
                    "rating": detail.get("ratingKinopoisk") or "",
                }
        return {}
    except Exception as e:
        logger.error(f"Kinopoisk new film: {e}")
        return {}


async def fetch_kinopoisk_cartoon() -> dict:
    if not KINOPOISK_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            items = await _kp_fetch_films_by_genre(
                client, genre_id=15, order="RATING",
                film_type=random.choice(["FILM", "TV_SERIES"]),
                page=random.randint(1, 5)
            )
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
                    "rating": detail.get("ratingKinopoisk") or "",
                }
        return {}
    except Exception as e:
        logger.error(f"Kinopoisk cartoon: {e}")
        return {}


async def fetch_kinopoisk_poster() -> dict:
    if not KINOPOISK_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            films = await _kp_fetch_top_films(
                client, random.choice(["TOP_250_BEST_FILMS", "TOP_100_POPULAR_FILMS"]),
                random.randint(1, 10)
            )
            random.shuffle(films)
            for film in films[:15]:
                base = _extract_film_base(film)
                if not base["id"]:
                    continue
                detail = await _kp_get_film_detail(client, base["id"])
                poster_url = detail.get("posterUrl") or base["poster"]
                if not poster_url:
                    continue
                return {
                    "title": base["title"],
                    "description": detail.get("description") or detail.get("shortDescription") or "",
                    "poster_url": poster_url, "year": base["year"], "genres": base["genres"],
                    "rating": detail.get("ratingKinopoisk") or "",
                }
        return {}
    except Exception as e:
        logger.error(f"Kinopoisk poster: {e}")
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
        "Отвечай ТОЛЬКО текстом поста."
    )
    user_msg = (
        f"Фильм: «{movie['title']}» ({movie['year']})\nЖанры: {movie['genres']}\n"
        f"Описание: {movie['description']}\n\n"
        "— 80–120 слов\n— 1–2 эмодзи\n"
        f"— В конце: ▶️ Смотреть трейлер: {movie['trailer_url']}\n"
        "— Хэштеги: #трейлер #кино #кислородпродакшен"
    )
    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, movie["poster_url"]


async def generate_series_post() -> tuple:
    series = await fetch_kinopoisk_series()
    if not series:
        return "", ""
    rating_str = f"⭐ {series['rating']}" if series.get("rating") else ""
    system = "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. Отвечай ТОЛЬКО текстом поста."
    user_msg = (
        f"Сериал: «{series['title']}» ({series['year']}) {rating_str}\n"
        f"Жанры: {series['genres']}\nОписание: {series['description']}\n\n"
        "— 100–150 слов\n— 1–2 эмодзи\n"
        "— Хэштеги: #сериал #кино #рекомендация #кислородпродакшен"
    )
    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, series["poster_url"]


async def generate_new_film_post() -> tuple:
    film = await fetch_kinopoisk_new_film()
    if not film:
        return "", ""
    rating_str = f"⭐ {film['rating']}" if film.get("rating") else ""
    trailer_line = f"\n▶️ Трейлер: {film['trailer_url']}" if film.get("trailer_url") else ""
    system = "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. Отвечай ТОЛЬКО текстом поста."
    user_msg = (
        f"Новинка: «{film['title']}» ({film['year']}) {rating_str}\n"
        f"Жанры: {film['genres']}\nОписание: {film['description']}\n\n"
        f"— 100–150 слов\n— 1–2 эмодзи{trailer_line}\n"
        "— Хэштеги: #новинка #кино #премьера #кислородпродакшен"
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
        "Отвечай ТОЛЬКО текстом поста."
    )
    user_msg = (
        f"Мультфильм: «{cartoon['title']}» ({cartoon['year']}) {rating_str}\n"
        f"Жанры: {cartoon['genres']}\nОписание: {cartoon['description']}\n\n"
        f"— 100–150 слов\n— 1–2 эмодзи (🎨✨){trailer_line}\n"
        "— Хэштеги: #мультфильм #анимация #кислородпродакшен"
    )
    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, cartoon["poster_url"]


async def generate_poster_post() -> tuple:
    movie = await fetch_kinopoisk_poster()
    if not movie:
        return "", ""
    rating_str = f"⭐ {movie['rating']}" if movie.get("rating") else ""
    system = "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. Отвечай ТОЛЬКО текстом поста."
    user_msg = (
        f"Фильм: «{movie['title']}» ({movie['year']}) {rating_str}\n"
        f"Жанры: {movie['genres']}\nОписание: {movie['description']}\n\n"
        "— 40–70 слов, коротко и атмосферно\n— 1 эмодзи\n"
        "— Хэштеги: #постер #кино #кислородпродакшен"
    )
    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    return text, movie["poster_url"]


# ─────────────────────────────────────────────
# ОТПРАВКА ПОСТА
# ─────────────────────────────────────────────

async def send_post(bot, channel: str, text: str, image_url: str = ""):
    if not text or text.startswith("Ошибка") or text.startswith("⚠️"):
        logger.error(f"Некорректный текст поста: {text[:80]}")
        return
    try:
        if image_url:
            try:
                await bot.send_photo(chat_id=channel, photo=image_url, caption=text)
                logger.info(f"✅ Фото+текст → {channel}")
                _stats["posts_sent"] += 1
                return
            except Exception as e:
                logger.warning(f"Фото не отправилось ({e}), отправляю текст")
        await bot.send_message(chat_id=channel, text=text)
        logger.info(f"✅ Текст → {channel}")
        _stats["posts_sent"] += 1
    except Exception as e:
        logger.error(f"Ошибка отправки в {channel}: {e}")


# ─────────────────────────────────────────────
# JOB FUNCTIONS — расписание
# ─────────────────────────────────────────────

async def job_kislorod_morning(context):
    text, img = await generate_kislorod_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text, img)

async def job_kislorod_new_film(context):
    text, img = await generate_new_film_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)

async def job_kislorod_trailer(context):
    text, poster = await generate_trailer_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, poster)
        await send_post(context.bot, CHANNEL_ACTOR, text, poster)
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)

async def job_kislorod_cartoon(context):
    text, img = await generate_cartoon_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)

async def job_kislorod_evening(context):
    text, img = await generate_kislorod_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text, img)

async def job_kislorod_poster(context):
    text, img = await generate_poster_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)

async def job_actor_morning(context):
    text, img = await generate_actor_post()
    await send_post(context.bot, CHANNEL_ACTOR, text, img)

async def job_actor_series(context):
    text, img = await generate_series_post()
    if text:
        await send_post(context.bot, CHANNEL_ACTOR, text, img)
    else:
        text2, img2 = await generate_actor_post()
        await send_post(context.bot, CHANNEL_ACTOR, text2, img2)

async def job_actor_evening(context):
    text, img = await generate_actor_post()
    await send_post(context.bot, CHANNEL_ACTOR, text, img)

async def job_actor_filmography(context):
    text, img = await generate_filmography_post()
    if text:
        await send_post(context.bot, CHANNEL_ACTOR, text, img)
    else:
        text2, img2 = await generate_actor_post()
        await send_post(context.bot, CHANNEL_ACTOR, text2, img2)


# ─────────────────────────────────────────────
# /start — ОНБОРДИНГ
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    _stats["total_users"].add(user_id)

    # ⚡ Режим быстрого старта — если роль уже выбрана, не сбрасываем
    existing_role = context.user_data.get("role")
    if existing_role and existing_role in ROLE_PROMPTS:
        role_label = {
            "actor": "🎭 Актёр", "director": "🎬 Режиссёр",
            "screenwriter": "✍️ Сценарист", "producer": "💼 Продюсер",
            "client": "🤝 Заказчик", "general": "🌐 Общий",
        }.get(existing_role, existing_role)
        await update.message.reply_text(
            f"⚡ Быстрый старт!\n\n"
            f"Твоя роль: {role_label}\n\n"
            f"Продолжаем с того места где остановились 👇",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Продолжить", callback_data=f"quickstart_continue")],
                [InlineKeyboardButton("🔄 Сменить роль", callback_data="quickstart_reset")],
            ]),
        )
        return

    # Новый пользователь — онбординг
    context.user_data.clear()
    context.user_data["onboarding"] = True

    step = ONBOARDING_STEPS[0]
    await update.message.reply_text(
        step["text"],
        reply_markup=InlineKeyboardMarkup(step["buttons"]),
    )
    await update.message.reply_text(
        "Или нажми 📋 Меню в любой момент.",
        reply_markup=webapp_keyboard(),
    )


# ─────────────────────────────────────────────
# CALLBACK HANDLER
# ─────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    # ── ОНБОРДИНГ ──────────────────────────────

    if action.startswith("onboard_"):
        role_map = {
            "onboard_actor":        "actor",
            "onboard_director":     "director",
            "onboard_screenwriter": "screenwriter",
            "onboard_producer":     "producer",
            "onboard_client":       "client",
            "onboard_general":      "general",
        }
        if action in role_map:
            role_key = role_map[action]
            context.user_data["role"] = role_key
            context.user_data["history"] = []
            _stats_inc_role(role_key)
            await query.edit_message_text(
                ONBOARDING_STEP2["text"],
                reply_markup=InlineKeyboardMarkup(ONBOARDING_STEP2["buttons"]),
            )
            return

        if action == "onboard_finish_chat":
            role_key = context.user_data.get("role", "general")
            context.user_data.pop("onboarding", None)
            await query.edit_message_text(
                ONBOARDING_STEP3_CHAT,
                reply_markup=hints_keyboard(role_key, context),
            )
            return

        if action == "onboard_finish_tool":
            context.user_data.pop("onboarding", None)
            await query.edit_message_text(
                ONBOARDING_STEP3_TOOL,
                reply_markup=tools_keyboard(context),
            )
            return

    # ── БЫСТРЫЙ СТАРТ ──────────────────────────

    if action == "quickstart_continue":
        role_key = context.user_data.get("role", "general")
        await query.edit_message_text(
            ROLE_PROMPTS[role_key]["welcome"],
            reply_markup=hints_keyboard(role_key, context),
        )
        return

    if action == "quickstart_reset":
        context.user_data.clear()
        step = ONBOARDING_STEPS[0]
        await query.edit_message_text(
            step["text"],
            reply_markup=InlineKeyboardMarkup(step["buttons"]),
        )
        return

    # ── ИНСТРУМЕНТЫ ────────────────────────────

    if action == "show_tools":
        recent = context.user_data.get("recent_requests", [])
        recent_text = ""
        if recent:
            tool_labels = {
                "storyboard": "🎬", "character": "🎭",
                "scene": "📝", "monologue": "🎤", "rewrite": "🔁",
            }
            lines = [f"  {tool_labels.get(r['tool'], '•')} {r['description']}" for r in reversed(recent)]
            recent_text = "\n\n📜 Недавние запросы:\n" + "\n".join(lines)
        await query.edit_message_text(
            "🛠 Творческие инструменты студии КИСЛОРОД:\n\n"
            "🎬 Раскадровка — текстовая раскадровка сцены\n"
            "🎭 Персонаж — полная карточка героя\n"
            "📝 Сцена — сцена в сценарном формате\n"
            "🎤 Монолог — монолог с подтекстом для актёра\n"
            "🔁 Переписать — перенести текст в другой жанр\n"
            "💾 Сохранения — все твои работы по папкам"
            + recent_text,
            reply_markup=tools_keyboard(context),
        )
        return

    if action == "show_recent":
        recent = context.user_data.get("recent_requests", [])
        if not recent:
            await query.answer("История пуста", show_alert=False)
            return
        tool_labels = {
            "storyboard": "🎬 Раскадровка", "character": "🎭 Персонаж",
            "scene": "📝 Сцена", "monologue": "🎤 Монолог", "rewrite": "🔁 Перезапись",
        }
        lines = ["📜 Последние 3 запроса:\n"]
        repeat_buttons = []
        for i, r in enumerate(reversed(recent), 1):
            label = tool_labels.get(r["tool"], r["tool"])
            lines.append(f"{i}. {label}: {r['description']}")
            repeat_buttons.append([
                InlineKeyboardButton(
                    f"🔁 Повторить #{i}", callback_data=f"repeat|{r['tool']}|{r['description']}"
                )
            ])
        repeat_buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="show_tools")])
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(repeat_buttons),
        )
        return

    if action.startswith("repeat|"):
        parts = action.split("|", 2)
        if len(parts) == 3:
            _, tool, desc = parts
            context.user_data["awaiting"] = tool
            await query.edit_message_text(
                f"🔁 Повторяем: _{desc}_\n\nОтправь описание (или нажми отмену):",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
                ]]),
            )
        return

    if action == "back_to_hints":
        role_key = context.user_data.get("role", "general")
        welcome = ROLE_PROMPTS.get(role_key, ROLE_PROMPTS["general"])["welcome"]
        await query.edit_message_text(welcome, reply_markup=hints_keyboard(role_key, context))
        return

    if action == "tool_storyboard":
        context.user_data["awaiting"] = "storyboard"
        await query.edit_message_text(
            "🎬 Опиши сцену для раскадровки:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )
        _stats_inc_tool("storyboard")
        return

    if action == "tool_character":
        context.user_data["awaiting"] = "character"
        await query.edit_message_text(
            "🎭 Опиши персонажа:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )
        _stats_inc_tool("character")
        return

    if action == "tool_scene":
        context.user_data["awaiting"] = "scene"
        await query.edit_message_text(
            "📝 Опиши что должно произойти в сцене:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )
        _stats_inc_tool("scene")
        return

    if action == "tool_monologue":
        context.user_data["awaiting"] = "monologue"
        await query.edit_message_text(
            "🎤 Опиши персонажа и его состояние:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )
        _stats_inc_tool("monologue")
        return

    if action == "tool_rewrite":
        context.user_data["awaiting"] = "rewrite"
        await query.edit_message_text(
            "🔁 Отправь текст сцены или диалога для переписки:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )
        _stats_inc_tool("rewrite")
        return

    # ── СОХРАНЕНИЯ — ПАПКИ ─────────────────────

    if action == "show_saves":
        saves = _get_saves(context)
        if not saves:
            await query.edit_message_text(
                "💾 У тебя пока нет сохранённых работ.\n\n"
                "После генерации нажми кнопку 💾 Сохранить.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="back_to_hints"),
                ]]),
            )
            return
        folder_counts = {}
        for s in saves:
            folder_counts[s["type"]] = folder_counts.get(s["type"], 0) + 1
        folder_buttons = []
        for ftype, flabel in SAVE_FOLDERS.items():
            cnt = folder_counts.get(ftype, 0)
            if cnt > 0:
                folder_buttons.append([
                    InlineKeyboardButton(f"{flabel} ({cnt})", callback_data=f"folder|{ftype}")
                ])
        folder_buttons.append([
            InlineKeyboardButton("📤 Экспорт всех в TXT", callback_data="export_saves"),
        ])
        folder_buttons.append([
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_hints"),
        ])
        await query.edit_message_text(
            f"💾 Твои сохранения — {len(saves)} работ\n\nВыбери папку:",
            reply_markup=InlineKeyboardMarkup(folder_buttons),
        )
        return

    if action.startswith("folder|"):
        folder_type = action.split("|", 1)[1]
        saves = _get_saves(context)
        folder_saves = [s for s in saves if s["type"] == folder_type]
        if not folder_saves:
            await query.answer("Папка пуста", show_alert=False)
            return
        flabel = SAVE_FOLDERS.get(folder_type, folder_type)
        lines = [f"{flabel}\n"]
        for i, s in enumerate(folder_saves, 1):
            lines.append(f"{i}. {s['title']}")
        lines.append("\nОтправь номер чтобы получить работу.")
        context.user_data["awaiting"] = "view_save"
        context.user_data["view_save_folder"] = folder_type
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ К папкам", callback_data="show_saves"),
            ]]),
        )
        return

    if action == "export_saves":
        saves = _get_saves(context)
        if not saves:
            await query.answer("Нет сохранений для экспорта", show_alert=True)
            return
        await query.answer("⏳ Готовлю файл...", show_alert=False)
        lines = ["КИСЛОРОД ПРОДАКШЕН — Мои сохранённые работы\n", "=" * 40 + "\n"]
        for i, s in enumerate(saves, 1):
            label = SAVE_TYPE_LABELS.get(s["type"], s["type"])
            lines.append(f"\n{i}. {label}: {s['title']}\n")
            lines.append("-" * 30 + "\n")
            lines.append(s["content"] + "\n")
        import io
        bio = io.BytesIO("\n".join(lines).encode("utf-8"))
        bio.name = "kislorod_saves.txt"
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=bio,
            filename="kislorod_saves.txt",
            caption=f"📤 Все твои сохранения — {len(saves)} работ",
        )
        return

    # ── СОХРАНИТЬ РАБОТУ ───────────────────────

    if action.startswith("save|"):
        parts = action.split("|", 2)
        if len(parts) == 3:
            _, save_type, title = parts
            history = context.user_data.get("history", [])
            content = ""
            for msg in reversed(history):
                if msg["role"] == "assistant":
                    content = msg["text"]
                    break
            if not content:
                content = f"[{title}]"
            _add_save(context, save_type, title, content)
            label = SAVE_TYPE_LABELS.get(save_type, save_type)
            # ✅ Подтверждение с названием и счётчиком
            count = _saves_count(context)
            await query.answer(
                f"✅ Сохранено в {label}!\n«{title[:40]}»\nВсего сохранений: {count}",
                show_alert=True,
            )
        return

    # ── УПРАВЛЕНИЕ ─────────────────────────────

    if action == "change_role":
        context.user_data.clear()
        await query.edit_message_text(
            "🎬 Нажми кнопку 📋 Меню внизу, чтобы выбрать роль.",
            reply_markup=None,
        )
        return

    if action == "cancel_awaiting":
        context.user_data.pop("awaiting", None)
        await query.edit_message_text("❌ Отменено.")
        return

    if action == "new_storyboard":
        context.user_data["awaiting"] = "storyboard"
        await query.edit_message_text(
            "🎬 Опиши новую сцену для раскадровки:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )
        return

    if action == "new_character":
        context.user_data["awaiting"] = "character"
        await query.edit_message_text(
            "🎭 Опиши нового персонажа:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )
        return

    if action == "new_scene":
        context.user_data["awaiting"] = "scene"
        await query.edit_message_text(
            "📝 Опиши новую сцену:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )
        return

    if action == "new_monologue":
        context.user_data["awaiting"] = "monologue"
        await query.edit_message_text(
            "🎤 Опиши персонажа для монолога:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )
        return

    if action == "new_rewrite":
        context.user_data["awaiting"] = "rewrite"
        await query.edit_message_text(
            "🔁 Отправь текст для переписки:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )
        return

    if action == "clear_chat":
        context.user_data["history"] = []
        role_key = context.user_data.get("role")
        if role_key and role_key in ROLE_PROMPTS:
            await query.edit_message_text(
                ROLE_PROMPTS[role_key]["welcome"] + "\n\n✅ История очищена",
                reply_markup=hints_keyboard(role_key, context),
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
        _stats_inc_role(role_key)
        await query.edit_message_text(
            ROLE_PROMPTS[role_key]["welcome"],
            reply_markup=hints_keyboard(role_key, context),
        )
        return

    # ── ПОДСКАЗКИ ──────────────────────────────

    if action in HINT_TEXTS:
        role_key = context.user_data.get("role", "general")
        hint_text = HINT_TEXTS[action]
        chat_id = query.message.chat_id

        await context.bot.send_message(
            chat_id=chat_id, text=f"_{hint_text}_", parse_mode="Markdown",
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
        _stats["total_messages"] += 1

        kb = hints_keyboard(role_key, context)
        await context.bot.send_message(chat_id=chat_id, text=response, reply_markup=kb)
        return


# ─────────────────────────────────────────────
# WEBAPP DATA
# ─────────────────────────────────────────────

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.message.web_app_data.data.strip()
    role_key = data
    if role_key not in ROLE_PROMPTS:
        return
    context.user_data["role"] = role_key
    context.user_data["history"] = []
    _stats_inc_role(role_key)
    await update.message.reply_text(
        ROLE_PROMPTS[role_key]["welcome"],
        reply_markup=hints_keyboard(role_key),
    )


# ─────────────────────────────────────────────
# HANDLE MESSAGE
# ─────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if not user_text:
        return

    user_id = update.effective_user.id
    _stats["total_users"].add(user_id)
    _stats["total_messages"] += 1

    awaiting = context.user_data.get("awaiting")

    # Просмотр сохранения по номеру
    if awaiting == "view_save":
        context.user_data.pop("awaiting", None)
        folder_type = context.user_data.pop("view_save_folder", None)
        saves = _get_saves(context)
        # Фильтруем по папке если задана
        display_saves = [s for s in saves if s["type"] == folder_type] if folder_type else saves
        try:
            idx = int(user_text.strip()) - 1
            if 0 <= idx < len(display_saves):
                s = display_saves[idx]
                label = SAVE_TYPE_LABELS.get(s["type"], s["type"])
                role_key = context.user_data.get("role", "general")
                await update.message.reply_text(
                    f"{label}: {s['title']}\n\n{s['content']}",
                    reply_markup=hints_keyboard(role_key, context),
                )
            else:
                await update.message.reply_text("Нет сохранения с таким номером.")
        except ValueError:
            await update.message.reply_text("Отправь номер из списка, например: 1")
        return

    if awaiting == "storyboard":
        context.user_data.pop("awaiting", None)
        await _generate_storyboard(update, context, user_text)
        return
    if awaiting == "character":
        context.user_data.pop("awaiting", None)
        await _generate_character(update, context, user_text)
        return
    if awaiting == "scene":
        context.user_data.pop("awaiting", None)
        await _generate_scene(update, context, user_text)
        return
    if awaiting == "monologue":
        context.user_data.pop("awaiting", None)
        await _generate_monologue(update, context, user_text)
        return
    if awaiting == "rewrite":
        context.user_data["rewrite_text"] = user_text
        context.user_data["awaiting"] = "rewrite_style"
        await update.message.reply_text(
            "🎨 В каком жанре/стиле переписать?\n"
            "_Например: нуар, комедия, хоррор, советское кино_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )
        return
    if awaiting == "rewrite_style":
        context.user_data.pop("awaiting", None)
        original_text = context.user_data.pop("rewrite_text", "")
        await _generate_rewrite(update, context, original_text, user_text)
        return

    role_key = context.user_data.get("role")
    if not role_key:
        role_key = "general"
        context.user_data["role"] = role_key
        context.user_data["history"] = []
        await update.message.reply_text(
            "🌐 Роль не выбрана — отвечаю как общий ассистент. "
            "Нажми 📋 Меню, чтобы выбрать роль.",
            reply_markup=webapp_keyboard(),
        )

    history = context.user_data.get("history", [])
    chat_id = update.effective_chat.id

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

    if not response or not response.strip():
        response = "Не смог сформулировать ответ. Попробуй переформулировать или очисти историю."

    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]
    await update.message.reply_text(response, reply_markup=hints_keyboard(role_key, context))


# ─────────────────────────────────────────────
# ИНСТРУМЕНТЫ — КОМАНДЫ
# ─────────────────────────────────────────────

async def storyboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    _stats_inc_tool("storyboard")
    if args:
        await _generate_storyboard(update, context, " ".join(args))
    else:
        context.user_data["awaiting"] = "storyboard"
        await update.message.reply_text(
            "🎬 Раскадровка сцены\n\nОпиши сцену — жанр, локацию, персонажей, действие.\n\n"
            "_Например: Ночная улица, дождь. Детектив видит тело. Нуар._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )


async def _generate_storyboard(update: Update, context: ContextTypes.DEFAULT_TYPE, scene: str):
    chat_id = update.effective_chat.id
    _add_to_history(context, "storyboard", scene)

    progress_id = await send_progress(context.bot, chat_id, "🎬 Генерирую раскадровку...")

    system = (
        "Ты — опытный режиссёр и раскадровщик. "
        "Создаёшь детальные текстовые раскадровки. "
        "Отвечай ТОЛЬКО раскадровкой — без предисловий."
    )
    user_msg = (
        f"Создай текстовую раскадровку для сцены:\n\n{scene}\n\n"
        "Формат каждого кадра:\n"
        "━━━━━━━━━━━━━━━━\n"
        "КАДР [номер]\n"
        "Ракурс: ...\nЛокация: ...\nДействие: ...\nСвет: ...\nЗвук: ...\nРеплика: ...\nДлительность: ...\n\n"
        "5–8 кадров. После всех кадров:\n"
        "РЕЖИССЁРСКАЯ ЗАМЕТКА: [1–2 предложения об атмосфере]"
    )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))
    try:
        response = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    await delete_progress(context.bot, chat_id, progress_id)

    if not response or response.startswith("⚠️"):
        response = "Не удалось сгенерировать раскадровку. Попробуй снова."

    history = context.user_data.get("history", [])
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]

    short_title = scene[:30]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🎬 Раскадровка сцены\n\n{response}",
        reply_markup=InlineKeyboardMarkup([
            make_save_row("storyboard", short_title),
            [
                InlineKeyboardButton("🔄 Новая раскадровка", callback_data="new_storyboard"),
                InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role"),
            ],
        ]),
    )


async def character_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    _stats_inc_tool("character")
    if args:
        await _generate_character(update, context, " ".join(args))
    else:
        context.user_data["awaiting"] = "character"
        await update.message.reply_text(
            "🎭 Карточка персонажа\n\nОпиши персонажа — имя, возраст, жанр, роль в истории.\n\n"
            "_Например: Максим, 35 лет, бывший полицейский. Криминальный триллер._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )


async def _generate_character(update: Update, context: ContextTypes.DEFAULT_TYPE, description: str):
    chat_id = update.effective_chat.id
    _add_to_history(context, "character", description)
    progress_id = await send_progress(context.bot, chat_id, "🎭 Создаю карточку персонажа...")

    system = (
        "Ты — опытный сценарист и актёрский педагог. "
        "Создаёшь детальные карточки персонажей. "
        "Отвечай ТОЛЬКО карточкой — без предисловий."
    )
    user_msg = (
        f"Создай карточку персонажа:\n\n{description}\n\n"
        "👤 ИМЯ И ВОЗРАСТ\n🧬 ФИЗИЧЕСКИЙ ПОРТРЕТ\n🧠 ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ\n"
        "📖 ИСТОРИЯ И ПРЕДЫСТОРИЯ\n🎯 МОТИВАЦИЯ\n🗣 РЕЧЬ И ПОВЕДЕНИЕ\n"
        "🎭 СОВЕТЫ АКТЁРУ\n📊 АРК РАЗВИТИЯ"
    )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))
    try:
        response = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    await delete_progress(context.bot, chat_id, progress_id)

    if not response or response.startswith("⚠️"):
        response = "Не удалось создать карточку. Попробуй снова."

    history = context.user_data.get("history", [])
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]

    short_title = description[:30]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🎭 Карточка персонажа\n\n{response}",
        reply_markup=InlineKeyboardMarkup([
            make_save_row("character", short_title),
            [
                InlineKeyboardButton("🔄 Новый персонаж", callback_data="new_character"),
                InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role"),
            ],
        ]),
    )


async def scene_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    _stats_inc_tool("scene")
    if args:
        await _generate_scene(update, context, " ".join(args))
    else:
        context.user_data["awaiting"] = "scene"
        await update.message.reply_text(
            "📝 Написать сцену\n\nОпиши что должно произойти: место, персонажи, конфликт, жанр.\n\n"
            "_Например: Кухня, поздний вечер. Муж и жена выясняют отношения. Психологическая драма._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )


async def _generate_scene(update: Update, context: ContextTypes.DEFAULT_TYPE, description: str):
    chat_id = update.effective_chat.id
    _add_to_history(context, "scene", description)
    progress_id = await send_progress(context.bot, chat_id, "📝 Пишу сцену...")

    system = (
        "Ты — профессиональный сценарист студии КИСЛОРОД ПРОДАКШЕН. "
        "Пишешь сцены в сценарном формате: INT./EXT., ремарки, диалоги. "
        "Отвечай ТОЛЬКО текстом сцены."
    )
    user_msg = (
        f"Напиши сцену:\n\n{description}\n\n"
        "— Сценарный формат (INT./EXT., ремарки, реплики)\n"
        "— 150–300 слов\n— Живые диалоги\n— В конце: КОНЕЦ СЦЕНЫ"
    )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))
    try:
        response = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    await delete_progress(context.bot, chat_id, progress_id)

    if not response or response.startswith("⚠️"):
        response = "Не удалось написать сцену. Попробуй снова."

    history = context.user_data.get("history", [])
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]

    short_title = description[:30]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📝 Сцена\n\n{response}",
        reply_markup=InlineKeyboardMarkup([
            make_save_row("scene", short_title),
            [
                InlineKeyboardButton("📝 Новая сцена", callback_data="new_scene"),
                InlineKeyboardButton("🔁 Переписать", callback_data="new_rewrite"),
            ],
            [InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role")],
        ]),
    )


async def monologue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    _stats_inc_tool("monologue")
    if args:
        await _generate_monologue(update, context, " ".join(args))
    else:
        context.user_data["awaiting"] = "monologue"
        await update.message.reply_text(
            "🎤 Монолог для актёра\n\nОпиши персонажа и его состояние.\n\n"
            "_Например: Мужчина 40 лет, потерял работу. Говорит сыну что всё хорошо._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
            ]]),
        )


async def _generate_monologue(update: Update, context: ContextTypes.DEFAULT_TYPE, description: str):
    chat_id = update.effective_chat.id
    _add_to_history(context, "monologue", description)
    progress_id = await send_progress(context.bot, chat_id, "🎤 Пишу монолог...")

    system = (
        "Ты — опытный сценарист и актёрский педагог студии КИСЛОРОД ПРОДАКШЕН. "
        "Пишешь монологи: живые, психологически точные, с подтекстом. "
        "Отвечай ТОЛЬКО текстом монолога."
    )
    user_msg = (
        f"Напиши монолог:\n\n{description}\n\n"
        "— 60–120 слов\n— Живая разговорная речь\n— Подтекст важнее текста\n"
        "— После монолога: АКТЁРСКАЯ ЗАМЕТКА: [о ключевом подтексте]"
    )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))
    try:
        response = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    await delete_progress(context.bot, chat_id, progress_id)

    if not response or response.startswith("⚠️"):
        response = "Не удалось написать монолог. Попробуй снова."

    history = context.user_data.get("history", [])
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]

    short_title = description[:30]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🎤 Монолог\n\n{response}",
        reply_markup=InlineKeyboardMarkup([
            make_save_row("monologue", short_title),
            [
                InlineKeyboardButton("🎤 Новый монолог", callback_data="new_monologue"),
                InlineKeyboardButton("🔁 Переписать", callback_data="new_rewrite"),
            ],
            [InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role")],
        ]),
    )


async def rewrite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _stats_inc_tool("rewrite")
    context.user_data["awaiting"] = "rewrite"
    await update.message.reply_text(
        "🔁 Переписать в другом стиле\n\n"
        "Отправь текст сцены или диалога — я спрошу, в каком жанре переписать.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting"),
        ]]),
    )


async def _generate_rewrite(update, context, original_text, style):
    chat_id = update.effective_chat.id
    _add_to_history(context, "rewrite", f"{style}: {original_text[:30]}")
    progress_id = await send_progress(context.bot, chat_id, f"🔁 Переписываю в стиле «{style}»...")

    system = (
        "Ты — профессиональный сценарист студии КИСЛОРОД ПРОДАКШЕН. "
        "Переписываешь сцены в разных жанрах, сохраняя суть. "
        "Отвечай ТОЛЬКО переписанным текстом."
    )
    user_msg = (
        f"Перепиши в стиле «{style}»:\n\n{original_text}\n\n"
        f"— Сохрани суть, измени тон под «{style}»\n"
        "— В конце: РЕЖИССЁРСКАЯ ЗАМЕТКА: [главное отличие от оригинала]"
    )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))
    try:
        response = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    await delete_progress(context.bot, chat_id, progress_id)

    if not response or response.startswith("⚠️"):
        response = "Не удалось переписать. Попробуй снова."

    history = context.user_data.get("history", [])
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]

    short_title = f"{style[:20]} — {original_text[:15]}"
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔁 Переписано в стиле «{style}»\n\n{response}",
        reply_markup=InlineKeyboardMarkup([
            make_save_row("rewrite", short_title),
            [
                InlineKeyboardButton("🔁 Другой стиль", callback_data="new_rewrite"),
                InlineKeyboardButton("📝 Новая сцена", callback_data="new_scene"),
            ],
            [InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role")],
        ]),
    )


# ─────────────────────────────────────────────
# /saves — Просмотр сохранений через команду
# ─────────────────────────────────────────────

async def saves_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saves = _get_saves(context)
    if not saves:
        await update.message.reply_text(
            "💾 У тебя пока нет сохранённых работ.\n\n"
            "После генерации нажми кнопку 💾 Сохранить."
        )
        return
    folder_counts = {}
    for s in saves:
        folder_counts[s["type"]] = folder_counts.get(s["type"], 0) + 1
    folder_buttons = []
    for ftype, flabel in SAVE_FOLDERS.items():
        cnt = folder_counts.get(ftype, 0)
        if cnt > 0:
            folder_buttons.append([
                InlineKeyboardButton(f"{flabel} ({cnt})", callback_data=f"folder|{ftype}")
            ])
    folder_buttons.append([
        InlineKeyboardButton("📤 Экспорт всех в TXT", callback_data="export_saves"),
    ])
    await update.message.reply_text(
        f"💾 Твои сохранения — {len(saves)} работ\n\nВыбери папку:",
        reply_markup=InlineKeyboardMarkup(folder_buttons),
    )


# ─────────────────────────────────────────────
# /stats — Статистика (только для админа)
# ─────────────────────────────────────────────

@admin_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users = len(_stats["total_users"])
    total_messages = _stats["total_messages"]
    saves_total = _stats["saves_total"]
    posts_sent = _stats["posts_sent"]

    role_lines = []
    role_labels = {
        "actor": "🎭 Актёр", "director": "🎬 Режиссёр",
        "screenwriter": "✍️ Сценарист", "producer": "💼 Продюсер",
        "client": "🤝 Заказчик", "general": "🌐 Общий",
    }
    for key, count in sorted(_stats["roles_chosen"].items(), key=lambda x: -x[1]):
        label = role_labels.get(key, key)
        role_lines.append(f"  {label}: {count}")

    tool_lines = []
    tool_labels = {
        "storyboard": "🎬 Раскадровка", "character": "🎭 Персонаж",
        "scene": "📝 Сцена", "monologue": "🎤 Монолог", "rewrite": "🔁 Переписка",
    }
    for key, count in sorted(_stats["tools_used"].items(), key=lambda x: -x[1]):
        label = tool_labels.get(key, key)
        tool_lines.append(f"  {label}: {count}")

    text = (
        "📊 Статистика бота КИСЛОРОД AI\n\n"
        f"👥 Уникальных пользователей: {total_users}\n"
        f"💬 Всего сообщений: {total_messages}\n"
        f"💾 Сохранений создано: {saves_total}\n"
        f"📢 Постов опубликовано: {posts_sent}\n\n"
        "🎭 Выбор ролей:\n" + ("\n".join(role_lines) if role_lines else "  —") + "\n\n"
        "🛠 Использование инструментов:\n" + ("\n".join(tool_lines) if tool_lines else "  —") + "\n\n"
        "⚠️ Статистика сбрасывается при перезапуске бота."
    )
    await update.message.reply_text(text)


# ─────────────────────────────────────────────
# СПРАВКА И УТИЛИТЫ
# ─────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS

    base_text = (
        "🎬 КИСЛОРОД AI — Справка\n\n"
        "/start          — Онбординг / сменить роль\n"
        "/clear          — Очистить историю чата\n"
        "/saves          — 💾 Твои сохранённые работы\n"
        "/storyboard     — Раскадровка сцены 🎬\n"
        "/character      — Карточка персонажа 🎭\n"
        "/scene          — Написать сцену 📝\n"
        "/monologue      — Монолог для актёра 🎤\n"
        "/rewrite        — Переписать в другом стиле 🔁\n"
        "/streaming      — Где смотреть фильм 🍿\n"
        "/help           — Справка\n"
    )

    admin_text = (
        "\n── Только для администратора ──\n"
        "/stats          — 📊 Статистика бота\n"
        "/schedule       — Расписание автопостинга\n\n"
        "📰 Посты:\n"
        "/post_now       — Новости кино (оба канала)\n"
        "/trailer_now    — Трейлер фильма\n"
        "/film_now       — Новинка кино\n"
        "/series_now     — Рекомендация сериала\n"
        "/cartoon_now    — Мультфильм\n"
        "/poster_now     — Красивый постер\n"
        "/myfilm_now     — Пост из фильмографии\n"
    )

    footer = "\nКонтакты:\n📧 actorsashapotapov@gmail.com\n💬 @actorsashapotapov"
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
        "   🕙 10:00 — новости кино 📰\n"
        "   🕛 12:00 — новинка кино 🎞\n"
        "   🕑 14:00 — трейлер фильма 🎬\n"
        "   🕓 16:00 — мультфильм 🎨\n"
        "   🕖 19:00 — вечерний дайджест 📰\n"
        "   🕘 21:00 — красивый постер 🖼\n\n"
        "🎭 @actorsashapotapovv — 4 поста в день:\n"
        "   🕚 11:00 — утренний пост\n"
        "   🕐 13:00 — из фильмографии 🎬\n"
        "   🕒 15:00 — рекомендация сериала 📺\n"
        "   🕗 20:00 — вечерний пост\n\n"
        "Всего: 10 постов в день"
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
    await update.message.reply_text("⏳ Ищу трейлер (~15 сек)...")
    text, poster = await generate_trailer_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, poster)
        await send_post(context.bot, CHANNEL_ACTOR, text, poster)
        await update.message.reply_text("✅ Трейлер опубликован!")
    else:
        await update.message.reply_text("❌ Не удалось. Проверь KINOPOISK_API_KEY.")


@admin_only
async def film_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу новинку (~15 сек)...")
    text, img = await generate_new_film_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
        await update.message.reply_text("✅ Новинка опубликована!")
    else:
        await update.message.reply_text("❌ Не удалось. Проверь KINOPOISK_API_KEY.")


@admin_only
async def series_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу сериал (~15 сек)...")
    text, img = await generate_series_post()
    if text:
        await send_post(context.bot, CHANNEL_ACTOR, text, img)
        await update.message.reply_text("✅ Пост о сериале опубликован!")
    else:
        await update.message.reply_text("❌ Не удалось. Проверь KINOPOISK_API_KEY.")


@admin_only
async def cartoon_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу мультфильм (~15 сек)...")
    text, img = await generate_cartoon_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
        await update.message.reply_text("✅ Пост о мультфильме опубликован!")
    else:
        await update.message.reply_text("❌ Не удалось. Проверь KINOPOISK_API_KEY.")


@admin_only
async def poster_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу постер (~15 сек)...")
    text, img = await generate_poster_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
        await update.message.reply_text("✅ Постер опубликован!")
    else:
        await update.message.reply_text("❌ Не удалось. Проверь KINOPOISK_API_KEY.")


@admin_only
async def myfilm_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Пишу пост о проекте (~15 сек)...")
    text, img = await generate_filmography_post()
    if text:
        await send_post(context.bot, CHANNEL_ACTOR, text, img)
        await update.message.reply_text("✅ Пост о проекте опубликован!")
    else:
        await update.message.reply_text("❌ Не удалось. Попробуй снова.")


# ─────────────────────────────────────────────
# STREAMING AVAILABILITY (RapidAPI)
# ─────────────────────────────────────────────

STREAMING_NAMES = {
    "netflix":        "Netflix",
    "prime":          "Amazon Prime Video",
    "appletv":        "Apple TV+",
    "disney":         "Disney+",
    "hbo":            "HBO Max",
    "hulu":           "Hulu",
    "peacock":        "Peacock",
    "paramount":      "Paramount+",
    "mubi":           "MUBI",
    "curiosity":      "Curiosity Stream",
    "ivi":            "IVI",
    "okko":           "Okko",
    "kinopoisk":      "Кинопоиск HD",
    "more":           "MORE.TV",
    "start":          "START",
    "wink":           "Wink",
}


async def fetch_streaming_info(title: str) -> dict:
    """Ищет фильм/сериал через Streaming Availability API и возвращает данные."""
    logger.info(f"=== STREAMING SEARCH: '{title}' ===")
    logger.info(f"=== RAPIDAPI_KEY: {RAPIDAPI_KEY[:10]}... ===")
    headers = {
        "x-rapidapi-host": "streaming-availability.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            search_resp = await client.get(
                "https://streaming-availability.p.rapidapi.com/shows/search/title",
                headers=headers,
                params={"title": title, "show_type": "all"},
            )
            logger.info(f"=== STATUS: {search_resp.status_code} ===")
            logger.info(f"=== BODY: {search_resp.text[:500]} ===")

            if search_resp.status_code != 200:
                logger.error(f"Streaming API error {search_resp.status_code}: {search_resp.text[:200]}")
                return {}

            results = search_resp.json()
            logger.info(f"=== RESULTS COUNT: {len(results) if isinstance(results, list) else type(results)} ===")

            if not results or not isinstance(results, list):
                return {}

            show = results[0]
            show_id    = show.get("id", "")
            show_type  = show.get("showType", "movie")
            title_ru   = show.get("title", title)
            title_orig = show.get("originalTitle", "")
            year       = show.get("releaseYear", "")
            overview   = show.get("overview", "")
            poster_url = (show.get("imageSet") or {}).get("verticalPoster", {}).get("w480", "") or \
                         (show.get("imageSet") or {}).get("horizontalPoster", {}).get("w480", "")
            rating     = show.get("rating", "")

            streaming_options = show.get("streamingOptions", {}).get("ru", [])
            logger.info(f"=== STREAMING OPTIONS RU: {len(streaming_options)} ===")

            services = []
            seen = set()
            for opt in streaming_options:
                service_id   = (opt.get("service") or {}).get("id", "")
                service_name = STREAMING_NAMES.get(service_id, service_id.capitalize())
                stream_type  = opt.get("type", "")
                link         = opt.get("link", "")
                if service_id and service_id not in seen:
                    seen.add(service_id)
                    type_label = {"subscription": "подписка", "rent": "аренда",
                                  "buy": "покупка", "free": "бесплатно"}.get(stream_type, stream_type)
                    services.append({"name": service_name, "type": type_label, "link": link})

            return {
                "id":         show_id,
                "type":       show_type,
                "title":      title_ru,
                "orig_title": title_orig,
                "year":       year,
                "overview":   overview,
                "poster":     poster_url,
                "rating":     rating,
                "services":   services,
            }

    except Exception as e:
        logger.error(f"fetch_streaming_info error: {type(e).__name__}: {e}")
        return {}


def _format_streaming_post(info: dict) -> str:
    """Форматирует пост о стриминге для Telegram."""
    type_emoji = "🎬" if info["type"] == "movie" else "📺"
    title_line = f"{type_emoji} *{info['title']}*"
    if info.get("orig_title") and info["orig_title"] != info["title"]:
        title_line += f" / _{info['orig_title']}_"
    if info.get("year"):
        title_line += f" ({info['year']})"

    lines = [title_line]

    if info.get("rating"):
        lines.append(f"⭐ Рейтинг: {info['rating']}/100")

    if info.get("overview"):
        overview = info["overview"][:300]
        if len(info["overview"]) > 300:
            overview += "..."
        lines.append(f"\n📝 {overview}")

    if info["services"]:
        lines.append("\n🇷🇺 *Где смотреть в России:*")
        for svc in info["services"]:
            link_part = f" — [смотреть]({svc['link']})" if svc.get("link") else ""
            lines.append(f"  • {svc['name']} ({svc['type']}){link_part}")
    else:
        lines.append("\n❌ В российских стриминговых сервисах не найдено")

    lines.append("\n#стриминг #кино #кислородпродакшен")
    return "\n".join(lines)


async def streaming_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /streaming <название фильма или сериала>
    Ищет, где смотреть в России, отвечает пользователю и постит в оба канала.
    """
    query_title = " ".join(context.args).strip() if context.args else ""
    if not query_title:
        await update.message.reply_text(
            "🎬 Использование:\n/streaming <название>\n\nПример: /streaming Дюна"
        )
        return

    await update.message.reply_text(f"🔍 Ищу «{query_title}»...")

    info = await fetch_streaming_info(query_title)

    if not info:
        await update.message.reply_text(
            f"❌ Фильм или сериал «{query_title}» не найден.\n"
            "Попробуй написать название на английском."
        )
        return

    post_text = _format_streaming_post(info)
    poster    = info.get("poster", "")

    # 1. Ответить пользователю
    try:
        if poster:
            await update.message.reply_photo(photo=poster, caption=post_text, parse_mode="Markdown")
        else:
            await update.message.reply_text(post_text, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"streaming reply error: {e}")
        await update.message.reply_text(post_text, parse_mode="Markdown")

    # 2. Опубликовать в оба канала
    await send_post(context.bot, CHANNEL_KISLOROD, post_text, poster)
    await send_post(context.bot, CHANNEL_ACTOR,    post_text, poster)

    await update.message.reply_text("✅ Пост опубликован в оба канала!")


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
    logger.info(f"RAPIDAPI_KEY:      {'✅' if RAPIDAPI_KEY      else '❌ НЕ ЗАДАН'}")
    logger.info(f"ADMIN_IDS:         {ADMIN_IDS}")

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды для всех
    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("help",         help_command))
    app.add_handler(CommandHandler("clear",        clear_command))
    app.add_handler(CommandHandler("saves",        saves_command))
    app.add_handler(CommandHandler("storyboard",   storyboard_command))
    app.add_handler(CommandHandler("character",    character_command))
    app.add_handler(CommandHandler("scene",        scene_command))
    app.add_handler(CommandHandler("monologue",    monologue_command))
    app.add_handler(CommandHandler("rewrite",      rewrite_command))
    app.add_handler(CommandHandler("streaming",    streaming_command))

    # Только для администратора
    app.add_handler(CommandHandler("stats",        stats_command))
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
    app.job_queue.run_daily(job_kislorod_morning,   time=dtime(7,  0))   # 10:00 МСК
    app.job_queue.run_daily(job_kislorod_new_film,  time=dtime(9,  0))   # 12:00 МСК
    app.job_queue.run_daily(job_kislorod_trailer,   time=dtime(11, 0))   # 14:00 МСК
    app.job_queue.run_daily(job_kislorod_cartoon,   time=dtime(13, 0))   # 16:00 МСК
    app.job_queue.run_daily(job_kislorod_evening,   time=dtime(16, 0))   # 19:00 МСК
    app.job_queue.run_daily(job_kislorod_poster,    time=dtime(18, 0))   # 21:00 МСК
    app.job_queue.run_daily(job_actor_morning,      time=dtime(8,  0))   # 11:00 МСК
    app.job_queue.run_daily(job_actor_filmography,  time=dtime(10, 0))   # 13:00 МСК
    app.job_queue.run_daily(job_actor_series,       time=dtime(12, 0))   # 15:00 МСК
    app.job_queue.run_daily(job_actor_evening,      time=dtime(17, 0))   # 20:00 МСК

    logger.info("=== Расписание запущено. Bot работает! ===")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
