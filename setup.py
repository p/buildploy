import os.path
from distutils.core import setup

package_name = 'buildploy'
package_version = '0.3.0'

data_files = ['LICENSE', 'README.md']

setup(name=package_name,
    version=package_version,
    description='Build projects into deployment repositories',
    author='Oleg Pudeyev',
    author_email='oleg@bsdpower.com',
    url='http://github.com/p/buildploy',
    py_modules=['buildploy'],
    scripts=['bin/buildploy'],
    data_files=[
        (data_files),
    ],
    license="BSD",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
)
