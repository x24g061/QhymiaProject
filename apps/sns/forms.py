from django import forms

from .models import Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["text", "image"]

        widgets = {
            "text": forms.Textarea(
                attrs={
                    "placeholder": "投稿内容を入力...",
                    "rows": 4,
                }
            ),
        }