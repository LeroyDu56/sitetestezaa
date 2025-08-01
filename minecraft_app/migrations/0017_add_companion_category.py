# Créez un nouveau fichier de migration : minecraft_app/migrations/0017_add_companion_category.py

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('minecraft_app', '0016_rank_duration_type_rank_exclude_from_discounts_and_more'),
    ]

    operations = [
        # Modifier les choix de catégorie pour inclure 'companion'
        migrations.AlterField(
            model_name='storeitem',
            name='category',
            field=models.CharField(
                choices=[
                    ('collectible', 'Collectible'),
                    ('cosmetic', 'Cosmetic'),
                    ('utility', 'Utility'),
                    ('special', 'Special'),
                    ('companion', 'Compagnon'),
                ],
                default='collectible',
                max_length=20
            ),
        ),
        # Ajouter le champ pet_permission
        migrations.AddField(
            model_name='storeitem',
            name='pet_permission',
            field=models.CharField(
                blank=True,
                help_text='Pour les compagnons: nom du pet (ex: dragon, chat, loup). La permission sera automatiquement: advancedpets.pet.<nom>',
                max_length=100,
                null=True
            ),
        ),
    ]