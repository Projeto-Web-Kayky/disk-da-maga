from django import forms
from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'nickname', 'phone_number', 'client_debts', 'photo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'input input-bordered w-full'})

            if name == 'photo':
                field.widget.attrs.update(
                    {
                        'class': 'file-input file-input-bordered w-full text-white bg-green-800 border-green-800'
                    }
                )
        if self.instance and self.instance.pk:
            # Na edição, remover campos que são calculados automaticamente
            if 'client_debts' in self.fields:
                del self.fields['client_debts']
