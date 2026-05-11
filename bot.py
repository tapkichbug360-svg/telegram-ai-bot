import os
import sys
import json
import requests
import urllib.parse
import logging
from io import BytesIO
from collections import defaultdict
from flask import Flask, request, jsonify

# === ĐỌC BIẾN MÔI TRƯỜNG ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

if not TELEGRAM_TOKEN:
    print("❌ Thiếu TELEGRAM_BOT_TOKEN")
    sys.exit(1)

print(f"✅ Token: {TELEGRAM_TOKEN[:20]}...")

# === CẤU HÌNH ===
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
chat_histories = defaultdict(list)

# === LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === GỬI TIN NHẮN QUA TELEGRAM API ===
def send_message(chat_id, text):
    """Gửi tin nhắn qua Telegram API trực tiếp"""
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        response = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=10)
        if response.status_code != 200:
            logger.error(f"Gửi tin nhắn lỗi: {response.text}")
        return response.ok
    except Exception as e:
        logger.error(f"Lỗi gửi tin nhắn: {e}")
        return False

def send_photo(chat_id, photo_bytes, caption=""):
    """Gửi ảnh qua Telegram API trực tiếp"""
    try:
        files = {"photo": ("image.jpg", photo_bytes, "image/jpeg")}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
        response = requests.post(f"{TELEGRAM_API_URL}/sendPhoto", data=data, files=files, timeout=30)
        return response.ok
    except Exception as e:
        logger.error(f"Lỗi gửi ảnh: {e}")
        return False

# === HÀM GỌI AI ===
def ask_ai(chat_id, prompt):
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
            "model": "openrouter/free",
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

# === TẠO ẢNH ===
def generate_image(prompt):
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()

# === FLASK WEBHOOK ===
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Bot is running!", 200

@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        logger.info(f"📨 Webhook received")
        
        if 'message' not in data:
            return jsonify({"status": "no message"}), 200
        
        msg = data['message']
        chat_id = msg['chat']['id']
        
        if 'text' not in msg:
            return jsonify({"status": "no text"}), 200
        
        text = msg['text'].strip()
        logger.info(f"💬 Chat {chat_id}: {text}")
        
        # Lệnh /hoi
        if text.startswith('/hoi'):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                send_message(chat_id, "💬 Dùng: `/hoi câu hỏi`")
                return jsonify({"status": "ok"}), 200
            question = parts[1]
            
            reply = ask_ai(chat_id, question)
            chat_histories[chat_id].append(f"User: {question}")
            chat_histories[chat_id].append(f"Bot: {reply}")
            
            if len(chat_histories[chat_id]) > 30:
                chat_histories[chat_id] = chat_histories[chat_id][-30:]
            
            send_message(chat_id, reply)
            return jsonify({"status": "ok"}), 200
        
        # Lệnh /ve
        if text.startswith('/ve'):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                send_message(chat_id, "🎨 Dùng: `/ve mô tả ảnh`")
                return jsonify({"status": "ok"}), 200
            prompt = parts[1]
            
            try:
                img_bytes = generate_image(prompt)
                send_photo(chat_id, img_bytes, f'🎨 {prompt[:50]}')
            except Exception as e:
                send_message(chat_id, f"⚠️ Lỗi tạo ảnh: {e}")
            return jsonify({"status": "ok"}), 200
        
        # Lệnh /reset
        if text.startswith('/reset'):
            chat_histories[chat_id] = []
            send_message(chat_id, "🗑️ Đã xóa lịch sử trò chuyện!")
            return jsonify({"status": "ok"}), 200
        
        # Lệnh /start
        if text.startswith('/start'):
            send_message(chat_id, "🤖 *Bot AI - Miễn Phí 100%*\n\n✨ *Tính năng:*\n• `/hoi câu hỏi` - Hỏi AI\n• `/ve mô tả` - Tạo ảnh\n• `/reset` - Xóa lịch sử\n\n💡 Ví dụ: `/hoi 1+1 bằng mấy?`")
            return jsonify({"status": "ok"}), 200
        
        # Tin nhắn thường - chat tự do (chỉ trong chat riêng)
        if msg['chat']['type'] == 'private':
            reply = ask_ai(chat_id, text)
            chat_histories[chat_id].append(f"User: {text}")
            chat_histories[chat_id].append(f"Bot: {reply}")
            if len(chat_histories[chat_id]) > 30:
                chat_histories[chat_id] = chat_histories[chat_id][-30:]
            send_message(chat_id, reply)
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"❌ Lỗi webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 200

# === MAIN ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"\n{'='*50}")
    print(f"🚀 Bot đang chạy Webhook mode!")
    print(f"📱 Telegram Bot: @Dengoancualam05_bot")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port)