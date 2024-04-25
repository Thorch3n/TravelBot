import re
import requests as rq
import peewee as pw
import os
from config_data import config
from telebot import TeleBot, types
from typing import Optional

# Путь к базе данных cities.db
db_path = os.path.join(os.path.dirname(__file__), '../../database/cities.db')
# Инициализация объекта базы данных
db = pw.SqliteDatabase(db_path)

# Путь к базе данных airports.db
airports_db_path = os.path.join(os.path.dirname(__file__), '../../database/airports.db')
# Инициализация объекта базы данных для аэропортов
airports_db = pw.SqliteDatabase(airports_db_path)

# Путь к базе данных history.db
history_db_path = os.path.join(os.path.dirname(__file__), '../../database/history.db')
# Инициализация объекта базы данных для истории команд пользователя
history_db = pw.SqliteDatabase(history_db_path)

# Ключ API для Aviasales
aviasales_token = config.AVIASALES_API_KEY


class BaseModel(pw.Model):
    class Meta:
        database = db


class City(BaseModel):
    # Модель для хранения информации о городах
    name = pw.CharField()
    ru = pw.CharField()
    code = pw.CharField(unique=True)
    lon = pw.FloatField()
    lat = pw.FloatField()


class Airports(BaseModel):
    # Модель для хранения информации об аэропортах
    name = pw.CharField()
    code = pw.CharField(unique=True)

    class Meta:
        database = airports_db


class History(BaseModel):
    # Модель для хранения истории команд пользователя
    user_id = pw.CharField()
    command = pw.CharField()
    timestamp = pw.DateTimeField(constraints=[pw.SQL('DEFAULT CURRENT_TIMESTAMP')])

    class Meta:
        database = history_db


def registrate(bot: TeleBot) -> None:
    """Регистрация обработчиков команд для бота.

    Args:
        bot (TeleBot): Объект бота.
    """

    @bot.message_handler(commands=['low'])
    def start(message: types.Message) -> None:
        """Обработчик команды /low.

        Args:
            message (types.Message): Объект сообщения от пользователя.
        """
        with history_db:
            user_id: str = str(message.from_user.id)
            command: str = message.text
            add_to_history(user_id, command)
            bot.send_message(message.chat.id, 'Введите название города отправления на русском языке')
            bot.register_next_step_handler(message, process_second_city)

    def add_to_history(user_id: str, command: str) -> None:
        """Добавление записи в историю команд пользователя.

        Args:
            user_id (str): Идентификатор пользователя.
            command (str): Текст команды.
        """
        # Проверяем количество записей для данного пользователя
        count: int = History.select().where(History.user_id == str(user_id)).count()
        # Если записей больше или равно 10, удаляем самую старую запись
        if count >= 10:
            oldest_record: History = History.select().where(History.user_id == str(user_id)).order_by(
                History.timestamp.asc()).first()
            oldest_record.delete_instance()

        # Добавляем новую запись в историю
        History.create(user_id=str(user_id), command=command)

    def process_second_city(message: types.Message, departure_city: Optional[City] = None) -> None:
        """Обработка второго этапа запроса - ввода города прибытия.

        Args:
            message (types.Message): Объект сообщения от пользователя.
            departure_city (Optional[City]): Объект города отправления (если уже введен).
        """
        try:
            db.connect(reuse_if_open=True)  # Подключение к базе данны
            departure_city = City.get_or_none(ru=message.text)
            if not departure_city:
                bot.send_message(message.chat.id, 'Город не найден в базе данных, либо город введен не корректно. '
                                                      'Пожалуйста, введите город отправления.')
                bot.register_next_step_handler(message, process_second_city)
                return

            bot.send_message(message.chat.id, 'Введите название города прибытия на русском языке')
            bot.register_next_step_handler(message, process_date_departure, departure_city=departure_city)
        except Exception as e:
            bot.reply_to(message, 'Что-то пошло не так, прошу повторите запрос')
        finally:
            db.close()

    def process_date_departure(message: types.Message, departure_city: City, arrival_city: Optional[City] = None) -> None:
        """Обработка третьего этапа запроса - ввода даты отправления.

        Args:
            message (types.Message): Объект сообщения от пользователя.
            departure_city (City): Объект города отправления.
            arrival_city (Optional[City]): Объект города прибытия (если уже введен).
        """
        try:
            db.connect(reuse_if_open=True)  # Подключение к базе данных
            arrival_city = City.get_or_none(ru=message.text)
            if not arrival_city:
                bot.send_message(message.chat.id, 'Город не найден в базе данных, либо город введен не корректно. '
                                                      'Пожалуйста, введите город прибытия.')
                bot.register_next_step_handler(message, process_date_departure, departure_city=departure_city)
                return

            bot.send_message(message.chat.id, 'Введите год и месяц отправления в формате YYYY-MM (Например 2024-02)')
            bot.register_next_step_handler(message, final_date, departure_city=departure_city, arrival_city=arrival_city)
        except Exception as e:
            bot.reply_to(message, 'Что-то пошло не так, прошу повторите запрос')
        finally:
            db.close()

    def final_date(message: types.Message, departure_city: City, arrival_city: City, date_info: Optional[str] = None) -> None:
        """Обработка финального этапа запроса - ввода даты отправления.

        Args:
            message (types.Message): Объект сообщения от пользователя.
            departure_city (City): Объект города отправления.
            arrival_city (City): Объект города прибытия.
            date_info (Optional[str]): Дата отправления (если уже введена).
        """
        try:
            db.connect(reuse_if_open=True)  # Подключение к базе данных

            date_info = message.text
            if not validate_date_format(date_info):
                bot.send_message(message.chat.id, 'Некорректный формат даты. Пожалуйста, введите в формате YYYY-MM.')
                bot.register_next_step_handler(message, final_date, departure_city=departure_city,
                                               arrival_city=arrival_city)
                return

            final(message, departure_city, arrival_city, date_info)
        except Exception as e:
            bot.reply_to(message, 'Что-то пошло не так, прошу повторите запрос')
        finally:
            db.close()

    def validate_date_format(date_text: str) -> bool:
        """Проверка формата даты.

        Args:
            date_text (str): Текст с датой.

        Returns:
            bool: Результат проверки.
        """
        pattern: re.Pattern = re.compile(r'^\d{4}-\d{2}$')
        return bool(pattern.match(date_text))

    def final(message: types.Message, origin_city: City, destination_city: City, departure_at: str) -> None:
        """Финальный этап запроса - обработка данных и отправка результатов.

        Args:
            message (types.Message): Объект сообщения от пользователя.
            origin_city (City): Объект города отправления.
            destination_city (City): Объект города прибытия.
            departure_at (str): Дата отправления.
        """
        try:
            db.connect(reuse_if_open=True)  # Подключение к базе данных

            airports_db.connect(reuse_if_open=True)

            origin_ru: str = origin_city.ru
            destination_ru: str = destination_city.ru
            origin_code: str = origin_city.code
            destination_code: str = destination_city.code

            aviasales_url: str = f'https://api.travelpayouts.com/aviasales/v3/prices_for_dates?origin={origin_code}&destination={destination_code}&departure_at={departure_at}&sorting=price&direct=false&cy=rub&limit=50&page=1&token={aviasales_token}'

            response: rq.Response = rq.get(aviasales_url)

            if response.status_code == 200:
                data: list = response.json().get('data', [])
                if not data:
                    bot.send_message(message.chat.id, 'По вашему запросу нет доступных рейсов')
                else:
                    for flight in data:
                        formated_date: str = flight['departure_at'][:19]
                        airports_origin_code: str = flight['origin_airport']
                        airports_destination_code: str = flight['destination_airport']
                        origin_airport_name: Optional[Airports] = Airports.get_or_none(code=airports_origin_code)
                        destination_airport_name: Optional[Airports] = Airports.get_or_none(code=airports_destination_code)
                        flight_info: str = (
                            f'Город отправления: {origin_ru}\n'
                            f'Город прибытия: {destination_ru}\n'
                            f'Дата отправления: {formated_date}\n'
                            f'Стоимость: {flight["price"]}\n'
                            f'Аэропорт отправления: {origin_airport_name.name}\n'
                            f'Аэропорт прибытия: {destination_airport_name.name}\n'
                            f'Ссылка: aviasales.ru{flight["link"]}'
                        )
                        bot.send_message(message.chat.id, flight_info)
            else:
                bot.send_message(message.chat.id, f'Ошибка при выполнении запроса: {response.status_code}')
        except Exception as e:
            bot.reply_to(message, 'Что-то пошло не так, прошу повторите запрос')
        finally:
            db.close()
