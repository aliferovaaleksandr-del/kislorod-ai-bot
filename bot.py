import os
import sys
import subprocess

subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot==20.7", "httpx==0.26.0", "-q"])

import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ROLE_PROMPTS = {
    "actor": {
        "system": (
            "Ty - opytnyy teatralnyy i kinoakter-nastavnik studii KISLOROD PRODAKSHEN. "
            "Pomogaesh akteram gotovitsya k rolyam: razbivaesh harakter personazha, biografiyu, "
            "motivaciyu, fizicheskie i emocional'nye sostoyaniya. "
            "Dlya primerika obraza predlagaesh detalnoe opisanie vneshnego vida, kostyuma, grima. "
            "Kogda akter opisyvaet video-probu slovami - daesh konkretnyy razbor: chto silno, "
            "chto slabo, kak uluchshit. "
            "Otvechay na russkom yazyke. Bud vdokhnovlyayushchim i tochnym."
        ),
        "welcome": (
            "Privet, akter!\n\n"
            "Ya tvoy lichnyy AI-nastavnik studii KISLOROD PRODAKSHEN.\n\n"
            "Chem mogu pomoch:\n"
            "- Podgotovka k roli\n"
            "- Primerika obraza\n"
            "- Razbor video-prob\n"
            "- Rabota s tekstom sceny\n\n"
            "Nad kakoy rolyu ty seychas rabotaesh?"
        )
    },
    "director": {
        "system": (
            "Ty - kreativnyy rezhisser-nastavnik studii KISLOROD PRODAKSHEN. "
            "Pomogaesh rezhisseram razrabatyvat koncepcii, raskadrovki, vizualnyy stil. "
            "Predlagaesh idei dlya scen, perehodov, rakursov, cvetovykh resheniy. "
            "Otvechay na russkom yazyke. Bud derzkim i kinematograficheski myslyashchim."
        ),
        "welcome": (
            "Privet, rezhisser!\n\n"
            "Ya tvoy AI-assistent dlya rezhisserskoy raboty.\n\n"
            "Pomogu s:\n"
            "- Koncepciya i vizualnyy stil\n"
            "- Raskadrovka i plan semok\n"
            "- Cvetovaya palitra i atmosfera\n"
            "- Rezhisserskiy scenariy\n\n"
            "Kakoy proekt v rabote?"
        )
    },
    "screenwriter": {
        "system": (
            "Ty - scenarist studii KISLOROD PRODAKSHEN. "
            "Pomogaesh pisat scenarii, dialogi, sinopsisy. "
            "Razrabatyvaesh haraktery personazhey i ikh arki razvitiya. "
            "Predlagaesh struktury istoriy, konflikty, povoroty. "
            "Pishesh zhivye kinematograficheskie dialogi. "
            "Otvechay na russkom yazyke. Bud literaturnym i glubokim."
        ),
        "welcome": (
            "Privet, scenarist!\n\n"
            "Ya tvoy AI-soavtor dlya raboty nad istoriyami.\n\n"
            "Sozdadim vmeste:\n"
            "- Sinopsis i struktura istorii\n"
            "- Haraktery personazhey\n"
            "- Zhivye dialogi i sceny\n"
            "- Tritment i pitch-dokument\n\n"
            "Kakaya ideya trebuet voploshcheniya?"
        )
    },
    "producer": {
        "system": (
            "Ty - produuser studii KISLOROD PRODAKSHEN. "
            "Pomogaesh s pitchingom, byudzhetami, tajm-menedzhmentom proizvodstva. "
            "Razrabatyvaesh tritmenty, lukbuki, prezentacii dlya investorov. "
            "Otvechay na russkom yazyke. Bud chetkim i strukturirovannym."
        ),
        "welcome": (
            "Privet, produuser!\n\n"
            "Ya tvoy AI-assistent dlya proizvodstvennykh zadach.\n\n"
            "Pomogu s:\n"
            "- Pitch i prezentaciya dlya investorov\n"
            "- Struktura byudzheta\n"
            "- Proizvodstvennyy plan\n"
            "- Tritment i lukbuk\n\n"
            "Chto za proekt?"
        )
    },
    "client": {
        "system": (
            "Ty - klientskiy menedzher studii KISLOROD PRODAKSHEN. "
            "Pomogaesh zakazchikam sformulirovat TZ, brif, kreativnuyu koncepciyu. "
            "Sozdaesh strukturirovannye koncept-dokumenty i prezentacii. "
            "Kontakty studii: actorsashapotapov@gmail.com | @actorsashapotapov. "
            "Otvechay na russkom yazyke. Bud druzhelyubnym i professionalnym."
        ),
        "welcome": (
            "Privet!\n\n"
            "Ya pomogu voploshchit vashu ideyu v gotovyy proekt.\n\n"
            "Vmeste sozdadim:\n"
            "- Tekhnicheskoe zadanie i brief\n"
            "- Kreativnaya koncepciya\n"
            "- Prezentaciya proekta\n"
            "- Kommunikacionnaya strategiya\n\n"
            "Rasskazhite o vashey zadache."
        )
    },
    "general": {
        "system": (
            "Ty - AI-assistent studii KISLOROD PRODAKSHEN - tvorcheskoy AI-studii, "
            "sozdayushchey multfilmy, klipy, serialy i reklamu. "
            "Pomogaesh vsem: akteram, rezhisseram, scenaristam, produuseram i zakazchikam. "
            "Sayt: https://aliferovaaleksandr-del.github.io/kislorod-production/ "
            "Email: actorsashapotapov@gmail.com | Telegram: @actorsashapotapov. "
            "Otvechay na russkom yazyke."
        ),
        "welcome": (
            "Dobro pozhalovat v KISLOROD PRODAKSHEN!\n\n"
            "Ya AI-assistent tvorcheskoy studii novogo pokoleniya.\n\n"
            "Vyberi rol nizhe - i ya nastroysya specialno dlya tebya!"
        )
    }
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
                return "Oshibka AI. Poprobuy snova."
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return "Ne udalos poluchit otvet. Poprobuy snova."


def role_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("Akter", callback_data="role_actor"),
            InlineKeyboardButton("Rezhisser", callback_data="role_director"),
        ],
        [
            InlineKeyboardButton("Scenarist", callback_data="role_screenwriter"),
            InlineKeyboardButton("Produuser", callback_data="role_producer"),
        ],
        [
            InlineKeyboardButton("Zakazchik", callback_data="role_client"),
            InlineKeyboardButton("Obshchiy", callback_data="role_general"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def back_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Smenit rol", callback_data="change_role"),
        InlineKeyboardButton("Ochistit chat", callback_data="clear_chat"),
    ]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "KISLOROD PRODUCTION - AI ASSISTENT\n\n"
        "Tvorcheskaya AI-studiya novogo pokoleniya.\n"
        "Multfilmy, Klipy, Serialy, Reklama\n\n"
        "Vyberi svoyu rol:",
        reply_markup=role_keyboard()
    )


async def select_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "change_role":
        context.user_data.clear()
        await query.edit_message_text("Vyberi novuyu rol:", reply_markup=role_keyboard())
        return

    if action == "clear_chat":
        context.user_data["history"] = []
        await query.answer("Istoriya ochistchena", show_alert=True)
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
        await update.message.reply_text("Snachala vyberi rol:", reply_markup=role_keyboard())
        return

    role = ROLE_PROMPTS[role_key]
    history = context.user_data.get("history", [])

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    history.append({"role": "user", "text": user_text})
    response = await ask_yandex_gpt(role["system"], history)
    history.append({"role": "assistant", "text": response})
    context.user_data["history"] = history[-30:]

    await update.message.reply_text(response, reply_markup=back_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "KISLOROD AI - Spravka\n\n"
        "/start - Nachat\n"
        "/role - Smenit rol\n"
        "/clear - Ochistit istoriyu\n"
        "/help - Spravka\n\n"
        "Kontakty:\n"
        "actorsashapotapov@gmail.com\n"
        "@actorsashapotapov"
    )


async def role_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Vyberi rol:", reply_markup=role_keyboard())


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("Istoriya ochistchena!")


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
