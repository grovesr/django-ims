=====
IMS
=====

IMS is a simple Django app to for managing inventory.  IMS stands for
Inventory Management System.  The base models are:
Site - location where inventory is stored
ProductInformation - description of inventory types
InventoryItem - record recording the status of a product at a site

Detailed documentation is in the "docs" directory.

Quick start
-----------

1. Add "ims" to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = (
        ...
        'ims',
    )

2. Include the ims URLconf in your project urls.py like this::

    url(r'^ims/', include('ims.urls')),

3. Run `python manage.py migrate` to create the ims models.

4. Start the development server and visit http://127.0.0.1:8000/admin/
   to administer the ims models (you'll need the Admin app enabled).

5. Visit http://127.0.0.1:8000/ims/ to work with inventory.

6. To test run run_tests.py
