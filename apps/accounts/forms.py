from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class SignUpForm(UserCreationForm):
    user_id = forms.CharField(
        label="ユーザーID",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "ユーザーIDを入力してください",
                "autocomplete": "username",
            }
        ),
    )

    email = forms.EmailField(
        label="メールアドレス",
        widget=forms.EmailInput(
            attrs={
                "placeholder": "メールアドレスを入力してください",
                "autocomplete": "email",
            }
        ),
        error_messages={
            "unique": "このメールアドレスは既に使用されています。",
        },
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
            "email",
            "password1",
            "password2",
        )

        error_messages = {
            "email": {
                "unique": "このメールアドレスは既に使用されています。",
            },
        }