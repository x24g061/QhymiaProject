from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import AdminChangeLog

from .forms import PostForm
from .models import Favorite, Like, Post

from .services import (
    get_latest_posts,
    get_recommended_posts,
)


# ========================================
# 管理者：SNS投稿削除
# ========================================

@login_required
def admin_delete_post(request, post_id):

    # 管理者モードでなければ削除不可
    if not request.session.get("admin_mode"):
        return JsonResponse(
            {
                "error": "管理者権限がありません。"
            },
            status=403,
        )

    # POST以外では削除しない
    if request.method != "POST":
        return JsonResponse(
            {
                "error": "不正なリクエストです。"
            },
            status=405,
        )

    post = get_object_or_404(
        Post.objects.select_related(
            "user",
            "user__character",
        ),
        id=post_id,
    )

    # 操作した管理者
    admin_character = getattr(
        request.user,
        "character",
        None,
    )

    # 投稿したキャラクター
    post_character = getattr(
        post.user,
        "character",
        None,
    )

    changes = {
        "sns_action": {
            "label": "SNS投稿",
            "before": "投稿あり",
            "after": "削除済み",
        },
        "post_id": {
            "label": "投稿ID",
            "before": post.id,
            "after": "削除済み",
        },
        "text": {
            "label": "投稿内容",
            "before": (
                post.text
                if post.text
                else "(本文なし)"
            ),
            "after": "削除済み",
        },
    }

    if post.image:
        changes["image"] = {
            "label": "画像",
            "before": "画像あり",
            "after": "削除済み",
        }

    # 削除する前に履歴を保存
    AdminChangeLog.objects.create(
        user=request.user,
        account_id=request.user.user_id,
        character_name=(
            admin_character.name
            if admin_character
            else ""
        ),
        target_character=post_character,
        target_character_name=(
            post_character.name
            if post_character
            else str(post.user)
        ),
        action_type="sns_post_delete",
        changes=changes,
    )

    # 履歴保存後に投稿を削除
    post.delete()

    return redirect("admin_panel")


# ========================================
# 通常SNS画面
# ========================================

@login_required
def sns_page(request):

    view_mode = request.GET.get(
        "view",
        "recommended",
    )


    # ========================================
    # 投稿一覧
    # ========================================

    if view_mode == "favorites":

        # お気に入り投稿
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
                favorites__user=request.user
            )
            .order_by(
                "-created_at"
            )[:50]
        )

        for post in posts:
            post.is_recommended = False


    elif view_mode == "latest":

        # 新着投稿
        posts = get_latest_posts()


    else:

        # おすすめ投稿
        view_mode = "recommended"

        posts = get_recommended_posts()


    # ========================================
    # お気に入り投稿ID
    # ========================================

    favorite_post_ids = set(
        Favorite.objects.filter(
            user=request.user
        ).values_list(
            "post_id",
            flat=True,
        )
    )


    # ========================================
    # 投稿処理
    # ========================================

    if request.method == "POST":

        form = PostForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():

            post = form.save(
                commit=False
            )

            post.user = request.user

            post.save()

            return redirect(
                "sns"
            )

    else:

        form = PostForm()


    # ========================================
    # SNS画面表示
    # ========================================

    return render(
        request,
        "sns_page.html",
        {
            "posts":
                posts,

            "form":
                form,

            "favorite_post_ids":
                favorite_post_ids,

            "view_mode":
                view_mode,
        },
    )

@login_required
@require_POST
def mini_create_post(request):

    text = request.POST.get(
        "text",
        "",
    ).strip()

    image = request.FILES.get(
        "image"
    )

    # 本文も画像もない場合
    if not text and not image:

        return JsonResponse(
            {
                "success": False,
                "error":
                    "投稿内容を入力してください。",
            },
            status=400,
        )

    form = PostForm(
        request.POST,
        request.FILES,
    )

    if not form.is_valid():

        return JsonResponse(
            {
                "success": False,
                "error":
                    "投稿に失敗しました。",
            },
            status=400,
        )

    post = form.save(
        commit=False
    )

    post.user = request.user

    post.save()

    return JsonResponse(
        {
            "success": True,
            "post_id": post.id,
        }
    )

# ========================================
# ミニSNS：投稿一覧だけ取得
# ========================================

@login_required
@require_GET
def mini_sns_feed(request):

    view_mode = request.GET.get(
        "view",
        "recommended",
    )


    # ========================================
    # 表示する投稿
    # ========================================

    if view_mode == "latest":

        # 新着
        posts = get_latest_posts()


    elif view_mode == "favorites":

        # お気に入り
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
                favorites__user=request.user
            )
            .order_by(
                "-created_at"
            )[:50]
        )

        for post in posts:
            post.is_recommended = False


    else:

        # おすすめ
        view_mode = "recommended"

        posts = get_recommended_posts()


    # ========================================
    # 表示中の投稿ID
    # ========================================

    post_ids = [
        post.id
        for post in posts
    ]


    # ========================================
    # いいね済み投稿
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
    # お気に入り済み投稿
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


    return render(
        request,
        "mini_sns_posts.html",
        {
            "mini_sns_posts":
                posts,

            "mini_sns_liked_post_ids":
                liked_post_ids,

            "mini_sns_favorite_post_ids":
                favorite_post_ids,

            "mini_sns_view_mode":
                view_mode,
        },
    )
# ========================================
# いいね
# ========================================

@login_required
def toggle_like(request, post_id):

    post = get_object_or_404(
        Post,
        id=post_id,
    )

    like = Like.objects.filter(
        user=request.user,
        post=post,
    ).first()

    liked = False

    if like:

        like.delete()

    else:

        Like.objects.create(
            user=request.user,
            post=post,
        )

        liked = True

    return JsonResponse(
        {
            "liked": liked,
            "like_count":
                post.likes.count(),
        }
    )


# ========================================
# お気に入り
# ========================================

@login_required
def toggle_favorite(
    request,
    post_id,
):

    post = get_object_or_404(
        Post,
        id=post_id,
    )

    favorite = (
        Favorite.objects
        .filter(
            user=request.user,
            post=post,
        )
        .first()
    )

    favorited = False

    if favorite:

        favorite.delete()

    else:

        Favorite.objects.create(
            user=request.user,
            post=post,
        )

        favorited = True

    return JsonResponse(
        {
            "favorited":
                favorited,
        }
    )


# ========================================
# 自分のSNS投稿を削除
# ========================================

@login_required
def delete_post(request, post_id):

    # 自分の投稿だけ取得可能
    post = get_object_or_404(
        Post,
        id=post_id,
        user=request.user,
    )

    if request.method == "POST":

        post.delete()

        # ミニSNSからのAjax削除
        if (
            request.headers.get(
                "X-Requested-With"
            )
            == "XMLHttpRequest"
        ):

            return JsonResponse(
                {
                    "success": True,
                }
            )

    # 通常SNSから削除した場合
    return redirect(
        "sns"
    )