from .models import Favorite, Like
from .services import get_recommended_posts


def mini_sns_posts(request):

    if not request.user.is_authenticated:
        return {
            "mini_sns_posts": [],
            "mini_sns_liked_post_ids": set(),
            "mini_sns_favorite_post_ids": set(),
            "mini_sns_view_mode": "recommended",
        }


    # ========================================
    # ミニSNS初回表示
    # おすすめ投稿を表示
    # ========================================

    posts = get_recommended_posts()


    # ========================================
    # 表示中の投稿ID
    # ========================================

    post_ids = [
        post.id
        for post in posts
    ]


    # ========================================
    # 自分がいいねした投稿
    # ========================================

    liked_post_ids = set(
        Like.objects.filter(
            user=request.user,
            post_id__in=post_ids,
        ).values_list(
            "post_id",
            flat=True,
        )
    )


    # ========================================
    # 自分がお気に入りした投稿
    # ========================================

    favorite_post_ids = set(
        Favorite.objects.filter(
            user=request.user,
            post_id__in=post_ids,
        ).values_list(
            "post_id",
            flat=True,
        )
    )


    return {
        "mini_sns_posts":
            posts,

        "mini_sns_liked_post_ids":
            liked_post_ids,

        "mini_sns_favorite_post_ids":
            favorite_post_ids,

        "mini_sns_view_mode":
            "recommended",
    }