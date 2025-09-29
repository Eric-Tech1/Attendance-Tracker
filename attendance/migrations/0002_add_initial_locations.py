from django.db import migrations

def add_locations(apps, schema_editor):
    Location = apps.get_model("attendance", "Location")

    # Insert your predefined locations/coordinates here
    Location.objects.create(name="ICT Lab", latitude=7.3775, longitude=3.9470)
    Location.objects.create(name="Hardware Lab", latitude=7.3780, longitude=3.9500)
    Location.objects.create(name="Software Lab", latitude=7.3800, longitude=3.9520)

def remove_locations(apps, schema_editor):
    Location = apps.get_model("attendance", "Location")
    Location.objects.filter(name__in=["ICT Lab", "Hardware Lab", "Software Lab"]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_locations, remove_locations),
    ]
