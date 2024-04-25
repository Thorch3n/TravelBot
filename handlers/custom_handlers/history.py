import peewee as pw
import os
from typing import Union

# Подключение к базе данных SQLite
history_db_path: str = os.path.join(os.path.dirname(__file__), '../../database/history.db')
history_db: pw.SqliteDatabase = pw.SqliteDatabase(history_db_path)


# Определение модели
class History(pw.Model):
    """
    Модель для хранения истории команд пользователя.
    """
    user_id: pw.CharField = pw.CharField()
    command: pw.CharField = pw.CharField()
    timestamp: pw.DateTimeField = pw.DateTimeField(constraints=[pw.SQL('DEFAULT CURRENT_TIMESTAMP')])

    class Meta:
        database: pw.Database = history_db


def registrate(bot):
    """
    Функция-регистратор команд для бота.

    Args:
        bot: Экземпляр бота для регистрации команд.
    """
    @bot.message_handler(commands=['history'])
    def start(message):
        """
        Обработчик команды '/history'. Выводит историю команд пользователя.

        Args:
            message: Объект сообщения от пользователя.
        """
        with history_db:
            user_id: int = message.from_user.id
            command: str = message.text
            add_to_history(user_id, command)
            user_history: pw.SelectQuery = History.select().where(History.user_id == str(user_id)).order_by(History.timestamp)
            if user_history:
                commands_list: str = "\n".join([entry.command for entry in user_history])
                bot.reply_to(message, f"Ваша история команд:\n{commands_list}")
            else:
                bot.reply_to(message, "У вас нет сохраненных команд в истории.")

    def add_to_history(user_id: Union[str, int], command: str) -> None:
        """
        Добавляет запись в историю команд пользователя.

        Args:
            user_id: Идентификатор пользователя.
            command: Текст выполненной команды.
        """
        # Проверяем количество записей для данного пользователя
        count: int = History.select().where(History.user_id == str(user_id)).count()
        # Если записей больше или равно 10, удаляем самую старую запись
        if count >= 10:
            oldest_record: pw.Model = History.select().where(History.user_id == str(user_id)).order_by(
                History.timestamp.asc()).first()
            if oldest_record:
                oldest_record.delete_instance()

        # Добавляем новую запись в историю
        History.create(user_id=str(user_id), command=command)
