import re

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

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        errors = []

        # 英大文字
        if not re.search(r"[A-Z]", password):
            errors.append(
                "パスワードには英大文字を1文字以上含めてください。"
            )

        # 英小文字
        if not re.search(r"[a-z]", password):
            errors.append(
                "パスワードには英小文字を1文字以上含めてください。"
            )

        # 数字
        if not re.search(r"[0-9]", password):
            errors.append(
                "パスワードには数字を1文字以上含めてください。"
            )

        # 半角英数字以外は禁止
        if not re.fullmatch(r"[A-Za-z0-9]+", password):
            errors.append(
                "パスワードに特殊文字は使用できません。"
            )

        # エラーをまとめて表示
        if errors:
            raise forms.ValidationError(errors)

        return password