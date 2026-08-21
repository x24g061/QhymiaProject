from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class SignUpForm(UserCreationForm):
    user_id = forms.CharField(
        label="固有ID",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "固有IDを入力してください",
                "autocomplete": "username",
            }
        ),
    )

    password1 = forms.CharField(
        label="パスワード",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "パスワードを入力してください",
                "autocomplete": "new-password",
            }
        ),
    )

    password2 = forms.CharField(
        label="パスワード確認",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "もう一度パスワードを入力してください",
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = User
        fields = (
            "user_id",
            "password1",
            "password2",
        )