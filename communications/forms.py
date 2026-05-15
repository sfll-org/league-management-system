from django import forms

from .models import EmailTemplate


class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ['name', 'subject_template', 'body_template', 'reply_to', 'from_name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-gray-700 border border-gray-600 rounded-lg text-white '
                         'placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 '
                         'focus:border-transparent',
                'placeholder': 'e.g., SES Session Invitation',
            }),
            'subject_template': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-gray-700 border border-gray-600 rounded-lg text-white '
                         'placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 '
                         'focus:border-transparent',
                'placeholder': 'e.g., {{player.first_name}} — Your SES Session Details',
            }),
            'body_template': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 bg-gray-700 border border-gray-600 rounded-lg text-white '
                         'placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 '
                         'focus:border-transparent font-mono text-sm',
                'rows': 12,
                'placeholder': 'Dear {{player.first_name}},\n\nYou are scheduled for {{session.name}} on '
                               '{{session.date}}...',
            }),
            'reply_to': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-gray-700 border border-gray-600 rounded-lg text-white '
                         'placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 '
                         'focus:border-transparent',
                'placeholder': 'reply@sfll.org',
            }),
            'from_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-gray-700 border border-gray-600 rounded-lg text-white '
                         'placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 '
                         'focus:border-transparent',
                'placeholder': 'San Francisco Little League',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 rounded bg-gray-700 border-gray-600 text-emerald-500 '
                         'focus:ring-emerald-500 focus:ring-offset-gray-800',
            }),
        }
