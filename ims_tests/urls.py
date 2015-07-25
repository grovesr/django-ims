from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
    url(r'^ims/',include('ims.urls',namespace='ims')),
)
