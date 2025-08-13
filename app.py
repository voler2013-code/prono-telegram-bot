import os
from fastapi import FastAPI, Request
import httpx
import domain

TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

app = FastAPI()

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
            "Acepto lugar/fecha/horario/coords/dupla en cualquier orden.\n"
        )
    else:
        try:
            resultado = domain.resolver_consulta(text)
            # Escapar caracteres especiales para MarkdownV2 de Telegram
            safe_resultado = resultado.replace("-", "\-").replace(".", "\.").replace("(", "\(").replace(")", "\)")
            reply = f"```\n{safe_resultado}\n```"
        except Exception as e:
            reply = f"Ocurrió un error procesando tu consulta: {e}"

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": reply, "parse_mode": "MarkdownV2"},
            timeout=30,
        )

    return {"ok": True}
