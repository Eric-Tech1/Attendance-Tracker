from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0007_alter_attendancerecord_location'),  # adjust if last migration number is different
    ]

    operations = [
        migrations.AddField(
            model_name='attendancerecord',
            name='location',
            field=models.ForeignKey(
                to='attendance.location',
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
            ),
        ),
    ]
