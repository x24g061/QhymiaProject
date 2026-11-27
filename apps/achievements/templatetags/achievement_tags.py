from django import template
from django.utils.html import format_html

from apps.achievements.services import get_public_title

register = template.Library()


@register.simple_tag
def public_title(character):

    title = get_public_title(character)

    if title is None:
        return ""

    return format_html(
        '<span class="public-player-title public-title-rank-{}">'
        '【{}】</span>',
        title.achievement.rank,
        title.achievement.title_name,
    )
