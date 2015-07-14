from django.contrib import admin
from ims.models import InventoryItem, Site, ProductInformation
    
class ProductInline(admin.TabularInline):
    model = InventoryItem
    extra = 0
 
class ProductInformationAdmin(admin.ModelAdmin):
    fieldsets = [
    (None,               {'fields': ['name', 'code', 'quantityOfMeasure',
                                     'unitOfMeasure','expendable','costPerItem']}),
    ('Warehouse Information', {'fields': ['warehouseLocation', 'cartonsPerPallet',
    'doubleStackPallets'], 'classes': ['collapse']}),
    ('Expiration Information', {'fields': ['canExpire', 'expirationDate',
    'expirationNotes'], 'classes': ['collapse']}),
    ]
    list_display = ['name','code']
    search_fields = ['name', 'code',]
    inlines = [ProductInline]
     
class SiteAdmin(admin.ModelAdmin):
    fieldsets = [
    (None,               {'fields': ['name','number', 'address1', 'address2',
                                     'address3','contactName','contactPhone']}),
    ('Notes',             {'fields': ['notes'], 'classes': ['collapse']})
    ]
    list_display = ['name', 'number']
    search_fields = ['name', 'number']
    inlines = [ProductInline]
     
class ProductAdmin(admin.ModelAdmin):
    fieldsets = [
    ]
    list_display = ['information', 'site', 'quantity']
    search_fields = []
     
# Register your models here.
admin.site.register(ProductInformation, ProductInformationAdmin)
admin.site.register(Site, SiteAdmin)
#admin.site.register(DRNumber)
#admin.site.register(TransactionPrefix)
admin.site.register(InventoryItem, ProductAdmin)