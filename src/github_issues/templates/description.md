{% if redmine_issue_num %}
###### Original Redmine Issue: [{{ redmine_issue_num }}]({{ redmine_link }})

{% endif %}
{% if author_name %}
Author Name: **{{ author_name }}**
{% endif %}

---

{{ description }}

