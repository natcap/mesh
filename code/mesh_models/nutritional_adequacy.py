import sys, os, logging, json, threading, time, platform, traceback, tempfile, locale, imp, errno, shutil, codecs, datetime, subprocess, math, random
from collections import OrderedDict, deque
from types import StringType

import pygeoprocessing as pg

from pprint import pprint as pp
from PyQt4 import QtGui
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from matplotlib.figure import Figure
# from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas

from matplotlib import rcParams
rcParams.update({'figure.autolayout': True}) # This line makes matplotlib automatically change the fig size according to legends, labels etc.

import gdal
import numpy as np

import pandas as pd

from code.mesh_utilities import config
from code.mesh_utilities import utilities
from code.mesh_utilities import data_creation


LOGGER = config.LOGGER
LOGGER.setLevel(logging.INFO)
ENCODING = sys.getfilesystemencoding()



            # TODO 1. This model needs to connect to the LUC change and how it affects how much cropland grows food.
def create_default_kw(calling_ui=None):
    if calling_ui:
        kw = generate_default_kw_from_ui(calling_ui)
    else:
        kw = generate_default_kw_from_nothing()

    return kw

def generate_default_kw_from_ui(ui):
    # Take an reference to the mesh application, analyze it, use results to return a new kw args specific to the users' needs
    kw = OrderedDict()
    ## AVailable from ui object
    # project_name
    # project_aoi
    # settings_folder
    # default_setup_files_folder
    # decision_contexts
    # external_drivers
    # assessment_times
    # base_data_folder


    # kw['lulc_uri'] = os.path.join(ui.base_data_folder, 'lulc', 'lulc_modis_2012.tif')
    kw['workspace_dir'] = os.path.join(ui.project_folder, 'output/model_setup_runs/nutritional_adequacy')
    kw['lulc_uri'] = os.path.join(ui.project_folder, 'input/baseline', 'lulc.tif')
    kw['crop_maps_folder'] = os.path.join(ui.base_data_folder, 'models', 'nutritional_adequacy', 'crop_data')
    kw['nutritional_content_table_uri'] = os.path.join(ui.project_folder, 'input/baseline', 'nutritional_contents.csv')
    kw['nutritional_requirements_table_uri'] = os.path.join(ui.project_folder,'input/baseline',  'nutrition_requirements_by_demographics.csv')
    kw['population_uri'] = os.path.join(ui.project_folder, 'input/baseline', 'population.tif')
    kw['economic_value_table_uri'] = os.path.join(ui.project_folder, 'input/baseline',  'economics_table.csv')
    kw['aoi_uri'] = ui.project_aoi



    return kw

def generate_default_kw_from_nothing():
    kw = OrderedDict()
    print('nyi')
    return kw


def create_data():
    """
    SHORTCUT Went manual here to speed up volta processing, but this should eventually be made programatic and break reliance on geoecon_utils
    :return:
    """
    project_folder = 'C:/mesh_alpha_0.2/projects/volta/'
    bulk_data_folder = 'E:/bulk_data/'
    input_folder = project_folder + 'input/Baseline/'
    output_folder = project_folder + 'input/Baseline/'
    bounding_box = (-5.35, 14.866667, 2.266667, 5.775)

    lulc_uri = input_folder + 'lulc_2012.tif'
    lulc = utilities.as_array(lulc_uri)


    crop_extent_1km_uri = bulk_data_folder + 'iiasa-ifpri_cropland/cropland_hybrid_14052014v8/Hybrid_14052014V8.tif'
    crop_extent_1km_clipped_uri = output_folder + 'cropland_extent_1km.tif'

    utilities.clip_by_coords_with_gdal(crop_extent_1km_uri, crop_extent_1km_clipped_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3], projection='WGS84')

    maize_input_uri = 'C:mesh_alpha_0.2/Base_Data/nutrition/crop_data/maize/maize_HarvestedAreaFraction.tif'
    maize_5min_uri = input_folder + 'maize_HarvestedAreaFraction_5min.tif'
    utilities.clip_by_coords_with_gdal(maize_input_uri, maize_5min_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3], projection='WGS84')

    population_uri = input_folder + 'pop.tif'

    lulc_uri = input_folder + 'lulc_2012.tif'
    lulc_1km_uri = input_folder + 'lulc_1km_2012.tif'

    bounding_box_pop = pg.get_bounding_box(lulc_uri)
    print('bounding_box_pop', bounding_box_pop)

    pg.resize_and_resample_dataset_uri(lulc_uri, bounding_box_pop, 847.704968, lulc_1km_uri, 'bilinear')

    lulc = utilities.as_array(lulc_uri)




def execute(args, ui):
    if not args:
        args = create_default_kw(ui)

    try:
        args['output_folder'] = args['workspace_dir']
    except:
        'cant'

    try:
        os.makedirs(os.path.join(args['output_folder'], 'YieldTonsPerCell'))
    except:
        'already there'
    try:
        os.makedirs(os.path.join(args['output_folder'], 'nutrient_production'))
    except:
        'already there'
    try:
        os.makedirs(os.path.join(args['output_folder'], 'crop_production_and_harvested_area'))
    except:
        'already there'

    ui.update_run_log('Calculating crop-specific production')


    bounding_box = data_creation.get_datasource_bounding_box(ui.root_app.project_aoi)
    # bounding_box = (-5.35, 14.866667, 2.266667, 5.775)
    ui.update_run_log('Loading input maps. Bounding box set to: ' + str(bounding_box))


    try:
        os.remove(os.path.join(args['output_folder'], 'crop_proportion_baseline_500m.tif'))
        os.remove(os.path.join(args['output_folder'], 'crop_proportion_baseline_1km.tif'))
        os.remove(os.path.join(args['output_folder'], 'crop_proportion_500m.tif'))
        os.remove(os.path.join(args['output_folder'], 'crop_proportion_1km.tif'))


    except:
        'no'

    lulc_baseline = utilities.as_array(args['lulc_uri'])
    crop_proportion_baseline_500m_uri = os.path.join(args['output_folder'], 'YieldTonsPerCell', 'crop_proportion_baseline_500m.tif')
    crop_proportion_baseline = np.where(lulc_baseline == 12, 1.0, 0.0)
    crop_proportion_baseline = np.where(lulc_baseline == 14, .5, crop_proportion_baseline)

    # BUG If the files are not in the normal folder and onl linked to, it fails to find them.

    utilities.save_array_as_geotiff(crop_proportion_baseline, crop_proportion_baseline_500m_uri, args['lulc_uri'])
    crop_proportion_baseline_1km_uri = os.path.join(args['output_folder'], 'YieldTonsPerCell', 'crop_proportion_baseline_1km.tif')

    population_bounding_box = utilities.get_bounding_box(args['population_uri'])
    cell_size = utilities.get_cell_size_from_uri(args['population_uri'])
    pg.resize_and_resample_dataset_uri(crop_proportion_baseline_500m_uri, population_bounding_box, cell_size, crop_proportion_baseline_1km_uri, 'bilinear')


    if False:
        # TODO Mixes scenario vsbaseline
        lulc_scenario = utilities.as_array(args['lulc_uri'])

        crop_proportion = np.where(lulc == 12, 1.0, 0.0)
        crop_proportion = np.where(lulc == 14, .5, crop_proportion)
        crop_proportion_500m_uri = os.path.join(args['output_folder'], 'YieldTonsPerCell', 'crop_proportion_500m.tif')
        utilities.save_array_as_geotiff(crop_proportion, crop_proportion_500m_uri, args['lulc_uri'])
        crop_proportion_1km_uri = os.path.join(args['output_folder'], 'YieldTonsPerCell', 'crop_proportion_1km.tif')
        pg.resize_and_resample_dataset_uri(crop_proportion_500m_uri, population_bounding_box, cell_size, crop_proportion_1km_uri, 'bilinear')

        crop_proportion_baseline_1km = utilities.as_array(crop_proportion_baseline_1km_uri)
        crop_proportion_1km = utilities.as_array(crop_proportion_1km_uri)

        change_ratio = np.where(crop_proportion_baseline_1km > 0, crop_proportion_1km / crop_proportion_baseline_1km, 1.0)

        change_ratio_mean = np.mean(change_ratio)



    ui.update_run_log('Loading input maps')
    crop_maps_folder = args['crop_maps_folder']
    nutritional_content_odict = utilities.file_to_python_object(args['nutritional_content_table_uri'])  # outputs as OrderedDict([('almond', OrderedDict([('fraction_refuse', '0.6'), ('Protein', '212.2'), ('Lipid', '494.2'), etc
    nutritional_requirements_odict = utilities.file_to_python_object(args['nutritional_requirements_table_uri'])
    population = utilities.as_array(args['population_uri'])
    demographic_groups_list = args['demographic_groups_list']
    demographics_folder = args['demographics_folder']

    ui.update_run_log('Calculating crop-specific production')
    harvested_area_filenames = []
    yield_per_ha_filenames = []
    yield_tons_per_cell_filenames = []
    ha_array = 0
    yield_per_ha_array = 0

    for folder_name in os.listdir(crop_maps_folder):
        print('folder_name', folder_name)
        current_folder = os.path.join(crop_maps_folder, folder_name)
        if os.path.isdir(current_folder):
            for filename in os.listdir(current_folder):

                current_file_uri = os.path.join(current_folder, filename)

                print('current_file_uri', current_file_uri)
                clipped_uri = os.path.join(args['output_folder'], 'crop_production_and_harvested_area',filename)
                current_crop_name = filename.split('_', 1)[0]
                test_file_uri = os.path.join(args['output_folder'], 'crop_production_and_harvested_area', current_crop_name + '_YieldTonsPerCell.tif')
                #if not os.path.exists(test_file_uri):
                if True:
                    if filename.endswith('HarvestedAreaHectares.tif'):
                        #if not os.path.exists(clipped_uri) or True:
                        if True:
                            dataset_uri_list = [args['lulc_uri'], current_file_uri]
                            resample_method_list = ['nearest', 'nearest']
                            out_pixel_size = pg.get_cell_size_from_uri(args['lulc_uri'])
                            mode = 'dataset'
                            dataset_to_align_index = 0
                            dataset_to_bound_index = 0
                            aoi_uri = args['aoi_uri']
                            dataset_out_uri_list = [args['lulc_uri'].replace('.tif', '_aligned.tif'), current_file_uri.replace('.tif', '_aligned.tif')]

                            # pg.clip_dataset_uri(current_file_uri, clipped_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3])
                            pg.align_dataset_list(dataset_uri_list=dataset_uri_list,
                                                  resample_method_list=resample_method_list,
                                                  out_pixel_size=out_pixel_size,
                                                  mode=mode,
                                                  dataset_to_align_index=dataset_to_align_index,
                                                  dataset_to_bound_index=dataset_to_bound_index,
                                                  aoi_uri=aoi_uri,
                                                  dataset_out_uri_list=dataset_out_uri_list,
                                                  assert_datasets_projected=False)

                            pg.clip_dataset_uri(current_file_uri, ui.root_app.project_aoi, clipped_uri, assert_projections=False)
                        harvested_area_filenames.append(clipped_uri)
                        ha_array = utilities.as_array(clipped_uri)
                        # ha_array *= change_ratio
                        # utilities.save_array_as_geotiff(ha_array, clipped_uri, clipped_uri)
                    if filename.endswith('YieldPerHectare.tif'):
                        #if not os.path.exists(clipped_uri) or True:
                        if True:
                            pg.clip_dataset_uri(current_file_uri, ui.root_app.project_aoi, clipped_uri, assert_projections=False)
                            # utilities.clip_dataset_uri(current_file_uri, clipped_uri, bounding_box[0], bounding_box[1], bounding_box[2], bounding_box[3])
                        yield_per_ha_filenames.append(clipped_uri)
                        yield_per_ha_array = utilities.as_array(clipped_uri)

                        yield_tons_per_cell_uri = os.path.join(args['output_folder'], 'YieldTonsPerCell', current_crop_name + '_YieldTonsPerCell.tif')

                        #if not os.path.exists(yield_tons_per_cell_uri) or True:
                        if True:
                            yield_tons_per_cell_array = yield_per_ha_array * ha_array
                            utilities.save_array_as_geotiff(yield_tons_per_cell_array, yield_tons_per_cell_uri, clipped_uri)
                        yield_tons_per_cell_filenames.append(yield_tons_per_cell_uri)

        ui.update_run_log('Creating yield (tons) map for ' + folder_name)

    match_5min_uri = os.path.join(args['output_folder'], 'crop_production_and_harvested_area', 'maize_HarvestedAreaHectares.tif')
    # match_5min_uri = os.path.join(ui.root_app.base_data_folder, 'models/crop_production/global_dataset/observed_yield/rice_yield_map.tif')
    match_array = utilities.as_array(match_5min_uri)

    if True:
        print('match_array.shape', match_array.shape)
    #if not os.path.exists(os.path.join(args['output_folder'], 'nutrient_production', 'Energy_per_cell_5min.tif') or True):
        Energy = np.zeros(match_array.shape)
        Protein = np.zeros(match_array.shape)
        VitA = np.zeros(match_array.shape)
        VitC = np.zeros(match_array.shape)
        VitE = np.zeros(match_array.shape)
        Thiamin = np.zeros(match_array.shape)
        Riboflavin = np.zeros(match_array.shape)
        Niacin = np.zeros(match_array.shape)
        VitB6 = np.zeros(match_array.shape)
        Folate = np.zeros(match_array.shape)
        VitB12 = np.zeros(match_array.shape)
        Ca = np.zeros(match_array.shape)
        Ph = np.zeros(match_array.shape)
        Mg = np.zeros(match_array.shape)
        K = np.zeros(match_array.shape)
        Na = np.zeros(match_array.shape)
        Fe = np.zeros(match_array.shape)
        Zn = np.zeros(match_array.shape)
        Cu = np.zeros(match_array.shape)


        for i in range(len(yield_tons_per_cell_filenames)):
            current_crop_name = os.path.splitext(os.path.split(harvested_area_filenames[i])[1])[0].split('_', 1)[0]
            ui.update_run_log('Calculating nutritional contribution of ' + current_crop_name)
            if current_crop_name in nutritional_content_odict.keys():
                Energy += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Energy'])
                Protein += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Protein'])
                VitA += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['VitA'])
                VitC += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['VitC'])
                VitE += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['VitE'])
                Thiamin += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Thiamin'])
                Riboflavin += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Riboflavin'])
                Niacin += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Niacin'])
                VitB6 += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['VitB6'])
                Folate += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Folate'])
                VitB12 += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['VitB12'])
                Ca += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Ca'])
                Ph += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Ph'])
                Mg += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Energy'])
                K += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Mg'])
                Na += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['K'])
                Fe += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Fe'])
                Zn += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Energy'])
                Cu += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Zn'])



        # TODO make this happen earlier in calcs
        Energy *= change_ratio_mean
        Protein *= change_ratio_mean
        VitA *= change_ratio_mean
        VitC *= change_ratio_mean
        VitE *= change_ratio_mean
        Thiamin *= change_ratio_mean
        Riboflavin *= change_ratio_mean
        Niacin *= change_ratio_mean
        VitB6 *= change_ratio_mean
        Folate *= change_ratio_mean
        VitB12 *= change_ratio_mean
        Ca *= change_ratio_mean
        Ph *= change_ratio_mean
        Mg *= change_ratio_mean
        K *= change_ratio_mean
        Na *= change_ratio_mean
        Fe *= change_ratio_mean
        Zn *= change_ratio_mean
        Cu *= change_ratio_mean

        match_1km_uri = os.path.join(ui.root_app.project_folder, 'C:/mesh_alpha_0.2/projects/volta_demo/input/Baseline/pop.tif')

        utilities.save_array_as_geotiff(Energy, os.path.join(args['output_folder'], 'nutrient_production', 'Energy_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Energy_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Energy_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Protein, os.path.join(args['output_folder'], 'nutrient_production', 'Protein_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Protein_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Protein_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(VitA, os.path.join(args['output_folder'], 'nutrient_production', 'VitA_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'VitA_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'VitA_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(VitC, os.path.join(args['output_folder'], 'nutrient_production', 'VitC_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'VitC_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'VitC_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(VitE, os.path.join(args['output_folder'], 'nutrient_production', 'VitE_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'VitE_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'VitE_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Thiamin, os.path.join(args['output_folder'], 'nutrient_production', 'Thiamin_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Thiamin_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Thiamin_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Riboflavin, os.path.join(args['output_folder'], 'nutrient_production', 'Riboflavin_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Riboflavin_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Riboflavin_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Niacin, os.path.join(args['output_folder'], 'nutrient_production', 'Niacin_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Niacin_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Niacin_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(VitB6, os.path.join(args['output_folder'], 'nutrient_production', 'VitB6_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'VitB6_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'VitB6_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Folate, os.path.join(args['output_folder'], 'nutrient_production', 'Folate_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Folate_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Folate_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(VitB12, os.path.join(args['output_folder'], 'nutrient_production', 'VitB12_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'VitB12_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'VitB12_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Ca, os.path.join(args['output_folder'], 'nutrient_production', 'Ca_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Ca_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Ca_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Ph, os.path.join(args['output_folder'], 'nutrient_production', 'Ph_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Ph_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Ph_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Mg, os.path.join(args['output_folder'], 'nutrient_production', 'Mg_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Mg_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Mg_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(K, os.path.join(args['output_folder'], 'nutrient_production', 'K_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'K_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'K_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Na, os.path.join(args['output_folder'], 'nutrient_production', 'Na_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Na_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Na_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Fe, os.path.join(args['output_folder'], 'nutrient_production', 'Fe_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Fe_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Fe_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Zn, os.path.join(args['output_folder'], 'nutrient_production', 'Zn_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Zn_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Zn_per_cell_1km.tif'), match_1km_uri)
        utilities.save_array_as_geotiff(Cu, os.path.join(args['output_folder'], 'nutrient_production', 'Cu_per_cell_5min.tif'), match_5min_uri)
        utilities.resample_while_preserving_sum(os.path.join(args['output_folder'], 'nutrient_production', 'Cu_per_cell_5min.tif'), os.path.join(args['output_folder'], 'nutrient_production', 'Cu_per_cell_1km.tif'), match_1km_uri)

    ui.update_run_log('Calculating total nutrient demand')
    overall_nutrient_sum = 0
    overall_nutrient_requirement_sum = 0
    overall_ratio_array = np.zeros(population.shape)
    overall_ratio = 0
    population_zero_normalized = np.where(population < 0, 0, population)
    for nutrient in nutritional_requirements_odict:
        nutrient_uri = os.path.join(args['output_folder'], 'nutrient_production', nutrient + '_per_cell_1km.tif')
        nutrient_array = utilities.as_array(nutrient_uri)

        nutrient_requirement_array = population_zero_normalized * float(nutritional_requirements_odict[nutrient]['avg']) * 365.0

        nutrient_provision_ratio = nutrient_array / nutrient_requirement_array
        overall_ratio_array += nutrient_provision_ratio
        nutrient_sum = np.sum(nutrient_array)
        overall_nutrient_sum += nutrient_sum
        nutrient_requirement_sum = np.sum(nutrient_requirement_array)
        overall_nutrient_requirement_sum += nutrient_requirement_sum
        output_string = 'Full landscape produced ' + str(nutrient_sum) + ' of ' + nutrient + ' compared to a national requirement of ' + str(nutrient_requirement_sum) + ', yielding nutritional adequacy ratio of ' + str(nutrient_sum / nutrient_requirement_sum) + '.'
        ui.update_run_log(output_string)
        overall_ratio += nutrient_provision_ratio
        utilities.save_array_as_geotiff(nutrient_provision_ratio, nutrient_uri.replace('_per_cell_1km.tif', '_adequacy_ratio.tif'), nutrient_uri)

    overall_ratio_array *= 1.0 / 19.0
    overall_ratio = (1.0 / 19.0) * (overall_nutrient_sum / overall_nutrient_requirement_sum)

    output_string = 'Overall nutrion adequacy ratio: ' + str(overall_ratio) + '.'
    ui.update_run_log(output_string)
    overall_ratio_uri = os.path.join(args['output_folder'], 'overall_adequacy_ratio.tif')
    utilities.save_array_as_geotiff(overall_ratio_array, overall_ratio_uri, nutrient_uri)


    return overall_ratio






if __name__ == "__main__":
    print('WARNING! Running Nutrition.py script locally.')
    #create_data()
    print ('Script finished.')