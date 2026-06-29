import os
import html
from fastapi import FastAPI, Request
import httpx
import domain

TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

app = FastAPI()

# Unicode dot visualmente casi idéntico al ASCII '.'
# U+2024 = ONE DOT LEADER. En fuentes monoespaciadas se ve muy parecido.
DOT_UNICODE = "\u2024"


def sanitize_dots(text: str) -> str:
    """
    Reemplaza todos los puntos ASCII '.' por el carácter Unicode '․'
    para que los puntos en el sondeo aparezcan visualmente más juntos.
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
        parse_mode = None   # Texto plano, sin formato
    else:
        try:
            resultado = domain.resolver_consulta(text)

            # 1. Reemplazar puntos ASCII por el punto Unicode compacto
            resultado_mod = sanitize_dots(resultado)

            # 2. Escapar solo caracteres que rompen HTML (<, >, &)
            safe = html.escape(resultado_mod)

            # 3. Envolver en <pre> para respetar espacios y fuente monoespaciada
            reply = f"<pre>{safe}</pre>"
            parse_mode = "HTML"

        except Exception as e:
            reply = f"<pre>Error: {html.escape(str(e))}</pre>"
            parse_mode = "HTML"

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
