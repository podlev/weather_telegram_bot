# Telegram бот для получения текущей погоды

Телеграм бот написанный на Python с использованием библиотеки [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot).

## Описание
Бот написан с использованием  библиотеки [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot). Используется SQLAlchemy для хранения информации о пользователях и хранения выполненных запросов. Погода берется с сайта https://openweathermap.org.

Бот в telegram: **@podlev_weather_bot**

## Как запустить
1. Создать и активировать виртаульное окружение
 ```
python -m venv venv
source venv/Scripts/activate
```  
2. Установить зависимости
```
pip install -r requirements.txt
```
3. Переименовать файл **.env.example** в **.env**
4. В файле .env указать телеграм токен и API key с сайта https://openweathermap.org/
5. Запустить скрипт
```
python main.py
```

## Автор
Telegram: [Лев Подъельников](https://t.me/podlev)
