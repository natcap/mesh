import os, sys
import numdal as nd
import geoecon as ge

def execute(destination_dir=None):
    # a = C:\OneDrive\base_data\naturalearth
    # nd.extract_features_in_shapefile_by_attribute(countries_uri, honduras_uri, 'ISO3=')

    if not destination_dir:
        destination_dir = nd.make_temp_run_folder()
    aoi_uri = 'C:/OneDrive/Projects/mesh/mesh_local/projects/Honduras03/input/Baseline/PASOS_boundary_robinson.shp'

    output_uri = os.path.join(destination_dir, 'dem.tif')
    if not os.path.exists(output_uri):
        ge.clip_hydrosheds_dem_from_aoi(output_uri, aoi_uri)

    base_data_dir = nd.config.BASE_DATA_DIR

    base_data_uri = os.path.join(base_data_dir, 'soil', 'erosivity_30s.tif')
    output_geotiff_uri = os.path.join(destination_dir, 'erosivity.tif')
    if not os.path.exists(output_geotiff_uri):
        nd.clip_geotiff_from_base_data(aoi_uri, base_data_uri, output_geotiff_uri, base_data_dir)


    base_data_uri = os.path.join(base_data_dir, 'soil', 'erodibility_30s.tif')
    output_geotiff_uri = os.path.join(destination_dir, 'erodibility.tif')
    if not os.path.exists(output_geotiff_uri):
        nd.clip_geotiff_from_base_data(aoi_uri, base_data_uri, output_geotiff_uri, base_data_dir)





if __name__=='__main__':
    # destination_dir = 'C:/OneDrive/Projects/mesh/mesh_local/projects/Honduras03/input/Baseline'
    destination_dir = None
    execute(destination_dir)