from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import Post


# ========================================
# SNS表示設定
# ========================================

TIMELINE_LIMIT = 50
RECOMMENDATION_DAYS = 7


# ========================================
# 新着投稿
# ========================================

def get_latest_posts():

    posts = list(
        Post.objects
        .select_related(
            "user",
            "user__character",
        )
        .prefetch_related(
            "likes",
        )
        .order_by(
            "-created_at"
        )[:TIMELINE_LIMIT]
    )

    for post in posts:
        post.is_recommended = False

    return posts


# ========================================
# おすすめ投稿
# ========================================

def get_recommended_posts():

    recommendation_start = (
        timezone.now()
        - timedelta(
            days=RECOMMENDATION_DAYS
        )
    )

    posts = list(
        Post.objects
        .select_related(
            "user",
            "user__character",
        )
        .prefetch_related(
            "likes",
        )
        .filter(
            created_at__gte=
                recommendation_start
        )
        .annotate(
            recommendation_like_count=
                Count("likes")
        )
        .filter(
            recommendation_like_count__gt=0
        )
        .order_by(
            "-recommendation_like_count",
            "-created_at",
        )[:TIMELINE_LIMIT]
    )

    for post in posts:
        post.is_recommended = True

    return posts