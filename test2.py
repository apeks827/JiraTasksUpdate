from jira.client import JIRA
from dist import secrets

jira = JIRA(
    server="https://jira.ozon.ru",
    token_auth=secrets.api  # Self-Hosted Jira (e.g. Server): the PAT token
    # auth=("admin", "admin"),  # a username/password tuple for cookie auth [Not recommended]
)
issue = jira.issue('SD911-2088745')
# print(jira.transitions(issue))
# print(issue.fields.status)

var = issue.raw['fields']['comment']
print(var)

comments = jira.issue('SD911-2088745', fields='comment')
print(comments.raw['fields']['comment'])

# check_comments = jira.comments(issue)
# print(check_comments)
