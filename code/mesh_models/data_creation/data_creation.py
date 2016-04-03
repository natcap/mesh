# coding=utf-8

import sys
import os
import logging
import shutil

from osgeo import ogr, osr
from matplotlib import rcParams

from mesh_utilities import config

rcParams.update({'figure.autolayout': True}) # This line makes matplotlib automatically change the fig size according to legends, labels etc.
LOGGER = config.LOGGER
LOGGER.setLevel(logging.INFO)
ENCODING = sys.getfilesystemencoding()


def clip_geotiff_from_base_data(input_shape_uri, base_data_uri, output_geotiff_uri):
    gdal_command = 'gdalwarp -cutline ' + input_shape_uri + ' -crop_to_cutline -overwrite -s_srs EPSG:4326 -t_srs EPSG:54030 -of GTiff ' + base_data_uri + ' ' + output_geotiff_uri
    os.system(gdal_command)


def copy_from_base_data(base_data_uri, output_uri):
    shutil.copyfile(base_data_uri, output_uri)


def save_shp_feature_by_attribute(shp_uri, attribute, output_shp_uri):
    input_shp = ogr.Open(shp_uri)
    input_layer = input_shp.GetLayer(0)
    driver = ogr.GetDriverByName('ESRI Shapefile')
    output_shp = driver.CreateDataSource(output_shp_uri)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    output_layer = output_shp.CreateLayer("selected_watershed", srs, ogr.wkbPolygon)
    input_layer.SetAttributeFilter('HYBAS_ID = ' + str(attribute))

    for input_feature in input_layer:
        geometry = input_feature.GetGeometryRef()
        output_feature = ogr.Feature(input_layer.GetLayerDefn())
        # output_feature.SetField("ws_id", 'ws')
        output_feature.SetGeometry(geometry)
        output_layer.CreateFeature(output_feature)
        output_feature.Destroy()
    output_shp.Destroy()
