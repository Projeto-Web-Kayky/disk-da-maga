from django.shortcuts import render, redirect, get_object_or_404
from clients.models import Client
from clients.forms import ClientForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseBadRequest
import json


@login_required
def client_list(request):
    clients = Client.objects.all()
    form = ClientForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('client_list')

    return render(
        request,
        'client_list.html',
        {
            'clients': clients,
            'form': form,
            'section_name': 'Lista de Clientes',
        },
    )


@login_required
def client_detail(request, client_id):
    """Render client detail modal fragment."""
    client = get_object_or_404(Client, pk=client_id)
    return render(request, 'partials/client_detail_modal.html', {'client': client})


@login_required
@require_POST
def client_delete(request, client_id):
    """Delete a client and return a small response to trigger UI update.

    This view is intended to be called via HTMX `hx-post` from the
    client detail modal. On success it returns a small script that
    reloads the page so the client list refreshes.
    """
    client = get_object_or_404(Client, pk=client_id)
    try:
        client.delete()
    except Exception as e:
        return HttpResponseBadRequest(str(e))
    # Respond with an HX-Trigger header so the frontend can remove the
    # client row from the DOM and close the modal without a full reload.
    response = HttpResponse(status=200)
    response['HX-Trigger'] = json.dumps({'clientDeleted': {'clientId': client_id}})
    return response
