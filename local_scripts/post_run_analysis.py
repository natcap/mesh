import os
import numdal as nd
import numpy as np
import hazelbean as hb
from collections import OrderedDict

import os, sys, math, random
from collections import OrderedDict
import numpy as np

import numdal as nd
import hazelbean

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

import pandas as pd

# TODO Put in mesh base data, compressed of course
ag_dir = 'C:\\OneDrive\\Projects\\base_data\\publications\\ag_tradeoffs\\land_econ'

def calc_caloric_production_from_lulc_uri(input_lulc_uri, aoi_uri, output_uri):
    # First check that the required files exist, creating them if not.
    # Data from Johnson et al 2016.

    working_dir = os.path.split(os.path.split(input_lulc_uri)[0])[0]
    baseline_dir = os.path.join(working_dir, 'Baseline')
    scenario_dir = os.path.split(input_lulc_uri)[0]

    calories_resampled_uri = os.path.join(scenario_dir, 'calories_per_ha_2000.tif')
    if not os.path.exists(calories_resampled_uri):
        # Get global 5m calories map from base data
        calories_per_cell_uri  = os.path.join(ag_dir, 'calories_per_cell.tif')
        calories_per_cell = nd.ArrayFrame(calories_per_cell_uri)
        ndv = calories_per_cell.no_data_value

        # Project the full global map to projection of lulc
        calories_per_cell_projected_uri  = os.path.join(baseline_dir, 'calories_per_cell_projected.tif')
        output_wkt = nd.get_projection_from_uri(input_lulc_uri)
        calories_per_cell_projected = nd.reproject(calories_per_cell, calories_per_cell_projected_uri,
                                                   output_wkt=output_wkt, no_data_value=ndv)

        # Clip the global data to the project aoi, but keep at 5 min for math summation reasons later
        clipped_calories_per_5m_cell_uri = os.path.join(baseline_dir, 'clipped_calories_per_5m_cell.tif')
        clipped_calories_per_5m_cell = calories_per_cell_projected.clip_by_shape(aoi_uri, output_uri=clipped_calories_per_5m_cell_uri,
                                                                                 no_data_value=ndv)
        # Load the baseline lulc for adjustment factor calculation and as a match_af
        baseline_lulc_uri = os.path.join(baseline_dir, 'lulc.tif')
        baseline_lulc = nd.ArrayFrame(baseline_lulc_uri)
        input_lulc = nd.ArrayFrame(input_lulc_uri)

        # Resample baseline lulc to the intput_lulc (a slight size change happens with the scenario generator)
        baseline_resampled_lulc = baseline_lulc.resample(input_lulc, discard_at_exit=True)

        # Resample calories to lulc
        calories_resampled = clipped_calories_per_5m_cell.resample(input_lulc, output_uri=calories_resampled_uri, no_data_value=ndv, discard_at_exit=True)
        calories_resampled = None

    input_lulc = nd.ArrayFrame(input_lulc_uri)
    ndv = input_lulc.no_data_value

    calories_resampled = nd.ArrayFrame(calories_resampled_uri)

    baseline_lulc_uri = os.path.join(baseline_dir, 'lulc.tif')
    baseline_lulc = nd.ArrayFrame(baseline_lulc_uri)

    baseline_resampled_lulc = baseline_lulc.resample(input_lulc, discard_at_exit=True)

    # baseline_lulc_uri = os.path.join(baseline_dir, 'lulc.tif')
    # baseline_lulc = nd.ArrayFrame(baseline_lulc_uri)

    clipped_calories_per_5m_cell_uri = os.path.join(baseline_dir, 'clipped_calories_per_5m_cell.tif')
    clipped_calories_per_5m_cell = nd.ArrayFrame(clipped_calories_per_5m_cell_uri)

    # Base on teh assumption that full ag is twice as contianing of calroies as mosaic, allocate the
    # caloric presence to these two ag locations. Note that these are still not scaled, but they are
    # correct relative to each other.
    # This simplification means we are doing the equivilent to the invest crop model beacause
    # the cells to allocate are lower res than the target.
    unscaled_calories_baseline = np.where(baseline_resampled_lulc.data == 12, calories_resampled.data, 0)
    unscaled_calories_baseline = np.where(baseline_resampled_lulc.data == 14, 0.5 * calories_resampled.data, unscaled_calories_baseline)

    # Multiply the unscaled calories by this adjustment factor, which is the ratio between the actual calories present
    # calculated from the 5 min resolution data, and the unscaled.
    n_calories_present = np.sum(clipped_calories_per_5m_cell)
    n_unscaled_calories_in_baseline = np.sum(unscaled_calories_baseline)
    adjustment_factor = n_calories_present / n_unscaled_calories_in_baseline

    unscaled_calories_input_lulc = np.where(input_lulc.data == 12, calories_resampled.data, 0)
    unscaled_calories_input_lulc = np.where(input_lulc.data == 14, 0.5 * calories_resampled.data, unscaled_calories_input_lulc)

    output_calories = unscaled_calories_input_lulc * adjustment_factor
    output_calories_af = nd.ArrayFrame(output_calories, input_lulc, data_type=6, no_data_value=ndv, output_uri=output_uri)

    print('Sum of ' + output_calories_af.uri + ': ' + str(output_calories_af.sum()))




def calc_calorie_production_from_input_dir(**kw):
    input_dir = kw.get('input_dir')
    aoi_uri = kw.get('aoi_uri')
    runs_dir = kw.get('runs_dir')
    run_name = kw.get('run_name')
    current_run_dir = kw.get('current_run_dir')
    scenarios = kw.get('scenario_names')

    #Requires that all scenarios be named lulc.tif, but in their dir.
    scenario_dirs = [os.path.join(input_dir, i) for i in scenarios if os.path.exists(os.path.join(input_dir, i, 'lulc.tif'))]

    lulc_uris = [os.path.join(i, 'lulc.tif') for i in scenario_dirs]



    for i, uri in enumerate(lulc_uris):
        model_output_dir = os.path.join(current_run_dir, scenarios[i], 'lulc_based_ag_production')
        if not os.path.exists(model_output_dir):
            os.mkdir(model_output_dir)
        caloric_production_uri = os.path.join(model_output_dir, 'caloric_production.tif')
        calc_caloric_production_from_lulc_uri(uri, aoi_uri, caloric_production_uri)

    return kw

def create_scenario_outputs_csv(**kw):
    input_dir = kw.get('input_dir')
    runs_dir = kw.get('runs_dir')
    run_name = kw.get('run_name')
    current_run_dir = kw.get('current_run_dir')
    scenario_outputs_csv_uri = kw.get('scenario_outputs_csv_uri')
    scenarios = kw.get('scenario_names')


    # TODO  Generalize
    scenario_results = [['', 'carbon', 'wy', 'n_export', 'p_export', 'sed_export', 'caloric_production',
                         'carbon_diff_from_baseline', 'wy_diff_from_baseline', 'n_export_diff_from_baseline', 'p_export_diff_from_baseline', 'sed_export_diff_from_baseline', 'caloric_production_diff_from_baseline',
                         'carbon_percent_diff_from_baseline', 'wy_percent_diff_from_baseline', 'n_export_percent_diff_from_baseline', 'p_export_percent_diff_from_baseline', 'sed_export_percent_diff_from_baseline', 'caloric_production_percent_diff_from_baseline',
                         'carbon_diff_from_baseline', 'wy_diff_from_baseline', 'n_export_diff_from_baseline', 'p_export_diff_from_baseline', 'sed_export_diff_from_baseline', 'caloric_production_diff_from_baseline',
                         'carbon_percent_diff_from_bau', 'wy_percent_diff_from_bau', 'n_export_percent_diff_from_bau', 'p_export_percent_diff_from_bau', 'sed_export_percent_diff_from_bau', 'caloric_production_percent_diff_from_bau', ]]




    # Calculate Sum
    baseline_results = []
    bau_results = []
    for scenario in scenarios:
        print('Adding ', scenario, ' to output csv.')
        scenario_result = []
        scenario_results.append(scenario_result)
        scenario_result.append(scenario)

        carbon_result_uri = os.path.join(runs_dir, run_name, scenario, 'carbon/tot_c_cur.tif')

        carbon = nd.ArrayFrame(carbon_result_uri)
        wy = nd.ArrayFrame(os.path.join(runs_dir, run_name, scenario, 'hydropower_water_yield/output/per_pixel/wyield.tif'))
        n_export = nd.ArrayFrame(os.path.join(runs_dir, run_name, scenario, 'ndr/n_export.tif'))
        p_export = nd.ArrayFrame(os.path.join(runs_dir, run_name, scenario, 'ndr/p_export.tif'))
        sed_export = nd.ArrayFrame(os.path.join(runs_dir, run_name, scenario, 'sdr/sed_export.tif'))
        calories = nd.ArrayFrame(os.path.join(input_dir, scenario, 'caloric_production.tif'))

        if scenario == kw['baseline_scenario_name']:
            baseline_results.append(carbon.sum())  # np.sum(carbon[carbon.data!=carbon.no_data_value])
            baseline_results.append(wy.sum())
            baseline_results.append(n_export.sum())
            baseline_results.append(p_export.sum())
            baseline_results.append(sed_export.sum())
            baseline_results.append(calories.sum())

        elif scenario == kw['bau_scenario_name']:
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

        if scenario not in [kw['baseline_scenario_name']]:
            scenario_result.append(str(float(carbon.sum() - baseline_results[0]) * 100))
            scenario_result.append(str(float(wy.sum() - baseline_results[1]) * 100))
            scenario_result.append(str(float(n_export.sum() - baseline_results[2]) * -1.0 * 100))  # -1 means interpret as retention
            scenario_result.append(str(float(p_export.sum() - baseline_results[3]) * -1.0 * 100))
            scenario_result.append(str(float(sed_export.sum() - baseline_results[4]) * -1.0 * 100))
            scenario_result.append(str(float(calories.sum() - baseline_results[5]) * 100))

            scenario_result.append(str(float((carbon.sum() - baseline_results[0]) / baseline_results[0]) * 100))
            scenario_result.append(str(float((wy.sum() - baseline_results[1]) / baseline_results[1]) * 100))
            scenario_result.append(str(float((n_export.sum() - baseline_results[2]) / baseline_results[2]) * -1.0 * 100))
            scenario_result.append(str(float((p_export.sum() - baseline_results[3]) / baseline_results[3]) * -1.0 * 100))
            scenario_result.append(str(float((sed_export.sum() - baseline_results[4]) / baseline_results[4]) * -1.0 * 100))
            scenario_result.append(str(float((calories.sum() - baseline_results[5]) / baseline_results[5]) * 100))

        if scenario not in [kw['baseline_scenario_name'], kw['bau_scenario_name']]:
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

    scenario_result.to_file

    return kw

def create_percent_difference_from_baseline_bar_chart(**kw):
    scenario_outputs_csv_uri = kw.get('scenario_outputs_csv_uri')
    current_run_dir = kw.get('current_run_dir')
    percent_difference_from_baseline_bar_chart_uri = os.path.join(current_run_dir, 'difference_from_baseline.png')

    matplotlib.style.use('ggplot')

    df = pd.read_csv(scenario_outputs_csv_uri, index_col=0)

    col_labels = kw['scenario_names']

    outcome_labels = [
        'Carbon storage',
        'Water yield',
        'Nitrogen export avoided',
        'Phosphorus export avoided',
        'Sediment export avoided',
        'Caloric production',
    ]

    # Plot the CHANGE between the different scenarios and the BASELINE
    difference_from_baseline_cols = ['carbon_percent_diff_from_baseline', 'wy_percent_diff_from_baseline', 'n_export_percent_diff_from_baseline', 'p_export_percent_diff_from_baseline',
                                     'sed_export_percent_diff_from_baseline', 'caloric_production_percent_diff_from_baseline']
    difference_from_baseline_df = df[difference_from_baseline_cols]


    num_scenarios = len(kw['scenario_names'])
    difference_from_baseline_df = difference_from_baseline_df.iloc[list(range(1, num_scenarios))]  # Select the desired rows (scenarios)

    plt.rcParams['figure.figsize'] = (14, 9)

    difference_from_baseline_df.plot.bar()

    ax = plt.gca()
    ax.set_ylabel('Percent change from Baseline', rotation=90, fontsize=20, labelpad=20)
    ax.set_xlabel('Scenario', rotation=0, fontsize=20, labelpad=20)

    ax.legend(labels=outcome_labels, loc=8, ncol=2)  # mode="expand", bbox_to_anchor=(0., 1.02, 1., .102), , borderaxespad=0.

    for c, i in enumerate(difference_from_baseline_df.index):
        result = np.sum(difference_from_baseline_df.ix[i])
        # ax.annotate('Sum: ' + str(nd.round_significant_n(result, 3)), xy=(c - .22, 3.8), fontsize=12)

    fig = plt.gcf()
    # fig.set_size_inches(18.5, 10.5)
    baseline_col_labels = col_labels[1:]

    plt.xticks(list(range(len(baseline_col_labels))), baseline_col_labels, rotation=0)

    plt.tight_layout()
    fig.savefig(percent_difference_from_baseline_bar_chart_uri)

    return kw

def create_percent_difference_from_bau_bar_chart(**kw):

    scenario_outputs_csv_uri = kw.get('scenario_outputs_csv_uri')
    current_run_dir = kw.get('current_run_dir')
    percent_difference_from_bau_bar_chart_uri = os.path.join(current_run_dir, 'difference_from_bau.png')


    matplotlib.style.use('ggplot')

    df = pd.read_csv(scenario_outputs_csv_uri, index_col=0)

    col_labels = kw.get('scenario_names')

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

    num_scenarios = len(kw['scenario_names'])
    difference_from_bau_df = difference_from_bau_df.iloc[list(range(2, num_scenarios))]  # Select the desired rows (scenarios)

    plt.rcParams['figure.figsize'] = (14, 9)

    difference_from_bau_df.plot.bar()

    ax = plt.gca()
    ax.set_ylabel('Percent difference from BAU', rotation=90, fontsize=20, labelpad=20)
    ax.set_xlabel('Scenario', rotation=0, fontsize=20, labelpad=20)

    ax.legend(labels=outcome_labels, loc=8, ncol=2)  # mode="expand", bbox_to_anchor=(0., 1.02, 1., .102), , borderaxespad=0.
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
    bau_col_labels = col_labels[2:]  # MAIN DIFFERENCE HERE from baseline. Just drop  another col

    plt.xticks(list(range(len(bau_col_labels))), bau_col_labels, rotation=0)

    # Nudge ylim on top up a bit for the legend.
    ax.set_ylim((ax.get_ylim()[0], ax.get_ylim()[1] + ((ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.035)))

    plt.tight_layout()

    fig.savefig(percent_difference_from_bau_bar_chart_uri)


def generate_default_kw():
    kw = OrderedDict()
    kw['mesh_projects_dir'] = '../projects'
    kw['project_name'] = 'Honduras05'
    kw['project_dir'] = os.path.join(kw['mesh_projects_dir'], kw['project_name'])
    kw['input_dir'] = os.path.join(kw['project_dir'], 'input')
    kw['output_dir'] = os.path.join(kw['project_dir'], 'output')
    kw['runs_dir'] = os.path.join(kw['output_dir'], 'runs')
    kw['run_name'] = 'default_run_name'
    kw['aoi_uri'] = 'aoi.shp' # DEFAULT
    kw['scenario_names'] = ['Baseline', 'BAU', 'Cons']
    kw['baseline_scenario_name'] = 'Baseline'
    kw['bau_scenario_name'] = 'BAU'
    return kw

def finalize_kw(kw):
    kw['current_run_dir'] = os.path.join(kw['runs_dir'], kw['run_name'])
    kw['scenario_outputs_csv_uri'] = os.path.join(kw['current_run_dir'], 'outputs_by_scenario.csv')
    return kw


def execute(**kw):
    kw = generate_default_kw()
    kw['run_name'] = 'r6'
    kw['aoi_uri'] = os.path.join(kw['input_dir'], 'Baseline', 'PASOS_cuencas_robinson.shp')
    kw['scenario_names'] = ['Baseline', 'Trend2030', 'ILM2030']
    kw['bau_scenario_name'] = 'Trend2030'
    kw = finalize_kw(kw)

    # kw = calc_calorie_production_from_input_dir(**kw)
    kw = create_scenario_outputs_csv(**kw)
    kw = create_percent_difference_from_baseline_bar_chart(**kw)
    kw = create_percent_difference_from_bau_bar_chart(**kw)

    return kw



# Example usage
if __name__=='__main__':


    execute()






