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

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("client_list")

    return render(
        request,
        "client_list.html",
        {
            "clients": clients,
            "form": form,
            "section_name": "Lista de Clientes",
        },
    )


@login_required
def client_detail(request, client_id):
    """Render client detail modal fragment."""
    client = get_object_or_404(Client, pk=client_id)
    return render(request, "partials/client_detail_modal.html", {"client": client})


@login_required
def client_edit(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    is_htmx = request.headers.get("Hx-Request") == "true"

    if request.method == "POST":
        form = ClientForm(request.POST, request.FILES, instance=client)

        if form.is_valid():
            form.save()

            if is_htmx:
                # 204 diz ao HTMX para não trocar o conteúdo,
                # e HX-Refresh força reload (caso você realmente queira isso).
                return HttpResponse(status=204, headers={"HX-Refresh": "true"})

            return redirect("client_list")

        # Form inválido → apenas renderizar com status correto
        status_code = 422 if is_htmx else 200
        return render(
            request,
            "partials/client_edit_modal.html",
            {"form": form, "client": client},
            status=status_code,
        )

    # GET
    form = ClientForm(instance=client)
    return render(
        request, "partials/client_edit_modal.html",
        {"form": form, "client": client}
    )


@login_required
@require_POST
def client_delete(request, client_id):
    client = get_object_or_404(Client, pk=client_id)

    try:
        client.delete()
    except Exception as e:
        return HttpResponseBadRequest(str(e))

    return HttpResponse(
        status=200,
        headers={
            "HX-Trigger": json.dumps({
                "clientDeleted": {"clientId": client_id}
            })
        }
    )
