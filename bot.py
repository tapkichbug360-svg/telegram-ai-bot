"""
==============================================
  TELEGRAM AI BOT - RENDER WEBHOOK FIXED
==============================================
"""

import os
import sys
import time
import json
import requests
import urllib.parse
import logging
from io import BytesIO
from collections import defaultdict
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes
import asyncio

# ==================== ĐỌC BIẾN MÔI TRƯỜNG ====================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

if not TELEGRAM_TOKEN:
    print("❌ Thiếu TELEGRAM_BOT_TOKEN")
    sys.exit(1)

print(f"✅ Bot token: {TELEGRAM_TOKEN[:20]}...")
if OPENROUTER_API_KEY:
    print(f"✅ OpenRouter key: {OPENROUTER_API_KEY[:20]}...")

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

# ==================== XỬ LÝ UPDATE (SYNC) ====================
def handle_update_sync(update_data):
    """Xử lý update đồng bộ - tránh lỗi event loop"""
    try:
        update = Update.de_json(update_data, bot)
        
        if not update or not update.message:
            return
        
        chat_id = update.message.chat.id
        user_text = update.message.text.strip() if update.message.text else ""
        
        if not user_text:
            return
        
        # Lệnh /hoi
        if user_text.startswith('/hoi'):
            parts = user_text.split(maxsplit=1)
            if len(parts) < 2:
                bot.send_message(chat_id=chat_id, text="💬 Cách dùng: `/hoi câu hỏi`", parse_mode='Markdown')
                return
            question = parts[1]
            
            reply = ask_ai(chat_id, question)
            
            chat_histories[chat_id].append(f"User: {question}")
            chat_histories[chat_id].append(f"Bot: {reply}")
            
            if len(chat_histories[chat_id]) > 30:
                chat_histories[chat_id] = chat_histories[chat_id][-30:]
            
            bot.send_message(chat_id=chat_id, text=reply)
            return
        
        # Lệnh /ve
        if user_text.startswith('/ve'):
            parts = user_text.split(maxsplit=1)
            if len(parts) < 2:
                bot.send_message(chat_id=chat_id, text="🎨 Cách dùng: `/ve mô tả ảnh`", parse_mode='Markdown')
                return
            prompt = parts[1]
            
            try:
                img_bytes = generate_image(prompt)
                bot.send_photo(
                    chat_id=chat_id,
                    photo=img_bytes,
                    caption=f'🎨 *{prompt[:50]}*',
                    parse_mode='Markdown'
                )
            except Exception as e:
                bot.send_message(chat_id=chat_id, text=f"⚠️ Lỗi tạo ảnh: {e}")
            return
        
        # Lệnh /reset
        if user_text.startswith('/reset'):
            chat_histories[chat_id] = []
            bot.send_message(chat_id=chat_id, text="🗑️ Đã xóa lịch sử!")
            return
        
        # Lệnh /start
        if user_text.startswith('/start'):
            bot.send_message(
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
            
    except Exception as e:
        logger.error(f"Xử lý update lỗi: {e}")

# ==================== FLASK WEBHOOK ====================
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Bot is running!", 200

@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    try:
        update_data = request.get_json(force=True)
        # Xử lý đồng bộ, không dùng asyncio
        handle_update_sync(update_data)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

# ==================== KHỞI ĐỘNG ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"\n{'='*50}")
    print(f"🚀 Bot đang chạy Webhook mode!")
    print(f"📱 Telegram Bot: @Dengoancualam05_bot")
    print(f"{'='*50}\n")
    
    app.run(host="0.0.0.0", port=port)