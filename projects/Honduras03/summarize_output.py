import os, sys, math, random
from collections import OrderedDict
import numpy as np

import numdal as nd
import hazelbean

context = """Taken from calc_es_marginal_value_protection_mask.py from volta case_study."""

input_folder = 'input'
output_folder = 'output'
runs_folder = os.path.join(output_folder, 'runs')


results_names = ['carbon', 'wy', 'n_export', 'p_export', 'sed_export']

run_name = 'full2'

scenarios = ['Baseline', 'Trend2030', 'ILM2030']

overall_results_dir = os.path.join(runs_folder, run_name)

do_marginal_ranking = False
if do_marginal_ranking:

    carbon_result_uri = os.path.join(runs_folder, run_name, 'Baseline', 'carbon/tot_c_cur.tif')
    carbon = nd.ArrayFrame(carbon_result_uri)
    # carbon.show(output_uri=os.path.join(runs_folder, run_name, 'Baseline', 'tot_c_cur.png'))

    wy = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'hydropower_water_yield/output/per_pixel/wyield.tif'))
    # wy.show(output_uri=os.path.join(runs_folder, run_name, 'Baseline', 'wyield.png'))

    n_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'ndr/n_export.tif'))
    # n_export.show(output_uri=os.path.join(runs_folder, run_name, 'Baseline', 'n_export.png'))

    p_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'ndr/p_export.tif'))
    # p_export.show(output_uri=os.path.join(runs_folder, run_name, 'Baseline', 'p_export.png'))

    sed_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, 'Baseline', 'sdr/sed_export.tif'))
    # sed_export.show(output_uri=os.path.join(runs_folder, run_name, 'Baseline', 'sed_export.png'))

    # TODO REDO THIS with new results using dem_burned. Requires loading the baseline scenarios.


    # Generate weighted marginal value from the CONS scenario
    # NOTE BAD CODING it defaults to cons because cons last in scenarios list.


    normalized_carbon = nd.normalize_values(carbon)
    normalized_carbon.show(output_folder=overall_results_dir, output_uri='normalized_carbon.png')

    normalized_wy = nd.normalize_values(wy)
    normalized_wy.show(output_folder=overall_results_dir, output_uri='normalized_wy.png')


    normalized_n_export = nd.normalize_values(n_export)
    normalized_n_export.show(output_folder=overall_results_dir, output_uri='normalized_n_export.png')

    normalized_p_export = nd.normalize_values(p_export)
    normalized_p_export.show(output_folder=overall_results_dir, output_uri='normalized_p_export.png')


    sed_export.show(output_folder=overall_results_dir, output_uri='sed_export.png')
    normalized_sed_export = nd.normalize_values(sed_export)
    normalized_sed_export.show(output_folder=overall_results_dir, output_uri='normalized_sed_export.png')

    normalized_wy = normalized_wy.resample(normalized_carbon, delete_original=False)
    normalized_n_export = normalized_n_export.resample(normalized_carbon, delete_original=False)
    normalized_p_export = normalized_p_export.resample(normalized_carbon, delete_original=False)
    normalized_sed_export = normalized_sed_export.resample(normalized_carbon, delete_original=False)

    # Because the resample assumes you now want to keep these, these must be manually told to delte
    normalized_n_export.discard_at_exit = True
    normalized_p_export.discard_at_exit = True
    normalized_sed_export.discard_at_exit = True


    print(normalized_wy)


    weights = [.25, -.05, .25, .25, .25]
    # NOTE, for some reason, the SDR model returns no_data_values for some areas in burkina. Manually set the multiply to treat those as zeros.
    # weighted_marginal = nd.multiply(normalized_carbon, weights[0]) + nd.multiply(normalized_n_export, weights[2])

    weighted_marginal = nd.multiply(normalized_carbon, weights[0]) + nd.multiply(normalized_wy, weights[1]) \
                        + nd.multiply(normalized_n_export, weights[2]) + nd.multiply(normalized_p_export, weights[3]) \
                        + nd.multiply(normalized_sed_export, weights[4], no_data_mode='set_no_data_to_zero')

    weighted_marginal.save(output_folder=overall_results_dir, output_uri='weighted_marginal.tif')

    protection_order_array, _ = nd.get_rank_array(weighted_marginal[:], ignore_value=-1)
    protection_order = nd.ArrayFrame(protection_order_array, carbon, no_data_value=-1) # Conceptual ND problem here... if the input is an array and the uri, it is tempting to update eg uri with kwargs, but this wouldn't update the input af attributes.


    protection_order_uri = os.path.join(overall_results_dir, 'protection_order.tif')

    # TODO Lines like this make sense but don't work because the state on disck then doesn't match the attribute. This is a more general problem than i thought. If i wanted to use the af,i have to manually set it like the line below.
    # Related to thie TODO is that the initialize from array is not parallel with other methods. the input all other locations is a uri...
    protection_order.save(output_uri=protection_order_uri)
    protection_order.uri=protection_order_uri
    protection_order.show(title='Order in which we should protect', cbar_label='order (lower is sooner)', output_uri='protection_order.png') # vmid=200000,

    #START HERE, protection_mask works. Regenerate it and start using it to make actual scenarios.

    protection_order_array_20 = nd.get_rank_of_top_percentile_of_array(20, weighted_marginal[:], ignore_value=-1)

    # NOTE: Be very sure that when you load an AF from array that you give it a match.
    protection_order_20 = nd.ArrayFrame(protection_order_array_20, carbon, no_data_value=-1)
    protection_order_20.show(title='Order in which we should protect, top 20%', cbar_label='order (lower is sooner)', output_folder=overall_results_dir, output_uri='protection_order_20.png')

    protection_20_mask_uri = os.path.join(overall_results_dir, 'protection_20_mask.tif')
    protection_20_mask = nd.where(protection_order_20 > 0)
    protection_20_mask.save(output_uri=protection_20_mask_uri)

    # protection_20_mask.show(output_folder=overall_results_dir, output_uri='protection_20_mask.png')

else:
    protection_20_mask_uri = os.path.join(overall_results_dir, 'protection_20_mask.tif')

do_lulc_reclass = False
if do_lulc_reclass:
    # Generate a new lulc where anything protected above has its lulc class raised by 20. This will then be used in the edge-based scenario generator.
    lulc_uri = os.path.join(input_folder, 'baseline', 'lulc.tif')
    lulc = nd.ArrayFrame(lulc_uri)

    protection_20_mask_uri = os.path.join(runs_folder, run_name, 'protection_20_mask.tif')
    protection_20_mask = nd.ArrayFrame(protection_20_mask_uri)

    masked_lulc_uri = os.path.join(runs_folder, run_name, 'masked_lulc.tif')

    #LOLHACK, because modis doesn't go above 16, +20 retains the original and specifies it was changed.
    masked_lulc = nd.where(protection_20_mask == 1, lulc + 20, lulc, output_uri=masked_lulc_uri)
    masked_lulc.show()

    print('masked_lulc', masked_lulc)
else:
    masked_lulc_uri = os.path.join(runs_folder, run_name, 'masked_lulc.tif')


do_undo_lulc_reclass = False
if do_undo_lulc_reclass:

    for scenario in ['BAU', 'No Deforestation', 'ES Prioritized', 'Both Strategies']:
        # nearest_to_edge.tif is the output of the proximity scenario generator.
        # In the  prioritized scenarios, the +20 to the protected class is never expanded into (not included in the expandable list in the scen gen).
        # Here, we put the original class back in place now that the other expansion has happened.
        unfixed_lulc_uri = os.path.join(input_folder, scenario, 'nearest_to_edge.tif')
        unfixed_lulc = nd.ArrayFrame(unfixed_lulc_uri)

        lulc_scenario_uri = os.path.join(input_folder, scenario, 'lulc_' + scenario + '.tif')
        lulc_scenario = nd.where(unfixed_lulc > 17, unfixed_lulc - 20, unfixed_lulc, output_uri=lulc_scenario_uri)
        print(lulc_scenario)



else:
    masked_lulc_uri = os.path.join(runs_folder, run_name, 'masked_lulc.tif')

do_compare_scenarios = True
if do_compare_scenarios:
    scenario_results = [['', 'carbon', 'wy', 'n_export', 's_export', 'sed_export']]

    for scenario in scenarios:
        scenario_result = []
        scenario_results.append(scenario_result)
        scenario_result.append(scenario)

        carbon_result_uri = os.path.join(runs_folder, run_name, scenario, 'carbon/tot_c_cur.tif')
        carbon = nd.ArrayFrame(carbon_result_uri)
        carbon.show(output_uri=os.path.join(runs_folder, run_name, scenario, 'tot_c_cur.png'))

        wy = nd.ArrayFrame(os.path.join(runs_folder, run_name, scenario, 'hydropower_water_yield/output/per_pixel/wyield.tif'))
        wy.show(output_uri=os.path.join(runs_folder, run_name, scenario, 'wyield.png'))

        n_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, scenario, 'ndr/n_export.tif'))
        n_export.show(output_uri=os.path.join(runs_folder, run_name, scenario, 'n_export.png'))

        p_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, scenario, 'ndr/p_export.tif'))
        p_export.show(output_uri=os.path.join(runs_folder, run_name, scenario, 'p_export.png'))


        sed_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, scenario, 'sdr/sed_export.tif' ))
        sed_export.show(output_uri=os.path.join(runs_folder, run_name, scenario, 'sed_export.png'))


        scenario_result.append(str(float(carbon.sum())))
        scenario_result.append(str(float(wy.sum())))
        scenario_result.append(str(float(n_export.sum())))
        scenario_result.append(str(float(p_export.sum())))
        scenario_result.append(str(float(sed_export.sum())))

        print('carbon sum: ', carbon.sum())
        print('wy sum: ', scenario, wy.sum())
        print('n_export sum: ', scenario, n_export.sum())
        print('p_export sum: ', scenario, p_export.sum())
        print('sed_export sum: ', scenario, sed_export.sum())

    # differences = []
    # print('scenario_results', scenario_results)
    # for i in range(len(results_names)):
    #     bau_difference = scenario_results[1][i] - scenario_results[0][i]
    #     cons_difference = scenario_results[2][i] - scenario_results[0][i]
    #     differences.append([bau_difference, cons_difference])
    #
    #     print(results_names[i] + ' bau difference ' + str(bau_difference) + ', cons difference ' + str(cons_difference))

    nd.pp(scenario_results)

    csv_output_uri = os.path.join(runs_folder, run_name, 'results.csv')


    hazelbean.python_object_to_csv(scenario_results, os.path.join(csv_output_uri))
