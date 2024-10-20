import random
import requests
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
import os

# Список активов для выбора
assets = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT",
    "DOTUSDT", "LINKUSDT", "LTCUSDT", "BCHUSDT", "XLMUSDT"
]

# Начальный капитал
initial_capital = 100
capital = initial_capital
portfolio = {}

# Параметры стратегии
num_parts = 10
part_size = capital / num_parts
buy_threshold = 0.05  # 5%
sell_threshold = 0.05  # 5%

# Метод для отображения текущей цены выбранного актива
def get_current_price(selected_asset):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={selected_asset}"
    response = requests.get(url)
    data = response.json()
    current_price = float(data['price'])
    return current_price

# Метод для стратегии торговли с использованием сеточной стратегии
async def grid_trading_strategy(update: Update, context: CallbackContext, selected_asset):
    keyboard = [[KeyboardButton("Остановить мониторинг")]]    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    current_price = get_current_price(selected_asset)
    message = f"Цена на старте мониторинга {selected_asset}: {current_price} USD"
    sent_message = await context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=reply_markup)
    
    buy_price = current_price * (1 - buy_threshold)
    message = f"Цена покупки {selected_asset}: {current_price} USD"
    sent_message = await context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=reply_markup)
    
    sell_price = buy_price * (1 + sell_threshold)
    message = f"Цена проджи {selected_asset}: {sell_price} USD"
    sent_message = await context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=reply_markup)
    
    global capital, portfolio
    funds_per_grid = capital / num_parts

    message_ids = []
    while not context.user_data.get('stop_monitoring', False):
        current_price = get_current_price(selected_asset)
        message = f"Текущая цена {selected_asset}: {current_price} USD"

        # Удаление предыдущих сообщений
        for message_id in message_ids:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
            except Exception as e:
                print(f"Ошибка при удалении сообщения: {e}")

        # Отправка нового сообщения с текущей ценой
        sent_message = await context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=reply_markup)
        message_ids.append(sent_message.message_id)


        
        if current_price <= buy_price and capital >= part_size:
            amount = part_size / current_price
            capital -= part_size
            portfolio[selected_asset] = {'amount': amount, 'price': current_price}
            buy_message = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Покупка выполнена: {amount:.8f} {selected_asset} по цене {current_price:.2f} USD")
            message_ids.append(buy_message.message_id)
        elif selected_asset in portfolio and current_price >= sell_price:
            amount = portfolio[selected_asset]['amount']
            capital += amount * current_price
            del portfolio[selected_asset]
            sell_message = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Продажа выполнена: {amount:.8f} {selected_asset} по цене {current_price:.2f} USD")
            message_ids.append(sell_message.message_id)

        account_status_message = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Состояние счета: {capital:.2f} USD")
        message_ids.append(account_status_message.message_id)

        # Ждем 60 секунд перед следующей проверкой
        for _ in range(60):
            if context.user_data.get('stop_monitoring', False):
                break
            await asyncio.sleep(1)


# Метод для отображения результатов
async def show_account_status(update: Update, context: CallbackContext):
    global capital, portfolio
    portfolio_str = "Текущий портфель:\n"
    if not(portfolio):
        portfolio_str += "Портфель пуст\n"
    else:
        for asset, info in portfolio.items():
            portfolio_str += f"{asset}: {info['amount']} шт. по цене {info['price']} USD\n"
    portfolio_str += f"Остаток капитала: {capital:.2f} USD"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=portfolio_str)

# Метод для взаимодействия через Телеграм
async def telegram_interaction(update: Update, context: CallbackContext):
    message = "Привет! Я торговый бот. Выберите действие:"
    keyboard = [
        [KeyboardButton("Работа с активами")],
        [KeyboardButton("Проверка текущего баланса")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=reply_markup)

# Метод для обработки выбора актива через кнопки
async def handle_message(update: Update, context: CallbackContext):
    text = update.message.text

    if text == "Работа с активами":
        message = "Выберите актив для торговли:"
        keyboard = [[KeyboardButton(asset)] for asset in assets]
        keyboard.append([KeyboardButton("Назад")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=reply_markup)
    elif text == "Проверка текущего баланса":
        await show_account_status(update, context)
    elif text == "Назад":
        await telegram_interaction(update, context)
    elif text == "Остановить мониторинг":
        context.user_data['stop_monitoring'] = True
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Мониторинг остановлен.")
        await telegram_interaction(update, context)
    else:
        selected_asset = text
        context.user_data['selected_asset'] = selected_asset
        context.user_data['stop_monitoring'] = False
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Выбран актив: {selected_asset}")

        # Запуск торговли
        asyncio.create_task(grid_trading_strategy(update, context, selected_asset))

# Загружаем токен телеграм-бота из .env файла
load_dotenv()
token = os.getenv('TELEGRAM_TOKEN')

# Создаем ApplicationBuilder и регистрируем обработчики команд
application = ApplicationBuilder().token(token).build()

application.add_handler(CommandHandler("start", telegram_interaction))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CommandHandler("status", show_account_status))

# Запускаем бот
if __name__ == '__main__':
    application.run_polling()
