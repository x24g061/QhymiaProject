from django.urls import path

from .views import sns_page

urlpatterns = [
    path('', sns_page, name='sns'),
]