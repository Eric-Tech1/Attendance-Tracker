from django.db import models
from django.contrib.auth.models import User


class Location(models.Model):
    name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    allowed_radius = models.IntegerField(default=50, help_text="Radius in meters")

    def __str__(self):
        return f"{self.name} ({self.latitude}, {self.longitude})"


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=30, default="Unknown")
    last_name = models.CharField(max_length=30, default="Unknown")
    matric_no = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.matric_no} - {self.first_name} {self.last_name}"


class AttendanceRecord(models.Model):
    STATUS_CHOICES = (
        ('Present', 'Present'),
        ('Absent', 'Absent'),
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        null=True,      # allow null for smoother migrations
        blank=True
    )
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        student_name = self.student.matric_no if self.student else "Unknown"
        return f"{student_name} - {self.date} - {self.status}"
