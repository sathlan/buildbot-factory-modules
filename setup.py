import os
from setuptools import setup, find_packages

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "ferbot",
    version = 0.1,
    author  = 'Sofer Athlan-Guyot',
    author_email = 'chem@unix4.me',
    description = ('Helpers to build complex factories for buildbot.  Can be based on Vagrant, use VirtualEnv, RVM, or openvz.'),
    url = 'ferbot.unix4.net',
    license = 'AGPL',
    keywords = 'buildbot vagrant virtualenv rvm continuous integegration CI',
    long_description=read('README.org'),
    packages = find_packages('src'),
    package_dir  = {'': 'src'},
    classifiers = [
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Intended Audience :: Developers',
        'Operating System :: Unix',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Testing',],
    install_requires = [
        'buildbot == 0.8.5',
        'nose == 1.1.2',
    ],
    test_suite='nose.collector',)

