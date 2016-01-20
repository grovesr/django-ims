from django.forms import Form, ClearableFileInput, FileField, \
ModelForm, HiddenInput, BooleanField, IntegerField, TextInput, \
Textarea, CheckboxInput
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text
from django.utils.html import conditional_escape
from django.forms.utils import ErrorList
from django.core.exceptions import ValidationError
from django.conf import settings
from ims.models import InventoryItem, ProductInformation, Site
import re

class ImsClearableFileInput(ClearableFileInput):
    fileUrl = ''
    def __init__(self, fileUrl = ''):
        self.fileUrl = fileUrl
        super(ImsClearableFileInput, self).__init__()
        
    def render(self, name, value, attrs=None):
        substitutions = {
            'initial_text': self.initial_text,
            'input_text': self.input_text,
            'clear_template': '',
            'clear_checkbox_label': self.clear_checkbox_label,
        }
        template = '%(input)s'
        substitutions['input'] = super(ClearableFileInput, self).render(name, value, attrs)
        if value and (hasattr(value, "url") or self.fileUrl != ''):
            template = self.template_with_initial
            urlPieces = force_text(value).rsplit('/',1)
            if len(urlPieces) > 1:
                urlText = urlPieces[1]
            else:
                urlText = 'Invalid'
            if not self.fileUrl and hasattr(value, "url"):
                substitutions['initial_url'] = value.url
                substitutions['initial'] = urlText
            else:
                substitutions['initial_url'] = self.fileUrl
                substitutions['initial'] = urlText
            if not self.is_required:
                checkbox_name = self.clear_checkbox_name(name)
                checkbox_id = self.clear_checkbox_id(checkbox_name)
                substitutions['clear_checkbox_name'] = conditional_escape(checkbox_name)
                substitutions['clear_checkbox_id'] = conditional_escape(checkbox_id)
                substitutions['clear'] = CheckboxInput().render(checkbox_name, False, attrs={'id': checkbox_id})
                substitutions['clear_template'] = self.template_with_clear % substitutions

        return mark_safe(template % substitutions)
    
class UploadFileForm(Form):
    file = FileField()

class InventoryItemForm(ModelForm):
    class Meta:
        model = InventoryItem
        fields=['information','quantity','site','modifier',]
        widgets = {'information': HiddenInput(),
                   'modifier': HiddenInput()}
    error_css_class = 'detail-table-error-text'
    required_css_class = 'ims-required-field'
    
class InventoryItemFormNoSite(ModelForm):
    class Meta:
        model = InventoryItem
        fields=['information','quantity','site','deleteItem']
        widgets = {'information': HiddenInput(),
                   'site':HiddenInput(),}
    deleteItem=BooleanField(required=False, label = "Delete")
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'
    
    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        if quantity < 0:
            raise ValidationError('quantity must be >= 0')
        return quantity
    
class InventoryItemFormNoSiteNoDelete(ModelForm):
    class Meta:
        model = InventoryItem
        fields=['information','quantity','site']
        widgets = {'information': HiddenInput(),
                   'site':HiddenInput(),}
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'
    
    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        if quantity < 0:
            raise ValidationError('quantity must be >= 0')
        return quantity
    
class InventoryItemFormAddSubtractNoSite(ModelForm):
    class Meta:
        model = InventoryItem
        fields=['information','site','addSubtract']
        widgets = {'information': HiddenInput(),
                   'site':HiddenInput(),}
    addSubtract=IntegerField(initial = 0, required=False, label = "Add/Subtract")
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'
    
    def clean_addSubtract(self):
        addSubtract = self.cleaned_data['addSubtract']
        if not addSubtract:
            addSubtract = 0;
        if self.instance.quantity + addSubtract < 0:
            raise ValidationError('final quantity must be >= 0')
        return addSubtract
    
def validate_product_code(code):
    m=re.findall(r'[^\w\d\_\-]+', code)
    if m:
        raise ValidationError('Invalid character(s).  Use only numbers, letters, dashes, or underscores')
    
class ProductInformationForm(ModelForm):
    class Meta:
        model = ProductInformation
        try:
            additionalFields = settings.PRODUCT_INFORMATION_FORM_ADDED_FIELDS
        except AttributeError:
            additionalFields = ['expendable',
                'cartonsPerPallet', 'doubleStackPallets', 'warehouseLocation',
                'canExpire', 'expirationDate', 'expirationNotes', 'costPerItem',
                'picture']
        fields=['modifier', 'category', 'name', 'code', 'unitOfMeasure', 
                'quantityOfMeasure',] + additionalFields 
        widgets = {'modifier':TextInput(attrs = {'readonly':'readonly'}),
                   'picture':ImsClearableFileInput(fileUrl = '#')}
        labels = {'expirationNotes':'Notes',}
        help_texts = {'expirationNotes':'Special product notes',}
    error_css_class = 'detail-table-error-text'
    required_css_class = 'ims-required-field'
    
    def clean_code(self):
        code = self.cleaned_data['code']
        m=re.findall(r'[^\w\d\_\-]+', code)
        validate_product_code(code)
        if m:
            raise ValidationError('Use only numbers, letters, dashes, or underscores')
        return code
    
class ProductInformationFormReadOnly(ModelForm):
    class Meta:
        model = ProductInformation
        try:
            additionalFields = settings.PRODUCT_INFORMATION_FORM_ADDED_FIELDS
        except AttributeError:
            additionalFields = ['expendable',
                'cartonsPerPallet', 'doubleStackPallets', 'warehouseLocation',
                'canExpire', 'expirationDate', 'expirationNotes', 'costPerItem',]
        fields=['modifier', 'category', 'name', 'code', 'unitOfMeasure', 
                'quantityOfMeasure',] + additionalFields 
        if 'picture' in fields:
            del(fields[fields.index('picture')])
        widgets = {}
        for field in fields:
            widget = model._meta.get_field(field).formfield().widget
            widget.attrs = widget.build_attrs({'readonly':1})
            widgets[field] = widget
        labels = {'expirationNotes':'Notes',}
        help_texts = {'expirationNotes':'Special product notes',}
    error_css_class = 'detail-table-error-text'
    required_css_class = 'ims-required-field'
    
class ProductInformationFormWithQuantity(ModelForm):
    class Meta:
        model = ProductInformation
        fields = [ 'code',]
        widgets = {'code':HiddenInput()
                   }
    Quantity=IntegerField(initial=0)
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'
    
class SiteForm(ModelForm):
    class Meta:
        model = Site
        fields = ['modifier','name','county','address1','address2','address3','contactName',
                  'contactPhone','notes',]
        widgets = {'modifier':TextInput(attrs = {'readonly':'readonly'}),
                   }
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'

class SiteFormReadOnly(ModelForm):
    class Meta:
        model = Site
        fields = ['name','county','address1','address2','address3','contactName',
                  'contactPhone','modifier','notes']
        widgets = {'name':TextInput(attrs = {'readonly':1}),
                   'county':TextInput(attrs = {'readonly':1}),
                   'address1':TextInput(attrs = {'readonly':1}),
                   'address2':TextInput(attrs = {'readonly':1}),
                   'address3':TextInput(attrs = {'readonly':1}),
                   'contactName':TextInput(attrs = {'readonly':1}),
                   'contactPhone':TextInput(attrs = {'readonly':1}),
                   'modifier':TextInput(attrs = {'readonly':'readonly'}),
                   'notes':Textarea(attrs = {'readonly':1}),
                   }
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'

class SiteListForm(ModelForm):
    class Meta:
        model = Site
        fields=['Delete',]
    Delete=BooleanField(initial = False,)
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'

class ProductListFormWithDelete(ModelForm):
    class Meta:
        model = ProductInformation
        fields=['Delete']
    Delete=BooleanField(initial = False,)
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'
    
class ProductListFormWithoutDelete(ModelForm):
    class Meta:
        model = ProductInformation
        fields=[]
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'
    
class ProductListFormWithAdd(ModelForm):
    class Meta:
        model = ProductInformation
        fields=['Add']
    Add=BooleanField(initial = False,)
    error_css_class = 'detail-error-text'
    required_css_class = 'ims-required-field'

class TitleErrorList(ErrorList):
    def __unicode__(self):              # __unicode__ on Python 2
        return self.as_title()

    def as_title(self):
        if not self: 
            return ''
        return '%s, ' % ''.join(['%s, ' % e for e in self])[:-2]
