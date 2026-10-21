from django import forms

from .models import Post


class PostForm(forms.ModelForm):

    class Meta:
        model = Post

        fields = [
            "text",
            "image",
            "image2",
        ]

        widgets = {
            "text": forms.Textarea(
                attrs={
                    "placeholder":
                        "投稿内容を入力...",
                    "rows": 4,
                    "maxlength": 180,
                }
            ),

            "image": forms.FileInput(
                attrs={
                    "accept": "image/*",
                }
            ),

            "image2": forms.FileInput(
                attrs={
                    "accept": "image/*",
                }
            ),
        }