# coding=utf-8

import sys
import os
import logging
import shutil
from collections import OrderedDict
import datetime
import random
import tempfile
import atexit
import time
import functools
import errno
import math

import numpy
import numpy as np
from osgeo import ogr, osr, gdal
from matplotlib import rcParams

from mesh_utilities import config
from mesh_utilities import utilities

rcParams.update({'figure.autolayout': True}) # This line makes matplotlib automatically change the fig size according to legends, labels etc.
LOGGER = config.LOGGER
LOGGER.setLevel(logging.INFO)
ENCODING = sys.getfilesystemencoding()


def clip_geotiff_from_base_data_gdal(input_shape_uri, base_data_uri, output_geotiff_uri):
    # Deprecated and removed via rename because it meant the user had to have gdal installed.
    gdal_command = 'gdalwarp -cutline ' + input_shape_uri + ' -crop_to_cutline -overwrite -s_srs EPSG:4326 -t_srs EPSG:54030 -of GTiff ' + base_data_uri + ' ' + output_geotiff_uri
    os.system(gdal_command)

def clip_geotiff_from_base_data(input_shape_uri, base_data_uri, output_geotiff_uri, base_data_dir):
    # Start by getting reproject shape out of command line.
    default_dataset_uri = os.path.join(base_data_dir, 'models', 'default', 'default_raster.tif')

    wgs84_wkt = get_dataset_projection_wkt_uri(base_data_uri)
    input_shape_wgs84_uri = input_shape_uri.replace('.shp', '_wgs84.shp')
    reproject_datasource_uri(input_shape_uri, wgs84_wkt, input_shape_wgs84_uri)

    temp_1_uri = temporary_filename('.tif')

    clip_dataset_uri(base_data_uri, input_shape_wgs84_uri, temp_1_uri,
                     assert_projections=False, process_pool=None, all_touched=False)

    pixel_spacing = get_cell_size_from_uri(default_dataset_uri)


    output_wkt = get_dataset_projection_wkt_uri(default_dataset_uri)
    resampling_method = 'nearest'




    reproject_dataset_uri(temp_1_uri, pixel_spacing, output_wkt, resampling_method, output_geotiff_uri)

    # resize_and_resample_dataset_uri(
    #     original_dataset_uri, bounding_box, out_pixel_size, output_uri,
    #     resample_method)

def get_dataset_projection_wkt_uri(dataset_uri):
    """Get the projection of a GDAL dataset as well known text (WKT).

    Args:
        dataset_uri (string): a URI for the GDAL dataset

    Returns:
        proj_wkt (string): WKT describing the GDAL dataset project
    """
    dataset = gdal.Open(dataset_uri)
    proj_wkt = dataset.GetProjection()
    gdal.Dataset.__swig_destroy__(dataset)
    dataset = None
    return proj_wkt



def clip_dataset_uri(
        source_dataset_uri, aoi_datasource_uri, out_dataset_uri,
        assert_projections=True, process_pool=None, all_touched=False):
    """Clip raster dataset to bounding box of provided vector datasource aoi.

    This function will clip source_dataset to the bounding box of the
    polygons in aoi_datasource and mask out the values in source_dataset
    outside of the AOI with the nodata values in source_dataset.

    Args:
        source_dataset_uri (string): uri to single band GDAL dataset to clip
        aoi_datasource_uri (string): uri to ogr datasource
        out_dataset_uri (string): path to disk for the clipped datset

    Keyword Args:
        assert_projections (boolean): a boolean value for whether the dataset
            needs to be projected
        process_pool: a process pool for multiprocessing
        all_touched (boolean): if true the clip uses the option ALL_TOUCHED=TRUE
            when calling RasterizeLayer for AOI masking.

    Returns:
        None
    """
    source_dataset = gdal.Open(source_dataset_uri)

    band = source_dataset.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    datatype = band.DataType

    if nodata is None:
        nodata = -9999

    gdal.Dataset.__swig_destroy__(source_dataset)
    source_dataset = None

    pixel_size = get_cell_size_from_uri(source_dataset_uri)
    vectorize_datasets(
        [source_dataset_uri], lambda x: x, out_dataset_uri, datatype, nodata,
        pixel_size, 'intersection', aoi_uri=aoi_datasource_uri,
        assert_datasets_projected=assert_projections,
        process_pool=process_pool, vectorize_op=False, all_touched=all_touched)



def reproject_dataset_uri(
        original_dataset_uri, pixel_spacing, output_wkt, resampling_method,
        output_uri):
    """Reproject and resample GDAL dataset.

    A function to reproject and resample a GDAL dataset given an output
    pixel size and output reference. Will use the datatype and nodata value
    from the original dataset.

    Args:
        original_dataset_uri (string): a URI to a gdal Dataset to written to
            disk
        pixel_spacing: output dataset pixel size in projected linear units
        output_wkt: output project in Well Known Text
        resampling_method (string): a string representing the one of the
            following resampling methods:
            "nearest|bilinear|cubic|cubic_spline|lanczos"
        output_uri (string): location on disk to dump the reprojected dataset

    Returns:
        None
    """
    # A dictionary to map the resampling method input string to the gdal type
    resample_dict = {
        "near": gdal.GRA_NearestNeighbour,
        "nearest_neighbor": gdal.GRA_NearestNeighbour,
        "nearest": gdal.GRA_NearestNeighbour,
        "bilinear": gdal.GRA_Bilinear,
        "cubic": gdal.GRA_Cubic,
        "cubic_spline": gdal.GRA_CubicSpline,
        "lanczos": gdal.GRA_Lanczos
    }

    # Get the nodata value and datatype from the original dataset
    output_type = get_datatype_from_uri(original_dataset_uri)
    out_nodata = get_nodata_from_uri(original_dataset_uri)

    original_dataset = gdal.Open(original_dataset_uri)

    original_wkt = original_dataset.GetProjection()

    # Create a virtual raster that is projected based on the output WKT. This
    # vrt does not save to disk and is used to get the proper projected
    # bounding box and size.
    vrt = gdal.AutoCreateWarpedVRT(
        original_dataset, None, output_wkt, gdal.GRA_Bilinear)

    geo_t = vrt.GetGeoTransform()
    x_size = vrt.RasterXSize  # Raster xsize
    y_size = vrt.RasterYSize  # Raster ysize

    # Calculate the extents of the projected dataset. These values will be used
    # to properly set the resampled size for the output dataset
    (ulx, uly) = (geo_t[0], geo_t[3])
    (lrx, lry) = (geo_t[0] + geo_t[1] * x_size, geo_t[3] + geo_t[5] * y_size)

    gdal_driver = gdal.GetDriverByName('GTiff')

    # Create the output dataset to receive the projected output, with the
    # proper resampled arrangement.
    output_dataset = gdal_driver.Create(
        output_uri, int((lrx - ulx)/pixel_spacing),
        int((uly - lry)/pixel_spacing), 1, output_type,
        options=['BIGTIFF=IF_SAFER'])

    # Set the nodata value for the output dataset
    output_dataset.GetRasterBand(1).SetNoDataValue(float(out_nodata))

    # Calculate the new geotransform
    output_geo = (ulx, pixel_spacing, geo_t[2], uly, geo_t[4], -pixel_spacing)

    # Set the geotransform
    output_dataset.SetGeoTransform(output_geo)
    output_dataset.SetProjection(output_wkt)

    # Perform the projection/resampling
    def reproject_callback(df_complete, psz_message, p_progress_arg):
        """The argument names come from the GDAL API for callbacks."""
        try:
            current_time = time.time()
            if ((current_time - reproject_callback.last_time) > 5.0 or
                    (df_complete == 1.0 and reproject_callback.total_time >= 5.0)):
                LOGGER.info(
                    "ReprojectImage %.1f%% complete %s, psz_message %s",
                    df_complete * 100, p_progress_arg[0], psz_message)
                reproject_callback.last_time = current_time
                reproject_callback.total_time += current_time
        except AttributeError:
            reproject_callback.last_time = time.time()
            reproject_callback.total_time = 0.0

    gdal.ReprojectImage(
        original_dataset, output_dataset, original_wkt, output_wkt,
        resample_dict[resampling_method], 0, 0, reproject_callback,
        [output_uri])

    output_dataset.FlushCache()

    #Make sure the dataset is closed and cleaned up
    gdal.Dataset.__swig_destroy__(output_dataset)
    output_dataset = None
    calculate_raster_stats_uri(output_uri)




def resize_and_resample_dataset_uri(
        original_dataset_uri, bounding_box, out_pixel_size, output_uri,
        resample_method):

    'This was a custom but very useful extension of pgp. However, i need to make it just WRAP the pgp version rather than duplicate code.'

    """Resize and resample the given dataset.

    Args:
        original_dataset_uri (string): a GDAL dataset
        bounding_box (list): [upper_left_x, upper_left_y, lower_right_x,
            lower_right_y]
        out_pixel_size: the pixel size in projected linear units
        output_uri (string): the location of the new resampled GDAL dataset
        resample_method (string): the resampling technique, one of
            "nearest|bilinear|cubic|cubic_spline|lanczos"

    Returns:
        None
    """
    resample_dict = {
        "nearest": gdal.GRA_NearestNeighbour,
        "near": gdal.GRA_NearestNeighbour,
        "bilinear": gdal.GRA_Bilinear,
        "cubic": gdal.GRA_Cubic,
        "cubicspline": gdal.GRA_CubicSpline,
        "lanczos": gdal.GRA_Lanczos,
        "average": gdal.GRA_Average
    }

    original_dataset = gdal.Open(original_dataset_uri)
    original_band = original_dataset.GetRasterBand(1)
    original_nodata = original_band.GetNoDataValue()

    if original_nodata is None:
        original_nodata = -9999

    original_sr = osr.SpatialReference()
    original_sr.ImportFromWkt(original_dataset.GetProjection())

    output_geo_transform = [
        bounding_box[0], out_pixel_size, 0.0, bounding_box[1], 0.0,
        -out_pixel_size]
    new_x_size = abs(
        int(numpy.round((bounding_box[2] - bounding_box[0]) / out_pixel_size)))
    new_y_size = abs(
        int(numpy.round((bounding_box[3] - bounding_box[1]) / out_pixel_size)))

    if new_x_size == 0:
        LOGGER.warn(
            "bounding_box is so small that x dimension rounds to 0; "
            "clamping to 1.")
        new_x_size = 1
    if new_y_size == 0:
        LOGGER.warn(
            "bounding_box is so small that y dimension rounds to 0; "
            "clamping to 1.")
        new_y_size = 1

    # create the new x and y size
    block_size = original_band.GetBlockSize()
    # If the original band is tiled, then its x blocksize will be different
    # than the number of columns
    if original_band.XSize > 256 and original_band.YSize > 256:
        # it makes sense for many functions to have 256x256 blocks
        block_size[0] = 256
        block_size[1] = 256
        gtiff_creation_options = [
            'TILED=YES', 'BIGTIFF=IF_SAFER', 'BLOCKXSIZE=%d' % block_size[0],
                                             'BLOCKYSIZE=%d' % block_size[1]]

        metadata = original_band.GetMetadata('IMAGE_STRUCTURE')
        if 'PIXELTYPE' in metadata:
            gtiff_creation_options.append('PIXELTYPE=' + metadata['PIXELTYPE'])
    else:
        # it is so small or strangely aligned, use the default creation options
        gtiff_creation_options = []

    create_directories([os.path.dirname(output_uri)])
    gdal_driver = gdal.GetDriverByName('GTiff')
    output_dataset = gdal_driver.Create(
        output_uri, new_x_size, new_y_size, 1, original_band.DataType,
        options=gtiff_creation_options)
    output_band = output_dataset.GetRasterBand(1)

    output_band.SetNoDataValue(original_nodata)

    # Set the geotransform
    output_dataset.SetGeoTransform(output_geo_transform)
    output_dataset.SetProjection(original_sr.ExportToWkt())

    # need to make this a closure so we get the current time and we can affect
    # state
    def reproject_callback(df_complete, psz_message, p_progress_arg):
        """The argument names come from the GDAL API for callbacks."""
        try:
            current_time = time.time()
            if ((current_time - reproject_callback.last_time) > 1.0 or
                    (df_complete == 1.0 and reproject_callback.total_time >= 5.0)):
                # LOGGER.info(
                #     "ReprojectImage %.1f%% complete %s, psz_message %s",
                #     df_complete * 100, p_progress_arg[0], psz_message)
                # reproject_callback.last_time = current_time
                # reproject_callback.total_time += current_time

                LOGGER.info("ReprojectImage " + str(df_complete * 100) + "% complete. " + str(p_progress_arg[0]) + " " + str(
                    psz_message))

        except AttributeError:
            reproject_callback.last_time = time.time()
            reproject_callback.total_time = 0.0

    # Perform the projection/resampling
    gdal.ReprojectImage(
        original_dataset, output_dataset, original_sr.ExportToWkt(),
        original_sr.ExportToWkt(), resample_dict[resample_method], 0, 0,
        reproject_callback, [output_uri])

    # Make sure the dataset is closed and cleaned up
    original_band = None
    gdal.Dataset.__swig_destroy__(original_dataset)
    original_dataset = None

    output_dataset.FlushCache()
    gdal.Dataset.__swig_destroy__(output_dataset)
    output_dataset = None
    calculate_raster_stats_uri(output_uri)



def get_cell_size_from_uri(dataset_uri):
    """Get the cell size of a dataset in units of meters.

    Raises an exception if the raster is not square since this'll break most of
    the pygeoprocessing algorithms.

    Args:
        dataset_uri (string): uri to a gdal dataset

    Returns:
        size_meters: cell size of the dataset in meters
    """

    srs = osr.SpatialReference()
    dataset = gdal.Open(dataset_uri)
    if dataset is None:
        raise IOError(
            'File not found or not valid dataset type at: %s' % dataset_uri)
    srs.SetProjection(dataset.GetProjection())
    linear_units = srs.GetLinearUnits()
    geotransform = dataset.GetGeoTransform()
    # take absolute value since sometimes negative widths/heights
    try:
        numpy.testing.assert_approx_equal(
            abs(geotransform[1]), abs(geotransform[5]))
        size_meters = abs(geotransform[1]) * linear_units
    except AssertionError as e:
        LOGGER.warn(e)
        size_meters = (
                          abs(geotransform[1]) + abs(geotransform[5])) / 2.0 * linear_units

    # Close and clean up dataset
    gdal.Dataset.__swig_destroy__(dataset)
    dataset = None

    return size_meters





def pretty_time(format=None):
    # Returns a nicely formated string of YEAR-MONTH-DAY_HOURS-MIN-SECONDS based on the the linux timestamp
    now = str(datetime.datetime.now())
    day, time = now.split(' ')
    day = day.replace('-', '')
    time = time.replace(':', '')
    if '.' in time:
        time, milliseconds = time.split('.')
        milliseconds = milliseconds[0:3]
    else:
        milliseconds = '000'

    if not format:
        return day + '_' + time
    elif format == 'full':
        return day + '_' + time + '_' + milliseconds
    elif format == 'day':
        return day


def copy_from_base_data(base_data_uri, output_uri):
    shutil.copyfile(base_data_uri, output_uri)


def reproject_shapefile_by_epsg(input_uri, output_uri, output_epsg_code):
    # print('redo without commandline')
    # command = 'ogr2ogr'
    # command += ' ' + output_uri + ' ' + input_uri
    # command += ' -t_srs EPSG:' + str(output_epsg_code)
    # os.system(command)

    output_epsg_code = int(float(output_epsg_code))

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(output_epsg_code)
    output_wkt = srs.ExportToWkt()

    reproject_datasource_uri(input_uri, output_wkt, output_uri)

# def reproject_shapefile_by_wkt(input_uri, output_uri, output_wkt):
#     reproject_datasource_uri(input_uri, output_wkt, )

def save_shp_feature_by_attribute(shp_uri, attribute, output_shp_uri):
    input_shp = ogr.Open(shp_uri)
    input_layer = input_shp.GetLayer(0)
    driver = ogr.GetDriverByName('ESRI Shapefile')

    intermediate1_uri = os.path.splitext(output_shp_uri)[0] + 't1' + os.path.splitext(output_shp_uri)[1]

    intermediate_shp = driver.CreateDataSource(intermediate1_uri)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    intermediate_layer = intermediate_shp.CreateLayer("selected_watershed", srs, ogr.wkbPolygon)
    input_layer.SetAttributeFilter('HYBAS_ID = ' + str(attribute))

    for input_feature in input_layer:
        geometry = input_feature.GetGeometryRef()
        intermediate_feature = ogr.Feature(input_layer.GetLayerDefn())

        # InVEST requires a ws_id for this, even though it's not used for the signe polygon watershed.

        intermediate_feature.SetGeometry(geometry)
        intermediate_layer.CreateFeature(intermediate_feature)
        #intermediate_feature.SetField("ws_id", "1")
        intermediate_feature.Destroy()
    intermediate_shp.Destroy()
    output_epsg_code = 54030

    intermediate2_uri = os.path.splitext(output_shp_uri)[0] + 't2' + os.path.splitext(output_shp_uri)[1]
    reproject_shapefile_by_epsg(intermediate1_uri, intermediate2_uri, output_epsg_code)


    # :param columns: 2-dim dictionary where the first level keys are the feature ids and the second level are the field ids.
    # {0:{colheader1:value1, colheader2: value2}, 1:{colheader1:value1, colheader2: value2}}


    columns = {0: {'ws_id': 1}}

    append_columns_to_shp_attributes_table(intermediate2_uri, columns, output_shp_uri)

def random_numerals_string(length=6):
    max_value = int(''.join(['9'] * length))
    to_return = str(random.randint(0, max_value)).zfill(length)
    return to_return

def append_columns_to_shp_attributes_table(input_shp_uri, columns, output_uri=None, **kwargs):
    """
    Append column(s) to input_shp_uri.

    ASSUMES POSITION IMPLIES HOW TO JOIN!!!

    If provided, will save to output_uri, otherwise will update input_shp_uri.
    Assumes that the shape of the columns dict concords to the attribute table (implicitly joining on ID).

    :param input_shp_uri: Uri to shapefile.
    :param columns: 2-dim dictionary where the first level keys are the feature ids and the second level are the field ids.

    {0:{colheader1:value1, colheader2: value2}, 1:{colheader1:value1, colheader2: value2}}


    :param output_uri: optional place to save
    :return: uri to file that was modified or saved.
    """

    # Setting this environment variable solves many encoding problems for special characters.
    os.environ['SHAPE_ENCODING'] = "utf-8"

    verbose = kwargs.get('verbose', False)

    # Determine what type of columns data have been given and cast to dict_2d
    if type(columns) is list and type(columns[0]) in [str, int, float]:
        input_type = 'list_1d'
        processed_columns = {0:{}}
        for key, value in enumerate(columns):
            processed_columns[0][key] = value
    elif type(columns) is list and type(columns[0]) is list:
        input_type =  'list_2d'
        processed_columns = {}
        for key, value in enumerate(columns):
            processed_columns[key] = {}
            for key2, value2 in enumerate(columns):
                processed_columns[key][key2] = value2
    elif (type(columns) is dict and type(columns[0]) is dict) or (type(columns) is OrderedDict and type(columns[0]) is OrderedDict):
        input_type = 'dict_2d'
        processed_columns = columns
    else:
        raise Exception('Unable to interpret columns datatype.')

    # Open input shp
    input_shp = ogr.Open(input_shp_uri)
    input_layer = input_shp.GetLayer(0)
    input_layer_def = input_layer.GetLayerDefn()
    input_feature_count = input_layer.GetFeatureCount()
    input_field_count = input_layer_def.GetFieldCount()

    # Alert user then columns is not the expected size.
    num_rows = len(columns)

    if num_rows < input_feature_count:
        config.LOGGER.warn('Number of rows in given columns is less than the shp file attribute table. Proceeding, but will have empty cells.')
    if num_rows > input_feature_count:
        config.LOGGER.warn('Number of rows in given columns is greater than the shp file attribute table. Proceeding, but will ignore overrun cells..')

    # Create temporary shp to write results. If outpur_uri is given, this is actually the final uri, not temp.
    if output_uri:
        temp_uri = output_uri
    else:
        temp_uri = ruri(input_shp_uri)

    driver = ogr.GetDriverByName('ESRI Shapefile')
    temp_shp = driver.CreateDataSource(temp_uri)
    temp_name = quad_split_path(input_shp_uri)[2]
    srs = input_layer.GetSpatialRef() # Assumes srs is the same as input.
    temp_layer = temp_shp.CreateLayer(temp_name, srs, ogr.wkbPolygon)

    # Create existing attribute field columns
    field_names_in_use = []
    for field_index in range(input_field_count):
        input_field_def = input_layer_def.GetFieldDefn(field_index)
        input_field_name = input_field_def.GetName()
        field_names_in_use.append(input_field_name)

        # Use the input field def to define the temp_field using OGR
        temp_field = ogr.FieldDefn(input_field_name, input_field_def.GetType())


        #threw errors if new number was too big. temp_field_width = input_field_def.GetWidth()
        # TODO Do programatic way of doing this.
        temp_field_width = 128
        precision = input_field_def.GetPrecision()

        temp_field.SetWidth(temp_field_width)
        temp_field.SetPrecision(precision)
        temp_layer.CreateField(temp_field)

    # Create new attribute field columns
    # First, Iterate through an arbitrary entry in the dictionary to get headings
    old_column_names = []
    new_column_names = []
    for column_name, column_value in processed_columns[list(processed_columns.keys())[0]].items():
        # Determine what type of field in the DBF file should be used base on the col's first entry
        if type(column_value) is int:
            dbf_field_type = config.type_string_to_ogr_field_type['int']
        elif type(column_value) is float:
            dbf_field_type = config.type_string_to_ogr_field_type['float']
        elif type(column_value) is str:
            dbf_field_type = config.type_string_to_ogr_field_type['string']
        else:
            print ('Encountered column type of ' + str(column_value) + '. Assuming you want float.')
            dbf_field_type = config.type_string_to_ogr_field_type['float']

        # Ensure that name is less than 10 characters (per stupid dbf requirements).
        if len(column_name) > 10:
            old_column_names.append(column_name)
            column_name = column_name[0:5] + random_numerals_string(5)
            new_column_names.append(column_name)
            config.LOGGER.warn('Field name longer than 10 given. Changing it to ' + column_name)  # Meh on hash collision.

        #Check to see if name has already been used.
        elif column_name in field_names_in_use:
            old_column_names.append(column_name)
            column_name = column_name.ljust(10,'0')
            column_name = column_name[0:5] + random_numerals_string(5)
            new_column_names.append(column_name)
            config.LOGGER.warn('Duplicate field name provided. Changing it to ' + column_name) #Meh on hash collision.

        # Use the input field def to define the temp_field using OGR
        temp_field = ogr.FieldDefn(str(column_name), dbf_field_type)

        # Final attribute to set for strings. Not sure if this is needed.
        if type(column_value) is str:
            temp_field.SetWidth(255)

        temp_layer.CreateField(temp_field)


    # TODO This function, append_columns_to_shp_attributes_table, fails when there are nested polygons... i think. Error found when I tried to do appending on NEV countries.

    # Iterate through dictionary changing keys to the now-unique  column headers.
    # CHECK, why did I assign new_entry here if i never use it and instead just pop off of processed_columns.
    for key, value in processed_columns.items():
        new_entry = value
        for i in range(len(new_column_names)):
            new_entry[new_column_names[i]] = processed_columns[key].pop(old_column_names[i])

    # Write values into the respective features
    temp_layer_def = temp_layer.GetLayerDefn()
    feature_count = 0
    num_features = len(input_layer)

    if verbose:
        print ('Starting to append columns from ' + str(num_features) + ' features.')
    for input_feature in input_layer:
        if verbose:
            sys.stdout.write(str(feature_count)+ ' ')
        geometry = input_feature.GetGeometryRef()
        temp_feature = ogr.Feature(temp_layer_def)
        for i in range(0, temp_layer_def.GetFieldCount()):
            field_def = temp_layer_def.GetFieldDefn(i)
            field_name = field_def.GetName()

            # Write the existing values
            if i < input_field_count:
                temp_feature.SetField(temp_layer_def.GetFieldDefn(i).GetNameRef(), input_feature.GetField(i))

            # Write a new value.
            else:
                temp_feature.SetField(temp_layer_def.GetFieldDefn(i).GetNameRef(),
                                      processed_columns[feature_count][temp_layer_def.GetFieldDefn(i).GetNameRef()])

        temp_feature.SetGeometry(geometry)
        temp_layer.CreateFeature(temp_feature)
        temp_feature.Destroy()

        feature_count += 1

    input_shp.Destroy()
    temp_shp.Destroy()

    if output_uri:
        rename_shapefile(temp_uri, output_uri)
    else:
        remove_shapefile(input_shp_uri)
        rename_shapefile(temp_uri, input_shp_uri)

    return 1

def replace_ext(input_uri, desired_ext):
    if os.path.splitext(input_uri)[1]:
        if desired_ext.startswith('.'):
            modified_uri = os.path.splitext(input_uri)[0] + desired_ext
        else:
            modified_uri = os.path.splitext(input_uri)[0] + '.' + desired_ext
    else:
        raise NameError('Cannot replace extension on the input_uri given because it did not have an extension.')
    return modified_uri
# Example Usage

def copy_shapefile(input_uri, output_uri):
    # Because shapefiles have 4+ separate files, use this to smartly copy all of the ones that exist based on versions of input uri.
    for ext in config.possible_shapefile_extensions:
        potential_uri = replace_ext(input_uri, ext)
        if os.path.exists(potential_uri):
            potential_output_uri = replace_ext(output_uri, ext)
            shutil.copyfile(potential_uri, potential_output_uri)

def rename_shapefile(input_uri, output_uri):
    # Because shapefiles have 4+ separate files, use this to smartly rename all of the ones that exist based on versions of input uri.
    for ext in config.possible_shapefile_extensions:
        potential_uri = replace_ext(input_uri, ext)
        if os.path.exists(potential_uri):
            potential_output_uri = replace_ext(output_uri, ext)
            os.rename(potential_uri, potential_output_uri)

def remove_shapefile(input_uri):
    # Because shapefiles have 4+ separate files, use this to smartly rename all of the ones that exist based on versions of input uri.
    for ext in config.possible_shapefile_extensions:
        potential_uri = replace_ext(input_uri, ext)
        if os.path.exists(potential_uri):
            os.remove(potential_uri)


def quad_split_path(input_uri):
    '''
    Splits a path into prior directories path, parent directory, basename (extensionless filename), file extension.
    :return: list of [prior directories path, parent directory, basename (extensionless filename), file extension]
    '''
    a, file_extension = os.path.splitext(input_uri)
    b, file_root = os.path.split(a)
    prior_path, parent_directory = os.path.split(b)

    return [prior_path, parent_directory, file_root, file_extension]


def random_string():
    """Return random string of numbers of expected length. Used in uri manipulation."""
    return pretty_time() + '_' + str(random.randint(0, 999999999)).zfill(9)


def insert_random_string_before_ext(input_uri):
    # split_uri = os.path.splitext(input_uri)
    # return split_uri[0] + '_' + random_string() + split_uri[1]
    split_uri = os.path.splitext(input_uri)
    if split_uri[1]:
        output_uri = split_uri[0] + '_' + random_string() + split_uri[1]
    else:
        output_uri = os.path.join(split_uri[0], random_string())
    return output_uri


def ruri(input_uri):
    '''Shortcut function to insert_random_string_before_ext'''
    return insert_random_string_before_ext(input_uri)



def vectorize_datasets(
        dataset_uri_list, dataset_pixel_op, dataset_out_uri, datatype_out,
        nodata_out, pixel_size_out, bounding_box_mode,
        resample_method_list=None, dataset_to_align_index=None,
        dataset_to_bound_index=None, aoi_uri=None,
        assert_datasets_projected=True, process_pool=None, vectorize_op=True,
        datasets_are_pre_aligned=False, dataset_options=None,
        all_touched=False):
    """Apply local raster operation on stack of datasets.

    This function applies a user defined function across a stack of
    datasets.  It has functionality align the output dataset grid
    with one of the input datasets, output a dataset that is the union
    or intersection of the input dataset bounding boxes, and control
    over the interpolation techniques of the input datasets, if
    necessary.  The datasets in dataset_uri_list must be in the same
    projection; the function will raise an exception if not.

    Args:
        dataset_uri_list (list): a list of file uris that point to files that
            can be opened with gdal.Open.
        dataset_pixel_op (function) a function that must take in as many
            arguments as there are elements in dataset_uri_list.  The arguments
            can be treated as interpolated or actual pixel values from the
            input datasets and the function should calculate the output
            value for that pixel stack.  The function is a parallel
            paradigmn and does not know the spatial position of the
            pixels in question at the time of the call.  If the
            `bounding_box_mode` parameter is "union" then the values
            of input dataset pixels that may be outside their original
            range will be the nodata values of those datasets.  Known
            bug: if dataset_pixel_op does not return a value in some cases
            the output dataset values are undefined even if the function
            does not crash or raise an exception.
        dataset_out_uri (string): the uri of the output dataset.  The
            projection will be the same as the datasets in dataset_uri_list.
        datatype_out: the GDAL output type of the output dataset
        nodata_out: the nodata value of the output dataset.
        pixel_size_out: the pixel size of the output dataset in
            projected coordinates.
        bounding_box_mode (string): one of "union" or "intersection",
            "dataset". If union the output dataset bounding box will be the
            union of the input datasets.  Will be the intersection otherwise.
            An exception is raised if the mode is "intersection" and the
            input datasets have an empty intersection. If dataset it will make
            a bounding box as large as the given dataset, if given
            dataset_to_bound_index must be defined.

    Keyword Args:
        resample_method_list (list): a list of resampling methods
            for each output uri in dataset_out_uri list.  Each element
            must be one of "nearest|bilinear|cubic|cubic_spline|lanczos".
            If None, the default is "nearest" for all input datasets.
        dataset_to_align_index (int): an int that corresponds to the position
            in one of the dataset_uri_lists that, if positive aligns the output
            rasters to fix on the upper left hand corner of the output
            datasets.  If negative, the bounding box aligns the intersection/
            union without adjustment.
        dataset_to_bound_index: if mode is "dataset" this indicates which
            dataset should be the output size.
        aoi_uri (string): a URI to an OGR datasource to be used for the
            aoi.  Irrespective of the `mode` input, the aoi will be used
            to intersect the final bounding box.
        assert_datasets_projected (boolean): if True this operation will
            test if any datasets are not projected and raise an exception
            if so.
        process_pool: a process pool for multiprocessing
        vectorize_op (boolean): if true the model will try to numpy.vectorize
            dataset_pixel_op.  If dataset_pixel_op is designed to use maximize
            array broadcasting, set this parameter to False, else it may
            inefficiently invoke the function on individual elements.
        datasets_are_pre_aligned (boolean): If this value is set to False
            this operation will first align and interpolate the input datasets
            based on the rules provided in bounding_box_mode,
            resample_method_list, dataset_to_align_index, and
            dataset_to_bound_index, if set to True the input dataset list must
            be aligned, probably by raster_utils.align_dataset_list
        dataset_options: this is an argument list that will be
            passed to the GTiff driver.  Useful for blocksizes, compression,
            etc.
        all_touched (boolean): if true the clip uses the option
            ALL_TOUCHED=TRUE when calling RasterizeLayer for AOI masking.

    Returns:
        None

    Raises:
        ValueError: invalid input provided
    """
    if not isinstance(dataset_uri_list, list):
        raise ValueError(
            "dataset_uri_list was not passed in as a list, maybe a single "
            "file was passed in?  Here is its value: %s" %
            (str(dataset_uri_list)))

    if aoi_uri is None:
        assert_file_existance(dataset_uri_list)
    else:
        assert_file_existance(dataset_uri_list + [aoi_uri])

    if dataset_out_uri in dataset_uri_list:
        raise ValueError(
            "%s is used as an output file, but it is also an input file "
            "in the input list %s" % (dataset_out_uri, str(dataset_uri_list)))

    valid_bounding_box_modes = ["union", "intersection", "dataset"]
    if bounding_box_mode not in valid_bounding_box_modes:
        raise ValueError(
            "Unknown bounding box mode %s; should be one of %s",
            bounding_box_mode, valid_bounding_box_modes)

    # Create a temporary list of filenames whose files delete on the python
    # interpreter exit
    if not datasets_are_pre_aligned:
        # Handle the cases where optional arguments are passed in
        if resample_method_list is None:
            resample_method_list = ["nearest"] * len(dataset_uri_list)
        if dataset_to_align_index is None:
            dataset_to_align_index = -1
        dataset_out_uri_list = [
            temporary_filename(suffix='.tif') for _ in dataset_uri_list]
        # Align and resample the datasets, then load datasets into a list
        align_dataset_list(
            dataset_uri_list, dataset_out_uri_list, resample_method_list,
            pixel_size_out, bounding_box_mode, dataset_to_align_index,
            dataset_to_bound_index=dataset_to_bound_index,
            aoi_uri=aoi_uri,
            assert_datasets_projected=assert_datasets_projected,
            all_touched=all_touched)
        aligned_datasets = [
            gdal.Open(filename, gdal.GA_ReadOnly) for filename in
            dataset_out_uri_list]
    else:
        # otherwise the input datasets are already aligned
        aligned_datasets = [
            gdal.Open(filename, gdal.GA_ReadOnly) for filename in
            dataset_uri_list]

    aligned_bands = [dataset.GetRasterBand(1) for dataset in aligned_datasets]

    n_rows = aligned_datasets[0].RasterYSize
    n_cols = aligned_datasets[0].RasterXSize

    output_dataset = new_raster_from_base(
        aligned_datasets[0], dataset_out_uri, 'GTiff', nodata_out,
        datatype_out, dataset_options=dataset_options)
    output_band = output_dataset.GetRasterBand(1)
    block_size = output_band.GetBlockSize()
    # makes sense to get the largest block size possible to reduce the number
    # of expensive readasarray calls
    for current_block_size in [band.GetBlockSize() for band in aligned_bands]:
        if (current_block_size[0] * current_block_size[1] >
                    block_size[0] * block_size[1]):
            block_size = current_block_size

    cols_per_block, rows_per_block = block_size[0], block_size[1]
    n_col_blocks = int(math.ceil(n_cols / float(cols_per_block)))
    n_row_blocks = int(math.ceil(n_rows / float(rows_per_block)))

    # If there's an AOI, mask it out
    if aoi_uri is not None:
        mask_uri = temporary_filename(suffix='.tif')
        mask_dataset = new_raster_from_base(
            aligned_datasets[0], mask_uri, 'GTiff', 255, gdal.GDT_Byte,
            fill_value=0, dataset_options=dataset_options)
        mask_band = mask_dataset.GetRasterBand(1)
        aoi_datasource = ogr.Open(aoi_uri)
        aoi_layer = aoi_datasource.GetLayer()
        if all_touched:
            option_list = ["ALL_TOUCHED=TRUE"]
        else:
            option_list = []
        gdal.RasterizeLayer(
            mask_dataset, [1], aoi_layer, burn_values=[1], options=option_list)
        aoi_layer = None
        aoi_datasource = None

    # We only want to do this if requested, otherwise we might have a more
    # efficient call if we don't vectorize.
    if vectorize_op:
        LOGGER.warn("this call is vectorizing which is deprecated and slow")
        dataset_pixel_op = numpy.vectorize(
            dataset_pixel_op, otypes=[_gdal_to_numpy_type(output_band)])

    last_time = time.time()

    last_row_block_width = None
    last_col_block_width = None
    for row_block_index in range(n_row_blocks):
        row_offset = row_block_index * rows_per_block
        row_block_width = n_rows - row_offset
        if row_block_width > rows_per_block:
            row_block_width = rows_per_block

        for col_block_index in range(n_col_blocks):
            col_offset = col_block_index * cols_per_block
            col_block_width = n_cols - col_offset
            if col_block_width > cols_per_block:
                col_block_width = cols_per_block

            current_time = time.time()
            if current_time - last_time > 5.0:
                LOGGER.info(
                    'raster stack calculation approx. %.2f%% complete',
                    ((row_block_index * n_col_blocks + col_block_index) /
                     float(n_row_blocks * n_col_blocks) * 100.0))
                last_time = current_time

            #This is true at least once since last_* initialized with None
            if (last_row_block_width != row_block_width or
                        last_col_block_width != col_block_width):
                dataset_blocks = [
                    numpy.zeros(
                        (row_block_width, col_block_width),
                        dtype=_gdal_to_numpy_type(band)) for band in aligned_bands]

                if aoi_uri != None:
                    mask_array = numpy.zeros(
                        (row_block_width, col_block_width), dtype=numpy.int8)

                last_row_block_width = row_block_width
                last_col_block_width = col_block_width

            for dataset_index in range(len(aligned_bands)):
                aligned_bands[dataset_index].ReadAsArray(
                    xoff=col_offset, yoff=row_offset,
                    win_xsize=col_block_width,
                    win_ysize=row_block_width,
                    buf_obj=dataset_blocks[dataset_index])

            out_block = dataset_pixel_op(*dataset_blocks)

            # Mask out the row if there is a mask
            if aoi_uri is not None:
                mask_band.ReadAsArray(
                    xoff=col_offset, yoff=row_offset,
                    win_xsize=col_block_width,
                    win_ysize=row_block_width,
                    buf_obj=mask_array)
                out_block[mask_array == 0] = nodata_out

            output_band.WriteArray(
                out_block[0:row_block_width, 0:col_block_width],
                xoff=col_offset, yoff=row_offset)

    # Making sure the band and dataset is flushed and not in memory before
    # adding stats
    output_band.FlushCache()
    output_band = None
    output_dataset.FlushCache()
    gdal.Dataset.__swig_destroy__(output_dataset)
    output_dataset = None

    # Clean up the files made by temporary file because we had an issue once
    # where I was running the water yield model over 2000 times and it made
    # so many temporary files I ran out of disk space.
    if aoi_uri is not None:
        mask_band = None
        gdal.Dataset.__swig_destroy__(mask_dataset)
        mask_dataset = None
        os.remove(mask_uri)
    aligned_bands = None
    for dataset in aligned_datasets:
        gdal.Dataset.__swig_destroy__(dataset)
    aligned_datasets = None
    if not datasets_are_pre_aligned:
        # if they weren't pre-aligned then we have temporary files to remove
        for temp_dataset_uri in dataset_out_uri_list:
            try:
                os.remove(temp_dataset_uri)
            except OSError:
                LOGGER.warn("couldn't delete file %s", temp_dataset_uri)
    calculate_raster_stats_uri(dataset_out_uri)

def calculate_raster_stats_uri(dataset_uri):
    """Calculate min, max, stdev, and mean for all bands in dataset.

    Args:
        dataset_uri (string): a uri to a GDAL raster dataset that will be
            modified by having its band statistics set

    Returns:
        None
    """

    dataset = gdal.Open(dataset_uri, gdal.GA_Update)

    for band_number in range(dataset.RasterCount):
        band = dataset.GetRasterBand(band_number + 1)
        band.ComputeStatistics(False)

    # Close and clean up dataset
    band = None
    gdal.Dataset.__swig_destroy__(dataset)
    dataset = None

def assert_file_existance(dataset_uri_list):
    """Assert that provided uris exist in filesystem.

    Verify that the uris passed in the argument exist on the filesystem
    if not, raise an exeception indicating which files do not exist

    Args:
        dataset_uri_list (list): a list of relative or absolute file paths to
            validate

    Returns:
        None

    Raises:
        IOError: if any files are not found
    """
    not_found_uris = []
    for uri in dataset_uri_list:
        if not os.path.exists(uri):
            not_found_uris.append(uri)

    if len(not_found_uris) != 0:
        error_message = (
            "The following files do not exist on the filesystem: " +
            str(not_found_uris))
        raise NameError(error_message)
        # raise exceptions.IOError(error_message)

def temporary_filename(suffix=''):
    """Get path to new temporary file that will be deleted on program exit.

    Returns a temporary filename using mkstemp. The file is deleted
    on exit using the atexit register.

    Keyword Args:
        suffix (string): the suffix to be appended to the temporary file

    Returns:
        fname: a unique temporary filename
    """
    file_handle, path = tempfile.mkstemp(suffix=suffix)
    os.close(file_handle)

    def remove_file(path):
        """Function to remove a file and handle exceptions to register
            in atexit."""
        try:
            os.remove(path)
        except OSError:
            # This happens if the file didn't exist, which is okay because
            # maybe we deleted it in a method
            pass

    atexit.register(remove_file, path)
    return path




def align_dataset_list(
        dataset_uri_list, dataset_out_uri_list, resample_method_list,
        out_pixel_size, mode, dataset_to_align_index,
        dataset_to_bound_index=None, aoi_uri=None,
        assert_datasets_projected=True, all_touched=False):
    """Create a new list of datasets that are aligned based on a list of
        inputted datasets.

    Take a list of dataset uris and generates a new set that is completely
    aligned with identical projections and pixel sizes.

    Args:
        dataset_uri_list (list): a list of input dataset uris
        dataset_out_uri_list (list): a parallel dataset uri list whose
            positions correspond to entries in dataset_uri_list
        resample_method_list (list): a list of resampling methods for each
            output uri in dataset_out_uri list.  Each element must be one of
            "nearest|bilinear|cubic|cubic_spline|lanczos"
        out_pixel_size: the output pixel size
        mode (string): one of "union", "intersection", or "dataset" which
            defines how the output output extents are defined as either the
            union or intersection of the input datasets or to have the same
            bounds as an existing raster.  If mode is "dataset" then
            dataset_to_bound_index must be defined
        dataset_to_align_index (int): an int that corresponds to the position
            in one of the dataset_uri_lists that, if positive aligns the output
            rasters to fix on the upper left hand corner of the output
            datasets.  If negative, the bounding box aligns the intersection/
            union without adjustment.
        all_touched (boolean): if True and an AOI is passed, the
            ALL_TOUCHED=TRUE option is passed to the RasterizeLayer function
            when determining the mask of the AOI.

    Keyword Args:
        dataset_to_bound_index: if mode is "dataset" then this index is
            used to indicate which dataset to define the output bounds of the
            dataset_out_uri_list
        aoi_uri (string): a URI to an OGR datasource to be used for the
            aoi.  Irrespective of the `mode` input, the aoi will be used
            to intersect the final bounding box.

    Returns:
        None
    """
    last_time = time.time()

    # make sure that the input lists are of the same length
    list_lengths = [
        len(dataset_uri_list), len(dataset_out_uri_list),
        len(resample_method_list)]
    if not reduce(lambda x, y: x if x == y else False, list_lengths):
        raise Exception(
            "dataset_uri_list, dataset_out_uri_list, and "
            "resample_method_list must be the same length "
            " current lengths are %s" % (str(list_lengths)))

    if assert_datasets_projected:
        assert_datasets_in_same_projection(dataset_uri_list)
    if mode not in ["union", "intersection", "dataset"]:
        raise Exception("Unknown mode %s" % (str(mode)))

    if dataset_to_align_index >= len(dataset_uri_list):
        raise Exception(
            "Alignment index is out of bounds of the datasets index: %s"
            "n_elements %s" % (dataset_to_align_index, len(dataset_uri_list)))
    if mode == "dataset" and dataset_to_bound_index is None:
        raise Exception(
            "Mode is 'dataset' but dataset_to_bound_index is not defined")
    if mode == "dataset" and (dataset_to_bound_index < 0 or
                                      dataset_to_bound_index >= len(dataset_uri_list)):
        raise Exception(
            "dataset_to_bound_index is out of bounds of the datasets index: %s"
            "n_elements %s" % (dataset_to_bound_index, len(dataset_uri_list)))

    def merge_bounding_boxes(bb1, bb2, mode):
        """Helper function to merge two bounding boxes through union or
            intersection"""
        less_than_or_equal = lambda x, y: x if x <= y else y
        greater_than = lambda x, y: x if x > y else y

        if mode == "union":
            comparison_ops = [
                less_than_or_equal, greater_than, greater_than,
                less_than_or_equal]
        if mode == "intersection":
            comparison_ops = [
                greater_than, less_than_or_equal, less_than_or_equal,
                greater_than]

        bb_out = [op(x, y) for op, x, y in zip(comparison_ops, bb1, bb2)]
        return bb_out

    # get the intersecting or unioned bounding box
    if mode == "dataset":
        bounding_box = get_bounding_box(
            dataset_uri_list[dataset_to_bound_index])
    else:
        bounding_box = reduce(
            functools.partial(merge_bounding_boxes, mode=mode),
            [get_bounding_box(dataset_uri) for dataset_uri in dataset_uri_list])

    if aoi_uri is not None:
        bounding_box = merge_bounding_boxes(
            bounding_box, get_datasource_bounding_box(aoi_uri), "intersection")

    if (bounding_box[0] >= bounding_box[2] or
                bounding_box[1] <= bounding_box[3]) and mode == "intersection":
        raise Exception("The datasets' intersection is empty "
                        "(i.e., not all the datasets touch each other).")

    if dataset_to_align_index >= 0:
        # bounding box needs alignment
        align_bounding_box = get_bounding_box(
            dataset_uri_list[dataset_to_align_index])
        align_pixel_size = get_cell_size_from_uri(
            dataset_uri_list[dataset_to_align_index])

        for index in [0, 1]:
            n_pixels = int(
                (bounding_box[index] - align_bounding_box[index]) /
                float(align_pixel_size))
            bounding_box[index] = \
                n_pixels * align_pixel_size + align_bounding_box[index]

    for original_dataset_uri, out_dataset_uri, resample_method, index in zip(
            dataset_uri_list, dataset_out_uri_list, resample_method_list,
            list(range(len(dataset_uri_list)))):
        current_time = time.time()
        if current_time - last_time > 5.0:
            last_time = current_time
            LOGGER.info(
                "align_dataset_list aligning dataset %d of %d",
                index, len(dataset_uri_list))

        resize_and_resample_dataset_uri(
            original_dataset_uri, bounding_box, out_pixel_size,
            out_dataset_uri, resample_method)

    # If there's an AOI, mask it out
    if aoi_uri is not None:
        first_dataset = gdal.Open(dataset_out_uri_list[0])
        n_rows = first_dataset.RasterYSize
        n_cols = first_dataset.RasterXSize
        gdal.Dataset.__swig_destroy__(first_dataset)
        first_dataset = None

        mask_uri = temporary_filename(suffix='.tif')
        new_raster_from_base_uri(
            dataset_out_uri_list[0], mask_uri, 'GTiff', 255, gdal.GDT_Byte,
            fill_value=0)

        mask_dataset = gdal.Open(mask_uri, gdal.GA_Update)
        mask_band = mask_dataset.GetRasterBand(1)
        aoi_datasource = ogr.Open(aoi_uri)
        aoi_layer = aoi_datasource.GetLayer()
        if all_touched:
            option_list = ["ALL_TOUCHED=TRUE"]
        else:
            option_list = []
        gdal.RasterizeLayer(
            mask_dataset, [1], aoi_layer, burn_values=[1], options=option_list)
        mask_row = numpy.zeros((1, n_cols), dtype=numpy.int8)

        out_dataset_list = [
            gdal.Open(uri, gdal.GA_Update) for uri in dataset_out_uri_list]
        out_band_list = [
            dataset.GetRasterBand(1) for dataset in out_dataset_list]
        nodata_out_list = [
            get_nodata_from_uri(uri) for uri in dataset_out_uri_list]

        for row_index in range(n_rows):
            mask_row = (mask_band.ReadAsArray(
                0, row_index, n_cols, 1) == 0)
            for out_band, nodata_out in zip(out_band_list, nodata_out_list):
                dataset_row = out_band.ReadAsArray(
                    0, row_index, n_cols, 1)
                out_band.WriteArray(
                    numpy.where(mask_row, nodata_out, dataset_row),
                    xoff=0, yoff=row_index)

        # Remove the mask aoi if necessary
        mask_band = None
        gdal.Dataset.__swig_destroy__(mask_dataset)
        mask_dataset = None
        os.remove(mask_uri)

        # Close and clean up datasource
        aoi_layer = None
        ogr.DataSource.__swig_destroy__(aoi_datasource)
        aoi_datasource = None

        # Clean up datasets
        out_band_list = None
        for dataset in out_dataset_list:
            dataset.FlushCache()
            gdal.Dataset.__swig_destroy__(dataset)
        out_dataset_list = None


def get_bounding_box(dataset_uri):
    """Get bounding box where coordinates are in projected units.

    Args:
        dataset_uri (string): a uri to a GDAL dataset

    Returns:
        bounding_box (list):
            [upper_left_x, upper_left_y, lower_right_x, lower_right_y] in
            projected coordinates
    """
    dataset = gdal.Open(dataset_uri)

    geotransform = dataset.GetGeoTransform()
    n_cols = dataset.RasterXSize
    n_rows = dataset.RasterYSize

    bounding_box = [geotransform[0],
                    geotransform[3],
                    geotransform[0] + n_cols * geotransform[1],
                    geotransform[3] + n_rows * geotransform[5]]

    # Close and cleanup dataset
    gdal.Dataset.__swig_destroy__(dataset)
    dataset = None

    return bounding_box

def get_datasource_bounding_box(datasource_uri):
    """Get datasource bounding box where coordinates are in projected units.

    Args:
        dataset_uri (string): a uri to a GDAL dataset

    Returns:
        bounding_box (list):
            [upper_left_x, upper_left_y, lower_right_x, lower_right_y] in
            projected coordinates
    """
    datasource = ogr.Open(datasource_uri)
    layer = datasource.GetLayer(0)
    extent = layer.GetExtent()
    # Reindex datasource extents into the upper left/lower right coordinates
    bounding_box = [extent[0],
                    extent[3],
                    extent[1],
                    extent[2]]
    return bounding_box

def reproject_datasource_uri(original_dataset_uri, output_wkt, output_uri):
    """Reproject OGR DataSource file.

    URI wrapper for reproject_datasource that takes in the uri for the
    datasource that is to be projected instead of the datasource itself.
    This function directly calls reproject_datasource.

    Args:
        original_dataset_uri (string): a uri to an ogr datasource
        output_wkt: the desired projection as Well Known Text
            (by layer.GetSpatialRef().ExportToWkt())
        output_uri (string): the path to where the new shapefile should be
            written to disk.

    Return:
        None
    """
    original_dataset = ogr.Open(original_dataset_uri)
    _ = reproject_datasource(original_dataset, output_wkt, output_uri)


def reproject_datasource(original_datasource, output_wkt, output_uri):
    """Reproject OGR DataSource object.

    Changes the projection of an ogr datasource by creating a new
    shapefile based on the output_wkt passed in.  The new shapefile
    then copies all the features and fields of the original_datasource
    as its own.

    Args:
        original_datasource: an ogr datasource
        output_wkt: the desired projection as Well Known Text
            (by layer.GetSpatialRef().ExportToWkt())
        output_uri (string): the filepath to the output shapefile

    Returns:
        output_datasource: the reprojected shapefile.
    """

    # if this file already exists, then remove it
    if os.path.isfile(output_uri):
        os.remove(output_uri)

    output_sr = osr.SpatialReference()
    output_sr.ImportFromWkt(output_wkt)

    # create a new shapefile from the orginal_datasource
    output_driver = ogr.GetDriverByName('ESRI Shapefile')
    output_datasource = output_driver.CreateDataSource(output_uri)

    # loop through all the layers in the orginal_datasource
    for original_layer in original_datasource:

        # Get the original_layer definition which holds needed attribute values
        original_layer_dfn = original_layer.GetLayerDefn()

        # Create the new layer for output_datasource using same name and
        # geometry type from original_datasource, but different projection
        output_layer = output_datasource.CreateLayer(
            original_layer_dfn.GetName(), output_sr,
            original_layer_dfn.GetGeomType())

        # Get the number of fields in original_layer
        original_field_count = original_layer_dfn.GetFieldCount()

        # For every field, create a duplicate field and add it to the new
        # shapefiles layer
        for fld_index in range(original_field_count):
            original_field = original_layer_dfn.GetFieldDefn(fld_index)
            output_field = ogr.FieldDefn(
                original_field.GetName(), original_field.GetType())
            output_layer.CreateField(output_field)

        original_layer.ResetReading()

        # Get the spatial reference of the original_layer to use in transforming
        original_sr = original_layer.GetSpatialRef()

        # Create a coordinate transformation
        coord_trans = osr.CoordinateTransformation(original_sr, output_sr)

        # Copy all of the features in original_layer to the new shapefile
        error_count = 0
        for original_feature in original_layer:
            geom = original_feature.GetGeometryRef()

            # Transform the geometry into format desired for the new projection
            error_code = geom.Transform(coord_trans)
            if error_code != 0: # error
                # this could be caused by an out of range transformation
                # whatever the case, don't put the transformed poly into the
                # output set
                error_count += 1
                continue

            # Copy original_datasource's feature and set as new shapes feature
            output_feature = ogr.Feature(
                feature_def=output_layer.GetLayerDefn())
            output_feature.SetFrom(original_feature)
            output_feature.SetGeometry(geom)

            # For all the fields in the feature set the field values from the
            # source field
            for fld_index2 in range(output_feature.GetFieldCount()):
                original_field_value = original_feature.GetField(fld_index2)
                output_feature.SetField(fld_index2, original_field_value)

            output_layer.CreateFeature(output_feature)
            output_feature = None

            original_feature = None
        if error_count > 0:
            LOGGER.warn(
                '%d features out of %d were unable to be transformed and are'
                ' not in the output dataset at %s', error_count,
                original_layer.GetFeatureCount(), output_uri)
        original_layer = None

    return output_datasource

def create_directories(directory_list):
    """Make directories provided in list of path strings.

    This function will create any of the directories in the directory list
    if possible and raise exceptions if something exception other than
    the directory previously existing occurs.

    Args:
        directory_list (list): a list of string uri paths

    Returns:
        None
    """
    for dir_name in directory_list:
        try:
            os.makedirs(dir_name)
        except OSError as exception:
            #It's okay if the directory already exists, if it fails for
            #some other reason, raise that exception
            if (exception.errno != errno.EEXIST and
                        exception.errno != errno.ENOENT):
                raise



def new_raster_from_base_uri(base_uri, *args, **kwargs):
    """A wrapper for the function new_raster_from_base that opens up
        the base_uri before passing it to new_raster_from_base.

        base_uri - a URI to a GDAL dataset on disk.

        All other arguments to new_raster_from_base are passed in.

        Returns nothing.
        """
    base_raster = gdal.Open(base_uri)
    if base_raster is None:
        raise IOError("%s not found when opening GDAL raster")
    new_raster = new_raster_from_base(base_raster, *args, **kwargs)

    gdal.Dataset.__swig_destroy__(new_raster)
    gdal.Dataset.__swig_destroy__(base_raster)
    new_raster = None
    base_raster = None


def new_raster_from_base(
        base, output_uri, gdal_format, nodata, datatype, fill_value=None,
        n_rows=None, n_cols=None, dataset_options=None):
    """Create a new, empty GDAL raster dataset with the spatial references,
        geotranforms of the base GDAL raster dataset.

        base - a the GDAL raster dataset to base output size, and transforms on
        output_uri - a string URI to the new output raster dataset.
        gdal_format - a string representing the GDAL file format of the
            output raster.  See http://gdal.org/formats_list.html for a list
            of available formats.  This parameter expects the format code, such
            as 'GTiff' or 'MEM'
        nodata - a value that will be set as the nodata value for the
            output raster.  Should be the same type as 'datatype'
        datatype - the pixel datatype of the output raster, for example
            gdal.GDT_Float32.  See the following header file for supported
            pixel types:
            http://www.gdal.org/gdal_8h.html#22e22ce0a55036a96f652765793fb7a4
        fill_value - (optional) the value to fill in the raster on creation
        n_rows - (optional) if set makes the resulting raster have n_rows in it
            if not, the number of rows of the outgoing dataset are equal to
            the base.
        n_cols - (optional) similar to n_rows, but for the columns.
        dataset_options - (optional) a list of dataset options that gets
            passed to the gdal creation driver, overrides defaults

        returns a new GDAL raster dataset."""

    #This might be a numpy type coming in, set it to native python type
    try:
        nodata = nodata.item()
    except AttributeError:
        pass

    if n_rows is None:
        n_rows = base.RasterYSize
    if n_cols is None:
        n_cols = base.RasterXSize
    projection = base.GetProjection()
    geotransform = base.GetGeoTransform()
    driver = gdal.GetDriverByName(gdal_format)

    base_band = base.GetRasterBand(1)
    block_size = base_band.GetBlockSize()
    metadata = base_band.GetMetadata('IMAGE_STRUCTURE')
    base_band = None

    if dataset_options == None:
        #make a new list to make sure we aren't ailiasing one passed in
        dataset_options = []
        #first, should it be tiled?  yes if it's not striped
        if block_size[0] != n_cols:
            #just do 256x256 blocks
            dataset_options = [
                'TILED=YES',
                'BLOCKXSIZE=256',
                'BLOCKYSIZE=256',
                'BIGTIFF=IF_SAFER']
        if 'PIXELTYPE' in metadata:
            dataset_options.append('PIXELTYPE=' + metadata['PIXELTYPE'])

    new_raster = driver.Create(
        output_uri.encode('utf-8'), n_cols, n_rows, 1, datatype,
        options=dataset_options)
    new_raster.SetProjection(projection)
    new_raster.SetGeoTransform(geotransform)
    band = new_raster.GetRasterBand(1)

    if nodata is not None:
        band.SetNoDataValue(nodata)
    else:
        LOGGER.warn(
            "None is passed in for the nodata value, failed to set any nodata "
            "value for new raster.")

    if fill_value != None:
        band.Fill(fill_value)
    elif nodata is not None:
        band.Fill(nodata)
    band = None

    return new_raster


def get_nodata_from_uri(dataset_uri):
    """Return nodata value from first band in gdal dataset cast as numpy datatype.

    Args:
        dataset_uri (string): a uri to a gdal dataset

    Returns:
        nodata: nodata value for dataset band 1
    """
    dataset = gdal.Open(dataset_uri)
    band = dataset.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    if nodata is not None:
        nodata = _gdal_to_numpy_type(band)(nodata)
    else:
        LOGGER.warn(
            "Warning the nodata value in %s is not set", dataset_uri)

    band = None
    gdal.Dataset.__swig_destroy__(dataset)
    dataset = None
    return nodata


def get_datatype_from_uri(dataset_uri):
    """Return datatype for first band in gdal dataset.

    Args:
        dataset_uri (string): a uri to a gdal dataset

    Returns:
        datatype: datatype for dataset band 1"""
    dataset = gdal.Open(dataset_uri)
    band = dataset.GetRasterBand(1)
    datatype = band.DataType

    # Close and clean up dataset
    band = None
    gdal.Dataset.__swig_destroy__(dataset)
    dataset = None

    return datatype


def get_row_col_from_uri(dataset_uri):
    """Return number of rows and columns of given dataset uri as tuple.

    Args:
        dataset_uri (string): a uri to a gdal dataset

    Returns:
        rows_cols (tuple): 2-tuple (n_row, n_col) from dataset_uri
    """
    dataset = gdal.Open(dataset_uri)
    n_rows = dataset.RasterYSize
    n_cols = dataset.RasterXSize

    # Close and clean up dataset
    band = None
    gdal.Dataset.__swig_destroy__(dataset)
    dataset = None

    return (n_rows, n_cols)

def _gdal_to_numpy_type(band):
    """Calculate the equivalent numpy datatype from a GDAL raster band type.

    Args:
        band (gdal.Band): GDAL band

    Returns:
        numpy_datatype (numpy.dtype): equivalent of band.DataType
    """

    gdal_type_to_numpy_lookup = {
        gdal.GDT_Int16: numpy.int16,
        gdal.GDT_Int32: numpy.int32,
        gdal.GDT_UInt16: numpy.uint16,
        gdal.GDT_UInt32: numpy.uint32,
        gdal.GDT_Float32: numpy.float32,
        gdal.GDT_Float64: numpy.float64
    }

    if band.DataType in gdal_type_to_numpy_lookup:
        return gdal_type_to_numpy_lookup[band.DataType]

    # only class not in the lookup is a Byte but double check.
    if band.DataType != gdal.GDT_Byte:
        raise ValueError("Unknown DataType: %s" % str(band.DataType))

    metadata = band.GetMetadata('IMAGE_STRUCTURE')
    if 'PIXELTYPE' in metadata and metadata['PIXELTYPE'] == 'SIGNEDBYTE':
        return numpy.int8
    return numpy.uint8















