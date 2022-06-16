import logging
import os
import sys
from datetime import datetime, timedelta
import json

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from telegram import TelegramError, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, Filters, MessageHandler
from database import engine, User

load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
API_KEY = os.getenv('API_KEY')

URL_WEATHER_API = 'https://api.openweathermap.org/data/2.5/weather'
WEATHER_STATUSES = {800: 'Ясно',
                    801: 'Умеренная облачность 10-25%'}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

buttons = ReplyKeyboardMarkup([[KeyboardButton(text='Отправить местоположение', request_location=True)],
                               ['Получить погоду']], resize_keyboard=True)


def check_env():
    return all((TOKEN, API_KEY))


def create_user(chat_id, latitude, longitude):
    logging.info(f'Вызвана функция создания пользователя id: {chat_id}.')
    session = Session(bind=engine)
    user = session.query(User).get(chat_id)
    if not user:
        user = User(id=chat_id, latitude=latitude, longitude=longitude)
        session.add(user)
        session.commit()
        session.close()
        logging.info(f'В базу данных добавлен пользователь id: {chat_id}.')
        return True
    elif user.latitude != latitude and user.longitude != longitude:
        logging.info(f'Пользователь с id: {chat_id} уже есть в базе данных, прислал новое местоположение.')
        user.latitude = latitude
        user.longitude = longitude
        user.last_response = ''
        session.commit()
        session.close()
        logging.info(f'Местоположение пользователя с id: {chat_id} обновлено.')
        return True
    else:
        logging.info(f'Создавать и обновлять данные пользователя c id {chat_id} не требуется.')
        return False



def update_last_response(chat_id, response):
    logging.info(f'Вызвана функция обновления последнего запроса пользователя id: {chat_id}.')
    session = Session(bind=engine)
    user = session.query(User).get(chat_id)
    user.last_response = json.dumps(response)
    user.last_update = datetime.now()
    session.commit()
    session.close()
    logging.info(f'Был обновлен последний запрос пользователя id: {chat_id}.')


def send_message(update, context, text):
    chat_id = update.effective_chat.id
    logging.info(f'Начата отправка сообщения пользователю {chat_id}.')
    try:
        context.bot.send_message(chat_id=chat_id, text=text, reply_markup=buttons)
    except TelegramError as e:
        logging.error(f'Не удалось отправить сообщение. Ошибка: {e}.')
    else:
        logging.info(f'Отправлено сообщение пользователю {chat_id} c текстом: "{text}".')


def start(update, context):
    logging.info('Получена команда /start.')
    text = 'Привет, отправь мне свое местоположение и я смогу присылать тебе погоду.'

    send_message(update, context, text)


def get_coordinates(update, context):
    logging.info('Получено сообщение с местоположением.')
    chat_id = update.effective_chat.id
    logging.info('Начато определение координат.')
    try:
        latitude = update.message.location.latitude
        longitude = update.message.location.longitude
    except Exception as e:
        logging.error(f'Не удалось определить координаты пользователя {chat_id}. Ошибка: {e}.')
    else:

        logging.info(f'Определены координаты пользователя {chat_id}. Широта: {latitude}, долгота {longitude}.')
        if create_user(chat_id, latitude, longitude):
            get_weather(update, context)
        else:
            text = 'Ваше местоположение не изменилось.'
            send_message(update, context, text)


def get_weather(update, context):
    logging.info(f'Получена команда на получение погоды')
    session = Session(bind=engine)
    chat_id = update.effective_chat.id
    user = session.query(User).get(chat_id)
    session.close()
    if not user:
        logging.error(f'Не найден пользователь {chat_id}.')
        text = 'Сначала отправь мне свое местоположение и я смогу присылать тебе погоду. Нажми кнопку «Отправить местоположение»'
        send_message(update, context, text)
        return
    latitude, longitude = user.latitude, user.longitude
    if not user.last_response:
        logging.info(f'Для данного пользователя еще не выполнянлся запрос к API.')
        response = get_response(latitude, longitude)
        update_last_response(user.id, response)
    elif datetime.now() - user.last_update > timedelta(hours=1):
        logging.info(f'Данные устарели, требуется новый запрос.')
        response = get_response(latitude, longitude)
        update_last_response(user.id, response)
    else:
        logging.info(f'С момента запроса не прошел час, берем данные из базы данных.')
        response = json.loads(user.last_response)

    weather = parse_weather(response)
    if weather:
        send_message(update, context, weather)
    else:
        text = 'Упс. Что-то пошло не так, попробуйте позже.'
        send_message(update, context, text)


def get_response(latitude, longitude):
    logging.info('Начато выполнение запроса к API для получения погоды.')
    try:
        params = {'lat': latitude,
                  'lon': longitude,
                  'lang': 'ru',
                  'units': 'metric',
                  'appid': API_KEY}
        response = requests.get(url=URL_WEATHER_API, params=params).json()
    except Exception as e:
        logging.error(f'Не удалось выполнить запрос к API для получения погоды. Ошибка: {e}.')
    else:
        logging.info(f'Выполнен запрос к API для получения погоды. Ответ: {response}.')
        return response


def parse_weather(response):
    logging.info('Начат парсинг ответа от API.')
    try:
        weather_id = int(response['weather'][0]['id'])
        weather = WEATHER_STATUSES.get(weather_id, weather_id)
        temp = round(float(response['main']['temp']))
        feels_like = round(float(response['main']['feels_like']))
        wind_speed = response['wind']['speed']
        name = response['name']
    except KeyError:
        logging.error(f'Не удалось выполнить парсинг ответа от API.')
        return None
    else:
        logging.info('Парсинг завершен.')
        return f'Погода в {name}. \n{weather}, температура воздуха {temp} °C (ощущается как {feels_like} °C). \nСила ветра {wind_speed} м/с.'


def main():
    if not check_env():
        logging.critical('Не найдены переменные виртуального окружения')
        sys.exit()

    updater = Updater(token=TOKEN)
    dispatcher = updater.dispatcher
    map_handler = MessageHandler(Filters.location, get_coordinates)
    command_handler = MessageHandler(Filters.command(('/start',)), start)
    weather_handler = MessageHandler(Filters.text(('Получить погоду',)), get_weather)
    dispatcher.add_handler(map_handler)
    dispatcher.add_handler(command_handler)
    dispatcher.add_handler(weather_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
