PASOS PARA SUBIR EL BOT A RENDER

1) Crear cuenta en GitHub y Render.com

2) En GitHub:
   - Crear un repositorio nuevo (public o private)
   - Subir todos los archivos de esta carpeta al repositorio

3) En Render.com:
   - New -> Web Service
   - Conectar con GitHub
   - Seleccionar el repositorio
   - Python 3.11
   - Build Command: pip install -r requirements.txt
   - Start Command: uvicorn app:app --host 0.0.0.0 --port 10000
   - Plan gratuito

4) Variables de entorno en Render:
   - Key: TELEGRAM_TOKEN
   - Value: tu token de BotFather

5) Deploy y obtener URL pública (ej: https://mi-bot.onrender.com)

6) Configurar webhook:
   - Abrir setwebhook.txt
   - Reemplazar <TOKEN> y <TU_URL>
   - Ejecutar el comando en tu terminal

7) Probar en Telegram enviando:
   hoy; 15hs; cuchi
