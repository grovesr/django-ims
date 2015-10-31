from ims import VERSION
import os
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='django-ims',
    version=VERSION,
    packages=['ims', 'ims_tests'],
    include_package_data=True,
    license='3-BSD License',  # example license
    description='django-ims is a simple Django app to for managing inventory',
    long_description=README,
    url='http://www.example.com/',
    author='Rob Groves',
    author_email='grovesr1@yahoo.com',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Python',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License', # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        # Replace these appropriately if you are stuck on Python 2.
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)
