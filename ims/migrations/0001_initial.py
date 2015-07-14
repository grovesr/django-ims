# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='InventoryItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('quantity', models.IntegerField(default=0, help_text=b'Number of inventory units (each, boxes, cases, ...) of this type at the site containing this product')),
                ('deleted', models.BooleanField(default=False)),
                ('modified', models.DateTimeField(default=None, help_text=b'last modified on this date', blank=True)),
                ('modifiedMicroseconds', models.IntegerField(default=0, help_text=b'modification microsecond offset')),
                ('modifier', models.CharField(default=b'admin', help_text=b'user that last modified this record', max_length=50, blank=True)),
            ],
            options={
                'get_latest_by': 'modified',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ProductInformation',
            fields=[
                ('unitOfMeasure', models.CharField(default=b'EACH', help_text=b'How are these measured (EACH, BOX, ...)?', max_length=10, choices=[(b'BALE', b'BALE'), (b'BOX', b'BOX'), (b'CARTON', b'CARTON'), (b'CASE', b'CASE'), (b'EACH', b'EACH'), (b'PACKAGE', b'PACKAGE')])),
                ('code', models.CharField(default=b'D11', max_length=10, serialize=False, primary_key=True, help_text=b'Unique Red Cross code for this product')),
                ('name', models.CharField(default=b'', help_text=b'Name of this product', max_length=50)),
                ('expendable', models.BooleanField(default=False, help_text=b'Is this product expendable?')),
                ('quantityOfMeasure', models.IntegerField(default=1, help_text=b'How many individual items in each package?')),
                ('costPerItem', models.DecimalField(decimal_places=2, default=0.0, max_digits=7, blank=True, help_text=b'How much does each individual item cost?', null=True)),
                ('cartonsPerPallet', models.IntegerField(default=0, help_text=b'How many of these units fit on one pallet?', null=True, blank=True)),
                ('doubleStackPallets', models.BooleanField(default=False, help_text=b'Can pallets containing these products be stacked?')),
                ('warehouseLocation', models.CharField(default=b'', max_length=10, null=True, help_text=b'location of this item in the warehouse', blank=True)),
                ('canExpire', models.BooleanField(default=False, help_text=b'Can this product expire?')),
                ('expirationDate', models.DateField(help_text=b'What is the expiration date, if any?', null=True, blank=True)),
                ('expirationNotes', models.TextField(default=b'', help_text=b'Special expiration notes for this product', null=True, blank=True)),
                ('modified', models.DateTimeField(default=None, help_text=b'last modified on this date', blank=True)),
                ('modifiedMicroseconds', models.IntegerField(default=0, help_text=b'modification microsecond offset')),
                ('modifier', models.CharField(default=b'admin', help_text=b'user that last modified this record', max_length=50, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Site',
            fields=[
                ('number', models.AutoField(help_text=b'unique site number', serialize=False, primary_key=True)),
                ('name', models.CharField(default=b'', help_text=b'Name of this site', max_length=50)),
                ('county', models.CharField(default=b'', help_text=b'County where site is located', max_length=50)),
                ('address1', models.CharField(default=b'', help_text=b'First street address of this site', max_length=50)),
                ('address2', models.CharField(default=b'', max_length=50, null=True, help_text=b'Second street address of this site', blank=True)),
                ('address3', models.CharField(default=b'', max_length=50, null=True, help_text=b'Third street address of this site', blank=True)),
                ('contactName', models.CharField(default=b'', help_text=b'Primary contact name', max_length=50)),
                ('contactPhone', models.CharField(default=b'', help_text=b'Primary contact phone number', max_length=25)),
                ('notes', models.TextField(default=b'', help_text=b'Additional information about the site', null=True, blank=True)),
                ('modified', models.DateTimeField(default=None, help_text=b'last modified on this date', blank=True)),
                ('modifiedMicroseconds', models.IntegerField(default=0, help_text=b'modification microsecond offset')),
                ('modifier', models.CharField(default=b'admin', help_text=b'user that last modified this record', max_length=50, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='information',
            field=models.ForeignKey(help_text=b'The detailed information about this product type', to='ims.ProductInformation'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='site',
            field=models.ForeignKey(help_text=b'The site containing this inventory', to='ims.Site'),
            preserve_default=True,
        ),
    ]
