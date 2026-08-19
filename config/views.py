from django.shortcuts import render


def home(request):
    return render(request, 'home.html')


def again(request):
    return render(request, 'again.html')