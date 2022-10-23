import telebot
from dist import secrets
from aiogram.utils.markdown import hlink


bot = telebot.TeleBot(secrets.tg)

my_chat_id = 105517177

@bot.message_handler(commands=['start', 'help', 'issues'])
def send_welcome(message):
    bot.reply_to(message, "Howdy, how are you doing?")


def send_message(issue):
    print('enter to send')
    hello_with_url = hlink(f'{issue}', f'https://jira.ozon.ru/browse/{issue}')
    bot.send_message(my_chat_id, f'Hi, there is a new issue for you: {hello_with_url}', parse_mode='HTML')
    print('exit send')



