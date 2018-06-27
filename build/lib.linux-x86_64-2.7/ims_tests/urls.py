from django.conf.urls import include, url

urlpatterns = [
    url(r'^ims/',include('ims.urls',namespace='ims')),
]
