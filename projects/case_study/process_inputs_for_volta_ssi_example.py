status = 'OUTDATED. Move to mesh_local/case_study/create_volta_case_study_data.py'


import os

import gdal, osr
import numpy as np

import geoecon_utils.geoecon_utils as gu

ssi_folder = 'C:/Research/GeoEcon/projects/mesh/projects/volta_new/'
bulk_data_folder = 'E:/bulk_data/'
workspace_folder = ssi_folder
input_folder = workspace_folder + 'input/Baseline'
output_rolder = workspace_folder + 'input/Baseline'

bounding_box = (-5.35, 14.866667, 2.266667, 5.775) # This was chosen to match the waterworld definition of the volta AOI

lulc_source_uri = bulk_data_folder + 'modis/lulc/2012/lulc_modis_2012.tif'
lulc_wgs_uri = 'lulc_2012_wgs.tif'
# gu.clip_by_coords_with_gdal(lulc_source_uri, lulc_wgs_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3])
lulc_uri = 'lulc_2012.tif'
# gu.change_projection_with_gdal(lulc_wgs_uri, lulc_uri, 'Robinson')

precip_source_uri = ssi_folder + 'Base_Data/climatic/baseline_bio12_Annual_Precipitation.tif'
precip_wgs_uri = 'precip_wgs.tif'
precip_resampled_uri = 'precip_resampled.tif'
precip_uri = 'precip.tif'
gu.clip_by_coords_with_gdal(precip_source_uri, precip_wgs_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3], projection='WGS84')
#gu.resize_and_resample_dataset_uri(precip_wgs_uri, bounding_box, .004166666667, precip_resampled_uri, 'cubic_spline')
gu.change_projection_with_gdal(precip_resampled_uri, precip_uri, 'Robinson')

hydrosheds_folder = bulk_data_folder + 'hydrosheds/hydrologically_conditioned_dem/3s/'
dem_unclipped_uri = 'dem_unclipped.tif'
# gu.merge_hydrosheds_data_by_tile_ids(hydrosheds_folder, dem_unclipped_uri, 'w10', 'e00', 'n00', 'n10')
dem_wgs_uri = 'dem_wgs.tif'
# gu.clip_by_coords_with_gdal(dem_unclipped_uri, dem_wgs_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3])
dem_resampled_wgs_uri = 'dem_resampled_wgs.tif'
# gu.resize_and_resample_dataset_uri(dem_wgs_uri, bounding_box, .004166666667, dem_resampled_wgs_uri, 'cubic_spline', fill_no_data_value = None)
dem_uri = 'dem.tif'
# gu.change_projection_with_gdal(dem_resampled_wgs_uri, dem_uri, 'Robinson')
dem_array = gu.as_array(dem_uri)

depth_to_root_restricting_layer_source_uri = 'E:/bulk_data/soil/1kmsoilgrids/BDRICM_02_apr_2014.tif'
depth_to_root_restricting_layer_wgs_uri = 'depth_to_root_restricting_layer_wgs.tif'
# gu.clip_by_coords_with_gdal(depth_to_root_restricting_layer_source_uri, depth_to_root_restricting_layer_wgs_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3])
depth_to_root_restricting_layer_uri = 'depth_to_root_restricting_layer.tif'
# gu.change_projection_with_gdal(depth_to_root_restricting_layer_wgs_uri, depth_to_root_restricting_layer_uri, 'Robinson')

reference_evapotranspiration_source_uri = 'E:/bulk_data/modis/MOD16A3_ET_2000_to_2013_mean.tif'
reference_evapotranspiration_wgs_uri = 'reference_evapotranspiration_wgs.tif'
# gu.clip_by_coords_with_gdal(reference_evapotranspiration_source_uri, reference_evapotranspiration_wgs_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3])
reference_evapotranspiration_uri = 'reference_evapotranspiration.tif'
# gu.change_projection_with_gdal(reference_evapotranspiration_wgs_uri, reference_evapotranspiration_uri, 'Robinson')

sand_percent_source_uri = 'E:/bulk_data/soil/1kmsoilgrids/SNDPPT_sd6_M_02_apr_2014.tif'
sand_percent_wgs_uri = 'sand_percent_wgs.tif'
# gu.clip_by_coords_with_gdal(sand_percent_source_uri, sand_percent_wgs_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3])
sand_percent_uri = 'sand_percent.tif'
# gu.change_projection_with_gdal(sand_percent_wgs_uri, sand_percent_uri, 'Robinson')
#sand_percent_array = gu.as_array(sand_percent_uri)

clay_percent_source_uri = 'E:/bulk_data/soil/1kmsoilgrids/CLYPPT_sd6_M_02_apr_2014.tif'
clay_percent_wgs_uri = 'clay_percent_wgs.tif'
# gu.clip_by_coords_with_gdal(clay_percent_source_uri, clay_percent_wgs_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3])
clay_percent_uri = 'clay_percent.tif'
# gu.change_projection_with_gdal(clay_percent_wgs_uri, clay_percent_uri,'Robinson')
#clay_percent_array = gu.as_array(clay_percent_uri)

pawc_uri = 'pawc.tif'
organic_matter_source_uri = 'E:/bulk_data/soil/1kmsoilgrids/ORCDRC_sd6_M_02_apr_2014.tif'
organic_matter_wgs_uri = 'organic_matter_wgs.tif'
organic_matter_uri = 'organic_matter.tif'
gu.clip_by_coords_with_gdal(organic_matter_source_uri, organic_matter_wgs_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3])
gu.change_projection_with_gdal(organic_matter_wgs_uri, organic_matter_uri, 'Robinson')
organic_matter_proportion_array = gu.as_array(organic_matter_uri).astype(np.float32) * 0.001 #conversion from permilles to proportion
#clay_proportion_array = clay_percent_array.astype(np.float32) * 0.01
#sand_proportion_array = sand_percent_array.astype(np.float32) * 0.01

#pawc = gu.calc_plant_available_water_content_from_texture(clay_proportion_array, sand_proportion_array, organic_matter_proportion_array)
#pawc = np.where(clay_percent_array == 255, 255, pawc)
#gu.save_array_as_geotiff(pawc, pawc_uri, 'clay_percent.tif')
#pawc_wgs_uri = 'pawc_wgs.tif'
#gu.change_projection_with_gdal(pawc_uri, pawc_wgs_uri, 'WGS84')

rivers_source_uri = 'E:/bulk_data/hydrosheds/rivers/af_riv_15s/af_riv_15s.shp'
#rivers_wgs_uri = input_folder + 'rivers_wgs.shp'
rivers_clipped_uri = input_folder + 'rivers_clipped.shp'
rivers_shape_uri = input_folder + 'rivers.shp'


# print "Clipping rivers shp file. May take a while."
# gu.clip_shapefile(rivers_source_uri, rivers_clipped_uri, bounding_box)
# gu.reproject_shp_file(rivers_clipped_uri, rivers_shape_uri, 'Robinson')
rivers_unprojected_tif_uri = 'rivers_unprojected.tif'
#gu.rasterize_shape_file_with_fixed_burn_value(rivers_shape_uri, rivers_unprojected_tif_uri, dem_uri)
# gu.convert_polygons_to_id_raster(rivers_shape_uri, 'UP_CELLS', rivers_unprojected_tif_uri, dem_uri, iterative_list=[100000, 70000, 50000, 40000, 30000, 25000, 22000, 20000, 18000, 16000, 13000, 12000, 11000, 10000, 9000, 8000, 7000, 6000, 5000, 4000, 3500, 3000, 2500, 2000, 1500, 1200, 800, 600, 400, 200, 100])
rivers_wgs_uri = 'rivers_wgs.tif'
# gu.change_projection_with_gdal(rivers_unprojected_tif_uri, rivers_wgs_uri, 'WGS84')
#rivers_uri = 'rivers.tif'
# gu.change_projection_with_gdal(rivers_unprojected_tif_uri, rivers_uri, 'Robinson')
#rivers_array = gu.as_array(rivers_uri)
# gu.resize_and_resample_dataset_uri(dem_wgs_uri, bounding_box, .004166666667, dem_resampled_wgs_uri, 'cubic_spline', fill_no_data_value = None)

watersheds_wgs_uri = input_folder + 'GVP_hydrology_catchment_volta-basin_2010_pol.shp' #To Do, this is still one manual thing insofar as I had to add the ws_id field.
watersheds_uri = input_folder + 'watersheds_robinson.shp'
##DONT withotu modifying ws_id gu.reproject_shp_file(watersheds_wgs_uri, watersheds_uri, 'Robinson')
watersheds_raster_unprojected_uri = 'watersheds_raster_unprojected.tif'
#gu.convert_polygons_to_id_raster(watersheds_uri, 'ws_id', watersheds_raster_unprojected_uri, dem_uri)
watersheds_raster_uri = 'watersheds.tif'
# gu.change_projection_with_gdal(subwatersheds_raster_unprojected_uri, subwatersheds_raster_uri, 'Robinson')
#watersheds_array = gu.as_array(watersheds_raster_uri)

subwatersheds_wgs_uri = input_folder + 'subwatersheds.shp' #To Do, this is still one manual thing insofar as I had to add the ws_id field.
subwatersheds_uri = input_folder + 'subwatersheds_robinson.shp'
# gu.reproject_shp_file(subwatersheds_wgs_uri, subwatersheds_uri, 'Robinson')
subwatersheds_raster_unprojected_uri = 'subwatersheds_raster_unprojected.tif'
# gu.convert_polygons_to_id_raster(subwatersheds_uri, 'ws_id', subwatersheds_raster_unprojected_uri, dem_uri)
subwatersheds_raster_uri = 'subwatersheds.tif'
# gu.change_projection_with_gdal(subwatersheds_raster_unprojected_uri, subwatersheds_raster_uri, 'Robinson')
subwatersheds_array = gu.as_array(subwatersheds_raster_uri)

coastline_40km_buffer_uri = ssi_folder + 'Base_Data/physical/coastline_40km_buffer.shp'
#coastline_40km_buffer_unprojected_geotiff_uri = 'coastline_40km_buffer_unprojected.tif'
coastline_40km_buffer_geotiff_resampled_uri = 'coastline_40km_buffer_resampled.tif'
coastline_40km_buffer_geotiff_uri = 'coastline_40km_buffer.tif'
#gu.rasterize_shape_file_with_fixed_burn_value(coastline_40km_buffer_uri, coastline_40km_buffer_unprojected_geotiff_uri, dem_uri)
#gu.resize_and_resample_dataset_uri(coastline_40km_buffer_unprojected_geotiff_uri, bounding_box, .004166666667, coastline_40km_buffer_geotiff_resampled_uri, 'cubic_spline')#.004166666667, 423.8385698
#gu.change_projection_with_gdal(coastline_40km_buffer_unprojected_geotiff_uri, coastline_40km_buffer_geotiff_uri, 'Robinson')


#rainfall_erosivity_index_uri = 'rainfall_erosivity_index.tif'
#rainfall_erosivity_index_array = gu.calc_rainfall_erosivity(precip_uri, coastline_40km_buffer_geotiff_uri, dem_uri, mountain_threshold = 600)
#gu.save_array_as_geotiff(rainfall_erosivity_index_array, rainfall_erosivity_index_uri, dem_uri)

#soil_erodibility_uri = 'soil_erodibility.tif'
#soil_erodibility_array = gu.calc_soil_erodability(clay_proportion_array, sand_proportion_array)
#gu.save_array_as_geotiff(soil_erodibility_array, soil_erodibility_uri, clay_percent_uri)

dem_burned_uri  = 'dem_burned.tif'
#dem_burned = np.where(rivers_array!=0, -1 * rivers_array, dem_array)
#row_ids, col_ids = gu.create_row_col_identity_matrices(dem_burned)
# Set non watershed areas at a higher elevation to ensure draining inwards
#dem_burned = np.where(subwatersheds_array==0, 99999, dem_burned)
#dem_burned = np.where(row_ids>= 2292, -201.0, dem_burned)
# gu.save_array_as_geotiff(dem_burned, dem_burned_uri, dem_uri)

print(os.path.join(input_folder, 'lulc_2012.tif'))
lulc_input_array = gu.as_array(os.path.join(input_folder, 'lulc_2012.tif'))
crop_lulc_array = np.where(lulc_input_array == 90, 90, 47) #Corresponds to maize and cotton. A defect of the invest crop production model is that it does not work with a lulc that has any classes not defined in the crops lookup table. Thus, i set it to cotton as a temporary fix where i don't want calories produced
gu.save_array_as_geotiff(crop_lulc_array, os.path.join(input_folder, 'crop_lulc_2012.tif'), os.path.join(input_folder, 'lulc_2012.tif'))

print("\n\nScript finished")





