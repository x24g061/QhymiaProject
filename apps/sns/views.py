from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PostForm
from .models import Like, Post


@login_required
def sns_page(request):
    posts = Post.objects.select_related(
        "user",
        "user__character"
    ).order_by("-created_at")

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
        },
    )


@login_required
def toggle_like(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    like = Like.objects.filter(
        user=request.user,
        post=post,
    ).first()

    if like:
        # すでにいいねしていたら解除
        like.delete()
    else:
        # まだいいねしていなければ追加
        Like.objects.create(
            user=request.user,
            post=post,
        )

    return redirect("sns")