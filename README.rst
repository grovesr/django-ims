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

6. To run tests, you must have the following at the same level as ims:
   run_test.py
   .secret_file.json
   ./ims_tests
     __init__.py
     test_settings.py
     tests.py
   ./templates
     /base
       base.html
       
7. .secret_file.json should include the following information set for your
    environment
    {
        "IMS_SECRET":"secret_key",
        "IMS_DB":"dbName",
        "IMS_DB_USER":"dbUserName",
        "IMS_DB_PASS":"dbPassword"
    }
       
8. to run the tests:
   python run_test.py