# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ims', '0008_auto_20151112_0719'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='productcategory',
            options={'ordering': ['category']},
        ),
        migrations.AlterField(
            model_name='productcategory',
            name='category',
            field=models.CharField(default=b'', unique=True, max_length=100),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='productinformation',
            name='code',
            field=models.CharField(default=b'', max_length=36, serialize=False, primary_key=True, help_text=b'Unique code for this product'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='productinformation',
            name='unitOfMeasure',
            field=models.CharField(default=b'EACH', help_text=b'How are these measured (EACH, BOX, ...)?', max_length=10, choices=[(b'BAG', b'BAG'), (b'BALE', b'BALE'), (b'BOTTLE', b'BOTTLE'), (b'BOX', b'BOX'), (b'CARTON', b'CARTON'), (b'CASE', b'CASE'), (b'EACH', b'EACH'), (b'GALLONS', b'GALLONS'), (b'LITERS', b'LITERS'), (b'OUNCES', b'OUNCES'), (b'PACKAGE', b'PACKAGE'), (b'PAIRS', b'PAIRS'), (b'POUNDS', b'POUNDS'), (b'QUARTS', b'QUARTS'), (b'ROLLS', b'ROLLS')]),
            preserve_default=True,
        ),
    ]
