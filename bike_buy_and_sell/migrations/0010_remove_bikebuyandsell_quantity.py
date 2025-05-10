from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bike_buy_and_sell', '0009_alter_chatmessage_options_chatmessage_assigned_to_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='bikebuyandsell',
            name='quantity',
        ),
    ]
