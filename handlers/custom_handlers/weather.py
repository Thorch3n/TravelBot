import requests as rq
import peewee as pw
import os
from config_data import config
from typing import Union

city: str = ''
db_path: str = os.path.join(os.path.dirname(__file__), '../../database/cities.db')
db: pw.SqliteDatabase = pw.SqliteDatabase(db_path)

history_db_path: str = os.path.join(os.path.dirname(__file__), '../../database/history.db')
history_db: pw.SqliteDatabase = pw.SqliteDatabase(history_db_path)

rapid_token: str = config.RAPID_API_KEY


class BaseModel(pw.Model):
    """
    Базовая модель для наследования другими моделями Peewee.
    """
    class Meta:
        database: pw.Database = db


class City(BaseModel):
    """
    Модель для хранения информации о городах.
    """
    name: pw.CharField = pw.CharField()
    ru: pw.CharField = pw.CharField()
    code: pw.CharField = pw.CharField(unique=True)
    lon: pw.FloatField = pw.FloatField()
    lat: pw.FloatField = pw.FloatField()


class History(BaseModel):
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
    @bot.message_handler(commands=['weather'])
    def start(message):
        """
        Обработчик команды '/weather'. Инициализирует процесс запроса информации о погоде у пользователя.

        Args:
            message: Объект сообщения от пользователя.
        """
        with history_db:
            user_id: int = message.from_user.id
            command: str = message.text
            add_to_history(user_id, command)
            bot.send_message(message.chat.id,
                             'Введите название города на русском языке, в котором необходимо узнать погоду')
            bot.register_next_step_handler(message, final)

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

    def final(message):
        """
        Завершающий обработчик запроса информации о погоде. Выполняет запрос к API и отправляет результат пользователю.

        Args:
            message: Объект сообщения от пользователя.
        """
        global city
        city = message.text
        data: pw.Model = City.get_or_none(City.ru == city)

        if data:
            city_name: str = data.ru
            city_lat: float = data.lat
            city_lon: float = data.lon

            url: str = "https://ai-weather-by-meteosource.p.rapidapi.com/daily"

            querystring: dict = {"lat": city_lat, "lon": city_lon, "timezone": "auto", "language": "en", "units": "metric"}

            headers: dict = {
                "X-RapidAPI-Key": rapid_token,
                "X-RapidAPI-Host": "ai-weather-by-meteosource.p.rapidapi.com"
            }

            try:
                response: rq.Response = rq.get(url, headers=headers, params=querystring)

                final_data: dict = response.json()
                for day_data in final_data['daily']['data']:
                    bot.send_message(message.chat.id, f'Город: {city_name}\n'
                                                      f'Дата: {day_data["day"]}\n'
                                                      f'Температура воздуха: {day_data["temperature"]} °C')
            except rq.RequestException as e:
                bot.send_message(message.chat.id, f'Произошла ошибка при запросе погоды: {str(e)}')
        else:
            bot.send_message(message.chat.id, 'Город не найден в базе данных, либо введен некорректно. Пожалуйста, '
                                              'повторите ввод города.')
            bot.register_next_step_handler(message, final)
