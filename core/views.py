from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def base_view(request):
    return render(request, 'base.html')

def ping(request):
    return JsonResponse({"status": "OK"}, status=200)