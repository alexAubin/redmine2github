---


{% if author_name %}Author Name: **{{ author_name }}** {% if author_github_username %}({{ author_github_username }}){% endif %}{% endif %}
{% if redmine_issue_num %}Original Redmine Issue: {{ redmine_issue_num }}{% endif %}{% if redmine_link %}, {{ redmine_link }}{% endif %}
{% if start_date %}Original Date: {{ start_date }}{% endif %}
{% if redmine_assignee %}Original Assignee: {{ redmine_assignee }}{% endif %}

---

{{ description }}



