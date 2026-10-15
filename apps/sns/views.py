from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PostForm
from .models import Favorite, Like, Post
from django.http import JsonResponse
from apps.accounts.models import AdminChangeLog
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

@login_required
def sns_page(request):
    view_mode = request.GET.get("view", "all")

    posts = Post.objects.select_related(
        "user",
        "user__character"
    ).order_by("-created_at")

    if view_mode == "favorites":
        posts = posts.filter(
            favorites__user=request.user
        )

    favorite_post_ids = set(
        Favorite.objects.filter(
            user=request.user
        ).values_list("post_id", flat=True)
    )

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)

        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            post.save()

            return redirect("sns")
    else:
        form = PostForm()

    return render(
        request,
        "sns_page.html",
        {
            "posts": posts,
            "form": form,
            "favorite_post_ids": favorite_post_ids,
            "view_mode": view_mode,
        },
    )


@login_required
def toggle_like(request, post_id):
    post = get_object_or_404(Post, id=post_id)

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

    return JsonResponse({
        "liked": liked,
        "like_count": post.likes.count(),
    })


@login_required
def toggle_favorite(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    favorite = Favorite.objects.filter(
        user=request.user,
        post=post,
    ).first()

    favorited = False

    if favorite:
        favorite.delete()
    else:
        Favorite.objects.create(
            user=request.user,
            post=post,
        )
        favorited = True

    return JsonResponse({
        "favorited": favorited,
    })

@login_required
def delete_post(request, post_id):
    post = get_object_or_404(
        Post,
        id=post_id,
        user=request.user,
    )

    if request.method == "POST":
        post.delete()

    return redirect("sns")