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

run_name = 'r1'

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

create_es_prioritization_mask = False
if create_es_prioritization_mask:
    carbon_result_uri = os.path.join(runs_folder, run_name, 'Baseline', 'carbon/tot_c_cur.tif')
    carbon = nd.ArrayFrame(carbon_result_uri)

    wy = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'hydropower_water_yield/output/per_pixel/wyield.tif'))
    n_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'ndr/n_export.tif'))
    effective_retention_n = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'ndr/intermediate_outputs/effective_retention_n.tif'))
    p_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'ndr/p_export.tif'))
    effective_retention_p = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'ndr/intermediate_outputs/effective_retention_p.tif'))
    sed_retention_index = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'sdr/sed_retention_index.tif')) # The index is calculated such that the value is in terms of avoided export tons soil.


    # Generate weighted marginal value from the CONS scenario
    normalized_carbon = nd.normalize_values(carbon)
    normalized_carbon.show(output_uri=os.path.join(overall_results_dir, 'normalized_carbon.png'))

    normalized_wy = nd.normalize_values(wy)
    normalized_wy.show(output_uri=os.path.join(overall_results_dir, 'normalized_wyield.png'))

    normalized_n_export = nd.normalize_values(n_export)
    normalized_n_export.show(output_uri=os.path.join(overall_results_dir, 'normalized_n_export.png'))

    normalized_effective_retention_n = nd.normalize_values(effective_retention_n)
    normalized_effective_retention_n.show(output_uri=os.path.join(overall_results_dir, 'normalized_effective_retention_n.png'))

    normalized_p_export = nd.normalize_values(p_export)
    normalized_p_export.show(output_uri=os.path.join(overall_results_dir, 'normalized_p_export.png'))

    normalized_effective_retention_p = nd.normalize_values(effective_retention_p)
    normalized_effective_retention_p.show(ooutput_uri=os.path.join(overall_results_dir, 'normalized_effective_retention_p.png'))

    normalized_sed_retention_index = nd.normalize_values(sed_retention_index)
    normalized_sed_retention_index.show(output_uri=os.path.join(overall_results_dir, 'normalized_sed_retention_index.png'))

    normalized_wy = normalized_wy.resample(normalized_carbon, delete_original=False)
    normalized_n_export = normalized_n_export.resample(normalized_carbon, delete_original=False)
    normalized_effective_retention_n = normalized_effective_retention_n.resample(normalized_carbon, delete_original=False)
    normalized_p_export = normalized_p_export.resample(normalized_carbon, delete_original=False)
    normalized_effective_retention_p = normalized_effective_retention_p.resample(normalized_carbon, delete_original=False)
    normalized_sed_retention_index = normalized_sed_retention_index.resample(normalized_carbon, delete_original=False)

    # Because the resample assumes you now want to keep these, these must be manually told to delte
    normalized_n_export.discard_at_exit = True
    normalized_effective_retention_n.discard_at_exit = True
    normalized_p_export.discard_at_exit = True
    normalized_effective_retention_p.discard_at_exit = True
    normalized_sed_retention_index.discard_at_exit = True


    weights = [.25, -.1, .15, .15, .15, .15, .25]
    # NOTE, for some reason, the SDR model returns no_data_values for some areas in burkina. Manually set the multiply to treat those as zeros.
    # weighted_marginal = nd.multiply(normalized_carbon, weights[0]) + nd.multiply(normalized_n_export, weights[2])

    weighted_marginal = nd.multiply(normalized_carbon, weights[0]) \
                        + nd.multiply(normalized_wy, weights[1]) \
                        + nd.multiply(normalized_n_export, weights[2]) \
                        + nd.multiply(normalized_effective_retention_n, weights[3]) \
                        + nd.multiply(normalized_p_export, weights[4]) \
                        + nd.multiply(normalized_effective_retention_p, weights[5]) \
                        + nd.multiply(normalized_sed_retention_index, weights[6], no_data_mode='set_no_data_to_zero')

    weighted_marginal.save(output_folder=overall_results_dir, output_uri='weighted_marginal.tif')

    es_prioritization_array, _ = nd.get_rank_array(weighted_marginal[:], ignore_value=-1)
    es_prioritization = nd.ArrayFrame(es_prioritization_array, carbon, no_data_value=-1) # Conceptual ND problem here... if the input is an array and the uri, it is tempting to update eg uri with kwargs, but this wouldn't update the input af attributes.

    es_prioritization_uri = os.path.join(overall_results_dir, 'es_prioritization.tif')

    es_prioritization.save(output_uri=es_prioritization_uri)
    es_prioritization.uri=es_prioritization_uri

    es_prioritization_array_top_20th_percentile_array = nd.get_rank_of_top_percentile_of_array(20, weighted_marginal[:], ignore_value=-1)

    # NOTE: Be very sure that when you load an AF from array that you give it a match.
    es_prioritization_array_top_20th_percentile = nd.ArrayFrame(es_prioritization_array_top_20th_percentile_array, carbon, no_data_value=-1)

    es_prioritization_mask_uri = os.path.join(overall_results_dir, 'es_prioritization_mask.tif')
    es_prioritization_mask = nd.where(es_prioritization_array_top_20th_percentile > 0, 1, 0) # Put a 1 whereever will be  prevented from expansion
    es_prioritization_mask.save(output_uri=es_prioritization_mask_uri)
else:
    es_prioritization_mask_uri = os.path.join(overall_results_dir, 'es_prioritization_mask.tif')

create_slope_mask = False
if create_slope_mask:
    print('carbon.resolution', carbon.resolution)
    slope = nd.ArrayFrame(os.path.join(input_folder, 'baseline', 'slope.tif'))
    slope_resampled_uri = slope.uri.replace('.tif', '_resampled.tif')
    slope.resample(match, resolution=carbon.resolution, output_uri=slope_resampled_uri) #394.187
    slope = nd.ArrayFrame(slope_resampled_uri)
    slope_threshold = 3.0

    slope_mask_array = np.where(slope.data > slope_threshold, 1, 0)

    slope_mask_uri = os.path.join(runs_folder, run_name, 'slope_mask.tif')
    slope_mask = nd.ArrayFrame(slope_mask_array, match, output_uri=slope_mask_uri)
else:
    slope_mask_uri = os.path.join(overall_results_dir, 'slope_mask.tif')


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

do_undo_lulc_reclass_old = False
if do_undo_lulc_reclass_old:
    # WENT MANUAL HERE, and ran the proximity scenario generator with masked_lulc and masked_lulc_with_slope_constraint, which created_dearest_to_edge.tif
    for scenario in scenarios:
        # nearest_to_edge.tif is the output of the proximity scenario generator.
        # In the  prioritized scenarios, the +20 to the protected class is never expanded into (not included in the expandable list in the scen gen).
        # Here, we put the original class back in place now that the other expansion has happened.
        unfixed_lulc_uri = os.path.join(input_folder, scenario, 'nearest_to_edge.tif')
        unfixed_lulc = nd.ArrayFrame(unfixed_lulc_uri)

        lulc_scenario_uri = os.path.join(input_folder, scenario, 'lulc.tif')

        if 'Slope' in scenario:
            # unfixed_lulc.show()
            lulc_scenario_pre1 = nd.where(unfixed_lulc > (16 + 50), unfixed_lulc - (50 + 20), unfixed_lulc, output_uri=lulc_scenario_uri.replace('.tif', 'pre1.tif'))
            # lulc_scenario_pre1.show()
            # This two step parsesoutboth slope and es prioritized reclasses because 20 + 30 = 50.
            lulc_scenario_pre2 = nd.where(lulc_scenario_pre1 > (16 + 20), lulc_scenario_pre1 - 50, lulc_scenario_pre1, output_uri=lulc_scenario_uri.replace('.tif', 'pre2.tif'))
            # lulc_scenario_pre2.show()
            lulc_scenario = nd.where(lulc_scenario_pre2 > (16), lulc_scenario_pre2 - 20, lulc_scenario_pre2, output_uri=lulc_scenario_uri)
            # lulc_scenario.show()
        else:
            lulc_scenario = nd.where(unfixed_lulc > (16), unfixed_lulc - 20, unfixed_lulc, output_uri=lulc_scenario_uri)



do_undo_lulc_reclass = True
if do_undo_lulc_reclass:
    # WENT MANUAL HERE, and ran the proximity scenario generator with masked_lulc and masked_lulc_with_slope_constraint, which created_dearest_to_edge.tif
    for scenario in scenarios[1:]: # Skip baseline
        # nearest_to_edge.tif is the output of the proximity scenario generator.
        # In the  prioritized scenarios, the +20 to the protected class is never expanded into (not included in the expandable list in the scen gen).
        # Here, we put the original class back in place now that the other expansion has happened.
        unfixed_lulc_uri = os.path.join(input_folder, scenario, 'lulc_expanded_with_protection_classes.tif')
        unfixed_lulc = nd.ArrayFrame(unfixed_lulc_uri)

        lulc_scenario_uri = os.path.join(input_folder, scenario, 'lulc.tif')

        lulc_scenario_array = np.where(unfixed_lulc.data > 16, unfixed_lulc.data - 20, unfixed_lulc.data) #LEARNING POINT, it fails if i specify the same output_uri because that is still open. Just leave it blank to write to a temp.
        lulc_scenario_array = np.where(lulc_scenario_array < 0, 255, lulc_scenario_array)
        lulc_scenario_array = np.where(lulc_scenario_array == 235, 255, lulc_scenario_array)

        # # The above nd.where didnt detect the ndv. write it back in. Also, note that the unary operator still doesn't work in numdal so have to use or (or || but not |)
        # Note that nd.where(((unfixed_lulc > 16) and (unfixed_lulc != 255)), unfixed_lulc - 20, unfixed_lulc, output_uri=lulc_scenario_uri) would not work due to this.
        lulc_scenario = nd.ArrayFrame(lulc_scenario_array, match, output_uri=lulc_scenario_uri, no_data_value=255.0, data_type=6)
        nd.pp(nd.get_value_count_odict_from_array(lulc_scenario.data))



else:
    masked_lulc_uri = os.path.join(runs_folder, run_name, 'masked_lulc.tif')
