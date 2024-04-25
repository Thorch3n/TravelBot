from typing import Union, Optional

import re
import requests as rq
import peewee as pw
import os
from config_data import config
from telebot import TeleBot, types

# Пути к базам данных
db_path: str = os.path.join(os.path.dirname(__file__), '../../database/cities.db')
db: pw.SqliteDatabase = pw.SqliteDatabase(db_path)

airports_db_path: str = os.path.join(os.path.dirname(__file__), '../../database/airports.db')
airports_db: pw.SqliteDatabase = pw.SqliteDatabase(airports_db_path)

history_db_path: str = os.path.join(os.path.dirname(__file__), '../../database/history.db')
history_db: pw.SqliteDatabase = pw.SqliteDatabase(history_db_path)

aviasales_token: str = config.AVIASALES_API_KEY


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


class Airports(BaseModel):
    """
    Модель для хранения информации об аэропортах.
    """
    name: pw.CharField = pw.CharField()
    code: pw.CharField = pw.CharField(unique=True)

    class Meta:
        database: pw.Database = airports_db


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

    @bot.message_handler(commands=['custom'])
    def start(message):
        """
        Обработчик команды '/custom'. Инициализирует процесс запроса информации у пользователя.

        Args:
            message: Объект сообщения от пользователя.
        """
        with history_db:
            user_id: int = message.from_user.id
            command: str = message.text
            add_to_history(user_id, command)
            bot.send_message(message.chat.id, 'Введите название города отправления на русском языке')
            bot.register_next_step_handler(message, process_second_city)

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
            oldest_record: Optional[History] = History.select().where(History.user_id == str(user_id)).order_by(
                History.timestamp.asc()).first()
            if oldest_record:
                oldest_record.delete_instance()

        # Добавляем новую запись в историю
        History.create(user_id=str(user_id), command=command)

    def process_second_city(message: types.Message, departure_city: Optional[City] = None) -> None:
        """
        Обработчик второго шага процесса запроса информации у пользователя - города прибытия.

        Args:
            message: Объект сообщения от пользователя.
        """
        try:
            db.connect(reuse_if_open=True)  # Подключение к базе данных
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

    def process_date_departure(message: types.Message, departure_city: City,
                               arrival_city: Optional[City] = None) -> None:
        """
        Обработчик второго шага процесса запроса информации у пользователя - ввода даты отправления.

        Args:
            message: Объект сообщения от пользователя.
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
            bot.register_next_step_handler(message, process_price_range, departure_city=departure_city,
                                           arrival_city=arrival_city)
        except Exception as e:
            bot.reply_to(message, 'Что-то пошло не так, прошу повторите запрос')
        finally:
            db.close()

    def process_price_range(message, departure_city: City, arrival_city: City,
                            date_info: Optional[City] = None) -> None:
        """
        Обработчик третьего шага процесса запроса информации у пользователя - ввода диапазона цен.

        Args:
            message: Объект сообщения от пользователя.
            :param date_info:
        """
        try:
            db.connect(reuse_if_open=True)  # Подключение к базе данных
            date_info = message.text
            if validate_date_format(date_info):
                bot.send_message(message.chat.id, 'Введите диапазон цен через дефис (например, 5000-10000)')
                bot.register_next_step_handler(message, final_price_range, date_info=date_info,
                                               departure_city=departure_city, arrival_city=arrival_city)
            else:
                bot.send_message(message.chat.id, 'Некорректный формат даты. Пожалуйста, введите в формате YYYY-MM.')
                bot.register_next_step_handler(message, process_price_range, departure_city=departure_city,
                                               arrival_city=arrival_city)
        except Exception as e:
            bot.reply_to(message, 'Что-то пошло не так, прошу повторите запрос')
        finally:
            db.close()

    def validate_date_format(date_text: str) -> bool:
        """
        Проверяет корректность формата введенной даты.

        Args:
            date_text: Строка с введенной датой.

        Returns:
            True, если формат корректен, в противном случае False.
        """
        pattern: re.Pattern = re.compile(r'^\d{4}-\d{2}$')
        return bool(pattern.match(date_text))

    def validate_price_range(price_range_text: str) -> bool:
        """
        Проверяет корректность формата введенного диапазона цен.

        Args:
            price_range_text: Строка с введенным диапазоном цен.

        Returns:
            True, если формат корректен, в противном случае False.
        """
        pattern: re.Pattern = re.compile(r'^\d+-\d+$')
        return bool(pattern.match(price_range_text))

    def final_price_range(message, departure_city: City, arrival_city: City,
                          date_info: City, price_range: Optional[City] = None) -> None:
        """
        Обработчик четвертого шага процесса запроса информации у пользователя - ввода окончательного диапазона цен.

        Args:
            message: Объект сообщения от пользователя.
            :param date_info:
        """
        try:
            db.connect(reuse_if_open=True)  # Подключение к базе данных
            price_range = message.text
            if validate_price_range(price_range):
                final(message, departure_city, arrival_city, date_info, price_range)
            else:
                bot.send_message(message.chat.id, 'Некорректный формат диапазона цен. Пожалуйста, введите в формате '
                                                  'нижняя_граница-верхняя_граница (например, 5000-10000).')
                bot.register_next_step_handler(message, final_price_range, departure_city=departure_city,
                                               arrival_city=arrival_city, date_info=date_info)
        except Exception as e:
            bot.reply_to(message, 'Что-то пошло не так, прошу повторите запрос')
        finally:
            db.close()

    def final(message: types.Message, origin_city: City, destination_city: City, departure_at: str, prices: str) -> None:
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
                    # Фильтруем данные по диапазону цен
                    filtered_data: list = [flight for flight in data if
                                           int(prices.split('-')[0]) <= flight['price'] <= int(
                                               prices.split('-')[1])]

                    if not filtered_data:
                        bot.send_message(message.chat.id,
                                         'По вашему запросу нет доступных рейсов в указанном диапазоне цен')
                        return

                    for flight in filtered_data:
                        formated_date: str = flight['departure_at'][:19]
                        airports_origin_code: str = flight['origin_airport']
                        airports_destination_code: str = flight['destination_airport']
                        origin_airport_name: Optional[Airports] = Airports.get_or_none(code=airports_origin_code)
                        destination_airport_name: Optional[Airports] = Airports.get_or_none(
                            code=airports_destination_code)
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
