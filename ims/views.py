from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.urlresolvers import reverse
from django.core.files import File
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.forms.models import modelformset_factory
from django.utils.dateparse import parse_datetime, parse_date, date_re
from django.conf import settings
from django.db import transaction
from .settings import PAGE_SIZE
from .models import Site, InventoryItem, ProductInformation, ProductCategory
from .forms import InventoryItemFormNoSite, InventoryItemFormAddSubtractNoSite,\
ProductInformationForm, ProductInformationFormWithQuantity, SiteForm, \
SiteFormReadOnly, SiteListForm,ProductListFormWithDelete, TitleErrorList, \
DateSpanQueryForm, ProductListFormWithAdd, UploadFileForm, \
ProductListFormWithoutDelete
from collections import OrderedDict
from subprocess import check_call, check_output, CalledProcessError
import os
import datetime
import pytz
import re
import xlwt
import logging
import StringIO
import zipfile
from xlrdutils.xlrdutils import XlrdutilsError

try:
    adminName = settings.SITE_ADMIN[0]
except AttributeError:
    adminName=''
try:
    adminEmail = settings.SITE_ADMIN[1]
except AttributeError:
    adminEmail=''
try:
    siteVersion = settings.SITE_VERSION
except AttributeError:
    siteVersion=''
try:
    imsVersion = settings.IMS_VERSION
except AttributeError:
    imsVersion=''
try:
    tempDir = settings.TEMP_DIR
except AttributeError:
    tempDir = '/tmp'

#TODO: Utilize Red Cross SSO authentication

# Get an instance of a logger
logger = logging.getLogger(__name__)
    
# Helper functions
def reorder_date_mdy_to_ymd(dateString,sep):
    parts=dateString.split(sep)
    return parts[2]+"-"+parts[0]+"-"+parts[1]

def parse_datestr_tz(dateTimeString,hours=0,minutes=0):
    if date_re.match(dateTimeString):
        naive=datetime.datetime.combine(parse_date(dateTimeString), datetime.time(hours,minutes))
    else:
        naive=parse_datetime(dateTimeString)
    return pytz.utc.localize(naive)

def log_actions(request = None, modifier='unknown', modificationMessage='no message'):
    versionInfo = 'Site Version: ' + siteVersion + ', IMS Version: ' + imsVersion
    try:
        logger.info(versionInfo + ',' + modifier + ', ' + modificationMessage)
    except IOError as e:
        if request:
            if 'errorMessage' not in request.session:
                request.session['errorMessage'] =  str(IOError('Error writing status to log file:<br/>%s' % str(e)))
            else:
                request.session['errorMessage'] +=  str(IOError('Error writing status to log file:<br/>%s' % str(e)))
        pass

def get_session_messages(request):
    if 'errorMessage' in request.session:
        errorMessage = request.session['errorMessage']
        errorMessage = errorMessage.replace('\n','<br />')
    else:
        errorMessage = ''
    request.session['errorMessage'] = ''
    if 'warningMessage' in request.session:
        warningMessage = request.session['warningMessage']
        warningMessage = warningMessage.replace('\n','<br />')
    else:
        warningMessage = ''
    request.session['warningMessage'] = ''
    if 'infoMessage' in request.session:
        infoMessage = request.session['infoMessage']
        infoMessage = infoMessage.replace('\n','<br />')
    else:
        infoMessage = ''
    request.session['infoMessage'] = ''
    return errorMessage, warningMessage, infoMessage

#TODO: rename to Ims from Rims
# Error classes 
class RimsError(Exception): pass

class RimsRestoreError(RimsError): pass

class RimsImportInventoryError(RimsError): pass

class RimsImportProductsError(RimsError): pass

class RimsImportCategoriesError(RimsError): pass
    
class RimsImportSitesError(RimsError): pass

class RimsImageProcessingError(RimsError): pass

class RimsDuplicateKeyError(RimsError): pass

# Create your views here.
@login_required()
def home(request):
    # display most recently edited sites and inventory
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    recentSites = Site.recently_changed_inventory(PAGE_SIZE)
    recentInventory = InventoryItem.recently_changed(PAGE_SIZE)
    if len(recentInventory) == 0:
        warningMessage += 'No inventory found.'
    return render(request,'ims/home.html', {'nav_rims':1,
                                             'sitesList':recentSites,
                                             'inventoryList':recentInventory,
                                             'errorMessage':errorMessage,
                                             'warningMessage':warningMessage,
                                             'infoMessage':infoMessage,
                                             'adminName':adminName,
                                             'adminEmail':adminEmail,
                                             'siteVersion':siteVersion,
                                             'imsVersion':imsVersion,
                                             })

@login_required()
def imports(request):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    perms=request.user.get_all_permissions()
    canDeleteSites='ims.delete_site' in perms
    canAddSites='ims.add_site' in perms
    canDeleteProducts='ims.delete_productinformation' in perms
    canAddProducts='ims.add_productinformation' in perms
    canDeleteInventory='ims.delete_inventoryitem' in perms
    canAddInventory='ims.add_inventoryitem' in perms
    canChangeProducts='ims.change_productinformation' in perms
    canChangeSites='ims.change_site' in perms
    canChangeInventory='ims.change_inventoryitem' in perms
    if request.method == 'POST':
        if 'Delete Sites' in request.POST:
            if canDeleteSites and canDeleteInventory:
                return site_delete_all(request)
            else:
                errorMessage='You don''t have permission to delete sites or inventory'
        if 'Delete Products' in request.POST:
            if canDeleteProducts and canDeleteInventory:
                return product_delete_all(request)
            else:
                errorMessage='You don''t have permission to delete products or inventory'
        if 'Delete Inventory' in request.POST:
            if canDeleteInventory:
                return inventory_delete_all(request)
            else:
                errorMessage='You don''t have permission to delete inventory'
        if 'Export Sites' in request.POST:
            return  create_site_export_xls_response(request)
        elif 'Export Products' in request.POST:
            return create_product_export_xls_response(request)
        elif 'Export All Inventory' in request.POST:
            return create_inventory_export_xls_response(request, exportType='All')
        elif 'Export Latest Inventory' in request.POST:
            return create_inventory_export_xls_response(request, exportType='Current')
        elif 'Backup' in request.POST:
            return create_backup_archive_response(request)
        elif 'Log File' in request.POST:
            return create_log_file_response(request)
        elif 'Import Sites' in request.POST:
            if canAddSites and canChangeSites:
                return redirect(reverse('ims:import_sites'))
            else:
                errorMessage = 'You don''t have permission to import sites'
        elif 'Import Products' in request.POST:
            if canAddProducts and canChangeProducts:
                return redirect(reverse('ims:import_products'))
            else:
                errorMessage = 'You don''t have permission to import products'
        elif 'Import Inventory' in request.POST:
            if canAddInventory:
                return redirect(reverse('ims:import_inventory'))
            else:
                errorMessage = 'You don''t have permission to import sites'
        elif 'Restore' in request.POST:
            return redirect(reverse('ims:restore',))
    return render(request,'ims/imports.html', {'nav_imports':1,
                                                'warningMessage':warningMessage,
                                                'infoMessage':infoMessage,
                                                'errorMessage':errorMessage,
                                                'canImportSites':canAddSites and canChangeSites,
                                                'canImportProducts':canAddProducts and canChangeProducts,
                                                'canImportInventory':canAddInventory and canChangeInventory,
                                                'canDeleteSites':canDeleteSites and canDeleteInventory,
                                                'canDeleteProducts':canDeleteProducts and canDeleteInventory,
                                                'canDeleteInventory':canDeleteInventory,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,
                                                })

def get_sorted_inventory(report = '', 
                         startDate = None, 
                         stopDate = None, 
                         orderBy = 'name',
                         orderDir = 'asc',
                         sortReverse = False):
    sitesList=None
    inventoryList=None
    includesCategories = False
    if report and startDate and stopDate:
        #parsedStartDate = parse_datestr_tz(reorder_date_mdy_to_ymd(startDate, '-'), 0, 0)
        parsedStopDate = parse_datestr_tz(reorder_date_mdy_to_ymd(stopDate, '-'), 23, 59)
        sites = Site.objects.all().order_by('name')
        sitesList = OrderedDict()
        inventoryList = {}
        if re.match('site_detail', report): # site detail reports don't contain inventory details, just get
            # the site data and pass it to the template for rendering
            sitesList = sites
        else:
            # other reports require information about the inventory at each site
            for site in sites:
                siteInventory = site.latest_inventory(stopDate=parsedStopDate, 
                    orderBy=orderBy, orderDir = orderDir)
                sitesList[site] = siteInventory
                if not includesCategories:
                    includesCategories = siteInventory.filter(information__category__isnull = False).count() > 0
                if re.match('inventory_detail', report) or re.match('inventory_status', report):
                    # these reports require details about each inventory item
                    # contained at each site
                    for item in siteInventory:
                        if item.information not in inventoryList:
                            # accumulation list
                            inventoryList[item.information] = list(), (0, 0)
                        siteQuantityList = inventoryList[item.information][0]
                        siteQuantityList.append((site, item.quantity, item.quantity * item.information.quantityOfMeasure))
                        newSiteQuantity = inventoryList[item.information][1][0] + item.quantity, inventoryList[item.information][1][1] + item.quantity * item.information.quantityOfMeasure
                        inventoryList[item.information] = siteQuantityList, newSiteQuantity
            
            sortedInventory = OrderedDict()
            informationItems = inventoryList.keys()
            if orderBy == 'code':
                # sort by code
                sortedCodes = [information.code for information in informationItems]
                sortedCodes.sort(reverse=sortReverse)
                for code in sortedCodes:
                    thisInfo = [information for information in inventoryList.keys() if information.code == code]
                    sortedInventory[thisInfo[0]] = inventoryList[thisInfo[0]]
            else:
                
                sortedNames = [information.name for information in informationItems]
                sortedNames.sort(reverse=sortReverse)
                for name in sortedNames:
                    thisInfo = [information for information in inventoryList.keys() if information.name == name]
                    sortedInventory[thisInfo[0]] = inventoryList[thisInfo[0]] #sortProductByName
            
            inventoryList = sortedInventory
    return sitesList, inventoryList, includesCategories

@login_required()

def reports_dates(request, 
                  report = None,
                  page = 1, 
                  startDate = None, 
                  stopDate = None,
                  orderBy = 'name', 
                  orderDir = 'asc'):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    dateSpanForm=DateSpanQueryForm()
    if orderDir == 'asc':
        sortReverse = False
        altOrderDir = 'desc'
    else:
        sortReverse = True
        altOrderDir = 'asc'
    if orderBy == 'name':
        altOrderBy = 'code'
    else:
        altOrderBy = 'name'
    if request.method == 'POST':
        beginDate = startDate
        endDate = stopDate
        if 'Site Inventory Print' in request.POST:
            return redirect(reverse('ims:reports_dates',
                             kwargs={'report':'site_inventory_print',
                                     'page':page,
                                     'startDate':beginDate,
                                     'stopDate':endDate,
                                     'orderBy':orderBy,
                                     'orderDir':orderDir}))
        elif 'Site Inventory XLS' in request.POST:
            return redirect(reverse('ims:reports_dates',
                             kwargs={'report':'site_inventory_xls',
                                     'page':page,
                                     'startDate':beginDate,
                                     'stopDate':endDate,}))
        elif 'Site Detail Print' in request.POST:
            return redirect(reverse('ims:reports_dates',
                             kwargs={'report':'site_detail_print',
                                     'page':page,
                                     'startDate':beginDate,
                                     'stopDate':endDate,}))
        elif 'Site Detail XLS' in request.POST:
            return redirect(reverse('ims:reports_dates',
                             kwargs={'report':'site_detail_xls',
                                     'page':page,
                                     'startDate':beginDate,
                                     'stopDate':endDate}))
        elif 'Inventory Detail Print' in request.POST:
            return redirect(reverse('ims:reports_dates',
                             kwargs={'report':'inventory_detail_print',
                                     'page':page,
                                     'startDate':beginDate,
                                     'stopDate':endDate,
                                     'orderBy':orderBy,
                                     'orderDir':orderDir}))
        elif 'Inventory Detail XLS' in request.POST:
            return redirect(reverse('ims:reports_dates',
                             kwargs={'report':'inventory_detail_xls',
                                     'page':page,
                                     'startDate':beginDate,
                                     'stopDate':endDate}))
        elif 'Inventory Status Print' in request.POST:
            return redirect(reverse('ims:reports_dates',
                             kwargs={'report':'inventory_status_print',
                                     'page':page,
                                     'startDate':beginDate,
                                     'stopDate':endDate,
                                     'orderBy':orderBy,
                                     'orderDir':orderDir}))
        elif 'Inventory Status XLS' in request.POST:
            return redirect(reverse('ims:reports_dates',
                             kwargs={'report':'inventory_status_xls',
                                     'page':page,
                                     'startDate':beginDate,
                                     'stopDate':endDate}))
    (sitesList, 
     inventoryList, 
     includesCategories) = get_sorted_inventory(report = report, 
                                                startDate = startDate, 
                                                stopDate = stopDate, 
                                                orderBy = orderBy, 
                                                orderDir = orderDir,
                                                sortReverse = sortReverse)
    
    return render(request,'ims/reports.html', {'nav_reports':1,
                                                'warningMessage':warningMessage,
                                                'infoMessage':infoMessage,
                                                'errorMessage':errorMessage,
                                                'report':report,
                                                'dateSpanForm':dateSpanForm,
                                                'startDate':startDate,
                                                'stopDate':stopDate,
                                                'pageNo':page,
                                                'sitesList':sitesList,
                                                'inventoryList':inventoryList,
                                                'orderBy':orderBy,
                                                'altOrderBy':altOrderBy,
                                                'orderDir':orderDir,
                                                'altOrderDir':altOrderDir,
                                                'addCategory':includesCategories,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,})

@login_required()
def reports(request):
    today=timezone.now()
    startDate=today.strftime('%m-%d-%Y')
    stopDate=today.strftime('%m-%d-%Y')
    return reports_dates(request, startDate=startDate, stopDate=stopDate)

@login_required()
def inventory_history_dates(request, siteId=None, code=None,  page=1, startDate=None, stopDate=None):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    try:
        site=Site.objects.get(pk=siteId)
    except Site.DoesNotExist:
        errorMessage += ('Unable to check inventory history.\nSite %s does not exist.' % 
        siteId)
        request.session['errorMessage'] = errorMessage
        return redirect(reverse('ims:sites'))
    try:
        product=ProductInformation.objects.get(pk=code)
    except ProductInformation.DoesNotExist:
        errorMessage += ('Unable to check inventory history.\nItem %s does not exist.' % 
        code)
        request.session['errorMessage'] = errorMessage
        return redirect(reverse('ims:site_detail', kwargs = {'siteId':siteId,}))
    #parsedStartDate=parse_datestr_tz(reorder_date_mdy_to_ymd(startDate,'-'),0,0)
    parsedStopDate=parse_datestr_tz(reorder_date_mdy_to_ymd(stopDate,'-'),23,59)
    inventoryList=site.inventory_history_for_product(code=product.code, stopDate=parsedStopDate)
    inventoryIds=[]
    for item in inventoryList:
        inventoryIds.append(item.pk)
    siteInventory=InventoryItem.objects.filter(pk__in=inventoryIds)
    inventoryItems=[]
    for item in siteInventory:
        inventoryItems.append(item)
    inventoryItems.sort(reverse=True)
    siteInventory = inventoryItems
    if page == 'all':
        pageSize = len(siteInventory)
        pageNum = 1
    else:
        pageSize = PAGE_SIZE
        pageNum = page
    numPages=int(len(siteInventory)/pageSize)
    if len(siteInventory)% pageSize !=0:
        numPages += 1
    numPages=(max(1,numPages))
    if page == 'all':
        numPagesIndicator = 'all'
    else:
        numPagesIndicator = numPages
    pageNo = min(numPages,max(1,int(pageNum)))
    startRow=(pageNo-1) * pageSize
    stopRow=startRow+pageSize
    return render(request, 'ims/inventory_history_dates.html',{
                  'site':site,
                  'product':product,
                  'pageNo':str(pageNo),
                  'previousPageNo':str(max(1,pageNo-1)),
                  'nextPageNo':str(min(pageNo+1,numPages)),
                  'numPages':numPagesIndicator,
                  'startRow':startRow,
                  'stopRow':stopRow,
                  'siteInventory':siteInventory,
                  'startDate':startDate,
                  'stopDate':stopDate,
                  'infoMessage':infoMessage,
                  'warningMessage':warningMessage,
                  'errorMessage':errorMessage,
                  'adminName':adminName,
                  'adminEmail':adminEmail,
                  'siteVersion':siteVersion,
                  'imsVersion':imsVersion,})
    
@login_required()
def inventory_history(request, siteId=None, code=None, page=1,):
    today=timezone.now()
    startDate=today.strftime('%m-%d-%Y')
    stopDate=today.strftime('%m-%d-%Y')
    return inventory_history_dates(request, siteId=siteId, code=code, page=page, 
                                   startDate=startDate, stopDate=stopDate)

@login_required()
def sites(request, page=1):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    canDelete=request.user.has_perm('ims.delete_site') and request.user.has_perm('ims.delete_inventoryitem')
    canAdd=request.user.has_perm('ims.add_site')
    sitesList=Site.objects.all().order_by('name')
    SiteFormset=modelformset_factory( Site, form=SiteListForm, fields=['Delete'], extra=0)
    if page == 'all':
        page_size = sitesList.count()
        pageNum = 1
    else:
        page_size = PAGE_SIZE
        pageNum = page
    numPages=int(sitesList.count()/page_size)
    if sitesList.count()% page_size !=0:
        numPages += 1
    numPages=(max(1,numPages))
    if page == 'all':
        numPagesIndicator = 'all'
    else:
        numPagesIndicator = numPages
    pageNo = min(numPages,max(1,int(pageNum)))
    slicedSitesList=sitesList[(pageNo-1) * page_size: pageNo * page_size]
    numSiteErrors=0
    for site in slicedSitesList:
        if not site.check_site():
            numSiteErrors += 1
    if request.method == "POST":
        siteForms=SiteFormset(request.POST,queryset=slicedSitesList, error_class=TitleErrorList)
        if 'Delete' in request.POST:
            if canDelete:
                sitesToDelete={}
                for siteForm in siteForms:
                    if siteForm.prefix+'-'+'Delete' in request.POST:
                        sitesToDelete[siteForm.instance]=siteForm.instance.inventoryitem_set.all()
                if len(sitesToDelete) > 0:
                    return site_delete(request,sitesToDelete=sitesToDelete, page=page)
                else:
                    warningMessage = 'No sites selected for deletion'
            else:
                errorMessage='You don''t have permission to delete sites'
        if 'Add' in request.POST:
            if canAdd:
                return redirect(reverse('ims:site_add'))
            else:
                errorMessage='You don''t have permission to add sites'
    siteForms=SiteFormset(queryset=slicedSitesList, error_class=TitleErrorList)
    if len(slicedSitesList) == 0:
        warningMessage += 'No sites found'
    return render(request,'ims/sites.html', {'nav_sites':1,
                                              'pageNo':str(pageNo),
                                              'previousPageNo':str(max(1,pageNo-1)),
                                              'nextPageNo':str(min(pageNo+1,numPages)),
                                              'numPages': numPagesIndicator,
                                              'numSiteErrors':numSiteErrors,
                                              'siteForms':siteForms,
                                              'infoMessage':infoMessage,
                                              'warningMessage':warningMessage,
                                              'errorMessage':errorMessage,
                                              'canAdd':canAdd,
                                              'canDelete':canDelete,
                                              'adminName':adminName,
                                              'adminEmail':adminEmail,
                                              'siteVersion':siteVersion,
                                              'imsVersion':imsVersion,
                                              })

@login_required()
def site_detail(request, siteId=1, page=1):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    try:
        site=Site.objects.get(pk=siteId)
    except Site.DoesNotExist:
        errorMessage += ('Site %s does not exist.' % 
        siteId)
        request.session['errorMessage'] = errorMessage
        return redirect(reverse('ims:sites'))
    if 'adjust' in request.GET:
        adjust = 'adjust'
    else:
        adjust = ''
    canAdd=request.user.has_perm('ims.add_inventoryitem')
    canChangeInventory=request.user.has_perm('ims.change_inventoryitem')
    canChangeSite=request.user.has_perm('ims.change_site')
    canDelete=request.user.has_perm('ims.delete_inventoryitem')
    siteInventory=site.latest_inventory()
    siteForm=SiteForm(site.__dict__,instance=site, error_class=TitleErrorList)
    if page == 'all':
        pageSize = siteInventory.count()
        pageNum = 1
    else:
        pageSize = PAGE_SIZE
        pageNum = str(page)
    numPages=max(1,int(siteInventory.count()/pageSize))
    if numPages > 1 and siteInventory.count()% pageSize !=0:
        numPages += 1
    numPages=(max(1,numPages))
    pageNo = min(numPages,max(1,int(pageNum)))
    if page == 'all':
        numPagesIndicator = 'all'
        pageIndicator='all'
    else:
        numPagesIndicator = numPages
        pageIndicator=pageNo
    startRow=(pageNo-1) * pageSize
    stopRow=startRow+pageSize
    InventoryAdjustFormset=modelformset_factory(InventoryItem,extra=0, can_delete=False,
                                             form=InventoryItemFormNoSite)
    InventoryAddSubtractFormset=modelformset_factory(InventoryItem,extra=0, can_delete=False,
                                             form=InventoryItemFormAddSubtractNoSite)
    inventoryAdjustForms=InventoryAdjustFormset(queryset=siteInventory, error_class=TitleErrorList)
    inventoryAddSubtractForms=InventoryAddSubtractFormset(queryset=siteInventory, error_class=TitleErrorList)
    if request.method == "POST":
        siteForm=SiteForm(request.POST,instance=site, error_class=TitleErrorList)
        if siteInventory.count() > 0:
            inventoryAdjustForms=InventoryAdjustFormset(request.POST, queryset=siteInventory, error_class=TitleErrorList)
            inventoryAddSubtractForms=InventoryAddSubtractFormset(request.POST, queryset=siteInventory, error_class=TitleErrorList)
        if 'Save Site' or 'Save Changes' in request.POST:
            if 'Save Site' in request.POST:
                if canChangeSite:
                    if siteForm.is_valid():
                        if siteForm.has_changed():
                            siteForm.instance.modifier=request.user.username
                            siteForm.save()
                            infoMessage = 'Successfully added site or changed site information'
                            log_actions(request = request, modifier=request.user.username,
                                        modificationMessage='changed site information for ' + str(siteForm.instance))
                            request.session['errorMessage'] += errorMessage
                            request.session['warningMessage'] = warningMessage
                            request.session['infoMessage'] = infoMessage
                            return redirect(reverse('ims:site_detail',
                                                    kwargs={'siteId':site.pk, 
                                                            'page':pageIndicator,},))
                        else:
                            warningMessage = 'No changes made to the site information'
                    else:
                        warningMessage='More information required before the site can be saved'
                else:
                    errorMessage='You don''t have permission to change site information'
            if ('Save Adjust Changes' in request.POST):
                adjust = 'adjust'
                if canChangeInventory and canDelete:
                    if inventoryAdjustForms.is_valid():
                        if inventoryAdjustForms.has_changed():
                            inventoryItems=[]
                            for inventoryForm in inventoryAdjustForms:
                                inventoryForm.instance.modifier=request.user.username
                                if inventoryForm.prefix+'-'+'deleteItem' in request.POST:
                                    inventoryForm.instance.deleted=True
                            inventoryItems=inventoryAdjustForms.save(commit=False)
                            for inventoryItem in inventoryItems:
                                newItem=inventoryItem.copy()
                                newItem.save()
                            siteInventory=site.latest_inventory()
                            request.session['infoMessage'] = 'Successfully changed site inventory'
                            inventoryAdjustForms=InventoryAdjustFormset(queryset=siteInventory, error_class=TitleErrorList)
                            return redirect(reverse('ims:site_detail',
                                                    kwargs={'siteId':site.pk, 
                                                            'page':pageIndicator,},) + "?adjust")
                        else:
                            warningMessage = 'No changes made to the site inventory'
            elif ('Save Add Subtract Changes' in request.POST):
                if canChangeInventory and canDelete:
                    if inventoryAddSubtractForms.is_valid():
                        if inventoryAddSubtractForms.has_changed():
                            inventoryItems=[]
                            for inventoryForm in inventoryAddSubtractForms:
                                inventoryForm.instance.modifier=request.user.username
                                if inventoryForm.prefix+'-'+'deleteItem' in request.POST:
                                    inventoryForm.instance.deleted=True
                                inventoryForm.instance.quantity += inventoryForm.cleaned_data['addSubtract']
                            inventoryItems=inventoryAddSubtractForms.save(commit=False)
                            for inventoryItem in inventoryItems:
                                newItem=inventoryItem.copy()
                                newItem.save()
                            siteInventory=site.latest_inventory()
                            request.session['infoMessage'] = 'Successfully changed site inventory'
                            inventoryAddSubtractForms=InventoryAddSubtractFormset(queryset=siteInventory, error_class=TitleErrorList)
                            return redirect(reverse('ims:site_detail',
                                                    kwargs={'siteId':site.pk, 
                                                            'page':pageIndicator,},))
                        else:
                            warningMessage = 'No changes made to the site inventory'
                else:
                    errorMessage='You don''t have permission to change or delete inventory'
            if 'Add New Inventory' in request.POST:
                if canAdd:
                    return redirect(reverse('ims:site_add_inventory',kwargs={'siteId':site.pk, 'page':1}))
                else:
                    errorMessage='You don''t have permission to add inventory'
        #siteForm=SiteForm(site.__dict__,instance=site, error_class=TitleErrorList)
        #inventoryForms=InventoryFormset(request.POST, queryset=siteInventory, error_class=TitleErrorList)
    return render(request, 'ims/site_detail.html', {"nav_sites":1,
                                                'site': site,
                                                'siteForm':siteForm,
                                                'startRow':startRow,
                                                'stopRow':stopRow,
                                                'pageNo':str(pageIndicator),
                                                'previousPageNo':str(max(1,pageNo-1)),
                                                'nextPageNo':str(min(pageNo+1,numPages)),
                                                'numPages': numPagesIndicator,
                                                'inventoryAdjustForms':inventoryAdjustForms,
                                                'inventoryAddSubtractForms':inventoryAddSubtractForms,
                                                'adjust':adjust,
                                                'canAdd':canAdd,
                                                'canChangeInventory':canChangeInventory,
                                                'canChangeSite':canChangeSite,
                                                'canDelete':canDelete,
                                                'warningMessage':warningMessage,
                                                'infoMessage':infoMessage,
                                                'errorMessage':errorMessage,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,
                                                })

@login_required()
def site_add(request):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    canAdd=request.user.has_perm('ims.add_site')
    siteForm=SiteForm(instance=Site(), error_class=TitleErrorList)
    if request.user.has_perm('ims.add_site'):
        if request.method == "POST":
            if 'Save Site' in request.POST:
                if canAdd:
                    siteForm=SiteForm(request.POST,Site(), error_class=TitleErrorList)
                    if siteForm.is_valid():
                        siteForm.instance.modifier=request.user.username
                        siteForm.save()
                        site=siteForm.instance
                        request.session['infoMessage'] = 'Successfully added site'
                        return redirect(reverse('ims:site_detail',
                                                kwargs={'siteId':site.pk, 
                                                        'page':1,},))
                    else:
                        warningMessage='More information required before site can be added'
                else:
                    errorMessage='You don''t have permission to add sites'
    else:
        errorMessage='You don''t have permission to add sites'
    return render(request, 'ims/site_detail.html', {"nav_sites":1,
                                                'canChangeSite':canAdd,
                                                'siteForm':siteForm,
                                                'warningMessage':warningMessage,
                                                'infoMessage':infoMessage,
                                                'errorMessage':errorMessage,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,
                                                })
    
@login_required()
def site_add_inventory(request, siteId=1, page=1):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    try:
        site=Site.objects.get(pk=siteId)
    except Site.DoesNotExist:
        errorMessage += ('Site %s does not exist.' % 
        siteId)
        request.session['errorMessage'] = errorMessage
        return redirect(reverse('ims:sites'))
    canAdd=request.user.has_perm('ims.add_inventoryitem')
    productsList=ProductInformation.objects.all().order_by('name')
    ProductFormset=modelformset_factory( ProductInformation, form=ProductListFormWithAdd, extra=0)
    if page == 'all':
        pageSize = productsList.count()
        pageNum = 1
    else:
        pageSize = PAGE_SIZE
        pageNum = page
    numPages=int(productsList.count()/pageSize)
    if productsList.count()% pageSize !=0:
        numPages += 1
    numPages=(max(1,numPages))
    if page == 'all':
        numPagesIndicator = 'all'
    else:
        numPagesIndicator = numPages
    pageNo = min(numPages,max(1,int(pageNum)))
    startRow=(pageNo-1) * pageSize
    stopRow=startRow+pageSize
    if canAdd:
        if request.method == "POST":
            productForms=ProductFormset(request.POST,queryset=productsList, error_class=TitleErrorList)
            if 'Add Products' in request.POST:
                if canAdd:
                        # current inventory at this site
                        siteInventory=site.latest_inventory()
                        productToAdd=[]
                        productList=[]
                        for productForm in productForms:
                            if productForm.prefix+'-'+'Add' in request.POST:
                                if siteInventory.filter(information=productForm.instance.pk).count() == 0:
                                    productToAdd.append(productForm.instance)
                                productList.append(productForm.instance)
                        return product_add_to_site_inventory(request, siteId=site.pk,
                                                             productToAdd=productToAdd,
                                                             productList=productList,)
            else:
                errorMessage='You don''t have permission to add site inventory'
    else:
        errorMessage='You don''t have permission to add site inventory'
    siteForm=SiteFormReadOnly(instance=site, error_class=TitleErrorList)
    productForms=ProductFormset(queryset=productsList, error_class=TitleErrorList)
    return render(request, 'ims/site_add_inventory.html', {"nav_sites":1,
                                                'site':site,
                                                'siteForm':siteForm,
                                                'startRow':startRow,
                                                'stopRow':stopRow,
                                                'pageNo':str(pageNo),
                                                'previousPageNo':str(max(1,pageNo-1)),
                                                'nextPageNo':str(min(pageNo+1,numPages)),
                                                'numPages': numPagesIndicator,
                                                'productForms':productForms,
                                                'warningMessage':warningMessage,
                                                'infoMessage':infoMessage,
                                                'errorMessage':errorMessage,
                                                'canAdd':canAdd,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,
                                                })

@login_required()
def site_delete(request, sitesToDelete={}, page=1):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    canDelete=request.user.has_perm('ims.delete_site')
    if request.method == 'POST':
        if 'Delete Site' in request.POST:
            if canDelete:
                sitesToDelete=request.POST.getlist('sites')
                numSites=len(sitesToDelete)
                for siteId in sitesToDelete:
                    site=Site.objects.get(pk=int(siteId))
                    siteInventory=site.inventoryitem_set.all()
                    for item in siteInventory:
                        item.delete()
                    site.delete()
                    infoMessage = 'Successfully deleted %d sites' % numSites
                    log_actions(request = request, modifier=request.user.username,
                                modificationMessage='deleted site and all associated inventory for site number ' + 
                                str(site.pk) + ' with name ' + site.name)
                request.session['errorMessage'] += errorMessage
                request.session['warningMessage'] = warningMessage
                request.session['infoMessage'] = infoMessage
                return redirect(reverse('ims:sites', kwargs={'page':1}))
        if 'Cancel' in request.POST:
            return redirect(reverse('ims:sites', kwargs={'page':1}))
    if 'Delete Site' not in request.POST:
        # then this comes directly from the sites view requesting site deletion
        if canDelete:
            if any([sitesToDelete[k].count()>0  for k in sitesToDelete]):
                warningMessage='One or more sites contain inventory.  Deleting the sites will delete all inventory as well. Delete anyway?'
            else:
                warningMessage='Are you sure?'
        else:
                errorMessage='You don''t have permission to delete sites'
                sitesToDelete=[]
    return render(request, 'ims/site_delete.html', {"nav_sites":1,
                                                'sitesToDelete':sitesToDelete,
                                                'warningMessage':warningMessage,
                                                'infoMessage':infoMessage,
                                                'errorMessage':errorMessage,
                                                'canDelete':canDelete,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,
                                                })

@login_required()
def site_delete_all(request):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    sites=Site.objects.all()
    canDelete=request.user.has_perm('ims.delete_site') and request.user.has_perm('ims.delete_inventoryitem')
    if request.method == 'POST':
        if 'Delete All Sites' in request.POST:
            if canDelete:
                sites=Site.objects.all()
                inventoryItems=InventoryItem.objects.all()
                sites.delete()
                inventoryItems.delete()
                log_actions(request = request, modifier=request.user.username,
                            modificationMessage='deleted all sites and inventory')
                request.session['infoMessage'] = 'Successfully deleted all sites'
                return redirect(reverse('ims:imports'))
        if 'Cancel' in request.POST:
            return redirect(reverse('ims:imports'))
    if canDelete:
        warningMessage='Delete all ' + str(sites.count()) + ' sites?  This will delete all inventory as well.'
    else:
        errorMessage='You don''t have permission to delete sites or inventory' 
    return render(request, 'ims/site_delete_all.html', {"nav_sites":1,
                                                'warningMessage':warningMessage,
                                                'infoMessage':infoMessage,
                                                'errorMessage':errorMessage,
                                                'canDelete':canDelete,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,
                                                })

@login_required()
def products(request, page=1):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    canAdd=request.user.has_perm('ims.add_productinformation')
    canDelete=request.user.has_perm('ims.delete_productinformation')
    if canDelete:
        ProductFormset=modelformset_factory( ProductInformation, form=ProductListFormWithDelete, extra=0)
    else:
        ProductFormset=modelformset_factory( ProductInformation, form=ProductListFormWithoutDelete, extra=0)
    productsList=ProductInformation.objects.all().order_by('name')
    if page == 'all':
        page_size = productsList.count()
        pageNum = 1
    else:
        page_size = PAGE_SIZE
        pageNum = page
    numPages=int(productsList.count()/page_size)
    if productsList.count()% page_size !=0:
        numPages += 1
    numPages=(max(1,numPages))
    if page == 'all':
        numPagesIndicator = 'all'
    else:
        numPagesIndicator = numPages
    pageNo = min(numPages,max(1,int(pageNum)))
    slicedProductsList=productsList[(pageNo-1) * page_size: pageNo * page_size]
    numProductErrors=0
    for product in slicedProductsList:
        if not product.check_product():
            numProductErrors += 1
    if request.method == 'POST':
        productForms=ProductFormset(request.POST,queryset=slicedProductsList, error_class=TitleErrorList)
        if 'Delete' in request.POST:
            if canDelete:
                productsToDelete={}
                for productForm in productForms:
                    if productForm.prefix+'-'+'Delete' in request.POST:
                        productsToDelete[productForm.instance]=productForm.instance.inventoryitem_set.all()
                if len(productsToDelete) > 0:
                    return product_delete(request,productsToDelete=productsToDelete, page=page)
                request.session['warningMessage'] = 'No products selected for deletion'
                return redirect(reverse('ims:products',kwargs={'page':page,}))
            else:
                errorMessage='You don''t have permission to delete products'
        if 'Add' in request.POST:
            if canAdd:
                return redirect(reverse('ims:product_add'))
            else:
                errorMessage='You don''t have permission to add products'
    productForms=ProductFormset(queryset=slicedProductsList, error_class=TitleErrorList)
    if len(slicedProductsList) == 0:
        warningMessage='No products found'
    return render(request,'ims/products.html', {'nav_products':1,
                                              'pageNo':str(pageNo),
                                              'previousPageNo':str(max(1,pageNo-1)),
                                              'nextPageNo':str(min(pageNo+1,numPages)),
                                              'numPages': numPagesIndicator,
                                              'productsList':slicedProductsList,
                                              'numProductErrors':numProductErrors,
                                              'productForms':productForms,
                                              'canAdd':canAdd,
                                              'canDelete':canDelete,
                                              'warningMessage':warningMessage,
                                              'infoMessage':infoMessage,
                                              'errorMessage':errorMessage,
                                              'adminName':adminName,
                                              'adminEmail':adminEmail,
                                              'siteVersion':siteVersion,
                                              'imsVersion':imsVersion,
                                              })

@login_required()
def product_detail(request, page=1, code='-1',):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    try:
        product = ProductInformation.objects.get(pk=code)
    except ProductInformation.DoesNotExist:
        errorMessage += ('Product %s does not exist.' % 
        code)
        request.session['errorMessage'] = errorMessage
        return redirect(reverse('ims:products'))
    canChange=request.user.has_perm('ims.change_productinformation')
    inventorySites=product.inventoryitem_set.all().values('site').distinct()
    sitesList=[]
    for siteNumber in inventorySites:
        site = Site.objects.get(pk=siteNumber['site'])
        sitesList.append((site,site.inventory_quantity(code)))
    if page == 'all':
        page_size = len(sitesList)
        pageNum = 1
    else:
        page_size = PAGE_SIZE
        pageNum = page
    numPages=int(len(sitesList)/page_size)
    if len(sitesList)% page_size !=0:
        numPages += 1
    numPages=(max(1,numPages))
    if page == 'all':
        numPagesIndicator = 'all'
    else:
        numPagesIndicator = numPages
    pageNo = min(numPages,max(1,int(pageNum)))
    slicedSitesList=sitesList[(pageNo-1) * page_size: pageNo * page_size]
    numSiteErrors=0
    for site in slicedSitesList:
        if not site[0].check_site():
            numSiteErrors += 1
    if 'picture' in request.GET:
        picture = 'picture'
    else:
        picture = ''
    productForm=ProductInformationForm(instance=product, error_class=TitleErrorList)
    if request.method == "POST":
        if 'SavePicture' in request.POST and 'rotation' in request.POST and canChange:
            try:
                with transaction.atomic():
                    rotate_picture(request, product, float(request.POST['rotation']))
            except:
                pass
            if 'errorMessage' not in request.session or request.session['errorMessage'] == '':
                request.session['infoMessage'] = 'Successfully saved picture rotation'
                log_actions(request = request, modifier=request.user.username,
                            modificationMessage='changed picture rotation for ' + str(product))
            else:
                log_actions(request = request, modifier=request.user.username,
                            modificationMessage='unable to change picture rotation for %s due to image processing error' %
                             str(product))
            return redirect(reverse('ims:product_detail',
                                                kwargs={'code':product.code,})+ picture)
        if 'Save' in request.POST:
            productForm=ProductInformationForm(request.POST,
                                               request.FILES,
                                               instance=product,
                                               error_class=TitleErrorList)
            if canChange:
                if productForm.is_valid():
                    if productForm.has_changed():
                        productForm.instance.modifier=request.user.username
                        originalPicture = product.picture.name
                        try:
                            with transaction.atomic():
                                product = productForm.save(commit = False)
                                if  product.code != code:
                                    # we've changed the primary key
                                    existingProducts = ProductInformation.objects.filter(pk = product.code)
                                    if existingProducts.count():
                                        request.session['errorMessage'] = (
                                        'Another product "%s" already has code "%s".' % 
                                        (existingProducts[0].name, product.code))
                                        raise RimsDuplicateKeyError
                                    product.save(force_insert = True)
                                    product.update_related(oldCode = code)
                                    oldProduct = ProductInformation.objects.filter(code = code)
                                    if oldProduct:
                                        oldProduct[0].delete()
                                else:
                                    product.save()                                
                                process_picture(request, product)
                        except (RimsImageProcessingError, RimsDuplicateKeyError):
                            pass
                        if 'errorMessage' not in request.session or request.session['errorMessage'] == '':
                            request.session['infoMessage'] = 'Successfully saved product information changes.'
                            log_actions(request = request, modifier=request.user.username,
                                        modificationMessage='changed product information for ' + str(productForm.instance))
                            if product.picture.name != originalPicture:
                                #picture has changed, offer opportunity to edit it
                                picture='?picture'
                                request.session['infoMessage'] += '\nAdjust picture rotation if needed and save.'
                        else:
                            log_actions(request = request, modifier=request.user.username,
                                        modificationMessage='unable to change product information for %s .  %s' %
                                         (str(productForm.instance), request.session['errorMessage']))
                            return redirect(reverse('ims:product_detail',
                                                kwargs={'code':code,})+ picture)
                    else:
                        request.session['warningMessage'] = 'No changes made to the product information.'
                    return redirect(reverse('ims:product_detail',
                                                kwargs={'code':product.code,})+ picture)
                else:
                    warningMessage = 'More information required before the product can be saved'
            else:
                errorMessage='You don''t have permission to change product information.'
    if product.picture:
        productForm.fields['picture'].widget.fileUrl = reverse('ims:product_detail',
                                            kwargs={'code':product.code,})+ '?picture'
    return render(request, 'ims/product_detail.html',
                            {"nav_products":1,
                             'pageNo':str(pageNo),
                             'previousPageNo':str(max(1,pageNo-1)),
                             'nextPageNo':str(min(pageNo+1,numPages)),
                             'numPages': numPagesIndicator,
                             'product': product,
                             'productForm':productForm,
                             'sitesList':sitesList,
                             'picture':picture,
                             'canChange':canChange,
                             'warningMessage':warningMessage,
                             'infoMessage':infoMessage,
                             'errorMessage':errorMessage,
                             'adminName':adminName,
                             'adminEmail':adminEmail,
                             'siteVersion':siteVersion,
                             'imsVersion':imsVersion,
                            })

@login_required()
def product_add(request):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    canAdd=request.user.has_perm('ims.add_productinformation')
    productForm=ProductInformationForm(error_class=TitleErrorList)
    picture=''
    if request.method == "POST":
        if 'Save' in request.POST:
            if canAdd:
                productForm=ProductInformationForm(request.POST,
                                               request.FILES,
                                               error_class=TitleErrorList)
                if productForm.is_valid():
                    if productForm.has_changed():
                        productForm.instance.modifier=request.user.username
                        try:
                            with transaction.atomic():
                                product=productForm.save()
                                process_picture(request, product)
                        except RimsImageProcessingError:
                            pass
                        if 'errorMessage' not in request.session or request.session['errorMessage'] == '':
                            request.session['infoMessage'] = 'Successfully saved product.'
                            log_actions(request = request, modifier=request.user.username,
                                        modificationMessage='added product information for ' + str(productForm.instance))
                            if product.picture:
                                picture='?picture'
                                request.session['infoMessage'] += '\nAdjust picture rotation if needed and save.'
                        else:
                            log_actions(request = request, modifier=request.user.username,
                                        modificationMessage='unable to add product information for %s .  %s' %
                                         (str(productForm.instance), request.session['errorMessage']))
                            return redirect(reverse('ims:products',))
                    else:
                        request.message['warningMessage'] = 'No changes made to the product information'
                    return redirect(reverse('ims:product_detail', kwargs={'code':product.pk,
                                                                        'page': 1,})+picture)
    if not canAdd:
        errorMessage='You don''t have permission to add new products'
    return render(request, 'ims/product_detail.html', {"nav_products":1,
                                                'productForm':productForm,
                                                'canAdd':canAdd,
                                                'warningMessage':warningMessage,
                                                'infoMessage':infoMessage,
                                                'errorMessage':errorMessage,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,
                                                })
    
@login_required()
def product_add_to_site_inventory(request, siteId=1, productToAdd=None, productList=None):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    try:
        site=Site.objects.get(pk=siteId)
    except Site.DoesNotExist:
        errorMessage += ('Site %s does not exist.' % 
        siteId)
        request.session['errorMessage'] = errorMessage
        return redirect(reverse('ims:sites'))
    canAdd=request.user.has_perm('ims.add_inventoryitem')
    ProductFormset=modelformset_factory(ProductInformation,extra=0,
                                                form=ProductInformationFormWithQuantity)
    newProduct = ProductInformation.objects.all()
    if productList:
        for productItem in newProduct:
            if productItem not in productList: 
                newProduct=newProduct.exclude(pk=productItem.pk)
    if request.method == 'POST':
        if newProduct.count() == 0:
            return redirect(reverse('ims:site_detail', kwargs={'siteId':site.pk,
                                                                'page':1}))
        if 'Save Inventory' in request.POST:
            if canAdd:
                productForms=ProductFormset(request.POST, queryset=newProduct, error_class=TitleErrorList)
                if productForms.is_valid():
                    request.session['infoMessage'] = ''
                    for productForm in productForms:
                        cleanedData=productForm.cleaned_data
                        item = site.add_inventory(product=productForm.instance,
                                                  quantity=int(cleanedData.get('Quantity')),
                                                  modifier=request.user.username,)
                        request.session['infoMessage'] += 'Successfully added product %s to inventory<br/>' % str(item)
                    return redirect(reverse('ims:site_detail',
                                    kwargs={'siteId':site.pk,
                                            'page':1}))
                else:
                    errorMessage = 'More information required before the inventory can be saved'
        if 'Cancel' in request.POST:
            return redirect(reverse('ims:site_detail', kwargs={'siteId':site.pk,
                                                                'page':1}),
                                        )
    if not canAdd:
        errorMessage='You don''t have permission to add to site inventory'
    productForms=ProductFormset(queryset=newProduct, error_class=TitleErrorList)
    #siteInventory=InventoryItem.objects.filter(site=siteId)
    siteInventory=site.latest_inventory()
    for productForm in productForms:
        if productForm.instance not in productToAdd:
            inventoryItem=siteInventory.get(information__code=productForm.instance.code)
            productForm.fields['Quantity'].initial=inventoryItem.quantity
    return render(request, 'ims/product_add_to_site_inventory.html', {'nav_sites':1,
                                                     'site':site,
                                                     'productForms':productForms,
                                                     'page':1,
                                                     'warningMessage':warningMessage,
                                                     'infoMessage':infoMessage,
                                                     'errorMessage':errorMessage,
                                                     'canAdd':canAdd,
                                                     'adminName':adminName,
                                                     'adminEmail':adminEmail,
                                                     'siteVersion':siteVersion,
                                                     'imsVersion':imsVersion,
                                                })
    
@login_required()
def product_delete(request, productsToDelete={}, page=1):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    canDeleteProduct=request.user.has_perm('ims.delete_productinformation')
    canDeleteInventory=request.user.has_perm('ims.delete_inventoryitem')
    if request.method == 'POST':
        if 'Delete Product' in request.POST:
            if canDeleteProduct and canDeleteInventory:
                productsToDelete=request.POST.getlist('products')
                infoMessage = ''
                for code in productsToDelete:
                    product=ProductInformation.objects.get(pk=code)
                    productInventory=product.inventoryitem_set.all()
                    for item in productInventory:
                        item.delete()
                    product.delete()
                    infoMessage += 'Successfully deleted product and associated inventory for product code %s with name "%s"<br/>' % (code, product.name)
                    log_actions(request = request, modifier=request.user.username,
                                modificationMessage=infoMessage)
                request.session['infoMessage'] = infoMessage
                return redirect(reverse('ims:products', kwargs={'page':1}))
        if 'Cancel' in request.POST:
            return redirect(reverse('ims:products', kwargs={'page':1}))
    if canDeleteProduct and canDeleteInventory:
        if any(productsToDelete[k].count() > 0  for k in productsToDelete):
            warningMessage='One or more products contain inventory.  Deleting the products will delete all inventory in all sites containing this product as well. Delete anyway?'
        else:
            warningMessage='Are you sure?'
    else:
        errorMessage = 'You don''t have permission to delete products or inventory'
        productsToDelete=[]
    
    return render(request, 'ims/product_delete.html', {"nav_products":1,
                                                'productsToDelete':productsToDelete,
                                                'warningMessage':warningMessage,
                                                'infoMessage':infoMessage,
                                                'errorMessage':errorMessage,
                                                'canDelete':canDeleteProduct and canDeleteInventory,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,
                                                })
    
@login_required()
def product_delete_all(request):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    canDelete=False
    products=ProductInformation.objects.all()
    if request.method == 'POST':
        if 'Delete All Products' in request.POST:
            if request.user.has_perms(['ims.delete_inventoryitem','ims.delete_productinformation']):
                products=ProductInformation.objects.all()
                inventoryItems=InventoryItem.objects.all()
                inventoryItems.delete()
                products.delete()
                request.session['infoMessage'] = 'Successfully deleted all products'
                log_actions(request = request, modifier=request.user.username,
                            modificationMessage=request.session['infoMessage'])
                return redirect(reverse('ims:imports'))
            else:
                errorMessage = 'You don''t have permission to delete products or inventory'
                return render(request, 'ims/product_delete_all.html', {"nav_imports":1,
                                                    'warningMessage':warningMessage,
                                                    'infoMessage':infoMessage,
                                                    'errorMessage':errorMessage,
                                                    'canDelete':canDelete,
                                                    'adminName':adminName,
                                                    'adminEmail':adminEmail,
                                                    'siteVersion':siteVersion,
                                                    'imsVersion':imsVersion,
                                                    })
        if 'Cancel' in request.POST:
            return redirect(reverse('ims:imports'))
    if request.user.has_perms(['ims.delete_inventoryitem','ims.delete_productinformation']):
        canDelete=True
        warningMessage='Delete all ' + str(products.count()) + ' products? This will delete all inventory as well.'
    else:
        errorMessage = 'You don''t have permission to delete products or inventory'
    return render(request, 'ims/product_delete_all.html', {"nav_imports":1,
                                                'warningMessage':warningMessage,
                                                'infoMessage':infoMessage,
                                                'errorMessage':errorMessage,
                                                'canDelete':canDelete,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,
                                                })

@login_required()
def inventory_delete_all(request):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    canDelete=False
    inventory=InventoryItem.objects.all()
    if request.method == 'POST':
        if 'Delete All Inventory' in request.POST:
            if request.user.has_perm('ims.delete_inventoryitem'):
                inventory.delete()
                request.session['infoMessage'] = 'Successfully deleted all inventory'
                log_actions(request = request, modifier=request.user.username,
                            modificationMessage=request.session['infoMessage'])
                return redirect(reverse('ims:imports'))
            else:
                errorMessage='You don''t have permission to delete inventory'
                return render(request, 'ims/inventory_delete_all.html', {"nav_imports":1,
                                                        'warningMessage':warningMessage,
                                                        'infoMessage':infoMessage,
                                                        'errorMessage':errorMessage,
                                                        'canDelete':canDelete,
                                                        'adminName':adminName,
                                                        'adminEmail':adminEmail,
                                                        'siteVersion':siteVersion,
                                                        'imsVersion':imsVersion,
                                                        })
        if 'Cancel' in request.POST:
            return redirect(reverse('ims:imports'))
    if request.user.has_perm('ims.delete_inventoryitem'):
        canDelete=True
        warningMessage='Delete all ' + str(inventory.count()) + ' inventory items?'
    else:
        errorMessage='You don''t have permission to delete inventory'
    return render(request, 'ims/inventory_delete_all.html', {"nav_imports":1,
                                                'warningMessage':warningMessage,
                                                'infoMessage':infoMessage,
                                                'errorMessage':errorMessage,
                                                'canDelete':canDelete,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,
                                                })
    
def create_log_file_response(request):
    logDir = os.path.join(settings.BASE_DIR, "log")
    if not os.path.isdir(logDir):
        errorMessage = '"log" directory doesn''t exist. This shouldn''t occur.\nSystem admin has been notified.'
        log_actions(request = request, modifier=request.user.username,
                    modificationMessage=errorMessage)
        request.session['errorMessage'] = errorMessage
        redirect(reverse('ims:imports'))
    xls = xlwt.Workbook(encoding="utf-8")
    sheets = []
    sheetIndex = 0
    for logFile in (settings.LOG_FILES):
        try:
            with open(logFile, 'r') as fStr:
                logFileString = fStr.read()
        except IOError:
            request.session['errorMessage'] = 'File Error:<br/>Unable to open %s' % logFile
            errorMessage = 'Unable to open log file.. This shouldn''t occur.\nSystem admin has been notified.'
            log_actions(request = request, modifier=request.user.username,
                        modificationMessage=errorMessage)
            return redirect('ims:imports')
        logEntries = re.split(r'(\[\d{2}\/\w+\/\d{4}\s\d{2}:\d{2}:\d{2}\])',
                              logFileString)
        fileName = logFile.rsplit(os.sep)[-1]
        sheets.append(xls.add_sheet(fileName.rsplit('.',1)[0]))
        sheets[sheetIndex].write(0,0,'Timestamp')
        sheets[sheetIndex].write(0,1,'Type')
        sheets[sheetIndex].write(0,2,'Log Contents')
        rowIndex = 1
        for logIndex in range(1,len(logEntries)-1,2):
            if re.match(r'\[\d{2}\/\w+\/\d{4}\s\d{2}:\d{2}:\d{2}\]',
                        logEntries[logIndex],
                        ):
                match = re.match(r'^(\w+)\s(.*$)',
                                    logEntries[logIndex+1].strip(),
                                    flags=re.DOTALL)
                sheets[sheetIndex].write(rowIndex,0,logEntries[logIndex].strip())
                if not match.lastindex or match.lastindex < 2:
                    sheets[sheetIndex].write(rowIndex,1,'LOG READ ERROR')
                    sheets[sheetIndex].write(rowIndex,2,'Unable to read log line')
                else:
                    sheets[sheetIndex].write(rowIndex,1,match.group(1))
                    sheets[sheetIndex].write(rowIndex,2,match.group(2))
                rowIndex += 1
        sheetIndex += 1
    response = HttpResponse(content_type="application/ms-excel")
    dateStamp=timezone.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    response['Content-Disposition'] = ('attachment; filename=%s_%s.xls' % 
                                        (settings.BASE_NAME,dateStamp))
    xls.save(response)
    return response
    
def trim_path(rootPath = '', dirPath = ''):
    archivePath = dirPath.replace(rootPath, "", 1)
    if rootPath:
        archivePath = archivePath.replace(os.path.sep, "", 1)
    return os.path.normcase(archivePath)

def zip_pictures(request,zipHandle):
    products = ProductInformation.objects.exclude(picture = '')
    for product in products:
        imageFile = product.picture.file.name
        thumbFile = imageFile.split('.')[0] + 'thumb.' + imageFile.split('.')[1]
        if os.path.isfile(imageFile):
            zipHandle.write(imageFile, trim_path(rootPath = settings.MEDIA_ROOT,
                                                 dirPath = imageFile))
        if os.path.isfile(thumbFile):
            zipHandle.write(thumbFile, trim_path(rootPath = settings.MEDIA_ROOT,
                                                 dirPath = thumbFile))
                
def create_backup_archive_response(request):
    #TODO: include picture in backup and restore
    errorMessage, __, __ = get_session_messages(request)
    try:
        xls = xlwt.Workbook(encoding="utf-8")
        xls=create_inventory_sheet(xls=xls, exportType='All')
        xls=create_product_export_sheet(xls=xls)
        xls=create_site_export_sheet(xls=xls)
        xls=create_category_export_sheet(xls=xls)
    except XlrdutilsError as e:
        errorMessage += ('<br/><br/>Unhandled exception occurred during creation of backup spreadsheet: %s<br/>' 
        % repr(e))
        log_actions(request = request, modifier=request.user.username,
                    modificationMessage=errorMessage)
        request.session['errorMessage'] += errorMessage
        return redirect(reverse('ims:imports'))
    dateStamp=timezone.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    xlsFileName = 'Backup_Export' + dateStamp + '.xls'
    backupFile = tempDir+ os.sep + xlsFileName
    try:
        xls.save(backupFile)
    except IOError as e:
        errorMessage += ('<br/><br/>Unhandled exception occurred during creation of backup file %s: %s<br/>' 
        % (backupFile, repr(e)))
        log_actions(request = request, modifier=request.user.username,
                    modificationMessage=errorMessage)
        request.session['errorMessage'] += errorMessage
        return redirect(reverse('ims:imports'))
    backupStream = StringIO.StringIO()
    zipHandle = zipfile.ZipFile(backupStream,'w',
                                compression = zipfile.ZIP_DEFLATED)
    zipHandle.write(backupFile, xlsFileName)
    try:
        os.remove(backupFile)
    except IOError as e:
        errorMessage += ('<br/><br/>Unhandled exception occurred during removal of temporary backup file %s: %s<br/>' 
        % (backupFile, repr(e)))
        log_actions(request = request, modifier=request.user.username,
                    modificationMessage=errorMessage)
        request.session['errorMessage'] += errorMessage
        return redirect(reverse('ims:imports'))
    zip_pictures(request, zipHandle)
    zipHandle.close()
    response = HttpResponse(backupStream.getvalue(), 
                            content_type="application/zip")
    
    response['Content-Disposition'] = 'attachment; filename=Backup_Export' + dateStamp + '.zip'
    return response
    
def create_inventory_export_xls_response(request, exportType='All'):
    errorMessage, __, __ = get_session_messages(request)
    try:
        xls = xlwt.Workbook(encoding="utf-8")
        xls=create_inventory_sheet(xls=xls, exportType=exportType)
    except XlrdutilsError as e:
        errorMessage += ('<br/><br/>Unhandled exception occurred during creation of inventory export spreadsheet: %s<br/>' 
        % repr(e))
        log_actions(request = request, modifier=request.user.username,
                    modificationMessage=errorMessage)
        request.session['errorMessage'] += errorMessage
        return redirect(reverse('ims:imports'))
    response = HttpResponse(content_type="application/ms-excel")
    response['Content-Disposition'] = 'attachment; filename=Inventory_Export_'+exportType+'.xls'
    xls.save(response)
    return response

def create_inventory_sheet(xls=None, exportType='All'):
    if not xls:
        return xls
    sheet1 = xls.add_sheet("Inventory")
    sites=Site.objects.all().order_by('name')
    sheet1=create_inventory_export_header(sheet=sheet1)
    rowIndex=1
    for site in sites:
        if exportType == 'All':
            allProducts=site.inventoryitem_set. values('information').distinct()
            productIdList=[]
            for product in allProducts:
                productIdList.append(product['information'])
            inventory=InventoryItem.objects.filter(
                                            site=site
                                            ).filter(
                                            information__in=productIdList
                                            ).order_by(
                                            'information')
        else: # latest inventory only
            inventory=site.latest_inventory()
        for item in inventory:
            sheet1.write(rowIndex,0,item.information.code)
            sheet1.write(rowIndex,1,item.information.name)
            sheet1.write(rowIndex,2,'p')
            sheet1.write(rowIndex,3,item.site.pk)
            sheet1.write(rowIndex,4,item.quantity)
            modified=item.modified
            localZone=pytz.timezone(settings.TIME_ZONE)
            modified=modified.astimezone(localZone).replace(tzinfo=None)
            style = xlwt.XFStyle()
            style.num_format_str = 'M/D/YY h:mm, mm:ss' # Other options: D-MMM-YY, D-MMM, MMM-YY, h:mm, h:mm:ss, h:mm, h:mm:ss, M/D/YY h:mm, mm:ss, [h]:mm:ss, mm:ss.0
            sheet1.write(rowIndex,5,modified,style)
            sheet1.write(rowIndex,6,item.modifier)
            sheet1.write(rowIndex,7,item.deleted)
            rowIndex += 1
    return xls

def create_site_export_xls_response(request):
    errorMessage, __, __ = get_session_messages(request)
    try:
        xls = xlwt.Workbook(encoding="utf-8")
        xls=create_site_export_sheet(xls=xls)
    except XlrdutilsError as e:
        errorMessage += ('<br/><br/>Unhandled exception occurred during creation of site export spreadsheet: %s<br/>' 
        % repr(e))
        log_actions(request = request, modifier=request.user.username,
                    modificationMessage=errorMessage)
        request.session['errorMessage'] += errorMessage
        return redirect(reverse('ims:imports'))
    response = HttpResponse(content_type="application/ms-excel")
    response['Content-Disposition'] = 'attachment; filename=Site_Export.xls'
    xls.save(response)
    return response

def create_site_export_sheet(xls=None):
    if not xls:
        return xls
    sheet1 = xls.add_sheet("Sites")
    sites=Site.objects.all().order_by('name')
    sheet1=create_site_export_header(sheet=sheet1)
    rowIndex=1
    for site in sites:
        sheet1.write(rowIndex,0,site.number)
        sheet1.write(rowIndex,1,site.name)
        sheet1.write(rowIndex,2,site.address1)
        sheet1.write(rowIndex,3,site.address2)
        sheet1.write(rowIndex,4,site.address3)
        sheet1.write(rowIndex,5,site.county)
        sheet1.write(rowIndex,6,site.contactName)
        sheet1.write(rowIndex,7,site.contactPhone)
        sheet1.write(rowIndex,8,site.notes)
        modified=site.modified
        localZone=pytz.timezone(settings.TIME_ZONE)
        modified=modified.astimezone(localZone).replace(tzinfo=None)
        style = xlwt.XFStyle()
        style.num_format_str = 'M/D/YY h:mm, mm:ss' # Other options: D-MMM-YY, D-MMM, MMM-YY, h:mm, h:mm:ss, h:mm, h:mm:ss, M/D/YY h:mm, mm:ss, [h]:mm:ss, mm:ss.0
        sheet1.write(rowIndex,9,modified,style)
        sheet1.write(rowIndex,10,site.modifier,style)
        rowIndex += 1
    return xls

def create_product_export_xls_response(request):
    errorMessage, __, __ = get_session_messages(request)
    try:
        xls = xlwt.Workbook(encoding="utf-8")
        xls=create_product_export_sheet(xls=xls)
    except XlrdutilsError as e:
        errorMessage += ('<br/><br/>Unhandled exception occurred during creation of product export spreadsheet: %s<br/>' 
        % repr(e))
        log_actions(request = request, modifier=request.user.username,
                    modificationMessage=errorMessage)
        request.session['errorMessage'] += errorMessage
        return redirect(reverse('ims:imports'))
    response = HttpResponse(content_type="application/ms-excel")
    response['Content-Disposition'] = 'attachment; filename=Product_Export.xls'
    xls.save(response)
    return response

def create_product_export_sheet(xls=None):
    if not xls:
        return xls
    sheet1 = xls.add_sheet("Products")
    products=ProductInformation.objects.all().order_by('code')
    sheet1=create_product_export_header(sheet=sheet1)
    rowIndex=1
    for product in products:
        sheet1.write(rowIndex,0,product.code)
        sheet1.write(rowIndex,1,product.name)
        if product.category:
            sheet1.write(rowIndex,2,str(product.category))
        sheet1.write(rowIndex,3,product.expendable_number())
        sheet1.write(rowIndex,4,product.unitOfMeasure)
        sheet1.write(rowIndex,5,product.quantityOfMeasure)
        sheet1.write(rowIndex,6,product.costPerItem)
        sheet1.write(rowIndex,7,product.cartonsPerPallet)
        sheet1.write(rowIndex,8,product.doubleStackPallets)
        sheet1.write(rowIndex,9,product.warehouseLocation)
        sheet1.write(rowIndex,10,product.expirationDate)
        sheet1.write(rowIndex,11,product.expirationNotes)
        modified=product.modified
        localZone=pytz.timezone(settings.TIME_ZONE)
        modified=modified.astimezone(localZone).replace(tzinfo=None)
        style = xlwt.XFStyle()
        style.num_format_str = 'M/D/YY h:mm, mm:ss' # Other options: D-MMM-YY, D-MMM, MMM-YY, h:mm, h:mm:ss, h:mm, h:mm:ss, M/D/YY h:mm, mm:ss, [h]:mm:ss, mm:ss.0
        sheet1.write(rowIndex,12,modified,style)
        sheet1.write(rowIndex,13,product.modifier)
        if product.picture:
            sheet1.write(rowIndex,14,product.picture.file.name)
        sheet1.write(rowIndex,15,product.originalPictureName)
        rowIndex += 1
    return xls

def create_category_export_sheet(xls=None):
    if not xls:
        return xls
    sheet1 = xls.add_sheet("Categories")
    categories=ProductCategory.objects.all().order_by('category')
    sheet1=create_category_export_header(sheet=sheet1)
    rowIndex=1
    for category in categories:
        sheet1.write(rowIndex,0,category.id)
        sheet1.write(rowIndex,1,category.category)
        rowIndex += 1
    return xls
    
def create_site_export_header(sheet=None):
    if sheet:
        sheet.write(0, 0, "Site Number")
        sheet.write(0, 1, "Site Name")
        sheet.write(0, 2, "Site Address 1")
        sheet.write(0, 3, "Site Address 2")
        sheet.write(0, 4, "Site Address 3")
        sheet.write(0, 5, "County")
        sheet.write(0, 6, "Site Contact Name")
        sheet.write(0, 7, "Site Phone")
        sheet.write(0, 8, "Site Notes")
        sheet.write(0, 9, "Modified")
        sheet.write(0, 10, "Modifier")
    else:
        return None
    return sheet

def create_product_export_header(sheet=None):
    if sheet:
        sheet.write(0, 0, "Product Code")
        sheet.write(0, 1, "Product Name")
        sheet.write(0, 2, "Product Category")
        sheet.write(0, 3, "Expendable")
        sheet.write(0, 4, "Unit of Measure")
        sheet.write(0, 5, "Qty of Measure")
        sheet.write(0, 6, "Cost Each")
        sheet.write(0, 7, "Cartons per Pallet")
        sheet.write(0, 8, "Double Stack Pallets")
        sheet.write(0, 9, "Warehouse Location")
        sheet.write(0, 10, "Expiration Date")
        sheet.write(0, 11, "Expiration Notes")
        sheet.write(0, 12, "Modified")
        sheet.write(0, 13, "Modifier")
        sheet.write(0, 14, "Picture")
        sheet.write(0, 15, "Original Picture Name")
    else:
        return None
    return sheet

def create_inventory_export_header(sheet=None):
    if sheet:
        sheet.write(0, 0, "Product Code")
        sheet.write(0, 1, "Product Name")
        sheet.write(0, 2, "Prefix")
        sheet.write(0, 3, "Site Number")
        sheet.write(0, 4, "Cartons")
        sheet.write(0, 5, "modified")
        sheet.write(0, 6, "modifier")
        sheet.write(0, 7,"deleted")
    else:
        return None
    return sheet

def create_category_export_header(sheet=None):
    if sheet:
        sheet.write(0, 0, "Category ID")
        sheet.write(0, 1, "Category")
    else:
        return None
    return sheet

def import_sites(request):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    perms = request.user.get_all_permissions()
    canChangeSites = 'ims.change_site' in perms
    canAddSites = 'ims.add_site' in perms
    if request.method == 'POST':
        if 'Cancel' in request.POST:
            return redirect(reverse('ims:imports'))
        if canAddSites and canChangeSites and 'Import' in request.POST:
            if 'file' in request.FILES:
                fileSelectForm = UploadFileForm(request.POST, request.FILES)
                if fileSelectForm.is_valid():
                    fileRequest=request.FILES['file']
                    try:
                        # make sure the database changes are atomic, in case 
                        # there is some error that occurs.  In the case of an 
                        # error in the import, we want to roll back to the 
                        # initial state
                        with transaction.atomic():
                            __,msg=Site.parse_sites_from_xls(file_contents=fileRequest.file.read(),
                                                                 modifier=request.user.username,
                                                                 retainModDate=False)
                            if len(msg) > 0:
                                errorMessage = ('Error while trying to import sites from spreadsheet:<br/>"%s".<br/><br/>Error Message:<br/> %s<br/>' 
                                                  % (fileRequest.name, msg))
                                log_actions(request = request, modifier=request.user.username,
                                            modificationMessage=errorMessage)
                            else:
                                infoMessage = ('Successful bulk import of sites using "%s"' 
                                               % fileRequest.name)
                                log_actions(request = request, 
                                            modifier=request.user.username,
                                            modificationMessage='successful bulk import of sites using "' + 
                                            fileRequest.name +'"')
                            if len(msg) > 0:
                                # in case of an issue rollback the atomic transaction
                                raise RimsImportSitesError
                    except Exception as e:
                        if isinstance(e,RimsError):
                            errorMessage += '<br/><br/>Changes to the database have been cancelled.<br/>'
                        else:
                            errorMessage += ('<br/><br/>Unhandled exception occurred during import_sites: %s<br/>Changes to the database have been cancelled.<br/>' 
                            % repr(e))
                            log_actions(request = request, modifier=request.user.username,
                                        modificationMessage=errorMessage)
                    request.session['errorMessage'] += errorMessage
                    request.session['warningMessage'] = warningMessage
                    request.session['infoMessage'] = infoMessage
                    return redirect(reverse('ims:imports'))
            else:
                warningMessage = 'No file selected'
    else:
        warningMessage='Importing sites will overwrite current site information!'
    if not (canAddSites and canChangeSites):
        errorMessage = 'You don''t have permission to import sites'
    fileSelectForm = UploadFileForm()
    return render(request,
                  'ims/import_sites.html', 
                  {'nav_imports':1,
                   'warningMessage':warningMessage,
                   'fileSelectForm':fileSelectForm,
                   'canImportSites':canAddSites and canChangeSites,
                   'infoMessage':infoMessage,
                   'errorMessage':errorMessage,
                   'adminName':adminName,
                   'adminEmail':adminEmail,
                   'siteVersion':siteVersion,
                   'imsVersion':imsVersion,
                   })

def import_products(request):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    perms = request.user.get_all_permissions()
    canChangeProducts = 'ims.change_productinformation' in perms
    canAddProducts = 'ims.add_productinformation' in perms
    if request.method == 'POST':
        if 'Cancel' in request.POST:
            return redirect(reverse('ims:imports'))
        if canAddProducts and canChangeProducts and 'Import' in request.POST:
            if 'file' in request.FILES:
                fileSelectForm = UploadFileForm(request.POST, request.FILES)
                if fileSelectForm.is_valid():
                    fileRequest=request.FILES['file']
                    try:
                        # make sure the database changes are atomic, in case 
                        # there is some error that occurs.  In the case of an 
                        # error in the import, we want to roll back to the 
                        # initial state
                        with transaction.atomic():
                            __,msg=ProductInformation.parse_product_information_from_xls(
                                       file_contents=fileRequest.file.read(),
                                       modifier=request.user.username,
                                       retainModDate=False)
                            if len(msg) > 0:
                                errorMessage = ('Error while trying to import products from spreadsheet:<br/>"%s".<br/><br/>Error Message:<br/> %s<br/>' 
                                                  % (fileRequest.name, msg))
                                log_actions(request = request, modifier=request.user.username,
                                            modificationMessage=errorMessage)
                            else:
                                infoMessage = ('Successful bulk import of products using "%s"' 
                                               % fileRequest.name)
                                log_actions(request = request, modifier = request.user.username,
                                            modificationMessage = infoMessage)
                            if len(msg) > 0:
                                # in case of an issue rollback the atomic transaction
                                raise RimsImportProductsError
                    except Exception as e:
                        if isinstance(e,RimsError):
                            errorMessage += '<br/><br/>Changes to the database have been cancelled.<br/>'
                        else:
                            errorMessage += ('<br/><br/>Unhandled exception occurred during import_products: %s<br/>Changes to the database have been cancelled.<br/>' 
                            % repr(e))
                            log_actions(request = request, modifier=request.user.username,
                                        modificationMessage=errorMessage)
                    request.session['errorMessage'] += errorMessage
                    request.session['warningMessage'] = warningMessage
                    request.session['infoMessage'] = infoMessage
                    return redirect(reverse('ims:imports'))
            else:
                warningMessage = 'No file selected'
    else:
        warningMessage='Importing products will overwrite current product information!'
    if not (canAddProducts and canChangeProducts):
        errorMessage = 'You don''t have permission to import products'
    fileSelectForm = UploadFileForm()
    return render(request,
                  'ims/import_products.html',
                  {'nav_imports':1,
                   'warningMessage':warningMessage,
                   'fileSelectForm':fileSelectForm,
                   'canImportProducts':canAddProducts and canChangeProducts,
                   'infoMessage':infoMessage,
                   'errorMessage':errorMessage,
                   'adminName':adminName,
                   'adminEmail':adminEmail,
                   'siteVersion':siteVersion,
                   'imsVersion':imsVersion,
                   })

def import_categories(request):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    perms = request.user.get_all_permissions()
    canChangeCategories = 'ims.change_productcategory' in perms
    canAddCategories = 'ims.add_productcategory' in perms
    if request.method == 'POST':
        if 'Cancel' in request.POST:
            return redirect(reverse('ims:imports'))
        if canAddCategories and canChangeCategories and 'Import' in request.POST:
            if 'file' in request.FILES:
                fileSelectForm = UploadFileForm(request.POST, request.FILES)
                if fileSelectForm.is_valid():
                    fileRequest=request.FILES['file']
                    try:
                        # make sure the database changes are atomic, in case 
                        # there is some error that occurs.  In the case of an 
                        # error in the import, we want to roll back to the 
                        # initial state
                        with transaction.atomic():
                            __,msg=ProductCategory.parse_product_categories_from_xls(
                                       file_contents=fileRequest.file.read(),
                                       modifier=request.user.username,
                                       retainModDate=False)
                            if len(msg) > 0:
                                errorMessage = ('Error while trying to import categories from spreadsheet:<br/>"%s".<br/><br/>Error Message:<br/> %s<br/>' 
                                                  % (fileRequest.name, msg))
                                log_actions(request = request, modifier=request.user.username,
                                            modificationMessage=errorMessage)
                            else:
                                infoMessage = ('Successful bulk import of categories using "%s"' 
                                               % fileRequest.name)
                                log_actions(request = request, modifier = request.user.username,
                                            modificationMessage = infoMessage)
                            if len(msg) > 0:
                                # in case of an issue rollback the atomic transaction
                                raise RimsImportCategoriesError
                    except Exception as e:
                        if isinstance(e,RimsError):
                            errorMessage += '<br/><br/>Changes to the database have been cancelled.<br/>'
                        else:
                            errorMessage += ('<br/><br/>Unhandled exception occurred during import_categories: %s<br/>Changes to the database have been cancelled.<br/>' 
                            % repr(e))
                            log_actions(request = request, modifier=request.user.username,
                                        modificationMessage=errorMessage)
                    request.session['errorMessage'] += errorMessage
                    request.session['warningMessage'] = warningMessage
                    request.session['infoMessage'] = infoMessage
                    return redirect(reverse('ims:imports'))
            else:
                warningMessage = 'No file selected'
    else:
        warningMessage='Importing products will overwrite current product information!'
    if not (canAddCategories and canChangeCategories):
        errorMessage = 'You don''t have permission to import categories'
    fileSelectForm = UploadFileForm()
    return render(request,
                  'ims/import_products.html',
                  {'nav_imports':1,
                   'warningMessage':warningMessage,
                   'fileSelectForm':fileSelectForm,
                   'canImportProducts':canAddCategories and canChangeCategories,
                   'infoMessage':infoMessage,
                   'errorMessage':errorMessage,
                   'adminName':adminName,
                   'adminEmail':adminEmail,
                   'siteVersion':siteVersion,
                   'imsVersion':imsVersion,
                   })

def import_inventory(request):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    perms = request.user.get_all_permissions()
    canAddInventory = 'ims.add_inventoryitem' in perms
    if request.method == 'POST':
        if 'Cancel' in request.POST:
            return redirect(reverse('ims:imports'))
        if canAddInventory and 'Import' in request.POST:
            if 'file' in request.FILES:
                fileSelectForm = UploadFileForm(request.POST, request.FILES)
                if fileSelectForm.is_valid():
                    fileRequest=request.FILES['file']
                    try:
                        # make sure the database changes are atomic, in case 
                        # there is some error that occurs.  In the case of an 
                        # error in the import, we want to roll back to the 
                        # initial state
                        with transaction.atomic():
                            __,msg=InventoryItem.parse_inventory_from_xls(
                                       file_contents=fileRequest.file.read(),
                                       modifier=request.user.username,
                                       retainModDate=False)
                            if len(msg) > 0:
                                errorMessage = ('Error while trying to import inventory from spreadsheet:<br/>"%s".<br/><br/>Error Message:<br/> %s<br/>' 
                                                  % (fileRequest.name, msg))
                                log_actions(request = request, modifier=request.user.username,
                                            modificationMessage=errorMessage)
                            else:
                                infoMessage = ('Successful bulk import of inventory using "%s"' 
                                               % fileRequest.name)
                                log_actions(request = request, modifier=request.user.username,
                                            modificationMessage='successful bulk import of inventory using "' + 
                                            fileRequest.name +'"')
                            if len(msg) > 0:
                                # in case of an issue rollback the atomic transaction
                                raise RimsImportInventoryError
                    except Exception as e:
                        if isinstance(e,RimsError):
                            errorMessage += '<br/><br/>Changes to the database have been cancelled.'
                        else:
                            errorMessage += ('<br/><br/>Unhandled exception occurred during import_inventory: %s<br/>Changes to the database have been cancelled.' 
                            % repr(e))
                            log_actions(request = request, modifier=request.user.username,
                                        modificationMessage=errorMessage)
                    request.session['errorMessage'] += errorMessage
                    request.session['warningMessage'] = warningMessage
                    request.session['infoMessage'] = infoMessage
                    return redirect(reverse('ims:imports'))
            else:
                warningMessage = 'No file selected'
    else:
        warningMessage='Importing inventory will change current inventory information!'
    if not canAddInventory:
        errorMessage = 'You don''t have permission to import inventory'
    fileSelectForm = UploadFileForm()
    return render(request,
                  'ims/import_inventory.html',
                  {'nav_imports':1,
                   'warningMessage':warningMessage,
                   'fileSelectForm':fileSelectForm,
                   'canImportInventory':canAddInventory,
                   'infoMessage':infoMessage,
                   'errorMessage':errorMessage,
                   'adminName':adminName,
                   'adminEmail':adminEmail,
                   'siteVersion':siteVersion,
                   'imsVersion':imsVersion,
                   })

def import_backup_from_xls(request,
                          modifier='',
                          perms=[]):
    errorMessage, warningMessage, infoMessage = get_session_messages(request)
    canDeleteSites='ims.delete_site' in perms
    canAddSites='ims.add_site' in perms
    canDeleteProducts='ims.delete_productinformation' in perms
    canAddProducts='ims.add_productinformation' in perms
    canDeleteInventory='ims.delete_inventoryitem' in perms
    canAddInventory='ims.add_inventoryitem' in perms
    canDeleteCategories='ims.delete_productcategory' in perms
    canAddCategories='ims.add_productcategory' in perms
    canChangeProducts='ims.change_productinformation' in perms
    canChangeSites='ims.change_site' in perms
    canChangeInventory='ims.change_inventoryitem' in perms
    canChangeCategories='ims.change_productcategory' in perms
    fileRequest=request.FILES['file']
    if canAddInventory and canChangeInventory and canDeleteInventory and\
            canAddSites and canChangeSites and canDeleteSites and\
            canAddProducts and canChangeProducts and canDeleteProducts and\
            canAddCategories and canChangeCategories and canDeleteCategories:
        file_contents=fileRequest.file.read()
        inventory=InventoryItem.objects.all()
        sites=Site.objects.all()
        products=ProductInformation.objects.all()
        categories = ProductCategory.objects.all()
        try:
            # make sure the deletes are atomic, in case there is some error that
            # occurs.  In the case of an error in the restore, we want to roll
            # back to the initial state
            with transaction.atomic():
                inventory.delete()
                sites.delete()
                products.delete()
                categories.delete()
                __, msg=Site.parse_sites_from_xls(file_contents=file_contents,
                                        modifier=modifier)
                if len(msg) > 0:
                    errorMessage=('Error while trying to restore sites from spreadsheet:<br/>"%s".<br/><br/>Error Message:<br/> %s' %
                                    (fileRequest.name, msg))
                    log_actions(request = request, modifier=modifier,
                                modificationMessage=errorMessage)
                else:
                    infoMessage += ('Successful restore of sites using "%s"<br/>' 
                                   % fileRequest.name)
                    log_actions(request = request, modifier=modifier,
                                modificationMessage=infoMessage)
                __, msg=ProductCategory.parse_product_categories_from_xls(file_contents=file_contents,
                                                      modifier=modifier)
                if len(msg) > 0:
                    errorMessage += ('Error while trying to restore categories from spreadsheet:<br/>"%s".<br/><br/>Error Message:<br/> %s' %
                                    (fileRequest.name, msg))
                    log_actions(request = request, modifier=modifier,
                                modificationMessage=errorMessage)
                else:
                    infoMessage += ('Successful restore of categories using "%s"<br/>' 
                                   % fileRequest.name)
                    log_actions(request = request, modifier=modifier,
                                modificationMessage=infoMessage)
                __, msg=ProductInformation.parse_product_information_from_xls(file_contents=file_contents,
                                                      modifier=modifier)
                if len(msg) > 0:
                    errorMessage += ('Error while trying to restore products from spreadsheet:<br/>"%s".<br/><br/>Error Message:<br/> %s' %
                                    (fileRequest.name, msg))
                    log_actions(request = request, modifier=modifier,
                                modificationMessage=errorMessage)
                else:
                    infoMessage += ('Successful restore of products using "%s"<br/>' 
                                   % fileRequest.name)
                    log_actions(request = request, modifier=modifier,
                                modificationMessage=infoMessage)
                __, msg=InventoryItem.parse_inventory_from_xls(file_contents=file_contents,
                                                          modifier=modifier)
                if len(msg) > 0 and msg != 'Found duplicate inventory items':
                    errorMessage += ('Error while trying to restore inventory from spreadsheet:<br/>"%s".<br/><br/>Error Message:<br/> %s' %
                                    (fileRequest.name, msg))
                    log_actions(request = request, modifier=modifier,
                                modificationMessage=errorMessage)
                else:
                    if msg == 'Found duplicate inventory items':
                        # when restoring, duplicate inventory items are OK
                        msg=''
                    infoMessage += ('Successful restore of inventory using "%s"<br/>' 
                                   % fileRequest.name)
                    log_actions(request = request, modifier=modifier,
                                modificationMessage=infoMessage)
                if len(msg) > 0:
                    # in case of an issue rollback the atomic transaction
                    errorMessage += msg + '<br/>'
                    raise RimsRestoreError
        except Exception as e:
            if isinstance(e,RimsError):
                errorMessage += '<br/><br/>Changes to the database have been cancelled.'
            else:
                errorMessage += ('<br/><br/>Unhandled exception occurred during restore: %s<br/>Changes to the database have been cancelled.' 
                % repr(e))
                log_actions(request = request, modifier=modifier,
                            modificationMessage=errorMessage)
                infoMessage=''
    else:
        errorMessage='You don''t have permission to restore the database'
    return infoMessage,warningMessage,errorMessage

def restore(request):
    errorMessage, __, infoMessage = get_session_messages(request)
    perms=request.user.get_all_permissions()
    canDeleteSites='ims.delete_site' in perms
    canAddSites='ims.add_site' in perms
    canDeleteProducts='ims.delete_productinformation' in perms
    canAddProducts='ims.add_productinformation' in perms
    canDeleteInventory='ims.delete_inventoryitem' in perms
    canAddInventory='ims.add_inventoryitem' in perms
    canChangeProducts='ims.change_productinformation' in perms
    canChangeSites='ims.change_site' in perms
    canChangeInventory='ims.change_inventoryitem' in perms
    canAdd = canAddInventory and canAddProducts and canAddSites
    canDelete = canDeleteInventory and canDeleteProducts and canDeleteSites
    canChange = canChangeInventory and canChangeProducts and canChangeSites
    warningMessage='Restoring the database will cause all current information to be replaced!!!'
    if not (canAdd and canChange and canDelete):
        errorMessage='You don''t have permission to restore the database'
    if request.method=='POST':
        if 'Cancel' in request.POST:
            return redirect(reverse('ims:imports'))
        if 'Restore' in request.POST:
            fileSelectForm = UploadFileForm(request.POST, request.FILES)
            if fileSelectForm.is_valid():
                infoMsg,warningMsg,errorMsg = import_backup_from_xls(request,
                                          modifier=request.user.username,
                                          perms=perms)
                request.session['errorMessage'] = errorMsg
                request.session['warningMessage'] = warningMsg
                request.session['infoMessage'] = infoMsg
                return redirect(reverse('ims:imports'))
            else:
                warningMessage='No file selected'
    fileSelectForm = UploadFileForm()
    return render(request, 'ims/restore.html', {"nav_imports":1,
                                                 'infoMessage':infoMessage,
                                                'warningMessage':warningMessage,
                                                'errorMessage':errorMessage,
                                                'canDelete':canDelete,
                                                'canAdd':canAdd,
                                                'canChange':canChange,
                                                'fileSelectForm':fileSelectForm,
                                                'adminName':adminName,
                                                'adminEmail':adminEmail,
                                                'siteVersion':siteVersion,
                                                'imsVersion':imsVersion,
                                                })
    
def process_picture(request, product):
    '''
    set size of uploaded picture file and create associated thumbnail image.
    '''
    if product.picture:
        product.originalPictureName = product.picture.file.name
        product.save()
        aspectRatio = get_picture_aspect_ratio(request, product = product)
        pictureHeight = int(settings.PICTURE_SIZE / aspectRatio)
        pictureWidth = aspectRatio * pictureHeight
        try:
            check_call(['convert', 
                                   '-resize', 
                                   '%dx%d' % 
                                   (pictureWidth,pictureHeight),
                                   product.picture.file.name, 
                                   product.picture.file.name])
        except CalledProcessError as e:
            request.session['errorMessage'] = 'Unable to resize picture. Nothing was saved. %s' % e.message
            raise RimsImageProcessingError
        create_thumbnail(request, product = product)
        
def create_thumbnail(request, product = None):
    if product and product.picture:
        aspectRatio = get_picture_aspect_ratio(request, product = product)
        thumbnailHeight = int(settings.THUMBNAIL_SIZE / aspectRatio)
        thumbnailWidth = aspectRatio * thumbnailHeight
        thumbnailPieces = product.picture.file.name.rsplit('.',1)
        thumbnailFile = thumbnailPieces[0] + 'thumb.' + thumbnailPieces[1]
        try:
            check_call(['convert', 
                                   '-resize', 
                                   '%dx%d' % 
                                   (thumbnailWidth,thumbnailHeight),
                                   product.picture.file.name, 
                                   thumbnailFile])
        except CalledProcessError as e:
            request.session['errorMessage'] = 'Unable to create thumbnail. Nothing was saved. %s' % e.message
            raise RimsImageProcessingError
        
def get_picture_aspect_ratio(request, product = None):
    aspectRatio = 1.0
    if product and product.picture:
        try:
            geometry = check_output(['identify','-format','%wx%h', product.picture.file.name])
        except CalledProcessError as e:
            request.session['errorMessage'] = 'Unable to open picture. Nothing was saved. %s' % e.message
            raise RimsImageProcessingError
        imageW, imageH = geometry.strip().split('x')
        aspectRatio = float(imageW) / float(imageH)
    return aspectRatio

def rotate_picture(request, product, rotation):
    '''
    set rotation of inventory picture and its thumbnail
    '''
    if product.picture:
        previousPictureName = product.picture.file.name
        previousThumbnailName = product.thumbnail_name()
        try:
            check_call(['convert', 
                                   '-rotate', 
                                   '%f' % 
                                   rotation,
                                   previousPictureName, 
                                   previousPictureName])
        except CalledProcessError as e:
            request.session['errorMessage'] = 'Unable to rotate picture. Nothing was saved. %s' % e.message
            raise RimsImageProcessingError
        with open(previousPictureName) as p:
            product.picture.save(product.originalPictureName, File(p))
        product.save()
        # we now know the actual picture file name and can create a matching
        # thumbnail
        create_thumbnail(request, product = product)
        if os.path.isfile(previousPictureName):
            os.remove(previousPictureName)
        if os.path.isfile(previousThumbnailName):
            os.remove(previousThumbnailName)