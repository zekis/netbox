from django import forms

from .models import Drawing
from .services import validate_context


class DrawingForm(forms.ModelForm):
    class Meta:
        model = Drawing
        fields = ('title', 'tenant', 'site', 'location', 'source_reference')

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        for field in ('tenant', 'site', 'location'):
            self.fields[field].queryset = self.fields[field].queryset.restrict(user, 'view')

    def clean(self):
        data = super().clean()
        if not self.errors:
            instance = Drawing(**{key: data[key] for key in self.Meta.fields})
            validate_context(instance, self.user)
        return data
