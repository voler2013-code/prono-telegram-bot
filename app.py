import os
from fastapi import FastAPI, Request
import httpx
import domain

TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

app = FastAPI()

# Carácter Unicode visualmente igual al punto ASCII '.'
DOT_UNICODE = "\u2024"  # ONE DOT LEADER


def sanitize_for_telegram(text: str) -> str:
    """
    Reemplaza todos los puntos ASCII '.' por un carácter Unicode
    que se ve igual pero que Telegram no interpreta como especial.
    """
    return text.replace('.', DOT_UNICODE)


@app.get("/")
def root():
    return {"ok": True, "msg": "Bot online"}


@app.post(f"/webhook/{TOKEN}")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    if text.strip() in ("/start", "/help"):
        reply = (
            "Envíame una consulta tipo:\n"
            "• hoy; 15hs; cuchi\n"
            "• hoy; alpina; 15hs; -5,5; 8,1\n"
            "• 01-12-2025; 14hs; -31,55; -64,33; -9; 25\n"
            "Acepto lugar/fecha/horario/coords/dupla en cualquier orden."
        )
        # Para el mensaje de ayuda no necesitamos formato especial
        parse_mode = None
    else:
        try:
            resultado = domain.resolver_consulta(text)
            # 1. Reemplazamos los puntos conflictivos
            safe_result = sanitize_for_telegram(resultado)
            # 2. Envolvemos en bloque de código para respetar espacios y caracteres
            reply = f"```\n{safe_result}\n```"
            parse_mode = "MarkdownV2"
        except Exception as e:
            reply = f"```\nError: {e}\n```"
            parse_mode = "MarkdownV2"

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": reply,
                "parse_mode": parse_mode
            },
            timeout=30,
        )

    return {"ok": True}
