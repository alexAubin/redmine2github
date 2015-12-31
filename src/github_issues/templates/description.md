{% if redmine_issue_num %}
###### Original Redmine Issue: {{ redmine_issue_num }}{% if redmine_link %}, {{ redmine_link }}{% endif %}

{% endif %}
{% if author_name %}
Author Name: **{{ author_name }}** {% if author_github_username %}({{ author_github_username }}){% endif %}

{% endif %}

---

{{ description }}

