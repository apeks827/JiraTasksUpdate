from jira.client import JIRA
from dist import secrets
import time

jira = JIRA(
    server="https://jira.ozon.ru",
    token_auth=secrets.api
)

# Who has authenticated
myself = jira.myself()

cnt = 0
while True:
    time.sleep(5)
    # Search issues
    new_issues = jira.search_issues(
        'project = SD911 AND status = "Ожидает обработки" AND assignee in (EMPTY) AND "Группа '
        'исполнителей" = TS_TMB_team')
    if not new_issues:
        cnt += 1
    print(cnt, new_issues)

    for issue in new_issues:
        print("Issue is: ", issue)
        comments = jira.issue(issue, fields='comment')
        print("Comments is:", comments)
        check_comments = comments.raw['fields']['comment']
        print("Check comments is: ", check_comments)
        if "Suvorinov Ivan Vladimirovich" in check_comments or "Pechenin Aleksandr Sergeevich" in check_comments or "Ivashov Vladimir Aleksandrovich" in check_comments or "Smolenskiy Aleksey Yuryevich" in check_comments or "Titov Oleg Olegovich" in check_comments:
            pass
        else:
            jira.assign_issue(issue, 'sergmakarov')
            try:
                jira.transition_issue(issue, '10036')
            except Exception as err:
                print(err)

