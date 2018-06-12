{% if file_name %}
###### File Attachment
{% elif description %}
###### Original Redmine Comment
{% elif status_new %}
###### Status Change
{% else %}
###### Properties Change
{% endif %}
{% if author_name %}
Author: **{{ author_name }}**

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
