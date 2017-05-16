import os, sys, math, random
from collections import OrderedDict

import numdal as nd

output_folder = 'output'
runs_folder = os.path.join(output_folder, 'runs')

models_run = ['carbon', 'hwy', 'ndr', 'sdr']
models_to_long_name = OrderedDict()
models_to_long_name['carbon'] = 'carbon'
models_to_long_name['hwy'] = 'hydropower_water_yield'
models_to_long_name['ndr'] = 'ndr'
models_to_long_name['sdr'] = 'sdr'

specific_run_folders = [os.path.join(runs_folder, i) for i in models_run]

scenarios = ['Baseline', 'ae_c', 'ae_nfw', 'ae_sav', 'ae_an']

# tifs_to_map = OrderedDict()
# tifs_to_map['carbon'] = ['tot_c_cur.tif']
# tifs_to_map['hwy'] = ['output\per_pixel\wyield.tif']
# tifs_to_map['ndr'] = ['n_export.tif', 'p_export.tif']
# tifs_to_map['sdr'] = ['sed_export.tif', 'sed_retention.tif']
#
# for model in models_run:
#     line = ''
#     for scenario in scenarios:
#         for tif in tifs_to_map[model]:
#
#
#             input_uri = os.path.join(runs_folder, model, scenario, models_to_long_name[model], tif)
#             af = nd.ArrayFrame(input_uri)
#             line += str(af.sum()) + ','
#
#     print(line)


for scenario in scenarios:
    af = nd.ArrayFrame(os.path.join(runs_folder, 'carbon', scenario, 'carbon','tot_c_cur.tif' ))
    print(scenario + ' carbon storage ' + str(af.sum()) )





