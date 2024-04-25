import os
from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv('keys.env'))

BOT_TOKEN = os.getenv('BOT_TOKEN')
RAPID_API_KEY = os.getenv('RAPID_API_KEY')
AVIASALES_API_KEY = os.getenv('AVIASALES_API_KEY')
DEFAULT_COMMANDS = (
    ('start', 'Запустить бота'),
    ('help', 'Вывести справку')
)
