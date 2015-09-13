# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ims', '0002_productinformation_picture'),
    ]

    operations = [
        migrations.AddField(
            model_name='productinformation',
            name='originalPictureName',
            field=models.CharField(default=None, max_length=100, blank=True),
            preserve_default=True,
        ),
    ]
