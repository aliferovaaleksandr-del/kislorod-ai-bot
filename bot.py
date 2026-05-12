import os
import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

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
            "Привет, актёр!\n\n"
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
            "Привет, режиссёр!\n\n"
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
            "Привет, сценарист!\n\n"
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
            "Привет, продюсер!\n\n"
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
            "Привет!\n\n"
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
            "Добро пожаловать в КИСЛОРОД ПРОДАКШЕН!\n\n"
            "Я AI-ассистент творческой студии нового поколения.\n\n"
            "Выбери роль ниже — и я настроюсь специально для тебя!"
        ),
    },
}


async def ask_yandex_gpt(system_prompt, conversation):
    messages = [{"role": "system", "text": system_prompt}]
    for msg in conversation[-20:]:
        messages.append({"role": msg["role"], "text": msg["text"]})

    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 1000,
        },
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
            else:
                logger.error(f"YandexGPT error {response.status_code}: {data}")
                return "Ошибка AI. Попробуй снова."
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return "Не удалось получить ответ. Попробуй снова."


def role_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🎭 Актёр", callback_data="role_actor"),
            InlineKeyboardButton("🎬 Режиссёр", callback_data="role_director"),
        ],
        [
            InlineKeyboardButton("✍️ Сценарист", callback_data="role_screenwriter"),
            InlineKeyboardButton("💼 Продюсер", callback_data="role_producer"),
        ],
        [
            InlineKeyboardButton("🤝 Заказчик", callback_data="role_client"),
            InlineKeyboardButton("🌐 Общий", callback_data="role_general"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role"),
                InlineKeyboardButton("🗑 Очистить чат", callback_data="clear_chat"),
            ]
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🎬 КИСЛОРОД ПРОДАКШЕН — AI АССИСТЕНТ\n\n"
        "Творческая AI-студия нового поколения.\n"
        "Мультфильмы • Клипы • Сериалы • Реклама\n\n"
        "Выбери свою роль:",
        reply_markup=role_keyboard(),
    )


async def select_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "change_role":
        context.user_data.clear()
        await query.edit_message_text("Выбери новую роль:", reply_markup=role_keyboard())
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
    role = ROLE_PROMPTS[role_key]
    await query.edit_message_text(role["welcome"], reply_markup=back_keyboard())


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if not user_text:
        return

    role_key = context.user_data.get("role")
    if not role_key:
        await update.message.reply_text(
            "Сначала выбери роль:", reply_markup=role_keyboard()
        )
        return

    role = ROLE_PROMPTS[role_key]
    history = context.user_data.get("history", [])

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    history.append({"role": "user", "text": user_text})
    response = await ask_yandex_gpt(role["system"], history)
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]

    await update.message.reply_text(response, reply_markup=back_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 КИСЛОРОД AI — Справка\n\n"
        "/start — Начать\n"
        "/role — Сменить роль\n"
        "/clear — Очистить историю\n"
        "/help — Справка\n\n"
        "Контакты:\n"
        "📧 actorsashapotapov@gmail.com\n"
        "💬 @actorsashapotapov"
    )


async def role_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери роль:", reply_markup=role_keyboard())


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("История очищена ✅")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("role", role_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CallbackQueryHandler(select_role))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("KISLOROD AI Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

worker: python bot.py

python-telegram-bot==20.7
httpx>=0.27.0,<0.28.0
