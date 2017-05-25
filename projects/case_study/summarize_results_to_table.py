import os, sys, math, random
from collections import OrderedDict
import numpy as np

import numdal as nd
import hazelbean

"""There are 41359569 ha in the volta."""

input_folder = 'input'
output_folder = 'output'
runs_folder = os.path.join(output_folder, 'runs')


results_names = ['carbon', 'wy', 'n_export', 'p_export', 'sed_retention']

run_name = 'Baseline'

scenarios = ['BAU',
             'No Deforestation',
             'ES Prioritized',
             'ES and Slope Prioritized',
             'Both Strategies',
             'No Deforestation ES and Slope Prioritized']

overall_results_dir = os.path.join(runs_folder, run_name)

match_uri = os.path.join(runs_folder, run_name, 'Baseline', 'carbon/tot_c_cur.tif')
match = nd.ArrayFrame(match_uri)


do_compare_scenarios = True
if do_compare_scenarios:
    scenario_results = [['', 'carbon', 'wy', 'n_export', 'p_export', 'sed_retention']]

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

    differences = []
    for i in range(len(results_names)):
        bau_difference = scenario_results[1][i] - scenario_results[0][i]
        cons_difference = scenario_results[2][i] - scenario_results[0][i]
        differences.append([bau_difference, cons_difference])

        print(results_names[i] + ' bau difference ' + str(bau_difference) + ', cons difference ' + str(cons_difference))

    nd.pp(scenario_results)

    csv_output_uri = os.path.join(runs_folder, run_name, 'results.csv')


    hazelbean.python_object_to_csv(scenario_results, os.path.join(csv_output_uri))
