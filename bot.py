"""
==============================================
  TELEGRAM AI BOT - KHÔNG CẦN TAG TRONG GROUP
==============================================
- Trong group: chỉ cần /hoi câu hỏi
- Trong chat riêng: nhắn thẳng
==============================================
"""

import os
import re
import time
import requests
import urllib.parse
import logging
from io import BytesIO
from collections import defaultdict
from pathlib import Path
from datetime import datetime

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

if not OPENROUTER_API_KEY:
    print("⚠️ Chưa có OPENROUTER_API_KEY trong file .env")

# ==================== CẤU HÌNH ====================
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "openrouter/free"  # Auto router

# ==================== IMPORT TELEGRAM ====================
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== LƯU TRỮ ====================
chat_histories = defaultdict(list)
bot_username = ""

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
            # Thêm kiểm tra an toàn
            if result and 'choices' in result and len(result['choices']) > 0:
                reply = result['choices'][0].get('message', {}).get('content', None)
                if reply:
                    return reply.strip()
                else:
                    return "⚠️ AI trả lời rỗng, vui lòng thử lại!"
            else:
                return "⚠️ Response không hợp lệ từ AI!"
        else:
            error = response.json().get('error', {}).get('message', 'Lỗi không xác định')
            return f"⚠️ Lỗi API: {error}"
            
    except requests.exceptions.Timeout:
        return "⚠️ Quá thời gian chờ, vui lòng thử lại!"
    except Exception as e:
        logger.error(f"Lỗi AI: {e}")
        return f"⚠️ Lỗi: {str(e)[:100]}"

# ==================== TẠO ẢNH ====================
def generate_image(prompt: str) -> bytes:
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()

# ==================== LỆNH /HOI ====================
async def cmd_hoi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /hoi - hỏi AI (trong group không cần tag)"""
    # Lấy nội dung sau lệnh /hoi
    args = context.args
    if not args:
        await update.message.reply_text(
            "💬 *Cách dùng:* `/hoi câu hỏi của bạn`\n"
            "Ví dụ: `/hoi 1+1 bằng mấy?`",
            parse_mode='Markdown'
        )
        return
    
    question = " ".join(args)
    
    # Gửi trạng thái đang nhập
    await update.message.chat.send_action(action="typing")
    
    try:
        chat_id = update.effective_chat.id
        reply = ask_ai(chat_id, question)
        
        # Lưu lịch sử
        chat_histories[chat_id].append(f"User: {question}")
        chat_histories[chat_id].append(f"Bot: {reply}")
        
        if len(chat_histories[chat_id]) > 30:
            chat_histories[chat_id] = chat_histories[chat_id][-30:]
        
        await update.message.reply_text(reply)
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi: {str(e)[:100]}")

# ==================== LỆNH /VE (TẠO ẢNH) ====================
async def cmd_ve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /ve - tạo ảnh"""
    args = context.args
    if not args:
        await update.message.reply_text(
            "🎨 *Cách dùng:* `/ve mô tả ảnh`\n"
            "Ví dụ: `/ve con mèo đang ngủ`",
            parse_mode='Markdown'
        )
        return
    
    prompt = " ".join(args)
    
    await update.message.chat.send_action(action="upload_photo")
    try:
        img_bytes = generate_image(prompt)
        await update.message.reply_photo(
            photo=BytesIO(img_bytes),
            caption=f'🎨 *"{prompt[:50]}"*',
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi tạo ảnh: {e}")

# ==================== LỆNH /RESET ====================
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_histories[chat_id] = []
    await update.message.reply_text("🗑️ Đã xóa lịch sử trò chuyện!")

# ==================== LỆNH /START ====================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot AI - Miễn Phí 100%*\n\n"
        "✨ *Tính năng:*\n"
        "• 💬 Hỏi đáp thông minh\n"
        "• 🎨 Tạo ảnh AI\n"
        "• 🔄 Nhớ lịch sử chat\n\n"
        "📌 *Cách dùng:*\n"
        "• `/hoi câu hỏi` - Hỏi AI\n"
        "• `/ve mô tả` - Tạo ảnh\n"
        "• `/reset` - Xóa lịch sử\n\n"
        "💡 *Ví dụ:*\n"
        "• `/hoi 1+1 bằng mấy?`\n"
        "• `/ve con mèo dễ thương`\n\n"
        "✅ *Dùng được trong group (không cần tag bot)*",
        parse_mode='Markdown'
    )

# ==================== XỬ LÝ TIN NHẮN THƯỜNG (CHAT RIÊNG) ====================
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý tin nhắn thường trong chat riêng (không cần lệnh)"""
    # Chỉ xử lý trong chat riêng, không xử lý trong group
    if update.effective_chat.type != "private":
        return
    
    user_text = update.message.text.strip()
    if not user_text:
        return
    
    # Xử lý vẽ ảnh (trong chat riêng)
    if user_text.lower().startswith('vẽ '):
        prompt = user_text[3:].strip()
        if prompt:
            await update.message.chat.send_action(action="upload_photo")
            try:
                img_bytes = generate_image(prompt)
                await update.message.reply_photo(
                    photo=BytesIO(img_bytes),
                    caption=f'🎨 *{prompt[:50]}*',
                    parse_mode='Markdown'
                )
            except Exception as e:
                await update.message.reply_text(f"⚠️ Lỗi: {e}")
        return
    
    # Chat AI bình thường
    await update.message.chat.send_action(action="typing")
    
    try:
        chat_id = update.effective_chat.id
        reply = ask_ai(chat_id, user_text)
        
        chat_histories[chat_id].append(f"User: {user_text}")
        chat_histories[chat_id].append(f"Bot: {reply}")
        
        if len(chat_histories[chat_id]) > 30:
            chat_histories[chat_id] = chat_histories[chat_id][-30:]
        
        await update.message.reply_text(reply)
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi: {str(e)[:100]}")

# ==================== KHỞI TẠO ====================
async def post_init(app):
    global bot_username
    me = await app.bot.get_me()
    bot_username = me.username or ""
    print(f"\n{'='*50}")
    print(f"✅ Bot @{bot_username} đã khởi động!")
    print(f"📝 Trong group: dùng /hoi câu hỏi (không cần tag)")
    print(f"💬 Trong chat riêng: nhắn tin trực tiếp")
    print(f"🎨 Tạo ảnh: /ve mô tả")
    print(f"{'='*50}\n")

# ==================== MAIN ====================
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("hoi", cmd_hoi))
    app.add_handler(CommandHandler("ve", cmd_ve))
    app.add_handler(CommandHandler("reset", cmd_reset))
    
    # Message handler cho chat riêng (tin nhắn thường không cần lệnh)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
        handle_private_message
    ))
    
    print("🚀 Bot đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()