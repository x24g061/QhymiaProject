from django.shortcuts import redirect, render

from .forms import PostForm
from .models import Post


def sns_page(request):
    posts = Post.objects.select_related(
        "user",
        "user__character"
    ).order_by("-created_at")

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)

        if form.is_valid():
            post = form.save(commit=False)

            # 現在のユーザーと投稿を内部で紐づける
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