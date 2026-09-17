from django.db import models
from apps.accounts.models import Character


class ChatMessage(models.Model):
    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="chat_messages"
    )

    message = models.CharField(max_length=200)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.character.name}: {self.message[:20]}"