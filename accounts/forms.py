from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm

from .models import User


class LoginForm(forms.Form):
    """Email + password login form."""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-emerald-500',
            'placeholder': 'you@example.com',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-emerald-500',
            'placeholder': 'Password',
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        if email and password:
            self.user = authenticate(username=email, password=password)
            if self.user is None:
                raise forms.ValidationError('Invalid email or password.')
            if not self.user.is_active:
                raise forms.ValidationError('This account is inactive.')
        return cleaned_data


class RegisterForm(UserCreationForm):
    """Registration form — email, name, password."""
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        widget_attrs = {
            'class': 'w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-emerald-500',
        }
        self.fields['email'].widget.attrs.update({**widget_attrs, 'placeholder': 'you@example.com'})
        self.fields['first_name'].widget.attrs.update({**widget_attrs, 'placeholder': 'First name'})
        self.fields['last_name'].widget.attrs.update({**widget_attrs, 'placeholder': 'Last name'})
        self.fields['password1'].widget.attrs.update({**widget_attrs, 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({**widget_attrs, 'placeholder': 'Confirm password'})
