import numdal as nd
import numpy as np
from collections import OrderedDict
import os

def execute(input_aoi_uri):
    carbon_dir = 'C:/OneDrive/base_data/carbon/johnson'
    carbon_above_ground_mg_per_ha_uri = os.path.join(carbon_dir, 'carbon_above_ground_mg_per_ha_global_30s.tif')
    carbon_above_ground_mg_per_ha = nd.ArrayFrame(carbon_above_ground_mg_per_ha_uri)
    # 3.9 bil print(carbon_above_ground_mg_per_ha.sum())

    temp_dir = nd.make_temp_run_folder()

    carbon_clipped_uri = os.path.join(temp_dir, 'c_clipped.tif')
    nd.clip_raster_by_shp(carbon_above_ground_mg_per_ha_uri, carbon_clipped_uri, input_aoi_uri)
    carbon_clipped = nd.ArrayFrame(carbon_clipped_uri)

    # lulc_uri = os.path.join(temp_dir, 'lulc.tif')
    lulc_uri = nd.temp('lulc.tif')
    global_lulc_uri = 'C:/OneDrive/base_data/lulc/lulc_modis_2012.tif'
    nd.clip_raster_by_shp(global_lulc_uri, lulc_uri, input_aoi_uri)
    lulc = nd.ArrayFrame(lulc_uri)

    classes_in_lulc = np.unique(lulc.data)

    carbon_reprojected_uri = os.path.join(temp_dir, 'reprojected.tif')
    carbon_clipped.reproject(lulc, output_uri=carbon_reprojected_uri)
    carbon_reprojected = nd.ArrayFrame(carbon_reprojected_uri)

    carbon_resampled_uri = os.path.join(temp_dir, 'resampled.tif')
    carbon_reprojected.resample(lulc, output_uri=carbon_resampled_uri)
    carbon_resampled_af = nd.ArrayFrame(carbon_resampled_uri)
    carbon_resampled_af.show(vmin=0, vmax=200)


    mean_values = OrderedDict()
    counts = OrderedDict()
    n_total_nonzero = np.count_nonzero(carbon_resampled_af.data)
    for class_id in classes_in_lulc:
        print('Calculating mean observed C for class ' + str(class_id))

        a = np.where(lulc.data == class_id, carbon_resampled_af.data, 0)
        a = np.where(a == carbon_resampled_af.no_data_value, 0, a)
        dem = np.count_nonzero(a)
        counts[class_id] = dem
        if dem:
            mean_values[class_id] = np.sum(a) / dem
        else:
            mean_values[class_id] = 0

    nd.pp(mean_values)



if __name__=='__main__':
    # volta_data_dir = 'input/Baseline'
    # volta_aoi_uri = os.path.join(volta_data_dir, 'aoi.shp')

    shapefile_uri = 'C:/OneDrive/base_data/hydrosheds/hydrobasins/hybas_af_lev01-06_v1c/hybas_af_lev01_v1c.shp'
    execute(shapefile_uri)


    all_africa_results = {
    '0': 10.1513469932,
    '1': 14.479150305,
    '2': 137.75817422,
    '3': 43.9465623508,
    '4': 11.4986335898,
    '5': 23.7233030412,
    '6': 3.37902456091,
    '7': 1.94970472987,
    '8': 14.8213165799,
    '9': 3.89288635591,
    '10': 2.04545457679,
    '11': 33.4550539629,
    '12': 2.31596429333,
    '13': 3.07908741801,
    '14': 4.62437497685,
    '15': 25.7101741846,
    '16': 0.69757897969,
    '255': 10.4296000466,
         }