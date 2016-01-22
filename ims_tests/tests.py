from django.test import TestCase, RequestFactory
from unittest import skip
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User, Permission
from django.contrib.sessions.middleware import SessionMiddleware
from collections import OrderedDict
from urllib import urlencode
import os 
import StringIO
import re
import logging
from ims.models import Site, ProductInformation, InventoryItem, ProductCategory
from ims.views import (inventory_delete_all, site_delete_all, product_delete_all,
site_delete, product_delete, product_add, site_add, site_detail, 
site_add_inventory, products_add_to_site_inventory, product_detail,
product_select_add_site)
from ims.settings import PAGE_SIZE, APP_DIR
import zipfile
logging.disable(logging.CRITICAL)

# test helper functions
def create_inventory_item_for_site(site=None,
                                     product=None,
                                     quantity=1,
                                     deleted=0,
                                     modifier='none'):
    if not site:
        site=Site(name="test site 1",
                  modifier=modifier)
        site.save()
    if not product:
        product=ProductInformation(name="test product 1",
                                   code="pdt1",
                                   modifier=modifier,)
        product.save()
    inventoryItem=site.add_inventory(product=product,
                                    quantity=quantity,
                                    deleted=deleted,
                                    modifier=modifier,)
    return site, product, inventoryItem

def create_products_with_inventory_items_for_sites(numSites=1,
                                                   numProducts=1,
                                                   numItems=1,
                                                   modifier='none',
                                                   uniqueCategories=False):
    sitesList=[]
    productList=[]
    inventoryItemList=[]
    categoryList=[]
    for s in range(numSites):
        siteName="test site "+str(s+1)
        site=Site(name=siteName,)
        site.save()
        sitesList.append(site)
        for p in range(numProducts):
            productName="test product "+str(p+1)
            productCode="pdt"+str(p+1)
            if uniqueCategories:
                categoryName="category-" + str(p+1)
            else:
                categoryName="category-1"
            category, created = ProductCategory.objects.get_or_create(category = categoryName)
            if created:
                category.save()
                categoryList.append(category)
            product, created=ProductInformation.objects.get_or_create(name=productName,
                                       code=productCode,
                                       category=category)
            if created:
                product.save()
                productList.append(product)
            for i in range(numItems):
                # increment the quantity for each addition of a new item for 
                # the same product code, so we can distinguish them
                site,product,inventoryItem=create_inventory_item_for_site(
                                            site=site,
                                            product=product,
                                            quantity=i+1,
                                            deleted=0,
                                            modifier=modifier)
                inventoryItemList.append(inventoryItem)
    return sitesList,productList,inventoryItemList,categoryList

def get_announcement_from_response(response=None, cls=None):
    if response and cls:
        m=re.search(('^.*<div\s*id="announcement".*?<p.*?class="' +
                    cls + '">\s*<i .*?</i>\s*<i .*?</i>\s*(.*?)\s*</p>.*?</div>'),
                    response.content, re.S)
        if m and len(m.groups()) > 0:
            return m.groups()[0].replace('\n','')
    return ''

def add_session_to_request(request):
    """Annotate a request object with a session"""
    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()


class SiteMethodTests(TestCase):
    """
    ims_tests for Site instance methods
    """
    
    #Site inventory ims_tests
    def test_latest_inventory_after_initial_creation(self):
        """
        site.latest_inventory should only return the latest change
        """
        print 'running SiteMethodTests.test_latest_inventory_after_initial_creation... '
        (createdSites,
         __,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        #latest_inventory is a queryset of all the most recent changes to the
        #site's inventory.  
        latestInventory=[]
        for site in createdSites:
            latestInventory += site.latest_inventory()
        
        sortedCreatedInventory=[]
        for site in createdSites:
            for item in site.inventoryitem_set.all():
                sortedCreatedInventory.append(item.create_key())
        sortedCreatedInventory.sort()
        sortedLatestInventory=[]
        for item in latestInventory:
            sortedLatestInventory.append(item.create_key())
        # make sure we return only one thing, since we only added one thing
        self.assertListEqual(sortedLatestInventory,
             sortedCreatedInventory,
             'created inventory in database doesn''t match created inventory')
        
    def test_latest_inventory_after_deletion(self):
        """
        site.latest_inventory should only return the latest change, and should
        not return any deleted items
        """
        print 'running SiteMethodTests.test_latest_inventory_after_deletion... '
        (createdSites,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        # indicate that the just added item is deleted
        create_inventory_item_for_site(site=createdSites[0],
                                       product=createdProducts[0],
                                       deleted=1)
        #latest_inventory is a queryset of all the most recent changes to the
        #site's inventory
        latestInventory=createdSites[0].latest_inventory()
        # latest_inventory is a queryset of all the most recent changes to the
        # site's inventory.  Check that a deleted item doesn't show up in
        # inventory
        with self.assertRaises(InventoryItem.DoesNotExist):
            latestInventory.get(information_id=createdProducts[0].pk)
     
    def test_latest_inventory_after_3_quantity_change(self):
        """
        site.latest_inventory should only return the latest change
        """
        print 'running SiteMethodTests.test_latest_inventory_after_3_quantity_change... '
        (createdSites,
         createdProducts,
         createdInventoryItems,
         createdCategories)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=3)
        # latest_inventory is a queryset of all the most recent changes to the
        # site's inventory.
        latestInventory=createdSites[0].latest_inventory()
        # check that the inventoryItem that we just added 
        # and then changed several times has the appropriate final quantity
        self.assertEqual(latestInventory.get(
                         information_id=createdProducts[0].pk).create_key(),
                         createdInventoryItems.pop().create_key())
        self.assertEqual(latestInventory.get(
                         information_id=createdProducts[0].pk).information.category.pk, 
                         createdCategories.pop().pk)
         
    def test_latest_inventory_after_3_quantity_change_and_deletion(self):
        """
        site.latest_inventory should only return the latest change and not
        return any deleted items.
        """
        print 'running SiteMethodTests.test_latest_inventory_after_3_quantity_change_and_deletion... '
        (createdSites,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=3)
        # indicate that the just added item is deleted
        create_inventory_item_for_site(site=createdSites[0],
                                       product=createdProducts[0],
                                       deleted=1)
        #latest_inventory is a queryset of all the most recent changes to the
        #site's inventory
        latestInventory=createdSites[0].latest_inventory()
        # Check that a deleted InventoryItem doesn't show up
        # in inventory
        with self.assertRaises(InventoryItem.DoesNotExist):
            latestInventory.get(information_id=createdProducts[0].pk)
         
    def test_inventory_set_after_3_changes(self):
        """
        InventoryItem history of changes should be retained in the database
        """
        print 'running SiteMethodTests.test_inventory_set_after_3_changes... '
        (createdSites,
         __,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=3)
        self.assertEqual(createdSites[0].inventoryitem_set.all().count(),3)
         
    def test_latest_inventory_after_deletion_and_re_addition(self):
        """
        site.latest_inventory should only return the latest change and not
        return any deleted items. If an item is deleted and then re-added, we
        should always see the last change
        """
        print 'running SiteMethodTests.test_latest_inventory_after_deletion_and_re_addition... '
        (createdSites,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        # indicate that the just added item is deleted
        create_inventory_item_for_site(site=createdSites[0],
                                       product=createdProducts[0],
                                       deleted=1)
        #latest_inventory is a queryset of all the most recent changes to the
        #site's inventory
        (__,
         __,
         lastItemChange)=create_inventory_item_for_site(
                            site=createdSites[0],
                            product=createdProducts[0],
                            quantity=100)
        # latest_inventory is a queryset of all the most recent changes to the
        # site's inventory.
        latestInventory=createdSites[0].latest_inventory()
        # Check that we still have inventory after a deletion
        # and re-addition
        self.assertEqual(
            latestInventory.get(
            information_id=createdProducts[0].pk).create_key(),
            lastItemChange.create_key())
        
    def test_latest_inventory_3_products_after_3_changes(self):
        """
        site.latest_inventory should only return the latest changes
        """
        print 'running SiteMethodTests.test_latest_inventory_3_products_after_3_changes... '
        (createdSites,
         createdProducts,
         createdInventoryItems,
         createdCategories)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=3,
                                numItems=3,
                                uniqueCategories=False,
                                )
        # latest_inventory is a queryset of all the most recent changes to the
        # site's inventory.
        latestInventory=createdSites[0].latest_inventory()
        self.assertEqual(
         latestInventory.get(information_id=createdProducts[0].pk).create_key(),
         createdInventoryItems[3*1-1].create_key())
        self.assertEqual(
         latestInventory.get(information_id=createdProducts[1].pk).create_key(),
         createdInventoryItems[3*2-1].create_key())
        self.assertEqual(
         latestInventory.get(information_id=createdProducts[2].pk).create_key(),
         createdInventoryItems[3*3-1].create_key())
        self.assertEqual(
         latestInventory.get(information_id=createdProducts[0].pk).information.category.pk,
         createdCategories.pop().pk)
    
    def test_parse_sites_from_xls_initial(self):
        """
        import 3 sites from Excel
        """
        print 'running SiteMethodTests.test_parse_sites_from_xls_initial... '
        filename=os.path.join(APP_DIR,
                              'testData/sites_add_site1_site2_site3.xls')
        importedSites,__=Site.parse_sites_from_xls(filename=filename, 
                                                            modifier='none',
                                                            save=True)
        self.assertNotEqual(importedSites,
                            None,
                            'Failure to import sites from excel')
        queriedSites=Site.objects.all()
        # check that we saved 3 sites
        self.assertEqual(
            queriedSites.count(),
            3,
            'Number of imported sites mismatch. Some sites didn''t get stored.')
        
        # check that the site modifiers are correctly stored
        sortedImportedSites=[]
        for site in importedSites:
            sortedImportedSites.append(site.create_key())
        sortedImportedSites.sort()
        sortedQueriedSites=[]
        for site in queriedSites:
            sortedQueriedSites.append(site.create_key())
        sortedQueriedSites.sort()
        self.assertListEqual(sortedImportedSites,
                             sortedQueriedSites,
                             'Imported sites don''t match the stored sites')
    
    def test_parse_sites_from_xls_with_dups(self):
        """
        import 3 sites from Excel, plus one duplicate site
        """
        print 'running SiteMethodTests.test_parse_sites_from_xls_with_dups... '
        filename=os.path.join(APP_DIR,
                              'testData/sites_add_site1_site2_site3_site3.xls')
        importedSites,__=Site.parse_sites_from_xls(filename=filename, 
                                                            modifier='none',
                                                            save=True)
        self.assertNotEqual(importedSites,
                            None,
                            'Failure to import sites from excel')
        queriedSites=Site.objects.all()
        # check that we only saved 3 sites
        self.assertEqual(
            queriedSites.count(),
            3,
            'You stored a duplicate site as a separate entity.')
    
    def test_parse_sites_from_xls_with_bad_header(self):
        """
        import 3 sites from Excel but use a file with invalid headers
        """
        print 'running SiteMethodTests.test_parse_sites_from_xls_with_bad_header... '
        filename=os.path.join(APP_DIR,
                              'testData/products_add_prod1_prod2_prod3.xls')
        __, siteMessage=Site.parse_sites_from_xls(filename=filename, 
                                                             modifier='none',
                                                             save=True)
        self.assert_(
        'Xlrdutils' in siteMessage,
        ('Failure to recognize a file with bad headers.\nSite.parse_sites_from_xls returned: %s'
         % siteMessage))
    
    def test_import_parse_from_xls_with_bad_date(self):
        """
        import 3 sites from Excel but use a file with a bad date format
        """
        print 'running SiteMethodTests.test_parse_sites_from_xls_with_bad_date... '
        filename=os.path.join(
                        APP_DIR,
                        'testData/sites_add_site1_site2_site3_bad_date.xls')
        __, siteMessage=Site.parse_sites_from_xls(filename=filename, 
                                                             modifier='none',
                                                             save=True)
        self.assert_('Xlrdutils' in siteMessage,
                     ('Failure to recognize a file with bad date format.\nSite.parse_sites_from_xls returned: %s'
                      % siteMessage))
    
class ProductInformationMethodTests(TestCase):
    """
    ProductInformation class method ims_tests
    """
    
    def test_num_sites_containing_with_3_sites(self):
        print 'running ProductInformationMethodTests.test_num_sites_containing_with_3_sites... '
        (__,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=3,
                                numProducts=1,
                                numItems=1)
        product = createdProducts[0]
        self.assertEqual(product.num_sites_containing(), 3)
        
    def test_num_sites_containing_with_3_sites_after_inventory_change(self):
        print 'running ProductInformationMethodTests.test_num_sites_containing_with_3_sites_after_inventory_change... '
        (__,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=3,
                                numProducts=1,
                                numItems=2)
        product = createdProducts[0]
        self.assertEqual(product.num_sites_containing(), 3)
        
    def test_parse_product_information_from_xls_initial(self):
        """
        import 3 products from Excel
        """
        print 'running ProductInformationMethodTests.test_parse_product_information_from_xls_initial... '
        filename=os.path.join(APP_DIR,
                              'testData/products_add_prod1_prod2_prod3.xls')
        (importedProducts,
         __)=ProductInformation.parse_product_information_from_xls(
                         filename=filename, 
                         modifier='none',
                         save=True)
        self.assertNotEqual(importedProducts,
                            None,
                            'Failure to import products from Excel')
        queriedProducts=ProductInformation.objects.all()
        # check that we saved 3 sites
        self.assertEqual(queriedProducts.count(),
                         3,
                         'Number of imported products mismatch. \
                         Some product didn''t get stored.')
        
        # check that the product modifiers are correctly stored
        sortedImportedProducts=[]
        for product in importedProducts:
            sortedImportedProducts.append(product.create_key())
        sortedImportedProducts.sort()
        sortedQueriedProducts=[]
        for product in queriedProducts:
            sortedQueriedProducts.append(product.create_key())
        sortedQueriedProducts.sort()
        self.assertListEqual(sortedImportedProducts, sortedQueriedProducts)
        
    def test_parse_product_information_from_xls_with_dups(self):
        """
        import 3 products from Excel, plus one duplicate product
        """
        print 'running ProductInformationMethodTests.test_parse_product_information_from_xls_with_dups... '
        filename=os.path.join(APP_DIR,
                              'testData/products_add_prod1_prod2_prod3_prod3.xls')
        (importedProducts,
         __)=ProductInformation.parse_product_information_from_xls(
                      filename=filename, 
                      modifier='none',
                      save=True)
        self.assertNotEqual(importedProducts,
                            None,
                            'Failure to import products from excel')
        queriedProducts=ProductInformation.objects.all()
        # check that we only saved 3 products
        self.assertTrue(
            queriedProducts.count() < 4,
            'You stored a duplicate product as a separate entity.')
        
    def test_parse_product_information_from_xls_with_bad_header(self):
        """
        import 3 products from Excel but use a file with invalid headers
        """
        print 'running ProductInformationMethodTests.test_parse_product_information_from_xls_with_bad_header... '
        filename=os.path.join(APP_DIR,
                              'testData/sites_add_site1_site2_site3.xls')
        (__,
         productMessage)=ProductInformation.parse_product_information_from_xls(
                         filename=filename, 
                         modifier='none',
                         save=True)
        self.assert_(
        'Xlrdutils' in productMessage,
        ('Failure to recognize a file with bad headers.\nProductInformation.parse_product_information_from_xls returned: %s'
         % productMessage))
    
    def test_parse_product_information_from_xls_with_bad_date(self):
        """
        import 3 products from Excel but use a file with a bad date format
        """
        print 'running ProductInformationMethodTests.test_parse_product_information_from_xls_with_bad_date... '
        filename=os.path.join(
                        APP_DIR,
                        'testData/products_add_prod1_prod2_prod3_bad_date.xls')
        (__,
         productMessage)=ProductInformation.parse_product_information_from_xls(
                      filename=filename, 
                      modifier='none',
                      save=True)
        self.assert_('Xlrdutils' in productMessage,
                     ('Failure to recognize a file with bad date format.\nProductInformation.parse_product_information_from_xls returned: %s'
                      % productMessage))
        
class InventoryItemMethodTests(TestCase):
    """
    InventoryItem class method ims_tests
    """
        
    def test_parse_inventory_from_xls_initial(self):
        """
        import 3 inventory items to 3 sites from Excel
        """
        print 'running InventoryItemMethodTests.test_parse_inventory_from_xls_initial... '
        for number in range(3):
            #create three sites
            siteName = 'test site %d' % (number + 1)
            siteNumber = number + 1
            site=Site(name = siteName,
                      number = siteNumber,
                      modifier = 'none')
            site.save()
        for number in range(3):
            #create three products
            productName="test product %d" % (number+1)
            productCode="pdt%d" % (number+1)
            product=ProductInformation(name=productName,
                                       code=productCode,
                                       modifier='none')
            product.save()
        filename=os.path.join(APP_DIR,
                              'testData/sites_add_site1_site2_site3.xls')
        Site.parse_sites_from_xls(filename=filename,  
                                    modifier='none',
                                    save=True)
        filename=os.path.join(APP_DIR,
                              'testData/products_add_prod1_prod2_prod3.xls')
        ProductInformation.parse_product_information_from_xls(filename=filename, 
                                                              modifier='none',
                                                              save=True)
        filename=os.path.join(
                 APP_DIR,
                 'testData/inventory_add_10_to_site1_site2_site3_prod1_prod2_prod3.xls')
        (importedInventoryItems,
         __)=InventoryItem.parse_inventory_from_xls(
                           filename=filename, 
                           modifier='none',
                           save=True)
        self.assertNotEqual(importedInventoryItems,
                            None,
                            'Failure to import inventory from Excel')
        self.assertEqual(len(importedInventoryItems),
                         9,
                         'Failure to create one or more inventoryItems.  Missing associated Site or ProductInformation?')
        queriedInventoryItems=InventoryItem.objects.all()
        # check that we saved 3 sites
        self.assertEqual(queriedInventoryItems.count(),
                         3*3,
                         'Total inventory mismatch.  Some InventoryItems didn''t get stored.')
        
        # check that the inventory IDs are correctly stored
        sortedImportedInventoryItems=[]
        for item in importedInventoryItems:
            sortedImportedInventoryItems.append(item.create_key())
        sortedImportedInventoryItems.sort()
        sortedQueriedInventoryItems=[]
        for item in queriedInventoryItems:
            sortedQueriedInventoryItems.append(item.create_key())
        sortedQueriedInventoryItems.sort()
        self.assertListEqual(sortedImportedInventoryItems,
                             sortedQueriedInventoryItems,
                             'Imported inventory doesn''t match stored inventory')
        
    def test_parse_inventory_from_xls_with_dups(self):
        """
        import 3 inventory items to 3 sites from Excel
        """
        print 'running InventoryItemMethodTests.test_parse_inventory_from_xls_initial... '
        for number in range(3):
            #create three sites
            siteName = 'test site %d' % (number + 1)
            siteNumber = number + 1
            site=Site(name = siteName,
                      number = siteNumber,
                      modifier = 'none')
            site.save()
        for number in range(3):
            #create three products
            productName="test product %d" % (number+1)
            productCode="pdt%d" % (number+1)
            product=ProductInformation(name=productName,
                                       code=productCode,
                                       modifier='none')
            product.save()
        filename=os.path.join(
                 APP_DIR,
                 'testData/inventory_add_10_to_site1_site2_site3_prod1_prod2_prod3_dups.xls')
        (importedInventoryItems,
         __)=InventoryItem.parse_inventory_from_xls(
                           filename=filename, 
                           modifier='none',
                           save=True)
        self.assertNotEqual(importedInventoryItems,
                            None,
                            'Failure to import inventory from Excel')
        queriedInventory=InventoryItem.objects.all()
        # check that we only saved 9 inventory items
        self.assertEqual(
            queriedInventory.count(), 10,
            'You didn''t store all all the inventory items')
        
    def test_parse_inventory_from_xls_with_bad_header(self):
        """
        import 3 inventory items to 3 sites from Excel file with a bad header
        """
        print 'running InventoryItemMethodTests.test_parse_inventory_from_xls_with_bad_header... '
        filename=os.path.join(APP_DIR,
                              'testData/products_add_prod1_prod2_prod3.xls')
        (__,
         inventoryMessage)=InventoryItem.parse_inventory_from_xls(
                           filename=filename, 
                           modifier='none',
                           save=True)
        self.assert_('Xlrdutils' in inventoryMessage,
                     ('Failure to recognize a file with bad header format.\nInventoryItem.parse_inventory_from_xl returned: %s'
                      % inventoryMessage))
        
    def test_parse_inventory_from_xls_with_bad_date(self):
        """
        import 3 inventory items to 3 sites from Excel file with a bad header
        """
        print 'running InventoryItemMethodTests.test_parse_inventory_from_xls_with_bad_date... '
        filename=os.path.join(
                 APP_DIR,
                 'testData/inventory_add_10_to_site1_site2_site3_prod1_prod2_prod3_bad_date.xls')
        (__,
         inventoryMessage)=InventoryItem.parse_inventory_from_xls(
                           filename=filename, 
                           modifier='none',
                           save=True)
        self.assert_('Xlrdutils' in inventoryMessage,
                     ('Failure to recognize a file with bad date format.\nInventoryItem.parse_inventory_from_xl returned: %s'
                      % inventoryMessage))
        
@skip('No longer using IMS page view')
class HomeViewTests(TestCase):
    """
    ims_tests for Home view
    """
    
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    def test_home_for_latest_changes_1(self):
        """
        The home view should display sites with recently edited inventory with
        the latest changes at the top and latest inventory changes with the
        latest changes at the top as well
        """
        print 'running HomeViewTests.test_home_for_latest_changes_1... '
        self.client.login(username='testUser', password='12345678')
        (createdSites,
         __,
         createdInventoryItems,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=20,
                                numProducts=5,
                                numItems=1)
        response=self.client.get(reverse('ims:home'))
        sitesResponseList=[]
        itemsResponseList=[]
        for site in response.context['sitesList']:
            
            sitesResponseList.append(site.create_key())
        for item in response.context['inventoryList']:
            # include the timestamp to ensure uniqueness when comparing
            itemsResponseList.append(item.create_key())
        
        sortedCreatedSites=[]
        for site in createdSites:
            sortedCreatedSites.append(site.create_key())
        # compare the latest changed sites only
        sortedCreatedSites.reverse()
        # just retain the latest inventory changes to compare to the response
        latestInventoryItems=OrderedDict()
        sortedCreatedInventoryItems=[]
        createdInventoryItems.reverse()
        for item in createdInventoryItems:
            if not latestInventoryItems.has_key(item.information):
                latestInventoryItems[item.information]=item
        for item in latestInventoryItems.values():
            # include the timestamp to ensure uniqueness when comparing
            sortedCreatedInventoryItems.append(item.create_key())
        self.assertListEqual(sitesResponseList, sortedCreatedSites[:PAGE_SIZE])
        self.assertListEqual(itemsResponseList,
                             sortedCreatedInventoryItems[:PAGE_SIZE])
    
    def test_home_for_latest_changes_2(self):
        """
        The home view should display sites with recently edited inventory with
        the latest changes at the top and latest inventory changes with the
        latest changes at the top as well
        """
        print 'running HomeViewTests.test_home_for_latest_changes_2... '
        self.client.login(username='testUser', password='12345678')
        (createdSites,
         __,
         createdInventoryItems,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=20,
                                numProducts=5,
                                numItems=1)
        response=self.client.get(reverse('ims:home'))
        sitesResponseList=[]
        itemsResponseList=[]
        for site in response.context['sitesList']:
            
            sitesResponseList.append(site.create_key())
        for item in response.context['inventoryList']:
            # include the timestamp to ensure uniqueness when comparing
            itemsResponseList.append(item.create_key())
        
        sortedCreatedSites=[]
        for site in createdSites:
            sortedCreatedSites.append(site.create_key())
        # compare the latest changed sites only
        sortedCreatedSites.reverse()
        # just retain the latest inventory changes to compare to the response
        latestInventoryItems=OrderedDict()
        sortedCreatedInventoryItems=[]
        createdInventoryItems.reverse()
        for item in createdInventoryItems:
            if not latestInventoryItems.has_key(item.information):
                latestInventoryItems[item.information]=item
        for item in latestInventoryItems.values():
            # include the timestamp to ensure uniqueness when comparing
            sortedCreatedInventoryItems.append(item.create_key())
        self.assertListEqual(sitesResponseList, sortedCreatedSites[:PAGE_SIZE])
        self.assertListEqual(itemsResponseList,
                             sortedCreatedInventoryItems[:PAGE_SIZE])
        
    def test_home_for_no_inventory(self):
        """
        If there is no inventory, ims:home should display nothing
        """
        print 'running HomeViewTests.test_home_for_no_inventory... '
        self.client.login(username='testUser', password='12345678')
        response=self.client.get(reverse('ims:home'))
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('No inventory found', resultWarning,
                         'IMS Home view didn''t generate the correct warning when there is no inventory.\nactual warning message = %s' 
                         % resultWarning)
        
class InventoryHistoryViewTests(TestCase):
    """
    ims_tests for inventory_history view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
        
    def test_inventory_history_with_invalid_site(self):
        print 'running InventoryHistoryViewTests.test_inventory_history_with_invalid_site... '
        self.client.login(username='testUser', password='12345678')
        siteId = 1
        code="D11"
        response=self.client.get(reverse('ims:inventory_history',
                                 kwargs = 
                                  {'siteId':siteId,
                                   'code':code,}),
                                  follow=True)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('Unable to check inventory history.<br />Site %d does not exist' % 
                      siteId, resultError,
                      'IMS inventory_history view didn''t generate the correct warning when an invalid site was requested.\nactual message = %s' %
                      resultError)
    
    def test_inventory_history_with_invalid_code(self):
        print 'running InventoryHistoryViewTests.test_inventory_history_with_invalid_code... '
        self.client.login(username='testUser', password='12345678')
        siteId = 1
        code="D11"
        site=Site(number = siteId)
        site.save()
        response=self.client.get(reverse('ims:inventory_history',
                                 kwargs = 
                                  {'siteId':siteId,
                                   'code':code,}),
                                  follow=True)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('Unable to check inventory history.<br />Item %s does not exist' % 
                      code, resultError,
                      'IMS inventory_history view didn''t generate the correct warning when an invalid code was requested.\nactual message = %s' %
                      resultError)
    
    def test_inventory_history_with_valid_history(self):
        print 'running InventoryHistoryViewTests.test_inventory_history_with_valid_history... '
        self.client.login(username='testUser', password='12345678')
        # create initial inventory item
        site, product, __ = create_inventory_item_for_site(quantity=1)
        # change it to create a history
        site, product, __ = create_inventory_item_for_site(
                                       site = site,
                                       product = product,
                                       quantity=2)
        response=self.client.get(reverse('ims:inventory_history',
                                 kwargs = 
                                  {'siteId':site.number,
                                   'code':product.code,}),
                                  follow=True)
        self.assertEqual(response.status_code, 200,
                         'Inventory History generated a non-200 response code')
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertEqual(resultError, '',
                         'IMS inventory_history view generated an error with a valid request.\nactual message = %s' %
                          resultError)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertEqual(resultWarning, '',
                         'IMS inventory_history view generated a warning with a valid request.\nactual message = %s' %
                          resultWarning)
        resultInfo = get_announcement_from_response(response=response,
                                                       cls="infonote")
        self.assertEqual(resultInfo, '',
                         'IMS inventory_history view generated info with a valid request.\nactual message = %s' %
                          resultInfo)

class SitesViewTests(TestCase):
    """
    ims_tests for sites view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    def test_sites_get_with_no_sites(self):
        print 'running SitesViewTests.test_sites_get_with_no_sites... '
        self.client.login(username='testUser', password='12345678')
        response=self.client.get(reverse('ims:sites'),
                                  follow=True)
        self.assertEquals(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('No sites found',
                      'IMS sites view didn''t generate the correct warning when no sites were found.\nactual message = %s' %
                      resultWarning)
        
    def test_sites_get_with_filter_and_no_sites(self):
        print 'running SitesViewTests.test_products_get_with_filter_and_no_products... '
        self.client.login(username='testUser', password='12345678')
        response=self.client.get(reverse('ims:sites',) +
                                 '?searchField=name&searchValue=blah',
                                 follow = False,)
        self.assertEquals(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('No sites found',
                      'IMS sites view didn''t generate the correct warning when no sites were found.\nactual message = %s' %
                      resultWarning)
    
    def test_sites_get_with_sites(self):
        print 'running SitesViewTests.test_sites_get_with_sites... '
        self.client.login(username='testUser', password='12345678')
        site = Site(name='test site',)
        site.save()
        response=self.client.get(reverse('ims:sites',),
                                 follow = False,)
        self.assertEqual(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertEqual('', resultWarning)
        
    def test_sites_get_with_filter(self):
        print 'running SitesViewTests.test_sites_get_with_filter... '
        self.client.login(username='testUser', password='12345678')
        site = Site(name='test site',)
        site.save()
        response=self.client.get(reverse('ims:sites',) +
                                 '?searchField=name&searchValue=test',
                                 follow = False,)
        self.assertEqual(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertEqual('', resultWarning)
    
    def test_sites_get_with_bad_filter(self):
        print 'running SitesViewTests.test_sites_get_with_bad_filter... '
        self.client.login(username='testUser', password='12345678')
        site = Site(name='test site',)
        site.save()
        response=self.client.get(reverse('ims:sites',) +
                                 '?searchField=name&searchValue=blah',
                                 follow = False,)
        self.assertRedirects(response, reverse('ims:sites',) +
                                 '?page=1&pageSize=%d' % PAGE_SIZE, 
                                 status_code = 302,
                                 target_status_code = 200)
    
    def test_sites_post_add(self):
        print 'running SitesViewTests.test_sites_post_add... '
        perms = ['add_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:sites'),
                                  {'Add':''},
                                  follow=False)
        self.assertRedirects(response, reverse('ims:site_add'), 
                                 status_code = 302,
                                 target_status_code = 200)
        
    def test_sites_post_add_without_add_site_perm(self):
        print 'running SitesViewTests.test_sites_post_add_without_add_site_perm... '
        self.client.login(username='testUser', password='12345678')
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['0'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['0'],
                    'Add':'Add',}
        response=self.client.post(reverse('ims:sites',),
                                  postData,
                                  follow = False,)
        self.assertEquals(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to add sites', 
                      resultError,
                      'IMS sites view didn''t generate the correct error when an unauthorized user tried to add.\nactual message = %s' %
                      resultError)
        
    def test_sites_post_delete(self):
        print 'running SitesViewTests.test_sites_post_delete... '
        perms = ['delete_site', 'delete_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-Delete': ['on'],
                    'form-0-number': [site.number],
                    'Delete': ['Delete']}
        response=self.client.post(reverse('ims:sites'),
                                  postData,
                                  follow=False)
        self.assertRedirects(response, 
                             (reverse('ims:site_delete') + 
                              '?site=' + str(site.number) + '&'), 
                             status_code = 302,
                             target_status_code = 200)
        
    def test_sites_post_delete_without_delete_site_perms(self):
        print 'running SitesViewTests.test_sites_post_delete... '
        perms = [ 'delete_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-Delete': ['on'],
                    'form-0-number': [site.number],
                    'Delete': ['Delete']}
        response=self.client.post(reverse('ims:sites'),
                                  postData,
                                  follow=False)
        self.assertEquals(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to delete sites', 
                      resultError,
                      'IMS sites view didn''t generate the correct error when an unauthorized user tried to add.\nactual message = %s' %
                      resultError)

class ProductDeleteViewTests(TestCase):
    """
    ims_tests for product_delete view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    def test_product_delete_get_with_no_get_parms(self):
        print 'running ProductDeleteViewTests.test_product_delete_get_with_no_get_parms... '
        perms = [ 'delete_productinformation', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.get(reverse('ims:product_delete'),
                                  follow = False)
        self.assertEquals(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('No products requested for deletion',
                      resultWarning,
                      'IMS product_delete view didn''t generate the correct warning when no sites requested found.\nactual message = %s' %
                      resultWarning)
    
    def test_product_delete_get(self):
        print 'running ProductDeleteViewTests.test_product_delete_get... '
        perms = [ 'delete_productinformation', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        product = ProductInformation(name = 'test product',
                                     code = code)
        product.save()
        response=self.client.get(reverse('ims:product_delete') + '?' +
                                 urlencode({'code':code}),
                                  follow = False)
        self.assertEqual(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('Are you sure?',
                      resultWarning,
                      'IMS product_delete view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
         
    def test_product_delete_get_with_inventory(self):
        print 'running ProductDeleteViewTests.test_product_delete_get_with_inventory... '
        perms = [ 'delete_productinformation', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        (__,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=3)
        response=self.client.get(reverse('ims:product_delete') + '?' +
                                 urlencode({'code':createdProducts[0].pk}),
                                  follow = False)
        self.assertEquals(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('One or more products contain inventory.  Deleting the products will delete all inventory in all sites containing this product as well. Delete anyway?',
                      resultWarning,
                      'IMS product_delete view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
         
    def test_product_delete_get_without_delete_productinformation_perm(self):
        print 'running ProductDeleteViewTests.test_product_delete_get_without_delete_productinformation_perm... '
        perms = ['delete_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        product = ProductInformation(name = 'test product',
                                     code = code)
        product.save()
        response=self.client.get(reverse('ims:product_delete') + '?' +
                                 urlencode({'code':code}),
                                  follow = False)
        self.assertEquals(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                     cls="errornote")
        self.assertIn('You don''t have permission to delete products',
                      resultError,
                      'IMS product_delete view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
        
    def test_product_delete_get_without_delete_inventoryitem_perm(self):
        print 'running ProductDeleteViewTests.test_product_delete_get_without_delete_inventoryitem_perm... '
        perms = ['delete_productinformation',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        product = ProductInformation(name = 'test product',
                                     code = code)
        product.save()
        response=self.client.get(reverse('ims:product_delete') + '?' +
                                 urlencode({'code':code}),
                                  follow = False)
        self.assertEquals(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                     cls="errornote")
        self.assertIn('You don''t have permission to delete products',
                      resultError,
                      'IMS product_delete view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
         
    def test_product_delete_post_with_no_post_parms(self):
        print 'running ProductDeleteViewTests.test_product_delete_post_with_no_post_parms... '
        perms = [ 'delete_productinformation', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'Delete':'Delete'}
        request = self.factory.post(reverse('ims:product_delete'),
                                    postData, 
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = product_delete(request)
        response.client = self.client
        resultError = request.session['errorMessage']
        self.assertIn('No products requested for deletion',
                      resultError,
                      'IMS product_delete view didn''t generate the correct warning when no products requested found.\nactual message = %s' %
                      resultError)
        self.assertRedirects(response, reverse('ims:products') + '?' +
                             urlencode({'page':1,
                                        'pageSize':PAGE_SIZE,}), 
                             status_code = 302,
                             target_status_code = 200)
     
    def test_product_delete_post(self):
        print 'running ProductDeleteViewTests.test_product_delete_post... '
        perms = [ 'delete_productinformation', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        product = ProductInformation(name = 'test product',
                                     code = code)
        product.save()
        postData = {'Delete':'Delete',
                    'products':[product.code,]}
        request = self.factory.post(reverse('ims:product_delete'),
                                    postData, 
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = product_delete(request)
        response.client = self.client
        resultInfo = request.session['infoMessage']
        self.assertIn(('Successfully deleted product and associated inventory for product code %s with name "%s"<br/>' % 
                       (product.meaningful_code(), product.name)),
                      resultInfo,
                      'IMS product_delete view didn''t generate the correct info when product deleted.\nactual message = %s' %
                      resultInfo)
        self.assertRedirects(response, reverse('ims:products') + '?' +
                             urlencode({'page':1,
                                        'pageSize':PAGE_SIZE,}), 
                             status_code = 302,
                             target_status_code = 200)
        self.assertEqual(ProductInformation.objects.all().count(), 
                         0,
                         'Product still in database after deleting.')
     
    def test_product_delete_post_with_inventory(self):
        print 'running ProductDeleteViewTests.test_product_delete_post_with_inventory... '
        perms = [ 'delete_productinformation', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        (__,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=3)
        postData = {'Delete':'Delete',
                    'products':[createdProducts[0].code,]}
        request = self.factory.post(reverse('ims:product_delete'),
                                    postData, 
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = product_delete(request)
        response.client = self.client
        resultInfo = request.session['infoMessage']
        self.assertIn(('Successfully deleted product and associated inventory for product code %s with name "%s"<br/>' % 
                       (createdProducts[0].meaningful_code(), createdProducts[0].name)),
                      resultInfo,
                      'IMS product_delete view didn''t generate the correct info when product deleted.\nactual message = %s' %
                      resultInfo)
        self.assertRedirects(response, reverse('ims:products') + '?' +
                             urlencode({'page':1,
                                        'pageSize':PAGE_SIZE,}), 
                             status_code = 302,
                             target_status_code = 200)
        self.assertEqual(ProductInformation.objects.all().count(), 
                         0,
                         'Product still in database after deleting.')

    def test_product_delete_post_without_delete_productinformation_perm(self):
        print 'running ProductDeleteViewTests.test_product_delete_post_without_delete_productinformation_perm... '
        perms = ['delete_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        product = ProductInformation(name = 'test product',
                                     code = code)
        product.save()
        postData = {'Delete':'Delete',
                    'products':[product.code,]}
        response = self.client.post(reverse('ims:product_delete'),
                                    postData, 
                                    follow = False)
        self.assertEqual(response.status_code,200)
        resultError = get_announcement_from_response(response=response,
                                                     cls="errornote")
        self.assertIn('You don''t have permission to delete products',
                      resultError,
                      'IMS product_delete view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
        
    def test_product_delete_post_without_delete_inventoryitem_perm(self):
        print 'running ProductDeleteViewTests.test_product_delete_post_without_delete_inventoryitem_perm... '
        perms = ['delete_productinformation',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        product = ProductInformation(name = 'test product',
                                     code = code)
        product.save()
        postData = {'Delete':'Delete',
                    'products':[product.code,]}
        response = self.client.post(reverse('ims:product_delete'),
                                    postData, 
                                    follow = False)
        self.assertEqual(response.status_code,200)
        resultError = get_announcement_from_response(response=response,
                                                     cls="errornote")
        self.assertIn('You don''t have permission to delete products',
                      resultError,
                      'IMS product_delete view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
 
    def test_product_delete_post_cancel(self):
        print 'running ProductDeleteViewTests.test_product_delete_post_cancel... '
        perms = [ 'delete_productinformation', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        product = ProductInformation(name = 'test product',
                                     code = code)
        product.save()
        postData = {'Cancel':'Cancel',
                    'products':[code,]}
        response = self.client.post(reverse('ims:product_delete'),
                                    postData, 
                                    follow = False)
        self.assertRedirects(response, reverse('ims:products') + '?' + 
                             urlencode({'page':1,
                             'pageSize':1,}), 
                             status_code = 302,
                             target_status_code = 200)

class SiteDeleteViewTests(TestCase):
    """
    ims_tests for site_delete view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    def test_site_delete_get_with_no_get_parms(self):
        print 'running SiteDeleteViewTests.test_site_delete_get_with_no_get_parms... '
        perms = [ 'delete_site', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.get(reverse('ims:site_delete'),
                                  follow = False)
        self.assertEquals(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('No sites requested for deletion',
                      resultWarning,
                      'IMS site_delete view didn''t generate the correct warning when no sites requested found.\nactual message = %s' %
                      resultWarning)
    
    def test_site_delete_get(self):
        print 'running SiteDeleteViewTests.test_site_delete_get... '
        perms = [ 'delete_site', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        response=self.client.get(reverse('ims:site_delete') + '?' +
                                 urlencode({'site':site.pk}),
                                  follow = False)
        self.assertEquals(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('Are you sure?',
                      resultWarning,
                      'IMS site_delete view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
        
    def test_site_delete_get_with_inventory(self):
        print 'running SiteDeleteViewTests.test_site_delete_get_with_inventory... '
        perms = [ 'delete_site', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        (createdSites,
         __,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=3)
        response=self.client.get(reverse('ims:site_delete') + '?' +
                                 urlencode({'site':createdSites[0].pk}),
                                  follow = False)
        self.assertEquals(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('One or more sites contain inventory.  Deleting the sites will delete all inventory as well. Delete anyway?',
                      resultWarning,
                      'IMS site_delete view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
        
    def test_site_delete_get_without_delete_site_perm(self):
        print 'running SiteDeleteViewTests.test_site_delete_get_without_delete_site_perm... '
        perms = ['delete_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        response=self.client.get(reverse('ims:site_delete') + '?' +
                                 urlencode({'site':site.pk}),
                                  follow = False)
        self.assertEquals(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to delete sites',
                      resultError,
                      'IMS site_delete view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
        
    def test_site_delete_get_without_delete_inventoryitem_perm(self):
        print 'running SiteDeleteViewTests.test_site_delete_get_without_delete_inventoryitem_perm... '
        perms = ['delete_site',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        response=self.client.get(reverse('ims:site_delete') + '?' +
                                 urlencode({'site':site.pk}),
                                  follow = False)
        self.assertEquals(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to delete sites',
                      resultError,
                      'IMS site_delete view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
        
    def test_site_delete_post_with_no_post_parms(self):
        print 'running SiteDeleteViewTests.test_site_delete_post_with_no_post_parms... '
        perms = [ 'delete_site', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'Delete':'Delete'}
        request = self.factory.post(reverse('ims:site_delete'),
                                    postData, 
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = site_delete(request)
        response.client = self.client
        resultError = request.session['errorMessage']
        self.assertIn('No sites requested for deletion',
                      resultError,
                      'IMS site_delete view didn''t generate the correct warning when no sites requested found.\nactual message = %s' %
                      resultError)
        self.assertRedirects(response, reverse('ims:sites') + '?' +
                             urlencode({'page':1,
                                        'pageSize':PAGE_SIZE,}), 
                             status_code = 302,
                             target_status_code = 200)
    
    def test_site_delete_post(self):
        print 'running SiteDeleteViewTests.test_site_delete_post... '
        perms = [ 'delete_site', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        postData = {'Delete':'Delete',
                    'sites':[site.number,]}
        request = self.factory.post(reverse('ims:site_delete'),
                                    postData, 
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = site_delete(request)
        response.client = self.client
        resultInfo = request.session['infoMessage']
        self.assertIn('Successfully deleted site %s<br />' % site.name,
                      resultInfo,
                      'IMS site_delete view didn''t generate the correct info site deleted.\nactual message = %s' %
                      resultInfo)
        self.assertRedirects(response, reverse('ims:sites') + '?' +
                             urlencode({'page':1,
                                        'pageSize':PAGE_SIZE,}), 
                             status_code = 302,
                             target_status_code = 200)
        self.assertEqual(Site.objects.all().count(), 
                         0,
                         'Site still in database after deleting.')
    
    def test_site_delete_post_with_inventory(self):
        print 'running SiteDeleteViewTests.test_site_delete_post_with_inventory... '
        perms = [ 'delete_site', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        (createdSites,
         __,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=3)
        postData = {'Delete':'Delete',
                    'sites':[createdSites[0].number,]}
        request = self.factory.post(reverse('ims:site_delete'),
                                    postData, 
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = site_delete(request)
        response.client = self.client
        resultInfo = request.session['infoMessage']
        self.assertIn('Successfully deleted site %s<br />' % createdSites[0].name,
                      resultInfo,
                      'IMS site_delete view didn''t generate the correct info site deleted.\nactual message = %s' %
                      resultInfo)
        self.assertRedirects(response, reverse('ims:sites') + '?' +
                             urlencode({'page':1,
                                        'pageSize':PAGE_SIZE,}), 
                             status_code = 302,
                             target_status_code = 200)
        self.assertEqual(Site.objects.all().count(), 
                         0,
                         'Site still in database after deleting.')
        self.assertEqual(InventoryItem.objects.all().count(), 
                         0,
                         'Inventory still in database after deleting.')
         
    def test_site_delete_post_without_delete_site_perm(self):
        print 'running SiteDeleteViewTests.test_site_delete_post_without_delete_site_perm... '
        perms = ['delete_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        postData = {'Delete':'Delete',
                    'sites':[site.number,]}
        response = self.client.post(reverse('ims:site_delete'),
                                    postData, 
                                    follow = False)
        self.assertEqual(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to delete sites',
                      resultError,
                      'IMS site_delete view didn''t generate the correct error with incorrect user permissions.\nactual message = %s' %
                      resultError)
    
    def test_site_delete_post_without_delete_inventoryitem_perm(self):
        print 'running SiteDeleteViewTests.test_site_delete_post_without_delete_inventoryitem_perm... '
        perms = ['delete_site',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        postData = {'Delete':'Delete',
                    'sites':[site.number,]}
        response = self.client.post(reverse('ims:site_delete'),
                                    postData, 
                                    follow = False)
        self.assertEqual(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to delete sites',
                      resultError,
                      'IMS site_delete view didn''t generate the correct error with incorrect user permissions.\nactual message = %s' %
                      resultError)
    
    def test_site_delete_post_cancel(self):
        print 'running SiteDeleteViewTests.test_site_delete_post_cancel... '
        perms = [ 'delete_site', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        postData = {'Cancel':'Cancel',
                    'sites':[site.number,]}
        response = self.client.post(reverse('ims:site_delete'),
                                    postData, 
                                    follow = False)
        self.assertRedirects(response, reverse('ims:sites') + '?' + 
                             urlencode({'page':1,
                             'pageSize':1,}), 
                             status_code = 302,
                             target_status_code = 200)
    
class SiteAddViewTests(TestCase):
    """
    ims_tests for site_add view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    def test_site_add_get(self):
        print 'running SiteAddViewTests.test_site_add_get... '
        perms = ['add_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response = self.client.get(reverse('ims:site_add'))
        self.assertEquals(response.status_code, 200)
        
    def test_site_add_get_without_add_site_perm(self):
        print 'running SiteAddViewTests.test_site_add_get_without_add_site_perm... '
        self.client.login(username='testUser', password='12345678')
        request = self.factory.get(reverse('ims:site_add'),
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = site_add(request)
        response.client = self.client
        resultError = request.session['errorMessage']
        self.assertIn('You don''t have permission to add sites', 
                      resultError,
                      'IMS site_add view didn''t generate the correct error when an unauthorized user tried to add.\nactual message = %s' %
                      resultError)
        self.assertRedirects(response, reverse('ims:sites',) + 
                              '?' + urlencode({'page':1,}), 
                             status_code = 302,
                             target_status_code = 200)
     
    def test_site_add_post(self):
        print 'running SiteAddViewTests.test_site_add_post... '
        perms = ['add_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'name': 'test site', 
                    'county': '', 
                    'address1': '11 main st.', 
                    'contactName' : 'John Smith',
                    'contactPhone' : '555-1212',
                    'modifier' : self.user.username,
                    'Save': 'Save', }
        request = self.factory.post(reverse('ims:site_add'),
                                    postData,
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = site_add(request)
        self.assertEqual(Site.objects.count(), 1)
        site = Site.objects.all()[0]
        resultInfo = request.session['infoMessage']
        self.assertIn('Successfully added site', resultInfo,
                      'IMS site_add view didn''t generate the correct info when saving.\nactual message = %s' %
                      resultInfo)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:site_detail',
                                     kwargs={'siteId':site.pk,},), 
                             status_code = 302,
                             target_status_code = 200)
         
    def test_site_add_post_no_change(self):
        print 'running SiteAddViewTests.test_site_add_post_no_change... '
        perms = ['add_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'Save':'Save'}
        response = self.client.post(reverse('ims:site_add'),
                                    postData,
                                    follow = False)
        self.assertEqual(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('More information required before site can be added', 
                      resultWarning,
                      'IMS site_add view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
     
    def test_site_add_post_without_add_site_perm(self):
        print 'running SiteAddViewTests.test_site_add_post_without_add_site_perm... '
        self.client.login(username='testUser', password='12345678')
        postData = {'name': 'test site', 
                    'county': '', 
                    'address1': '11 main st.', 
                    'contactName' : 'John Smith',
                    'contactPhone' : '555-1212',
                    'modifier' : self.user.username,
                    'Save': 'Save', }
        request = self.factory.post(reverse('ims:site_add'),
                                    postData,
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = site_add(request)
        resultInfo = request.session['errorMessage']
        self.assertIn('You don''t have permission to add sites', resultInfo,
                      'IMS site_add view didn''t generate the correct error when saving.\nactual message = %s' %
                      resultInfo)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:sites',) + '?' +
                             urlencode({'page':1,}), 
                             status_code = 302,
                             target_status_code = 200)
    
class SiteDetailViewTests(TestCase):
    """
    ims_tests for site_detail view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    def test_site_detail_get(self):
        print 'running SiteDetailViewTests.test_site_detail_get... '
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        response=self.client.get(reverse('ims:site_detail',
                                 kwargs = 
                                  {'siteId':site.pk,}),
                                  follow=False)
        self.assertEqual(response.status_code, 200)
    
    def test_site_detail_get_with_invalid_site(self):
        print 'running SiteDetailViewTests.test_site_detail_get_with_invalid_site... '
        self.client.login(username='testUser', password='12345678')
        siteId = 1
        request=self.factory.get(reverse('ims:site_detail',
                                 kwargs = 
                                  {'siteId':siteId,}),
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = site_detail(request, siteId = siteId)
        resultError = request.session['errorMessage']
        self.assertIn('Site %d does not exist' % siteId, 
                      resultError,
                      'IMS site detail view didn''t generate the correct error when an invalid site was requested.\nactual message = %s' %
                      resultError)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:sites',) + '?' +
                             urlencode({'page':1,}), 
                             status_code = 302,
                             target_status_code = 200)
        
    def test_site_detail_get_with_filter(self):
        print 'running SiteDetailViewTests.test_site_detail_get_with_filter... '
        self.client.login(username='testUser', password='12345678')
        (createdSites,
         __,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=2,
                                numItems=1)
        site = createdSites[0]
        response=self.client.get(reverse('ims:site_detail',
                                 kwargs = 
                                  {'siteId':site.pk,}) + 
                                 '?searchField=information__name&searchValue=test product 1',
                                  follow=False)
        self.assertEqual(response.status_code, 200)
    
    def test_site_detail_get_with_bad_inventory_filter(self):
        print 'running SiteDetailViewTests.test_site_detail_get_with_bad_inventory_filter... '
        self.client.login(username='testUser', password='12345678')
        (createdSites,
         __,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=2,
                                numItems=1)
        site = createdSites[0]
        request=self.factory.get(reverse('ims:site_detail',
                                 kwargs = 
                                  {'siteId':site.pk,}) + 
                                 '?searchField=information__name&searchValue=blah',
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = site_detail(request, siteId = site.pk)
        resultWarning = request.session['warningMessage']
        self.assertIn('No inventory found using filter criteria.<br/>Showing all inventory.', 
                      resultWarning,
                      'IMS site detail view didn''t generate the correct error with a bad inventory filter.\nactual message = %s' %
                      resultWarning)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:site_detail',
                                 kwargs = 
                                  {'siteId':site.pk,}) + '?' +
                             urlencode({'page':1,}), 
                             status_code = 302,
                             target_status_code = 200)
    
    def test_site_detail_post_save_site(self):
        print 'running SiteDetailViewTests.test_site_detail_post_save_site... '
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        perms = ['change_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'name': 'test site', 
                    'county': '', 
                    'address1': '11 main st.', 
                    'contactName' : 'John Smith',
                    'contactPhone' : '555-1212',
                    'modifier' : self.user.username,
                    'Save Site': 'Save Site', }
        request=self.factory.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = site_detail(request, siteId = site.pk)
        resultInfo = request.session['infoMessage']
        self.assertIn('Successfully changed site information', 
                      resultInfo,
                      'IMS site detail view didn''t generate the correct info.\nactual message = %s' %
                      resultInfo)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:site_detail',
                                     kwargs={'siteId':site.pk,},) + 
                                     '?' + urlencode({'page':1,
                                                      'pageSize':PAGE_SIZE,
                                                      'adjust':'False'}), 
                             302, 
                             200)
    
    def test_site_detail_post_save_site_invalid_fields(self):
        print 'running SiteDetailViewTests.test_site_detail_post_save_site_invalid_fields... '
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        perms = ['change_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'Save Site': 'Save Site', }
        response=self.client.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        self.assertEqual(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('More information required before the site can be saved', 
                      resultWarning,
                      'IMS site detail view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
    
    def test_site_detail_post_save_site_no_change(self):
        print 'running SiteDetailViewTests.test_site_detail_post_save_site_no_change... '
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site',
                    county =  '', 
                    address1 = '11 main st.', 
                    contactName = 'John Smith',
                    contactPhone = '555-1212',
                    modifier = self.user.username,)
        site.save()
        perms = ['change_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'name': 'test site', 
                    'county': '', 
                    'address1': '11 main st.', 
                    'contactName' : 'John Smith',
                    'contactPhone' : '555-1212',
                    'modifier' : self.user.username,
                    'Save Site': 'Save Site', }
        response=self.client.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        self.assertEqual(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('No changes made to the site information', 
                      resultWarning,
                      'IMS site detail view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
    
    def test_site_detail_post_save_site_without_change_site_perm(self):
        print 'running SiteDetailViewTests.test_site_detail_post_save_site_without_change_site_perm... '
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site',)
        site.save()
        self.client.login(username='testUser', password='12345678')
        postData = {'name': 'test site', 
                    'county': '', 
                    'address1': '11 main st.', 
                    'contactName' : 'John Smith',
                    'contactPhone' : '555-1212',
                    'modifier' : self.user.username,
                    'Save Site': 'Save Site', }
        response=self.client.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        self.assertEqual(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to change site information', 
                      resultError,
                      'IMS site detail view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
        
    def test_site_detail_post_save_adjust_changes_quantity(self):
        print 'running SiteDetailViewTests.test_site_detail_post_save_adjust_changes_quantity... '
        (createdSites,
         createdProducts,
         createdInventory,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        site = createdSites[0]
        product = createdProducts[0]
        inventory = createdInventory[0]
        perms = ['change_inventoryitem', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        newQuantity = 5
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-id':[inventory.pk],
                    'form-0-site':[site.pk],
                    'form-0-information':[product.pk],
                    'form-0-quantity':[newQuantity],
                    'Save Adjust Changes':'Save Adjust Changes',}
        request=self.factory.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = site_detail(request, siteId = site.pk)
        resultInfo = request.session['infoMessage']
        self.assertIn('Successfully changed site inventory', 
                      resultInfo,
                      'IMS site detail view didn''t generate the correct info.\nactual message = %s' %
                      resultInfo)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:site_detail',
                                     kwargs={'siteId':site.pk,},) + 
                                     '?' + urlencode({'page':1,
                                                      'pageSize':PAGE_SIZE,
                                                      'adjust':'True'}), 
                             302, 
                             200)
        newInventory = site.latest_inventory_for_product(code = product.pk)
        self.assertEqual(newInventory.quantity, 
                         5, 
                         'site_detail view didn''t show the correct inventory quantity after changing to %d\n Quantity = %d' % (newQuantity, newInventory.quantity))

    def test_site_detail_post_save_adjust_changes_delete(self):
        print 'running SiteDetailViewTests.test_site_detail_post_save_adjust_changes... '
        (createdSites,
         createdProducts,
         createdInventory,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=2,
                                numItems=1)
        site = createdSites[0]
        numInventory = site.latest_inventory().count()
        self.assertEqual(numInventory, 
                         2, 
                         'site_detail view didn''t show the correct inventory after adding 2. Quantity = %d' % numInventory)
        perms = ['change_inventoryitem', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': [len(createdProducts)],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'Save Adjust Changes':'Save Adjust Changes',}
        addItemDict = {}
        deleteIndex = 1
        for index in range(len(createdInventory)):
            addItemDict['form-%d-id' % index] = createdInventory[index].pk
            addItemDict['form-%d-site' % index] = createdInventory[index].site.pk
            addItemDict['form-%d-quantity' % index] = createdInventory[index].quantity
            addItemDict['form-%d-information' % index] = createdInventory[index].information.pk
            if index == deleteIndex:
                addItemDict['form-%d-deleteItem' % index] = 'on'
        postData.update(addItemDict)
        request=self.factory.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = site_detail(request, siteId = site.pk)
        resultInfo = request.session['infoMessage']
        self.assertIn('Successfully changed site inventory', 
                      resultInfo,
                      'IMS site detail view didn''t generate the correct info.\nactual message = %s' %
                      resultInfo)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:site_detail',
                                     kwargs={'siteId':site.pk,},) + 
                                     '?' + urlencode({'page':1,
                                                      'pageSize':PAGE_SIZE,
                                                      'adjust':'True'}), 
                             302, 
                             200)
        numInventory = site.latest_inventory().count()
        self.assertEqual(numInventory, 
                         1, 
                         'site_detail view didn''t show the correct inventory after deleting 1. Quantity = %d' % numInventory)

    def test_site_detail_post_save_adjust_changes_without_change_inventoryitem_perm(self):
        print 'running SiteDetailViewTests.test_site_detail_post_save_adjust_changes_without_change_inventoryitem_perm... '
        (createdSites,
         createdProducts,
         createdInventory,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        site = createdSites[0]
        product = createdProducts[0]
        inventory = createdInventory[0]
        perms = ['delete_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        newQuantity = 5
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-id':[inventory.pk],
                    'form-0-site':[site.pk],
                    'form-0-information':[product.pk],
                    'form-0-quantity':[newQuantity],
                    'Save Adjust Changes':'Save Adjust Changes',}
        response=self.client.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to change or delete inventory', 
                      resultError,
                      'IMS site detail view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
        
    def test_site_detail_post_save_adjust_changes_without_delete_inventoryitem_perm(self):
        print 'running SiteDetailViewTests.test_site_detail_post_save_adjust_changes_without_delete_inventoryitem_perm... '
        (createdSites,
         createdProducts,
         createdInventory,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        site = createdSites[0]
        product = createdProducts[0]
        inventory = createdInventory[0]
        perms = ['delete_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        newQuantity = 5
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-id':[inventory.pk],
                    'form-0-site':[site.pk],
                    'form-0-information':[product.pk],
                    'form-0-quantity':[newQuantity],
                    'Save Adjust Changes':'Save Adjust Changes',}
        response=self.client.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to change or delete inventory', 
                      resultError,
                      'IMS site detail view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
        
    def test_site_detail_post_save_add_subtract_changes_quantity(self):
        print 'running SiteDetailViewTests.test_site_detail_post_save_add_subtract_changes_quantity... '
        (createdSites,
         createdProducts,
         createdInventory,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        site = createdSites[0]
        product = createdProducts[0]
        inventory = createdInventory[0]
        perms = ['change_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        quantityAdd = 5
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-id':[inventory.pk],
                    'form-0-site':[site.pk],
                    'form-0-information':[product.pk],
                    'form-0-addSubtract':[quantityAdd],
                    'Save Add Subtract Changes':'Save Add Subtract Changes',}
        request=self.factory.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = site_detail(request, siteId = site.pk)
        resultInfo = request.session['infoMessage']
        self.assertIn('Successfully changed site inventory', 
                      resultInfo,
                      'IMS site detail view didn''t generate the correct info.\nactual message = %s' %
                      resultInfo)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:site_detail',
                                     kwargs={'siteId':site.pk,},) + 
                                     '?' + urlencode({'page':1,
                                                      'pageSize':PAGE_SIZE,
                                                      'adjust':'False'}), 
                             302, 
                             200)
        newInventory = site.latest_inventory_for_product(code = product.pk)
        self.assertEqual(newInventory.quantity, 
                         1 + quantityAdd, 
                         'site_detail view didn''t show the correct inventory quantity after changing to %d\n Quantity = %d' % (1 + quantityAdd, newInventory.quantity))
 
    def test_site_detail_post_save_add_subtract_changes_without_change_inventoryitem_perm(self):
        print 'running SiteDetailViewTests.test_site_detail_post_save_add_subtract_changes_without_change_inventoryitem_perm... '
        (createdSites,
         createdProducts,
         createdInventory,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        site = createdSites[0]
        product = createdProducts[0]
        inventory = createdInventory[0]
        self.client.login(username='testUser', password='12345678')
        quantityAdd = 5
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-id':[inventory.pk],
                    'form-0-site':[site.pk],
                    'form-0-information':[product.pk],
                    'form-0-addSubtract':[quantityAdd],
                    'Save Add Subtract Changes':'Save Add Subtract Changes',}
        response=self.client.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to change inventory', 
                      resultError,
                      'IMS site detail view didn''t generate the correct error.\nactual message = %s' %
                      resultError)

    def test_site_detail_post_add_new_inventory(self):
        print 'running SiteDetailViewTests.test_site_detail_post_add_new_inventory... '
        site = Site(name = 'test site')
        site.save()
        product = ProductInformation(name = 'test product',
                                     code= 'D11',)
        product.save()
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'Add New Inventory':'Add New Inventory',}
        response=self.client.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        self.assertRedirects(response, 
                             reverse('ims:site_add_inventory',kwargs={'siteId':site.pk}), 
                             302, 
                             200)
        
    def test_site_detail_post_add_new_inventory_without_add_inventory_perm(self):
        print 'running SiteDetailViewTests.test_site_detail_post_add_new_inventory_without_change_inventory_perm... '
        site = Site(name = 'test site')
        site.save()
        self.client.login(username='testUser', password='12345678')
        postData = {'Add New Inventory':'Add New Inventory',}
        response=self.client.post(reverse('ims:site_detail',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to add inventory', 
                      resultError,
                      'IMS site detail view didn''t generate the correct error.\nactual message = %s' %
                      resultError)

class SiteAddInventoryViewTests(TestCase):
    """
    ims_tests for site_add_inventory view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    def test_site_add_inventory_get(self):
        print 'running SiteAddInventoryViewTests.test_site_add_inventory_get... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site',)
        site.save()
        product = ProductInformation(name = 'test product',
                                     code = 'D11')
        product.save()
        response=self.client.get(reverse('ims:site_add_inventory',
                                         kwargs = {'siteId':site.pk,}),
                                  follow=False)
        self.assertEqual(response.status_code, 200)
        
    def test_site_add_inventory_get_without_add_inventoryitem_perm(self):
        print 'running SiteAddInventoryViewTests.test_site_add_inventory_get_without_add_inventoryitem_perm... '
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site',)
        site.save()
        product = ProductInformation(name = 'test product',
                                     code = 'D11')
        product.save()
        response=self.client.get(reverse('ims:site_add_inventory',
                                         kwargs = {'siteId':site.pk,}),
                                  follow=False)
        self.assertEqual(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to add site inventory', 
                      resultError,
                      'IMS site_add_inventory view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
        
    def test_site_add_inventory_with_invalid_site(self):
        print 'running SiteAddInventoryViewTests.test_site_add_inventory_with_invalid_site... '
        self.client.login(username='testUser', password='12345678')
        siteId = 1
        request = self.factory.get(reverse('ims:site_add_inventory',
                                         kwargs = {'siteId':siteId,}),
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = site_add_inventory(request, siteId = siteId)
        resultError = request.session['errorMessage']
        self.assertIn('Site %d does not exist' % 
                      siteId, resultError,
                      'IMS site_add_inventory view didn''t generate the correct error when an invalid site was requested.\nactual message = %s' %
                      resultError)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:sites'), 
                             302, 
                             200)
        
    def test_site_add_inventory_with_no_products(self):
        print 'running SiteAddInventoryViewTests.test_site_add_inventory_with_no_products... '
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site',)
        site.save()
        request = self.factory.get(reverse('ims:site_add_inventory',
                                         kwargs = {'siteId':site.pk,}),
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = site_add_inventory(request, siteId = site.pk)
        resultWarning = request.session['warningMessage']
        self.assertIn('No products found to add',
                      resultWarning,
                      'IMS site_add_inventory view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:site_detail', 
                                     kwargs = {'siteId':site.pk}), 
                             302, 
                             200)
    
    def test_site_add_inventory_post(self):
        print 'running SiteAddInventoryViewTests.test_site_add_inventory_post... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site',)
        site.save()
        product = ProductInformation(name = 'test product',
                                     code = 'D11')
        product.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-code':[product.pk],
                    'form-0-Add':['on'],
                    'Add Products':'Add Products',}
        response=self.client.post(reverse('ims:site_add_inventory',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        productsToAdd = '?code=D11&'
        self.assertRedirects(response, 
                             reverse('ims:products_add_to_site_inventory',
                                        kwargs = {'siteId': site.pk}) +
                                        productsToAdd, 
                             302, 
                             200)
    
    def test_site_add_inventory_post_no_products(self):
        print 'running SiteAddInventoryViewTests.test_site_add_inventory_post_no_products... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site',)
        site.save()
        product = ProductInformation(name = 'test product',
                                     code = 'D11')
        product.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-code':[product.pk],
                    'Add Products':'Add Products',}
        response=self.client.post(reverse('ims:site_add_inventory',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('No products selected to add',
                      resultWarning,
                      'IMS site_add_inventory didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
    
    def test_site_add_inventory_post_without_add_inventoryitem_perm(self):
        print 'running SiteAddInventoryViewTests.test_site_add_inventory_post_without_add_inventoryitem_perm... '
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site',)
        site.save()
        product = ProductInformation(name = 'test product',
                                     code = 'D11')
        product.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-code':[product.pk],
                    'form-0-Add':['on'],
                    'Add Products':'Add Products',}
        response=self.client.post(reverse('ims:site_add_inventory',
                                  kwargs = 
                                  {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to add site inventory',
                      resultError,
                      'IMS site_add_inventory didn''t generate the correct error.\nactual message = %s' %
                      resultError)

class ProductsViewTests(TestCase):
    """
    ims_tests for products view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
        
    def test_products_get_with_no_products(self):
        print 'running ProductsViewTests.test_products_get_with_no_products... '
        self.client.login(username='testUser', password='12345678')
        response=self.client.get(reverse('ims:products'),
                                  follow=True)
        self.assertEquals(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('No products found',
                      'IMS products view didn''t generate the correct warning when no products were found.\nactual message = %s' %
                      resultWarning)
        
    def test_products_get_with_filter_and_no_products(self):
        print 'running ProductsViewTests.test_products_get_with_filter_and_no_products... '
        self.client.login(username='testUser', password='12345678')
        response=self.client.get(reverse('ims:products',) +
                                 '?searchField=name&searchValue=blah',
                                 follow = False,)
        self.assertEquals(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('No products found',
                      'IMS products view didn''t generate the correct warning when no products were found.\nactual message = %s' %
                      resultWarning)
    
    def test_products_get_with_products(self):
        print 'running ProductsViewTests.test_products_get_with_products... '
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        product = ProductInformation(name='test product',
                                     code = code)
        product.save()
        response=self.client.get(reverse('ims:products',),
                                 follow = False,)
        self.assertEqual(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertEqual('', resultWarning)
        
    def test_products_get_with_filter(self):
        print 'running ProductsViewTests.test_products_get_with_filter... '
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        product = ProductInformation(name='test product',
                                     code = code)
        product.save()
        response=self.client.get(reverse('ims:products',) +
                                 '?searchField=name&searchValue=test',
                                 follow = False,)
        self.assertEqual(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertEqual('', resultWarning)
    
    def test_products_get_with_bad_filter(self):
        print 'running ProductsViewTests.test_products_get_with_bad_filter... '
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        product = ProductInformation(name='test product',
                                     code = code)
        product.save()
        response=self.client.get(reverse('ims:products',) +
                                 '?searchField=name&searchValue=blah',
                                 follow = False,)
        self.assertRedirects(response, reverse('ims:products',) +
                                 '?page=1&pageSize=%d' % PAGE_SIZE, 
                                 status_code = 302,
                                 target_status_code = 200)
    
    def test_products_post_add(self):
        print 'running ProductsViewTests.test_products_post_add... '
        perms = ['add_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['0'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['0'],
                    'Add':'Add',}
        response=self.client.post(reverse('ims:products',),
                                  postData,
                                  follow = False,)
        self.assertRedirects(response, reverse('ims:product_add',), 
                                 status_code = 302,
                                 target_status_code = 200)
    
    def test_products_post_add_without_add_productinformation_perm(self):
        print 'running ProductsViewTests.test_products_post_add_without_add_productinformation_perm... '
        self.client.login(username='testUser', password='12345678')
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['0'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['0'],
                    'Add':'Add',}
        response=self.client.post(reverse('ims:products',),
                                  postData,
                                  follow = False,)
        self.assertEquals(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to add new products', 
                      resultError,
                      'IMS products view didn''t generate the correct error when an unauthorized user tried to add.\nactual message = %s' %
                      resultError)
        
    def test_products_post_delete(self):
        print 'running ProductsViewTests.test_products_post_delete... '
        perms = ['delete_productinformation', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        productName = 'test product'
        code = 'D11'
        product = ProductInformation(name = productName,
                                     code = code,)
        product.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-code':[code],
                    'form-0-Delete':['on'],
                    'Delete':'Delete',}
        response=self.client.post(reverse('ims:products',),
                                  postData,
                                  follow = False,)
        self.assertRedirects(response, reverse('ims:product_delete',) + 
                             '?code=D11&', 
                             status_code = 302,
                             target_status_code = 200)
        
    def test_products_post_delete_without_delete_inventoryitem_perms(self):
        print 'running ProductsViewTests.test_products_post_delete_without_delete_inventoryitem_perms... '
        perms = ['delete_productinformation',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        productName = 'test product'
        code = 'D11'
        product = ProductInformation(name = productName,
                                     code = code,)
        product.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-code':[code],
                    'form-0-Delete':['on'],
                    'Delete':'Delete',}
        response=self.client.post(reverse('ims:products',),
                                  postData,
                                  follow = False,)
        self.assertEquals(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to delete products', 
                      resultError,
                      'IMS products view didn''t generate the correct error when an unauthorized user tried to add.\nactual message = %s' %
                      resultError)

    def test_products_post_delete_without_delete_productinformation_perms(self):
        print 'running ProductsViewTests.test_products_post_delete_without_delete_productinformation_perms... '
        perms = ['delete_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        productName = 'test product'
        code = 'D11'
        product = ProductInformation(name = productName,
                                     code = code,)
        product.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': ['1'],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'form-0-code':[code],
                    'form-0-Delete':['on'],
                    'Delete':'Delete',}
        response=self.client.post(reverse('ims:products',),
                                  postData,
                                  follow = False,)
        self.assertEquals(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to delete products', 
                      resultError,
                      'IMS products view didn''t generate the correct error when an unauthorized user tried to add.\nactual message = %s' %
                      resultError)

class ProductAddViewTests(TestCase):
    """
    ims_tests for product_add view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    def test_product_add_get(self):
        print 'running ProductAddViewTests.test_product_add_get... '
        perms = ['add_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response = self.client.get(reverse('ims:product_add'))
        self.assertEquals(response.status_code, 200)
        
    def test_product_add_get_without_add_productinformation_perm(self):
        print 'running ProductAddViewTests.test_product_add_get_without_add_productinformation_perm... '
        self.client.login(username='testUser', password='12345678')
        request = self.factory.get(reverse('ims:product_add'),
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = product_add(request)
        response.client = self.client
        resultError = request.session['errorMessage']
        self.assertIn('You don''t have permission to add new products', 
                      resultError,
                      'IMS product_add view didn''t generate the correct error when an unauthorized user tried to add.\nactual message = %s' %
                      resultError)
        self.assertRedirects(response, reverse('ims:products',) + 
                              '?' + urlencode({'page':1,}), 
                             status_code = 302,
                             target_status_code = 200)
    
    def test_product_add_post(self):
        print 'running ProductAddViewTests.test_product_add_post... '
        perms = ['add_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'quantityOfMeasure': 1, 
                    'unitOfMeasure': 'EACH', 
                    'code': 'D11', 
                    'Save': 'Save', 
                    'name': 'test product'}
        request = self.factory.post(reverse('ims:product_add'),
                                    postData,
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = product_add(request)
        resultInfo = request.session['infoMessage']
        self.assertIn('Successfully saved product.', resultInfo,
                      'IMS product_add view didn''t generate the correct info when saving.\nactual message = %s' %
                      resultInfo)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:product_detail', 
                                     kwargs={'code':'D11'}) + '?' +
                                     urlencode({'page':1,
                                                'picture':'False'}), 
                             status_code = 302,
                             target_status_code = 200)
        
    def test_product_add_post_no_change(self):
        print 'running ProductAddViewTests.test_product_add_post_no_change... '
        perms = ['add_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'Save':'Save'}
        response = self.client.post(reverse('ims:product_add'),
                                    postData,
                                    follow = False)
        self.assertEqual(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('More information required before product can be added', 
                      resultWarning,
                      'IMS product_add view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
    
    def test_product_add_post_with_error_message(self):
        print 'running ProductAddViewTests.test_product_add_post_with_error_message... '
        perms = ['add_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        postData = {'quantityOfMeasure': 1, 
                    'unitOfMeasure': 'EACH', 
                    'code': 'D11', 
                    'Save': 'Save', 
                    'name': 'test product'}
        request = self.factory.post(reverse('ims:product_add'),
                                    postData,
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        request.session['errorMessage'] = 'Error'
        response = product_add(request)
        response.client = self.client
        self.assertRedirects(response, reverse('ims:products',) + 
                              '?' + urlencode({'page':1,}), 
                             status_code = 302,
                             target_status_code = 200)
        
    def test_product_add_post_without_add_productinformation_perm(self):
        print 'running ProductAddViewTests.test_product_add_post_without_add_productinformation_perm... '
        self.client.login(username='testUser', password='12345678')
        postData = {'quantityOfMeasure': 1, 
                    'unitOfMeasure': 'EACH', 
                    'code': 'D11', 
                    'Save': 'Save', 
                    'name': 'test product'}
        request = self.factory.post(reverse('ims:product_add'),
                                    postData,
                                    follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = product_add(request)
        resultInfo = request.session['errorMessage']
        self.assertIn('You don''t have permission to add new products', resultInfo,
                      'IMS product_add view didn''t generate the correct error when saving.\nactual message = %s' %
                      resultInfo)
        response.client = self.client
        self.assertRedirects(response, 
                             reverse('ims:products',) + '?' +
                             urlencode({'page':1,}), 
                             status_code = 302,
                             target_status_code = 200)

class ProductDetailViewTests(TestCase):
    """
    ims_tests for product_detail view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    def test_product_detail_get(self):
        print 'running ProductDetailViewTests.test_product_detail_get... '
        self.client.login(username='testUser', password='12345678')
        product = ProductInformation(code='D11')
        product.save()
        code="D11"
        response=self.client.get(reverse('ims:product_detail',
                                 kwargs = 
                                  {'code':code,}),
                                  follow=True)
        self.assertEqual(response.status_code, 200,
                         "Product Detail View didn't return status code 200 with a valid product code.")
        
    def test_product_detail_get_with_filter_and_no_sites(self):
        print 'running ProductDetailViewTests.test_product_detail_get_with_filter_and_no_sites... '
        self.client.login(username='testUser', password='12345678')
        product = ProductInformation(code='D11')
        product.save()
        code="D11"
        response=self.client.get(reverse('ims:product_detail',
                                 kwargs = 
                                  {'code':code,}) +
                                 '?searchField=site__name&searchValue=blah',
                                 follow = False,)
        self.assertEqual(response.status_code, 200,)
        
    def test_product_detail_get_with_bad_filter(self):
        print 'running ProductDetailViewTests.test_product_detail_get_with_bad_filter... '
        self.client.login(username='testUser', password='12345678')
        code="D11"
        product = ProductInformation(code=code)
        product.save()
        site = Site(name='test site')
        site.save()
        site.add_inventory(product = product, 
                           quantity = 1, 
                           modifier = self.user.username)
        request=self.factory.get(reverse('ims:product_detail',
                                 kwargs = 
                                  {'code':code,}) +
                                 '?searchField=site__name&searchValue=blah',
                                 follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = product_detail(request, code = code)
        resultWarning = request.session['warningMessage']
        self.assertIn('No sites found using filter criteria.<br/>Showing all sites.', 
                      resultWarning,
                      'IMS product detail view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
        response.client = self.client
        self.assertRedirects(response, reverse('ims:product_detail',
                                 kwargs = 
                                  {'code':code,}) +
                                 '?page=1&picture=False', 
                                 status_code = 302,
                                 target_status_code = 200)
        
    def test_product_detail_get_with_filter(self):
        print 'running ProductDetailViewTests.test_product_detail_get_with_filter... '
        self.client.login(username='testUser', password='12345678')
        code="D11"
        product = ProductInformation(code=code)
        product.save()
        site = Site(name='test site')
        site.save()
        site.add_inventory(product = product, 
                           quantity = 1, 
                           modifier = self.user.username)
        response=self.client.get(reverse('ims:product_detail',
                                 kwargs = 
                                  {'code':code,}) +
                                 '?searchField=site__name&searchValue=test',
                                 follow = False)
        self.assertEqual(response.status_code, 200,)
        
    def test_product_detail_get_with_invalid_product(self):
        print 'running ProductDetailViewTests.test_product_detail_get_with_invalid_product... '
        self.client.login(username='testUser', password='12345678')
        code="D11"
        request=self.factory.get(reverse('ims:product_detail',
                                 kwargs = 
                                  {'code':code,}),
                                  follow = False)
        request.user = self.user
        add_session_to_request(request)
        response = product_detail(request, code = code)
        resultError = request.session['errorMessage']
        self.assertIn('Product %s does not exist.' % code, 
                      resultError,
                      'IMS product detail view didn''t generate the correct warning.\nactual message = %s' %
                      resultError)
        response.client = self.client
        self.assertRedirects(response, reverse('ims:products',), 
                             status_code = 302,
                             target_status_code = 200)
        
    def test_product_detail_post_save(self):
        print 'running ProductDetailViewTests.test_product_detail_post_save... '
        perms = ['change_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        productName = 'test product'
        product = ProductInformation(name = productName,
                                     code = code)
        product.save()
        postData = {'quantityOfMeasure': 1, 
                    'unitOfMeasure': 'EACH', 
                    'code': code, 
                    'Save': 'Save', 
                    'name': productName}
        request=self.factory.post(reverse('ims:product_detail',
                                  kwargs = 
                                  {'code':code,}),
                                  postData,
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = product_detail(request, code = code)
        resultInfo = request.session['infoMessage']
        self.assertIn('Successfully saved product information changes.', 
                      resultInfo,
                      'IMS product detail view didn''t generate the correct info.\nactual message = %s' %
                      resultInfo)
        response.client = self.client
        picture = 'picture=False'
        filterQuery = ''
        self.assertRedirects(response, 
                             reverse('ims:product_detail',
                                            kwargs={'code':code,}) 
                                    + '?' + picture + '&' + filterQuery, 
                             302, 
                             200)
    
    def test_product_detail_post_save_invalid_fields(self):
        print 'running ProductDetailViewTests.test_product_detail_post_save_invalid_fields... '
        perms = ['change_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        productName = 'test product'
        product = ProductInformation(name = productName,
                                     code = code)
        product.save()
        postData = {'quantityOfMeasure': 1, 
                    'unitOfMeasure': 'EACH', 
                    'code': '', 
                    'Save': 'Save', 
                    'name': productName}
        response=self.client.post(reverse('ims:product_detail',
                                  kwargs = 
                                  {'code':code,}),
                                  postData,
                                  follow=False)
        self.assertEqual(response.status_code, 200)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('More information required before the product can be saved', 
                      resultWarning,
                      'IMS product detail view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
        
#TODO: figure out why this sets productForm.has_changed() = True
#     def test_product_detail_post_no_change(self):
#         print 'running ProductDetailViewTests.test_product_detail_post_no_change... '
#         perms = ['change_productinformation']
#         permissions = Permission.objects.filter(codename__in = perms)
#         self.user.user_permissions=permissions
#         self.client.login(username='testUser', password='12345678')
#         code = 'D11'
#         productName = 'test product'
#         product = ProductInformation(name = productName,
#                                      code = code,)
#         product.save()
#         postData = {'Save':'Save',}
#         response=self.client.post(reverse('ims:product_detail',
#                                   kwargs = 
#                                   {'code':code,}),
#                                   postData,
#                                   follow=False)
#         self.assertEqual(response.status_code, 200)
#         resultWarning = get_announcement_from_response(response=response,
#                                                        cls="warningnote")
#         self.assertIn('No changes made to the product information.', 
#                       resultWarning,
#                       'IMS product detail view didn''t generate the correct warning.\nactual message = %s' %
#                       resultWarning)

    def test_product_detail_post_without_change_productinformation_perm(self):
        print 'running ProductDetailViewTests.test_product_detail_post_without_change_productinformation_perm... '
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        productName = 'test product'
        product = ProductInformation(name = productName,
                                     code = code,)
        product.save()
        postData = {'Save':'Save',}
        response=self.client.post(reverse('ims:product_detail',
                                  kwargs = 
                                  {'code':code,}),
                                  postData,
                                  follow=False)
        self.assertEqual(response.status_code, 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('You don''t have permission to change product information.', 
                      resultError,
                      'IMS product detail view didn''t generate the correct error.\nactual message = %s' %
                      resultError)

class ProductSelectAddSiteViewTests(TestCase):
    """
    ims_tests for product_select_add_site view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
        
    def test_product_select_add_site_get(self):
        print 'running ProductSelectAddSiteViewTests.test_product_select_add_site_get... '
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        productName = 'test product'
        product = ProductInformation(name = productName,
                                     code = code,)
        product.save()
        site1 = Site(name = 'test site 1')
        site1.save()
        site2 = Site(name = 'test site 2')
        site2.save()
        response=self.client.get(reverse('ims:product_select_add_site',
                                         kwargs={'code':code}),
                                  follow=False)
        self.assertEquals(response.status_code, 200)
    
    def test_product_select_add_site_get_bad_product(self):
        print 'running ProductSelectAddSiteViewTests.test_product_select_add_site_get_bad_product... '
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        request=self.factory.get(reverse('ims:product_select_add_site',
                                         kwargs={'code':code}),
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = product_select_add_site(request, code = code)
        resultError = request.session['errorMessage']
        self.assertIn('Product %s does not exist.' % code, 
                      resultError,
                      'IMS product_select_add_site view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
        response.client = self.client
        self.assertRedirects(response,reverse('ims:products'), 
                                 status_code = 302,
                                 target_status_code = 200)
    
    def test_product_select_add_site_single_site(self):
        print 'running ProductSelectAddSiteViewTests.test_product_select_add_site_single_site... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        productName = 'test product'
        product = ProductInformation(name = productName,
                                     code = code,)
        product.save()
        site = Site(name = 'test site 1')
        site.save()
        response=self.client.get(reverse('ims:product_select_add_site',
                                         kwargs={'code':code}),
                                  follow=False)
        self.assertRedirects(response,reverse('ims:products_add_to_site_inventory',
                                         kwargs={'siteId':site.pk}) + '?' +
                                 urlencode({'code':product.pk}), 
                                 status_code = 302,
                                 target_status_code = 200)
        
    def test_product_select_add_site_no_sites(self):
        print 'running ProductSelectAddSiteViewTests.test_product_select_add_site_no_sites... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        code = 'D11'
        productName = 'test product'
        product = ProductInformation(name = productName,
                                     code = code,)
        product.save()
        request=self.factory.get(reverse('ims:product_select_add_site',
                                         kwargs={'code':code}),
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = product_select_add_site(request, code = code)
        resultWarning = request.session['warningMessage']
        self.assertIn('No sites found.',
                      resultWarning,
                      'IMS product_select_add_site view didn''t generate the correct warning.\nactual message = %s' %
                      resultWarning)
        response.client = self.client
        self.assertRedirects(response,reverse('ims:product_detail',
                                              kwargs={'code':product.code,}), 
                                 status_code = 302,
                                 target_status_code = 200)

class ProductsAddToSiteInventoryViewTests(TestCase):
    """
    ims_tests for products_add_to_site_inventory view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    def test_products_add_to_site_inventory_get(self):
        print 'running ProductsAddToSiteInventoryViewTests.test_products_add_to_site_inventory_get... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        site = Site(name = 'test site')
        site.save()
        productName = 'test product'
        code = 'D11'
        product = ProductInformation(name = productName, code = code)
        product.save()
        response=self.client.get(reverse('ims:products_add_to_site_inventory',
                                         kwargs = {'siteId':site.pk,}) + 
                                  '?' + urlencode({'code':code}),
                                  follow=True)
        self.assertEqual(response.status_code, 200)
        
    def test_products_add_to_site_inventory_get_without_add_inventoryitem_perm(self):
        print 'running ProductsAddToSiteInventoryViewTests.test_products_add_to_site_inventory_get_without_add_inventoryitem_perm... '
        self.client.login(username='testUser', password='12345678')
        productName = 'test product'
        code = 'D11'
        site = Site(name = 'test site')
        site.save()
        product = ProductInformation(name = productName, code = code)
        product.save()
        request=self.factory.get(reverse('ims:products_add_to_site_inventory',
                                         kwargs = {'siteId':site.pk,}) + 
                                  '?' + urlencode({'code':code}),
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = products_add_to_site_inventory(request, siteId = site.pk)
        resultError = request.session['errorMessage']
        self.assertIn('You don''t have permission to add to site inventory', 
                      resultError,
                      'IMS products_add_to_site_inventory view didn''t generate the correct error.\nactual message = %s' %
                      resultError)
        response.client = self.client
        self.assertRedirects(response, reverse('ims:site_detail',
                                               kwargs={'siteId':site.pk,}), 
                                 status_code = 302,
                                 target_status_code = 200)
    
    def test_products_add_to_site_inventory_get_with_invalid_site(self):
        print 'running ProductsAddToSiteInventoryViewTests.test_products_add_to_site_inventory_get_with_invalid_site... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        productName = 'test product'
        code = 'D11'
        siteNumber = 1
        product = ProductInformation(name = productName, code = code)
        product.save()
        response=self.client.get(reverse('ims:products_add_to_site_inventory',
                                         kwargs = {'siteId':siteNumber,}) + 
                                  '?' + urlencode({'code':code}),
                                  follow=True)
        self.assertRedirects(response, reverse('ims:sites'), 
                                 status_code = 302,
                                 target_status_code = 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('Site %d does not exist' % 
                      siteNumber, resultError,
                      'IMS products_add_to_site_inventory view didn''t generate the correct error when an invalid site was requested.\nactual message = %s' %
                      resultError)
        
    def test_products_add_to_site_inventory_get_with_invalid_product(self):
        print 'running ProductsAddToSiteInventoryViewTests.test_products_add_to_site_inventory_get_with_invalid_product... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        siteName = 'test site'
        code = 'D11'
        site = Site(name = siteName)
        site.save()
        response=self.client.get(reverse('ims:products_add_to_site_inventory',
                                         kwargs = {'siteId':site.number,}) + 
                                  '?' + urlencode({'code':code}),
                                  follow=True)
        self.assertRedirects(response, reverse('ims:products'), 
                                 status_code = 302,
                                 target_status_code = 200)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertIn('No valid products selected', 
                      resultError,
                      'IMS products_add_to_site_inventory view didn''t generate the correct error when an invalid product was requested.\nactual message = %s' %
                      resultError)
        
    def test_products_add_to_site_inventory_post(self):
        print 'running ProductsAddToSiteInventoryViewTests.test_products_add_to_site_inventory_post... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        (createdSites,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        site = createdSites[0]
        # create another product that has not been added to a site yet
        productName = 'another product'
        code = 'D11'
        product = ProductInformation(name = productName, 
                                     code = code)
        product.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': [len(createdProducts)],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'Save Inventory':'Save Inventory',}
        addItemDict = {}
        addItemDict['codes'] = []
        siteInventory = site.latest_inventory()
        for index in range(len(siteInventory)):
            addItemDict['codes'].append(siteInventory[index].information.pk)
            addItemDict['form-%d-code' % index] = [siteInventory[index].information.pk]
            addItemDict['form-%d-Quantity' % index] = [siteInventory[index].quantity]
        postData.update(addItemDict)
        request=self.factory.post(reverse('ims:products_add_to_site_inventory',
                                         kwargs = {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = products_add_to_site_inventory(request, siteId = site.pk)
        resultInfo = request.session['infoMessage']
        successfullAdditions = re.findall('Successfully added product', 
                                          resultInfo,
                                          re.M | re.DOTALL)
        self.assertEqual(len(successfullAdditions), len(createdProducts))
        response.client = self.client
        self.assertRedirects(response, reverse('ims:site_detail',
                                               kwargs={'siteId':site.pk,}), 
                                 status_code = 302,
                                 target_status_code = 200)
    
    def test_products_add_to_site_inventory_post_invalid_data(self):
        print 'running ProductsAddToSiteInventoryViewTests.test_products_add_to_site_inventory_post_invalid_data... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        (createdSites,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        site = createdSites[0]
        # create another product that has not been added to a site yet
        productName = 'another product'
        code = 'D11'
        product = ProductInformation(name = productName, 
                                     code = code)
        product.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': [len(createdProducts)],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'Save Inventory':'Save Inventory',}
        addItemDict = {}
        addItemDict['codes'] = []
        siteInventory = site.latest_inventory()
        for index in range(len(siteInventory)):
            addItemDict['codes'].append(siteInventory[index].information.pk)
            addItemDict['form-%d-code' % index] = [siteInventory[index].information.pk]
            addItemDict['form-%d-Quantity' % index] = ''
        postData.update(addItemDict)
        response=self.client.post(reverse('ims:products_add_to_site_inventory',
                                         kwargs = {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertIn('More information required before the inventory can be saved',
                         resultWarning,
                         'IMS products_add_to_site_inventory view didn''t generate the correct warning.\nactual message = %s'
                         % resultWarning)
        
    def test_products_add_to_site_inventory_post_without_add_inventoryitem_perm(self):
        print 'running ProductsAddToSiteInventoryViewTests.test_products_add_to_site_inventory_post_without_add_inventoryitem_perm... '
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        (createdSites,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        site = createdSites[0]
        # create another product that has not been added to a site yet
        productName = 'another product'
        code = 'D11'
        product = ProductInformation(name = productName, 
                                     code = code)
        product.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': [len(createdProducts)],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'Save Inventory':'Save Inventory',}
        addItemDict = {}
        addItemDict['codes'] = []
        siteInventory = site.latest_inventory()
        for index in range(len(siteInventory)):
            addItemDict['codes'].append(siteInventory[index].information.pk)
            addItemDict['form-%d-code' % index] = [siteInventory[index].information.pk]
            addItemDict['form-%d-Quantity' % index] = [siteInventory[index].quantity]
        postData.update(addItemDict)
        request=self.factory.post(reverse('ims:products_add_to_site_inventory',
                                         kwargs = {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        request.user = self.user
        add_session_to_request(request)
        response = products_add_to_site_inventory(request, siteId = site.pk)
        resultError = request.session['errorMessage']
        self.assertIn('You don''t have permission to add to site inventory',
                         resultError,
                         'IMS products_add_to_site_inventory view didn''t generate the correct error.\nactual message = %s'
                         % resultError)
        response.client = self.client
        self.assertRedirects(response, reverse('ims:site_detail',
                                               kwargs={'siteId':site.pk,}), 
                                 status_code = 302,
                                 target_status_code = 200)
        
    def test_products_add_to_site_inventory_post_cancel(self):
        print 'running ProductsAddToSiteInventoryViewTests.test_products_add_to_site_inventory_post_cancel... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        (createdSites,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=1,
                                numItems=1)
        site = createdSites[0]
        # create another product that has not been added to a site yet
        productName = 'another product'
        code = 'D11'
        product = ProductInformation(name = productName, 
                                     code = code)
        product.save()
        postData = {'form-MAX_NUM_FORMS': ['1000'],
                    'form-TOTAL_FORMS': [len(createdProducts)],
                    'form-MIN_NUM_FORMS': ['0'],
                    'form-INITIAL_FORMS': ['1'],
                    'Cancel':'Cancel',}
        addItemDict = {}
        addItemDict['codes'] = []
        siteInventory = site.latest_inventory()
        for index in range(len(siteInventory)):
            addItemDict['codes'].append(siteInventory[index].information.pk)
            addItemDict['form-%d-code' % index] = [siteInventory[index].information.pk]
            addItemDict['form-%d-Quantity' % index] = [siteInventory[index].quantity]
        postData.update(addItemDict)
        response=self.client.post(reverse('ims:products_add_to_site_inventory',
                                         kwargs = {'siteId':site.pk,}),
                                  postData,
                                  follow=False)
        self.assertRedirects(response, reverse('ims:site_detail',
                                               kwargs={'siteId':site.pk,}), 
                                 status_code = 302,
                                 target_status_code = 200)

class ImportSitesViewTests(TestCase):
    """
    ims_tests for import_sites view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    
    def test_import_sites_warning_with_file_and_perms(self):
        print 'running ImportSitesViewTests.test_import_sites_warning_with_file_and_perms... '
        perms = ['add_site', 'change_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        with open(os.path.join(
                  APP_DIR,
                  'testData/sites_add_site1_site2_site3.xls'))as fp:
            response=self.client.post(reverse('ims:import_sites'),
                                      {'Import':'Import','file':fp},
                                      follow=True)
        queriedSites=Site.objects.all()
        # check that we saved 3 sites
        self.assertEqual(
             queriedSites.count(),
             3,
            'Number of imported sites mismatch. Some sites didn''t get stored.')
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertEqual(resultWarning, '',
                         'import_sites view generated a warning with a valid file and user.\nactual warning message = %s' 
                         % resultWarning)

    def test_import_sites_warning_file_with_dups(self):
        print 'running ImportSitesViewTests.test_import_sites_warning_file_with_dups... '
        perms = ['add_site', 'change_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        with open(
                  os.path.join(
                  APP_DIR,
                  'testData/sites_add_site1_site2_site3_site3.xls')) as fp:
            response=self.client.post(reverse('ims:import_sites'),
                                      {'Import':'Import','file':fp},
                                      follow=True)
        warningRe = '^.*Found duplicate site numbers.*$'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(re.match(warningRe,resultWarning),
                         'import_sites view generated incorrect warning when import contained duplicates.\nRE for part of desired Warning Message = %s\n\nactual warning message = %s' 
                         % (warningRe, resultWarning))

    def test_import_sites_warning_with_no_file_and_perms(self):
        print 'running ImportSitesViewTests.test_import_sites_warning_with_no_file_and_perms... '
        perms = ['add_site', 'change_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:import_sites'),
                                  {'Import':'Import'},
                                  follow=True)
        warning='No file selected'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertEqual(resultWarning, warning,
                         'import_sites view generated incorrect warning when no file was selected.\ndesired Warning Message = %s\n\nactual warning message = %s' 
                         % (warning, resultWarning))

    def test_import_sites_error_with_file_and_without_add_site_perm(self):
        print 'running ImportSitesViewTests.test_import_sites_error_with_file_and_without_add_site_perm... '
        perms = ['change_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        with open(
                  os.path.join(
                  APP_DIR,
                  'testData/sites_add_site1_site2_site3.xls')) as fp:
            response=self.client.post(reverse('ims:import_sites'),
                                      {'Import Sites':'Import','file':fp},
                                      follow=True)
        warning='You don''t have permission to import sites'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertEqual(resultWarning, warning,
                         'import_sites view generated incorrect warning when user didn''t have add_site perms.\ndesired Warning Message = %s\n\nactual warning message = %s' 
                         % (warning, resultWarning))

    def test_import_sites_error_with_file_and_without_change_site_perm(self):
        print 'running ImportSitesViewTests.test_import_sites_error_with_file_and_without_change_site_perm... '
        perms = ['add_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        with open(os.path.join(
                  APP_DIR,
                  'testData/sites_add_site1_site2_site3.xls')) as fp:
            response=self.client.post(reverse('ims:import_sites'),
                                      {'Import Sites':'Import','file':fp},
                                      follow=True)
        warning='You don''t have permission to import sites'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertEqual(resultWarning, warning,
                         'import_sites view generated incorrect warning when user didn''t have change_site perms.\ndesired Warning Message = %s\n\nactual warning message = %s' 
                         % (warning, resultWarning))
        
        
class ImportProductsViewTests(TestCase):
    """
    ims_tests for import_products view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
        
    def test_import_products_error_with_file_and_perms(self):
        print 'running ImportProductsViewTests.test_import_products_error_with_file_and_perms... '
        perms = ['add_productinformation', 'change_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        with open(os.path.join(
                  APP_DIR,
                  'testData/products_add_prod1_prod2_prod3.xls')) as fp:
            response=self.client.post(reverse('ims:import_products'),
                                      {'Import':'Import','file':fp},
                                      follow=True)
        queriedProducts=ProductInformation.objects.all()
        # check that we saved 3 sites
        self.assertEqual(queriedProducts.count(),
                         3,
                         'Number of imported products mismatch. Some products didn''t get stored. Found %d expected 3' % queriedProducts.count())
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertEqual(resultWarning, 
                         '',
                         'import_products view generated a warning with a valid file and user.\nactual warning message = %s' 
                         % resultWarning)

    def test_import_products_error_file_with_dups(self):
        print 'running ImportProductsViewTests.test_import_products_error_file_with_dups... '
        perms = ['add_productinformation', 'change_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        with open(
                  os.path.join(
                  APP_DIR,
                  'testData/products_add_prod1_prod2_prod3_prod3.xls')) as fp:
            response=self.client.post(reverse('ims:import_products'),
                                      {'Import':'Import','file':fp},
                                      follow=True)
        warningRe = '^.*Found duplicate product codes.*$'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(re.match(warningRe,resultWarning),
                         'import_products view generated incorrect warning when import contained duplicates.\nRE for part of desired Warning Message = %s\n\nactual warning message = %s' 
                         % (warningRe, resultWarning))
        
    def test_import_products_warning_with_no_file_and_perms(self):
        print 'running ImportProductsViewTests.test_import_products_warning_with_no_file_and_perms... '
        perms = ['add_productinformation', 'change_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:import_products'),
                                  {'Import':'Import'},
                                  follow=True)
        warning='No file selected'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertEqual(resultWarning, 
                         warning,
                         'import_products view generated incorrect warning when no file was selected.\ndesired Warning Message = %s\n\nactual warning message = %s' 
                         % (warning, resultWarning))

    def test_import_products_error_with_file_and_without_add_productinformation_perm(self):
        print 'running ImportProductsViewTests.test_import_products_error_with_file_and_without_add_productinformation_perm... '
        perms = ['change_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        with open(os.path.join(
                  APP_DIR,
                  'testData/products_add_prod1_prod2_prod3.xls')) as fp:
            response=self.client.post(reverse('ims:import_products'),
                                      {'Import':'Import','file':fp},
                                      follow=True)
        warning='You don''t have permission to import products'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertEqual(resultWarning,
                         warning,
                         'import_products view generated incorrect warning when user didn''t have add_productinformation perms.\ndesired Warning Message = %s\n\nactual warning message = %s' 
                         % (warning, resultWarning))

    def test_import_products_error_with_file_and_without_change_productinformation_perm(self):
        print 'running ImportProductsViewTests.test_import_products_error_with_file_and_without_change_productinformation_perm... '
        perms = ['add_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        with open(os.path.join(
                  APP_DIR,
                  'testData/products_add_prod1_prod2_prod3.xls')) as fp:
            response=self.client.post(reverse('ims:import_products'),
                                      {'Import':'Import','file':fp},
                                      follow=True)
        warning='You don''t have permission to import products'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertEqual(resultWarning,
                         warning,
                        'import_products view generated incorrect warning when user didn''t have change_productinformation perms.\ndesired Warning Message = %s\n\nactual warning message = %s' 
                        % (warning, resultWarning))
        
        
class ImportInventoryViewTests(TestCase):
    """
    ims_tests for import_inventory view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
        
    def test_import_inventory_error_with_file_and_perms(self):
        print 'running ImportInventoryViewTests.test_import_inventory_error_with_file_and_perms... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with products and sites, so we can
        # import inventory
        filename=os.path.join(APP_DIR,
                              'testData/sites_add_site1_site2_site3.xls')
        Site.parse_sites_from_xls(filename=filename,  
                                    modifier='none',
                                    save=True)
        filename=os.path.join(APP_DIR,
                              'testData/products_add_prod1_prod2_prod3.xls')
        ProductInformation.parse_product_information_from_xls(filename=filename, 
                                                              modifier='none',
                                                              save=True)
        with open(os.path.join(
                  APP_DIR,
                  'testData/inventory_add_10_to_site1_site2_site3_prod1_prod2_prod3.xls')) as fp:
            response=self.client.post(reverse('ims:import_inventory'),
                                      {'Import':'Import','file':fp},
                                      follow=True)
        queriedInventory=InventoryItem.objects.all()
        # check that we saved 3 sites
        self.assertEqual(queriedInventory.count(),
                         9,
                         'Number of imported inventory items mismatch. Some inventory didn''t get stored.')
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertEqual(resultWarning, 
                         '',
                         'imports view generated a warning with a valid file and user.\nactual warning message = %s' 
                         % resultWarning)
    
    def test_import_inventory_error_file_with_dups(self):
        print 'running ImportInventoryViewTests.test_import_inventory_error_file_with_dups... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with products and sites, so we can
        # import inventory
        filename=os.path.join(APP_DIR,
                              'testData/sites_add_site1_site2_site3.xls')
        Site.parse_sites_from_xls(filename=filename,  
                                    modifier='none',
                                    save=True)
        filename=os.path.join(APP_DIR,
                              'testData/products_add_prod1_prod2_prod3.xls')
        ProductInformation.parse_product_information_from_xls(filename=filename, 
                                                              modifier='none',
                                                              save=True)
        with open(
                  os.path.join(
                  APP_DIR,
                  'testData/inventory_add_10_to_site1_site2_site3_prod1_prod2_prod3_dups.xls')) as fp:
            response=self.client.post(reverse('ims:import_inventory'),
                                      {'Import':'Import','file':fp},
                                      follow=True)
        warningRe = '^.*Found duplicate inventory items.*$'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(re.match(warningRe,resultWarning),
                         'import_inventory view generated incorrect warning when import contained duplicates.\nRE for part of desired Warning Message = %s\n\nactual warning message = %s' 
                         % (warningRe, resultWarning))
    
    def test_import_inventory_warning_with_no_file_and_perms(self):
        print 'running ImportInventoryViewTests.test_import_inventory_warning_with_no_file_and_perms... '
        perms = ['add_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with products and sites, so we can
        # import inventory
        filename=os.path.join(APP_DIR,
                              'testData/sites_add_site1_site2_site3.xls')
        Site.parse_sites_from_xls(filename=filename,  
                                    modifier='none',
                                    save=True)
        filename=os.path.join(APP_DIR,
                              'testData/products_add_prod1_prod2_prod3.xls')
        ProductInformation.parse_product_information_from_xls(filename=filename, 
                                                              modifier='none',
                                                              save=True)
        response=self.client.post(reverse('ims:import_inventory'),
                                      {'Import':'Import',},
                                      follow=True)
        warning = 'No file selected'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assertEqual(warning,
                         resultWarning,
                         'import_inventory view generated incorrect warning when no file was selected.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
    def test_import_inventory_error_with_file_and_without_add_inventoryitem_perm(self):
        print 'running ImportInventoryViewTests.test_import_inventory_error_with_file_and_without_add_inventoryitem_perm...'
        self.client.login(username='testUser', password='12345678')
        # populate the database with products and sites, so we can
        # import inventory
        filename=os.path.join(APP_DIR,
                              'testData/sites_add_site1_site2_site3.xls')
        Site.parse_sites_from_xls(filename=filename,  
                                    modifier='none',
                                    save=True)
        filename=os.path.join(APP_DIR,
                              'testData/products_add_prod1_prod2_prod3.xls')
        ProductInformation.parse_product_information_from_xls(filename=filename, 
                                                              modifier='none',
                                                              save=True)
        with open(os.path.join(
                  APP_DIR,
                  'testData/inventory_add_10_to_site1_site2_site3_prod1_prod2_prod3.xls')) as fp:
            response=self.client.post(reverse('ims:import_inventory'),
                                      {'Import':'Import','file':fp},
                                      follow=True)
        warning = 'You don''t have permission to import inventory'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assertEqual(warning,
                         resultWarning,
                         'import_inventory view generated incorrect warning when user didn''t have add_inventoryitem perms.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
        
class SiteDeleteAllViewTests(TestCase):
    """
    ims_tests for site_delete_all view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
        
    def test_site_delete_all_confirmed_with_perms(self):
        print 'running SiteDeleteAllViewTests.test_site_delete_all_confirmed_with_perms... '
        perms = ['delete_site', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        request = self.factory.post(reverse('ims:imports'), 
                                    {'Delete All Sites':'Delete All Sites'},)
        add_session_to_request(request)
        request.user=self.user
        # populate the database with some data
        create_products_with_inventory_items_for_sites(numSites=20,
                                                       numProducts=5,
                                                       numItems=1)
        site_delete_all(request)
        self.assertEqual(Site.objects.all().count(),
                         0,
                         'Did not delete all sites')
        self.assertEqual(InventoryItem.objects.all().count(),
                         0,
                         'Did not delete all inventory')
        
    def test_site_delete_all_confirmed_without_delete_site_perm(self):
        print 'running SiteDeleteAllViewTests.test_site_delete_all_confirmed_without_delete_site_perm... ' 
        perms = ['delete_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        request = self.factory.post(reverse('ims:imports'), 
                                    {'Delete All Sites':'Delete All Sites'},)
        add_session_to_request(request)
        request.user=self.user
        # populate the database with some data
        create_products_with_inventory_items_for_sites(numSites=20,
                                                       numProducts=5,
                                                       numItems=1)
        response=site_delete_all(request)
        warning='You don''t have permission to delete sites or inventory'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(warning in resultWarning, 
                     ('site_delete_all view didn''t generate the appropriate warning when requested to delete all sites without delete_site perms.\ndesired warning message = %s\nactual warning message = %s'
                      % (warning, resultWarning)))
    
    def test_site_delete_all_confirmed_without_delete_inventoryitem_perm(self):
        print 'running SiteDeleteAllViewTests.test_site_delete_all_confirmed_without_delete_inventoryitem_perm... '
        perms = ['delete_site',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        request = self.factory.post(reverse('ims:imports'), 
                                    {'Delete All Sites':'Delete All Sites'},)
        add_session_to_request(request)
        request.user=self.user
        # populate the database with some data
        create_products_with_inventory_items_for_sites( numSites=20,
                                                        numProducts=5,
                                                        numItems=1)
        response=site_delete_all(request)
        warning='You don''t have permission to delete sites or inventory'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(warning in resultWarning, 
                     ('site_delete_all view didn''t generate the appropriate warning when requested to delete all sites without delete_inventory perms.\ndesired warning message = %s\nactual warning message = %s' 
                     % (warning,resultWarning)))
        
    def test_site_delete_all_canceled_with_perms(self):
        print 'running SiteDeleteAllViewTests.test_site_delete_all_canceled_with_perms... '
        perms = ['delete_site', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        request = self.factory.post(reverse('ims:imports'), 
                                    {'Cancel':'Cancel'},)
        add_session_to_request(request)
        request.user=self.user
        # populate the database with some data
        (createdSites,
         __,
         createdInventoryItems,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=20,
                                numProducts=5,
                                numItems=1)
        site_delete_all(request)
        self.assertEqual(Site.objects.all().count(),
                         len(createdSites),
                         'Deleted sites, should have canceled')
        self.assertEqual(InventoryItem.objects.all().count(),
                         len(createdInventoryItems),
                         'Deleted inventory, should have canceled')
        
        
class ProductDeleteAllViewTests(TestCase):
    """
    ims_tests for product_delete_all view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
        
    def test_product_delete_all_confirmed_with_perms(self):
        print 'running ProductDeleteAllViewTests.test_product_delete_all_confirmed_with_perms... '
        perms = ['delete_productinformation', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        request = self.factory.post(reverse('ims:imports'), 
                                    {'Delete All Products':'Delete All Products'},)
        add_session_to_request(request)
        request.user=self.user
        # populate the database with some data
        create_products_with_inventory_items_for_sites(
                                            numSites=20,
                                            numProducts=5,
                                            numItems=1)
        product_delete_all(request)
        self.assertEqual(ProductInformation.objects.all().count(),
                         0,
                         'Did not delete all products')
        self.assertEqual(InventoryItem.objects.all().count(),
                         0,
                         'Did not delete all inventory')
        
    def test_product_delete_all_confirmed_without_delete_productinformation_perm(self):
        print 'running ProductDeleteAllViewTests.test_product_delete_all_confirmed_without_delete_productinformation_perm... '
        perms = ['delete_inventoryitem',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        request = self.factory.post(reverse('ims:imports'), 
                                    {'Delete All Products':'Delete All Products'},)
        add_session_to_request(request)
        request.user=self.user
        # populate the database with some data
        create_products_with_inventory_items_for_sites(numSites=20,
                                                       numProducts=5,
                                                       numItems=1)
        response=product_delete_all(request)
        warning='You don''t have permission to delete products or inventory'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(warning in resultWarning, 
                     'product_delete_all view didn''t generate the appropriate warning when requested to delete all products without delete_productinformation perms.\ndesired warning message = %s\nactual warning message = %s' 
                     % (warning, resultWarning))
    
    def test_product_delete_all_confirmed_without_delete_inventoryitem_perm(self):
        print 'running ProductDeleteAllViewTests.test_product_delete_all_confirmed_without_delete_inventoryitem_perm... '
        perms = ['delete_productinformation',]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        request = self.factory.post(reverse('ims:imports'), 
                                    {'Delete All Products':'Delete All Products'},)
        add_session_to_request(request)
        request.user=self.user
        # populate the database with some data
        create_products_with_inventory_items_for_sites(numSites=20,
                                                       numProducts=5,
                                                       numItems=1)
        response=product_delete_all(request)
        warning='You don''t have permission to delete products or inventory'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(warning in resultWarning, 
                     'product_delete_all view didn''t generate the appropriate warning when requested to delete all products without delete_inventoryitem perms.\ndesired warning message = %s\nactual warning message = %s' 
                     % (warning, resultWarning))
        
    def test_product_delete_all_canceled_with_perms(self):
        print 'running ProductDeleteAllViewTests.test_product_delete_all_canceled_with_perms... '
        perms = ['delete_productinformation', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        request = self.factory.post(reverse('ims:imports'), 
                                    {'Cancel':'Cancel'},)
        add_session_to_request(request)
        request.user=self.user
        # populate the database with some data
        (createdSites,
         __,
         createdInventoryItems,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=20,
                                numProducts=5,
                                numItems=1)
        product_delete_all(request)
        self.assertEqual(Site.objects.all().count(),
                         len(createdSites),
                         'Deleted products, should have canceled')
        self.assertEqual(InventoryItem.objects.all().count(),
                         len(createdInventoryItems),
                         'Deleted inventory, should have canceled')
        
        
class InventoryDeleteAllViewTests(TestCase):
    """
    ims_tests for product_delete_all view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
        
    def test_inventory_delete_all_confirmed_with_perms(self):
        print 'running InventoryDeleteAllViewTests.test_inventory_delete_all_confirmed_with_perms... '
        perms = ['delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        request = self.factory.post(reverse('ims:imports'), 
                                    {'Delete All Inventory':'Delete All Inventory'},)
        add_session_to_request(request)
        request.user=self.user
        # populate the database with some data
        create_products_with_inventory_items_for_sites(numSites=20,
                                                       numProducts=5,
                                                       numItems=1)
        inventory_delete_all(request)
        self.assertEqual(InventoryItem.objects.all().count(),
                         0,
                         'Did not delete all inventory')
        
    def test_inventory_delete_all_confirmed_without_delete_inventoryitem_perm(self):
        print 'running InventoryDeleteAllViewTests.test_inventory_delete_all_confirmed_without_delete_inventoryitem_perm... '
        perms = []
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        request = self.factory.post(reverse('ims:imports'), 
                                    {'Delete All Inventory':'Delete All Inventory'},)
        add_session_to_request(request)
        request.user=self.user
        # populate the database with some data
        create_products_with_inventory_items_for_sites(numSites=20,
                                                       numProducts=5,
                                                       numItems=1)
        response=inventory_delete_all(request)
        warning='You don''t have permission to delete inventory'
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(warning in resultWarning, 
                     'imports view didn''t generate the appropriate warning when requested to delete all inventory without delete_inventoryitem perms.\ndesired warning message = %s\nactual warning message = %s' 
                     % (warning, resultWarning))
        
    def test_inventory_delete_all_canceled_with_perms(self):
        print 'running InventoryDeleteAllViewTests.test_inventory_delete_all_canceled_with_perms... '
        perms = ['delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        request = self.factory.post(reverse('ims:imports'), 
                                    {'Cancel':'Cancel'},)
        add_session_to_request(request)
        request.user=self.user
        # populate the database with some data
        (__,
         __,
         createdInventoryItems,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=20,
                                numProducts=5,
                                numItems=1)
        inventory_delete_all(request)
        self.assertEqual(InventoryItem.objects.all().count(),
                         len(createdInventoryItems),
                         'Deleted inventory, should have canceled')
    
        
class ImportsViewTests(TestCase):
    """
    ims_tests for Imports view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
    
    def test_delete_sites_warning_with_perms(self):
        print 'running ImportsViewTests.test_delete_sites_warning_with_perms... '
        perms = ['delete_site', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        (createdSites,
         __,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=20,
                                numProducts=5,
                                numItems=1)
        warning=('Delete all %d sites?  This will delete all inventory as well.'
                 % len(createdSites))
        response=self.client.post(reverse('ims:imports'),
                                  {'Delete Sites':'Delete'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assert_(warning in resultWarning, 
                     "imports view didn't generate the appropriate warning when requested to delete all sites with appropriate perms.\ndesired warning message = %s\nactual warning message = " 
                     % resultWarning)
    
    def test_delete_sites_error_without_delete_site_perm(self):
        print 'running ImportsViewTests.test_delete_sites_error_without_delete_site_perm... '
        perms = ['delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        create_products_with_inventory_items_for_sites(numSites=20,
                                                       numProducts=5,
                                                       numItems=1)
        warning='You don''t have permission to delete sites or inventory'
        response=self.client.post(reverse('ims:imports'), {'Delete Sites':'Delete'}, follow=True)
        resultWarning = get_announcement_from_response(response=response, cls="errornote")
        self.assert_(warning in resultWarning, 
                     'imports view didn''t generate the appropriate warning when requested to delete all sites without delete_site perms.\ndesired warning message = %s\nactual warning message = %s' 
                     % (warning, resultWarning))
    
    def test_delete_sites_error_without_delete_inventoryitem_perm(self):
        print 'running ImportsViewTests.test_delete_sites_error_without_delete_inventoryitem_perm... '
        perms = ['delete_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        create_products_with_inventory_items_for_sites(numSites=20,
                                                       numProducts=5,
                                                       numItems=1)
        warning='You don''t have permission to delete sites or inventory'
        response=self.client.post(reverse('ims:imports'),
                                  {'Delete Sites':'Delete'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(warning in resultWarning, 
                     'imports view didn''t generate the appropriate warning when requested to delete all sites without delete_inventory perms.\ndesired warning message = %s\nactual warning message = %s' 
                      % (warning,resultWarning))

    def test_export_sites(self):
        print 'running ImportsViewTests.test_export_sites... '
        # populate the database with some data
        (createdSites,
         __,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                 numSites=3,
                                 numProducts=5,
                                 numItems=1,
                                 modifier='testUser')
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Export Sites':'All'},
                                  follow=True)
        parsedExportedSites,__=Site.parse_sites_from_xls( 
                                            file_contents=response.content,
                                            save=False)
        sortedParsedExportedSites=[]
        for site in parsedExportedSites:
            sortedParsedExportedSites.append(site.create_key_no_microseconds())
        sortedParsedExportedSites.sort()
        sortedCreatedSites=[]
        for site in createdSites:
            sortedCreatedSites.append(site.create_key_no_microseconds())
        sortedCreatedSites.sort()
        self.assertListEqual(sortedParsedExportedSites,
                             sortedCreatedSites,
                             'Sites exported to Excel don''t match the sites in the database')
    
    def test_delete_products_warning_with_perms(self):
        print'running ImportsViewTests.test_delete_products_warning_with_perms... '
        perms = ['delete_productinformation', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        (__,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=20,
                                numProducts=5,
                                numItems=1)
        warning=('Delete all %d products? This will delete all inventory as well.' 
                % len(createdProducts))
        response=self.client.post(reverse('ims:imports'),
                                  {'Delete Products':'Delete'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        self.assert_(warning in resultWarning, 
                     'imports view didn''t generate the appropriate warning when requested to delete all products with appropriate perms.\ndesired warning message = %s\nactual warning message = %s' 
                     % (warning, resultWarning))
    
    def test_delete_products_error_without_delete_productinformation_perm(self):
        print 'running ImportsViewTests.test_delete_products_error_without_delete_productinformation_perm... '
        perms = ['delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        create_products_with_inventory_items_for_sites(numSites=20,
                                                       numProducts=5,
                                                       numItems=1)
        warning='You don''t have permission to delete products or inventory'
        response=self.client.post(reverse('ims:imports'),
                                  {'Delete Products':'Delete'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(warning in resultWarning, 
                     'imports view didn''t generate the appropriate warning when requested to delete all products without delete_productinformation perms.\ndesired warning message = %s\nactual warning message = %s' 
                     % (warning,resultWarning))
        
    def test_delete_products_error_without_delete_inventoryitem_perm(self):
        print 'running ImportsViewTests.test_delete_products_error_without_delete_inventoryitem_perm... '
        perms = ['delete_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        create_products_with_inventory_items_for_sites(numSites=20,
                                                       numProducts=5,
                                                       numItems=1)
        warning='You don''t have permission to delete products or inventory'
        response=self.client.post(reverse('ims:imports'),
                                  {'Delete Products':'Delete'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(warning in resultWarning, 
                     'imports view didn''t generate the appropriate warning when requested to delete all products without delete_inventory perms.\ndesired warning message = %s\nactual warning message = %s' 
                     % (warning, resultWarning))

    def test_export_products(self):
        print 'running ImportsViewTests.test_export_products... '
        # populate the database with some data
        (__,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=3,
                                numProducts=5,
                                numItems=1,
                                modifier='testUser')
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Export Products':'All'},
                                  follow=True)
        (parsedExportedProducts,
         __)=ProductInformation.parse_product_information_from_xls(
                         file_contents=response.content, 
                         save=True)
        sortedParsedExportedProducts=[]
        for product in parsedExportedProducts:
            sortedParsedExportedProducts.append(product.create_key_no_microseconds())
        sortedParsedExportedProducts.sort()
        sortedCreatedProducts=[]
        for product in createdProducts:
            sortedCreatedProducts.append(product.create_key_no_microseconds())
        sortedCreatedProducts.sort()
        self.assertListEqual(sortedParsedExportedProducts,
                             sortedCreatedProducts, 
                             'Products exported to Excel don''t match the products in the database')
    
    def test_delete_inventory_warning_with_perms(self):
        print 'running ImportsViewTests.test_delete_inventory_warning_with_perms... '
        perms = ['delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        (__,
         __,
         createdInventoryItems,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=20,
                                numProducts=5,
                                numItems=1)
        warning='Delete all %d inventory items?' % len(createdInventoryItems)
        response=self.client.post(reverse('ims:imports'),
                                  {'Delete Inventory':'Delete'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response, 
                                                       cls="warningnote")
        self.assert_(warning in resultWarning, 
                     'imports view didn''t generate the appropriate warning when requested to delete all inventory with appropriate perms.\ndesired warning message = %s\nactual warning message = %s' 
                     % (warning, resultWarning))
    
    def test_delete_inventory_error_without_delete_inventory_perm(self):
        print 'running ImportsViewTests.test_delete_inventory_error_without_delete_inventory_perm... '
        perms = ['delete_productinformation']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        create_products_with_inventory_items_for_sites(numSites=20,
                                                       numProducts=5,
                                                       numItems=1)
        warning='You don''t have permission to delete inventory'
        response=self.client.post(reverse('ims:imports'),
                                  {'Delete Inventory':'Delete'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        self.assert_(warning in resultWarning, 
                     'imports view didn''t generate the appropriate warning when requested to delete all inventory without delete_inventory perms.\ndesired warning message = %s\nactual warning message = %s' 
                     % (warning, resultWarning))
        
    def test_export_all_inventory(self):
        print 'running ImportsViewTests.test_export_all_inventory... '
        # populate the database with some data
        (createdSites,
         __,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=3,
                                numProducts=5,
                                numItems=3,
                                modifier='testUser')
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Export All Inventory':'All'},
                                  follow=True)
        (parsedExportedInventory,
         __)=InventoryItem.parse_inventory_from_xls(
                           file_contents=response.content, 
                           save=False)
        sortedParsedExportedInventory=[]
        for item in parsedExportedInventory:
            sortedParsedExportedInventory.append(item.create_key_no_pk_no_microseconds())
        sortedParsedExportedInventory.sort()
        sortedCreatedInventory=[]
        for site in createdSites:
            for item in site.inventoryitem_set.all():
                sortedCreatedInventory.append(item.create_key_no_pk_no_microseconds())
        sortedCreatedInventory.sort()
        self.assertListEqual(sortedParsedExportedInventory,
                             sortedCreatedInventory,
                             'Inventory exported to Excel doesn''t match the inventory in the database')
        
    def test_export_current_inventory(self):
        print 'running ImportsViewTests.test_export_current_inventory... '
        # populate the database with some data
        (createdSites,
         __,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=3,
                                numProducts=5,
                                numItems=3,
                                modifier='testUser')
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Export Latest Inventory':'Current'},
                                  follow=True)
        (parsedExportedInventory,
         __)=InventoryItem.parse_inventory_from_xls(
                           file_contents=response.content, 
                           save=False)
        sortedParsedExportedInventory=[]
        for item in parsedExportedInventory:
            sortedParsedExportedInventory.append(item.create_key_no_pk_no_microseconds())
        sortedParsedExportedInventory.sort()
        sortedCreatedInventory=[]
        for site in createdSites:
            for item in site.latest_inventory():
                sortedCreatedInventory.append(item.create_key_no_pk_no_microseconds())
        sortedCreatedInventory.sort()
        self.assertListEqual(sortedParsedExportedInventory,
                             sortedCreatedInventory,
                             'Inventory exported to Excel doesn''t match the inventory in the database')
    
    def test_backup(self):
        print 'running ImportsViewTests.test_backup... '
        # populate the database with some data
        (createdSites,
         createdProducts,
         __,
         __)=create_products_with_inventory_items_for_sites(
                                numSites=3,
                                numProducts=5,
                                numItems=3,
                                modifier='testUser')
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Backup':'Backup'},
                                  follow=True)
        try:
            f = StringIO.StringIO(response.content)
            zipArchive = zipfile.ZipFile(f, 'r')
            backups = [filename for filename in zipArchive.namelist() if 'Backup' in filename]
            self.assertTrue(len(backups) > 0,'No Backup spreadsheet in the archive')
            if backups:
                fileContents=zipArchive.open(backups[0],'r').read()
            zipArchive.close()
            (parsedBackedUpInventory,
             __)=InventoryItem.parse_inventory_from_xls(
                               file_contents=fileContents, 
                               save=False)
            parsedBackedUpSites,__=Site.parse_sites_from_xls(
                                file_contents=fileContents,
                                save=False)
            parsedBackedUpProducts,__=ProductInformation.parse_product_information_from_xls(
                                file_contents=fileContents,
                                save=False)
        finally:
            zipArchive.close()
            f.close()
        # Compare inventory
        sortedParsedBackedUpInventory=[]
        for item in parsedBackedUpInventory:
            sortedParsedBackedUpInventory.append(item.create_key_no_pk_no_microseconds())
        sortedParsedBackedUpInventory.sort()
        sortedCreatedInventory=[]
        for site in createdSites:
            for item in site.inventoryitem_set.all():
                sortedCreatedInventory.append(item.create_key_no_pk_no_microseconds())
        sortedCreatedInventory.sort()
        self.assertListEqual(sortedParsedBackedUpInventory,
                             sortedCreatedInventory,
                             'Inventory exported to Excel backup doesn''t match the inventory in the database')
        # compare sites
        sortedParsedBackedUpSites=[]
        for site in parsedBackedUpSites:
            sortedParsedBackedUpSites.append(site.create_key_no_microseconds())
        sortedParsedBackedUpSites.sort()
        sortedCreatedSites=[]
        for site in createdSites:
            sortedCreatedSites.append(site.create_key_no_microseconds())
        sortedCreatedSites.sort()
        self.assertListEqual(sortedParsedBackedUpSites,
                             sortedCreatedSites,
                             'Sites exported to Excel backup don''t match the sites in the database')
        # compare products
        sortedParsedBackedUpProducts=[]
        for product in parsedBackedUpProducts:
            sortedParsedBackedUpProducts.append(product.create_key_no_microseconds())
        sortedParsedBackedUpProducts.sort()
        sortedCreatedProducts=[]
        for product in createdProducts:
            sortedCreatedProducts.append(product.create_key_no_microseconds())
        sortedCreatedProducts.sort()
        self.assertListEqual(sortedParsedBackedUpProducts,
                             sortedCreatedProducts,
                             'Products exported to Excel backup don''t match the products in the database')
        
    def test_restore_error_without_add_inventoryitem_perm(self):
        print 'running ImportsViewTests.test_restore_error_without_add_inventoryitem_perm... '
        perms = [
                 'change_inventoryitem',
                 'delete_inventoryitem',
                 'add_productinformation',
                 'change_productinformation',
                 'delete_productinformation',
                 'add_site',
                 'change_site',
                 'delete_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Restore':'Restore'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        warning = 'You don''t have permission to restore the database'
        self.assertEqual(warning,resultWarning,'imports view generated incorrect warning when user without add_inventoryitem perm requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
    def test_restore_error_without_change_inventoryitem_perm(self):
        print 'running ImportsViewTests.test_restore_error_without_change_inventoryitem_perm... '
        perms = ['add_inventoryitem',
                 
                 'delete_inventoryitem',
                 'add_productinformation',
                 'change_productinformation',
                 'delete_productinformation',
                 'add_site',
                 'change_site',
                 'delete_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Restore':'Restore'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        warning = 'You don''t have permission to restore the database'
        self.assertEqual(warning,resultWarning,'imports view generated incorrect warning when user without change_inventoryitem perm requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
    def test_restore_error_without_delete_inventoryitem_perm(self):
        print 'running ImportsViewTests.test_restore_error_without_delete_inventoryitem_perm... '
        perms = ['add_inventoryitem',
                 'change_inventoryitem',

                 'add_productinformation',
                 'change_productinformation',
                 'delete_productinformation',
                 'add_site',
                 'change_site',
                 'delete_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Restore':'Restore'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        warning = 'You don''t have permission to restore the database'
        self.assertEqual(warning,resultWarning,'imports view generated incorrect warning when user without delete_inventoryitem perm requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
    def test_restore_error_without_add_productinformation_perm(self):
        print 'running ImportsViewTests.test_restore_error_without_add_productinformation_perm... '
        perms = ['add_inventoryitem',
                 'change_inventoryitem',
                 'delete_inventoryitem',

                 'change_productinformation',
                 'delete_productinformation',
                 'add_site',
                 'change_site',
                 'delete_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Restore':'Restore'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        warning = 'You don''t have permission to restore the database'
        self.assertEqual(warning,resultWarning,'imports view generated incorrect warning when user without add_productinformation perm requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
    def test_restore_error_without_change_productinformation_perm(self):
        print 'running ImportsViewTests.test_restore_error_without_change_productinformation_perm... '
        perms = ['add_inventoryitem',
                 'change_inventoryitem',
                 'delete_inventoryitem',
                 'add_productinformation',

                 'delete_productinformation',
                 'add_site',
                 'change_site',
                 'delete_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Restore':'Restore'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        warning = 'You don''t have permission to restore the database'
        self.assertEqual(warning,resultWarning,'imports view generated incorrect warning when user without change_productinformation perm requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
    def test_restore_error_without_delete_productinformation_perm(self):
        print 'running ImportsViewTests.test_restore_error_without_delete_productinformation_perm... '
        perms = ['add_inventoryitem',
                 'change_inventoryitem',
                 'delete_inventoryitem',
                 'add_productinformation',
                 'change_productinformation',

                 'add_site',
                 'change_site',
                 'delete_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Restore':'Restore'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        warning = 'You don''t have permission to restore the database'
        self.assertEqual(warning,resultWarning,'imports view generated incorrect warning when user without delete_productinformation perm requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
    
    def test_restore_error_without_add_site_perm(self):
        print 'running ImportsViewTests.test_restore_error_without_add_site_perm... '
        perms = ['add_inventoryitem',
                 'change_inventoryitem',
                 'delete_inventoryitem',
                 'add_productinformation',
                 'change_productinformation',
                 'delete_productinformation',

                 'change_site',
                 'delete_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Restore':'Restore'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        warning = 'You don''t have permission to restore the database'
        self.assertEqual(warning,resultWarning,'imports view generated incorrect warning when user without add_site perm requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
    def test_restore_error_without_change_site_perm(self):
        print 'running ImportsViewTests.test_restore_error_without_change_site_perm... '
        perms = ['add_inventoryitem',
                 'change_inventoryitem',
                 'delete_inventoryitem',
                 'add_productinformation',
                 'change_productinformation',
                 'delete_productinformation',
                 'add_site',

                 'delete_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Restore':'Restore'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        warning = 'You don''t have permission to restore the database'
        self.assertEqual(warning,resultWarning,'imports view generated incorrect warning when user without change_site perm requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
    def test_restore_error_without_delete_site_perm(self):
        print 'running ImportsViewTests.test_restore_error_without_delete_site_perm... '
        perms = ['add_inventoryitem',
                 'change_inventoryitem',
                 'delete_inventoryitem',
                 'add_productinformation',
                 'change_productinformation',
                 'delete_productinformation',
                 'add_site',
                 'change_site',
                 ]
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Restore':'Restore'},
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        warning = 'You don''t have permission to restore the database'
        self.assertEqual(warning,resultWarning,'imports view generated incorrect warning when user without delete_site perm requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))


class RestoreViewTests(TestCase):
    """
    restore view ims_tests
    """
    
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        
        
    def test_restore_get_warning_with_perms(self):
        print 'running RestoreViewTests.test_restore_get_warning_with_perms... '
        perms = ['add_inventoryitem',
                 'change_inventoryitem',
                 'delete_inventoryitem',
                 'add_productinformation',
                 'change_productinformation',
                 'delete_productinformation',
                 'add_site',
                 'change_site',
                 'delete_site']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.get(reverse('ims:restore'),
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        warning = 'Restoring the database will cause all current information to be replaced!!!'
        self.assertEqual(warning,resultWarning,'restore view generated incorrect warning when user requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
    
    def test_restore_get_error_without_perms(self):
        print 'running RestoreViewTests.test_restore_get_warning_without_perms... '
        self.client.login(username='testUser', password='12345678')
        response=self.client.get(reverse('ims:restore'),
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="errornote")
        warning = 'You don''t have permission to restore the database'
        self.assertEqual(warning,resultWarning,'restore view generated incorrect warning when unauthorized user requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
    def test_restore_info_with_perms(self):
        print 'running RestoreViewTests.test_restore_info_with_perms... '
        perms = ['add_inventoryitem',
                 'change_inventoryitem',
                 'delete_inventoryitem',
                 'add_productinformation',
                 'change_productinformation',
                 'delete_productinformation',
                 'add_site',
                 'change_site',
                 'delete_site',
                 'add_productcategory',
                 'change_productcategory',
                 'delete_productcategory']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        with open(os.path.join(
                  APP_DIR,
                  'testData/Backup_3site_3prod_inventory10.zip')) as fp:
            response=self.client.post(reverse('ims:restore'),
                                      {'Restore':'Restore','file':fp},
                                      format = 'multipart',
                                      follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="infonote")
        warning = 'Successful restore of sites using "Backup_3site_3prod_inventory10.zip"<br/>Successful restore of categories using "Backup_3site_3prod_inventory10.zip"<br/>Successful restore of sites using "Backup_3site_3prod_inventory10.zip"<br/>Successful restore of products using "Backup_3site_3prod_inventory10.zip"<br/>Successful restore of inventory using "Backup_3site_3prod_inventory10.zip"<br/>'
        self.assertEqual(warning,resultWarning,'restore view generated incorrect warning when user requested a database restore.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
    def test_restore_warning_no_file_with_perms(self):
        print 'running RestoreViewTests.test_restore_warning_no_file_with_perms... '
        perms = ['add_inventoryitem',
                 'change_inventoryitem',
                 'delete_inventoryitem',
                 'add_productinformation',
                 'change_productinformation',
                 'delete_productinformation',
                 'add_site',
                 'change_site',
                 'delete_site',
                 'add_productcategory',
                 'change_productcategory',
                 'delete_productcategory']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:restore'),
                                  {'Restore':'Restore'},
                                  format = 'multipart',
                                  follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="warningnote")
        warning = 'No file selected'
        self.assertEqual(warning,resultWarning,'restore view generated incorrect warning when user requested a database restore with no file selected.\ndesired Warning Message = %s\n\nactual warning message = %s'
                         % (warning, resultWarning))
        
    def test_restore_error_bad_file_with_perms(self):
        print 'running RestoreViewTests.test_restore_error_bad_file_with_perms... '
        perms = ['add_inventoryitem',
                 'change_inventoryitem',
                 'delete_inventoryitem',
                 'add_productinformation',
                 'change_productinformation',
                 'delete_productinformation',
                 'add_site',
                 'change_site',
                 'delete_site',
                 'add_productcategory',
                 'change_productcategory',
                 'delete_productcategory']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        with open(os.path.join(
                  APP_DIR,
                  'testData/Backup_3site_3prod_inventory10.xls')) as fp:
            response=self.client.post(reverse('ims:restore'),
                                      {'Restore':'Restore','file':fp},
                                      format = 'multipart',
                                      follow=True)
        resultError = get_announcement_from_response(response=response,
                                                       cls="errornote")
        error = "Error while trying to restore database from backup archive:<br/>\"Backup_3site_3prod_inventory10.xls\".<br/><br/>Error Message:<br/> BadZipfile('File is not a zip file',)"
        self.assertIn(error,resultError,'restore view generated incorrect error when user requested a database restore with an invalid file.\ndesired Error Message = %s\n\nactual error message = %s'
                         % (error, resultError))