import threading
import time
from threading import Timer

import telebot
from aiogram.utils.markdown import hlink
from jira.client import JIRA
from telebot import types

from dist import secrets

jira = JIRA(
    server="https://jira.ozon.ru",
    token_auth=secrets.api
)

# Who has authenticated
myself = jira.myself()


def loop():
    loop.call_count += 1

    if loop.call_count > 10:
        print('Reset')
        return

    try:
        cnt = 0
        while True:
            time.sleep(10)
            print("Start searching new issues...")
            # Search issues
            new_issues = jira.search_issues(
                'project = SD911 AND status = "Ожидает обработки" AND assignee in (EMPTY) AND "Группа '
                'исполнителей" = TS_TMB_team')
            if not new_issues:
                cnt += 1
                print("Yay! No new issues!")
            print("-------------------------------------------------------------------------------")

            for issue in new_issues:
                issue_creator = issue.raw['fields']['creator']['name']
                issue_name = issue.raw['fields']['summary']
                print("Issue is: ", issue)  # issue ID
                check_comments = issue.raw['fields']['comment']['comments']  # comments from issue
                print("Check comments is: ", check_comments)
                # check comments
                if "Suvorinov Ivan Vladimirovich" in check_comments or "Pechenin Aleksandr Sergeevich" in check_comments or "Ivashov Vladimir Aleksandrovich" in check_comments or "Smolenskiy Aleksey Yuryevich" in check_comments or "Titov Oleg Olegovich" in check_comments:
                    pass
                else:
                    try:
                        send_message(issue, issue_creator, issue_name)
                    except Exception as err:
                        print(err)
                    # assign on me
                    jira.assign_issue(issue, 'sergmakarov')
                    try:
                        # transition to status "В работе"
                        jira.transition_issue(issue, '21')
                    except Exception as err:
                        print(err)

    except Exception as err:
        print(err)
        Timer(15, loop).start()


def get_list(oh_crap):
    issues = []
    issue_creator = []
    issue_name = []
    for issue in oh_crap:
        issue_creator_infunc = issue.raw['fields']['creator']['name']
        issue_name_infunc = issue.raw['fields']['summary']
        issue_creator.append(issue_creator_infunc)
        issue_name.append(issue_name_infunc)
        issues.append(issue.key)
    return issues, issue_creator, issue_name


def new_issues_ondesk():
    new_issues = jira.search_issues(
        'project = SD911 AND status = "Ожидает обработки" AND assignee in (EMPTY) AND "Группа '
        'исполнителей" = TS_TMB_team')
    return get_list(new_issues)


def issues_on_me():
    oh_crap = jira.search_issues('status in ("Ожидает обработки", "Повторно открыта", "Ожидает разработки", Уточнено, '
                                 '"В работе", Согласовано) AND assignee in (currentUser())')
    print(oh_crap)
    return get_list(oh_crap)


def search_updates():
    something_new = jira.search_issues('updatedDate >= -4d and key in watchedIssues() AND status != Обработано')
    return get_list(something_new)


bot = telebot.TeleBot(secrets.tg)

my_id = 105517177


def send_message(issue, creator, name):
    answer = hlink(f'{issue}: {name}', f'https://jira.ozon.ru/browse/{issue}')
    bot.send_message(my_id, f'Hi! There is a new issue: {answer} from {creator}', parse_mode='HTML')


def send_message_updates(issue, creator, name):
    answer = hlink(f'{issue}: {name}', f'https://jira.ozon.ru/browse/{issue}')
    bot.send_message(my_id, f'Hi! There is a new update: {answer} from {creator}', parse_mode='HTML')


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    itembtn1 = types.KeyboardButton('Issues on me')
    itembtn2 = types.KeyboardButton('-')
    itembtn3 = types.KeyboardButton('Updates')
    markup.add(itembtn1, itembtn2, itembtn3)
    bot.send_message(message.chat.id, "Choose what you want:", reply_markup=markup)


@bot.message_handler(content_types=['text'])
def got_message(message):
    keyboard = telebot.types.InlineKeyboardMarkup()
    buttons_in_row = 1
    buttons_added = []
    if message.text == "Issues on me":
        issues = issues_on_me()
        issue_name = issues[2]
        if not issues:
            bot.send_message(my_id, text='Nothing!')
        else:
            issue_name_nums = 0
            for issue in issues[0]:
                issue_name_str = issue_name[issue_name_nums]
                buttons_added.append(telebot.types.InlineKeyboardButton(f'{issue}: {issue_name_str}',
                                                                        url=f'https://jira.ozon.ru/browse/{issue}'))
                if len(buttons_added) == buttons_in_row:
                    keyboard.add(*buttons_added)
                    buttons_added = []
            if buttons_added:
                print(*buttons_added)
                issue_name_nums += 1
            bot.send_message(my_id, text='Issues on me:', reply_markup=keyboard)

    elif message.text == "reserved":
        # def close_keyboard(bot, update):
        #     bot.send_message(my_id, text='Issues on me:', reply_markup=ReplyKeyboardRemove())
        pass

    elif message.text == "Updates":
        issues = search_updates()
        issue_name = issues[2]
        if not issues:
            bot.send_message(my_id, text='Nothing!')
        else:
            issue_name_nums = 0
            for issue in issues[0]:
                issue_name_str = issue_name[issue_name_nums]
                buttons_added.append(telebot.types.InlineKeyboardButton(f'{issue}: {issue_name_str}',
                                                                        url=f'https://jira.ozon.ru/browse/{issue}'))
                if len(buttons_added) == buttons_in_row:
                    keyboard.add(*buttons_added)
                    buttons_added = []
                issue_name_nums += 1
            # return_btn = telebot.types.InlineKeyboardButton("Return", callback_data="return")
            # keyboard.add(return_btn)
            bot.send_message(my_id, text='Last updates:', reply_markup=keyboard)


# @bot.callback_query_handler(func=lambda call: True)
# def callback_query(call):
#     if call.data == "return":
#         bot.answer_callback_query(call.id, "/start")


def search_updates_timeout():
    search_updates_timeout.call_count += 1

    if search_updates_timeout.call_count > 10:
        print('Reset')
        return

    try:
        while True:
            time.sleep(300)
            print("Start searching updates...")
            new_issues = jira.search_issues('updatedDate >= -6m and key in watchedIssues() AND status != Обработано')
            if not new_issues:
                print("No new updates!")
            print("-------------------------------------------------------------------------------")

            for issue in new_issues:
                issue_creator = issue.raw['fields']['creator']['name']
                issue_name = issue.raw['fields']['summary']
                print("Issue is: ", issue)  # issue ID
                try:
                    send_message_updates(issue, issue_creator, issue_name)
                except Exception as err:
                    print(err)

    except Exception as err:
        print(err)
        Timer(30, search_updates_timeout).start()


loop.call_count = 0
search_updates_timeout.call_count = 0

thread_main_loop = threading.Thread(target=loop)
thread_tg_bot = threading.Thread(target=bot.infinity_polling)
thread_check_updates = threading.Thread(target=search_updates_timeout)

thread_main_loop.start()
thread_tg_bot.start()
thread_check_updates.start()
# thread_check_updates.start()


# async def main():
#     try:
#
#     except Exception as err:
#         # если таймаут, то повторяем
#         print(err)
#         while Exception:
#             time.sleep(15)
#             asyncio.run(main())


# if __name__ == '__main__':
