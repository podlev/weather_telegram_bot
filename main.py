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

from database import engine, User
from get_emoji import get_emoji, get_emoji_str

load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
API_KEY = os.getenv('API_KEY')

URL_WEATHER_API = 'https://api.openweathermap.org/data/2.5/forecast'

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - '
                              '%(funcName)s - %(lineno)d - %(message)s')
handler = logging.FileHandler('main.log', encoding='utf-8')
handler.setFormatter(formatter)
logger.addHandler(handler)


start_keyboard = keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton(text='Указать местоположение', request_location=True)]], resize_keyboard=True)
main_keyboard = ReplyKeyboardMarkup([['Получить погоду'], ['Помощь']], resize_keyboard=True)


def check_env() -> bool:
    """Функция проверки переменных виртуального окружения."""
    return all((TOKEN, API_KEY))


def create_update_user(chat_id: int, name: str, latitude: float, longitude: float, city: str = None) -> bool:
    """Функция создания или обновления данных пользователя.
    Если пользователя нет в базе то добавляем, если есть, но его координаты отличаются - то обновляем координаты.
    Иначе ничего не делаем. Если пользователя был добавлен или обновлен то возвращает True иначе False."""
    logger.info(f'Вызвана функция создания пользователя id: {chat_id}.')
    session = Session(bind=engine)
    user = session.query(User).get(chat_id)
    if not user:
        user = User(id=chat_id, name=name, latitude=latitude, longitude=longitude, city=city)
        session.add(user)
        session.commit()
        session.close()
        logger.info(f'В базу данных добавлен пользователь id: {chat_id}.')
        return True
    elif abs(user.latitude - latitude) > 0.005 and abs(user.longitude - longitude) > 0.005:
        logger.info(f'Пользователь с id: {chat_id} уже есть в базе данных, прислал новое местоположение.')
        user.latitude = latitude
        user.longitude = longitude
        user.city = city
        user.last_message = ''
        session.commit()
        session.close()
        logger.info(f'Местоположение пользователя с id: {chat_id} обновлено.')
        return True
    else:
        logger.info(f'Обновление не выполнено: местоположение пользователя с id: {chat_id} не изменилось. ')
        return False


def update_last_message(chat_id: int, text: str) -> None:
    """Функция позволяет хранить в базе последнее отправленное сообщение в течении часа.
    При вызове обновляет поле last_message и last_update пользователя."""
    logger.info(f'Вызвана функция обновления последнего сообщения пользователя id: {chat_id}.')
    if text:
        session = Session(bind=engine)
        user = session.query(User).get(chat_id)
        user.last_message = text
        user.last_update = datetime.now()
        session.commit()
        session.close()
        logger.info(f'Было обновлено последнее сообщение пользователя id: {chat_id}, сообщение {text[:30]}.')
    else:
        logger.error(f'Обновление не выполнено: сообщение text не должно быть: {text[:30]}.')


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
    except TelegramError as error:
        logger.error(f'Не удалось отправить сообщение пользователю {chat_id}. Ошибка: {error}.')
    else:
        logger.info(f'Отправлено сообщение пользователю {chat_id} с текстом {text[:30]}...')


def get_response(latitude: float, longitude: float) -> Optional[dict]:
    """Функция которая делает запрос к API по адресу https://api.openweathermap.org/data/2.5/forecast.
    """
    logger.info(f'Начато выполнение запроса к API {URL_WEATHER_API}.')
    try:
        params = {'lat': latitude,
                  'lon': longitude,
                  'lang': 'ru',
                  'units': 'metric',
                  'appid': API_KEY}
        response = requests.get(url=URL_WEATHER_API, params=params).json()
        if response.get('cod') == '200':
            logger.info(f'Выполнен запрос к API {URL_WEATHER_API}. Response: {response}.')
            return response
        else:
            logger.error(f'Запрос к API вернул не статус 200. Response: {response}.')
            return None
    except Exception as error:
        logger.error(f'Не удалось выполнить запрос к API. Ошибка: {error}.')
        return None


def parse_weather(response: dict) -> Optional[str]:
    """Разбирает ответ и формирует строку с погодой."""
    logger.info(f'Начат парсинг ответа от API. Response: {response}')
    try:
        city_name = response['city']['name']
        time_shift = response['city']['timezone']
    except KeyError:
        city_name = 'Не определено'
        time_shift = 0
        logger.error(f'Не удалось определить название населенного пункта. Response: {response}')
    message = f'{get_emoji_str("U+1F3D9")} Погода в: {city_name}.\n\n'

    try:
        for data in response.get('list')[:8]:
            date = data['dt_txt']
            real_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S") + timedelta(seconds=time_shift)
            if real_date.day <= datetime.now().day:
                today_text = 'Сегодня в'
            else:
                today_text = 'Завтра в'
            weather = data['weather'][0]['description']
            code = int(data['weather'][0]['id'])
            temp = round(float(data['main']['temp']))
            temp_feels_like = round(float(data['main']['feels_like']))
            humidity = round(float(data['main']['humidity']))
            wind_speed = float(data['wind']['speed'])
            emoji = get_emoji(code)
            # Получаем эмоджи для кода
            if not emoji:
                logger.error(f'Не удалось получить emoji для кода {code}.')
                emoji = get_emoji_str('U+2753')
            # Формируем сообщение о ветре
            wind = ''
            if wind_speed <= 1.5:
                wind = 'Ветра нет'
            elif 1.5 < wind_speed <= 5.4:
                wind = 'Легкий ветерок'
            elif 5.4 < wind_speed <= 10.7:
                wind = 'Ветер'
            elif 10.7 < wind_speed <= 17.1:
                wind = 'Сильный ветер'
            elif 17.1 < wind_speed:
                wind = 'Шторм'
            # Формируем итоговое сообщение
            message += (f'{get_emoji_str("U+1F558")} {today_text} {real_date.strftime("%H:%M")}\n'
                        f'{emoji} {weather.capitalize()}.\n'
                        f'{get_emoji_str("U+1F321")} Температура {temp}°C (ощущается {temp_feels_like}°C).\n'
                        f'{get_emoji_str("U+1F4A7")} Влажность {humidity}%.\n'
                        f'{get_emoji_str("U+1F4A8")} {wind} ({wind_speed} м/с).\n\n')

        sunrise = response['city'].get('sunrise')
        sunset = response['city'].get('sunset')

        if all((sunrise, sunset)):
            sunrise_time = datetime.fromtimestamp(sunrise + time_shift).strftime('%H:%M')
            sunset_time = datetime.fromtimestamp(sunset + time_shift).strftime('%H:%M')
            message += (f'{get_emoji_str("U+1F31E")} Время рассвета: {sunrise_time} '
                        f'\n{get_emoji_str("U+1F31A")} Время заката: {sunset_time}')
        else:
            logger.error(f'Не удалось получить ключи sunrise, sunset, timezone. Response: {response}')
    except KeyError:
        logger.error(f'Не удалось разобрать запрос. Response: {response}')
        return None
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
    name = update.effective_chat.username
    logger.info('Начато определение координат.')
    try:
        latitude = update.message.location.latitude
        longitude = update.message.location.longitude
    except Exception as e:
        logger.error(f'Не удалось определить координаты пользователя {chat_id}. Ошибка: {e}.')
    else:
        logger.info(f'Определены координаты пользователя {chat_id}. Широта: {latitude}, долгота {longitude}.')
        if create_update_user(chat_id, name, latitude, longitude):
            handler_get_weather(update, context)
        else:
            text = 'Ваше местоположение не изменилось.'
            send_message(update, context, text, main_keyboard)


def handler_get_weather(update: update_type, context: callbackcontext) -> None:
    """Функция обработки сообщения с текстом «Получить текущую погоду».
    Функция либо делает запрос к API если данные устарели или еще не запрашивались,
    либо берет последнее сообщение в базе данных.
    """
    logger.info(f'Получена команда «Получить погоду».')
    session = Session(bind=engine)
    chat_id = update.effective_chat.id
    user = session.query(User).get(chat_id)
    session.close()
    # Ситуация если пользователь не отправил местоположение, но отправил сообщение «Получить погоду»
    if not user:
        logger.error(f'Не был найден пользователь if: {chat_id}.')
        text = ('Сначала отправь мне свое местоположение '
                'и я смогу присылать тебе погоду. Нажми кнопку «Отправить местоположение».')
        send_message(update, context, text, start_keyboard)
        return

    # если для данного пользователя или местоположения еще не выполнялся запрос к API
    if not user.last_message or datetime.now() - user.last_update > timedelta(hours=1):
        logger.info((f'Для данного пользователя id {chat_id} или местоположения еще не выполнялся запрос к API '
                     f'или данные устарели.'))
        latitude, longitude = user.latitude, user.longitude
        response = get_response(latitude, longitude)
        if not response:
            text = 'Упс. Что-то пошло не так, попробуйте позже.'
            send_message(update, context, text, main_keyboard)
            return
        text = parse_weather(response)
        if not text:
            text = 'Упс. Что-то пошло не так, попробуйте позже.'
        else:
            update_last_message(user.id, text)
    # если запрос выполнялся и прошло меньше часа
    else:
        logger.info((f'С момента последнего запроса для пользователя if {chat_id}'
                     f'не прошел час, загружаем сообщение из базы данных.'))
        text = user.last_message

    send_message(update, context, text, main_keyboard)


def handler_help(update: update_type, context: callbackcontext) -> None:
    """Функция обработки сообщения с текстом «Помощь»."""
    logger.info(f'Получена команда «Помощь».')
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
                                                   'Получить погоду',)), handler_get_weather)
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
