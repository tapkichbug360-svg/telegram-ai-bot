import os
import sys
import json
import requests
import urllib.parse
import logging
from io import BytesIO
from collections import defaultdict
from flask import Flask, request, jsonify
from telegram import Bot, Update

# === ĐỌC BIẾN MÔI TRƯỜNG ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

if not TELEGRAM_TOKEN:
    print("❌ Thiếu TELEGRAM_BOT_TOKEN")
    sys.exit(1)

print(f"✅ Token: {TELEGRAM_TOKEN[:20]}...")
if OPENROUTER_API_KEY:
    print(f"✅ OpenRouter: {OPENROUTER_API_KEY[:20]}...")

# === CẤU HÌNH ===
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "openrouter/free"
chat_histories = defaultdict(list)
bot = Bot(token=TELEGRAM_TOKEN)

# === LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === HÀM GỌI AI ===
def ask_ai(chat_id, prompt):
    try:
        history = chat_histories.get(chat_id, [])
        messages = [{"role": "system", "content": "Bạn là trợ lý AI. Trả lời ngắn gọn bằng tiếng Việt."}]
        
        for msg in history[-10:]:
            if msg.startswith("User:"):
                messages.append({"role": "user", "content": msg[5:]})
            elif msg.startswith("Bot:"):
                messages.append({"role": "assistant", "content": msg[4:]})
        
        messages.append({"role": "user", "content": prompt})
        
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        data = {"model": MODEL_NAME, "messages": messages, "temperature": 0.7, "max_tokens": 1000}
        
        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        return f"⚠️ Lỗi API: {response.status_code}"
    except Exception as e:
        return f"⚠️ Lỗi: {str(e)[:100]}"

# === TẠO ẢNH ===
def generate_image(prompt):
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

# === FLASK WEBHOOK ===
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Bot is running!", 200

@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        logger.info(f"📨 Webhook received: {json.dumps(data)[:200]}")
        
        if 'message' not in data:
            return jsonify({"status": "no message"}), 200
        
        msg = data['message']
        chat_id = msg['chat']['id']
        
        # Xử lý text
        if 'text' in msg:
            text = msg['text'].strip()
            logger.info(f"💬 Chat {chat_id}: {text}")
            
            # Lệnh /hoi
            if text.startswith('/hoi'):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    bot.send_message(chat_id=chat_id, text="💬 Dùng: `/hoi câu hỏi`", parse_mode='Markdown')
                    return jsonify({"status": "ok"}), 200
                question = parts[1]
                reply = ask_ai(chat_id, question)
                chat_histories[chat_id].append(f"User: {question}")
                chat_histories[chat_id].append(f"Bot: {reply}")
                bot.send_message(chat_id=chat_id, text=reply)
                return jsonify({"status": "ok"}), 200
            
            # Lệnh /ve
            if text.startswith('/ve'):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    bot.send_message(chat_id=chat_id, text="🎨 Dùng: `/ve mô tả`", parse_mode='Markdown')
                    return jsonify({"status": "ok"}), 200
                prompt = parts[1]
                try:
                    img = generate_image(prompt)
                    bot.send_photo(chat_id=chat_id, photo=img, caption=f'🎨 {prompt[:50]}')
                except Exception as e:
                    bot.send_message(chat_id=chat_id, text=f"⚠️ Lỗi: {e}")
                return jsonify({"status": "ok"}), 200
            
            # Lệnh /reset
            if text.startswith('/reset'):
                chat_histories[chat_id] = []
                bot.send_message(chat_id=chat_id, text="🗑️ Đã xóa lịch sử!")
                return jsonify({"status": "ok"}), 200
            
            # Lệnh /start
            if text.startswith('/start'):
                bot.send_message(chat_id=chat_id, text="🤖 Bot AI Free!\n/hoi câu hỏi - Hỏi AI\n/ve mô tả - Tạo ảnh\n/reset - Xóa lịch sử")
                return jsonify({"status": "ok"}), 200
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"❌ Lỗi webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 200

# === MAIN ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)