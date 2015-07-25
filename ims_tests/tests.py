from django.test import TestCase, RequestFactory
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.auth.models import User, Permission
from django.contrib.sessions.middleware import SessionMiddleware
from collections import OrderedDict
import os, re
# Create your ims_tests here.
from ims.models import Site, ProductInformation, InventoryItem
from ims.views import inventory_delete_all, site_delete_all, product_delete_all
from ims.settings import PAGE_SIZE, APP_DIR

TEST_LOG = os.path.join(APP_DIR,
                        'testData/redcross.log')

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
                                                   modifier='none'):
    sitesList=[]
    productList=[]
    inventoryItemList=[]
    for m in range(numSites):
        siteName="test site "+str(m+1)
        site=Site(name=siteName,)
        site.save()
        sitesList.append(site)
        for n in range(numProducts):
            if m == 0:
                productName="test product "+str(n+1)
                productCode="pdt"+str(n+1)
                product=ProductInformation(name=productName, code=productCode,)
                product.save()
                productList.append(product)
            else:
                product=ProductInformation.objects.get(pk="pdt"+str(n+1))
            for p in range(numItems):
                # increment the quantity for each addition of a new item for 
                # the same product code, so we can distinguish them
                site,product,inventoryItem=create_inventory_item_for_site(
                                            site=site,
                                            product=product,
                                            quantity=p+1,
                                            deleted=0,
                                            modifier=modifier)
                inventoryItemList.append(inventoryItem)
    return sitesList,productList,inventoryItemList

def get_announcement_from_response(response=None, cls=None):
    if response and cls:
        m=re.search(('^.*<div\s*id="announcement".*?<p.*?class="' +
                    cls + '">\s*<img.*?</img>\s*<img.*?</img>\s*(.*?)\s*</p>.*?</div>'),
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
    
    def setUp(self):
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
    #Site inventory ims_tests
    def test_latest_inventory_after_initial_creation(self):
        """
        site.latest_inventory should only return the latest change
        """
        print 'running SiteMethodTests.test_latest_inventory_after_initial_creation... '
        (createdSites,
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
         
    def test_latest_inventory_after_3_quantity_change_and_deletion(self):
        """
        site.latest_inventory should only return the latest change and not
        return any deleted items.
        """
        print 'running SiteMethodTests.test_latest_inventory_after_3_quantity_change_and_deletion... '
        (createdSites,
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
        (site,
         product,
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
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
                                numSites=1,
                                numProducts=3,
                                numItems=3,
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
    
    def test_parse_sites_from_xls_initial(self):
        """
        import 3 sites from Excel
        """
        print 'running SiteMethodTests.test_parse_sites_from_xls_initial... '
        filename=os.path.join(APP_DIR,
                              'testData/sites_add_site1_site2_site3.xls')
        importedSites,siteMessage=Site.parse_sites_from_xls(filename=filename, 
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
        importedSites,siteMessage=Site.parse_sites_from_xls(filename=filename, 
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
        importedSites, siteMessage=Site.parse_sites_from_xls(filename=filename, 
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
        importedSites, siteMessage=Site.parse_sites_from_xls(filename=filename, 
                                                             modifier='none',
                                                             save=True)
        self.assert_('Xlrdutils' in siteMessage,
                     ('Failure to recognize a file with bad date format.\nSite.parse_sites_from_xls returned: %s'
                      % siteMessage))
    
class ProductInformationMethodTests(TestCase):
    """
    ProductInformation class method ims_tests
    """
    
    def setUp(self):
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
        
    def test_parse_product_information_from_xls_initial(self):
        """
        import 3 products from Excel
        """
        print 'running ProductInformationMethodTests.test_parse_product_information_from_xls_initial... '
        filename=os.path.join(APP_DIR,
                              'testData/products_add_prod1_prod2_prod3.xls')
        (importedProducts,
         productMessage)=ProductInformation.parse_product_information_from_xls(
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
         siteMessage)=ProductInformation.parse_product_information_from_xls(
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
        (importedProducts,
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
        (importedProducts,
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
    
    def setUp(self):
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
        
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
         inventoryMessage)=InventoryItem.parse_inventory_from_xls(
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
         inventoryMessage)=InventoryItem.parse_inventory_from_xls(
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
        (importedInventoryItems,
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
        (importedInventoryItems,
         inventoryMessage)=InventoryItem.parse_inventory_from_xls(
                           filename=filename, 
                           modifier='none',
                           save=True)
        self.assert_('Xlrdutils' in inventoryMessage,
                     ('Failure to recognize a file with bad date format.\nInventoryItem.parse_inventory_from_xl returned: %s'
                      % inventoryMessage))
        
class HomeViewTests(TestCase):
    """
    ims_tests for Home view
    """
    
    def setUp(self):
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
        
    def test_home_for_latest_changes_1(self):
        """
        The home view should display sites with recently edited inventory with
        the latest changes at the top and latest inventory changes with the
        latest changes at the top as well
        """
        print 'running HomeViewTests.test_home_for_latest_changes_1... '
        (createdSites,
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
        (createdSites,
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
        
        
class ImportSitesViewTests(TestCase):
    """
    ims_tests for import_sites view
    """
    def setUp(self):
        # Most ims_tests need access to the request factory and/or a user.
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testUser', password='12345678')
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
    
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
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
        
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
                         'Number of imported products mismatch. Some products didn''t get stored.')
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
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
        
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
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
        
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
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
        
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
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
        
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
        response=inventory_delete_all(request)
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
        (createdSites,
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
                                numSites=20,
                                numProducts=5,
                                numItems=1)
        response=inventory_delete_all(request)
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
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
    
    def test_delete_sites_warning_with_perms(self):
        print 'running ImportsViewTests.test_delete_sites_warning_with_perms... '
        perms = ['delete_site', 'delete_inventoryitem']
        permissions = Permission.objects.filter(codename__in = perms)
        self.user.user_permissions=permissions
        self.client.login(username='testUser', password='12345678')
        # populate the database with some data
        (createdSites,
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
         createdProducts,
         createdIinventoryItems)=create_products_with_inventory_items_for_sites(
                                 numSites=3,
                                 numProducts=5,
                                 numItems=1,
                                 modifier='testUser')
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Export Sites':'All'},
                                  follow=True)
        parsedExportedSites,siteMessage=Site.parse_sites_from_xls( 
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
        (createdSites,
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
        (createdSites,
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
                                numSites=3,
                                numProducts=5,
                                numItems=1,
                                modifier='testUser')
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Export Products':'All'},
                                  follow=True)
        (parsedExportedProducts,
         productMessage)=ProductInformation.parse_product_information_from_xls(
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
        (createdSites,
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
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
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
                                numSites=3,
                                numProducts=5,
                                numItems=3,
                                modifier='testUser')
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Export All Inventory':'All'},
                                  follow=True)
        (parsedExportedInventory,
         inventoryMessage)=InventoryItem.parse_inventory_from_xls(
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
         createdProducts,
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
                                numSites=3,
                                numProducts=5,
                                numItems=3,
                                modifier='testUser')
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Export Latest Inventory':'Current'},
                                  follow=True)
        (parsedExportedInventory,
         inventoryMessage)=InventoryItem.parse_inventory_from_xls(
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
         createdInventoryItems)=create_products_with_inventory_items_for_sites(
                                numSites=3,
                                numProducts=5,
                                numItems=3,
                                modifier='testUser')
        self.client.login(username='testUser', password='12345678')
        response=self.client.post(reverse('ims:imports'),
                                  {'Backup':'Backup'},
                                  follow=True)
        fileContents=response.content
        (parsedBackedUpInventory,
         inventoryMessage)=InventoryItem.parse_inventory_from_xls(
                           file_contents=fileContents, 
                           save=False)
        parsedBackedUpSites,siteMessage=Site.parse_sites_from_xls(
                            file_contents=fileContents,
                            save=False)
        parsedBackedUpProducts,productMessage=ProductInformation.parse_product_information_from_xls(
                            file_contents=fileContents,
                            save=False)
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
        try:
            os.remove(TEST_LOG)
        except OSError:
            pass
        settings.LOG_FILE=TEST_LOG
        
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
        print 'running RestoreViewTests.test_restore_warning_with_perms... '
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
        with open(os.path.join(
                  APP_DIR,
                  'testData/backup_3site_3prod_inventory10.xls')) as fp:
            response=self.client.post(reverse('ims:restore'),
                                      {'Restore':'Restore','file':fp},
                                      format = 'multipart',
                                      follow=True)
        resultWarning = get_announcement_from_response(response=response,
                                                       cls="infonote")
        warning = 'Successful restore of sites using "backup_3site_3prod_inventory10.xls"<br/>Successful restore of products using "backup_3site_3prod_inventory10.xls"<br/>Successful restore of inventory using "backup_3site_3prod_inventory10.xls"<br/>'
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
                 'delete_site']
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