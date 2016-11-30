# coding=utf-8

import sys
import os
import logging
import shutil
from collections import OrderedDict
import datetime
import random

from osgeo import ogr, osr
from matplotlib import rcParams

from mesh_utilities import config
from mesh_utilities import utilities

rcParams.update({'figure.autolayout': True}) # This line makes matplotlib automatically change the fig size according to legends, labels etc.
LOGGER = config.LOGGER
LOGGER.setLevel(logging.INFO)
ENCODING = sys.getfilesystemencoding()


def clip_geotiff_from_base_data(input_shape_uri, base_data_uri, output_geotiff_uri):
    gdal_command = 'gdalwarp -cutline ' + input_shape_uri + ' -crop_to_cutline -overwrite -s_srs EPSG:4326 -t_srs EPSG:54030 -of GTiff ' + base_data_uri + ' ' + output_geotiff_uri
    os.system(gdal_command)


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
    command = 'ogr2ogr'
    command += ' ' + output_uri + ' ' + input_uri
    command += ' -t_srs EPSG:' + str(output_epsg_code)
    os.system(command)


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

