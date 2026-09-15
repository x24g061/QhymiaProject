from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import Character, User


class SocialAccountAdapter(DefaultSocialAccountAdapter):

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(
            request,
            sociallogin,
            data
        )

        user.user_id = self.generate_user_id()

        return user

    def generate_user_id(self):
        last_user = User.objects.order_by("-id").first()

        if last_user is None:
            next_number = 1
        else:
            next_number = last_user.id + 1

        return f"QH{next_number:06d}"


class AccountAdapter(DefaultAccountAdapter):

    def get_login_redirect_url(self, request):
        user = request.user

        if Character.objects.filter(user=user).exists():
            return "/"

        return "/character/create/"

    def get_signup_redirect_url(self, request):
        return "/character/create/"