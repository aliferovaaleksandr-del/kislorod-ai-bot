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
# ✅ ИСПРАВЛЕНО: убран захардкоженный ключ — только из переменных окружения
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
IMAGE_STYLE = os.getenv("IMAGE_STYLE", "pixar")  # pixar | comic | anime | cinematic | watercolor

CHANNEL_KISLOROD = "@realtimeproductionn"
CHANNEL_ACTOR = "@actorsashapotapovv"

WEBAPP_URL = "https://aliferovaaleksandr-del.github.io/kislorod-ai-bot/menu.html"

ADMIN_IDS = {380171031}

# ─────────────────────────────────────────────
# ГЛОБАЛЬНАЯ СТАТИСТИКА
# ─────────────────────────────────────────────
_stats = {
    "total_users": set(),
    "total_messages": 0,
    "roles_chosen": {},
    "tools_used": {},
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
logging.getLogger("httpx").setLevel(logging.WARNING)


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
        [
            InlineKeyboardButton("🖼 Генератор постера", callback_data="tool_poster"),
            InlineKeyboardButton("📄 Разбор сценария", callback_data="tool_analyze"),
        ],
        [
            InlineKeyboardButton("🎯 AI-Питчинг", callback_data="tool_pitch"),
        ],
    ]
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
# KINOAFISHA.INFO — ПАРСЕР ПРЕМЬЕР
# ─────────────────────────────────────────────

_kinoafisha_cache: list = []
_kinoafisha_cache_time: float = 0
_CACHE_TTL = 3600  # обновляем кэш раз в час

async def fetch_kinoafisha_premieres(url: str = "https://www.kinoafisha.info/releases/") -> list[dict]:
    """
    Парсит kinoafisha.info — статический HTML, работает без JS.
    Возвращает список словарей: title, description, genre, year, country, poster_url, movie_url, date.
    """
    import time as _time
    global _kinoafisha_cache, _kinoafisha_cache_time

    # Возвращаем кэш если свежий
    if _kinoafisha_cache and (_time.time() - _kinoafisha_cache_time) < _CACHE_TTL:
        logger.info(f"kinoafisha: возвращаю кэш ({len(_kinoafisha_cache)} фильмов)")
        return _kinoafisha_cache

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 не установлен! Добавь в requirements.txt: beautifulsoup4")
        return []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
            resp = await client.get(url)

        if resp.status_code != 200:
            logger.error(f"kinoafisha: статус {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        movies = []
        current_date = ""

        for tag in soup.find_all(True):
            # Дата группы (например "21 мая 2026")
            if tag.name in ("h2", "h3", "div") and tag.get("class"):
                classes = " ".join(tag.get("class", []))
                if any(k in classes for k in ("date", "release-date", "group")):
                    text = tag.get_text(strip=True)
                    if any(m in text for m in [
                        "января","февраля","марта","апреля","мая","июня",
                        "июля","августа","сентября","октября","ноября","декабря"
                    ]):
                        current_date = text

        # Основной парсинг — карточки фильмов
        # kinoafisha использует структуру с <a> внутри секций с датой
        # Ищем все блоки дат и фильмы под ними
        content = soup.get_text(separator="\n")

        # Парсим через структуру ссылок на фильмы
        all_movie_links = soup.find_all("a", href=lambda h: h and "/movies/" in h)
        seen_urls = set()
        current_date = ""

        # Перебираем весь DOM в порядке появления
        for elem in soup.descendants:
            if not hasattr(elem, "name"):
                continue

            # Детектируем дату-заголовок группы
            if elem.name in ("h2", "h3", "p", "div", "span"):
                txt = elem.get_text(strip=True)
                if (len(txt) < 30 and any(m in txt for m in [
                    "января","февраля","марта","апреля","мая","июня",
                    "июля","августа","сентября","октября","ноября","декабря"
                ])):
                    current_date = txt

            # Карточка фильма — ищем <a href="/movies/..."> с img внутри
            if elem.name == "a" and elem.get("href", "").startswith("/movies/"):
                movie_url = "https://www.kinoafisha.info" + elem["href"]
                if movie_url in seen_urls:
                    continue
                seen_urls.add(movie_url)

                # Постер
                img = elem.find("img")
                poster_url = ""
                if img:
                    poster_url = img.get("src", "") or img.get("data-src", "")
                    # Заменяем thumbnail на нормальный размер
                    if "90x150" in poster_url:
                        poster_url = poster_url.replace("90x150", "220x315")

                # Название — из title атрибута img или текста ссылки
                title = ""
                if img:
                    title = img.get("title", "") or img.get("alt", "")
                if not title:
                    title = elem.get_text(strip=True)

                if not title or len(title) < 2:
                    continue

                # Ищем описание, жанр, год рядом с карточкой (в родительском блоке)
                description = ""
                genre = ""
                year = ""
                country = ""

                parent = elem.parent
                if parent:
                    # Ищем текстовые блоки рядом
                    for sib in parent.find_all(["p", "span", "div"]):
                        sib_text = sib.get_text(strip=True)
                        # Жанр+год обычно вида "боевик, триллер 2026, США"
                        if sib_text and any(c.isdigit() for c in sib_text) and len(sib_text) < 80:
                            # Пробуем разобрать
                            parts = sib_text.rsplit(" ", 2)
                            if len(parts) >= 2:
                                year_candidate = [p for p in parts if p.isdigit() and len(p) == 4]
                                if year_candidate:
                                    year = year_candidate[0]
                                    country = parts[-1] if not parts[-1].isdigit() else ""
                                    genre = sib_text.split(year)[0].strip().rstrip(",").strip()
                        # Описание — более длинный текст
                        elif sib_text and 10 < len(sib_text) < 300 and not any(
                            x in sib_text for x in ["Билеты", "Напомнить", "Реклама"]
                        ):
                            if not description:
                                description = sib_text

                movies.append({
                    "title": title,
                    "description": description,
                    "genre": genre,
                    "year": year,
                    "country": country,
                    "poster_url": poster_url,
                    "movie_url": movie_url,
                    "date": current_date,
                })

        # Убираем дубликаты по названию
        seen_titles = set()
        unique = []
        for m in movies:
            if m["title"] not in seen_titles and m["title"]:
                seen_titles.add(m["title"])
                unique.append(m)

        logger.info(f"kinoafisha: спарсено {len(unique)} фильмов с {url}")

        if unique:
            _kinoafisha_cache = unique
            import time as _time2
            _kinoafisha_cache_time = _time2.time()

        return unique

    except Exception as e:
        logger.error(f"kinoafisha parse error: {e}")
        return []


async def fetch_kinoafisha_all() -> dict[str, list]:
    """Загружает премьеры со всех разделов kinoafisha одновременно."""
    results = await asyncio.gather(
        fetch_kinoafisha_premieres("https://www.kinoafisha.info/releases/"),
        fetch_kinoafisha_premieres("https://www.kinoafisha.info/releases/online/"),
        return_exceptions=True,
    )
    cinema = results[0] if not isinstance(results[0], Exception) else []
    online = results[1] if not isinstance(results[1], Exception) else []
    return {"cinema": cinema, "online": online}


_used_kinoafisha_ids: set = set()


def _pick_kinoafisha(movies: list, genre_filter: str = None) -> dict:
    """Выбирает случайный фильм из списка kinoafisha, избегая повторов."""
    if genre_filter:
        filtered = [m for m in movies if genre_filter.lower() in m.get("genre", "").lower()]
        if filtered:
            movies = filtered

    random.shuffle(movies)
    for m in movies:
        mid = m.get("movie_url", m.get("title", ""))
        if mid not in _used_kinoafisha_ids:
            return m

    # Все показаны — сбрасываем
    _used_kinoafisha_ids.clear()
    return movies[0] if movies else {}


def _build_kinoafisha_post(movie: dict, emoji: str, hashtags: str) -> tuple[str, str]:
    """Собирает текст поста из объекта kinoafisha."""
    title = movie.get("title", "—")
    description = movie.get("description", "")
    genre = movie.get("genre", "")
    year = movie.get("year", "")
    country = movie.get("country", "")
    poster_url = movie.get("poster_url", "")
    movie_url = movie.get("movie_url", "")
    date = movie.get("date", "")

    lines = [f"{emoji} *{title}*"]
    if year:
        year_country = f"{year}"
        if country:
            year_country += f", {country}"
        lines[0] += f" ({year_country})"
    if genre:
        lines.append(f"🎭 {genre.capitalize()}")
    if date:
        lines.append(f"📅 В кино: {date}")
    if description:
        lines.append(f"\n{description}")
    if movie_url:
        lines.append(f"\n🔗 [Подробнее на Киноафише]({movie_url})")
    lines.append(f"\n{hashtags}")

    return "\n".join(lines), poster_url


async def generate_kinoafisha_film_post() -> tuple[str, str]:
    """Новинка — фильм из kinoafisha (не мультик)."""
    data = await fetch_kinoafisha_all()
    movies = data["cinema"] + data["online"]
    # Исключаем анимацию
    movies = [m for m in movies if "анимац" not in m.get("genre", "").lower()
              and "мульт" not in m.get("genre", "").lower()]
    if not movies:
        return await _generate_gpt_film_post(), ""
    movie = _pick_kinoafisha(movies)
    if not movie:
        return await _generate_gpt_film_post(), ""
    _used_kinoafisha_ids.add(movie.get("movie_url", movie.get("title")))
    return _build_kinoafisha_post(movie, "🎬", "#кино #новинка #фильм #кислородпродакшен")


async def generate_kinoafisha_cartoon_post() -> tuple[str, str]:
    """Мультфильм / анимация из kinoafisha."""
    data = await fetch_kinoafisha_all()
    movies = data["cinema"] + data["online"]
    movie = _pick_kinoafisha(movies, genre_filter="анимац")
    if not movie:
        # Пробуем без фильтра жанра — ищем по ключевым словам в названии
        movie = _pick_kinoafisha(
            [m for m in movies if any(k in m.get("title", "").lower()
             for k in ["лео", "тиг", "кот", "коты", "мульт", "приключ"])]
        )
    if not movie:
        return await _generate_gpt_cartoon_post(), ""
    _used_kinoafisha_ids.add(movie.get("movie_url", movie.get("title")))
    return _build_kinoafisha_post(movie, "🎨", "#мультфильм #анимация #кислородпродакшен")


async def generate_kinoafisha_premiere_post() -> tuple[str, str]:
    """Ближайшая премьера из kinoafisha."""
    data = await fetch_kinoafisha_all()
    movies = data["cinema"]  # только кинотеатральные
    if not movies:
        movies = data["online"]
    if not movies:
        return await _generate_gpt_film_post(), ""
    # Берём первые по дате (они идут в хронологическом порядке на странице)
    movie = _pick_kinoafisha(movies[:15])
    if not movie:
        return await _generate_gpt_film_post(), ""
    _used_kinoafisha_ids.add(movie.get("movie_url", movie.get("title")))
    return _build_kinoafisha_post(movie, "🔥", "#премьера #новинка #кино #кислородпродакшен")


async def generate_kinoafisha_news_post() -> tuple[str, str]:
    """
    Генерирует развёрнутый пост через YandexGPT на основе данных kinoafisha.
    Используется для новостных постов когда нет NewsAPI.
    """
    data = await fetch_kinoafisha_all()
    movies = (data["cinema"] + data["online"])[:8]

    if not movies:
        return await _generate_gpt_film_post(), ""

    movies_text = ""
    for i, m in enumerate(movies, 1):
        movies_text += f"{i}. «{m['title']}»"
        if m.get("genre"):
            movies_text += f" — {m['genre']}"
        if m.get("year"):
            movies_text += f" ({m['year']})"
        if m.get("description"):
            movies_text += f"\n   {m['description'][:100]}"
        movies_text += "\n"

    system = (
        "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН о кино. "
        "Отвечай ТОЛЬКО текстом поста — без пояснений, без markdown, без кавычек."
    )
    user_msg = (
        f"Ближайшие кинопремьеры в России:\n\n{movies_text}\n\n"
        "Напиши живой пост-дайджест для Telegram-канала о ближайших премьерах.\n"
        "— 150–250 слов\n— Живой разговорный стиль\n— 1–2 эмодзи\n"
        "— Хэштеги: #кино #премьеры #кислородпродакшен"
    )

    text = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])

    # Постер первого фильма если есть
    poster = movies[0].get("poster_url", "") if movies else ""
    return text, poster


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
    msg = await bot.send_message(chat_id=chat_id, text=f"{label}\n\n{PROGRESS_FRAMES[0]}")
    for frame in PROGRESS_FRAMES[1:]:
        await asyncio.sleep(0.9)
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=msg.message_id, text=f"{label}\n\n{frame}",
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
    "producer":   "🎯 Питч",
}

SAVE_FOLDERS = {
    "storyboard": "🎬 Раскадровки",
    "character":  "🎭 Персонажи",
    "scene":      "📝 Сцены",
    "monologue":  "🎤 Монологи",
    "rewrite":    "🔁 Перезаписи",
    "chat":       "💬 Ответы",
    "producer":   "🎯 Питчи",
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
    history = context.user_data.get("recent_requests", [])
    entry = {"tool": tool, "description": description[:60]}
    if not history or history[-1]["description"] != entry["description"]:
        history.append(entry)
    if len(history) > 3:
        history.pop(0)
    context.user_data["recent_requests"] = history


def save_keyboard(save_type: str, title: str) -> InlineKeyboardButton:
    short_title = title[:30]
    return InlineKeyboardButton("💾 Сохранить", callback_data=f"save|{save_type}|{short_title}")


def make_save_row(save_type: str, title: str) -> list:
    return [save_keyboard(save_type, title)]


def hints_keyboard_with_count(role_key: str, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
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
# STREAMING AVAILABILITY — СЛОВАРЬ СЕРВИСОВ
# ─────────────────────────────────────────────

STREAMING_NAMES = {
    "netflix":    "Netflix",
    "prime":      "Amazon Prime Video",
    "appletv":    "Apple TV+",
    "disney":     "Disney+",
    "hbo":        "HBO Max",
    "hulu":       "Hulu",
    "peacock":    "Peacock",
    "paramount":  "Paramount+",
    "mubi":       "MUBI",
    "curiosity":  "Curiosity Stream",
    "ivi":        "IVI",
    "okko":       "Okko",
    "kinopoisk":  "Кинопоиск HD",
    "more":       "MORE.TV",
    "start":      "START",
    "wink":       "Wink",
}

_used_show_ids: set = set()


# ─────────────────────────────────────────────
# STREAMING AVAILABILITY API
# ─────────────────────────────────────────────

async def fetch_streaming_shows(
    show_type: str = "movie",
    order_by: str = "popularity_1week",
    genres: list = None,
    page: int = 1,
    country: str = "ru",
) -> list:
    if not RAPIDAPI_KEY:
        logger.warning("RAPIDAPI_KEY не задан — Streaming API недоступен")
        return []

    headers = {
        "x-rapidapi-host": "streaming-availability.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    params = {
        "country": country,
        "order_by": order_by,
        "show_type": show_type,
        "series_granularity": "show",
        "output_language": "en",
        "rating_min": 55,
        "page": page,
    }
    if genres:
        params["genres"] = ",".join(genres)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                "https://streaming-availability.p.rapidapi.com/shows/search/filters",
                headers=headers,
                params=params,
            )
        logger.info(f"Streaming [{show_type}] country={country} status={resp.status_code}")
        if resp.status_code == 403:
            logger.error("Streaming API 403 — проверь RAPIDAPI_KEY или план подписки")
            return []
        if resp.status_code == 429:
            logger.error("Streaming API 429 — превышен лимит запросов")
            return []
        if resp.status_code != 200:
            logger.error(f"Streaming API error {resp.status_code}: {resp.text[:300]}")
            return []
        data = resp.json()
        shows = data.get("shows", [])
        logger.info(f"Streaming [{show_type}] country={country} → найдено {len(shows)} шоу")
        return shows
    except Exception as e:
        logger.error(f"fetch_streaming_shows error: {e}")
        return []


async def fetch_streaming_shows_with_fallback(
    show_type: str = "movie",
    order_by: str = "popularity_1week",
    genres: list = None,
) -> list:
    for country in ["ru", "us", "de"]:
        shows = await fetch_streaming_shows(show_type, order_by, genres, country=country)
        if shows:
            logger.info(f"Streaming: использован country={country}")
            return shows
        logger.warning(f"Streaming: country={country} вернул пустой список")
    logger.error("Streaming: все страны (ru/us/de) вернули пустой список")
    return []


def _pick_show(shows: list) -> dict:
    random.shuffle(shows)
    for show in shows:
        if show.get("id") not in _used_show_ids:
            return show
    _used_show_ids.clear()
    return shows[0] if shows else {}


def _build_streaming_post(show: dict, emoji: str, hashtags: str) -> tuple[str, str]:
    title      = show.get("title", "—")
    orig_title = show.get("originalTitle", "")
    year       = show.get("releaseYear") or show.get("firstAirYear", "")
    overview   = (show.get("overview") or "")[:280]
    rating     = show.get("rating", "")
    genres     = ", ".join(g.get("name", "") for g in (show.get("genres") or [])[:3])
    poster_url = (
        (show.get("imageSet") or {}).get("verticalPoster", {}).get("w480", "")
        or (show.get("imageSet") or {}).get("horizontalPoster", {}).get("w480", "")
        or ""
    )

    options = (show.get("streamingOptions") or {}).get("ru", [])
    services, seen = [], set()
    for opt in options:
        sid   = (opt.get("service") or {}).get("id", "")
        sname = STREAMING_NAMES.get(sid, sid.capitalize())
        stype = {"subscription": "подписка", "rent": "аренда",
                 "buy": "покупка", "free": "бесплатно"}.get(opt.get("type", ""), "")
        link  = opt.get("link", "")
        if sid and sid not in seen:
            seen.add(sid)
            services.append({"name": sname, "type": stype, "link": link})

    lines = [f"{emoji} *{title}*"]
    if orig_title and orig_title != title:
        lines[0] += f" / _{orig_title}_"
    if year:
        lines[0] += f" ({year})"
    if rating:
        lines.append(f"⭐ Рейтинг: {rating}/100")
    if genres:
        lines.append(f"🎭 {genres}")
    if overview:
        lines.append(f"\n{overview}")
    if services:
        lines.append("\n🇷🇺 *Где смотреть:*")
        for svc in services[:4]:
            link_part = f" — [смотреть]({svc['link']})" if svc.get("link") else ""
            lines.append(f"  • {svc['name']} ({svc['type']}){link_part}")
    else:
        lines.append("\n🔍 Доступность в России уточняется")
    lines.append(f"\n{hashtags}")

    return "\n".join(lines), poster_url


# ─────────────────────────────────────────────
# ГЕНЕРАТОРЫ ПОСТОВ — ПОЛНАЯ ЦЕПОЧКА ИСТОЧНИКОВ
# Приоритет: Kinoafisha → TMDB → Streaming → GPT
# ─────────────────────────────────────────────

async def generate_streaming_film_post() -> tuple[str, str]:
    """Фильм: Kinoafisha → TMDB → Streaming → GPT"""
    # 1. Kinoafisha
    result = await generate_kinoafisha_film_post()
    if result[0] and not result[0].startswith("⚠️"):
        return result
    # 2. TMDB
    if TMDB_API_KEY:
        result = await generate_tmdb_film_post()
        if result[0]:
            return result
    # 3. Streaming API
    shows = await fetch_streaming_shows_with_fallback("movie", order_by="popularity_1week")
    shows = [s for s in shows if not any(
        g.get("id") in ("animation", "family") for g in (s.get("genres") or [])
    )]
    if not shows:
        shows = await fetch_streaming_shows_with_fallback("movie", order_by="popularity_alltime")
    show = _pick_show(shows)
    if show:
        _used_show_ids.add(show.get("id"))
        return _build_streaming_post(show, emoji="🎬", hashtags="#кино #новинка #фильм #кислородпродакшен")
    # 4. GPT fallback
    return await _generate_gpt_film_post(), ""


async def generate_streaming_series_post() -> tuple[str, str]:
    """Сериал: TMDB → Streaming → GPT (kinoafisha не парсит сериалы отдельно)"""
    if TMDB_API_KEY:
        result = await generate_tmdb_series_post()
        if result[0]:
            return result
    shows = await fetch_streaming_shows_with_fallback("series", order_by="popularity_1week")
    if not shows:
        shows = await fetch_streaming_shows_with_fallback("series", order_by="popularity_alltime")
    show = _pick_show(shows)
    if show:
        _used_show_ids.add(show.get("id"))
        return _build_streaming_post(show, emoji="📺", hashtags="#сериал #новинка #стриминг #кислородпродакшен")
    return await _generate_gpt_series_post(), ""


async def generate_streaming_cartoon_post() -> tuple[str, str]:
    """Мультфильм: Kinoafisha → TMDB → Streaming → GPT"""
    # 1. Kinoafisha
    result = await generate_kinoafisha_cartoon_post()
    if result[0] and not result[0].startswith("⚠️"):
        return result
    # 2. TMDB
    if TMDB_API_KEY:
        result = await generate_tmdb_cartoon_post()
        if result[0]:
            return result
    # 3. Streaming
    shows = await fetch_streaming_shows_with_fallback("movie", genres=["animation"])
    if not shows:
        all_shows = await fetch_streaming_shows_with_fallback("movie", order_by="popularity_alltime")
        shows = [s for s in all_shows if any(
            g.get("id") in ("animation", "family") for g in (s.get("genres") or [])
        )]
    show = _pick_show(shows)
    if show:
        _used_show_ids.add(show.get("id"))
        return _build_streaming_post(show, emoji="🎨", hashtags="#мультфильм #анимация #кислородпродакшен")
    return await _generate_gpt_cartoon_post(), ""


async def generate_streaming_premiere_post() -> tuple[str, str]:
    """Премьера: Kinoafisha → TMDB → Streaming → GPT"""
    # 1. Kinoafisha — самые свежие
    result = await generate_kinoafisha_premiere_post()
    if result[0] and not result[0].startswith("⚠️"):
        return result
    # 2. TMDB
    if TMDB_API_KEY:
        result = await generate_tmdb_premiere_post()
        if result[0]:
            return result
    # 3. Streaming
    shows = await fetch_streaming_shows_with_fallback("movie", order_by="release_year")
    if not shows:
        shows = await fetch_streaming_shows_with_fallback("series", order_by="release_year")
    show = _pick_show(shows)
    if show:
        _used_show_ids.add(show.get("id"))
        return _build_streaming_post(show, emoji="🔥", hashtags="#премьера #новинка #кино #кислородпродакшен")
    return await _generate_gpt_film_post(), ""


# ─────────────────────────────────────────────
# TOGETHER AI — FLUX
# ─────────────────────────────────────────────

async def generate_together_image(prompt: str) -> bytes | None:
    if not TOGETHER_API_KEY:
        logger.warning("Together AI: нет TOGETHER_API_KEY")
        return None

    STYLE_SUFFIXES = {
        "pixar": (
            ", Pixar 3D animation style, Disney Pixar movie render, "
            "full body character, expressive cartoon face, vibrant colors, "
            "studio lighting, 8k render, smooth 3D, whole person visible head to toe"
        ),
        "comic": (
            ", Marvel comic book art style, bold ink outlines, "
            "full body shot, dynamic pose, vivid saturated colors, "
            "superhero poster art, sharp clean lines, whole character visible"
        ),
        "anime": (
            ", Studio Ghibli anime style, full body character, "
            "detailed anime face, large expressive eyes, soft cel shading, "
            "vibrant anime colors, whole person visible head to toe"
        ),
        "cinematic": (
            ", cinematic movie poster, full body shot, sharp focus on face, "
            "photorealistic skin, dramatic lighting, 8k, anamorphic lens, "
            "whole person visible, professional photography"
        ),
        "watercolor": (
            ", watercolor painting style, full body illustration, "
            "loose brushstrokes, soft color washes, artistic concept art, "
            "warm palette, whole character visible head to toe"
        ),
    }

    suffix = STYLE_SUFFIXES.get(IMAGE_STYLE, STYLE_SUFFIXES["pixar"])
    full_prompt = (
        prompt + suffix +
        ", full body visible, complete character from head to toe, "
        "no cropping, wide shot, entire figure in frame"
    )
    logger.info(f"Together AI: стиль={IMAGE_STYLE}, промпт={full_prompt[:100]}...")

    payload = {
        "model": "black-forest-labs/FLUX.1-schnell-Free",
        "prompt": full_prompt,
        "width": 768,
        "height": 1344,
        "steps": 4,
        "n": 1,
        "response_format": "b64_json",
    }

    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                "https://api.together.xyz/v1/images/generations",
                json=payload,
                headers=headers,
            )
        if resp.status_code == 200:
            data = resp.json()
            b64 = data["data"][0].get("b64_json")
            if b64:
                import base64
                logger.info("Together AI: успех!")
                return base64.b64decode(b64)
            url = data["data"][0].get("url")
            if url:
                return await _download_image(url)
        logger.error(f"Together AI error {resp.status_code}: {resp.text[:300]}")
        return None
    except Exception as e:
        logger.error(f"Together AI exception: {e}")
        return None


# ─────────────────────────────────────────────
# HUGGING FACE
# ─────────────────────────────────────────────

async def generate_hf_image(prompt: str) -> bytes | None:
    if not HF_TOKEN:
        logger.warning("HuggingFace: нет HF_TOKEN")
        return None

    STYLE_MODELS = {
        "pixar":      ["stablediffusionapi/disney-pixar-cartoon", "Yntec/BeauteouxMIX3", "stabilityai/stable-diffusion-xl-base-1.0"],
        "comic":      ["Yntec/Marvel-Diffusion", "ogkalu/comic-diffusion", "stabilityai/stable-diffusion-xl-base-1.0"],
        "anime":      ["Linaqruf/anything-v3.0", "hakurei/waifu-diffusion", "stabilityai/stable-diffusion-xl-base-1.0"],
        "cinematic":  ["black-forest-labs/FLUX.1-dev", "black-forest-labs/FLUX.1-schnell", "stabilityai/stable-diffusion-3.5-large"],
        "watercolor": ["Yntec/Colorful2", "stabilityai/stable-diffusion-xl-base-1.0", "black-forest-labs/FLUX.1-schnell"],
    }
    models = STYLE_MODELS.get(IMAGE_STYLE, STYLE_MODELS["cinematic"])

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }

    STYLE_PRESETS = {
        "cinematic": {"suffix": ", sharp focus, highly detailed face, photorealistic, dramatic cinematic lighting, 8k, film poster", "negative": "blurry, deformed, ugly, bad anatomy, low quality, watermark, text", "guidance": 7.5, "steps": 30},
        "pixar": {"suffix": ", disney pixar style, 3d cartoon, cute expressive face, full body, vibrant colors, studio lighting, animated movie", "negative": "realistic, photo, blurry, deformed, ugly, low quality, watermark, text", "guidance": 7.5, "steps": 30},
        "comic": {"suffix": ", marvel comics style, comic book art, bold ink outlines, full body, vivid colors, superhero poster, dynamic pose", "negative": "photo, realistic, blurry, deformed, ugly, low quality, watermark, text", "guidance": 8.0, "steps": 30},
        "anime": {"suffix": ", anime style, full body character, detailed anime face, large eyes, cel shading, vibrant colors, manga illustration", "negative": "realistic, photo, blurry, deformed, ugly, low quality, watermark, text", "guidance": 7.5, "steps": 30},
        "watercolor": {"suffix": ", watercolor painting, full body, soft brushstrokes, artistic illustration, warm colors, painterly", "negative": "photo, realistic, blurry, deformed, ugly, low quality, watermark, text", "guidance": 7.0, "steps": 30},
    }

    style = STYLE_PRESETS.get(IMAGE_STYLE, STYLE_PRESETS["pixar"])
    enhanced_prompt = prompt + style["suffix"]

    for model in models:
        if "flux" in model.lower():
            payload = {"inputs": enhanced_prompt, "parameters": {"guidance_scale": style["guidance"], "num_inference_steps": style["steps"], "width": 768, "height": 1024}}
        else:
            payload = {"inputs": enhanced_prompt, "parameters": {"guidance_scale": style["guidance"], "num_inference_steps": style["steps"], "width": 768, "height": 1024, "negative_prompt": style["negative"]}}

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"https://api-inference.huggingface.co/models/{model}", json=payload, headers=headers)

            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "image" in content_type or len(resp.content) > 10000:
                    return resp.content

            if resp.status_code == 503:
                wait_time = resp.json().get("estimated_time", 20)
                await asyncio.sleep(min(wait_time, 30))
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(f"https://api-inference.huggingface.co/models/{model}", json=payload, headers=headers)
                if resp.status_code == 200:
                    return resp.content

        except Exception as e:
            logger.error(f"HuggingFace exception ({model}): {e}")
            continue

    return None


# ─────────────────────────────────────────────
# REPLICATE FLUX.1
# ─────────────────────────────────────────────

async def generate_replicate_flux(prompt: str) -> bytes | None:
    if not REPLICATE_API_KEY:
        logger.warning("Replicate: нет REPLICATE_API_KEY")
        return None

    headers = {
        "Authorization": f"Bearer {REPLICATE_API_KEY}",
        "Content-Type": "application/json",
        "Prefer": "wait=60",
    }
    payload = {
        "input": {
            "prompt": prompt,
            "aspect_ratio": "2:3",
            "output_format": "jpg",
            "output_quality": 90,
            "num_inference_steps": 28,
            "guidance": 3.5,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                "https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro/predictions",
                json=payload,
                headers=headers,
            )

        if resp.status_code not in (200, 201):
            logger.error(f"Replicate submit error {resp.status_code}: {resp.text[:300]}")
            return None

        data = resp.json()
        output = data.get("output")
        if output:
            image_url = output if isinstance(output, str) else output[0]
            return await _download_image(image_url)

        prediction_id = data.get("id")
        if not prediction_id:
            return None

        for attempt in range(30):
            await asyncio.sleep(3)
            async with httpx.AsyncClient(timeout=30.0) as client:
                poll = await client.get(
                    f"https://api.replicate.com/v1/predictions/{prediction_id}",
                    headers={"Authorization": f"Bearer {REPLICATE_API_KEY}"},
                )
            poll_data = poll.json()
            status = poll_data.get("status")
            if status == "succeeded":
                output = poll_data.get("output")
                image_url = output if isinstance(output, str) else output[0]
                return await _download_image(image_url)
            elif status in ("failed", "canceled"):
                return None

        return None

    except Exception as e:
        logger.error(f"Replicate exception: {e}")
        return None


async def _download_image(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            return resp.content
        return None
    except Exception as e:
        logger.error(f"_download_image exception: {e}")
        return None


# ─────────────────────────────────────────────
# YANDEX ART
# ─────────────────────────────────────────────

async def generate_yandex_art(prompt: str) -> bytes | None:
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        logger.warning("YandexART: нет YANDEX_API_KEY или YANDEX_FOLDER_ID")
        return None

    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": f"art://{YANDEX_FOLDER_ID}/yandex-art/latest",
        "generationOptions": {"seed": random.randint(1, 9999999), "aspectRatio": {"widthRatio": 2, "heightRatio": 3}},
        "messages": [{"weight": 1, "text": prompt}],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync",
                json=payload, headers=headers,
            )
        if resp.status_code != 200:
            logger.error(f"YandexART submit error {resp.status_code}: {resp.text[:200]}")
            return None

        operation_id = resp.json().get("id")
        if not operation_id:
            return None

        for attempt in range(20):
            await asyncio.sleep(3)
            async with httpx.AsyncClient(timeout=15.0) as client:
                poll = await client.get(
                    f"https://llm.api.cloud.yandex.net/operations/{operation_id}",
                    headers=headers,
                )
            data = poll.json()
            if data.get("done"):
                b64 = data.get("response", {}).get("image", "")
                if b64:
                    import base64
                    return base64.b64decode(b64)
                return None

        return None

    except Exception as e:
        logger.error(f"YandexART exception: {e}")
        return None


async def generate_image(prompt: str) -> bytes | None:
    """Together AI → HuggingFace → Replicate → YandexART"""
    if TOGETHER_API_KEY:
        result = await generate_together_image(prompt)
        if result:
            return result
        logger.warning("Together AI не ответил, переключаюсь на HuggingFace...")
    if HF_TOKEN:
        result = await generate_hf_image(prompt)
        if result:
            return result
        logger.warning("HuggingFace не ответил, переключаюсь на Replicate...")
    if REPLICATE_API_KEY:
        result = await generate_replicate_flux(prompt)
        if result:
            return result
        logger.warning("Replicate не ответил, переключаюсь на YandexART...")
    return await generate_yandex_art(prompt)


# ─────────────────────────────────────────────
# TMDB API
# ─────────────────────────────────────────────

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG  = "https://image.tmdb.org/t/p/w500"

_used_tmdb_ids: set = set()


async def fetch_tmdb(endpoint: str, params: dict) -> dict:
    if not TMDB_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{TMDB_BASE}{endpoint}",
                params={"api_key": TMDB_API_KEY, "language": "ru-RU", **params},
            )
        if resp.status_code != 200:
            return {}
        return resp.json()
    except Exception as e:
        logger.error(f"TMDB exception: {e}")
        return {}


async def fetch_tmdb_movies(genre_id: int = None, year_from: int = 2024) -> list:
    params = {
        "sort_by": "popularity.desc",
        "vote_count.gte": 50,
        "primary_release_date.gte": f"{year_from}-01-01",
        "with_original_language": "en|ru",
    }
    if genre_id:
        params["with_genres"] = genre_id
    data = await fetch_tmdb("/discover/movie", params)
    return data.get("results", [])


async def fetch_tmdb_series(genre_id: int = None, year_from: int = 2024) -> list:
    params = {
        "sort_by": "popularity.desc",
        "vote_count.gte": 30,
        "first_air_date.gte": f"{year_from}-01-01",
    }
    if genre_id:
        params["with_genres"] = genre_id
    data = await fetch_tmdb("/discover/tv", params)
    return data.get("results", [])


def _pick_tmdb(items: list) -> dict:
    random.shuffle(items)
    for item in items:
        if item.get("id") not in _used_tmdb_ids:
            return item
    _used_tmdb_ids.clear()
    return items[0] if items else {}


def _build_tmdb_movie_post(movie: dict, emoji: str, hashtags: str) -> tuple[str, str]:
    title    = movie.get("title") or movie.get("name") or "—"
    orig     = movie.get("original_title") or movie.get("original_name") or ""
    year     = (movie.get("release_date") or movie.get("first_air_date") or "")[:4]
    overview = (movie.get("overview") or "")[:300]
    rating   = movie.get("vote_average", 0)
    poster   = f"{TMDB_IMG}{movie['poster_path']}" if movie.get("poster_path") else ""

    lines = [f"{emoji} *{title}*"]
    if orig and orig != title:
        lines[0] += f" / _{orig}_"
    if year:
        lines[0] += f" ({year})"
    if rating:
        lines.append(f"⭐ Рейтинг: {rating:.1f}/10")
    if overview:
        lines.append(f"\n{overview}")
    lines.append(f"\n{hashtags}")

    return "\n".join(lines), poster


async def generate_tmdb_film_post() -> tuple[str, str]:
    movies = await fetch_tmdb_movies(year_from=2024)
    movies = [m for m in movies if 16 not in (m.get("genre_ids") or [])]
    if not movies:
        movies = await fetch_tmdb_movies(year_from=2023)
        movies = [m for m in movies if 16 not in (m.get("genre_ids") or [])]
    movie = _pick_tmdb(movies)
    if not movie:
        return await _generate_gpt_film_post(), ""
    _used_tmdb_ids.add(movie.get("id"))
    return _build_tmdb_movie_post(movie, "🎬", "#кино #новинка #фильм #кислородпродакшен")


async def generate_tmdb_series_post() -> tuple[str, str]:
    series = await fetch_tmdb_series(year_from=2024)
    if not series:
        series = await fetch_tmdb_series(year_from=2023)
    item = _pick_tmdb(series)
    if not item:
        return await _generate_gpt_series_post(), ""
    _used_tmdb_ids.add(item.get("id"))
    return _build_tmdb_movie_post(item, "📺", "#сериал #новинка #стриминг #кислородпродакшен")


async def generate_tmdb_cartoon_post() -> tuple[str, str]:
    movies = await fetch_tmdb_movies(genre_id=16, year_from=2023)
    if not movies:
        movies = await fetch_tmdb_movies(genre_id=16, year_from=2020)
    movie = _pick_tmdb(movies)
    if not movie:
        return await _generate_gpt_cartoon_post(), ""
    _used_tmdb_ids.add(movie.get("id"))
    return _build_tmdb_movie_post(movie, "🎨", "#мультфильм #анимация #кислородпродакшен")


async def generate_tmdb_premiere_post() -> tuple[str, str]:
    from datetime import date
    this_year = date.today().year
    movies = await fetch_tmdb_movies(year_from=this_year)
    if not movies:
        movies = await fetch_tmdb_series(year_from=this_year)
    item = _pick_tmdb(movies)
    if not item:
        return await _generate_gpt_film_post(), ""
    _used_tmdb_ids.add(item.get("id"))
    return _build_tmdb_movie_post(item, "🔥", "#премьера #новинка #кино #кислородпродакшен")


# ─────────────────────────────────────────────
# GPT-FALLBACK ПОСТЫ
# ─────────────────────────────────────────────

async def _generate_gpt_film_post() -> str:
    system = "Ты — редактор Telegram-канала о кино. Отвечай ТОЛЬКО текстом поста — без пояснений."
    user_msg = "Напиши пост о популярном фильме последних лет для Telegram-канала. 150–250 слов, 1–2 эмодзи. Хэштеги: #кино #новинка #фильм #кислородпродакшен"
    return await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])


async def _generate_gpt_series_post() -> str:
    system = "Ты — редактор Telegram-канала о кино. Отвечай ТОЛЬКО текстом поста — без пояснений."
    user_msg = "Напиши пост о популярном сериале последних лет для Telegram-канала. 150–250 слов, 1–2 эмодзи. Хэштеги: #сериал #новинка #стриминг #кислородпродакшен"
    return await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])


async def _generate_gpt_cartoon_post() -> str:
    system = "Ты — редактор Telegram-канала о кино. Отвечай ТОЛЬКО текстом поста — без пояснений."
    user_msg = "Напиши пост об интересном мультфильме или анимации последних лет для Telegram-канала. 150–250 слов, 1–2 эмодзи. Хэштеги: #мультфильм #анимация #кислородпродакшен"
    return await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])


# ─────────────────────────────────────────────
# NEWSAPI ПОСТЫ
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
            "Напиши один пост. 150–250 слов, живой стиль, 1–2 эмодзи. "
            "Хэштеги: #кино #кислородпродакшен #продакшен"
        )
    else:
        # Fallback на kinoafisha если NewsAPI недоступен
        result = await generate_kinoafisha_news_post()
        if result[0]:
            return result
        system = "Ты — редактор Telegram-канала КИСЛОРОД ПРОДАКШЕН. Отвечай ТОЛЬКО текстом поста."
        user_msg = "Напиши пост о трендах в кино и продакшене. 150–250 слов, 1–2 эмодзи, хэштеги: #кино #кислородпродакшен #продакшен"

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
        user_msg = "Напиши личный пост об актёрском пути. 120–200 слов, от первого лица, 1–2 эмодзи. Хэштеги: #актёр #кино #александрпотапов"

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
# ОТПРАВКА ПОСТА
# ─────────────────────────────────────────────

async def send_post(bot, channel: str, text: str, image_url: str = "", parse_mode: str = ""):
    if not text or text.startswith("Ошибка") or text.startswith("⚠️"):
        logger.error(f"Некорректный текст поста: {text[:80]}")
        return
    try:
        if image_url:
            try:
                await bot.send_photo(
                    chat_id=channel,
                    photo=image_url,
                    caption=text[:1024],  # Telegram лимит caption
                    parse_mode=parse_mode or None,
                )
                logger.info(f"✅ Фото+текст → {channel}")
                _stats["posts_sent"] += 1
                return
            except Exception as e:
                logger.warning(f"Фото не отправилось ({e}), отправляю текст")
        await bot.send_message(
            chat_id=channel,
            text=text,
            parse_mode=parse_mode or None,
        )
        logger.info(f"✅ Текст → {channel}")
        _stats["posts_sent"] += 1
    except Exception as e:
        logger.error(f"Ошибка отправки в {channel}: {e}")


# ─────────────────────────────────────────────
# JOB FUNCTIONS — РАСПИСАНИЕ
# UTC = МСК − 3
#
# @realtimeproductionn:
#   07:00 UTC / 10:00 МСК — новости кино (NewsAPI + Kinoafisha fallback)
#   08:30 UTC / 11:30 МСК — новинка ФИЛЬМ (Kinoafisha → TMDB → Streaming)
#   10:00 UTC / 13:00 МСК — новинка СЕРИАЛ → оба канала
#   12:00 UTC / 15:00 МСК — МУЛЬТФИЛЬМ (Kinoafisha → TMDB → Streaming)
#   14:00 UTC / 17:00 МСК — ПРЕМЬЕРА (Kinoafisha → TMDB → Streaming)
#   16:00 UTC / 19:00 МСК — вечерний дайджест
#
# @actorsashapotapovv:
#   08:00 UTC / 11:00 МСК — утренний пост
#   10:00 UTC / 13:00 МСК — сериал (вместе с КИСЛОРОД)
#   11:00 UTC / 14:00 МСК — из фильмографии
#   15:30 UTC / 18:30 МСК — новинка ФИЛЬМ
#   17:00 UTC / 20:00 МСК — вечерний пост
# ─────────────────────────────────────────────

async def job_kislorod_morning(context):
    text, img = await generate_kislorod_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text, img)


async def job_kislorod_film(context):
    text, img = await generate_streaming_film_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img, parse_mode="Markdown")
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)


async def job_both_series(context):
    text, img = await generate_streaming_series_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img, parse_mode="Markdown")
        await send_post(context.bot, CHANNEL_ACTOR, text, img, parse_mode="Markdown")
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)
        text3, img3 = await generate_actor_post()
        await send_post(context.bot, CHANNEL_ACTOR, text3, img3)


async def job_kislorod_cartoon(context):
    text, img = await generate_streaming_cartoon_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img, parse_mode="Markdown")
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)


async def job_kislorod_premiere(context):
    text, img = await generate_streaming_premiere_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img, parse_mode="Markdown")
    else:
        text2, img2 = await generate_kislorod_post()
        await send_post(context.bot, CHANNEL_KISLOROD, text2, img2)


async def job_kislorod_evening(context):
    text, img = await generate_kislorod_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text, img)


async def job_actor_morning(context):
    text, img = await generate_actor_post()
    await send_post(context.bot, CHANNEL_ACTOR, text, img)


async def job_actor_filmography(context):
    text, img = await generate_filmography_post()
    if text:
        await send_post(context.bot, CHANNEL_ACTOR, text, img)
    else:
        text2, img2 = await generate_actor_post()
        await send_post(context.bot, CHANNEL_ACTOR, text2, img2)


async def job_actor_film(context):
    text, img = await generate_streaming_film_post()
    if text:
        await send_post(context.bot, CHANNEL_ACTOR, text, img, parse_mode="Markdown")
    else:
        text2, img2 = await generate_actor_post()
        await send_post(context.bot, CHANNEL_ACTOR, text2, img2)


async def job_actor_evening(context):
    text, img = await generate_actor_post()
    await send_post(context.bot, CHANNEL_ACTOR, text, img)


# ─────────────────────────────────────────────
# ЦИТАТА ДНЯ
# ─────────────────────────────────────────────

async def generate_quote_post() -> str:
    system = "Ты — редактор вдохновляющего Telegram-канала о кино. Отвечай ТОЛЬКО текстом поста."
    user_msg = (
        "Напиши вдохновляющий пост с цитатой великого режиссёра, сценариста или актёра. "
        "Формат:\n🎬 Цитата дня\n\n«[цитата]»\n\n— [Имя автора], [профессия]\n\n"
        "[2-3 предложения почему эта цитата важна]\n\n#цитатадня #кино #кислородпродакшен"
    )
    return await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])


# ─────────────────────────────────────────────
# КИНО-ФАКТ
# ─────────────────────────────────────────────

async def generate_kinofact_post() -> str:
    system = "Ты — редактор познавательного Telegram-канала о кино. Отвечай ТОЛЬКО текстом поста."
    user_msg = (
        "Напиши интересный пост с малоизвестным фактом о съёмках знаменитого фильма. "
        "Формат:\n🎥 Кино-факт\n\n[интересный факт, 100-150 слов]\n\n#кинофакт #кино #кислородпродакшен"
    )
    return await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])


# ─────────────────────────────────────────────
# ОПРОС НЕДЕЛИ
# ─────────────────────────────────────────────

WEEKLY_POLLS = [
    ("🎬 Какой жанр кино вам нравится больше всего?",
     ["🎭 Драма", "😂 Комедия", "🔥 Боевик", "👻 Хоррор", "🚀 Фантастика", "❤️ Мелодрама"]),
    ("📺 Что вы предпочитаете смотреть?",
     ["🎬 Фильмы", "📺 Сериалы", "🎨 Мультфильмы", "📹 Документальное"]),
    ("🤖 Как вы относитесь к AI в кино?",
     ["🔥 Это будущее!", "🤔 Зависит от использования", "😟 Предпочитаю классику", "🎯 Главное — результат"]),
    ("🎭 Кто важнее в кино?",
     ["🎬 Режиссёр", "✍️ Сценарист", "🎭 Актёр", "💼 Продюсер"]),
    ("🌍 Какое кино вы смотрите чаще?",
     ["🇷🇺 Российское", "🇺🇸 Голливуд", "🌏 Азиатское", "🌍 Европейское"]),
]

_poll_index = 0


async def send_weekly_poll(bot, channel: str):
    global _poll_index
    question, options = WEEKLY_POLLS[_poll_index % len(WEEKLY_POLLS)]
    _poll_index += 1
    try:
        await bot.send_poll(
            chat_id=channel,
            question=question,
            options=options,
            is_anonymous=True,
        )
        logger.info(f"✅ Опрос → {channel}")
        _stats["posts_sent"] += 1
    except Exception as e:
        logger.error(f"Ошибка отправки опроса в {channel}: {e}")


# ─────────────────────────────────────────────
# ГЕНЕРАТОР ПОСТЕРА — /poster
# ─────────────────────────────────────────────

async def poster_command(update, context):
    _stats_inc_tool("poster")
    args = context.args
    if args:
        await _generate_poster(update, context, " ".join(args))
    else:
        context.user_data["awaiting"] = "poster"
        await update.message.reply_text(
            "🖼 Генератор постера\n\n"
            "Опиши свой проект — жанр, атмосферу, главного героя.\n\n"
            "_Например: Мрачный детектив, ночной город, дождь, одинокий следователь_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]),
        )


async def _generate_poster(update, context, description: str):
    import io
    chat_id = update.effective_chat.id
    msg = await context.bot.send_message(chat_id=chat_id, text="🖼 Генерирую постер (~30-60 сек)...")

    system = "Ты — арт-директор. Создай промпт для генерации постера фильма на английском языке."
    user_msg = f"Проект: {description}\n\nСоздай детальный промпт для постера: стиль, цвета, композиция, атмосфера. Только промпт, без пояснений. На английском."
    art_prompt = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    art_prompt = f"Movie poster, cinematic, professional: {art_prompt[:300]}"

    image_bytes = await generate_image(art_prompt)

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
    except Exception:
        pass

    # ✅ ИСПРАВЛЕНО: добавлена кнопка Сохранить для постера
    role_key = context.user_data.get("role", "general")
    short_title = description[:30]

    if image_bytes:
        bio = io.BytesIO(image_bytes)
        bio.name = "poster.jpg"
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=bio,
            caption=f"🖼 Постер для: _{description[:60]}_\n\n✨ Студия КИСЛОРОД ПРОДАКШЕН",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                make_save_row("chat", short_title),
                [InlineKeyboardButton("🔄 Новый постер", callback_data="tool_poster")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back_to_hints")],
            ]),
        )
        # Сохраняем описание в историю чтобы кнопка Сохранить нашла контент
        history = context.user_data.get("history", [])
        history.append({"role": "assistant", "text": f"🖼 Постер: {description}"})
        context.user_data["history"] = history[-30:]
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Не удалось сгенерировать постер. Попробуй ещё раз или переформулируй описание.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Попробовать снова", callback_data="tool_poster")]]),
        )


# ─────────────────────────────────────────────
# РАЗБОР СЦЕНАРИЯ — /analyze
# ─────────────────────────────────────────────

async def analyze_command(update, context):
    _stats_inc_tool("analyze")
    context.user_data["awaiting"] = "analyze"
    await update.message.reply_text(
        "📄 Разбор сценария\n\n"
        "Отправь текст своей сцены или фрагмента сценария — я дам профессиональный разбор.\n\n"
        "_Структура, персонажи, диалоги, подтекст, что улучшить_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]),
    )


async def _generate_analysis(update, context, script_text: str):
    chat_id = update.effective_chat.id
    progress_id = await send_progress(context.bot, chat_id, "📄 Анализирую сценарий...")

    system = (
        "Ты — профессиональный сценарный редактор студии КИСЛОРОД ПРОДАКШЕН. "
        "Даёшь детальный разбор сценариев. Отвечай ТОЛЬКО разбором — без предисловий."
    )
    user_msg = (
        f"Сделай профессиональный разбор этого фрагмента:\n\n{script_text[:2000]}\n\n"
        "📖 СТРУКТУРА\n🎭 ПЕРСОНАЖИ\n💬 ДИАЛОГИ\n🎬 ВИЗУАЛЬНОСТЬ\n"
        "⚡ ЧТО РАБОТАЕТ\n🔧 ЧТО УЛУЧШИТЬ\n⭐ ОЦЕНКА /10"
    )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))
    try:
        response = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    finally:
        stop_typing.set(); typing_task.cancel()
        try: await typing_task
        except asyncio.CancelledError: pass

    await delete_progress(context.bot, chat_id, progress_id)

    history = context.user_data.get("history", [])
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]

    short_title = script_text[:30]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📄 Разбор сценария\n\n{response}",
        reply_markup=InlineKeyboardMarkup([
            make_save_row("scene", short_title),
            [InlineKeyboardButton("📄 Разобрать ещё", callback_data="tool_analyze")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_hints")],
        ]),
    )


# ─────────────────────────────────────────────
# AI-ПИТЧИНГ — /pitch
# ─────────────────────────────────────────────

async def pitch_command(update, context):
    _stats_inc_tool("pitch")
    context.user_data["awaiting"] = "pitch"
    await update.message.reply_text(
        "🎯 AI-Питчинг\n\n"
        "Опиши свою идею проекта в 1-3 предложениях — я создам полноценный питч-документ.\n\n"
        "_Например: Сериал о молодом хакере в Москве 90-х, который случайно взламывает сервер ФСБ_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]),
    )


async def _generate_pitch(update, context, idea: str):
    chat_id = update.effective_chat.id
    progress_id = await send_progress(context.bot, chat_id, "🎯 Создаю питч-документ...")

    system = (
        "Ты — опытный продюсер студии КИСЛОРОД ПРОДАКШЕН. "
        "Создаёшь профессиональные питч-документы. Отвечай ТОЛЬКО питчем — без предисловий."
    )
    user_msg = (
        f"Создай питч-документ:\n\n{idea}\n\n"
        "🎬 НАЗВАНИЕ\n📖 СИНОПСИС\n🎭 ГЛАВНЫЕ ГЕРОИ\n"
        "🎯 ЦЕЛЕВАЯ АУДИТОРИЯ\n🌍 РЫНОК\n💰 ФОРМАТ И БЮДЖЕТ\n"
        "⚡ ПОЧЕМУ СЕЙЧАС\n✨ УНИКАЛЬНОСТЬ"
    )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))
    try:
        response = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    finally:
        stop_typing.set(); typing_task.cancel()
        try: await typing_task
        except asyncio.CancelledError: pass

    await delete_progress(context.bot, chat_id, progress_id)

    history = context.user_data.get("history", [])
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]

    short_title = idea[:30]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🎯 Питч-документ\n\n{response}",
        reply_markup=InlineKeyboardMarkup([
            make_save_row("producer", short_title),
            [InlineKeyboardButton("🎯 Новый питч", callback_data="tool_pitch")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_hints")],
        ]),
    )


async def job_quote_day(context):
    text = await generate_quote_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text)
    await send_post(context.bot, CHANNEL_ACTOR, text)


async def job_kinofact(context):
    text = await generate_kinofact_post()
    await send_post(context.bot, CHANNEL_KISLOROD, text)
    await send_post(context.bot, CHANNEL_ACTOR, text)


async def job_weekly_poll(context):
    await send_weekly_poll(context.bot, CHANNEL_KISLOROD)
    await send_weekly_poll(context.bot, CHANNEL_ACTOR)


# ─────────────────────────────────────────────
# ПОСТЕРЫ В КАНАЛЫ
# ─────────────────────────────────────────────

POSTER_THEMES = [
    ("Таинственный детектив в ночном городе, неон, дождь, одинокий следователь", "🔍 Детектив"),
    ("Эпическая космическая опера, звёздные корабли, далёкие галактики", "🚀 Sci-Fi"),
    ("Мрачная сказка, тёмный лес, волшебный замок, таинственная героиня", "🧙 Фэнтези"),
    ("Советский ретро-триллер, 1970-е, Москва, шпионы и секреты", "🕵️ Ретро"),
    ("Постапокалиптический мир, выжженная пустыня, последний герой", "💀 Постапок"),
    ("Романтическая драма, Париж, закат, двое на мосту", "❤️ Драма"),
    ("Боевик в стиле нуар, чёрно-белое, джаз, преступный мир", "🎷 Нуар"),
    ("Анимационный мультфильм, яркие краски, волшебные существа, дети-герои", "🎨 Анимация"),
    ("Хоррор, старый особняк, туман, призраки, полночь", "👻 Хоррор"),
    ("Историческая эпопея, Древняя Русь, богатыри, битва", "⚔️ Эпик"),
    ("Молодёжная комедия, студенческий кампус, яркое лето, дружба", "😂 Комедия"),
    ("Документальный стиль, дикая природа, Сибирь, экспедиция", "🌿 Доку"),
]

_poster_theme_index = 0

FUNNY_FILM_IDEAS = [
    ("Титаник", "«Доска на двоих»", "Роза подвинулась. Джек выжил. Фильм закончился на 40-й минуте.", "Romantic movie poster parody: a giant wooden door floating in icy ocean, two people comfortably lying on it with blankets and mugs of tea, smiling. Classic Titanic ship in background. Absurd comedy style, cinematic lighting, film poster composition."),
    ("Терминатор", "«Терминатор: Техподдержка»", "Он прилетел из будущего. Но не убивать — а починить Wi-Fi. Роутер оказался сложнее Сары Коннор.", "Funny movie poster parody: muscular cyborg Terminator in sunglasses sitting at a help desk, holding a router, talking on phone with frustrated expression, office background with sticky notes. Comedy movie poster style, dramatic lighting."),
    ("Король Лев", "«Симба: Стартап»", "Симба не вернулся мстить. Он открыл IT-стартап в Найроби. Шрам стал его инвестором.", "Funny animated movie poster parody: lion cub in business suit at a laptop in a savanna office, PowerPoint presentation on a rock screen, hyenas in HR badges nearby. Comedy Pixar-style poster, bright colors, cinematic."),
    ("Властелин колец", "«Одно кольцо: Утеряно»", "Гэндальф просто написал объявление на доску в таверне. Нашли за три дня. Квест отменён.", "Funny fantasy movie poster parody: wizard pinning a Lost Ring flyer on a medieval tavern bulletin board. Dramatic lighting, epic landscape in background, comedy style, cinematic film poster composition."),
    ("Матрица", "«Нео берёт синюю»", "Нео выбрал синюю таблетку. Проснулся. Выпил кофе. Пошёл на работу. Конец.", "Funny sci-fi movie poster parody: office worker in suit choosing between red and blue pill, picks blue, background shows boring office cubicles instead of matrix code. Deadpan comedy style, film poster composition."),
    ("Звёздные войны", "«Папа с проблемами»", "Дарт Вейдер просто хотел сказать Люку что он его папа. Но дозвониться не мог — сигнал в космосе плохой.", "Funny Star Wars parody movie poster: Darth Vader holding a phone with No Signal on screen, frustrated expression under the helmet. Death Star in background. Comedy style, cinematic epic lighting, film poster."),
    ("Один дома", "«Кевин звонит 112»", "8-летний Кевин нашёл телефон и позвонил в полицию. Грабители арестованы через 12 минут. Хронометраж фильма: 14 минут.", "Funny Christmas movie poster parody: smart kid on phone calling police, two bumbling robbers already in handcuffs visible through window, Christmas decorations everywhere. Comedy style, warm holiday lighting, film poster."),
    ("Назад в будущее", "«Марти инвестирует»", "Марти вернулся в 1955 и вложил 100 долларов в акции будущих компаний. В 1985 году он оказался богаче Биффа.", "Funny sci-fi movie poster parody: teenager in time-traveling DeLorean reading a stock market newspaper with huge grin, dollar signs flying around. Comedy style, 80s retro film poster, cinematic lighting."),
    ("Гарри Поттер", "«Гермиона решает всё»", "Гермиона прочитала все книги в библиотеке Хогвартса ещё в сентябре. Волдеморт побеждён к Рождеству.", "Funny magic school movie poster parody: clever girl with huge stack of books, wand in one hand, checklist in other, defeated villain small in background. Comedy Harry Potter parody style, magical lighting, film poster."),
    ("Интерстеллар", "«Купер выходит через другую дверь»", "Купер искал спасение среди звёзд. А потом заметил запасный выход прямо за фермой. Всё было нормально.", "Funny sci-fi movie poster parody: astronaut in spacesuit finding a mundane Emergency Exit door in the middle of a cornfield in space, pointing at it with relief. Comedy style, dramatic space lighting, cinematic film poster."),
    ("Джурасик Парк", "«Динозавры в IKEA»", "Динозавры сбежали с острова и забрели в торговый центр. В зоне самовывоза IKEA их поймали — они не смогли найти выход.", "Funny movie poster parody: T-Rex and raptors confused inside IKEA store, carrying flat-pack boxes, staff hiding behind displays. Comedy style, bright commercial lighting, absurd humor, film poster composition."),
    ("Аватар", "«Синяя краска»", "Джейк Салли потратил 20 долларов на синюю краску в строительном магазине. Стал своим среди На'ви на второй день.", "Funny sci-fi movie poster parody: human man painted bright blue with a paint roller still in hand, standing proudly among tall blue aliens who look confused. Comedy style, lush jungle background, cinematic lighting."),
]

_funny_poster_index = 0


async def generate_funny_film_poster_idea() -> tuple[str, str, str]:
    global _funny_poster_index
    item = FUNNY_FILM_IDEAS[_funny_poster_index % len(FUNNY_FILM_IDEAS)]
    _funny_poster_index += 1
    film_title, funny_title, concept, art_prompt_base = item
    art_prompt = art_prompt_base + " High quality, award-winning cinematography, dramatic poster lighting."
    return film_title, f"{funny_title}\n\n{concept}", art_prompt


async def generate_funny_poster_caption(film_title: str, concept: str) -> str:
    system = (
        "Ты — остроумный сценарист Telegram-канала о кино с юмором стендап-комика. "
        "Пишешь короткие, едкие, смешные посты. Юмор абсурдный, ироничный. "
        "Отвечай ТОЛЬКО текстом поста, без пояснений."
    )
    user_msg = (
        f"Напиши смешной пост для пародийного постера «{film_title}».\n\n"
        f"Концепция: {concept}\n\n"
        "— Начни с 🎬 и смешного названия версии фильма\n"
        "— 3-4 предложения абсурдного сюжета с конкретными деталями\n"
        "— Добавь неожиданную деталь которой нет в концепции\n"
        "— Финальный вопрос к подписчикам\n"
        "— Хэштеги: #пародия #кино #еслибы #кислородпродакшен"
    )
    return await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])


def compress_image(image_bytes: bytes, max_size_kb: int = 400) -> bytes:
    try:
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(image_bytes))
        if max(img.size) > 1280:
            img.thumbnail((1280, 1280), Image.LANCZOS)
        for q in [85, 75, 60, 45]:
            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=q, optimize=True)
            if buf.tell() <= max_size_kb * 1024:
                buf.seek(0)
                return buf.read()
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.warning(f"compress_image error: {e}")
        return image_bytes


async def send_photo_safe(bot, channel: str, image_bytes: bytes, caption: str) -> bool:
    import io
    compressed = compress_image(image_bytes)
    logger.info(f"Фото {len(compressed)//1024} КБ → {channel}")
    bio = io.BytesIO(compressed)
    bio.name = "poster.jpg"
    try:
        await bot.send_photo(
            chat_id=channel,
            photo=bio,
            caption=caption[:1024],  # Telegram лимит
            read_timeout=60,
            write_timeout=60,
            connect_timeout=30,
        )
        return True
    except Exception as e:
        logger.error(f"send_photo_safe error {channel}: {e}")
        return False


# ✅ ИСПРАВЛЕНО: job_funny_poster и job_quote_day разведены по времени (не совпадают)
async def job_funny_poster(context):
    """Смешной постер — 12:00 МСК"""
    logger.info("Генерирую смешной постер к фильму...")
    film_title, concept, art_prompt = await generate_funny_film_poster_idea()
    image_bytes = await generate_image(art_prompt)
    caption = await generate_funny_poster_caption(film_title, concept)

    for channel in [CHANNEL_KISLOROD, CHANNEL_ACTOR]:
        if image_bytes:
            ok = await send_photo_safe(context.bot, channel, image_bytes, caption)
            if ok:
                _stats["posts_sent"] += 1
                continue
        try:
            await context.bot.send_message(chat_id=channel, text=caption)
            _stats["posts_sent"] += 1
        except Exception as e:
            logger.error(f"funny_poster error {channel}: {e}")


async def job_channel_poster(context):
    """Тематический постер — 20:30 МСК"""
    import io
    global _poster_theme_index
    theme_prompt, theme_label = POSTER_THEMES[_poster_theme_index % len(POSTER_THEMES)]
    _poster_theme_index += 1

    art_prompt = (
        f"Movie poster, cinematic, professional, high quality, dramatic lighting: {theme_prompt}. "
        "Film poster style, bold typography space, atmospheric, award-winning cinematography"
    )
    image_bytes = await generate_image(art_prompt)

    if image_bytes:
        system = "Ты — редактор Telegram-канала о кино. Отвечай ТОЛЬКО текстом поста."
        user_msg = (
            f"Напиши короткий вдохновляющий пост для постера «{theme_label}». "
            "2-3 предложения, атмосферно, с эмодзи. "
            "Хэштеги: #кино #постер #кислородпродакшен"
        )
        caption = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])

        bio = io.BytesIO(image_bytes)
        bio.name = "poster.jpg"
        for channel in [CHANNEL_KISLOROD, CHANNEL_ACTOR]:
            try:
                bio.seek(0)
                await context.bot.send_photo(chat_id=channel, photo=bio, caption=caption[:1024])
                logger.info(f"✅ Постер → {channel}")
                _stats["posts_sent"] += 1
            except Exception as e:
                logger.error(f"Ошибка отправки постера в {channel}: {e}")
    else:
        logger.warning("job_channel_poster: генерация не дала результата")


# ─────────────────────────────────────────────
# /start — ОНБОРДИНГ
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    _stats["total_users"].add(user_id)

    existing_role = context.user_data.get("role")
    if existing_role and existing_role in ROLE_PROMPTS:
        role_label = {
            "actor": "🎭 Актёр", "director": "🎬 Режиссёр",
            "screenwriter": "✍️ Сценарист", "producer": "💼 Продюсер",
            "client": "🤝 Заказчик", "general": "🌐 Общий",
        }.get(existing_role, existing_role)
        await update.message.reply_text(
            f"⚡ Быстрый старт!\n\nТвоя роль: {role_label}\n\nПродолжаем с того места где остановились 👇",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Продолжить", callback_data="quickstart_continue")],
                [InlineKeyboardButton("🔄 Сменить роль", callback_data="quickstart_reset")],
            ]),
        )
        return

    context.user_data.clear()
    context.user_data["onboarding"] = True

    step = ONBOARDING_STEPS[0]
    await update.message.reply_text(step["text"], reply_markup=InlineKeyboardMarkup(step["buttons"]))
    await update.message.reply_text("Или нажми 📋 Меню в любой момент.", reply_markup=webapp_keyboard())


# ─────────────────────────────────────────────
# CALLBACK HANDLER
# ─────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

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
            await query.edit_message_text(ONBOARDING_STEP3_CHAT, reply_markup=hints_keyboard(role_key, context))
            return
        if action == "onboard_finish_tool":
            context.user_data.pop("onboarding", None)
            await query.edit_message_text(ONBOARDING_STEP3_TOOL, reply_markup=tools_keyboard(context))
            return

    if action == "quickstart_continue":
        role_key = context.user_data.get("role", "general")
        await query.edit_message_text(
            ROLE_PROMPTS[role_key]["welcome"], reply_markup=hints_keyboard(role_key, context)
        )
        return

    if action == "quickstart_reset":
        context.user_data.clear()
        step = ONBOARDING_STEPS[0]
        await query.edit_message_text(step["text"], reply_markup=InlineKeyboardMarkup(step["buttons"]))
        return

    if action == "show_tools":
        recent = context.user_data.get("recent_requests", [])
        recent_text = ""
        if recent:
            tool_labels = {"storyboard": "🎬", "character": "🎭", "scene": "📝", "monologue": "🎤", "rewrite": "🔁"}
            lines = [f"  {tool_labels.get(r['tool'], '•')} {r['description']}" for r in reversed(recent)]
            recent_text = "\n\n📜 Недавние запросы:\n" + "\n".join(lines)
        await query.edit_message_text(
            "🛠 Творческие инструменты студии КИСЛОРОД:\n\n"
            "🎬 Раскадровка — текстовая раскадровка сцены\n"
            "🎭 Персонаж — полная карточка героя\n"
            "📝 Сцена — сцена в сценарном формате\n"
            "🎤 Монолог — монолог с подтекстом для актёра\n"
            "🔁 Переписать — перенести текст в другой жанр\n"
            "💾 Сохранения — все твои работы по папкам" + recent_text,
            reply_markup=tools_keyboard(context),
        )
        return

    if action == "show_recent":
        recent = context.user_data.get("recent_requests", [])
        if not recent:
            await query.answer("История пуста", show_alert=False)
            return
        tool_labels = {"storyboard": "🎬 Раскадровка", "character": "🎭 Персонаж", "scene": "📝 Сцена", "monologue": "🎤 Монолог", "rewrite": "🔁 Перезапись"}
        lines = ["📜 Последние 3 запроса:\n"]
        repeat_buttons = []
        for i, r in enumerate(reversed(recent), 1):
            label = tool_labels.get(r["tool"], r["tool"])
            lines.append(f"{i}. {label}: {r['description']}")
            repeat_buttons.append([InlineKeyboardButton(f"🔁 Повторить #{i}", callback_data=f"repeat|{r['tool']}|{r['description']}")])
        repeat_buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="show_tools")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(repeat_buttons))
        return

    if action.startswith("repeat|"):
        parts = action.split("|", 2)
        if len(parts) == 3:
            _, tool, desc = parts
            context.user_data["awaiting"] = tool
            await query.edit_message_text(
                f"🔁 Повторяем: _{desc}_\n\nОтправь описание (или нажми отмену):",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]),
            )
        return

    if action == "back_to_hints":
        role_key = context.user_data.get("role", "general")
        welcome = ROLE_PROMPTS.get(role_key, ROLE_PROMPTS["general"])["welcome"]
        await query.edit_message_text(welcome, reply_markup=hints_keyboard(role_key, context))
        return

    if action == "tool_storyboard":
        context.user_data["awaiting"] = "storyboard"
        await query.edit_message_text("🎬 Опиши сцену для раскадровки:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]))
        _stats_inc_tool("storyboard"); return

    if action == "tool_character":
        context.user_data["awaiting"] = "character"
        await query.edit_message_text("🎭 Опиши персонажа:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]))
        _stats_inc_tool("character"); return

    if action == "tool_scene":
        context.user_data["awaiting"] = "scene"
        await query.edit_message_text("📝 Опиши что должно произойти в сцене:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]))
        _stats_inc_tool("scene"); return

    if action == "tool_monologue":
        context.user_data["awaiting"] = "monologue"
        await query.edit_message_text("🎤 Опиши персонажа и его состояние:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]))
        _stats_inc_tool("monologue"); return

    if action == "tool_poster":
        context.user_data["awaiting"] = "poster"
        await query.edit_message_text("🖼 Опиши свой проект для постера:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]))
        _stats_inc_tool("poster"); return

    if action == "tool_analyze":
        context.user_data["awaiting"] = "analyze"
        await query.edit_message_text("📄 Отправь текст сценария для разбора:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]))
        _stats_inc_tool("analyze"); return

    if action == "tool_pitch":
        context.user_data["awaiting"] = "pitch"
        await query.edit_message_text("🎯 Опиши идею своего проекта:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]))
        _stats_inc_tool("pitch"); return

    if action == "tool_rewrite":
        context.user_data["awaiting"] = "rewrite"
        await query.edit_message_text("🔁 Отправь текст сцены или диалога для переписки:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]))
        _stats_inc_tool("rewrite"); return

    if action == "show_saves":
        saves = _get_saves(context)
        if not saves:
            await query.edit_message_text(
                "💾 У тебя пока нет сохранённых работ.\n\nПосле генерации нажми кнопку 💾 Сохранить.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_hints")]]),
            )
            return
        folder_counts = {}
        for s in saves:
            folder_counts[s["type"]] = folder_counts.get(s["type"], 0) + 1
        folder_buttons = []
        for ftype, flabel in SAVE_FOLDERS.items():
            cnt = folder_counts.get(ftype, 0)
            if cnt > 0:
                folder_buttons.append([InlineKeyboardButton(f"{flabel} ({cnt})", callback_data=f"folder|{ftype}")])
        folder_buttons.append([InlineKeyboardButton("📤 Экспорт всех в TXT", callback_data="export_saves")])
        folder_buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_hints")])
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ К папкам", callback_data="show_saves")]]),
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
            count = _saves_count(context)
            await query.answer(
                f"✅ Сохранено в {label}!\n«{title[:40]}»\nВсего сохранений: {count}",
                show_alert=True,
            )
        return

    if action == "change_role":
        context.user_data.clear()
        await query.edit_message_text("🎬 Нажми кнопку 📋 Меню внизу, чтобы выбрать роль.", reply_markup=None)
        return

    if action == "cancel_awaiting":
        context.user_data.pop("awaiting", None)
        context.user_data.pop("view_save_folder", None)  # ✅ ИСПРАВЛЕНО: чистим и folder тоже
        await query.edit_message_text("❌ Отменено.")
        return

    if action == "new_storyboard":
        context.user_data["awaiting"] = "storyboard"
        await query.edit_message_text("🎬 Опиши новую сцену для раскадровки:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]])); return

    if action == "new_character":
        context.user_data["awaiting"] = "character"
        await query.edit_message_text("🎭 Опиши нового персонажа:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]])); return

    if action == "new_scene":
        context.user_data["awaiting"] = "scene"
        await query.edit_message_text("📝 Опиши новую сцену:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]])); return

    if action == "new_monologue":
        context.user_data["awaiting"] = "monologue"
        await query.edit_message_text("🎤 Опиши персонажа для монолога:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]])); return

    if action == "new_rewrite":
        context.user_data["awaiting"] = "rewrite"
        await query.edit_message_text("🔁 Отправь текст для переписки:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]])); return

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
            ROLE_PROMPTS[role_key]["welcome"], reply_markup=hints_keyboard(role_key, context)
        )
        return

    if action in HINT_TEXTS:
        role_key = context.user_data.get("role", "general")
        hint_text = HINT_TEXTS[action]
        chat_id = query.message.chat_id

        await context.bot.send_message(chat_id=chat_id, text=f"_{hint_text}_", parse_mode="Markdown")

        history = context.user_data.get("history", [])
        stop_typing = asyncio.Event()
        typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))
        try:
            history.append({"role": "user", "text": hint_text})
            response = await ask_yandex_gpt(ROLE_PROMPTS[role_key]["system"], history)
        finally:
            stop_typing.set(); typing_task.cancel()
            try: await typing_task
            except asyncio.CancelledError: pass

        if not response or not response.strip():
            response = "Не смог сформулировать ответ. Попробуй переформулировать вопрос."

        history.append({"role": "assistant", "text": response})
        context.user_data["history"] = history[-30:]
        _stats["total_messages"] += 1

        await context.bot.send_message(
            chat_id=chat_id, text=response, reply_markup=hints_keyboard(role_key, context)
        )
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
        ROLE_PROMPTS[role_key]["welcome"], reply_markup=hints_keyboard(role_key)
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

    # ✅ ИСПРАВЛЕНО: безопасная обработка view_save с проверкой папки
    if awaiting == "view_save":
        context.user_data.pop("awaiting", None)
        folder_type = context.user_data.pop("view_save_folder", None)
        saves = _get_saves(context)
        display_saves = [s for s in saves if s["type"] == folder_type] if folder_type else saves
        if not display_saves:
            await update.message.reply_text("Сохранений нет. Воспользуйся меню 👇", reply_markup=webapp_keyboard())
            return
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
                await update.message.reply_text(f"Нет сохранения с номером {idx+1}. Введи число от 1 до {len(display_saves)}.")
        except ValueError:
            await update.message.reply_text("Отправь номер из списка, например: 1")
        return

    if awaiting == "storyboard":
        context.user_data.pop("awaiting", None)
        await _generate_storyboard(update, context, user_text); return
    if awaiting == "character":
        context.user_data.pop("awaiting", None)
        await _generate_character(update, context, user_text); return
    if awaiting == "scene":
        context.user_data.pop("awaiting", None)
        await _generate_scene(update, context, user_text); return
    if awaiting == "monologue":
        context.user_data.pop("awaiting", None)
        await _generate_monologue(update, context, user_text); return
    if awaiting == "poster":
        context.user_data.pop("awaiting", None)
        await _generate_poster(update, context, user_text); return
    if awaiting == "analyze":
        context.user_data.pop("awaiting", None)
        await _generate_analysis(update, context, user_text); return
    if awaiting == "pitch":
        context.user_data.pop("awaiting", None)
        await _generate_pitch(update, context, user_text); return
    if awaiting == "rewrite":
        context.user_data["rewrite_text"] = user_text
        context.user_data["awaiting"] = "rewrite_style"
        await update.message.reply_text(
            "🎨 В каком жанре/стиле переписать?\n_Например: нуар, комедия, хоррор, советское кино_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]),
        )
        return
    if awaiting == "rewrite_style":
        context.user_data.pop("awaiting", None)
        original_text = context.user_data.pop("rewrite_text", "")
        await _generate_rewrite(update, context, original_text, user_text); return

    role_key = context.user_data.get("role")
    if not role_key:
        role_key = "general"
        context.user_data["role"] = role_key
        context.user_data["history"] = []
        await update.message.reply_text(
            "🌐 Роль не выбрана — отвечаю как общий ассистент. Нажми 📋 Меню, чтобы выбрать роль.",
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
        stop_typing.set(); typing_task.cancel()
        try: await typing_task
        except asyncio.CancelledError: pass

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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]),
        )


async def _generate_storyboard(update: Update, context: ContextTypes.DEFAULT_TYPE, scene: str):
    chat_id = update.effective_chat.id
    _add_to_history(context, "storyboard", scene)
    progress_id = await send_progress(context.bot, chat_id, "🎬 Генерирую раскадровку...")

    system = "Ты — опытный режиссёр и раскадровщик. Создаёшь детальные текстовые раскадровки. Отвечай ТОЛЬКО раскадровкой — без предисловий."
    user_msg = (
        f"Создай текстовую раскадровку для сцены:\n\n{scene}\n\n"
        "Формат каждого кадра:\n"
        "━━━━━━━━━━━━━━━━\nКАДР [номер]\nРакурс: ...\nЛокация: ...\nДействие: ...\nСвет: ...\nЗвук: ...\nРеплика: ...\nДлительность: ...\n\n"
        "5–8 кадров. После:\nРЕЖИССЁРСКАЯ ЗАМЕТКА: [1–2 предложения об атмосфере]"
    )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))
    try:
        response = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    finally:
        stop_typing.set(); typing_task.cancel()
        try: await typing_task
        except asyncio.CancelledError: pass

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
            [InlineKeyboardButton("🔄 Новая раскадровка", callback_data="new_storyboard"),
             InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role")],
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]),
        )


async def _generate_character(update: Update, context: ContextTypes.DEFAULT_TYPE, description: str):
    chat_id = update.effective_chat.id
    _add_to_history(context, "character", description)
    progress_id = await send_progress(context.bot, chat_id, "🎭 Создаю карточку персонажа...")

    system = "Ты — опытный сценарист и актёрский педагог. Создаёшь детальные карточки персонажей. Отвечай ТОЛЬКО карточкой — без предисловий."
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
        stop_typing.set(); typing_task.cancel()
        try: await typing_task
        except asyncio.CancelledError: pass

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
            [InlineKeyboardButton("🔄 Новый персонаж", callback_data="new_character"),
             InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role")],
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]),
        )


async def _generate_scene(update: Update, context: ContextTypes.DEFAULT_TYPE, description: str):
    chat_id = update.effective_chat.id
    _add_to_history(context, "scene", description)
    progress_id = await send_progress(context.bot, chat_id, "📝 Пишу сцену...")

    system = "Ты — профессиональный сценарист студии КИСЛОРОД ПРОДАКШЕН. Пишешь сцены в сценарном формате. Отвечай ТОЛЬКО текстом сцены."
    user_msg = (
        f"Напиши сцену:\n\n{description}\n\n"
        "— Сценарный формат (INT./EXT., ремарки, реплики)\n— 150–300 слов\n— В конце: КОНЕЦ СЦЕНЫ"
    )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))
    try:
        response = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    finally:
        stop_typing.set(); typing_task.cancel()
        try: await typing_task
        except asyncio.CancelledError: pass

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
            [InlineKeyboardButton("📝 Новая сцена", callback_data="new_scene"),
             InlineKeyboardButton("🔁 Переписать", callback_data="new_rewrite")],
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]),
        )


async def _generate_monologue(update: Update, context: ContextTypes.DEFAULT_TYPE, description: str):
    chat_id = update.effective_chat.id
    _add_to_history(context, "monologue", description)
    progress_id = await send_progress(context.bot, chat_id, "🎤 Пишу монолог...")

    system = "Ты — опытный сценарист и актёрский педагог студии КИСЛОРОД ПРОДАКШЕН. Пишешь монологи: живые, психологически точные, с подтекстом. Отвечай ТОЛЬКО текстом монолога."
    user_msg = (
        f"Напиши монолог:\n\n{description}\n\n"
        "— 60–120 слов\n— Живая разговорная речь\n— Подтекст важнее текста\n"
        "— После: АКТЁРСКАЯ ЗАМЕТКА: [о ключевом подтексте]"
    )

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))
    try:
        response = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
    finally:
        stop_typing.set(); typing_task.cancel()
        try: await typing_task
        except asyncio.CancelledError: pass

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
            [InlineKeyboardButton("🎤 Новый монолог", callback_data="new_monologue"),
             InlineKeyboardButton("🔁 Переписать", callback_data="new_rewrite")],
            [InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role")],
        ]),
    )


async def rewrite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _stats_inc_tool("rewrite")
    context.user_data["awaiting"] = "rewrite"
    await update.message.reply_text(
        "🔁 Переписать в другом стиле\n\nОтправь текст сцены или диалога — я спрошу, в каком жанре переписать.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_awaiting")]]),
    )


async def _generate_rewrite(update, context, original_text, style):
    chat_id = update.effective_chat.id
    _add_to_history(context, "rewrite", f"{style}: {original_text[:30]}")
    progress_id = await send_progress(context.bot, chat_id, f"🔁 Переписываю в стиле «{style}»...")

    system = "Ты — профессиональный сценарист студии КИСЛОРОД ПРОДАКШЕН. Переписываешь сцены в разных жанрах, сохраняя суть. Отвечай ТОЛЬКО переписанным текстом."
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
        stop_typing.set(); typing_task.cancel()
        try: await typing_task
        except asyncio.CancelledError: pass

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
            [InlineKeyboardButton("🔁 Другой стиль", callback_data="new_rewrite"),
             InlineKeyboardButton("📝 Новая сцена", callback_data="new_scene")],
            [InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role")],
        ]),
    )


# ─────────────────────────────────────────────
# КОМАНДЫ
# ─────────────────────────────────────────────

async def saves_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saves = _get_saves(context)
    if not saves:
        await update.message.reply_text("💾 У тебя пока нет сохранённых работ.\n\nПосле генерации нажми кнопку 💾 Сохранить.")
        return
    folder_counts = {}
    for s in saves:
        folder_counts[s["type"]] = folder_counts.get(s["type"], 0) + 1
    folder_buttons = []
    for ftype, flabel in SAVE_FOLDERS.items():
        cnt = folder_counts.get(ftype, 0)
        if cnt > 0:
            folder_buttons.append([InlineKeyboardButton(f"{flabel} ({cnt})", callback_data=f"folder|{ftype}")])
    folder_buttons.append([InlineKeyboardButton("📤 Экспорт всех в TXT", callback_data="export_saves")])
    await update.message.reply_text(
        f"💾 Твои сохранения — {len(saves)} работ\n\nВыбери папку:",
        reply_markup=InlineKeyboardMarkup(folder_buttons),
    )


@admin_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users = len(_stats["total_users"])
    role_labels = {"actor": "🎭 Актёр", "director": "🎬 Режиссёр", "screenwriter": "✍️ Сценарист", "producer": "💼 Продюсер", "client": "🤝 Заказчик", "general": "🌐 Общий"}
    tool_labels = {"storyboard": "🎬 Раскадровка", "character": "🎭 Персонаж", "scene": "📝 Сцена", "monologue": "🎤 Монолог", "rewrite": "🔁 Переписка", "poster": "🖼 Постер", "analyze": "📄 Разбор", "pitch": "🎯 Питч"}

    role_lines = [f"  {role_labels.get(k, k)}: {v}" for k, v in sorted(_stats["roles_chosen"].items(), key=lambda x: -x[1])]
    tool_lines = [f"  {tool_labels.get(k, k)}: {v}" for k, v in sorted(_stats["tools_used"].items(), key=lambda x: -x[1])]

    text = (
        "📊 Статистика бота КИСЛОРОД AI\n\n"
        f"👥 Уникальных пользователей: {total_users}\n"
        f"💬 Всего сообщений: {_stats['total_messages']}\n"
        f"💾 Сохранений создано: {_stats['saves_total']}\n"
        f"📢 Постов опубликовано: {_stats['posts_sent']}\n\n"
        "🎭 Выбор ролей:\n" + ("\n".join(role_lines) if role_lines else "  —") + "\n\n"
        "🛠 Использование инструментов:\n" + ("\n".join(tool_lines) if tool_lines else "  —") + "\n\n"
        "⚠️ Статистика сбрасывается при перезапуске бота."
    )
    await update.message.reply_text(text)


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
        "/poster         — Генератор постера 🖼\n"
        "/analyze        — Разбор сценария 📄\n"
        "/pitch          — AI-Питчинг 🎯\n"
        "/help           — Справка\n"
    )

    admin_text = (
        "\n── Только для администратора ──\n"
        "/stats             — 📊 Статистика бота\n"
        "/schedule          — Расписание автопостинга\n\n"
        "📰 Ручной постинг:\n"
        "/post_now          — Новости кино (NewsAPI)\n"
        "/film_now          — 🎬 Фильм (Kinoafisha+TMDB)\n"
        "/series_now        — 📺 Сериал\n"
        "/cartoon_now       — 🎨 Мультфильм\n"
        "/premiere_now      — 🔥 Премьера\n"
        "/kinoafisha_now    — 🎟 Дайджест Киноафиши\n"
        "/myfilm_now        — Из фильмографии\n"
        "/poster_now        — 🖼 Постер в каналы\n"
        "/funny_now         — 😂 Смешной постер\n"
    )

    footer = "\nКонтакты:\n📧 actorsashapotapov@gmail.com\n💬 @actorsashapotapov"
    full_text = base_text + (admin_text if is_admin else "") + footer
    await update.message.reply_text(full_text, reply_markup=webapp_keyboard())


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("✅ История очищена. Нажми 📋 Меню чтобы выбрать роль:", reply_markup=webapp_keyboard())


@admin_only
async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 Расписание автопостинга (МСК):\n\n"
        "📺 @realtimeproductionn — 7 постов:\n"
        "   🕘 09:00 — Цитата дня ✨\n"
        "   🕙 10:00 — Новости кино 📰\n"
        "   🕙 11:30 — Фильм 🎬 (Kinoafisha→TMDB→Streaming)\n"
        "   🕐 13:00 — Сериал 📺 (оба канала)\n"
        "   🕒 15:00 — Мультфильм 🎨\n"
        "   🕔 17:00 — Премьера 🔥\n"
        "   🕖 19:00 — Вечерний дайджест\n\n"
        "🎭 @actorsashapotapovv — 5 постов:\n"
        "   🕘 09:00 — Цитата дня ✨\n"
        "   🕚 11:00 — Утренний пост 📰\n"
        "   🕐 13:00 — Сериал 📺 (вместе с КИСЛОРОД)\n"
        "   🕑 14:00 — Из фильмографии 🎬\n"
        "   🕡 18:30 — Фильм 🎬\n"
        "   🕗 20:00 — Вечерний пост\n\n"
        "📸 Оба канала:\n"
        "   🕛 12:00 — Смешной постер 😂\n"
        "   🕡 16:30 — Кино-факт 🎥\n"
        "   🕥 20:30 — Тематический постер 🖼\n"
        "   Воскресенье 12:00 — Опрос недели 📊\n\n"
        "Источники: Kinoafisha.info → TMDB → Streaming API → YandexGPT"
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
async def kinoafisha_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Публикует дайджест с Киноафиши в оба канала."""
    await update.message.reply_text("⏳ Парсю Киноафишу (~10 сек)...")
    text, img = await generate_kinoafisha_news_post()
    if text and not text.startswith("⚠️"):
        await send_post(context.bot, CHANNEL_KISLOROD, text, img)
        await send_post(context.bot, CHANNEL_ACTOR, text, img)
        await update.message.reply_text("✅ Дайджест Киноафиши опубликован в оба канала!")
    else:
        await update.message.reply_text("❌ Не удалось получить данные с Киноафиши.")


@admin_only
async def film_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу новинку фильм (~15 сек)...")
    text, img = await generate_streaming_film_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img, parse_mode="Markdown")
        await send_post(context.bot, CHANNEL_ACTOR, text, img, parse_mode="Markdown")
        await update.message.reply_text("✅ Фильм опубликован в оба канала!")
    else:
        await update.message.reply_text("❌ Не удалось. Источники: Kinoafisha, TMDB, Streaming — все недоступны.")


@admin_only
async def series_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу новинку сериал (~10 сек)...")
    text, img = await generate_streaming_series_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img, parse_mode="Markdown")
        await send_post(context.bot, CHANNEL_ACTOR, text, img, parse_mode="Markdown")
        await update.message.reply_text("✅ Сериал опубликован в оба канала!")
    else:
        await update.message.reply_text("❌ Не удалось. Проверь TMDB_API_KEY и RAPIDAPI_KEY.")


@admin_only
async def cartoon_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу мультфильм (~15 сек)...")
    text, img = await generate_streaming_cartoon_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img, parse_mode="Markdown")
        await send_post(context.bot, CHANNEL_ACTOR, text, img, parse_mode="Markdown")
        await update.message.reply_text("✅ Мультфильм опубликован в оба канала!")
    else:
        await update.message.reply_text("❌ Не удалось.")


@admin_only
async def premiere_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Ищу премьеру (~15 сек)...")
    text, img = await generate_streaming_premiere_post()
    if text:
        await send_post(context.bot, CHANNEL_KISLOROD, text, img, parse_mode="Markdown")
        await send_post(context.bot, CHANNEL_ACTOR, text, img, parse_mode="Markdown")
        await update.message.reply_text("✅ Премьера опубликована в оба канала!")
    else:
        await update.message.reply_text("❌ Не удалось.")


@admin_only
async def funny_now_command(update, context):
    await update.message.reply_text("😂 Генерирую смешной постер (~60 сек)...")
    film_title, concept, art_prompt = await generate_funny_film_poster_idea()
    image_bytes = await generate_image(art_prompt)
    caption = await generate_funny_poster_caption(film_title, concept)
    results = []
    for channel in [CHANNEL_KISLOROD, CHANNEL_ACTOR]:
        if image_bytes:
            ok = await send_photo_safe(context.bot, channel, image_bytes, caption)
            if ok:
                results.append(f"✅ {channel}")
                _stats["posts_sent"] += 1
                continue
        try:
            await context.bot.send_message(chat_id=channel, text=caption)
            results.append(f"📝 {channel} (текст)")
            _stats["posts_sent"] += 1
        except Exception as e:
            results.append(f"❌ {channel}: {e}")
    await update.message.reply_text(
        f"{'✅' if image_bytes else '⚠️'} Смешной постер «{film_title}»\n" + "\n".join(results)
    )


@admin_only
async def poster_now_command(update, context):
    await update.message.reply_text("⏳ Генерирую постер для каналов (~60 сек)...")
    import io
    global _poster_theme_index
    theme_prompt, theme_label = POSTER_THEMES[_poster_theme_index % len(POSTER_THEMES)]
    _poster_theme_index += 1
    art_prompt = f"Movie poster, cinematic, professional, high quality, dramatic lighting: {theme_prompt}. Film poster style, bold typography space, atmospheric"
    image_bytes = await generate_image(art_prompt)
    if image_bytes:
        system = "Ты — редактор Telegram-канала о кино. Отвечай ТОЛЬКО текстом поста."
        user_msg = f"Напиши короткий вдохновляющий пост для постера «{theme_label}». 2-3 предложения, эмодзи, хэштеги #кино #постер #кислородпродакшен"
        caption = await ask_yandex_gpt(system, [{"role": "user", "text": user_msg}])
        bio = io.BytesIO(image_bytes)
        bio.name = "poster.jpg"
        for channel in [CHANNEL_KISLOROD, CHANNEL_ACTOR]:
            try:
                bio.seek(0)
                await context.bot.send_photo(chat_id=channel, photo=bio, caption=caption[:1024])
            except Exception as e:
                logger.error(f"poster_now error {channel}: {e}")
        await update.message.reply_text("✅ Постер опубликован в оба канала!")
    else:
        await update.message.reply_text("❌ Генерация не удалась. Попробуй снова.")


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
# MAIN
# ─────────────────────────────────────────────

def main():
    logger.info("=== KISLOROD AI Bot starting ===")
    logger.info(f"BOT_TOKEN:         {'✅' if BOT_TOKEN        else '❌ НЕ ЗАДАН'}")
    logger.info(f"YANDEX_API_KEY:    {'✅' if YANDEX_API_KEY   else '❌ НЕ ЗАДАН'}")
    logger.info(f"YANDEX_FOLDER_ID:  {YANDEX_FOLDER_ID         or '❌ НЕ ЗАДАН'}")
    logger.info(f"NEWS_API_KEY:      {'✅' if NEWS_API_KEY      else '❌ НЕ ЗАДАН'}")
    logger.info(f"RAPIDAPI_KEY:      {'✅' if RAPIDAPI_KEY      else '❌ НЕ ЗАДАН (Streaming отключён)'}")
    logger.info(f"TMDB_API_KEY:      {'✅' if TMDB_API_KEY      else '❌ НЕ ЗАДАН'}")
    logger.info(f"REPLICATE_API_KEY: {'✅' if REPLICATE_API_KEY else '❌ НЕ ЗАДАН'}")
    logger.info(f"HF_TOKEN:          {'✅' if HF_TOKEN          else '❌ НЕ ЗАДАН'}")
    logger.info(f"TOGETHER_API_KEY:  {'✅' if TOGETHER_API_KEY  else '❌ НЕ ЗАДАН'}")
    logger.info(f"IMAGE_STYLE:       {IMAGE_STYLE}")
    logger.info(f"ADMIN_IDS:         {ADMIN_IDS}")
    logger.info("Источники контента: Kinoafisha.info → TMDB → Streaming API → YandexGPT")

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды для всех
    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("help",        help_command))
    app.add_handler(CommandHandler("clear",       clear_command))
    app.add_handler(CommandHandler("saves",       saves_command))
    app.add_handler(CommandHandler("storyboard",  storyboard_command))
    app.add_handler(CommandHandler("character",   character_command))
    app.add_handler(CommandHandler("scene",       scene_command))
    app.add_handler(CommandHandler("monologue",   monologue_command))
    app.add_handler(CommandHandler("rewrite",     rewrite_command))
    app.add_handler(CommandHandler("poster",      poster_command))
    app.add_handler(CommandHandler("analyze",     analyze_command))
    app.add_handler(CommandHandler("pitch",       pitch_command))

    # Только для администратора
    app.add_handler(CommandHandler("stats",           stats_command))
    app.add_handler(CommandHandler("schedule",        schedule_command))
    app.add_handler(CommandHandler("post_now",        post_now_command))
    app.add_handler(CommandHandler("film_now",        film_now_command))
    app.add_handler(CommandHandler("series_now",      series_now_command))
    app.add_handler(CommandHandler("cartoon_now",     cartoon_now_command))
    app.add_handler(CommandHandler("premiere_now",    premiere_now_command))
    app.add_handler(CommandHandler("myfilm_now",      myfilm_now_command))
    app.add_handler(CommandHandler("poster_now",      poster_now_command))
    app.add_handler(CommandHandler("funny_now",       funny_now_command))
    app.add_handler(CommandHandler("kinoafisha_now",  kinoafisha_now_command))

    # Callback и сообщения
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ── Расписание (UTC = МСК − 3) ──────────────────────────
    # Оба канала
    app.job_queue.run_daily(job_quote_day,        time=dtime(6,  0))   # 09:00 МСК ✅ (было 9:00 — конфликт с funny)
    app.job_queue.run_daily(job_funny_poster,     time=dtime(9,  0))   # 12:00 МСК ✅ ИСПРАВЛЕНО (разведено с цитатой)
    app.job_queue.run_daily(job_kinofact,         time=dtime(13, 30))  # 16:30 МСК
    app.job_queue.run_daily(job_channel_poster,   time=dtime(17, 30))  # 20:30 МСК
    app.job_queue.run_daily(job_weekly_poll,      time=dtime(9,  0), days=(6,))  # воскр. 12:00 МСК

    # @realtimeproductionn
    app.job_queue.run_daily(job_kislorod_morning,  time=dtime(7,  0))   # 10:00 МСК
    app.job_queue.run_daily(job_kislorod_film,     time=dtime(8, 30))   # 11:30 МСК
    app.job_queue.run_daily(job_both_series,       time=dtime(10,  0))  # 13:00 МСК (оба канала)
    app.job_queue.run_daily(job_kislorod_cartoon,  time=dtime(12,  0))  # 15:00 МСК
    app.job_queue.run_daily(job_kislorod_premiere, time=dtime(14,  0))  # 17:00 МСК
    app.job_queue.run_daily(job_kislorod_evening,  time=dtime(16,  0))  # 19:00 МСК

    # @actorsashapotapovv
    app.job_queue.run_daily(job_actor_morning,     time=dtime(8,  0))   # 11:00 МСК
    # job_both_series покрывает 13:00 для актёрского канала
    app.job_queue.run_daily(job_actor_filmography, time=dtime(11,  0))  # 14:00 МСК
    app.job_queue.run_daily(job_actor_film,        time=dtime(15, 30))  # 18:30 МСК
    app.job_queue.run_daily(job_actor_evening,     time=dtime(17,  0))  # 20:00 МСК

    logger.info("=== Расписание запущено. Bot работает! ===")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
