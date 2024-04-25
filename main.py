import telebot
from config_data import config
from handlers.default_handlers import start, help
from handlers.custom_handlers import low, high, custom, history, weather

bot = telebot.TeleBot(config.BOT_TOKEN)

start.registrate(bot)
help.registrate(bot)
low.registrate(bot)
high.registrate(bot)
custom.registrate(bot)
weather.registrate(bot)
history.registrate(bot)

if __name__ == '__main__':
    bot.infinity_polling()
