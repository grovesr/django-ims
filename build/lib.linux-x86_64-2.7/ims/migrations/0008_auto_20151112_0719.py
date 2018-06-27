# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ims', '0007_auto_20151109_0707'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productinformation',
            name='code',
            field=models.CharField(default=b'', max_length=36, serialize=False, primary_key=True, help_text=b'Unique Red Cross code for this product'),
            preserve_default=True,
        ),
    ]
