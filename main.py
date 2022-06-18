import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from telegram import TelegramError, ReplyKeyboardMarkup, KeyboardButton
from telegram import update as update_type
from telegram.ext import Updater, Filters, MessageHandler
from telegram.ext import callbackcontext
from get_emoji import get_emoji, get_emoji_str

from database import engine, User

load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
API_KEY = os.getenv('API_KEY')

URL_WEATHER_API = 'https://api.openweathermap.org/data/2.5/weather'

logger = logging.getLogger(__name__)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - '
                              '%(funcName)s - %(lineno)d - %(message)s')
handler = logging.FileHandler('main.log', encoding='utf-8')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

start_keyboard = keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton(text='Указать местоположение', request_location=True)]], resize_keyboard=True)
main_keyboard = ReplyKeyboardMarkup([['Получить текущую погоду'], ['Помощь']], resize_keyboard=True)


def check_env() -> bool:
    """Функция проверки переменных виртуального окружения."""
    return all((TOKEN, API_KEY))


def create_update_user(chat_id: int, latitude: float, longitude: float) -> bool:
    """Функция создания или обновления данных пользователя.
    Если пользователя нет в базе то добавляем, если есть, но его координаты отличаются - то обновляем координаты.
    Иначе ничего не делаем. Если пользователя был добавлен или обновлен то возвращает True иначе False."""
    logger.info(f'Вызвана функция создания пользователя id: {chat_id}.')
    session = Session(bind=engine)
    user = session.query(User).get(chat_id)
    if not user:
        user = User(id=chat_id, latitude=latitude, longitude=longitude)
        session.add(user)
        session.commit()
        session.close()
        logger.info(f'В базу данных добавлен пользователь id: {chat_id}.')
        return True
    elif abs(user.latitude - latitude) > 0.002 and abs(user.longitude - longitude) > 0.002:
        logger.info(f'Пользователь с id: {chat_id} уже есть в базе данных, прислал новое местоположение.')
        user.latitude = latitude
        user.longitude = longitude
        user.last_response = ''
        session.commit()
        session.close()
        logger.info(f'Местоположение пользователя с id: {chat_id} обновлено.')
        return True
    else:
        logger.info(f'Создавать или обновлять данные пользователя c id: {chat_id} не требуется.')
        return False


def update_last_response(chat_id: int, response: dict) -> None:
    """Функция обновления запроса для пользователя, позволяет хранить в базе результат запроса в течении часа.
    При вызове обновляет поле last_response и last_update пользователя."""
    logger.info(f'Вызвана функция обновления последнего запроса пользователя id: {chat_id}.')
    session = Session(bind=engine)
    user = session.query(User).get(chat_id)
    user.last_response = json.dumps(response)
    user.last_update = datetime.now()
    session.commit()
    session.close()
    logger.info(f'Был обновлен последний запрос пользователя id: {chat_id}.')


def send_message(update: update_type,
                 context: callbackcontext,
                 text: str,
                 keyboard: Optional[ReplyKeyboardMarkup] = None) -> None:
    """Функция отправки сообщения в telegram."""
    chat_id = update.effective_chat.id
    logger.info(f'Начата отправка сообщения пользователю {chat_id}.')
    try:
        if keyboard:
            context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
        else:
            context.bot.send_message(chat_id=chat_id, text=text)
    except TelegramError as e:
        logger.error(f'Не удалось отправить сообщение. Ошибка: {e}.')
    else:
        logger.info(f'Отправлено сообщение пользователю {chat_id} с текстом {text[:20]}...')


def get_response(latitude: float, longitude: float) -> Optional[dict]:
    """Функция которая делает запрос к API по адресу https://api.openweathermap.org/data/2.5/weather.
    """
    logger.info('Начато выполнение запроса к API для получения погоды.')
    try:
        params = {'lat': latitude,
                  'lon': longitude,
                  'lang': 'ru',
                  'units': 'metric',
                  'appid': API_KEY}
        response = requests.get(url=URL_WEATHER_API, params=params).json()
    except Exception as e:
        logger.error(f'Не удалось выполнить запрос к API, url: {URL_WEATHER_API} для получения погоды. Ошибка: {e}.')
        return None
    else:
        logger.info(f'Выполнен запрос к API для получения погоды. Ответ: {response}.')
        return response


def parse_weather(response: dict) -> Optional[str]:
    """Функция которая делает запрос к API по адресу https://api.openweathermap.org/data/2.5/weather.
    Разбирает ответ и формирует строку с погодой."""
    logger.info('Начат парсинг ответа от API.')
    try:
        weather = response['weather'][0]['description']
        code = int(response['weather'][0]['id'])
        temp = round(float(response['main']['temp']))
        temp_feels_like = round(float(response['main']['feels_like']))
        humidity = round(float(response['main']['humidity']))
        wind_speed = float(response['wind']['speed'])
        name = response['name']
    except KeyError:
        logger.error(f'Не удалось выполнить парсинг ответа от API.')
        return None
    logger.info('Парсинг завершен.')
    emoji = get_emoji(code)
    if not emoji:
        logger.error(f'Не удалось получить emoji для кода {code}.')
        emoji = get_emoji_str('U+2753')
    wind = ''
    if wind_speed <= 1.5:
        wind = 'Ветра нет'
    elif 1.5 < wind_speed <= 5.4:
        wind = 'Легкий ветер'
    elif 5.4 < wind_speed <= 10.7:
        wind = 'Ветер'
    elif 10.7 < wind_speed <= 17.1:
        wind = 'Сильный ветер'
    elif 17.1 < wind_speed:
        wind = 'Шторм'
    message = (f'{get_emoji_str("U+1F3D9")} Погода в: {name}.\n'
               f'{emoji} {weather.capitalize()}.\n'
               f'{get_emoji_str("U+1F321")}️ Температура воздуха {temp}°C (ощущается как {temp_feels_like} °C).\n'
               f'{get_emoji_str("U+1F4A7")} Влажность {humidity}%.\n'
               f'{get_emoji_str("U+1F4A8")} {wind} (скорость {wind_speed} м/с).')
    return message


def handler_start(update: update_type, context: callbackcontext) -> None:
    """Функция обработки команды /start.
    отправляет пользователю сообщение и кдавиатуру с кнопкной «Отправить местоположение»."""
    logger.info('Получена команда /start.')
    text = 'Привет, отправь мне свое местоположение и я смогу присылать тебе погоду.'
    send_message(update, context, text, start_keyboard)


def handler_get_coordinates(update: update_type, context: callbackcontext) -> None:
    """Функция обработки сообщения с местоположением.
    Извлекает широту и долготу из сообщения и передает функции create_update_user,
    которая либо создает нового пользователя, либо обновляет координаты и отправляет погоду,
    либо ничего не делает и отправляет сообщение «Ваше местоположение не изменилось».
    """
    logger.info('Получено сообщение с местоположением.')
    chat_id = update.effective_chat.id
    logger.info('Начато определение координат.')
    try:
        latitude = update.message.location.latitude
        longitude = update.message.location.longitude
    except Exception as e:
        logger.error(f'Не удалось определить координаты пользователя {chat_id}. Ошибка: {e}.')
    else:

        logger.info(f'Определены координаты пользователя {chat_id}. Широта: {latitude}, долгота {longitude}.')
        if create_update_user(chat_id, latitude, longitude):
            handler_get_weather(update, context)
        else:
            text = 'Ваше местоположение не изменилось.'
            send_message(update, context, text, main_keyboard)


def handler_get_weather(update: update_type, context: callbackcontext) -> None:
    """Функция обработки сообщения с текстом «Получить текущую погоду».
    Функция либо делает запрос к API если данные устарели или еще не запрашивались,
    либо берет данные последнего запроса в базе данных.
    """
    logger.info(f'Получена команда на получение погоды')
    session = Session(bind=engine)
    chat_id = update.effective_chat.id
    user = session.query(User).get(chat_id)
    session.close()
    # Ситуация если пользователь не отправил местоположение, но отправил сообщение «Получить текущую погоду»
    if not user:
        logger.error(f'Не найден пользователь {chat_id}.')
        text = ('Сначала отправь мне свое местоположение '
                'и я смогу присылать тебе погоду. Нажми кнопку «Отправить местоположение»')

        send_message(update, context, text, start_keyboard)
        return

    latitude, longitude = user.latitude, user.longitude
    # если для данного пользователя или местоположения еще не выполнялся запрос к API
    if not user.last_response or datetime.now() - user.last_update > timedelta(hours=1):
        logger.info(f'Для данного пользователя или местоположения еще не выполнялся запрос к API или данные устарели.')
        response = get_response(latitude, longitude)
        if not response:
            text = 'Упс. Что-то пошло не так, попробуйте позже.'
            send_message(update, context, text, main_keyboard)
            return
        update_last_response(user.id, response)
    # если запрос выполнялся и прошло меньше часа
    else:
        logger.info(f'С момента последнего запроса не прошел час, загружаем данные из базы данных.')
        response = json.loads(user.last_response)

    text = parse_weather(response)
    if not text:
        text = 'Упс. Что-то пошло не так, попробуйте позже.'
    send_message(update, context, text, main_keyboard)


def handler_help(update: update_type, context: callbackcontext) -> None:
    """Функция обработки сообщения с текстом «Помощь»."""
    logger.info(f'Получена команда Помощь')
    text = ('Бот позволяет получить погоду в текущем местоположении. '
            'Если необходимо изменить местоположение - отправь боту новую геопозицию. '
            'Погода берется с сайта https://openweathermap.org.\n'
            'Автор: @podlev')
    send_message(update, context, text, main_keyboard)


def main() -> None:
    """Основная функция."""
    if not check_env():
        logger.critical('Не найдены переменные виртуального окружения')
        sys.exit()

    updater = Updater(token=TOKEN)
    dispatcher = updater.dispatcher
    map_handler = MessageHandler(Filters.location, handler_get_coordinates)
    command_handler = MessageHandler(Filters.command(('/start',)), handler_start)
    weather_handler = MessageHandler(Filters.text(('Получить текущую погоду',
                                                   'Получить погоду', )), handler_get_weather)
    help_handler = MessageHandler(Filters.text(('Помощь',)), handler_help)
    dispatcher.add_handler(map_handler)
    dispatcher.add_handler(command_handler)
    dispatcher.add_handler(weather_handler)
    dispatcher.add_handler(help_handler)

    updater.start_polling()
    updater.idle()
    logger.info(f'Бот запущен')


if __name__ == '__main__':
    main()
