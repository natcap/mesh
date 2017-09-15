import os, sys, math, random
from collections import OrderedDict
import numpy as np

import numdal as nd
import hazelbean

"""There are 41359569 ha in the volta."""

input_folder = 'input'
output_folder = 'output'
runs_folder = os.path.join(output_folder, 'runs')


results_names = ['carbon', 'wy', 'n_export', 'p_export', 'sed_retention_index']

run_name = 'Full'

scenarios = [
    "Baseline",
    "BAU",
    "LU Targetted",
    "ES Prioritized",
    "Slope Constrained",
    "LU ES",
    "LU Slope",
    "ES Slope",
    "All Strategies",
]




overall_results_dir = os.path.join(runs_folder, run_name)

match_uri = os.path.join(runs_folder, run_name, 'Baseline', 'carbon/tot_c_cur.tif')
match = nd.ArrayFrame(match_uri)

carbon_result_uri = os.path.join(runs_folder, run_name, 'Baseline', 'carbon/tot_c_cur.tif')
carbon = nd.ArrayFrame(carbon_result_uri)

lulc_uri = os.path.join(input_folder, 'Baseline', 'lulc.tif')
lulc = nd.ArrayFrame(lulc_uri)

create_es_prioritization_mask = True
if create_es_prioritization_mask:
    carbon_result_uri = os.path.join(runs_folder, run_name, 'Baseline', 'carbon/tot_c_cur.tif')
    carbon = nd.ArrayFrame(carbon_result_uri)

    wy = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'hydropower_water_yield/output/per_pixel/wyield.tif'))
    n_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'ndr/n_export.tif'))
    effective_retention_n = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'ndr/intermediate_outputs/effective_retention_n.tif'))
    p_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'ndr/p_export.tif'))
    effective_retention_p = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'ndr/intermediate_outputs/effective_retention_p.tif'))
    sed_retention = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'sdr/sed_retention.tif')) # The index is calculated such that the value is in terms of avoided export tons soil.
    sed_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'sdr/sed_export.tif')) # The index is calculated such that the value is in terms of avoided export tons soil.


    # Generate weighted marginal value from the CONS scenario
    normalized_carbon = nd.normalize_values(carbon)
    # normalized_carbon.show(output_uri=os.path.join(overall_results_dir, 'normalized_carbon.png'))

    normalized_wy = nd.normalize_values(wy)
    # normalized_wy.show(output_uri=os.path.join(overall_results_dir, 'normalized_wyield.png'))

    normalized_n_export = nd.normalize_values(n_export)
    # normalized_n_export.show(output_uri=os.path.join(overall_results_dir, 'normalized_n_export.png'))

    normalized_effective_retention_n = nd.normalize_values(effective_retention_n)
    # normalized_effective_retention_n.show(output_uri=os.path.join(overall_results_dir, 'normalized_effective_retention_n.png'))

    normalized_p_export = nd.normalize_values(p_export)
    # normalized_p_export.show(output_uri=os.path.join(overall_results_dir, 'normalized_p_export.png'))

    normalized_effective_retention_p = nd.normalize_values(effective_retention_p)
    # normalized_effective_retention_p.show(ooutput_uri=os.path.join(overall_results_dir, 'normalized_effective_retention_p.png'))

    normalized_sed_retention = nd.normalize_values(sed_retention)
    # normalized_sed_retention.show(output_uri=os.path.join(overall_results_dir, 'normalized_sed_retention.png'))
    normalized_sed_export = nd.normalize_values(sed_export)
    # normalized_sed_retention.show(output_uri=os.path.join(overall_results_dir, 'normalized_sed_retention.png'))

    normalized_wy = normalized_wy.resample(normalized_carbon, delete_original=False)
    normalized_n_export = normalized_n_export.resample(normalized_carbon, delete_original=False)
    normalized_effective_retention_n = normalized_effective_retention_n.resample(normalized_carbon, delete_original=False)
    normalized_p_export = normalized_p_export.resample(normalized_carbon, delete_original=False)
    normalized_effective_retention_p = normalized_effective_retention_p.resample(normalized_carbon, delete_original=False)
    normalized_sed_retention = normalized_sed_retention.resample(normalized_carbon, delete_original=False)
    normalized_sed_export = normalized_sed_export.resample(normalized_carbon, delete_original=False)

    # Because the resample assumes you now want to keep these, these must be manually told to delte
    normalized_n_export.discard_at_exit = True
    normalized_effective_retention_n.discard_at_exit = True
    normalized_p_export.discard_at_exit = True
    normalized_effective_retention_p.discard_at_exit = True
    normalized_sed_retention.discard_at_exit = True
    normalized_sed_export.discard_at_exit = True

    # # START HERE
    # reassess the weights, get rid of effective retention, ensure all signs correct.
    weights = [.2, .2, .1, .1, .1, .1, .1, .1]
    # NOTE, for some reason, the SDR model returns no_data_values for some areas in burkina. Manually set the multiply to treat those as zeros.
    # weighted_marginal = nd.multiply(normalized_carbon, weights[0]) + nd.multiply(normalized_n_export, weights[2])

    weighted_marginal = nd.multiply(normalized_carbon, weights[0], no_data_mode='set_no_data_to_zero') \
                        + nd.multiply(normalized_wy, weights[1], no_data_mode='set_no_data_to_zero') \
                        + nd.multiply(normalized_n_export, weights[2], no_data_mode='set_no_data_to_zero') \
                        + nd.multiply(normalized_effective_retention_n, weights[3], no_data_mode='set_no_data_to_zero') \
                        + nd.multiply(normalized_p_export, weights[4], no_data_mode='set_no_data_to_zero') \
                        + nd.multiply(normalized_effective_retention_p, weights[5], no_data_mode='set_no_data_to_zero') \
                        + nd.multiply(normalized_sed_export, weights[6], no_data_mode='set_no_data_to_zero') \
                        + nd.multiply(normalized_sed_retention, weights[7], no_data_mode='set_no_data_to_zero')

    # weighted_marginal = nd.multiply(normalized_carbon, weights[0]) \
    #                     + nd.multiply(normalized_wy, weights[1]) \
    #                     + nd.multiply(normalized_n_export, weights[2]) \
    #                     + nd.multiply(normalized_p_export, weights[4]) \
    #                     + nd.multiply(normalized_sed_retention, weights[6], no_data_mode='set_no_data_to_zero')

    weighted_marginal = nd.change_no_data_value_based_on_mask_inplace(weighted_marginal.uri, lulc.uri, new_no_data_value=None)
    weighted_marginal.save(output_folder=overall_results_dir, output_uri='weighted_marginal.tif')

    es_prioritization_rank_array, _ = nd.get_rank_array(weighted_marginal[:], ignore_value=-1)
    es_prioritization_rank = nd.ArrayFrame(es_prioritization_rank_array, carbon, no_data_value=-1) # Conceptual ND problem here... if the input is an array and the uri, it is tempting to update eg uri with kwargs, but this wouldn't update the input af attributes.
    es_prioritization_rank = nd.change_no_data_value_based_on_mask_inplace(es_prioritization_rank.uri, lulc.uri, new_no_data_value=None)

    es_prioritization_rank_uri = os.path.join(overall_results_dir, 'es_prioritization_rank.tif')

    es_prioritization_rank.save(output_uri=es_prioritization_rank_uri)
    es_prioritization_rank.show(output_uri=es_prioritization_rank_uri.replace('.tif', '.png'), title='Ranked ecosystem service provisioning areas')
    es_prioritization_rank.uri=es_prioritization_rank_uri

    es_prioritization_array_top_20th_percentile_array = nd.get_rank_of_top_percentile_of_array(10, weighted_marginal[:], ignore_value=-1)

    # NOTE: Be very sure that when you load an AF from array that you give it a match.
    es_prioritization_array_top_20th_percentile = nd.ArrayFrame(es_prioritization_array_top_20th_percentile_array, carbon, no_data_value=-1)

    es_prioritization_mask_uri = os.path.join(overall_results_dir, 'es_prioritization_mask.tif')
    es_prioritization_mask = nd.where(es_prioritization_array_top_20th_percentile > 0, 1, 0) # Put a 1 whereever will be  prevented from expansion
    es_prioritization_mask.save(output_uri=es_prioritization_mask_uri)
else:
    es_prioritization_mask_uri = os.path.join(overall_results_dir, 'es_prioritization_mask.tif')

create_slope_mask = False
slope_threshold_to_use = 3
if create_slope_mask:
    print('carbon.resolution', carbon.resolution)
    slope = nd.ArrayFrame(os.path.join(input_folder, 'baseline', 'slope.tif'))
    slope_resampled_uri = slope.uri.replace('.tif', '_resampled.tif')
    slope.resample(match, resolution=carbon.resolution, output_uri=slope_resampled_uri) #394.187
    slope = nd.ArrayFrame(slope_resampled_uri)


    for i in [1., 2., 3., 4., 5., 6., 7., 8., 9., 10.]:
        slope_threshold = i

        slope_mask_array = np.where(slope.data > slope_threshold, 1, 0)

        slope_mask_uri = os.path.join(input_folder, 'baseline', 'slope_gt' + str(int(slope_threshold)) + '_mask.tif')
        slope_mask = nd.ArrayFrame(slope_mask_array, match, output_uri=slope_mask_uri)

    slope_mask_uri = os.path.join(input_folder, 'baseline', 'slope_gt' + str(int(slope_threshold_to_use)) + '_mask.tif')

else:
    # slope_mask_uri = os.path.join(input_folder, 'baseline', 'slope_mask.tif')
    slope_mask_uri = os.path.join(input_folder, 'baseline', 'slope_gt' + str(int(slope_threshold_to_use)) + '_mask.tif')


do_lulc_reclass = False
if do_lulc_reclass:
    # Generate a new lulc where anything protected above has its lulc class raised by 20. This will then be used in the edge-based scenario generator.
    lulc_uri = os.path.join(input_folder, 'baseline', 'lulc.tif')
    lulc = nd.ArrayFrame(lulc_uri)

    es_prioritization_mask = nd.ArrayFrame(es_prioritization_mask_uri)
    es_prioritization_lulc_uri = os.path.join(runs_folder, run_name, 'es_prioritization_lulc.tif')
    #LOLHACK, because modis doesn't go above 16, +100 retains the original and specifies it was changed.
    es_prioritization_lulc = nd.where(es_prioritization_mask == 1, lulc + 20, lulc, output_uri=es_prioritization_lulc_uri)

    slope_constrained_mask = nd.ArrayFrame(slope_mask_uri)
    slope_constrained_lulc_uri = os.path.join(runs_folder, run_name, 'slope_constrained_lulc.tif')
    slope_constrained_lulc = nd.where(slope_constrained_mask == 1, lulc + 20, lulc, output_uri=slope_constrained_lulc_uri)

    es_and_slope_lulc_uri = os.path.join(runs_folder, run_name, 'es_and_slope_lulc.tif')
    es_and_slope_lulc_array = np.where((es_prioritization_mask.data == 1) | (slope_constrained_mask.data == 1), lulc.data + 20, lulc.data)
    es_and_slope_lulc = nd.ArrayFrame(es_and_slope_lulc_array, match, output_uri=es_and_slope_lulc_uri)
else:
    slope_constrained_lulc_uri = os.path.join(runs_folder, run_name, 'slope_constrained_lulc.tif')
    es_prioritization_lulc_uri = os.path.join(runs_folder, run_name, 'es_prioritization_lulc.tif')
    es_and_slope_lulc_uri = os.path.join(runs_folder, run_name, 'es_and_slope_lulc.tif')

