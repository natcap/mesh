import os, sys, math, random
from collections import OrderedDict
import numpy as np

import numdal as nd
import hazelbean


import numpy as np
import matplotlib
import matplotlib.pyplot as plt

import pandas as pd



"""There are 41359569 ha in the volta."""



def create_scenario_calorie_csv(input_dir, output_uri):
    scenario_results = [['', 'carbon', 'wy', 'n_export', 'p_export', 'sed_export', 'caloric_production',
                             'carbon_diff_from_baseline', 'wy_diff_from_baseline', 'n_export_diff_from_baseline', 'p_export_diff_from_baseline', 'sed_export_diff_from_baseline', 'caloric_production_diff_from_baseline',
                             'carbon_percent_diff_from_baseline', 'wy_percent_diff_from_baseline', 'n_export_percent_diff_from_baseline', 'p_export_percent_diff_from_baseline', 'sed_export_percent_diff_from_baseline', 'caloric_production_percent_diff_from_baseline',
                             'carbon_diff_from_baseline', 'wy_diff_from_baseline', 'n_export_diff_from_baseline', 'p_export_diff_from_baseline', 'sed_export_diff_from_baseline', 'caloric_production_diff_from_baseline',
                             'carbon_percent_diff_from_bau', 'wy_percent_diff_from_bau', 'n_export_percent_diff_from_bau', 'p_export_percent_diff_from_bau', 'sed_export_percent_diff_from_bau', 'caloric_production_percent_diff_from_bau',]]


    # Calculate Sum
    baseline_results = []
    bau_results = []
    for scenario in scenarios:
        scenario_result = []
        scenario_results.append(scenario_result)
        scenario_result.append(scenario)


        carbon_result_uri = os.path.join(runs_folder, run_name, scenario, 'carbon/tot_c_cur.tif')

        carbon = nd.ArrayFrame(carbon_result_uri)
        wy = nd.ArrayFrame(os.path.join(runs_folder, run_name, scenario, 'hydropower_water_yield/output/per_pixel/wyield.tif'))
        n_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, scenario, 'ndr/n_export.tif'))
        p_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, scenario, 'ndr/p_export.tif'))
        sed_export = nd.ArrayFrame(os.path.join(runs_folder, run_name, scenario, 'sdr/sed_export.tif' ))
        # calories = nd.ArrayFrame(os.path.join(input_dir, scenario, 'caloric_production.tif' ))
        calories = nd.ArrayFrame(os.path.join(runs_folder, run_name, scenario, 'nutritional_adequacy/caloric_production.tif' ))

        if scenario == 'Baseline':
            baseline_results.append(carbon.sum()) #np.sum(carbon[carbon.data!=carbon.no_data_value])
            baseline_results.append(wy.sum())
            baseline_results.append(n_export.sum())
            baseline_results.append(p_export.sum())
            baseline_results.append(sed_export.sum())
            baseline_results.append(calories.sum())

        # TODO Generalize BAU
        elif scenario == 'Trend':
            bau_results.append(carbon.sum())
            bau_results.append(wy.sum())
            bau_results.append(n_export.sum())
            bau_results.append(p_export.sum())
            bau_results.append(sed_export.sum())
            bau_results.append(calories.sum())

        scenario_result.append(str(float(carbon.sum())))
        scenario_result.append(str(float(wy.sum())))
        scenario_result.append(str(float(n_export.sum())))
        scenario_result.append(str(float(p_export.sum())))
        scenario_result.append(str(float(sed_export.sum())))
        scenario_result.append(str(float(calories.sum())))

        if scenario not in ['Baseline']:
            scenario_result.append(str(float(carbon.sum() - baseline_results[0]) * 100))
            scenario_result.append(str(float(wy.sum() - baseline_results[1]) * 100))
            scenario_result.append(str(float(n_export.sum() - baseline_results[2]) * -1.0 * 100)) # -1 means interpret as retention
            scenario_result.append(str(float(p_export.sum() - baseline_results[3]) * -1.0 * 100))
            scenario_result.append(str(float(sed_export.sum() - baseline_results[4]) * -1.0 * 100))
            scenario_result.append(str(float(calories.sum() - baseline_results[5]) * 100))

            scenario_result.append(str(float((carbon.sum() - baseline_results[0]) / baseline_results[0]) * 100))
            scenario_result.append(str(float((wy.sum() - baseline_results[1]) / baseline_results[1]) * 100))
            scenario_result.append(str(float((n_export.sum() - baseline_results[2]) / baseline_results[2]) * -1.0 * 100))
            scenario_result.append(str(float((p_export.sum() - baseline_results[3]) / baseline_results[3]) * -1.0 * 100))
            scenario_result.append(str(float((sed_export.sum() - baseline_results[4]) / baseline_results[4]) * -1.0 * 100))
            scenario_result.append(str(float((calories.sum() - baseline_results[5]) / baseline_results[5]) * 100))


        if scenario not in ['Baseline', 'BAU', 'Trend']:
            scenario_result.append(str(float(carbon.sum() - bau_results[0]) * 100))
            scenario_result.append(str(float(wy.sum() - bau_results[1]) * 100))
            scenario_result.append(str(float(n_export.sum() - bau_results[2]) * -1.0 * 100))
            scenario_result.append(str(float(p_export.sum() - bau_results[3]) * -1.0 * 100))
            scenario_result.append(str(float(sed_export.sum() - bau_results[4]) * -1.0 * 100))
            scenario_result.append(str(float(calories.sum() - bau_results[5]) * 100))

            scenario_result.append(str(float((carbon.sum() - bau_results[0]) / bau_results[0]) * 100))
            scenario_result.append(str(float((wy.sum() - bau_results[1]) / bau_results[1]) * 100))
            scenario_result.append(str(float((n_export.sum() - bau_results[2]) / bau_results[2]) * -1.0 * 100))
            scenario_result.append(str(float((p_export.sum() - bau_results[3]) / bau_results[3]) * -1.0 * 100))
            scenario_result.append(str(float((sed_export.sum() - bau_results[4]) / bau_results[4]) * -1.0 * 100))
            scenario_result.append(str(float((calories.sum() - bau_results[5]) / bau_results[5]) * 100))


    nd.pp(scenario_results)

    hazelbean.python_object_to_csv(scenario_results, os.path.join(output_uri))


def create_percent_difference_from_baseline_bar_chart(csv_uri, output_uri):
    matplotlib.style.use('ggplot')

    df = pd.read_csv(csv_uri, index_col=0)

    col_labels = [
        "Baseline",
        "Trend",
        "ILM",
        "TAR",
    ]

    outcome_labels = [
        'Carbon storage',
        'Water yield',
        'Nitrogen export avoided',
        'Phosphorus export avoided',
        'Sediment export avoided',
        'Caloric production',
    ]


    # Plot the CHANGE between the different scenarios and the BASELINE
    # difference_from_baseline_cols = ['nitrogen_export_sum', 'phosphorus_export_sum', 'water_yield_lost_sum', 'carbon_storage_lost_sum', 'sediment_export_tons']
    difference_from_baseline_cols = ['carbon_percent_diff_from_baseline', 'wy_percent_diff_from_baseline', 'n_export_percent_diff_from_baseline', 'p_export_percent_diff_from_baseline',
                                     'sed_export_percent_diff_from_baseline', 'caloric_production_percent_diff_from_baseline']
    difference_from_baseline_df = df[difference_from_baseline_cols]

    # TODO Generalize
    num_scenarios = 4
    difference_from_baseline_df = difference_from_baseline_df.iloc[list(range(1, num_scenarios))] # Select the desired rows (scenarios)

    plt.rcParams['figure.figsize'] = (14, 9)


    difference_from_baseline_df.plot.bar()

    ax = plt.gca()
    ax.set_ylabel('Percent change from Baseline', rotation=90, fontsize=20, labelpad=20)
    ax.set_xlabel('Scenario', rotation=0, fontsize=20, labelpad=20)



    ax.legend(labels=outcome_labels, loc=8, ncol=2) #mode="expand", bbox_to_anchor=(0., 1.02, 1., .102), , borderaxespad=0.

    for c, i in enumerate(difference_from_baseline_df.index):
        result = np.sum(difference_from_baseline_df.ix[i])
        # ax.annotate('Sum: ' + str(nd.round_significant_n(result, 3)), xy=(c - .22, 3.8), fontsize=12)

    fig = plt.gcf()
    # fig.set_size_inches(18.5, 10.5)
    baseline_col_labels = col_labels[1:]

    plt.xticks(list(range(len(baseline_col_labels))), baseline_col_labels, rotation=0)

    plt.tight_layout()


    # String	Number
    # upper right	1
    # upper left	2
    # lower left	3
    # lower right	4
    # right	5
    # center left	6
    # center right	7
    # lower center	8
    # upper center	9
    # center

    # plt.legend(loc=8, borderaxespad=0.)

    fig.savefig(output_uri)



def create_percent_difference_from_bau_bar_chart(csv_uri, output_uri):
    matplotlib.style.use('ggplot')

    df = pd.read_csv(csv_uri, index_col=0)

    col_labels = [
        "Baseline",
        "Trend",
        "ILM",
        "TAR"
    ]


    outcome_labels = [
        'Carbon storage',
        'Water yield',
        'Nitrogen export avoided',
        'Phosphorus export avoided',
        'Sediment export avoided',
        'Caloric production',
    ]


    # Plot the CHANGE between the different scenarios and the bau
    # difference_from_bau_cols = ['nitrogen_export_sum', 'phosphorus_export_sum', 'water_yield_lost_sum', 'carbon_storage_lost_sum', 'sediment_export_tons']

    difference_from_bau_cols = ['carbon_percent_diff_from_bau', 'wy_percent_diff_from_bau', 'n_export_percent_diff_from_bau', 'p_export_percent_diff_from_bau',
                                     'sed_export_percent_diff_from_bau', 'caloric_production_percent_diff_from_bau']
    difference_from_bau_df = df[difference_from_bau_cols]

    # TODO Generalize
    num_scenarios = 4
    difference_from_bau_df = difference_from_bau_df.iloc[list(range(2, num_scenarios))] # Select the desired rows (scenarios)


    plt.rcParams['figure.figsize'] = (14, 9)

    difference_from_bau_df.plot.bar()

    ax = plt.gca()
    ax.set_ylabel('Percent difference from BAU', rotation=90, fontsize=20, labelpad=20)
    ax.set_xlabel('Scenario', rotation=0, fontsize=20, labelpad=20)

    ax.legend(labels=outcome_labels, loc=8, ncol=2) #mode="expand", bbox_to_anchor=(0., 1.02, 1., .102), , borderaxespad=0.
    ## Annotaitons needed to be located dependent on bar height.
    # ax.annotate('Scenario\nsums:', xy=(-.46, 2.865), fontsize=12, color='grey')
    # for c, i in enumerate(difference_from_bau_df.index):
    #     result = np.sum(difference_from_bau_df.ix[i])
    #     if c == 0:
    #
    #         ax.annotate(str(nd.round_significant_n(result, 3)), xy=(c, 3.0), fontsize=12, color='grey')
    #     else:
    #         ax.annotate(str(nd.round_significant_n(result, 3)), xy=(c, 3.0), fontsize=12, color='grey')

    fig = plt.gcf()
    # fig.set_size_inches(18.5, 10.5)
    bau_col_labels = col_labels[2:] # MAIN DIFFERENCE HERE from baseline. Just drop  another col

    plt.xticks(list(range(len(bau_col_labels))), bau_col_labels, rotation=0)

    # Nudge ylim on top up a bit for the legend.
    ax.set_ylim((ax.get_ylim()[0], ax.get_ylim()[1] + ((ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.035)))

    plt.tight_layout()

    fig.savefig(output_uri)





project_dir = '../projects/Ghana01'
input_dir = os.path.join(project_dir, 'input')
output_dir = os.path.join(project_dir, 'output')
runs_folder = os.path.join(output_dir, 'runs')


results_names = ['carbon', 'wy', 'n_export', 'p_export', 'sed_retention', 'calories']

run_name = 'r3'

scenarios = [    "Baseline",
                 "Trend",
                 "ILM",
                 "TAR",
                 ]

overall_results_dir = os.path.join(runs_folder, run_name)

match_uri = os.path.join(runs_folder, run_name, 'Baseline', 'carbon/tot_c_cur.tif')
match = nd.ArrayFrame(match_uri)
#
results_csv_uri = os.path.join(runs_folder, run_name, 'calories_results.csv')

do_create_scenario_calorie_csv = 1
if do_create_scenario_calorie_csv:
    create_scenario_calorie_csv(input_dir, results_csv_uri)

do_create_percent_difference_from_baseline_bar_chart = 1
if do_create_percent_difference_from_baseline_bar_chart:
    difference_from_baseline_csv_uri = os.path.join(runs_folder, run_name, 'proportion_differences_from_bau.csv')
    difference_from_baseline_barchart_uri = os.path.join(runs_folder, run_name, 'difference_from_baseline.png')
    create_percent_difference_from_baseline_bar_chart(results_csv_uri, difference_from_baseline_barchart_uri)

do_create_percent_difference_from_bau_bar_chart = 1
if do_create_percent_difference_from_bau_bar_chart:
    difference_from_bau_csv_uri = os.path.join(runs_folder, run_name, 'proportion_differences_from_baseline.csv')
    difference_from_bau_barchart_uri = os.path.join(runs_folder, run_name, 'difference_from_bau.png')
    create_percent_difference_from_bau_bar_chart(results_csv_uri, difference_from_bau_barchart_uri)

do_minor_alignment_nudge = 0
if do_minor_alignment_nudge:

    baseline_af = nd.ArrayFrame('input\\Baseline\\lulc.tif')
    uris = ['input\\All Strategies\\lulc.tif', 'input\\ES Slope\\lulc.tif']
    for scenario in scenarios:
        uri = os.path.join(input_dir, scenario, 'lulc.tif')
        af = nd.ArrayFrame(uri)
        output_uri = os.path.join(input_dir, scenario, 'lulc_' + scenario.lower().replace(' ', '_') + '_aligned.tif')
        af.align_self_with_other(baseline_af, output_uri=output_uri, resampling_method='nearest')

        af_aligned = nd.ArrayFrame(output_uri)
        nd.pp(nd.get_value_count_odict_from_array(af.data))
        nd.pp(nd.get_value_count_odict_from_array(af_aligned.data))
plt.show()

do_extract_lulc_from_input_to_zip = 0
if do_extract_lulc_from_input_to_zip:
    nd.zip_files_from_dir_by_filter(input_dir, 'inputted_lulc.zip', 'lulc_', '.tif', exclude_strings=['resample', 'old', 'with', 'lulc.tif'])