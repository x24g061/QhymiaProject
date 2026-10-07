from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import User


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Googleログイン用アダプター。

    Googleから取得したメールアドレスを使って
    Qhymia独自の user_id を自動生成する。
    """

    def is_auto_signup_allowed(self, request, sociallogin):
        """
        Googleログイン時の自動ユーザー登録を許可する。
        """
        return True

    def populate_user(self, request, sociallogin, data):
        """
        Googleから取得した情報をUserへ設定する。
        """

        user = super().populate_user(
            request,
            sociallogin,
            data,
        )

        email = data.get("email", "")

        if email:
            base_user_id = email.split("@")[0]
        else:
            base_user_id = "google_user"

        base_user_id = base_user_id[:20]

        user.user_id = self.generate_unique_user_id(
            base_user_id
        )

        return user

    def generate_unique_user_id(self, base_user_id):
        """
        user_idが重複した場合は末尾に数字を付ける。
        """

        base_user_id = base_user_id[:20]

        if not User.objects.filter(
            user_id=base_user_id
        ).exists():
            return base_user_id

        counter = 1

        while True:
            suffix = str(counter)

            candidate = (
                base_user_id[:20 - len(suffix)]
                + suffix
            )

            if not User.objects.filter(
                user_id=candidate
            ).exists():
                return candidate

            counter += 1


class AccountAdapter(DefaultAccountAdapter):
    """
    ログイン後の遷移先を決定する。
    """

    def get_login_redirect_url(self, request):
        user = request.user

        # キャラクター未作成
        if not hasattr(user, "character"):
            return "/accounts/character/create/"

        # キャラクター作成済み
        return "/"