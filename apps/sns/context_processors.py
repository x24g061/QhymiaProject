from .models import Favorite, Like, Post


def mini_sns_posts(request):

    if not request.user.is_authenticated:
        return {
            "mini_sns_posts": [],
            "mini_sns_liked_post_ids": set(),
            "mini_sns_favorite_post_ids": set(),
        }

    posts = list(
        Post.objects
        .select_related(
            "user",
            "user__character",
        )
        .prefetch_related(
            "likes",
        )
        .order_by("-created_at")[:50]
    )

    post_ids = [
        post.id
        for post in posts
    ]

    liked_post_ids = set(
        Like.objects.filter(
            user=request.user,
            post_id__in=post_ids,
        ).values_list(
            "post_id",
            flat=True,
        )
    )

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
        "mini_sns_posts": posts,
        "mini_sns_liked_post_ids": liked_post_ids,
        "mini_sns_favorite_post_ids": favorite_post_ids,
    }