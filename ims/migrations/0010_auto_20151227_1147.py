# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2015-12-27 16:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ims', '0009_auto_20151115_0846'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productinformation',
            name='originalPictureName',
            field=models.CharField(blank=True, default=b'', max_length=256),
        ),
    ]
