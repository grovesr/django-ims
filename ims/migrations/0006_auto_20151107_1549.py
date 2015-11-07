# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ims', '0005_auto_20150913_0927'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productinformation',
            name='category',
            field=models.ForeignKey(blank=True, to='ims.ProductCategory', help_text=b'Category', null=True),
            preserve_default=True,
        ),
    ]
