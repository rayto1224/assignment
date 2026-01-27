# importer/forms.py
from django import forms
from .models import ImportTask

class CSVUploadForm(forms.ModelForm):
    class Meta:
        model = ImportTask
        fields = ['uploaded_file']