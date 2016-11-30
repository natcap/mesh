if __name__=='__main__':
    import os

    os.chdir('../..')

#    import data_creation

    from mesh_models.data_creation import data_creation

    input_uri = 'C:\\OneDrive\\Projects\\mesh\\mesh_local\\projects\\12\\input\\Baseline\\aoi.shp'
    output_uri = 'C:\\OneDrive\\Projects\\mesh\\mesh_local\\projects\\12\\input\\Baseline\\aoi_r.shp'
    output_epsg_code = 54030
    data_creation.reproject_shapefile_by_epsg(input_uri, output_uri, output_epsg_code)
