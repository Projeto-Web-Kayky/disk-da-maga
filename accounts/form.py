from django import forms


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        required=True,
        label='Usuário',
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'Digite seu usuário'}
        ),
        error_messages={
            'required': 'Este campo é obrigatório.',
            'max_length': 'O nome de usuário é muito longo.',
        }
    )
    password = forms.CharField(
        required=True,
        label='Senha',
        widget=forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'Digite sua senha'}
        ),
        error_messages={
            'required': 'Este campo é obrigatório.',
        }
    )
