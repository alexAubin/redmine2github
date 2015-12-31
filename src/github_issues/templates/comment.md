{% if file_name %}
###### File Attachment
{% elif description %}
###### Original Redmine Comment
{% elif status_new %}
###### Status Change
{% endif %}
{% if author_name %}
Author Name: **{{ author_name }}** {% if author_github_username %}({{ author_github_username }}){% endif %}

{% endif %}
{% if file_name %}
File: [{{ file_name }}]({{file_url}}) ({{ file_size }})
{% endif %}
{% if status_new %}Status Changed: **{{ status_new }}**
{% endif %}
{% if description %}

---

{{ description }}
{% endif %}
