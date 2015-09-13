# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ims', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='productinformation',
            name='picture',
            field=models.ImageField(help_text=b'Picture of this product', null=True, upload_to=b'inventory_pictures/%Y/%m', blank=True),
            preserve_default=True,
        ),
    ]
