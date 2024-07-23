import logging
from logging import Formatter, Handler, INFO, LogRecord
import time

from environs import Env
import requests
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout
from telebot import TeleBot

logger = logging.getLogger('lessons_bot')


class TelegramLogsHandler(Handler):
    def __init__(self, tg_bot: TeleBot, chat_id: str) -> None:
        super().__init__()

        self.chat_id = chat_id
        self.tg_bot = tg_bot

        self.setFormatter(Formatter('[%(name)s][%(levelname)s]: %(message)s'))

    def emit(self, record: LogRecord):
        log_entry = self.format(record)

        self.tg_bot.send_message(
            self.chat_id,
            log_entry
        )


def get_reviewed_lesson(token: str,
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


def main(timestamp: float | None = None) -> None:
    env = Env()
    env.read_env()

    dvmn_token = env.str('DVMN_TOKEN')

    bot = TeleBot(env.str('TG_BOT'))
    chat_id = env.str('TG_CHAT_ID')

    logger.setLevel(INFO)
    logger.addHandler(TelegramLogsHandler(bot, chat_id))

    logger.info('Bot started.')

    connection_attempt = 1
    max_connection_attempts = 3

    while True:
        try:
            try:
                lesson_review = get_reviewed_lesson(dvmn_token, timestamp)
            except ReadTimeout:
                continue
            except (ConnectionError, HTTPError) as connection_error:
                # prevent spamming log messages to chat
                if connection_attempt == 1:
                    logger.exception(
                        f'{connection_error}\nTrying to reconnect...'
                    )
                elif connection_attempt > max_connection_attempts:
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

                    lesson_check_status = process_dvmn_response(lesson_review)

                    bot.send_message(
                        chat_id,
                        'Ваша работа проверена!\n\n'
                        f'Название урока: {lesson_check_status["title"]}\n'
                        f'Статус: {lesson_check_status["status"]}\n'
                        f'Ссылка: {lesson_check_status["url"]}'
                    )

        except Exception as exception:
            logger.exception(exception)


if __name__ == '__main__':
    main()
