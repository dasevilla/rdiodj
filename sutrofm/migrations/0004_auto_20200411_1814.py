# Generated by Django 3.0.4 on 2020-04-11 18:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sutrofm', '0003_auto_20200410_2331'),
    ]

    operations = [
        migrations.AddField(
            model_name='party',
            name='last_manager_check_in',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='party',
            name='last_manager_uuid',
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
