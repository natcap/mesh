# coding=utf-8

from collections import OrderedDict
import os
import datetime
import json
import csv
import platform
import sys
import shutil

from osgeo import gdal, ogr, osr
from PyQt4.QtGui import *
import xlrd
import pygeoprocessing.geoprocessing
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
        L.warn(e)
        size_meters = (
                          abs(geotransform[1]) + abs(geotransform[5])) / 2.0 * linear_units

    # Close and clean up dataset
    gdal.Dataset.__swig_destroy__(dataset)
    dataset = None

    return size_meters




def pretty_time():
    # Returns a nicely formated string of YEAR-MONTH-DAY_HOURS-MIN-SECONDS based on the the linux timestamp
    return str(datetime.datetime.now()).replace(" ","_").replace(":","-").split(".")[0]

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
        dst_ds.GetRasterBand(1).SetNoDataValue(no_data_value)
        dst_ds.GetRasterBand(1).WriteArray(array)
    # else:
    #     command_line_gdal_translate(array, processed_out_uri, tiled=True, compression_method=compression_method)



    if not os.path.exists(processed_out_uri):
        raise NameError('Failed to create geotiff ' + processed_out_uri + '.')

    if verbose:
        L.info('Saved ' + processed_out_uri + ' which had stats: ' + desc(array))

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
