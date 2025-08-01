# Generated by Django 4.2.7 on 2025-05-01 16:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('minecraft_app', '0010_userpurchase_gifted_by_userpurchase_is_gift'),
    ]

    operations = [
        migrations.AddField(
            model_name='rank',
            name='features',
            field=models.TextField(blank=True, help_text='Enter features, one per line. These will be displayed as bullet points.'),
        ),
        migrations.AlterField(
            model_name='userpurchase',
            name='amount',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
    ]
