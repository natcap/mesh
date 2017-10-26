# coding=utf-8

from collections import OrderedDict
import os
import datetime
import json
import csv
import platform
import sys
import shutil
import random
import pprint
import pprint as pp
import atexit
import time
import functools
import errno
import math

from osgeo import gdal, ogr, osr
from PyQt4.QtGui import *
import xlrd
import pygeoprocessing.geoprocessing
import pygeoprocessing.geoprocessing as pg

import numpy
import config
import numpy as np

initial_temp_env_var = None
for temp_var in ['TMP', ' TEMP', 'TMPDIR']:
    if temp_var in os.environ:
        initial_temp_env_var = os.environ[temp_var]

def open_dir(dir_path):
    if platform.system() == "Windows":
        os.startfile(dir_path)
    elif platform.system() == "Linux":
        subprocess.Popen(['xdg-open', dir_path])
    else:
        #for mac
        os.system('open "%s"' % dir_path)


def get_user_natcap_folder():
    """Return the file location of the user's settings folder.  This folder
    location is OS-dependent."""
    if platform.system() == 'Windows':
        config_folder = os.path.join('~', 'AppData', 'Local', 'NatCap')
    else:
        config_folder = os.path.join('~', '.natcap')
    expanded_path = os.path.expanduser(config_folder)
    user_folder = expanded_path.decode(sys.getfilesystemencoding())
    return user_folder

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


def correct_temp_env(app):
    # HACKISH solution to solve tmpfile problem that arose when iui deleted the tmpfile folder via atexit, which made tmpfile calls from mesh  no longer work.
    # for temp_var in ['TMP',' TEMP', 'TMPDIR']:
    #     if temp_var in os.environ:
    #         del os.environ[temp_var]
    #
    #     if temp_var in os.environ:
    #         os.environ[temp_var] = initial_temp_env_var

    # Current fix: just read off what could be a tempfile location and attempt to remake that directory.
    tmp_paths = [str(os.environ[i]) for i in os.environ if 'TEMP' in i or 'TMP' in i]
    for path in tmp_paths:
        try:
            os.makedirs(path)
        except:
            'exists'

def read_txt_file_as_serialized_headers(uri, highest_level_blanks=3):
    """Read a txt file where the number of blank lines before a line indicates what level in the title-heirarchy it is. Top level
    level denotes how many blank lines define the highest level heading, otherwise it determinesw the highest level by the number
    of lines on the first line.
    """
    qt_objects = []
    with open(uri, 'r+') as f:
        blank_lines_counter = 0
        odict = OrderedDict()
        for line in f:
            if line == '\\n' or line =='\n':
                blank_lines_counter += 1
            elif line.startswith('show_image'):
                to_append = line.split(' ', 1)[1]
                blank_lines_counter = 0
                qt_objects.append(to_append)
            else:
                if blank_lines_counter == 3:
                    #qt_objects.append(QLabel())
                    qt_objects.append(QLabel())
                    to_append = QLabel(line)
                    to_append.setFont(config.heading_font)
                    to_append.setWordWrap(True)

                    blank_lines_counter = 0
                elif blank_lines_counter == 2:
                    #qt_objects.append(QLabel())
                    to_append = QLabel(line)
                    to_append.setFont(config.bold_font)
                    to_append.setWordWrap(True)
                    blank_lines_counter = 0
                elif blank_lines_counter <= 1:
                    #qt_objects.append(QLabel())
                    to_append = QLabel(line)
                    to_append.setWordWrap(True)
                    blank_lines_counter = 0

                to_append.setMargin(3)
                qt_objects.append(to_append)

    return qt_objects

def get_raster_min_max(raster_path, value):
    """Return the min or the max of a raster found at 'raster_path'.

    Use gdal.band.GetStatistics to return the minimun or maximum value
    from a raster

    Parameters:
        raster_path (string): location to a raster on disk
        value (string): a string of either "min" or "max"

    Return:
        a float being the minimum or maximum
    """
    value_mapping = {"min": 0, "max": 1}
    index = value_mapping[value]

    raster = gdal.Open(raster_path)
    band = raster.GetRasterBand(1)
    statistics = band.GetStatistics(0, 1)

    # Close and clean up dataset
    band = None
    gdal.Dataset.__swig_destroy__(raster)
    raster = None

    return statistics[index]

def get_raster_sum(raster_path):
    """Returns the sum of the non nodata pixels in a raster

    Parameters:
        raster_path (string): a location to a raster on disk

    Returns:
        a number of the sum of the pixels
    """
    nodata = pygeoprocessing.geoprocessing.get_nodata_from_uri(raster_path)

    sum_val = 0.0
    for data, block in pygeoprocessing.geoprocessing.iterblocks(
        raster_path, band_list=[1]):

        # Create a mask to ignore nodata values from summation
        pixels_mask = (block != nodata)

        # If there are only nodata values in this block skip block
        if numpy.all(~pixels_mask):
            continue

        sum_val = sum_val + numpy.sum(block[pixels_mask])

    return sum_val

def iterable_to_json(input_iterable, output_uri):
    with open(output_uri, 'w') as fp:
        json.dump(input_iterable, fp)

def simple_iterable_to_csv(input_iterable, output_uri, verbose=False):
    if not os.path.exists(os.path.split(output_uri)[0]) and os.path.split(output_uri)[0]:
        print('Specified output_uri folder ' + output_uri + ' that does not exist.')
        #os.makedirs(os.path.split(output_uri)[0])

    to_write = ''
    if isinstance(input_iterable, (dict, OrderedDict)):
        for key, value in input_iterable.items():
            try:
                value_string = str(value)
            except:
                'cannot be made a string'
            to_write += key + ',' + value_string + '\n'
    elif isinstance(input_iterable, list):
        for key, value in enumerate(input_iterable):
            try:
                value_string = str(value)
            except:
                'cannot be made a string'
            to_write += str(key) + ',' + value_string + '\n'
    else:
        print('Needs to be a OrderedDict, dict or list')

    open(output_uri, 'w').write(to_write) #This line exports as CSV everything in out_list, where each list element of out_list is a row of string text


def python_object_to_csv(input_iterable, output_uri, csv_type=None, verbose=False):
    if csv_type:
        data_type = csv_type
    else:
        data_type = determine_data_type_and_dimensions_for_write(input_iterable)
    protected_characters = [',', '\n']
    first_row = True
    if not os.path.exists(os.path.split(output_uri)[0]) and os.path.split(output_uri)[0]:
        print('Specified output_uri folder ' + os.path.split(output_uri)[0] + ' does not exist. Creating it.')
        os.makedirs(os.path.split(output_uri)[0])

    to_write = ''

    if data_type == 'singleton':
        to_write = input_iterable
    elif data_type == '1d_list':
        to_write += ','.join(input_iterable)
    elif data_type == '2d_list':
        for row in input_iterable:
            if any(character in row for character in protected_characters):
                raise NameError('Protected character found in the string-ed version of the iterable.')
            to_write += ','.join(row) + '\n'
    elif data_type == '2d_list_odict_NOT_SUPPORTED':
        raise
    elif data_type == '1d_odict':
        for key, value in input_iterable.items():
            # check to see if commas or line breaks are in the iterable string.
            value = str(value)
            if any(character in key for character in protected_characters) or any(character in value for character in protected_characters):
                raise NameError('Protected character found in the string-ed version of the iterable.')
            to_write += str(key) + ',' + str(value) + '\n'
    elif data_type == '2d_odict_list':
        raise NameError('NYI')
    elif data_type == '2d_odict':
        if isinstance(input_iterable, list):
            # TODOO Fix the odict-reading methods to be more robust and specific to mesh.
            # The only way you can get here is it was manually declared to be this type and the list implies that it was empty (1 row).
            # Currently, I do not deal with indexed data_types consistently, nor do I account for empty data (as in here) the same on IO operations.
            to_write += ','.join(input_iterable)
        else:
            for key, value in input_iterable.items():
                if first_row:
                    # On the first row, we need to write BOTH th efirst and second rows for col_headers and data respecitvely.
                    first_row = False
                    if any(character in key for character in protected_characters) or any(character in value for character in protected_characters):
                        raise NameError('Protected character found in the string-ed version of the iterable.')
                    to_write += ','.join(value.keys()) + '\n' # Note the following duplication of keys, values to address the nature of first row being keys.
                if any(character in key for character in protected_characters) or any(character in value for character in protected_characters):
                    raise NameError('Protected character found in the string-ed version of the iterable.')
                first_col = True
                for value2 in value.values():
                    if first_col:
                        first_col = False
                    else:
                        to_write += ','
                    if isinstance(value2, list):
                        to_write += '<^>'.join(value2) # LOL WTF. Ran out of time and got creative. Catears.
                    else:
                        to_write += str(value2)
                to_write += '\n'
    elif data_type == 'dd':
        # To ensure i didnt bork 2d_odict reading, i created this conditional to mimic (partially) the advances made in hazelbean library.
        if isinstance(input_iterable, list):
            to_write += ','.join(input_iterable)
        else:
            for key, value in input_iterable.items():
                if first_row:
                    # On the first row, we need to write BOTH th efirst and second rows for col_headers and data respecitvely.
                    first_row = False
                    if any(character in key for character in protected_characters) or any(character in value for character in protected_characters):
                        raise NameError('Protected character found in the string-ed version of the iterable.')

                    # NOTE THE MASSIVE DIFFERENCE that comes from the leading comma. This differs from 2cd_odict.
                    to_write += ',' + ','.join(value.keys()) + '\n' # Note the following duplication of keys, values to address the nature of first row being keys.
                if any(character in key for character in protected_characters) or any(character in value for character in protected_characters):
                    raise NameError('Protected character found in the string-ed version of the iterable.')
                first_col = True
                for key2, value2 in value.items():
                    if first_col:
                        to_write += str(key) + ','
                        first_col = False
                        if isinstance(value2, list):
                            to_write += '<^>'.join(value2)  # LOL WTF. Ran out of time and got creative. Catears.
                        else:
                            to_write += str(value2)
                    else:
                        to_write += ','
                        if isinstance(value2, list):
                            to_write += '<^>'.join(value2)  # LOL WTF. Ran out of time and got creative. Catears.
                        else:
                            to_write += str(value2)

                to_write += '\n'
    else:
        raise NameError('Not sure how to handle that data_type.')

    open(output_uri, 'w').write(to_write)

    if verbose:
        print('\nWriting python object to csv at ' + output_uri + '. Auto-detected the data_type to be: ' + data_type)
        print('String written:\n' + to_write)

def determine_data_type_and_dimensions_for_write(input_python_object):
    """
    Inspects a file of type to determine what the dimensions of the data are and make a guess at the best file_type to
    express the data as. The prediction is based on what content is in the upper-left cell and the dimensions.
    Useful when converting a python iterable to a file output.
    Function forked from original found in geoecon_utils library, used with permission open BSD from Justin Johnson.
    """

    data_type = None

    # First check to see if more than 2 dimensions. Currently, I do not detect beyond 2 dimensions here and instead just use the
    # Str function in python in the write function.
    if isinstance(input_python_object, str):
        data_type = 'singleton'
    # elif isinstance(input_python_object, dict):
    #     raise TypeError('Only works with OrderedDicts not dicts.')
    elif isinstance(input_python_object, list):
        first_row = input_python_object[0]
        if isinstance(first_row, (str, int, float, bool)):
            data_type = '1d_list'
        # elif isinstance(first_row, dict):
        #     raise TypeError('Only works with OrderedDicts not dicts.')
        elif isinstance(first_row, list):
            data_type = '2d_list'
        elif isinstance(first_row, OrderedDict):
            data_type = '2d_list_odict_NOT_SUPPORTED'
        else:
            raise
    elif isinstance(input_python_object, OrderedDict):
        first_row_key = next(iter(input_python_object))
        first_row = input_python_object[first_row_key]
        if isinstance(first_row, (str, int, float, bool)):
            data_type = '1d_odict'
        # elif isinstance(first_row, dict):
        #     raise TypeError('Only works with OrderedDicts not dicts.')
        elif isinstance(first_row, list):
            data_type = '2d_odict_list'
        elif isinstance(first_row, OrderedDict):
            data_type = '2d_odict'
        else:
            raise NameError('Unsupported object type. Did you give a blank OrderedDict to python_object_to_csv()?')
    else:
        raise NameError('Unsupported object type. You probably gave "None" to python_object_to_csv()')
    return data_type

def resample_preserve_sum(input_uri, output_uri, match_uri, resolution=None, **kwargs):
    if not resolution:
        #NOTE: I could have just ignored kwargs here. Not sure why i kept it in.
        if kwargs.get('resolution'):
            resolution = kwargs.get('resolution')
        elif match_uri:
            resolution = get_cell_size_from_uri(match_uri)
        else:
            raise NameError('Unable to resample. resolution not set AND the Match AFs resolution is not set nor was it specified in kwargs.')

    kwargs['resample_method'] = 'average'

    input_array = as_array(input_uri)

    initial_sum = np.nansum(input_array)
    temp_uri = ruri('temp.tif')
    resample_simple(input_uri, data_type=7, match_uri=match_uri, resolution=resolution, output_uri=temp_uri, **kwargs)
    temp_array = as_array(temp_uri)
    temp_sum = np.nansum(temp_array)

    # TODO, Here, I had to float() it because the type was np.float64, which failed in the apply_op's logic for determining what type of calculation it was,
    adjustment_factor = float(initial_sum / temp_sum)

    # new_af = temp_af * adjustment_factor
    adjusted_sum_array = temp_array * adjustment_factor #nd.multiply(temp_af, adjustment_factor, calculation_data_type=7, data_type=7, output_uri=output_uri)
    save_array_as_geotiff(adjusted_sum_array, output_uri, match_uri)

    return

def resample_simple(src_uri, output_uri, match_uri=None, resolution=None, **kwargs):

    # Must have either match_af or resolution set
    if not resolution:
        if kwargs.get('resolution'):
            resolution = kwargs.get('resolution')
        elif match_uri:
            resolution = get_cell_size_from_uri(match_uri)
        else:
            raise NameError('Unable to resample. resolution not set AND the Match AFs resolution is not set nor was it specified in kwargs.')

    bounding_box = kwargs.get('bounding_box', None)
    if not bounding_box:
        if match_uri:
            bounding_box = get_bounding_box(match_uri)
        else:
            bounding_box = get_bounding_box(src_uri)

    resample_method = kwargs.get('resample_method', 'nearest')
    output_datatype = kwargs.get('output_datatype')

    # Call the uri-based utility function.
    resize_and_resample_dataset_uri(
        src_uri, bounding_box, resolution, output_uri, resample_method)




def file_to_python_object(file_uri, declare_type=None, verbose=False, return_all_parts=False, xls_worksheet=None):
    """
    Creates a python iterable, usually an OrderedDict (from collections library) that expresses data of 1 to 3 dimensions
    based on an input file formatted to indicate its data type.

    Function forked from original found in geoecon_utils library, used with permission open BSD from Justin Johnson.
    """
    file_extension = None
    if os.path.exists(file_uri):
        (file_path, file_extension) = os.path.splitext(file_uri)
        (folder, file_name) = os.path.split(file_path)
    else:
        print('File does not exist: ' + file_uri)
        return
        #raise NameError('File does not exist: ' + file_uri)

    if file_extension == '.json':
        json_data=open(file_uri).read()
        data = json.loads(json_data)
        return data

    elif file_extension == '.xls' or file_extension == '.xlsx':
        wb = xlrd.open_workbook(file_uri)
        if xls_worksheet:
            if isinstance(xls_worksheet, str):
                sh = wb.sheet_by_name(xls_worksheet)
            elif isinstance(xls_worksheet, int) or isinstance(xls_worksheet, float):
                sh = wb.sheet_by_index(xls_worksheet)
            else:
                print("file_to_iterable() given unimplemented xls worksheet type")
        else:
            # Assume it's just the first sheet
            sh = wb.sheet_by_index(0)

        auto_generated_csv_uri = os.path.join(folder, file_name + '_autogenerated_csv_at_' + pretty_time() + '.csv')
        auto_generated_csv_file = open(auto_generated_csv_uri, 'wb')
        wr = csv.writer(auto_generated_csv_file, quoting=csv.QUOTE_NONE) #  quoting=csv.QUOTE_ALL
        for rownum in xrange(sh.nrows):
            wr.writerow(sh.row_values(rownum))
        auto_generated_csv_file.close()
        file_uri = auto_generated_csv_uri


    data_type, num_rows, num_cols = determine_data_type_and_dimensions_for_read(file_uri)
    if declare_type:
        data_type = declare_type

    row_headers = []
    col_headers = []

    data = None
    if data_type == 'singleton':
        with open(file_uri, 'r') as f:
            for row in f:
                split_row = row.replace('\n','').split(',')
        data = split_row[0]
    elif data_type == '1d_list':
        data = []
        with open(file_uri, 'r') as f:
            for row in f:
                split_row = row.replace('\n','').split(',')
                data.append(split_row[0])
    elif data_type == '1d_dict':
        data = {}
        with open(file_uri, 'r') as f:
            for row in f:
                split_row = row.replace('\n','').split(',')
                data[split_row[0]] = split_row[1]
    elif data_type == '1d_odict':
        data = OrderedDict()
        with open(file_uri, 'r') as f:
            for row in f:
                split_row = row.replace('\n','').split(',')
                data[split_row[0]] = split_row[1]
    elif data_type == '2d_odict':
        data = OrderedDict()
        first_row = True
        with open(file_uri, 'r') as f:
            for row in f:
                split_row = row.replace('\n','').split(',')
                if first_row:
                    col_headers = split_row[1:]
                    first_row = False
                else:
                    row_odict = OrderedDict()
                    row_headers.append(split_row[0])
                    for col_header_index in range(len(col_headers)):
                        row_odict[col_headers[col_header_index]] = split_row[col_header_index + 1] # Plus 1 because the first in the split_row is the row_header
                    data[split_row[0]] = row_odict
    elif data_type == '2d_indexed_odict':
        data = OrderedDict()
        first_row = True
        with open(file_uri, 'r') as f:
            for row in f:
                split_row = row.replace('\n','').split(',')
                if first_row:
                    col_headers = split_row
                    first_row = False
                else:
                    row_odict = OrderedDict()
                    row_headers.append(split_row[0])
                    for col_header_index in range(len(col_headers)):
                        row_odict[col_headers[col_header_index]] = split_row[col_header_index]
                        data[split_row[0]] = row_odict
    elif data_type == '2d_list':
        data = []
        with open(file_uri, 'r') as f:
            for row in f:
                split_row = row.replace('\n','').split(',')
                data.append([i for i in split_row])
    elif data_type == '3d_odict_odict_list':
        data = OrderedDict()
        first_row = True
        with open(file_uri, 'r') as f:
            for row in f:
                split_row = row.replace('\n','').split(',')
                if first_row:
                    col_headers = split_row[1:]
                    first_row = False
                else:
                    row_odict = OrderedDict()
                    row_headers.append(split_row[0])
                    for col_header_index in range(len(col_headers)):
                        if '<^>' in split_row[col_header_index + 1]:
                            row_odict[col_headers[col_header_index]] = split_row[col_header_index + 1].split('<^>')
                        else:
                            row_odict[col_headers[col_header_index]] = split_row[col_header_index + 1] # Plus 1 because the first in the split_row is the row_header
                    data[split_row[0]] = row_odict
    elif data_type == 'horizontal_list':
        data = []
        first_row = True
        with open(file_uri, 'r') as f:
            for row in f:
                split_row = row.replace('\n','').split(',')
                if first_row:
                    col_headers = split_row
                    first_row = False
                    data = split_row
    elif data_type == 'indexed_column_headers_with_no_data':
        data = []
        first_row = True
        with open(file_uri, 'r') as f:
            for row in f:
                split_row = row.replace('\n','').split(',')
                if first_row:
                    col_headers = split_row
                    first_row = False
                    data = col_headers
                    # for entry in split_row:
                    #     data[entry] = ''
                else:
                    print("Shouldn't get here", data_type)
    elif data_type == 'column_headers_with_no_data':
        data = []
        with open(file_uri, 'r') as f:
            for row in f:
                split_row = row.replace('\n','').split(',')
                if first_row:
                    col_headers = split_row[1:]
                    first_row = False
                    data = split_row[1:]
                else:
                    print("Shouldn't get here", data_type)

    extra_return_dict = OrderedDict()
    extra_return_dict.update({'data_type':data_type,'num_rows':num_rows, 'num_cols':num_cols, 'row_headers':row_headers, 'col_headers':col_headers})

    if verbose:
        #print('\n\nmesh_utilities/utilities.file_to_iterable() loaded file from' + file_uri + 'and generated data as follows:\nParams:' + str(extra_return_dict) + '\nData:' + str(data) + '\n\n')
        print('\nReading file at ' + file_uri)
        print('data_type: ' + data_type + ',  shape: num_rows ' + str(num_rows) + ', num_cols ' + str(num_cols))
        print('col_headers: ' + ', '.join(col_headers))
        print('row_headers: ' + ', '.join(row_headers))
        print('python object loaded (next line):')
        print(data)

    if return_all_parts:
        return data, extra_return_dict
    else:
        return data






def determine_data_type_and_dimensions_for_read(file_uri):
    """
    Inspects a file of type to determine what the dimensions of the data are and make a guess at the best file_type to
    express the data as. The prediction is based on what content is in the upper-left cell and the dimensions.
    Useful when converting a python iterable to a file output.
    Function forked from original found in geoecon_utils library, used with permission open BSD from Justin Johnson.

    :param file_uri:
    :return: data_type, num_rows, num_cols
    """

    row_headers = []
    col_headers = []
    index_synonyms = ['', 'name', 'names', 'unique_name', 'unique_names', 'index', 'indices', 'id', 'ids', 'var_name', 'var_names']
    declare_type = None
    data = None
    blank_ul = False
    ul_index = None
    contains_3d_delimiter = False

    if os.path.exists(file_uri):
        with open(file_uri, 'r') as f: # Default behavior in open() assumes the first delimiter is \n and the sescond is ','. I extend this with extra_delimiters.
            for row in f:
                if '<^>' in row:
                    contains_3d_delimiter = True
        with open(file_uri, 'r') as f:
            col_lengths = []
            for row in f:
                split_row = row.replace('\n','').split(',')
                if split_row[0] not in index_synonyms:
                    col_lengths.append(len(split_row))
                else:
                    if split_row[0] == '':
                        blank_ul = True
                    else:
                        ul_index = split_row[0]

            num_rows = len(col_lengths)
            #num_rows = 0
            num_cols = 0
            if num_rows > 0:
                num_cols = max(col_lengths)
            else:
                num_cols = 1

            if declare_type:
                data_type = declare_type
            else:
                if num_cols == 1:
                    if num_rows == 1:
                        data_type = 'singleton'
                    elif num_rows == 0:
                        if blank_ul:
                            data_type = 'horizontal_list'
                        elif ul_index:
                            data_type = 'indexed_column_headers_with_no_data'
                        else:
                            data_type = 'column_headers_with_no_data'
                    else:
                        data_type = '1d_list'
                elif num_cols == 2:
                    if blank_ul:
                        print('A 2 column file cannot have a blank UL cell.')
                    if declare_type in ['dict']:
                        data_type = '1d_dict'
                        num_cols -= 1
                    else:
                        data_type = '1d_odict'
                        num_cols -= 1
                else:
                    if contains_3d_delimiter:
                        if blank_ul:
                            data_type = '3d_odict_odict_list'
                            num_cols -= 1
                        elif ul_index in index_synonyms:
                            data_type = '3d_odict_odict_list' # NOTE I don't Differentiate between indexed_3d_odict_odict_list and 3d_odict_odict_list
                        else:
                            if declare_type in ['odict_list']:
                                data_type = '3d_odict_list_list'
                                data = OrderedDict()
                                num_cols -= 1
                            elif declare_type in ['list_odict']:
                                data_type = '3d_list_odict_list'
                                num_rows -= 1 # This is only corrected here because all other cases are caught by checking the length of col_lengths.
                            else:
                                data_type = '3d_list'
                    else:
                        if blank_ul:
                            data_type = '2d_odict'
                            num_cols -= 1
                        elif ul_index:
                            data_type = '2d_indexed_odict'
                        else:
                            if declare_type in ['odict_list']:
                                data_type = '2d_odict_list'
                                num_cols -= 1
                            elif declare_type in ['list_odict']:
                                data_type = '2d_list_odict'
                                num_rows -= 1 # This is only corrected here because all other cases are caught by checking the length of col_lengths.
                            else:
                                data_type = '2d_list'
        return data_type, num_rows, num_cols

def convert_csv_to_html_table_string(csv_uri):
    reader = csv.reader(open(csv_uri))

    to_write = ''

    rownum = 0
    to_write += '<table>'
    for row in reader:  # Read a single row from the CSV file
        if rownum == 0:
            to_write += '<tr>'  # write <tr> tag
            for column in row:
                to_write += '<th>' + column + '</th>'
            to_write += '</tr>'
        else:
            to_write += '<tr>'
            for column in row:
                to_write += '<td>' + column + '</td>'
            to_write += '</tr>'
        rownum += 1
    to_write += '</table>'

    return to_write



def convert_to_bool(input):
    return str(input).lower() in ("yes", "true", "t", "1")

def get_bounding_box(dataset_uri, return_in_basemap_order=False):
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

    if return_in_basemap_order:
        bounding_box = [
            bounding_box[3], # llcrnrlat
            bounding_box[1], # urcrnrlat
            bounding_box[0], # llcrnrlon
            bounding_box[2], # urcrnrlon
        ]
        return bounding_box
    return bounding_box

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
        print(e)
        size_meters = (
                          abs(geotransform[1]) + abs(geotransform[5])) / 2.0 * linear_units

    # Close and clean up dataset
    gdal.Dataset.__swig_destroy__(dataset)
    dataset = None

    return size_meters



def as_array(uri, return_all_parts = False, verbose = False): #use GDAL to laod uri. By default only returns the array"
    # Simplest function for loading a geotiff as an array. returns only the array by defauls, ignoring the DS and BAND unless return_all_parts = True.
    ds = gdal.Open(uri)
    band = ds.GetRasterBand(1)
    try:
        array = band.ReadAsArray()
    except:
        warnings.warn('Failed to load all of the array. It may be too big for memory.')
        array = None

    # Close and clean up dataset
    if return_all_parts:
        return ds, band, array
    else:
        band = None
        gdal.Dataset.__swig_destroy__(ds)
        ds = None
        return array

def save_array_as_geotiff(array, out_uri, geotiff_uri_to_match=None, ds_to_match=None, band_to_match=None,
                          optimize_data_type=True, data_type_override=None, no_data_value_override=None,
                          geotransform_override=None, projection_override=None, n_cols_override=None,
                          n_rows_override=None, compression_method=None, verbose=None, set_inf_to_no_data_value=True):
    '''
    Saves an array as a geotiff at uri_out. Attempts to correctly deal with many possible data flaws, such as
    assigning a datatype to the geotiff that matches the required pixel depth. Also determines the best (according to me)
    no_data_value to use based on the dtype and range of the data
    '''
    execute_in_python = True

    n_cols = array.shape[1]
    n_rows = array.shape[0]
    geotransform = None
    projection = None
    data_type = None
    no_data_value = None

    if geotiff_uri_to_match != None:
        ds_to_match = gdal.Open(geotiff_uri_to_match)
        band_to_match = ds_to_match.GetRasterBand(1)

    # ideally, the function is passed a gdal dataset (ds) and the gdal band.
    if ds_to_match and band_to_match:
        n_cols = ds_to_match.RasterXSize
        n_rows = ds_to_match.RasterYSize
        data_type = band_to_match.DataType
        no_data_value = band_to_match.GetNoDataValue()
        geotransform = ds_to_match.GetGeoTransform()
        projection = ds_to_match.GetProjection()

    # Determine optimal data type and no_data_value. Note that it is best to calculate this anew to avoid inheriting a
    # too-small data type that clips data, and thus optimize_data_type is true by default.
    if optimize_data_type and False:  # TODOO Deactivated optimize_data_type due to unexpected crashes
        temp_data_type, temp_no_data_value = determine_optimal_data_type_and_no_data_value(array)
        if data_type_override:
            if temp_data_type == data_type_override:
                data_type = data_type_override
            else:
                warnings.warn('You specified an data_type_override but its not the same as the optimized data_type. Ensure this is correct')
                data_type = data_type_override
        else:
            data_type = temp_data_type
        if no_data_value_override:
            if temp_no_data_value == no_data_value_override:
                no_data_value = no_data_value_override
            else:
                warnings.warn('You specified an no_data_value_override but its not the same as the optimized no_data_value. Ensure this is correct')
                no_data_value = no_data_value_override
        else:
            no_data_value = temp_no_data_value
    elif data_type_override or no_data_value_override:
        if data_type_override:
            data_type = data_type_override
        else:
            data_type = 7  # set to largest bitsize
        if no_data_value_override:
            no_data_value = no_data_value_override
        else:
            no_data_value = 9223372036854775807
    else:
        data_type = 6
        no_data_value = -9999

    if not data_type:
        data_type = 7

    array = array.astype(gdal_number_to_numpy_type[data_type])

    if geotransform_override:
        if type(geotransform_override) is str:
            geotransform = config.common_geotransforms[geotransform_override]
        else:
            geotransform = geotransform_override

    if not geotransform:
        raise NameError('You must have a geotransform set, either in the geotiff_to_match, or manually as a 6-long list. '
                        'e.g. geotransform = (-180.0, 0.08333333333333333, 0.0, 90.0, 0.0, -0.08333333333333333) to '
                        'set to global extent with 5min cells or via a common keyword (defined in config).')

    if geotransform_override:
        if type(geotransform_override) is str:
            geotransform = config.common_geotransforms[geotransform_override]
        else:
            geotransform = geotransform_override

    if projection_override:
        if type(projection_override) is str:
            projection_override = config.common_epsg_codes_by_name[projection_override]
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(int(projection_override))
            projection = srs.ExportToWkt()

        else:
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(int(projection_override))
            projection = srs.ExportToWkt()

    if n_cols_override:
        n_cols = n_cols_override
    if n_rows_override:
        n_rows = n_rows_override

    if not projection:
        raise NameError('You must have a projection set, either in the geotiff_to_match, or manually via projection_override')

    # Process out_uri
    folder_uri, filename = os.path.split(out_uri)
    basename, file_extension = os.path.splitext(filename)
    if file_extension != '.tif':
        file_extension = '.tif'
        L.info('No file_extension specified. Assuming .tif.')
    if os.path.exists(folder_uri) or not folder_uri:
        'Everything is fine.'
    elif geotiff_uri_to_match:
        warnings.warn('Folder did not exist, assuming you want the same as the geotiff_uri_to_match.')
        folder_uri = os.path.split(geotiff_uri_to_match)[0]
        if not os.path.exists(folder_uri):
            raise NameError('Folder in geotiff_uri_to_match did not exist.')
    else:
        try:
            os.mkdir(folder_uri)
        except:
            raise NameError('Not able to create required folder for ' + folder_uri)

    processed_out_uri = os.path.join(folder_uri, basename + file_extension)

    dst_options = ['BIGTIFF=IF_SAFER', 'TILED=YES']
    if compression_method:
        dst_options.append('COMPRESS=' + compression_method)
        if compression_method == 'lzw':
            dst_options.append('PREDICTOR=2')

            # OUTDATED BUT HILARIOUS NOTE: When I compress an image with gdalwarp the result is often many times larger than the original!
            # By default gdalwarp operates on chunks that are not necessarily aligned with the boundaries of the blocks/tiles/strips of the output format, so this might cause repeated compression/decompression of partial blocks, leading to lost space in the output format.
            # Another possibility is to use gdalwarp without compression and then follow up with gdal_translate with compression:

    if set_inf_to_no_data_value:
        array[(array == np.inf) | (np.isneginf(array))] = no_data_value

    if execute_in_python:
        driver = gdal.GetDriverByName('GTiff')
        dst_ds = driver.Create(processed_out_uri, n_cols, n_rows, 1, data_type, dst_options)
        dst_ds.SetGeoTransform(geotransform)
        dst_ds.SetProjection(projection)
        if data_type > 5:
            dst_ds.GetRasterBand(1).SetNoDataValue(float(no_data_value))
        else:
            dst_ds.GetRasterBand(1).SetNoDataValue(int(no_data_value))
        dst_ds.GetRasterBand(1).WriteArray(array)
    # else:
    #     command_line_gdal_translate(array, processed_out_uri, tiled=True, compression_method=compression_method)



    if not os.path.exists(processed_out_uri):
        raise NameError('Failed to create geotiff ' + processed_out_uri + '.')

    if verbose:
        L.info('Saved ' + processed_out_uri + ' which had stats: ' + desc(array))


def create_buffered_polygon(input_uri, output_uri, buffer_cell_width):

    driver = ogr.GetDriverByName("ESRI Shapefile")
    input_ds = driver.Open(input_uri, 0)
    input_layer = input_ds.GetLayer()
    input_srs = input_layer.GetSpatialRef()

    # Assume output will have same srs as input
    output_srs = input_srs

    # Create the output Layer
    output_ds = driver.CreateDataSource(output_uri)
    output_layer = output_ds.CreateLayer("buffered", output_srs, geom_type=ogr.wkbMultiPolygon)

    # Add input Layer Fields to the output Layer
    input_layer_def = output_layer.GetLayerDefn()
    for i in range(0, input_layer_def.GetFieldCount()):
        field_def = input_layer_def.GetFieldDefn(i)
        output_layer.CreateField(field_def)

    # Get the output Layer's Feature Definition
    output_layer_def = output_layer.GetLayerDefn()

    # Add features to the ouput Layer
    for i in range(0, input_layer.GetFeatureCount()):
        # Get the input Feature
        input_feature = input_layer.GetFeature(i)
        # Create output Feature
        output_feature = ogr.Feature(output_layer_def)
        # Add field values from input Layer
        for i in range(0, output_layer_def.GetFieldCount()):
            output_feature.SetField(output_layer_def.GetFieldDefn(i).GetNameRef(), input_feature.GetField(i))
        # Set geometry as centroid
        geom = input_feature.GetGeometryRef()
        centroid = geom.Centroid()
        buffered_geom = geom.Buffer(buffer_cell_width)
        output_feature.SetGeometry(buffered_geom)
        # Add new feature to output Layer
        output_layer.CreateFeature(output_feature)

    # Close datasources
    input_ds.Destroy()
    output_ds.Destroy()



def clip_by_shape_with_buffered_intermediate_uri(src_uri, shp_uri, output_uri, match_uri, *args, **kwargs):
    """
    For use when reprojecting the whole af is not practical, eg selecting a country out of MODIS and then clip reprojecting.
    
    Steps involved:
    
        1. reproject shapefile to match src_uri
        2. create buffer of 1
        3. use 2 to clip src_uri
        4. resample and reproject to match desired resolution
        5. clip with shp_uri
    
    """
    src_ds = gdal.Open(src_uri)
    srs_input = osr.SpatialReference()
    srs_input.ImportFromWkt(src_ds.GetProjectionRef())
    input_wkt = srs_input.ExportToWkt()
    src_ds = None

    resampling_method = kwargs.get('resampling_method', 'nearest')

    # Step 1, reproject shapefile to match src_uri
    aoi_reprojected_uri = shp_uri.replace('.shp', '_reprojected.shp')
    reproject_datasource_uri(shp_uri, input_wkt, aoi_reprojected_uri)

    # Step 2, create a buffered version of the polygon.
    buffer_resolution = get_cell_size_from_uri(src_uri)
    buffer_cell_width = buffer_resolution * 12
    buffered_polygon_uri = os.path.splitext(aoi_reprojected_uri)[0] + '_buffered' + os.path.splitext(aoi_reprojected_uri)[1]
    if os.path.exists(buffered_polygon_uri):
        os.remove(buffered_polygon_uri)
    create_buffered_polygon(aoi_reprojected_uri, buffered_polygon_uri, buffer_cell_width)

    # Step 3, Clip src using buffered shapefile
    buffered_clip_uri = os.path.join(os.path.split(aoi_reprojected_uri)[0], 'raster_buffered_clipped.tif')
    clip_dataset_uri(src_uri, buffered_polygon_uri, buffered_clip_uri, assert_projections=False, all_touched=True) # , assert_projections=False

    # Step 4: Reproject to projection of original shape file
    penultimate_uri = os.path.join(os.path.split(aoi_reprojected_uri)[0], 'raster_penultimate.tif')
    original_ds = gdal.Open(src_uri) # For now, just assume that the shape_ds has the crs you want.
    shape_ds = ogr.Open(shp_uri)
    srs = osr.SpatialReference()
    srs.ImportFromWkt(shape_ds.GetLayer(0).GetSpatialRef().__str__())
    output_wkt = srs.ExportToWkt()
    resolution = get_cell_size_from_geotransform_uri(match_uri)
    reproject_dataset_uri(buffered_clip_uri, resolution, output_wkt, resampling_method, penultimate_uri)

    # Step 5: Clip final product with original shapefile
    # TODO FLAW, clip will shrink the final output raster if the aoi here bounds it further when applied at this higher resolution. need to come up with a preserve-bb option for clip with intermediate. Probably fully replace pgp clip.
    clip_dataset_uri(penultimate_uri, shp_uri, output_uri, match_uri, all_touched=True)

    # Cleanup
    os.remove(buffered_polygon_uri)
    os.remove(buffered_clip_uri)
    os.remove(penultimate_uri)
    return

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
            print(
                '%d features out of %d were unable to be transformed and are'
                ' not in the output dataset at %s', error_count,
                original_layer.GetFeatureCount(), output_uri)
        original_layer = None

    return output_datasource




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
        "nearest": gdal.GRA_NearestNeighbour,
        "nearest_neighbor": gdal.GRA_NearestNeighbour,
        "bilinear": gdal.GRA_Bilinear,
        "cubic": gdal.GRA_Cubic,
        "cubic_spline": gdal.GRA_CubicSpline,
        "lanczos": gdal.GRA_Lanczos,
        "average": gdal.GRA_Average,
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
                print(
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

class DatasetUnprojected(Exception):
    """An exception in case a dataset is unprojected"""
    pass


class DifferentProjections(Exception):
    """An exception in case a set of datasets are not in the same projection"""
    pass



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
        print(
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


def clip_dataset_uri(
        source_dataset_uri, aoi_datasource_uri, out_dataset_uri,
        assert_projections=True, process_pool=None, all_touched=False, **kwargs):
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

    output_dataset = pg.new_raster_from_base(
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
        mask_dataset = pg.new_raster_from_base(
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
        print("this call is vectorizing which is deprecated and slow")
        dataset_pixel_op = numpy.vectorize(
            dataset_pixel_op, otypes=[_gdal_to_numpy_type(output_band)])

    last_time = time.time()

    last_row_block_width = None
    last_col_block_width = None
    for row_block_index in xrange(n_row_blocks):
        row_offset = row_block_index * rows_per_block
        row_block_width = n_rows - row_offset
        if row_block_width > rows_per_block:
            row_block_width = rows_per_block

        for col_block_index in xrange(n_col_blocks):
            col_offset = col_block_index * cols_per_block
            col_block_width = n_cols - col_offset
            if col_block_width > cols_per_block:
                col_block_width = cols_per_block

            current_time = time.time()
            if current_time - last_time > 5.0:
                print(
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

            for dataset_index in xrange(len(aligned_bands)):
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
                print("couldn't delete file %s", temp_dataset_uri)
    calculate_raster_stats_uri(dataset_out_uri
                               )




def temporary_filename(suffix=''):
    """Get path to new temporary file that will be deleted on program exit.

    Returns a temporary filename using mkstemp. The file is deleted
    on exit using the atexit register.

    Keyword Args:
        suffix (string): the suffix to be appended to the temporary file

    Returns:
        fname: a unique temporary filename
    """
    # file_handle, path = tempfile.mkstemp(suffix=suffix)
    # os.close(file_handle)
    #
    def remove_file(path):
        """Function to remove a file and handle exceptions to register
            in atexit."""
        try:
            os.remove(path)
        except OSError:
            # This happens if the file didn't exist, which is okay because
            # maybe we deleted it in a method
            pass

    path = ruri('temp.tif')

    atexit.register(remove_file, path)
    return path


def is_dataset_projected(input_uri):
    dataset = gdal.Open(input_uri)
    projection_as_str = dataset.GetProjection()
    dataset_sr = osr.SpatialReference()
    dataset_sr.ImportFromWkt(projection_as_str)
    if dataset_sr.IsProjected():
        return True
    else:
        return False

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
        raise exceptions.IOError(error_message)


def assert_dataset_is_projected(input_uri):
    dataset = gdal.Open(input_uri)
    projection_as_str = dataset.GetProjection()
    dataset_sr = osr.SpatialReference()
    dataset_sr.ImportFromWkt(projection_as_str)
    if dataset_sr.IsProjected():
        return True
    else:
        raise NameError('Dataset ' + input_uri + ' is unprojected.')

def assert_datasets_in_same_projection(dataset_uri_list):
    """Assert that provided datasets are all in the same projection.

    Tests if datasets represented by their uris are projected and in
    the same projection and raises an exception if not.

    Args:
        dataset_uri_list (list): (description)

    Returns:
        is_true (boolean): True (otherwise exception raised)

    Raises:
        DatasetUnprojected: if one of the datasets is unprojected.
        DifferentProjections: if at least one of the datasets is in
            a different projection
    """
    dataset_list = [gdal.Open(dataset_uri) for dataset_uri in dataset_uri_list]
    dataset_projections = []

    unprojected_datasets = set()

    for dataset in dataset_list:
        projection_as_str = dataset.GetProjection()
        dataset_sr = osr.SpatialReference()
        dataset_sr.ImportFromWkt(projection_as_str)
        if not dataset_sr.IsProjected():
            unprojected_datasets.add(dataset.GetFileList()[0])
        dataset_projections.append((dataset_sr, dataset.GetFileList()[0]))

    if len(unprojected_datasets) > 0:
        raise DatasetUnprojected(
            "These datasets are unprojected %s" % (unprojected_datasets))

    for index in range(len(dataset_projections)-1):
        if not dataset_projections[index][0].IsSame(
                dataset_projections[index+1][0]):
            print(
                "These two datasets might not be in the same projection."
                " The different projections are:\n\n'filename: %s'\n%s\n\n"
                "and:\n\n'filename:%s'\n%s\n\n",
                dataset_projections[index][1],
                dataset_projections[index][0].ExportToPrettyWkt(),
                dataset_projections[index+1][1],
                dataset_projections[index+1][0].ExportToPrettyWkt())

    for dataset in dataset_list:
        # Close and clean up dataset
        gdal.Dataset.__swig_destroy__(dataset)
    dataset_list = None
    return True

def get_equatorial_pixel_spacing_from_angular_unit(input_uri):
    cell_size_in_angular_units = get_cell_size_from_geotransform_uri(input_uri)
    size_of_one_arcdegree_at_equator_in_meters = 111319.49079327358  # Based on (2 * math.pi * 6378.137*1000) / 360
    return size_of_one_arcdegree_at_equator_in_meters * cell_size_in_angular_units

def get_cell_size_from_geotransform_uri(dataset_uri):
    # Assume linear unit is 1 meter and that the geotransofrm is defined in angular units.
    dataset = gdal.Open(dataset_uri)
    srs = osr.SpatialReference()
    srs.SetProjection(dataset.GetProjection())

    if dataset is None:
        raise IOError(
            'File not found or not valid dataset type at: %s' % dataset_uri)
    linear_units = 1.0
    linear_units_from_srs = srs.GetLinearUnits()
    if linear_units_from_srs != linear_units:
        raise NameError('You are attempting to get cellsize from the geotransform, but this data is projected already with a different linear unit than 1.')
    geotransform = dataset.GetGeoTransform()

    # take absolute value since sometimes negative widths/heights
    try:
        numpy.testing.assert_approx_equal(
            abs(geotransform[1]), abs(geotransform[5]))
        size_meters = abs(geotransform[1]) * linear_units
    except AssertionError as e:
        print(e)
        size_meters = (
                          abs(geotransform[1]) + abs(geotransform[5])) / 2.0 * linear_units

    # Close and clean up dataset
    gdal.Dataset.__swig_destroy__(dataset)
    dataset = None

    return size_meters


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
            range(len(dataset_uri_list))):
        current_time = time.time()
        if current_time - last_time > 5.0:
            last_time = current_time
            print(
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
        pg.new_raster_from_base_uri(
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

def resize_and_resample_dataset_uri(
        original_dataset_uri, bounding_box, out_pixel_size, output_uri,
        resample_method):
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
        "nearest_neighbor": gdal.GRA_NearestNeighbour,
        "bilinear": gdal.GRA_Bilinear,
        "cubic": gdal.GRA_Cubic,
        "cubic_spline": gdal.GRA_CubicSpline,
        "lanczos": gdal.GRA_Lanczos,
        "average": gdal.GRA_Average,
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
        print(
            "bounding_box is so small that x dimension rounds to 0; "
            "clamping to 1.")
        new_x_size = 1
    if new_y_size == 0:
        print(
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
            if ((current_time - reproject_callback.last_time) > 5.0 or
                    (df_complete == 1.0 and reproject_callback.total_time >= 5.0)):
                print(
                    "ReprojectImage %.1f%% complete %s, psz_message %s",
                    df_complete * 100, p_progress_arg[0], psz_message)
                reproject_callback.last_time = current_time
                reproject_callback.total_time += current_time
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



def reproject_to_cylindrical(input_uri, output_uri=None, discard_backup=True, method='nearest_neighbor'):
    # Useful because matches the wgs no projected projection, allowing for raster math with accurate grid-cells.
    # If output_uri = None, overwrites input.
    temp_uri = rsuri(input_uri, 'reprojecting')

    # PERFORMANCE, make this copy conditional.
    shutil.copy(input_uri, temp_uri)

    ds = gdal.Open(temp_uri)
    projection = ds.GetProjection()
    ds = None

    if 'PROJECTION[' not in projection:
        pixel_spacing = get_equatorial_pixel_spacing_from_angular_unit(temp_uri)
    else:
        pixel_spacing = get_cell_size_from_uri(temp_uri)

    wkt = get_wkt_from_epsg_code(32662) # DEPRECATED, but accurate enough for global work. the newer 32663 is not regstered in eg QGIS

    if output_uri:
        try:
            reproject_dataset_uri(
                temp_uri, pixel_spacing, wkt, method,
                output_uri)
        except:
            raise NameError('Unable to reproject ' + input_uri)
    else:
        # reproject_dataset_uri(
        #     temp_uri, pixel_spacing, wkt, method,
        #     input_uri)
        try:
            reproject_dataset_uri(
                temp_uri, pixel_spacing, wkt, method,
                input_uri)
        except:
            raise NameError('Unable to reproject ' + input_uri)


    if discard_backup:
        os.remove(temp_uri)



def reproject_shapefile_to_cylindrical(input_uri, output_uri=None, discard_backup=True, method='nearest_neighbor'):
    # Useful because matches the wgs no projected projection, allowing for raster math with accurate grid-cells.
    # If output_uri = None, overwrites input.
    output_wkt = get_wkt_from_epsg_code(32662) # DEPRECATED, but accurate enough for global work. the newer 32663 is not regstered in eg QGIS

    if not output_uri:
        output_uri = rsuri(input_uri, 'reprojecting')

    # ds = gdal.Open(output_uri)
    # projection = ds.GetProjection()
    # ds = None

    try:
        reproject_datasource_uri(input_uri, output_wkt, output_uri)

    except:
        raise NameError('Unable to reproject ' + input_uri)


    if not output_uri:
        temp_uri = rsuri(input_uri, 'reprojecting_temp')
        os.rename(input_uri, temp_uri)
        os.rename(output_uri, input_uri)

        if discard_backup:
            os.remove(temp_uri)



def get_wkt_from_epsg_code(epsg_code):
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(int(epsg_code))
    wkt = srs.ExportToWkt()

    return wkt

def suri(input_uri, input_string):
    '''Shortcut function to insert_string_before_ext'''
    return insert_string_before_ext(input_uri, input_string)


def insert_string_before_ext(input_uri, input_string):
    # The following helper functions are useful for quickly creating temporary files that resemble but dont overwrite
    # their input. The one confusing point i have so far is that calling this on a folder creates a string representing
    # a subfolder, not an in-situ new folder.

    # split_uri = os.path.splitext(input_uri)
    # return os.path.join(split_uri[0] + '_' + str(input_string) + split_uri[1])
    split_uri = os.path.splitext(input_uri)
    if split_uri[1]:
        output_uri = split_uri[0] + '_' + str(input_string) + split_uri[1]
    else:
        output_uri = split_uri[0] + str(input_string)
    return output_uri


def ruri(input_uri):
    '''Shortcut function to insert_random_string_before_ext'''
    return insert_random_string_before_ext(input_uri)

def random_alphanumeric_string(length=6):
    """Returns randomly chosen, lowercase characters as a string with given length. Uses chr(int) to convert random."""
    start_of_numerals_ascii_int = 48
    start_of_uppercase_letters_ascii_int = 65
    start_of_lowercase_letters_ascii_int = 97
    alphanumeric_ascii_ints = list(range(start_of_numerals_ascii_int, start_of_numerals_ascii_int + 10)) + list(range(start_of_uppercase_letters_ascii_int, start_of_uppercase_letters_ascii_int + 26)) + list(range(start_of_lowercase_letters_ascii_int, start_of_lowercase_letters_ascii_int + 26))
    alphanumeric_lowercase_ascii_ints = list(range(start_of_numerals_ascii_int, start_of_numerals_ascii_int + 10)) + list(range(start_of_lowercase_letters_ascii_int, start_of_lowercase_letters_ascii_int + 26))
    alphanumeric_ascii_symbols = [chr(i) for i in alphanumeric_ascii_ints]
    alphanumeric_lowercase_ascii_symbols = [chr(i) for i in alphanumeric_lowercase_ascii_ints]  # numbers are lowercase i assume...
    random_chars = [random.choice(alphanumeric_lowercase_ascii_symbols) for i in range(length)]

    return ''.join(random_chars)

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


def random_string():
    """Return random string of numbers of expected length. Used in uri manipulation."""
    return pretty_time(format='full') + str(random_alphanumeric_string(3))

def insert_random_string_before_ext(input_uri):
    split_uri = os.path.splitext(input_uri)
    if split_uri[1]:
        output_uri = split_uri[0] + '_' + random_string() + split_uri[1]
    else:
        # If it's a folder, just tack it onto the end
        output_uri = split_uri[0] + '_' + random_string()
    return output_uri


def rsuri(input_uri, input_string):
    return insert_string_and_random_string_before_ext(input_uri, input_string)


def insert_string_and_random_string_before_ext(input_uri, input_string):
    split_uri = os.path.splitext(input_uri)
    if split_uri[1]:
        output_uri = split_uri[0] + '_' + str(input_string) + '_' + random_string() + split_uri[1]
    else:
        output_uri = split_uri[0] + '_' + str(input_string) + '_' + random_string()
    return output_uri


gdal_number_to_numpy_type = {
    1: numpy.uint8,
    2: numpy.uint16,
    3: numpy.int16,
    4: numpy.uint32,
    5: numpy.int32,
    6: numpy.float32,
    7: numpy.float64,
    8: numpy.complex64,
    9: numpy.complex64,
    10: numpy.complex64,
    11: numpy.complex128
}



# Eventually expand this. probably all work but i want to check.
gdal_readable_formats = '''.tif
.bil
.adf
.asc'''


gdal_readable_formats_shortnames = '''AAIGrid
ACE2
ADRG
AIG
ARG
BLX
BAG
BMP
BSB
BT
CPG
CTG
DIMAP
DIPEx
DODS
DOQ1
DOQ2
DTED
E00GRID
ECRGTOC
ECW
EHdr
EIR
ELAS
ENVI
ERS
FAST
GPKG
GEORASTER
GRIB
GMT
GRASS
GRASSASCIIGrid
GSAG
GSBG
GS7BG
GTA
GTiff
GTX
GXF
HDF4
HDF5
HF2
HFA
IDA
ILWIS
INGR
IRIS
ISIS2
ISIS3
JDEM
JPEG
JPEG2000
JP2ECW
JP2KAK
JP2MrSID
JP2OpenJPEG
JPIPKAK
KEA
KMLSUPEROVERLAY
L1B
LAN
LCP
Leveller
LOSLAS
MBTiles
MAP
MEM
MFF
MFF2 (HKV)
MG4Lidar
MrSID
MSG
MSGN
NDF
NGSGEOID
NITF
netCDF
NTv2
NWT_GRC
NWT_GRD
OGDI
OZI
PCIDSK
PCRaster
PDF
PDS
PLMosaic
PostGISRaster
Rasterlite
RIK
RMF
ROI_PAC
RPFTOC
RS2
RST
SAGA
SAR_CEOS
SDE
SDTS
SGI
SNODAS
SRP
SRTMHGT
USGSDEM
VICAR
VRT
WCS
WMS
XYZ
ZMap'''
gdal_readable_formats = gdal_readable_formats.split('\n')








# # Example usage
# iterable = file_to_iterable('2d_list.csv', verbose=True)
# returned = iterable_to_csv(iterable, 'created_output_' + pretty_time() + '.csv', verbose=True)
#
