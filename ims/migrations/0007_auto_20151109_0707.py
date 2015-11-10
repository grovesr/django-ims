# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ims', '0006_auto_20151107_1549'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productinformation',
            name='code',
            field=models.CharField(default=b'', max_length=32, serialize=False, primary_key=True, help_text=b'Unique Red Cross code for this product'),
            preserve_default=True,
        ),
    ]
