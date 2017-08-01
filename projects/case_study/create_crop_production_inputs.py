# coding=utf-8

# ABANDONED. Decided to just extrapolate from calories because the logic there actually is identical to invest model.


import os
import gdal
import numpy as np
from osgeo import osr

# TODO REMOVE before importation into mesh
import numdal as nd

def convert_lulc_to_crop_management_scenario_raster(lulc_uri, output_uri):
    lulc_ds = gdal.Open(lulc_uri)
    lulc_band = lulc_ds.GetRasterBand(1)
    lulc_array = lulc_band.ReadAsArray()

    management_array = np.where((lulc_array == 12) | (lulc_array == 14), 2, 0) # 2 is corn

    gdal_format = 'GTiff'
    nodata = 255
    datatype = 1

    output_ds = nd.new_raster_from_base_uri(lulc_uri, output_uri, gdal_format, nodata, datatype)
    output_ds = None

    output_ds = gdal.Open(output_uri, gdal.GA_Update)

    output_band = output_ds.GetRasterBand(1)
    output_band.WriteArray(management_array)
    output_band.FlushCache()
    output_band = None

    nd.show(management_array)

def get_crop_mix_in_shapefile(input_shapefile_uri, global_dataset_dir):

    # START HERE, figure out how to auto-generate a crop-specific lulc.

    observed_yield_dir = os.path.join(global_dataset_dir, 'observed_yield')

    for crop_yield_filename in os.listdir(observed_yield_dir):
        crop_yield_uri = os.path.join(observed_yield_dir, crop_yield_filename)
        if crop_yield_uri.endswith('.tif'):

            print('crop_yield_uri', crop_yield_uri)

            temp_reprojected_uri = nd.temp('.tif', remove_at_exit=False)
            temp_clipped_uri = nd.temp('.tif', remove_at_exit=False)

            spatialRef = osr.SpatialReference()
            spatialRef.ImportFromEPSG(32663) # wec
            output_wkt = spatialRef.ExportToWkt()

            reprojected_shapefile_uri = input_shapefile_uri.replace('.shp', '_wec.shp')
            nd.reproject_dataset_uri(crop_yield_uri, 10000, output_wkt, 'nearest', temp_reprojected_uri)
            print(1)
            nd.reproject_datasource_uri(input_shapefile_uri, output_wkt, reprojected_shapefile_uri)
            print(2)
            nd.clip_dataset_uri(temp_reprojected_uri, reprojected_shapefile_uri, temp_clipped_uri)
            print(3)

            ds = gdal.Open(temp_clipped_uri)
            band = ds.GetRasterBand(1)
            array = band.ReadAsArray()

            array_sum = np.sum(array)
            print(crop_yield_uri, array_sum)





if __name__=='__main__':
    data_dir = 'C:/OneDrive/Projects/mesh/mesh_local/projects/v5/input/Baseline'

    global_dataset_dir = 'C:/OneDrive/Projects/mesh/mesh_local/base_data/models/crop_production/global_dataset'
    input_shapefile_uri = os.path.join(data_dir, 'aoi.shp')
    get_crop_mix_in_shapefile(input_shapefile_uri, global_dataset_dir)





    # lulc_uri = os.path.join(data_dir, 'lulc.tif')
    # output_uri = os.path.join(data_dir, 'crop_management.tif')
    # convert_lulc_to_crop_management_scenario_raster(lulc_uri, output_uri)