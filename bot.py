"""
KISLOROD PRODUCTION — AI Telegram Bot
Powered by YandexGPT via Yandex Foundation Models API
"""

import os
import logging
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

YANDEX_MODEL = f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest"

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
#  ROLE SYSTEM PROMPTS
# ─────────────────────────────────────────
ROLE_PROMPTS = {
    "actor": {
        "emoji": "🎭",
        "label": "Актёр",
        "system": (
            "Ты — опытный театральный и киноактёр-наставник студии КИСЛОРОД ПРОДАКШЕН. "
            "Помогаешь актёрам готовиться к ролям: разбираешь характер персонажа, его биографию, "
            "мотивацию, физические и эмоциональные состояния. "
            "Для примерки образа предлагаешь детальное описание внешнего вида, костюма, грима "
            "персонажа (motion concept). "
            "Когда актёр описывает видео-пробу словами — даёшь конкретный разбор: что сильно, "
            "что слабо, как улучшить. "
            "Отвечай на русском языке. Будь вдохновляющим, точным, как настоящий мастер."
        ),
        "welcome": (
            "🎭 *Привет, актёр!*\n\n"
            "Я твой личный AI-наставник студии КИСЛОРОД ПРОДАКШЕН.\n\n"
            "Чем могу помочь:\n"
            "• 📖 Подготовка к роли — характер, биография, мотивация\n"
            "• 👗 Примерка образа — внешность, костюм, грим\n"
            "• 🎬 Разбор видео-проб — сильные и слабые стороны\n"
            "• 💬 Работа с текстом сцены и диалогами\n\n"
            "Над какой ролью ты сейчас работаешь?"
        )
    },
    "director": {
        "emoji": "🎬",
        "label": "Режиссёр",
        "system": (
            "Ты — креативный режиссёр-наставник студии КИСЛОРОД ПРОДАКШЕН. "
            "Помогаешь режиссёрам разрабатывать концепции, раскадровки, визуальный стиль, "
            "режиссёрский замысел. "
            "Предлагаешь идеи для сцен, переходов, ракурсов, цветовых решений. "
            "Можешь создать подробный режиссёрский план, разобрать конкретную сцену, "
            "предложить операторские решения. "
            "Отвечай на русском языке. Будь дерзким и кинематографически мыслящим."
        ),
        "welcome": (
            "🎬 *Привет, режиссёр!*\n\n"
            "Я твой AI-ассистент для режиссёрской работы.\n\n"
            "Помогу с:\n"
            "• 🎯 Концепция и визуальный стиль проекта\n"
            "• 📋 Раскадровка и план съёмок\n"
            "• 🎨 Цветовая палитра, атмосфера, ракурсы\n"
            "• 🎭 Работа с актёрами и мизансцены\n"
            "• 📝 Режиссёрский сценарий\n\n"
            "Какой проект в работе?"
        )
    },
    "screenwriter": {
        "emoji": "✍️",
        "label": "Сценарист",
        "system": (
            "Ты — сценарист студии КИСЛОРОД ПРОДАКШЕН. "
            "Помогаешь писать сценарии, диалоги, синопсисы. "
            "Разрабатываешь характеры персонажей и их арки развития. "
            "Предлагаешь структуры историй, конфликты, повороты. "
            "Пишешь живые кинематографические диалоги. "
            "Можешь создать полноценный питч-документ или тритмент. "
            "Отвечай на русском языке. Будь литературным и глубоким."
        ),
        "welcome": (
            "✍️ *Привет, сценарист!*\n\n"
            "Я твой AI-соавтор для работы над историями.\n\n"
            "Создадим вместе:\n"
            "• 💡 Синопсис и структуру истории\n"
            "• 👥 Характеры и арки персонажей\n"
            "• 💬 Живые диалоги и сцены\n"
            "• 📄 Тритмент и питч-документ\n"
            "• 🔄 Сюжетные повороты и конфликты\n\n"
            "Какая идея требует воплощения?"
        )
    },
    "producer": {
        "emoji": "💼",
        "label": "Продюсер",
        "system": (
            "Ты — продюсер студии КИСЛОРОД ПРОДАКШЕН. "
            "Помогаешь с питчингом, бюджетами, тайм-менеджментом производства. "
            "Разрабатываешь тритменты, лукбуки, презентации для инвесторов. "
            "Создаёшь структурированные производственные документы. "
            "Знаешь специфику AI-продакшена и современные инструменты. "
            "Отвечай на русском языке. Будь чётким, структурированным, деловым."
        ),
        "welcome": (
            "💼 *Привет, продюсер!*\n\n"
            "Я твой AI-ассистент для производственных задач.\n\n"
            "Помогу с:\n"
            "• 📊 Питч и презентация для инвесторов\n"
            "• 💰 Структура бюджета и планирование\n"
            "• 📋 Производственный план и дедлайны\n"
            "• 📁 Тритмент и лукбук проекта\n"
            "• 🤝 Переговорные позиции и аргументы\n\n"
            "Что за проект?"
        )
    },
    "client": {
        "emoji": "🏢",
        "label": "Заказчик",
        "system": (
            "Ты — клиентский менеджер студии КИСЛОРОД ПРОДАКШЕН. "
            "Помогаешь заказчикам сформулировать техническое задание, брифинг, "
            "креативную концепцию. "
            "Создаёшь структурированные концепт-документы и презентации. "
            "Умеешь превратить размытую идею в чёткое ТЗ. "
            "Контакты студии: actorsashapotapov@gmail.com | @actorsashapotapov. "
            "Отвечай на русском языке. Будь дружелюбным, терпеливым, профессиональным."
        ),
        "welcome": (
            "🏢 *Привет!*\n\n"
            "Я помогу воплотить вашу идею в готовый проект КИСЛОРОД ПРОДАКШЕН.\n\n"
            "Вместе создадим:\n"
            "• 📝 Техническое задание и бриф\n"
            "• 🎨 Креативная концепция проекта\n"
            "• 📊 Презентация и визуальный дашборд\n"
            "• 🎯 Цели, аудитория, ключевые сообщения\n"
            "• 💬 Коммуникационная стратегия\n\n"
            "Расскажите о вашей задаче — я помогу её сформулировать чётко."
        )
    },
    "general": {
        "emoji": "💬",
        "label": "Общий",
        "system": (
            "Ты — AI-ассистент студии КИСЛОРОД ПРОДАКШЕН — творческой AI-студии, "
            "создающей мультфильмы, клипы, сериалы и рекламу. "
            "Помогаешь всем: актёрам, режиссёрам, сценаристам, продюсерам и заказчикам. "
            "Сайт: https://aliferovaaleksandr-del.github.io/kislorod-production/ "
            "Email: actorsashapotapov@gmail.com | Telegram: @actorsashapotapov. "
            "Отвечай на русском языке. Будь вдохновляющим и конкретным."
        ),
        "welcome": (
            "✦ *Добро пожаловать в КИСЛОРОД ПРОДАКШЕН!*\n\n"
            "Я AI-ассистент творческой студии нового поколения.\n\n"
            "Выбери роль ниже — и я настроюсь специально для тебя, "
            "или просто напиши свой вопрос! 👇"
        )
    }
}

# ─────────────────────────────────────────
#  YANDEX GPT API
# ─────────────────────────────────────────
async def ask_yandex_gpt(system_prompt: str, conversation: list[dict]) -> str:
    """Call YandexGPT Foundation Models API."""
    messages = [{"role": "system", "text": system_prompt}]
    for msg in conversation[-20:]:  # keep last 20 messages
        messages.append({"role": msg["role"], "text": msg["text"]})

    model_uri = f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest"

    payload = {
        "modelUri": model_uri,
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 1000
        },
        "messages": messages
    }

    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                json=payload,
                headers=headers
            )
            data = response.json()

            if response.status_code == 200:
                return data["result"]["alternatives"][0]["message"]["text"]
            else:
                logger.error(f"YandexGPT error {response.status_code}: {data}")
                return f"⚠️ Ошибка AI: {data.get('message', 'Неизвестная ошибка')}. Попробуйте снова."
    except Exception as e:
        logger.error(f"YandexGPT request failed: {e}")
        return "⚠️ Не удалось получить ответ. Проверьте соединение и попробуйте снова."


# ─────────────────────────────────────────
#  KEYBOARDS
# ─────────────────────────────────────────
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
            InlineKeyboardButton("🏢 Заказчик", callback_data="role_client"),
            InlineKeyboardButton("💬 Общий", callback_data="role_general"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Сменить роль", callback_data="change_role"),
        InlineKeyboardButton("🗑 Очистить чат", callback_data="clear_chat"),
    ]])


# ─────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    context.user_data.clear()
    welcome_text = (
        "✦ *KISLOROD PRODUCTION — AI АССИСТЕНТ*\n\n"
        "Творческая AI-студия нового поколения.\n"
        "Мультфильмы · Клипы · Сериалы · Реклама\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выбери свою роль — я настроюсь специально для тебя:"
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=role_keyboard()
    )

async def select_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle role selection via inline buttons."""
    query = update.callback_query
    await query.answer()

    action = query.data

    if action == "change_role":
        context.user_data.clear()
        await query.edit_message_text(
            "🔄 Выбери новую роль:",
            reply_markup=role_keyboard()
        )
        return

    if action == "clear_chat":
        role = context.user_data.get("role")
        context.user_data["history"] = []
        await query.answer("✅ История очищена", show_alert=True)
        return

    role_key = action.replace("role_", "")
    if role_key not in ROLE_PROMPTS:
        return

    context.user_data["role"] = role_key
    context.user_data["history"] = []

    role = ROLE_PROMPTS[role_key]
    await query.edit_message_text(
        role["welcome"],
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user text messages and respond via YandexGPT."""
    user_text = update.message.text.strip()

    if not user_text:
        return

    # Check if role is selected
    role_key = context.user_data.get("role")
    if not role_key:
        await update.message.reply_text(
            "👆 Сначала выбери роль:",
            reply_markup=role_keyboard()
        )
        return

    role = ROLE_PROMPTS[role_key]
    history = context.user_data.get("history", [])

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # Add user message to history
    history.append({"role": "user", "text": user_text})

    # Get AI response
    response = await ask_yandex_gpt(role["system"], history)

    # Add assistant response to history
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]  # keep last 30 messages

    # Send response
    await update.message.reply_text(
        response,
        reply_markup=back_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "ℹ️ *KISLOROD AI — Справка*\n\n"
        "📌 *Команды:*\n"
        "/start — Начать / выбрать роль\n"
        "/role — Сменить роль\n"
        "/clear — Очистить историю чата\n"
        "/help — Эта справка\n\n"
        "📌 *Роли:*\n"
        "🎭 Актёр — подготовка к роли, образ, разбор проб\n"
        "🎬 Режиссёр — концепция, раскадровка, стиль\n"
        "✍️ Сценарист — сценарий, диалоги, структура\n"
        "💼 Продюсер — питч, бюджет, презентации\n"
        "🏢 Заказчик — ТЗ, концепция, бриф\n"
        "💬 Общий — любые вопросы студии\n\n"
        "📌 *Контакты:*\n"
        "✉️ actorsashapotapov@gmail.com\n"
        "✈️ @actorsashapotapov\n"
        "🌐 https://aliferovaaleksandr-del.github.io/kislorod-production/"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def role_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /role command."""
    await update.message.reply_text(
        "🔄 Выбери роль:",
        reply_markup=role_keyboard()
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command."""
    context.user_data["history"] = []
    await update.message.reply_text("✅ История чата очищена. Продолжай!")


# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("role", role_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CallbackQueryHandler(select_role))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✦ KISLOROD AI Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
