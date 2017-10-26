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

from mesh_utilities import config
from mesh_utilities import utilities
from mesh_utilities import data_creation


LOGGER = config.LOGGER
LOGGER.setLevel(logging.INFO)
ENCODING = sys.getfilesystemencoding()

try:
    import numdal as nd # TESTING ONLY
except:
    'you are on deplyment'

def create_default_kw(calling_ui=None):
    if calling_ui:
        kw = generate_default_kw_from_ui(calling_ui)
    else:
        kw = generate_default_kw_from_nothing()

    return kw

def generate_default_kw_from_ui(ui):
    # Take an reference to the mesh application, analyze it, use results to return a new kw kw specific to the users' needs

    kw = OrderedDict()
    kw['workspace_dir'] = os.path.join(ui.project_folder, 'output/model_setup_runs/nutritional_adequacy')
    kw['aoi_uri'] = ui.project_aoi
    kw['lulc_uri'] = os.path.join(ui.project_folder, 'input/baseline', 'lulc.tif')
    kw['model_base_data_dir'] = os.path.join(ui.base_data_folder, 'models', 'nutritional_adequacy')
    kw['crop_maps_folder'] = os.path.join(kw['model_base_data_dir'], 'crop_data')
    kw['nutritional_content_table_uri'] = os.path.join(ui.project_folder, 'input/baseline', 'nutritional_contents.csv')
    kw['nutritional_requirements_table_uri'] = os.path.join(ui.project_folder,'input/baseline',  'nutritional_requirements_by_demographics.csv')
    kw['population_uri'] = os.path.join(ui.project_folder, 'input/baseline', 'population.tif')
    kw['economic_value_table_uri'] = os.path.join(ui.project_folder, 'input/baseline',  'economics_table.csv')

    return kw

def generate_default_kw_from_nothing():
    kw = OrderedDict()
    print('nyi')
    return kw

def calc_caloric_production_from_lulc_uri(input_lulc_uri, ui=None, **kw):
    # First check that the required files exist, creating them if not.
    # Data from Johnson et al 2016.

    aoi_uri = kw['aoi_uri']
    output_dir = kw['workspace_dir']
    working_dir = os.path.split(os.path.split(input_lulc_uri)[0])[0]
    baseline_dir = os.path.join(working_dir, 'Baseline')
    scenario_dir = os.path.split(input_lulc_uri)[0]


    # intermediate files
    global_calories_per_cell_uri = os.path.join(kw['model_base_data_dir'], 'calories_per_cell.tif')
    clipped_calories_per_5m_cell_uri = os.path.join(output_dir, 'clipped_calories_per_5m_cell.tif')
    calories_resampled_uri = os.path.join(output_dir, 'calories_per_ha_2000.tif')

    # Get global 5m calories map from base data and project the full global map to projection of lulc, but keeping the global resolution
    global_calories_per_cell_projected_uri  = os.path.join(output_dir, 'global_calories_per_cell_projected.tif')
    output_wkt = pg.get_dataset_projection_wkt_uri(input_lulc_uri)

    # Set cell size based on size at equator. Need to fully think this through.
    # cell_size = 111319.49079327358 * pg.get_cell_size_from_uri(global_calories_per_cell_uri)
    cell_size = pg.get_cell_size_from_uri(global_calories_per_cell_uri)

    # Reproject the global calorie data into lulc projection
    pg.reproject_dataset_uri(global_calories_per_cell_uri,
                             cell_size,
                             output_wkt,
                             'bilinear',
                             global_calories_per_cell_projected_uri)

    # Clip the global data to the project aoi, but keep at 5 min for math summation reasons later
    pg.clip_dataset_uri(
        global_calories_per_cell_projected_uri, aoi_uri, clipped_calories_per_5m_cell_uri,
        assert_projections=True, process_pool=None, all_touched=False)

    # Now that it's clipped, it's small enough to resample to lulc resolution
    pg.resize_and_resample_dataset_uri(clipped_calories_per_5m_cell_uri, pg.get_bounding_box(input_lulc_uri), pg.get_cell_size_from_uri(input_lulc_uri), calories_resampled_uri,
                                       'bilinear')

    # Load both baseline lulc and scenario lulc. Even if only 1 scenario is being included, still must have the baseline calculated
    # to calibrate how the baseline data extrapolates to the scenario.
    baseline_lulc_uri = os.path.join(baseline_dir, 'lulc.tif')
    # baseline_resampled_uri = baseline_lulc_uri.replace('.tif', '_resampled.tif')
    baseline_resampled_uri = os.path.join(output_dir, 'lulc_resampled.tif')
    pg.resize_and_resample_dataset_uri(baseline_lulc_uri, pg.get_bounding_box(input_lulc_uri), pg.get_cell_size_from_uri(input_lulc_uri), baseline_resampled_uri, 'nearest')

    # Base on teh assumption that full ag is twice as contianing of calroies as mosaic, allocate the
    # caloric presence to these two ag locations. Note that these are still not scaled, but they are
    # correct relative to each other.
    # This simplification means we are doing the equivilent to the invest crop model beacause
    # the cells to allocate are lower res than the target.
    baseline_resampled_array = utilities.as_array(baseline_resampled_uri)
    calories_resampled_array = utilities.as_array(calories_resampled_uri)
    unscaled_calories_baseline = np.where(baseline_resampled_array == 12, calories_resampled_array, 0)
    unscaled_calories_baseline = np.where(baseline_resampled_array== 14, 0.5 * calories_resampled_array, unscaled_calories_baseline)

    # Do the same replacement for the scenario lulc
    input_lulc_array = utilities.as_array(input_lulc_uri)
    unscaled_calories_input_lulc = np.where(input_lulc_array == 12, calories_resampled_array, 0)
    unscaled_calories_input_lulc = np.where(input_lulc_array == 14, 0.5 * calories_resampled_array, unscaled_calories_input_lulc)

    if 'Honduras' in ui.root_app.project_folder or 'Ghana' in ui.root_app.project_folder:
        # CUSTOM calc in agroforestry  value following Johan's suggested %
        unscaled_calories_input_lulc = np.where(input_lulc_array == 17, 0.6 * calories_resampled_array, unscaled_calories_input_lulc)
        if 'ilm' in scenario_dir.lower():
            avg_palm_cal_per_reg_cal = (8516/1295) * (3000/1800) # oil palm cal per kg/ avg crop calkg * (ilm ratio improvement over trend, which is assumed to be same as in earthstat.
            unscaled_calories_input_lulc = np.where(input_lulc_array == 18, avg_palm_cal_per_reg_cal * calories_resampled_array, unscaled_calories_input_lulc)

    # Multiply the unscaled calories by this adjustment factor, which is the ratio between the actual calories present
    # calculated from the 5 min resolution data, and the unscaled.
    clipped_calories_per_5m_cell_array = utilities.as_array(clipped_calories_per_5m_cell_uri)
    n_calories_present = np.nansum(clipped_calories_per_5m_cell_array)
    n_unscaled_calories_in_baseline = np.nansum(unscaled_calories_baseline)
    adjustment_factor = n_calories_present / n_unscaled_calories_in_baseline

    # Scale the scenario calories by the baseline adjustment factor
    output_calories = unscaled_calories_input_lulc * adjustment_factor
    output_calories_uri = os.path.join(output_dir, 'caloric_production.tif')

    ui.update_run_log('Total calories: ' + str(np.nansum(output_calories)))
    ui.update_run_log('Creating caloric_production.tif')
    utilities.save_array_as_geotiff(output_calories, output_calories_uri, input_lulc_uri, data_type_override=7)

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
    pg.resize_and_resample_dataset_uri(lulc_uri, bounding_box_pop, 847.704968, lulc_1km_uri, 'bilinear')

    lulc = utilities.as_array(lulc_uri)




def execute(kw, ui):
    if not kw:
        kw = create_default_kw(ui)
    kw['output_folder'] = kw['workspace_dir']
    ui.update_run_log('Calculating crop-specific production')

    baseline_lulc_uri = ui.root_app.project_key_raster

    if not kw.get('model_base_data_dir'):
        kw['model_base_data_dir'] = os.path.join(ui.root_app.base_data_folder, 'models', 'nutritional_adequacy')

    bounding_box = data_creation.get_datasource_bounding_box(ui.root_app.project_aoi)
    ui.update_run_log('Loading input maps. Bounding box set to: ' + str(bounding_box))

    # TODO Unimplemented switch here.
    run_full_nutritional_model = True # OTW just cal calories
    if run_full_nutritional_model:
        try:
            os.remove(os.path.join(kw['output_folder'], 'crop_proportion_baseline_500m.tif'))
            os.remove(os.path.join(kw['output_folder'], 'crop_proportion_baseline_1km.tif'))
            os.remove(os.path.join(kw['output_folder'], 'crop_proportion_500m.tif'))
            os.remove(os.path.join(kw['output_folder'], 'crop_proportion_1km.tif'))


        except:
            'no'

        match_uri = kw['lulc_uri']
        lulc_baseline = utilities.as_array(baseline_lulc_uri)
        lulc_nan_mask = np.where(lulc_baseline >= 250, 1, 0)
        crop_proportion_baseline_500m_uri = os.path.join(kw['output_folder'], 'YieldTonsPerCell', 'crop_proportion_baseline_500m.tif')
        crop_proportion_baseline = np.where(lulc_baseline == 12, 1.0, 0.0)
        # TODO START HERE, i missed a nan mask and now the results have near infinite value. create a robust solution
        # crop_proportion_baseline[lulc_nan_mask] = np.nan
        crop_proportion_baseline = np.where(lulc_baseline == 14, .5, crop_proportion_baseline)

        # BUG If the files are not in the normal folder and onl linked to, it fails to find them.
        try:
            os.mkdir(os.path.join(kw['output_folder'], 'YieldTonsPerCell'))
        except:
            'Dir already exists.'

        clipped_dir = os.path.join(kw['output_folder'], 'crop_production_and_harvested_area')
        try:            
            os.mkdir(clipped_dir)
        except:
            'Dir already exists.'
        try:
            os.mkdir(os.path.join(kw['output_folder'], 'nutrient_production'))
        except:
            'Dir already exists.'

        utilities.save_array_as_geotiff(crop_proportion_baseline, crop_proportion_baseline_500m_uri, kw['lulc_uri'])
        crop_proportion_baseline_1km_uri = os.path.join(kw['output_folder'], 'YieldTonsPerCell', 'crop_proportion_baseline_1km.tif')

        population_bounding_box = utilities.get_bounding_box(kw['population_uri'])
        cell_size = utilities.get_cell_size_from_uri(kw['population_uri'])
        pg.resize_and_resample_dataset_uri(crop_proportion_baseline_500m_uri, population_bounding_box, cell_size, crop_proportion_baseline_1km_uri, 'bilinear')

        if kw['lulc_uri'] != baseline_lulc_uri:
            lulc_scenario = utilities.as_array(kw['lulc_uri'])

            crop_proportion = np.where(lulc_scenario == 12, 1.0, 0.0)
            crop_proportion = np.where(lulc_scenario == 14, .5, crop_proportion)
            crop_proportion_500m_uri = os.path.join(kw['output_folder'], 'YieldTonsPerCell', 'crop_proportion_500m.tif')
            utilities.save_array_as_geotiff(crop_proportion, crop_proportion_500m_uri, kw['lulc_uri'])
            crop_proportion_1km_uri = os.path.join(kw['output_folder'], 'YieldTonsPerCell', 'crop_proportion_1km.tif')
            # original_dataset_uri, bounding_box, out_pixel_size, output_uri, resample_method
            pg.resize_and_resample_dataset_uri(crop_proportion_500m_uri, population_bounding_box, cell_size, crop_proportion_1km_uri, 'bilinear')

            crop_proportion_baseline_1km = utilities.as_array(crop_proportion_baseline_1km_uri)
            crop_proportion_1km = utilities.as_array(crop_proportion_1km_uri)

            change_ratio = np.where(crop_proportion_baseline_1km > 0, crop_proportion_1km / crop_proportion_baseline_1km, 1.0)

            change_ratio_mean = np.mean(change_ratio)
        else:
            change_ratio_mean = 1.0



        ui.update_run_log('Loading input maps')
        crop_maps_folder = kw['crop_maps_folder']
        nutritional_content_odict = utilities.file_to_python_object(kw['nutritional_content_table_uri'], declare_type='2d_odict')  # outputs as OrderedDict([('almond', OrderedDict([('fraction_refuse', '0.6'), ('Protein', '212.2'), ('Lipid', '494.2'), etc
        nutritional_requirements_odict = utilities.file_to_python_object(kw['nutritional_requirements_table_uri'], declare_type='2d_indexed_odict')

        population = utilities.as_array(kw['population_uri'])
        demographic_groups_list = kw['demographic_groups_list']
        demographics_folder = kw['demographics_folder']

        ui.update_run_log('Calculating crop-specific production')
        lulc_array = utilities.as_array(kw['lulc_uri'])
        lulc_wkt = pg.get_dataset_projection_wkt_uri(kw['lulc_uri'])
        harvested_area_ha_filenames = []
        harvested_area_fraction_filenames = []
        yield_tons_per_ha_filenames = []
        yield_tons_per_cell_filenames = []
        ha_array = 0
        yield_per_ha_array = 0

        # Calculate ha per cell
        cell_size = pg.get_cell_size_from_uri(kw['lulc_uri'])
        ha_per_cell = np.ones(lulc_array.shape) * (cell_size ** 2 / 10000)
        ha_per_cell_uri = os.path.join(kw['output_folder'], 'ha_per_cell.tif')
        utilities.save_array_as_geotiff(ha_per_cell, ha_per_cell_uri, kw['lulc_uri'])

        for folder_name in os.listdir(crop_maps_folder):
            current_folder = os.path.join(crop_maps_folder, folder_name)
            if os.path.isdir(current_folder):
                current_crop_name = folder_name.split('_', 1)[0]
                input_harvested_area_fraction_uri = os.path.join(current_folder, current_crop_name + '_HarvestedAreaFraction.tif')
                clipped_harvested_area_fraction_uri = os.path.join(clipped_dir, current_crop_name + '_HarvestedAreaFraction.tif')
                input_yield_tons_per_ha_uri = os.path.join(current_folder, current_crop_name + '_YieldPerHectare.tif')
                clipped_yield_tons_per_ha_uri = os.path.join(clipped_dir, current_crop_name + '_YieldPerHectare.tif')
                yield_tons_per_cell_uri = os.path.join(clipped_dir, current_crop_name + '_YieldTonsPerCell.tif')




                if not os.path.exists(clipped_harvested_area_fraction_uri) or not os.path.exists(clipped_yield_tons_per_ha_uri) or not os.path.exists(yield_tons_per_cell_uri):
                    utilities.clip_by_shape_with_buffered_intermediate_uri(input_harvested_area_fraction_uri, kw['aoi_uri'], clipped_harvested_area_fraction_uri, match_uri, resampling_method='bilinear')
                    harvested_area_fraction_array = utilities.as_array(clipped_harvested_area_fraction_uri)
                    utilities.clip_by_shape_with_buffered_intermediate_uri(input_yield_tons_per_ha_uri, kw['aoi_uri'], clipped_yield_tons_per_ha_uri, match_uri, resampling_method='bilinear')
                    yield_tons_per_ha_array = utilities.as_array(clipped_yield_tons_per_ha_uri)

                    nan1 = utilities.get_nodata_from_uri(input_harvested_area_fraction_uri)
                    nan2 = utilities.get_nodata_from_uri(input_yield_tons_per_ha_uri)

                    nan_mask = np.where((yield_tons_per_ha_array == nan1) & (harvested_area_fraction_array == nan2))

                    yield_tons_per_cell_array = yield_tons_per_ha_array * harvested_area_fraction_array * ha_per_cell

                    yield_tons_per_cell_array[nan_mask] == nan1

                    utilities.save_array_as_geotiff(yield_tons_per_cell_array, yield_tons_per_cell_uri, kw['lulc_uri'], data_type_override=7, no_data_value_override=nan1)

                harvested_area_fraction_filenames.append(clipped_harvested_area_fraction_uri)
                yield_tons_per_ha_filenames.append(clipped_yield_tons_per_ha_uri)
                yield_tons_per_cell_filenames.append(yield_tons_per_cell_uri)

            ui.update_run_log('Creating yield (tons) map for ' + folder_name)

        match_5min_uri = os.path.join(kw['output_folder'], 'crop_production_and_harvested_area', 'maize_HarvestedAreaFraction.tif')
        # match_5min_uri = os.path.join(ui.root_app.base_data_folder, 'models/crop_production/global_dataset/observed_yield/rice_yield_map.tif')
        match_array = utilities.as_array(match_5min_uri)

        nan3 = utilities.get_nodata_from_uri(input_harvested_area_fraction_uri)
        array = utilities.as_array(input_harvested_area_fraction_uri)
        nan_mask = np.where(array == nan3)

        if not all([os.path.exists(i) for i in yield_tons_per_cell_filenames]):
        #if not os.path.exists(os.path.join(kw['output_folder'], 'nutrient_production', 'Energy_per_cell_5min.tif') or True):
            Energy = np.zeros(match_array.shape).astype(np.float64)
            Energy[nan_mask] = nan3
            # Fat = np.zeros(match_array.shape).astype(np.float64)
            #[Fatnan_mask] = nan3
            Protein = np.zeros(match_array.shape).astype(np.float64)
            Protein[nan_mask] = nan3
            VitA = np.zeros(match_array.shape).astype(np.float64)
            VitA[nan_mask] = nan3
            VitC = np.zeros(match_array.shape).astype(np.float64)
            VitC[nan_mask] = nan3
            VitE = np.zeros(match_array.shape).astype(np.float64)
            VitE[nan_mask] = nan3
            Thiamin = np.zeros(match_array.shape).astype(np.float64)
            Thiamin[nan_mask] = nan3
            Riboflavin = np.zeros(match_array.shape).astype(np.float64)
            Riboflavin[nan_mask] = nan3
            Niacin = np.zeros(match_array.shape).astype(np.float64)
            Niacin[nan_mask] = nan3
            VitB6 = np.zeros(match_array.shape).astype(np.float64)
            VitB6[nan_mask] = nan3
            Folate = np.zeros(match_array.shape).astype(np.float64)
            Folate[nan_mask] = nan3
            VitB12 = np.zeros(match_array.shape).astype(np.float64)
            VitB12[nan_mask] = nan3
            Ca = np.zeros(match_array.shape).astype(np.float64)
            Ca[nan_mask] = nan3
            Ph = np.zeros(match_array.shape).astype(np.float64)
            Ph[nan_mask] = nan3
            Mg = np.zeros(match_array.shape).astype(np.float64)
            Mg[nan_mask] = nan3
            K = np.zeros(match_array.shape).astype(np.float64)
            K[nan_mask] = nan3
            Na = np.zeros(match_array.shape).astype(np.float64)
            Na[nan_mask] = nan3
            Fe = np.zeros(match_array.shape).astype(np.float64)
            Fe[nan_mask] = nan3
            Zn = np.zeros(match_array.shape).astype(np.float64)
            Zn[nan_mask] = nan3
            Cu = np.zeros(match_array.shape).astype(np.float64)
            Cu[nan_mask] = nan3


            for i in range(len(yield_tons_per_cell_filenames)):
                current_crop_name = os.path.splitext(os.path.split(harvested_area_fraction_filenames[i])[1])[0].split('_', 1)[0]
                ui.update_run_log('Calculating nutritional contribution of ' + current_crop_name)
                if current_crop_name in nutritional_content_odict.keys():
                    Energy += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Energy'])
                    # Fat += utilities.as_array(yield_tons_per_cell_filenames[i]) * 1000.0 * float(nutritional_content_odict[current_crop_name]['Fat'])
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
            # Fat *= change_ratio_mean
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

            match_1km_uri = os.path.join(kw['output_folder'], 'YieldTonsPerCell', 'crop_proportion_baseline_1km.tif')

            utilities.save_array_as_geotiff(Energy, os.path.join(kw['output_folder'], 'nutrient_production', 'Energy_per_cell_5min.tif'), match_5min_uri, data_type_override=7, no_data_value_override=nan3)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Energy_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Energy_per_cell_1km.tif'), match_1km_uri)
            # utilities.save_array_as_geotiff(Fat, os.path.join(kw['output_folder'], 'nutrient_production', 'Fat_per_cell_5min.tif'), match_5min_uri)
            # utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Fat_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Fat_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Protein, os.path.join(kw['output_folder'], 'nutrient_production', 'Protein_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Protein_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Protein_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(VitA, os.path.join(kw['output_folder'], 'nutrient_production', 'VitA_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'VitA_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'VitA_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(VitC, os.path.join(kw['output_folder'], 'nutrient_production', 'VitC_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'VitC_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'VitC_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(VitE, os.path.join(kw['output_folder'], 'nutrient_production', 'VitE_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'VitE_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'VitE_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Thiamin, os.path.join(kw['output_folder'], 'nutrient_production', 'Thiamin_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Thiamin_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Thiamin_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Riboflavin, os.path.join(kw['output_folder'], 'nutrient_production', 'Riboflavin_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Riboflavin_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Riboflavin_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Niacin, os.path.join(kw['output_folder'], 'nutrient_production', 'Niacin_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Niacin_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Niacin_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(VitB6, os.path.join(kw['output_folder'], 'nutrient_production', 'VitB6_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'VitB6_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'VitB6_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Folate, os.path.join(kw['output_folder'], 'nutrient_production', 'Folate_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Folate_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Folate_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(VitB12, os.path.join(kw['output_folder'], 'nutrient_production', 'VitB12_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'VitB12_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'VitB12_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Ca, os.path.join(kw['output_folder'], 'nutrient_production', 'Ca_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Ca_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Ca_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Ph, os.path.join(kw['output_folder'], 'nutrient_production', 'Ph_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Ph_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Ph_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Mg, os.path.join(kw['output_folder'], 'nutrient_production', 'Mg_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Mg_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Mg_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(K, os.path.join(kw['output_folder'], 'nutrient_production', 'K_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'K_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'K_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Na, os.path.join(kw['output_folder'], 'nutrient_production', 'Na_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Na_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Na_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Fe, os.path.join(kw['output_folder'], 'nutrient_production', 'Fe_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Fe_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Fe_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Zn, os.path.join(kw['output_folder'], 'nutrient_production', 'Zn_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Zn_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Zn_per_cell_1km.tif'), match_1km_uri)
            utilities.save_array_as_geotiff(Cu, os.path.join(kw['output_folder'], 'nutrient_production', 'Cu_per_cell_5min.tif'), match_5min_uri)
            utilities.resample_preserve_sum(os.path.join(kw['output_folder'], 'nutrient_production', 'Cu_per_cell_5min.tif'), os.path.join(kw['output_folder'], 'nutrient_production', 'Cu_per_cell_1km.tif'), match_1km_uri)


        # TODO FOR HONDURAS need to switch to a non-population-map derived resolution. Incorporate decision making unit map to set the desired resolution
        ui.update_run_log('Calculating total nutrient demand')
        overall_nutrient_sum = 0
        overall_nutrient_requirement_sum = 0
        overall_ratio_array = np.zeros(population.shape)
        overall_ratio = 0
        population_zero_normalized = np.where(population < 0, 0, population)
        for nutrient in nutritional_requirements_odict:
            nutrient_uri = os.path.join(kw['output_folder'], 'nutrient_production', nutrient + '_per_cell_1km.tif')
            nutrient_array = utilities.as_array(nutrient_uri)

            nutrient_requirement_array = population_zero_normalized * float(nutritional_requirements_odict[nutrient]['recommended_daily_allowance']) * 365.0
            # nutrient_requirement_array[nan_mask] = np.nan
            # nutrient_requirement_array[nutrient_requirement_array<=0] = np.nan

            nutrient_provision_ratio = np.where((nutrient_array / nutrient_requirement_array > 0) & (nutrient_array / nutrient_requirement_array < 999999999999999999999999999999),
                                                nutrient_array / nutrient_requirement_array,
                                                0)

            # nutrient_provision_ratio[nan_mask] = np.nan

            print(22, nutrient_provision_ratio)
            print(np.nansum(nutrient_provision_ratio))

            print(33, nutrient_array)
            print(np.nansum(nutrient_array))

            print(44, nutrient_requirement_array)
            print(np.nansum(nutrient_requirement_array))

            overall_ratio_array += nutrient_provision_ratio
            nutrient_sum = np.nansum(nutrient_array)
            overall_nutrient_sum += nutrient_sum
            nutrient_requirement_sum = np.nansum(nutrient_requirement_array)
            overall_nutrient_requirement_sum += nutrient_requirement_sum
            output_string = 'Full landscape produced ' + str(nutrient_sum) + ' of ' + nutrient + ' compared to a national requirement of ' + str(nutrient_requirement_sum) + ', yielding nutritional adequacy ratio of ' + str(nutrient_sum / nutrient_requirement_sum) + '.'
            ui.update_run_log(output_string)
            overall_ratio += nutrient_provision_ratio
            utilities.save_array_as_geotiff(nutrient_provision_ratio, nutrient_uri.replace('_per_cell_1km.tif', '_adequacy_ratio.tif'), nutrient_uri)

        overall_ratio_array *= 1.0 / 19.0
        overall_ratio = (1.0 / 19.0) * (overall_nutrient_sum / overall_nutrient_requirement_sum)

        output_string = 'Overall nutrion adequacy ratio: ' + str(overall_ratio) + '.'
        ui.update_run_log(output_string)
        overall_ratio_uri = os.path.join(kw['output_folder'], 'overall_adequacy_ratio.tif')
        utilities.save_array_as_geotiff(overall_ratio_array, overall_ratio_uri, nutrient_uri)

    else:
        calc_caloric_production_from_lulc_uri(kw['lulc_uri'], ui=ui, **kw)

    return






if __name__ == "__main__":
    print('WARNING! Running Nutrition.py script locally.')
    #create_data()
    print ('Script finished.')