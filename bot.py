import os
import logging
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= CONFIGURATION =================
# Укажите ваш токен Telegram-бота от BotFather
TELEGRAM_BOT_TOKEN = "ТВОЙ_ТОКЕН_БОТА"

# Ссылка от ngrok, которую вы скопировали (обязательно с /v1 на конце!)
NGROK_URL = "https://brownnose-deafening-relieving.ngrok-free.dev/v1"

# Имя модели в LM Studio (должно совпадать с API Model Identifier)
MODEL_NAME = "lumimaid-v0.2-8b"
# =================================================

# Инициализация клиента OpenAI для работы с LM Studio
client = OpenAI(
    base_url=NGROK_URL,
    api_key="not-needed"  # LM Studio не требует реальный ключ
)

# Системный промпт (базовый характер бота)
BASE_SYSTEM_PROMPT = (
    "Ты — виртуальный собеседник с живым характером. "
    "Общайся естественно, эмоционально, поддерживай разговор тепло и открыто."
)

FORMAT_INSTRUCTION = (
    "\n\nТРЕБОВАНИЯ К СТИЛЮ:\n"
    "1. Используй звездочки *для описания эмоций, мимики и жестов* (например, *улыбается*).\n"
    "2. Используй обычный текст для диалога.\n"
    "3. Пиши лаконично и по делу, избегай затянутых монологов."
)

# Словарь для хранения истории сообщений пользователей
user_histories = {}

def get_user_history(user_id: int):
    if user_id not in user_histories:
        user_histories[user_id] = [
            {"role": "system", "content": BASE_SYSTEM_PROMPT + FORMAT_INSTRUCTION}
        ]
    return user_histories[user_id]

# Обработчик команды /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = [
        {"role": "system", "content": BASE_SYSTEM_PROMPT + FORMAT_INSTRUCTION}
    ]
    
    keyboard = [
        [InlineKeyboardButton("🧹 Очистить память", callback_data="clear_memory")],
        [InlineKeyboardButton("🎭 Сменить режим", callback_data="change_mode")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "Привет! Я улыбнулась, игриво разминая пальцы на клавиатуре. "
        "Так рада, что ты пришел. Поговорим о чем-нибудь интересном?"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# Обработчик команды /clear и кнопки очистки
async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
        target = query.message
    else:
        user_id = update.effective_user.id
        target = update.message

    user_histories[user_id] = [
        {"role": "system", "content": BASE_SYSTEM_PROMPT + FORMAT_INSTRUCTION}
    ]
    
    text = "Я всё забыла... Начнём сначала? 🔥"
    if query:
        await target.edit_text(text)
    else:
        await target.reply_text(text)

# Обработчик кнопки смены режима
async def change_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    modes_text = (
        "Выбери стиль общения:\n\n"
        "• 🌸 *Романтика* — милый флирт, нежность и чувства.\n"
        "• 🔥 *Флирт* — заигрывания, интрига и подколы.\n"
        "• 💥 *Без цензуры (NSFW)* — максимальная страсть, секстинг и полная откровенность."
    )
    keyboard = [
        [InlineKeyboardButton("💥 Без цензуры (NSFW)", callback_data="set_nsfw")],
        [InlineKeyboardButton("🌸 Романтика", callback_data="set_romance")]
    ]
    await query.message.reply_text(modes_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def set_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text("Переключила режим. Никаких рамок... 😈")

# Обработка текстовых сообщений от пользователя
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    history = get_user_history(user_id)
    history.append({"role": "user", "content": user_text})

    # Ограничение истории, чтобы контекст не раздувался (храним последние 10 сообщений + системный промпт)
    if len(history) > 11:
        history = [history[0]] + history[-10:]
        user_histories[user_id] = history

    # Отправляем статус "печатает..." в Telegram, пока модель думает
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # Запрос к локальной модели через ngrok и LM Studio (с ограничением max_tokens)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=history,
            max_tokens=250,   # Ограничиваем длину ответа для скорости
            temperature=0.7   # Степень креативности
        )

        reply_text = response.choices[0].message.content

        # Добавляем ответ бота в историю
        history.append({"role": "assistant", "content": reply_text})

        await update.message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Ошибка при запросе к модели: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при обращении к локальной модели. Убедись, что LM Studio запущен, модель активна, а ссылка ngrok актуальна."
        )

def main():
    # Создаем приложение бота
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CallbackQueryHandler(clear_command, pattern="^clear_memory$"))
    app.add_handler(CallbackQueryHandler(change_mode_callback, pattern="^change_mode$"))
    app.add_handler(CallbackQueryHandler(set_mode_callback, pattern="^(set_nsfw|set_romance)$"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Бот запущен и ожидает сообщения...")
    app.run_polling()

if __name__ == '__main__':
    main()
