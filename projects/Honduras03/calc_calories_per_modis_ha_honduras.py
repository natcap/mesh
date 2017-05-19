import os
import numdal as nd
import numpy as np
import hazelbean as hb

# TODO Make this type of post-mesh results parsing something included into mesh. All i'd need to do is get the run_name, scnearios as input. Then also systemitize what the outputs are.


ag_dir = 'C:\\OneDrive\\base_data\\publications\\ag_tradeoffs\\land_econ'
project_dir = 'input/Baseline'


def calc_caloric_production_from_lulc(input_lulc_uri):
    # Data from Johnson et al 2016.
    calories_per_cell_uri  = os.path.join(ag_dir, 'calories_per_cell.tif')
    calories_per_cell = nd.ArrayFrame(calories_per_cell_uri)

    ndv = calories_per_cell.no_data_value

    # Project the full global to robinson (to match volta projeciton and also to allow np.clip_by_shape)
    calories_per_cell_projected_uri  = os.path.join(project_dir, 'calories_per_cell_projected.tif')
    if not os.path.exists(calories_per_cell_projected_uri):
        calories_per_cell_projected = nd.reproject(calories_per_cell, calories_per_cell_projected_uri, epsg_code=54030, no_data_value=ndv)
    else:
        calories_per_cell_projected = nd.ArrayFrame(calories_per_cell_projected_uri)

    # Polygon of the Volta (also in Robinson projection)
    aoi_uri = 'input/Baseline/PASOS_boundary_robinson.shp'

    # Clip the global data to the volta, but keep at 5 min for math summation reasons later
    clipped_calories_per_5m_cell_uri = 'input/Baseline/clipped_calories_per_5m_cell.tif'
    if not os.path.exists(clipped_calories_per_5m_cell_uri):
        clipped_calories_per_5m_cell = calories_per_cell_projected.clip_by_shape(aoi_uri, output_uri=clipped_calories_per_5m_cell_uri, no_data_value=ndv)
    else:
        clipped_calories_per_5m_cell = nd.ArrayFrame(clipped_calories_per_5m_cell_uri)

    # Load the baseline lulc for adjustment factor calculation and as a match_af
    lulc_uri = 'input/Baseline/lulc.tif'
    lulc = nd.ArrayFrame(lulc_uri)
    lulc_ndv = lulc.no_data_value

    # resample to LULC's resolution. Note that this will change the sum of calories.
    calories_resampled_uri = 'input/Baseline/calories_resampled.tif'
    if not os.path.exists(calories_resampled_uri):
        calories_resampled = clipped_calories_per_5m_cell.resample(lulc, output_uri=calories_resampled_uri, no_data_value=ndv)
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
        baseline_calories_af = nd.ArrayFrame(baseline_calories, lulc, output_uri=baseline_calories_uri, data_type=6, no_data_value=ndv)

    input_lulc = nd.ArrayFrame(input_lulc_uri)
    unscaled_calories_input_lulc = np.where(input_lulc.data == 12, calories_resampled.data, 0)
    unscaled_calories_input_lulc = np.where(input_lulc.data == 14, 0.5 * calories_resampled.data, unscaled_calories_input_lulc)

    output_calories = unscaled_calories_input_lulc * adjustment_factor

    output_calories_uri = os.path.join(project_dir, 'calories_in_' + nd.explode_uri(input_lulc_uri)['file_root'] + '.tif')
    output_calories_af = nd.ArrayFrame(output_calories, lulc, data_type=7, no_data_value=ndv, output_uri=output_calories_uri)
    # output_calories_af.save(output_uri=output_calories_uri)
    sum_calories = output_calories_af.sum()
    print('Calories from ' + input_lulc_uri + ': ' + str(sum_calories))

    return sum_calories

def calc_caloric_production_on_uri_list(input_uri_list, output_csv_uri):
    first_lulc = True
    baseline_calories = 0

    output = []

    for uri in input_uri_list:
        row = []
        row.append(nd.explode_uri(uri)['file_root'])

        af = nd.ArrayFrame(uri)
        # nd.pp(nd.enumerate_array_as_odict(af.data))
        sum_calories = calc_caloric_production_from_lulc(uri)

        row.append(str(sum_calories))

        if first_lulc:
            baseline_calories = sum_calories
            first_lulc = False
        else:
            row.append(str(sum_calories - baseline_calories))

        output.append(row)

    hb.python_object_to_csv(output, output_csv_uri)

# Example usage
if __name__=='__main__':

    lulc_uris_to_consider = ['input/Baseline/lulc.tif',
                             'input/Trend2030/luc2030Trend.tif',
                             'input/ILM2030/luc2030ILM.tif',]

    output_csv_uri = 'input/ag_production_output.csv'
    calc_caloric_production_on_uri_list(lulc_uris_to_consider, output_csv_uri)

