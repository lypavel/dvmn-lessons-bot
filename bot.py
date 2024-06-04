from environs import Env
import requests as rq
from telebot import TeleBot


def dvmn_long_polling(token: str,
                      timestamp: int | float | None) -> dict:
    api_url = 'https://dvmn.org/api/long_polling/'

    headers = {'Authorization': f'Token {token}'}
    payload = {'timestamp': timestamp}

    response = rq.get(api_url, headers=headers, params=payload)
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

    while True:
        try:
            response = dvmn_long_polling(dvmn_token, timestamp)
        except (rq.exceptions.ReadTimeout, rq.exceptions.ConnectionError):
            pass

        response_status = response['status']
        match response_status:
            case 'timeout':
                timestamp = response['timestamp_to_request']
            case 'found':
                timestamp = response['last_attempt_timestamp']

                lesson_check = process_dvmn_response(response)
                send_notification(lesson_check, bot, chat_id)


if __name__ == '__main__':
    main()
