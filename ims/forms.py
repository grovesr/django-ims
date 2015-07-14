from django import forms
from django.forms.utils import ErrorList
from ims.models import InventoryItem, ProductInformation, Site
from functools import partial

class UploadFileForm(forms.Form):
    file = forms.FileField()

class DateSpanQueryForm(forms.Form):
    DateInput = partial(forms.DateInput, {'class': 'datepicker'})
    startDate=forms.DateField(widget=DateInput(), label="start")
    stopDate=forms.DateField(widget=DateInput(), label="end")
    
class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields=['information','quantity','site','modifier',]
        widgets = {'information': forms.HiddenInput(),
                   'modifier': forms.HiddenInput()}
    error_css_class = 'detail-table-error-text'
    required_css_class = 'ims-required-field'
    
class InventoryItemFormNoSite(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields=['information','quantity','site','deleteItem']
        widgets = {'information': forms.HiddenInput(),
                   'site':forms.HiddenInput(),}
    deleteItem=forms.BooleanField(required=False)
    error_css_class = 'detail-table-error-text'
    required_css_class = 'ims-required-field'
    
class ProductInformationForm(forms.ModelForm):
    class Meta:
        model = ProductInformation
        fields=['modifier', 'name', 'code', 'unitOfMeasure', 'quantityOfMeasure','expendable',
                'cartonsPerPallet', 'doubleStackPallets', 'warehouseLocation',
                'canExpire', 'expirationDate', 'expirationNotes', 'costPerItem',]
        widgets = {'modifier':forms.TextInput(attrs = {'readonly':'readonly'}),
                   }
    error_css_class = 'detail-table-error-text'
    required_css_class = 'ims-required-field'
    
class ProductInformationFormWithQuantity(forms.ModelForm):
    class Meta:
        model = ProductInformation
        fields = [ 'code',]
        widgets = {'code':forms.HiddenInput()
                   }
    Quantity=forms.IntegerField(initial=0)
    error_css_class = 'detail-table-error-text'
    required_css_class = 'ims-required-field'
    
class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ['modifier','name','county','address1','address2','address3','contactName',
                  'contactPhone','notes',]
        widgets = {'modifier':forms.TextInput(attrs = {'readonly':'readonly'}),
                   }
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'

class SiteFormReadOnly(forms.ModelForm):
    class Meta:
        model = Site
        fields = ['name','county','address1','address2','address3','contactName',
                  'contactPhone','modifier','notes']
        widgets = {'name':forms.TextInput(attrs = {'readonly':1}),
                   'county':forms.TextInput(attrs = {'readonly':1}),
                   'address1':forms.TextInput(attrs = {'readonly':1}),
                   'address2':forms.TextInput(attrs = {'readonly':1}),
                   'address3':forms.TextInput(attrs = {'readonly':1}),
                   'contactName':forms.TextInput(attrs = {'readonly':1}),
                   'contactPhone':forms.TextInput(attrs = {'readonly':1}),
                   'modifier':forms.TextInput(attrs = {'readonly':'readonly'}),
                   'notes':forms.Textarea(attrs = {'readonly':1}),
                   }
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'

class SiteListForm(forms.ModelForm):
    class Meta:
        model = Site
        fields=['Delete',]
    Delete=forms.BooleanField(initial = False,)
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'

class ProductListFormWithDelete(forms.ModelForm):
    class Meta:
        model = ProductInformation
        fields=['Delete']
    Delete=forms.BooleanField(initial = False,)
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'
    
class ProductListFormWithoutDelete(forms.ModelForm):
    class Meta:
        model = ProductInformation
        fields=[]
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'
    
class ProductListFormWithAdd(forms.ModelForm):
    class Meta:
        model = ProductInformation
        fields=['Add']
    Add=forms.BooleanField(initial = False,)
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'

class TitleErrorList(ErrorList):
    def __unicode__(self):              # __unicode__ on Python 2
        return self.as_title()

    def as_title(self):
        if not self: 
            return ''
        return '%s, ' % ''.join(['%s, ' % e for e in self])[:-2]
