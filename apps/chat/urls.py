from django.urls import path

from . import views


app_name = "chat"


urlpatterns = [

    # オープンチャット利用規約
    path(
        "terms/",
        views.chat_terms,
        name="terms",
    ),

    # チャットメッセージ取得
    path(
        "messages/",
        views.get_messages,
        name="get_messages",
    ),

    # チャット送信
    path(
        "send/",
        views.send_message,
        name="send_message",
    ),

]