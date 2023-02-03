import threading
import time
from threading import Timer

import telebot
from datetime import datetime
from aiogram.utils.markdown import hlink
from jira.client import JIRA
from telebot import types

from dist import secrets

# Main

variable = True
variable_time = True
to_assign = 0


def start_stop(var):
    global variable
    variable = var

def start_stop_by_time(var):
    global variable_time
    variable_time = var

def restart():
    thread_main_loop_restart = threading.Thread(target=loop)
    thread_main_loop_restart.start()

def loop():
    loop.call_count += 1

    if loop.call_count > 10:
        print('Reset')
        loop.call_count = 0
        return restart()

    try:
        global to_assign
        while True:
            flag = -1
            print("Start searching new issues...")
            # Search issues
            new_issues = jira.search_issues(
                'project = SD911 AND status = "Ожидает обработки" AND assignee in (EMPTY) AND "Группа '
                'исполнителей" = TS_TMB_team')
            if not new_issues:
                print("Yay! No new issues!")
            # check start/stop
            if not variable or not variable_time:
                print("Search new issues closed")
                print("-------------------------------------------------------------------------------")
                break
            for issue in new_issues:
                issue_creator = issue.raw['fields']['creator']['name']
                issue_name = issue.raw['fields']['summary']  # issue name like "проблема с пк"
                check_comments = issue.raw['fields']['comment']['comments']  # comments from issue
                comments = ''.join(map(str, check_comments))
                print("Issue is: ", issue)  # issue ID
                print("Check skud is: ", issue_name)
                # check comments
                # print("Check comments is: ", check_comments)
                # print(type(comments))
                names = ["isuvorinov", "alpechenin", "vivashov", "asmolensky", "otitov"]
                for name in names:
                    if name in comments:
                        print(f"Skip {issue} by comments conditions")
                        flag = 0
                if "пропуск" in issue_name.lower() or "скуд" in issue_name.lower() or "vivashov" in issue_creator or "ivsuvorinov" in issue_creator or "otitov" in issue_creator or "возврат" in issue_name.lower() or "предостав" in issue_name.lower() or "ноутбук" in issue_name.lower():
                    print(f"Skip {issue} by conditions by issue_name or creator_name")
                    flag = 0

                if flag == -1:
                    try:
                        if to_assign == 0:
                            jira.transition_issue(issue, '21')
                            assignee = issue.raw['fields']['assignee']
                            print(f"Assigned to {assignee}")
                            try:
                                send_message(my_id, issue, issue_creator, issue_name)
                            except Exception as err:
                                print(err)
                            if issue.raw['fields']['assignee'] != 'sergmakarov':
                                jira.assign_issue(issue, 'sergmakarov')
                                print('Reassigned to sergmakarov')
                            to_assign = 1
                        else:
                            jira.transition_issue(issue, '21')
                            assignee = issue.raw['fields']['assignee']
                            print(f"Assigned to {assignee}")
                            try:
                                send_message(vovan_id, issue, issue_creator, issue_name)
                            except Exception as err:
                                print(err)
                            if issue.raw['fields']['assignee'] != 'vivashov':
                                jira.assign_issue(issue, 'vivashov')
                                print('Reassigned to vivashov')
                            to_assign = 0
                        # transition to status "В работе"

                    except Exception as err:
                        print("Err change status: ", err)
            print("-------------------------------------------------------------------------------")
            time.sleep(10)

    except Exception as err:
        print("Failure to check new issues: ", err)
        # got_err(err.__class__)
        if variable is False:
            pass
        else:
            Timer(15, loop).start()



def search_updates_timeout():
    search_updates_timeout.call_count += 1

    if search_updates_timeout.call_count > 10:
        print('Reset')
        return

    try:
        while True:
            time.sleep(300)
            print("Start searching updates...")
            new_issues = jira.search_issues(
                'updatedDate >= -6m and key in watchedIssues() AND status not in (Обработано, Закрыто, Отменено)')
            if not new_issues:
                print("No new updates!")

            for issue in new_issues:
                issue_creator = issue.raw['fields']['creator']['name']
                issue_name = issue.raw['fields']['summary']
                print("Issue is: ", issue)  # issue ID
                try:
                    send_message_updates(issue, issue_creator, issue_name)
                except Exception as err:
                    print(err)
            print("-------------------------------------------------------------------------------")
    except Exception as err:
        print(err)
        # got_err(err.__class__)
        Timer(30, search_updates_timeout).start()


thread_main_loop = threading.Thread(target=loop)
thread_check_updates = threading.Thread(target=search_updates_timeout)

# Jira

jira = JIRA(
    server="https://jira.o3.ru",
    token_auth=secrets.api
)


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
    something_new = jira.search_issues('updatedDate >= -4d and key in watchedIssues() AND status not in (Обработано, '
                                       'Закрыто, Отменено)')
    return get_list(something_new)


# TgBot

bot = telebot.TeleBot(secrets.tg)

my_id = 105517177
vovan_id = 1823360851


def send_message(to_send_id, issue, creator, name):
    answer = hlink(f'{issue}: {name}', f'https://jira.ozon.ru/browse/{issue}')
    teams_link = hlink(f'{creator}', f'https://teams.microsoft.com/l/chat/0/0?users={creator}@ozon.ru')
    bot.send_message(to_send_id, f'Hi! There is a new issue: {answer} from: {teams_link}', parse_mode='HTML')


def send_message_updates(issue, creator, name):
    answer = hlink(f'{issue}: {name}', f'https://jira.ozon.ru/browse/{issue}')
    bot.send_message(my_id, f'Hi! There is a new update: {answer} from {creator}', parse_mode='HTML')


def got_err(err):
    bot.send_message(my_id, f'Got err, check: {err}')


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if message.chat.id == 105517177:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        itembtn1 = types.KeyboardButton('Issues on me')
        itembtn2 = types.KeyboardButton('-')
        itembtn3 = types.KeyboardButton('Updates')
        markup.add(itembtn1, itembtn2, itembtn3)
        bot.send_message(message.chat.id, "Choose what you want:", reply_markup=markup)
        if variable is True:
            pass
        else:
            start_stop(True)
            print("Try to start")
            restart()
    else:
        pass


@bot.message_handler(content_types=['text'])
def got_message(message):
    if message.chat.id == 105517177:
        keyboard = telebot.types.InlineKeyboardMarkup()
        buttons_in_row = 1
        buttons_added = []
        if message.text == "Issues on me":
            issues = issues_on_me()
            issue_name = issues[2]
            if not issue_name:
                bot.send_message(my_id, text='Nothing!')
            else:
                issue_name_nums = 0
                for issue in issues[0]:
                    issue_name_str = issue_name[issue_name_nums]
                    buttons_added.append(telebot.types.InlineKeyboardButton(f'{issue}: {issue_name_str}',
                                                                            url=f'https://jira.ozon.ru/browse/{issue}'))
                    issue_name_nums += 1
                    if len(buttons_added) == buttons_in_row:
                        keyboard.add(*buttons_added)
                        buttons_added = []
                bot.send_message(my_id, text='Issues on me:', reply_markup=keyboard)

        elif message.text == "-":
            answer = hlink(f'/start', '/start')
            bot.send_message(my_id, f'Click start to open again: {answer}', parse_mode='HTML',
                             reply_markup=types.ReplyKeyboardRemove())
            start_stop(False)


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
                bot.send_message(my_id, text='Last updates:', reply_markup=keyboard)
    else:
        pass

def check_time():
    global variable
    flag = False
    while True:
        current_time = datetime.now()
        sleep_hour = [23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        print(f'Hour is {current_time.hour}')
        if current_time.hour in sleep_hour:
            print('Sleep...')
            flag = False
            start_stop_by_time(False)
        else:
            if current_time.hour == 11 and flag == False:
                flag = True
                start_stop_by_time(False)
                time.sleep(11)
                start_stop_by_time(True)
                loop()
            else:
                pass
        time.sleep(300)

loop.call_count = 0
search_updates_timeout.call_count = 0

thread_tg_bot = threading.Thread(target=bot.infinity_polling)
thread_time_loop = threading.Thread(target=check_time)


thread_main_loop.start()
thread_tg_bot.start()
thread_check_updates.start()
thread_time_loop.start()
