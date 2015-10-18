import sys, os, logging, json, threading, time, platform, traceback, tempfile, locale, imp, errno, shutil, codecs, datetime, subprocess, math, random
from collections import OrderedDict, deque
from types import StringType

#import pygeoprocessing as pg
import pygeoprocessing_vmesh as pg

from osgeo import ogr, osr

from pprint import pprint as pp
from PyQt4 import QtGui
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
from matplotlib import rcParams
rcParams.update({'figure.autolayout': True}) # This line makes matplotlib automatically change the fig size according to legends, labels etc.

import gdal
import numpy as np

import pandas as pd

from mesh_utilities import config
from mesh_utilities import utilities

import invest_natcap

LOGGER = config.LOGGER
LOGGER.setLevel(logging.INFO)
ENCODING = sys.getfilesystemencoding()


def clip_geotiff_from_base_data(input_shape_uri, base_data_uri, output_geotiff_uri):
    gdal_command = 'gdalwarp -cutline ' + input_shape_uri + ' -crop_to_cutline -overwrite -s_srs EPSG:4326 -t_srs EPSG:54030 -of GTiff ' + base_data_uri + ' ' + output_geotiff_uri
    print gdal_command
    os.system(gdal_command)


def copy_from_base_data(base_data_uri, output_uri):
    shutil.copyfile(base_data_uri, output_uri)


def save_shp_feature_by_attribute(shp_uri, attribute, output_shp_uri):
    input_shp = ogr.Open(shp_uri)
    input_layer = input_shp.GetLayer(0)

    driver = ogr.GetDriverByName('ESRI Shapefile')

    # if not os.path.exists(output_shp_uri):
    #     os.makedirs(output_shp_uri)

    output_shp = driver.CreateDataSource(output_shp_uri)

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    output_layer = output_shp.CreateLayer("selected_watershed", srs, ogr.wkbPolygon)
    # field_name = ogr.FieldDefn("ws_id", ogr.OFTString)
    # field_name.SetWidth(24)
    # output_layer.CreateField(field_name)

    input_layer.SetAttributeFilter('HYBAS_ID = ' + attribute)

    for input_feature in input_layer:
        #print input_feature.GetField("HYBAS_ID")
        geometry = input_feature.GetGeometryRef()
        output_feature = ogr.Feature(input_layer.GetLayerDefn())
        # output_feature.SetField("ws_id", 'ws')

        output_feature.SetGeometry(geometry)
        output_layer.CreateFeature(output_feature)

        output_feature.Destroy()

    output_shp.Destroy()





if __name__ == "__main__":
    print 'WARNING! Running .py script locally.'
    #create_data()
    print 'Script finished.'