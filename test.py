from jira.client import JIRA
from dist import secrets
import time

jira = JIRA(
    server="https://jira.ozon.ru",
    token_auth=secrets.api
)

# Who has authenticated
myself = jira.myself()


def main():
    try:
        cnt = 0
        while True:
            time.sleep(10)
            # Search issues
            new_issues = jira.search_issues(
                'project = SD911 AND status = "Ожидает обработки" AND assignee in (EMPTY) AND "Группа '
                'исполнителей" = TS_TMB_team')
            if not new_issues:
                cnt += 1
            print(cnt, new_issues)

            for issue in new_issues:
                print("Issue is: ", issue)  # issue ID
                check_comments = issue.raw['fields']['comment']  # comments from issue
                print("Check comments is: ", check_comments)
                # check comments
                if "Suvorinov Ivan Vladimirovich" in check_comments or "Pechenin Aleksandr Sergeevich" in check_comments or "Ivashov Vladimir Aleksandrovich" in check_comments or "Smolenskiy Aleksey Yuryevich" in check_comments or "Titov Oleg Olegovich" in check_comments:
                    pass
                else:
                    # assign on me
                    jira.assign_issue(issue, 'sergmakarov')
                    try:
                        # transition to status "В работе"
                        jira.transition_issue(issue, '21')
                    except Exception as err:
                        print(err)
    except Exception as err:
        # если таймаут, то повторяем
        print(err)
        while Exception:
            time.sleep(15)
            main()


if __name__ == '__main__':
    main()
