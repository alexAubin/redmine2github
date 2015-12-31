{% if file_name %}File Attachment {% else %} Original Redmine Comment {% endif %}
{% if author_name %}Author Name: **{{ author_name }}** {% if author_github_username %}({{ author_github_username }}){% endif %}{% endif %}
{% if file_name %}File Name: [{{ file_name }}]({{file_url}}) ({{ file_size }}) {% endif %}
{% if note_date %}Original Date: {{ note_date }}{% endif %}
{% if status_new %}Status Changed: **{{ status_new }}**{% endif %}

{% if description %}
---

{{ description }}
{% endif %}
