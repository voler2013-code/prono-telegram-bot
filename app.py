import os
import re
from fastapi import FastAPI, Request
import httpx
import domain

TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

app = FastAPI()

# ------------------------------------------------------------
# Función de escape completa para MarkdownV2 de Telegram
# (por si alguna vez no usás bloque de código)
# ------------------------------------------------------------
def escape_markdown_v2(text: str) -> str:
    """Escapa todos los caracteres especiales de MarkdownV2."""
    # Caracteres que deben ser escapados: _ * [ ] ( ) ~ ` > # + - = | { } . ! \
    special_chars = r'_*[]()~`>#+-=|{}.!'
    # Usamos regex para escapar cada carácter especial añadiendo \ delante
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)


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
        # El mensaje de ayuda es corto, lo enviamos sin bloque de código y sin parse_mode
        parse_mode = None
    else:
        try:
            resultado = domain.resolver_consulta(text)
            # El resultado (sondeo u otro texto) lo metemos en un bloque de código
            # para que se vea exactamente igual que en la terminal.
            reply = f"```\n{resultado}\n```"
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
                "parse_mode": parse_mode  # None para texto plano, "MarkdownV2" para bloque de código
            },
            timeout=30,
        )

    return {"ok": True}
