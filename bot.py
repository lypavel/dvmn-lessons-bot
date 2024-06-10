import sys
import time

from environs import Env
import requests
from requests.exceptions import ReadTimeout, ConnectionError
from telebot import TeleBot


def dvmn_long_polling(token: str,
                      timestamp: int | float | None) -> dict:
    api_url = 'https://dvmn.org/api/long_polling/'

    headers = {'Authorization': f'Token {token}'}
    payload = {'timestamp': timestamp}

    response = requests.get(api_url, headers=headers, params=payload)
    response.raise_for_status()

    return response.json()


def process_dvmn_response(response: dict) -> dict:
    lesson = response['new_attempts'][0]
    title = lesson['lesson_title']
    is_negative = lesson['is_negative']
    status = 'Принято' if not is_negative else 'Отклонено'
    url = lesson['lesson_url']

    return {
        'title': title,
        'status': status,
        'url': url
    }


def send_notification(check_status: dict, bot: TeleBot, chat_id: str) -> None:
    bot.send_message(
        chat_id,
        'Ваша работа проверена!\n\n'
        f'Название урока: {check_status["title"]}\n'
        f'Статус: {check_status["status"]}\n'
        f'Ссылка: {check_status["url"]}'
    )


def main(timestamp: float | None = None) -> None:
    env = Env()
    env.read_env()

    dvmn_token = env.str('DVMN_TOKEN')

    bot = TeleBot(env.str('TG_BOT'))
    chat_id = env.str('TG_CHAT_ID')

    connection_attempt = 1
    max_connection_attempts = 3

    while True:
        try:
            lesson_review = dvmn_long_polling(dvmn_token, timestamp)
        except (ConnectionError, ReadTimeout) as error:
            print(f"{error}\nTrying to reconnect...", file=sys.stderr)
            if connection_attempt > max_connection_attempts:
                time.sleep(10)
            connection_attempt += 1
            continue

        connection_attempt = 1

        dvmn_response_status = lesson_review['status']
        match dvmn_response_status:
            case 'timeout':
                timestamp = lesson_review['timestamp_to_request']
            case 'found':
                timestamp = lesson_review['last_attempt_timestamp']

                lesson_check = process_dvmn_response(lesson_review)
                send_notification(lesson_check, bot, chat_id)


if __name__ == '__main__':
    main()
