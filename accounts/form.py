from django import forms


class LoginForm(forms.Form):

    default_input_css = {'class': 'form-control'}

    username = forms.CharField(
        max_length=150,
        label='Usuário',
        widget=forms.TextInput(
            attrs={**default_input_css, 'placeholder': 'Digite seu usuário'}
        ),
        error_messages={
            'required': 'Este campo é obrigatório.',
            'max_length': 'O nome de usuário é muito longo.',
        },
    )

    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(
            attrs={**default_input_css, 'placeholder': 'Digite sua senha'}
        ),
        error_messages={
            'required': 'Este campo é obrigatório.',
        },
    )
