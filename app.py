# app.py
from fastapi import FastAPI, Request
from important_info.API_loader import env
from Custom_modules.dictionary_api import get_meaning  # old dictionaryapi.dev
from Custom_modules.telegram_bot import _send_async as send_text_async  # await this

# MW helpers (put the module from earlier as custom_modules/mw_dictionary.py)
from Custom_modules.dictionary_api_v2 import (
    fetch_mw_english_json,
    fetch_mw_spanish_json,
    format_mw_entries,
)

WEBHOOK_SECRET = env("WEBHOOK_SECRET")

app = FastAPI()


@app.get("/")
async def health():
    return {"ok": True}


async def send_chunks(chat_id: int, text: str) -> None:
    """Split long messages so Telegram accepts them."""
    limit = 4096
    for i in range(0, len(text), limit):
        await send_text_async(text[i:i + limit], chat_id)


@app.post("/telegram/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        return {"ok": True}

    update = await request.json()
    message = update.get("message") or update.get("channel_post") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    print("UPDATE TEXT:", text)

    if not chat_id or not text:
        return {"ok": True}

    if text.startswith("/dict"):
        # Patterns supported:
        #   /dict hello        -> old dictionaryapi.dev (EN)
        #   /dict mw hello     -> Merriam-Webster English
        #   /dict es hola      -> Merriam-Webster Spanish-English
        parts = text.split()
        if len(parts) == 1:
            await send_chunks(
                chat_id,
                "Usage:\n"
                "/dict <word>\n"
                "/dict mw <word>\n"
                "/dict es <palabra>",
            )
            return {"ok": True}

        # Subcommand?
        sub = parts[1].lower()
        if sub == "mw":
            if len(parts) < 3:
                await send_chunks(chat_id, "Usage: /dict mw <word>")
                return {"ok": True}
            word = " ".join(parts[2:])
            try:
                data = fetch_mw_english_json(word)
                out = format_mw_entries(data, language="en")
            except Exception:
                out = f"Failed to fetch Merriam-Webster entry for '{word}'."
            await send_chunks(chat_id, out)
            return {"ok": True}

        if sub == "es":
            if len(parts) < 3:
                await send_chunks(chat_id, "Usage: /dict es <palabra>")
                return {"ok": True}
            word = " ".join(parts[2:])
            try:
                data = fetch_mw_spanish_json(word)
                out = format_mw_entries(data, language="es")
            except Exception:
                out = f"Failed to fetch Merriam-Webster (Spanish-English) entry for '{word}'."
            await send_chunks(chat_id, out)
            return {"ok": True}

        # Default: old dictionary (dictionaryapi.dev)
        word = " ".join(parts[1:])
        try:
            out = get_meaning(word)
        except Exception:
            out = f"Failed to fetch definition for '{word}'."
        await send_chunks(chat_id, out)
        return {"ok": True}

    # Fallback help
    await send_chunks(
        chat_id,
        "Commands:\n"
        "/dict <word>\n"
        "/dict mw <word>\n"
        "/dict es <palabra>",
    )
    return {"ok": True}
