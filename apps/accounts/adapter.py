from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import User


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