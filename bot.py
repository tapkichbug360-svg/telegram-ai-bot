"""
==============================================
  TELEGRAM AI BOT - WEB SERVICE (WEBHOOK)
==============================================
- Dùng webhook thay vì polling
- Chạy trên Render Web Service (có gói Free)
==============================================
"""

import os
import requests
import urllib.parse
import logging
from io import BytesIO
from collections import defaultdict
from pathlib import Path
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

# ==================== ĐỌC FILE .ENV ====================
env_path = Path(__file__).parent / ".env"
TELEGRAM_TOKEN = ""
OPENROUTER_API_KEY = ""

if env_path.exists():
    with open(env_path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                TELEGRAM_TOKEN = line.split("=", 1)[1].strip()
            elif line.startswith("OPENROUTER_API_KEY="):
                OPENROUTER_API_KEY = line.split("=", 1)[1].strip()

if not TELEGRAM_TOKEN:
    raise SystemExit("❌ Thiếu TELEGRAM_BOT_TOKEN trong file .env")

# ==================== CẤU HÌNH ====================
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "openrouter/free"

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== LƯU TRỮ ====================
chat_histories = defaultdict(list)
bot = Bot(token=TELEGRAM_TOKEN)

# ==================== HÀM GỌI AI ====================
def ask_ai(chat_id: int, prompt: str) -> str:
    try:
        history = chat_histories.get(chat_id, [])
        
        messages = [
            {"role": "system", "content": "Bạn là trợ lý AI thông minh. Trả lời ngắn gọn, chính xác bằng tiếng Việt."}
        ]
        
        for msg in history[-10:]:
            if msg.startswith("User:"):
                messages.append({"role": "user", "content": msg[5:]})
            elif msg.startswith("Bot:"):
                messages.append({"role": "assistant", "content": msg[4:]})
        
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            reply = result['choices'][0]['message']['content']
            return reply.strip() if reply else "⚠️ AI trả lời rỗng!"
        else:
            return f"⚠️ Lỗi API: {response.status_code}"
            
    except Exception as e:
        return f"⚠️ Lỗi: {str(e)[:100]}"

# ==================== TẠO ẢNH ====================
def generate_image(prompt: str) -> bytes:
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()

# ==================== XỬ LÝ UPDATE ====================
async def handle_update(update: Update):
    """Xử lý update từ Telegram"""
    if not update.message:
        return
    
    chat_id = update.message.chat.id
    user_text = update.message.text.strip() if update.message.text else ""
    
    if not user_text:
        return
    
    # Xử lý lệnh /hoi
    if user_text.startswith('/hoi'):
        # Lấy nội dung sau lệnh /hoi
        parts = user_text.split(maxsplit=1)
        if len(parts) < 2:
            await bot.send_message(chat_id=chat_id, text="💬 Cách dùng: `/hoi câu hỏi của bạn`", parse_mode='Markdown')
            return
        question = parts[1]
        
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        reply = ask_ai(chat_id, question)
        
        # Lưu lịch sử
        chat_histories[chat_id].append(f"User: {question}")
        chat_histories[chat_id].append(f"Bot: {reply}")
        
        if len(chat_histories[chat_id]) > 30:
            chat_histories[chat_id] = chat_histories[chat_id][-30:]
        
        await bot.send_message(chat_id=chat_id, text=reply)
        return
    
    # Xử lý lệnh /ve
    if user_text.startswith('/ve'):
        parts = user_text.split(maxsplit=1)
        if len(parts) < 2:
            await bot.send_message(chat_id=chat_id, text="🎨 Cách dùng: `/ve mô tả ảnh`", parse_mode='Markdown')
            return
        prompt = parts[1]
        
        await bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        try:
            img_bytes = generate_image(prompt)
            await bot.send_photo(
                chat_id=chat_id,
                photo=BytesIO(img_bytes),
                caption=f'🎨 *{prompt[:50]}*',
                parse_mode='Markdown'
            )
        except Exception as e:
            await bot.send_message(chat_id=chat_id, text=f"⚠️ Lỗi tạo ảnh: {e}")
        return
    
    # Xử lý lệnh /reset
    if user_text.startswith('/reset'):
        chat_histories[chat_id] = []
        await bot.send_message(chat_id=chat_id, text="🗑️ Đã xóa lịch sử trò chuyện!")
        return
    
    # Xử lý lệnh /start
    if user_text.startswith('/start'):
        await bot.send_message(
            chat_id=chat_id,
            text="🤖 *Bot AI - Miễn Phí 100%*\n\n"
                 "✨ *Tính năng:*\n"
                 "• 💬 `/hoi câu hỏi` - Hỏi AI\n"
                 "• 🎨 `/ve mô tả` - Tạo ảnh\n"
                 "• 🔄 `/reset` - Xóa lịch sử\n\n"
                 "💡 *Ví dụ:*\n"
                 "• `/hoi 1+1 bằng mấy?`\n"
                 "• `/ve con mèo dễ thương`",
            parse_mode='Markdown'
        )
        return

# ==================== FLASK WEBHOOK ====================
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Bot is running!", 200

@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        import asyncio
        asyncio.run(handle_update(update))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

# ==================== KHỞI ĐỘNG ====================
if __name__ == "__main__":
    # Set webhook
    port = int(os.environ.get("PORT", 10000))
    # Lấy URL từ Render (Render tự động set biến RENDER_EXTERNAL_HOSTNAME)
    render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
    
    if render_hostname:
        webhook_url = f"https://{render_hostname}/webhook/{TELEGRAM_TOKEN}"
    else:
        # Chạy local
        webhook_url = f"https://localhost/webhook/{TELEGRAM_TOKEN}"
    
    print(f"\n{'='*50}")
    print(f"🚀 Bot đang chạy Web Service mode!")
    print(f"🔗 Webhook URL: {webhook_url}")
    print(f"{'='*50}\n")
    
    # Chạy Flask
    app.run(host="0.0.0.0", port=port)