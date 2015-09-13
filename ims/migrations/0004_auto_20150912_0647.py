# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ims', '0003_productinformation_originalpicturename'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productinformation',
            name='originalPictureName',
            field=models.CharField(default=None, max_length=256, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='productinformation',
            name='picture',
            field=models.ImageField(help_text=b'Picture of this product', max_length=256, null=True, upload_to=b'inventory_pictures/%Y/%m', blank=True),
            preserve_default=True,
        ),
    ]
