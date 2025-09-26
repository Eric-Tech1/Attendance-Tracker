from django.db import migrations


def add_default_locations(apps, schema_editor):
    Location = apps.get_model('attendance', 'Location')
    default_locations = [
        ("ICT Lab", 6.5244, 3.3792, 50),      # Example coords (update with real ones)
        ("Hardware Lab", 6.5245, 3.3793, 50),
        ("Software Lab", 6.5246, 3.3794, 50),
    ]

    for name, lat, lng, radius in default_locations:
        Location.objects.get_or_create(
            name=name,
            defaults={
                "latitude": lat,
                "longitude": lng,
                "allowed_radius": radius
            }
        )


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0001_initial"),  # change to your actual initial migration
    ]

    operations = [
        migrations.RunPython(add_default_locations),
    ]
