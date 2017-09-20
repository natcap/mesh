import os
import numdal as nd
import numpy as np
import hazelbean as hb

ag_dir = 'C:\\OneDrive\\Projects\\base_data\\publications\\ag_tradeoffs\\land_econ'
project_dir = 'input/Baseline'

output_dir = 'output'


def calc_caloric_production_from_lulc(input_lulc_uri):
    # Data from Johnson et al 2016.


    calories_per_cell_uri  = os.path.join(ag_dir, 'calories_per_cell.tif')
    calories_per_cell = nd.ArrayFrame(calories_per_cell_uri)

    ndv = calories_per_cell.no_data_value

    # print('calories_per_cell', calories_per_cell.sum())

    # Project the full global to robinson (to match volta projeciton and also to allow np.clip_by_shape)
    calories_per_cell_projected_uri  = os.path.join(project_dir, 'calories_per_cell_projected.tif')
    if not os.path.exists(calories_per_cell_projected_uri):
        calories_per_cell_projected = nd.reproject(calories_per_cell, calories_per_cell_projected_uri, epsg_code=54030, no_data_value=ndv)
    else:
        calories_per_cell_projected = nd.ArrayFrame(calories_per_cell_projected_uri)

    # print('calories_per_cell_projected', calories_per_cell_projected.sum())

    # Polygon of the Volta (also in Robinson projection)
    aoi_uri = 'input/Baseline/PASOS_cuencas_robinson.shp'

    # Clip the global data to the volta, but keep at 5 min for math summation reasons later
    clipped_calories_per_5m_cell_uri = 'input/Baseline/clipped_calories_per_5m_cell.tif'
    if not os.path.exists(clipped_calories_per_5m_cell_uri):
        clipped_calories_per_5m_cell = calories_per_cell_projected.clip_by_shape(aoi_uri, output_uri=clipped_calories_per_5m_cell_uri, no_data_value=ndv)
    else:
        clipped_calories_per_5m_cell = nd.ArrayFrame(clipped_calories_per_5m_cell_uri)

    print('clipped_calories_per_5m_cell', clipped_calories_per_5m_cell.sum())

    # Load the baseline lulc for adjustment factor calculation and as a match_af
    lulc_uri = 'input/Baseline/lulc.tif'
    lulc = nd.ArrayFrame(lulc_uri)

    input_lulc = nd.ArrayFrame(input_lulc_uri)

    # Resample to the intput_lulc (a slight size change happens with the scenario generator)
    lulc = lulc.resample(input_lulc)



    # resample to LULC's resolution. Note that this will change the sum of calories.
    calories_resampled_uri = 'input/Baseline/calories_resampled.tif'
    if not os.path.exists(calories_resampled_uri):
        calories_resampled = clipped_calories_per_5m_cell.resample(input_lulc, output_uri=calories_resampled_uri, no_data_value=ndv)
    else:
        calories_resampled = nd.ArrayFrame(calories_resampled_uri)

    # Base on teh assumption that full ag is twice as contianing of calroies as mosaic, allocate the
    # caloric presence to these two ag locations. Note that these are still not scaled, but they are
    # correct relative to each other.
    # This simplification means we are doing the equivilent to the invest crop model beacause
    # the cells to allocate are lower res than the target.
    unscaled_calories_baseline = np.where(lulc.data == 12, calories_resampled.data, 0)
    unscaled_calories_baseline = np.where(lulc.data == 14, 0.5 * calories_resampled.data, unscaled_calories_baseline)

    # Multiply the unscaled calories by this adjustment factor, which is the ratio between the actual calories present
    # calculated from the 5 min resolution data, and the unscaled.
    n_calories_present = np.sum(clipped_calories_per_5m_cell)
    n_unscaled_calories_in_baseline = np.sum(unscaled_calories_baseline)
    adjustment_factor = n_calories_present / n_unscaled_calories_in_baseline

    calc_baseline_calories = False
    if calc_baseline_calories:
        baseline_calories = unscaled_calories_baseline * adjustment_factor
        baseline_calories_uri = 'input/Baseline/baseline_calories.tif'
        # NOTE, this uses numdal in a weired way because it has THREE inputs (of which the last is jammed into kwargs).
        baseline_calories_af = nd.ArrayFrame(baseline_calories, input_lulc, output_uri=baseline_calories_uri, data_type=6, no_data_value=ndv)

    input_lulc = nd.ArrayFrame(input_lulc_uri)


    unscaled_calories_input_lulc = np.where(input_lulc.data == 12, calories_resampled.data, 0)
    unscaled_calories_input_lulc = np.where(input_lulc.data == 14, 0.5 * calories_resampled.data, unscaled_calories_input_lulc)

    output_calories = unscaled_calories_input_lulc * adjustment_factor

    output_calories_uri = os.path.join(output_dir, 'calories_in_' + nd.explode_uri(input_lulc_uri)['parent_directory_no_suffix'] + '.tif').replace(' ', '_')
    output_calories_af = nd.ArrayFrame(output_calories, input_lulc, data_type=6, no_data_value=ndv, output_uri=output_calories_uri)
    # output_calories_af.save(output_uri=output_calories_uri)
    sum_calories = output_calories_af.sum()

    return sum_calories, output_calories_af

def calc_caloric_production_on_uri_list(input_uri_list, output_csv_uri):
    first_lulc = True
    baseline_calories = 0

    output = []

    af_list = []
    for uri in input_uri_list:
        row = []
        row.append(nd.explode_uri(uri)['file_root'])

        af = nd.ArrayFrame(uri)
        sum_calories, af = calc_caloric_production_from_lulc(uri)
        row.append(str(sum_calories))

        # af.show()
        af_list.append(af)
        if first_lulc:
            baseline_calories = sum_calories
            first_lulc = False
        else:
            row.append(str(sum_calories - baseline_calories))

        output.append(row)

    hb.python_object_to_csv(output, output_csv_uri)

    return af_list

def get_scenario_names_from_input_dir(input_dir):
    listdir = os.listdir(input_dir)

    scenarios = [i for i in listdir if os.path.isdir(os.path.join(input_dir, i))]

    return scenarios

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
        # print('projection', projection)
        # output_wkt = projection.ExportToWkt()
        calories_per_cell_projected = nd.reproject(calories_per_cell, calories_per_cell_projected_uri,
                                                   output_wkt=output_wkt, no_data_value=ndv)

        # Clip the global data to the project aoi, but keep at 5 min for math summation reasons later
        clipped_calories_per_5m_cell_uri = 'input/Baseline/clipped_calories_per_5m_cell.tif'
        clipped_calories_per_5m_cell = calories_per_cell_projected.clip_by_shape(aoi_uri, output_uri=clipped_calories_per_5m_cell_uri,
                                                                                 no_data_value=ndv)
        # Load the baseline lulc for adjustment factor calculation and as a match_af
        baseline_lulc_uri = os.path.join(baseline_dir, 'lulc.tif')
        baseline_lulc = nd.ArrayFrame(baseline_lulc_uri)
        input_lulc = nd.ArrayFrame(input_lulc_uri)

        # Resample baseline lulc to the intput_lulc (a slight size change happens with the scenario generator)
        baseline_resampled_lulc = baseline_lulc.resample(input_lulc, discard_at_exit=True)

        # Resample calories to lulc
        calories_resampled = clipped_calories_per_5m_cell.resample(input_lulc, output_uri=calories_resampled_uri, no_data_value=ndv)
        calories_resampled = None

    input_lulc = nd.ArrayFrame(input_lulc_uri)
    ndv = input_lulc.no_data_value

    calories_resampled = nd.ArrayFrame(calories_resampled_uri)

    baseline_lulc_uri = os.path.join(baseline_dir, 'lulc.tif')
    baseline_lulc = nd.ArrayFrame(baseline_lulc_uri)
    baseline_resampled_lulc = baseline_lulc.resample(input_lulc, discard_at_exit=True)

    # baseline_lulc_uri = os.path.join(baseline_dir, 'lulc.tif')
    # print('baseline_lulc_uri', baseline_lulc_uri)
    # baseline_lulc = nd.ArrayFrame(baseline_lulc_uri)

    clipped_calories_per_5m_cell_uri = 'input/Baseline/clipped_calories_per_5m_cell.tif'
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




def calc_calorie_production_from_input_dir(input_dir):
    # run_dir = os.path.join(input_dir, 'runs', run_name)

    scenarios = get_scenario_names_from_input_dir(input_dir)

    #require that all scenarios be named lulc.tif, but in their dir.
    scenario_dirs = [os.path.join(input_dir, i) for i in scenarios if os.path.exists(os.path.join(input_dir, i, 'lulc.tif'))]

    lulc_uris = [os.path.join(i, 'lulc.tif') for i in scenario_dirs]

    # TODO FIX when put in mesh... make it project_aoi
    aoi_uri = os.path.join(input_dir, 'Baseline', 'PASOS_cuencas_robinson.shp')
    for i, uri in enumerate(lulc_uris):
        caloric_production_uri = os.path.join(scenario_dirs[i], 'caloric_production.tif')
        calc_caloric_production_from_lulc_uri(uri, aoi_uri, caloric_production_uri)



# Example usage
if __name__=='__main__':

    input_dir = 'input'
    calc_calorie_production_from_input_dir(input_dir)




