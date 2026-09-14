from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PostForm
from .models import Favorite, Like, Post
from django.http import JsonResponse

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