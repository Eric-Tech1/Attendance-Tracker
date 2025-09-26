from django import forms
from .models import Student, Location, AttendanceRecord
from django.contrib.auth.models import User


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ["first_name", "last_name", "matric_no", "department"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "First Name"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Last Name"}),
            "matric_no": forms.TextInput(attrs={"class": "form-control", "placeholder": "Matric Number"}),
            "department": forms.TextInput(attrs={"class": "form-control", "placeholder": "Department"}),
        }

class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'latitude', 'longitude', 'allowed_radius']


class AttendanceRecordForm(forms.ModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ['student', 'status', 'check_in', 'check_out', 'latitude', 'longitude']


class DateRangeForm(forms.Form):
    start_date = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
