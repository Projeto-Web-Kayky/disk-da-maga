from django.shortcuts import render, redirect
from clients.models import Client
from clients.forms import ClientForm
from django.contrib.auth.decorators import login_required


@login_required
def client_list(request):
    clients = Client.objects.all()
    form = ClientForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('client_list')

    return render(
        request, 'client_list.html', {'clients': clients, 'form': form, 'section_name': 'Lista de Clientes',}
    )
