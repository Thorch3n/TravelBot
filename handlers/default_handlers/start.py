import os
import peewee as pw
from typing import Optional
from telebot import TeleBot, types

# Путь к базе данных history.db
history_db_path = os.path.join(os.path.dirname(__file__), '../../database/history.db')
# Инициализация объекта базы данных
history_db = pw.SqliteDatabase(history_db_path)


class History(pw.Model):
    # Модель для хранения истории команд пользователя
    user_id = pw.CharField()
    command = pw.CharField()
    timestamp = pw.DateTimeField(constraints=[pw.SQL('DEFAULT CURRENT_TIMESTAMP')])

    class Meta:
        # Указываем, что модель использует базу данных history_db
        database = history_db


def registrate(bot: TeleBot) -> None:
    """Регистрация обработчиков команд для бота.

    Args:
        bot (TeleBot): Объект бота.
    """

    @bot.message_handler(commands=['start'])
    def start(message: types.Message) -> None:
        """Обработчик команды /start.

        Args:
            message (types.Message): Объект сообщения от пользователя.
        """
        with history_db:
            user_id: str = str(message.from_user.id)
            command: str = message.text
            add_to_history(user_id, command)
            bot.send_message(message.chat.id,
                             text='Привет, {}! Я бот помогающий найти авиабилеты и узнать погоду в нужном '
                                  'Вам городе. Напишите команду /help для того, чтобы узнать доступные команды!'.format(message.from_user.first_name))

    def add_to_history(user_id: str, command: str) -> None:
        """Добавление записи в историю команд пользователя.

        Args:
            user_id (str): Идентификатор пользователя.
            command (str): Текст команды.
        """
        # Проверяем количество записей для данного пользователя
        count: int = History.select().where(History.user_id == user_id).count()
        # Если записей больше или равно 10, удаляем самую старую запись
        if count >= 10:
            oldest_record: History = History.select().where(History.user_id == user_id).order_by(
                History.timestamp.asc()).first()
            oldest_record.delete_instance()

        # Добавляем новую запись в историю
        History.create(user_id=user_id, command=command)
