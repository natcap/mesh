import logging
from PyQt4.QtGui import *
from PyQt4.QtCore import *

global_folder= ''


logging.basicConfig(format='%(asctime)s %(name)-18s %(levelname)-8s \
    %(message)s', level=logging.DEBUG, datefmt='%m/%d/%Y %H:%M:%S ')
LOGGER = logging.getLogger('mesh_runtime_log')
LOGGER.setLevel(logging.INFO)

heading_font = QFont()
heading_font.setPointSize(12)
heading_font.setWeight(75)
heading_font.setUnderline(False)
heading_font.setBold(True)

minor_heading_font = QFont()
minor_heading_font.setPointSize(10)
minor_heading_font.setWeight(75)
minor_heading_font.setUnderline(False)
minor_heading_font.setBold(True)

bold_font = QFont()
bold_font.setPointSize(8)
bold_font.setWeight(75)
bold_font.setUnderline(False)
bold_font.setBold(True)

italic_font = QFont()
italic_font.setPointSize(8)
italic_font.setWeight(75)
italic_font.setUnderline(False)
italic_font.setBold(False)
italic_font.setItalic(True)

small_font = QFont()
small_font.setPointSize(7)
small_font.setWeight(75)
small_font.setUnderline(False)
small_font.setBold(False)
small_font.setItalic(True) #

stylesheet = """
QWidget {

border-width: 10px;
background-color: rgb(255, 255, 255);

padding: 6px;
}
"""

size_policy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
size_policy.setHorizontalStretch(1)
size_policy.setVerticalStretch(1)

size_policy_minimum = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
size_policy_minimum.setHorizontalStretch(1)
size_policy_minimum.setVerticalStretch(1)


gdal_number_to_ogr_field_type = {
    1: 0, # not sure if not OFSTBoolean
    2: 0, # seemed to be unimplemented as uint etc.
    3: 0,
    4: 0,
    5: 0,
    6: 2,
    7: 2, # not sure if correct
}

type_string_to_ogr_field_type = {
    'int': gdal_number_to_ogr_field_type[1],
    'uint': gdal_number_to_ogr_field_type[1],
    'uint8': gdal_number_to_ogr_field_type[1],
    'uint16': gdal_number_to_ogr_field_type[1],
    'int16': gdal_number_to_ogr_field_type[1],
    'uint32': gdal_number_to_ogr_field_type[1],
    'int32': gdal_number_to_ogr_field_type[1],
    'float': gdal_number_to_ogr_field_type[6],
    'float32': gdal_number_to_ogr_field_type[6],
    'float64': gdal_number_to_ogr_field_type[7],
    'string': 4,
}

possible_shapefile_extensions = ['.shp',
                            '.shx',
                            '.dbf',
                            '.prj',
                            '.sbn',
                            '.sbx',
                            '.fbn',
                            '.fbx',
                            '.ain',
                            '.aih',
                            '.ixs',
                            '.mxs',
                            '.atx',
                            '.shp.xml',
                            '.cpg',
                            '.qix'
                            ]
