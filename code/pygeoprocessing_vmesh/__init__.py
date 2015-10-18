"""__init__ module for pygeprocessing, imports all the geoprocessing functions
    into the pygeoprocessing namespace"""

import unittest
import logging
import types

import pygeoprocessing.geoprocessing as geoprocessing
from geoprocessing import *

__all__ = []
for attrname in dir(geoprocessing):
    if type(getattr(geoprocessing, attrname)) is types.FunctionType:
        __all__.append(attrname)

LOGGER = logging.getLogger('pygeoprocessing')
LOGGER.setLevel(logging.DEBUG)

def test():
    """run modulewide tests"""
    LOGGER.info('running tests on %s', os.path.dirname(__file__))
    suite = unittest.TestLoader().discover(os.path.dirname(__file__))
    unittest.TextTestRunner(verbosity=2).run(suite)
__version__ = "0.2.2"
build_data = ['release', 'build_id', 'py_arch', 'branch', 'version_str']
branch = 'master'
build_id = 'master-bf9195957c9a'
py_arch = '32bit'
release = '0.2.2'
version_str = '0.2.2'
__version__ = "0.2.2"
build_data = ['release', 'build_id', 'py_arch', 'branch', 'version_str']
branch = 'master'
build_id = 'master-bf9195957c9a'
py_arch = '32bit'
release = '0.2.2'
version_str = '0.2.2'
