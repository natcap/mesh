#from __future__ import absolute_import


import os
from collections import OrderedDict

import nutritional_adequacy
from mesh_utilities import config
from mesh_utilities import utilities


from PyQt4.QtGui import *
from PyQt4.QtCore import *
from base_classes import ScrollWidget, InputSelector
from base_classes import *



class NutritionalAdequacyModelDialog(QDialog):
    """
    Creates dialog that sets up and runs the nutritional adequacy ratio model.
    """
    def __init__(self, root_app=None, parent=None, last_run_override=None):
        self.root_app = root_app
        self.parent = parent
        # self.listener = Listener(self.root_app, self)  # Give the dialog it's OWN listener so that the run_in_next_queue fn can update the info box during run time.
        # self.listener.start()

        super(NutritionalAdequacyModelDialog, self).__init__()
        self.input_selectors = []

        # make folders
        self.setup_run_folder = os.path.join(self.root_app.project_folder, 'output/model_setup_runs/nutritional_adequacy')
        if not os.path.exists(self.setup_run_folder):
            os.makedirs(self.setup_run_folder)

        self.setup_run_file_uri = os.path.join(self.setup_run_folder, 'nutritional_adequacy_setup_file.json')
        if last_run_override:
            odict = last_run_override
        elif os.path.exists(self.setup_run_file_uri):
            odict = utilities.file_to_python_object(self.setup_run_file_uri)
        else:
            odict = nutritional_adequacy.generate_default_kw_from_ui(self.root_app)


        self.main_layout = QVBoxLayout()
        self.setMinimumSize(1000, 700)
        self.setLayout(self.main_layout)
        self.setWindowTitle('Setup Food Security and Nutritional Adequacy')
        self.title_l = QLabel('Setup Food Security and Nutritional Adequacy')
        self.title_l.setFont(config.minor_heading_font)
        self.main_layout.addWidget(self.title_l)

        self.inputs_scroll = ScrollWidget()
        self.inputs_scroll.setMinimumHeight(150)
        self.main_layout.addWidget(self.inputs_scroll)
        self.inputs_scroll.scroll_layout.setAlignment(Qt.AlignTop)
        self.inputs_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.inputs_scroll.scroll_layout.setStretch(44, 1)

        self.grid_layout = QGridLayout()
        self.inputs_scroll.scroll_layout.addLayout(self.grid_layout)

        self.baseline_inputs_l = QLabel('Baseline inputs (required)')
        self.baseline_inputs_l.setFont(config.bold_font)
        self.grid_layout.addWidget(self.baseline_inputs_l)
        self.grid_layout.addWidget(QLabel(), 0, 1)  # used to take a place in the grid, pushing thigns downward

        self.workspace_dir_l = QLabel('Workspace directory')
        self.grid_layout.addWidget(self.workspace_dir_l)
        self.input_selectors.append(InputSelector('workspace_dir', self.root_app, self))
        self.grid_layout.addWidget(self.input_selectors[-1]) # LOL add the last thing added.

        self.aoi_l = QLabel('Area of interest shapefile')
        self.grid_layout.addWidget(self.aoi_l)
        self.input_selectors.append(InputSelector('aoi_uri', self.root_app, self))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.lulc_l = QLabel('Land-use, land cover (LULC) map')
        self.grid_layout.addWidget(self.lulc_l)
        self.input_selectors.append(InputSelector('lulc_uri', self.root_app, self))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.grid_layout.addWidget(QLabel('Crop maps folder'))
        self.input_selectors.append(InputSelector('crop_maps_folder', self.root_app, self, 'folder'))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.nutritional_content_table_l = QLabel('Nutritional content table')
        self.grid_layout.addWidget(self.nutritional_content_table_l)
        self.input_selectors.append(InputSelector('nutritional_content_table_uri', self.root_app, self))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.nutritional_requirements_table_l = QLabel('Nutritional requirements table')
        self.grid_layout.addWidget(self.nutritional_requirements_table_l)
        self.input_selectors.append(InputSelector('nutritional_requirements_table_uri', self.root_app, self))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.population_map_l = QLabel('Population map')
        self.grid_layout.addWidget(self.population_map_l)
        self.input_selectors.append(InputSelector('population_uri', self.root_app, self))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.economic_value_l = QLabel('Economic value table')
        self.grid_layout.addWidget(self.economic_value_l)
        self.input_selectors.append(InputSelector('economic_value_table_uri', self.root_app, self))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.production_modifiers_l = QLabel('\nProduction modifiers (optional)')
        self.production_modifiers_l.setFont(config.bold_font)
        self.grid_layout.addWidget(self.production_modifiers_l)
        self.grid_layout.addWidget(QLabel())

        self.current_yield_l = QLabel('New yield map')
        self.grid_layout.addWidget(self.current_yield_l)
        self.input_selectors.append(InputSelector('new_yield_uri', self.root_app, self))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.potential_yield_l = QLabel('Potential yield map')
        self.grid_layout.addWidget(self.potential_yield_l)
        self.input_selectors.append(InputSelector('cotential_yield_uri', self.root_app, self))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.yield_increase_l = QLabel('Proportional yield increase factor')
        self.grid_layout.addWidget(self.yield_increase_l)
        self.input_selectors.append(InputSelector('proportional_yield_increase_factor', self.root_app, self, 'text'))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.pollinator_l = QLabel('Pollinator presence map')
        self.grid_layout.addWidget(self.pollinator_l)
        self.input_selectors.append(InputSelector('pollinator_presence_uri', self.root_app, self))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.water_availability_l = QLabel('Water availability map')
        self.grid_layout.addWidget(self.water_availability_l)
        self.input_selectors.append(InputSelector('water_availability_uri', self.root_app, self))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.demographic_inputs_l = QLabel('\nDemographics (optional)')
        self.demographic_inputs_l.setFont(config.bold_font)
        self.grid_layout.addWidget(self.demographic_inputs_l)
        self.grid_layout.addWidget(QLabel())

        self.demographic_groups_list_l = QLabel('Demographic groups (separate with comma)')
        self.grid_layout.addWidget(self.demographic_groups_list_l)
        self.input_selectors.append(InputSelector('demographic_groups_list', self.root_app, self, 'text'))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.demographic_maps_folder_l = QLabel('Demographic maps folder')
        self.grid_layout.addWidget(self.demographic_maps_folder_l)
        self.input_selectors.append(InputSelector('demographics_folder', self.root_app, self, 'folder'))
        self.grid_layout.addWidget(self.input_selectors[-1])

        self.run_details_header_l = QLabel('\nRun details')
        self.run_details_header_l.setFont(config.minor_heading_font)
        self.main_layout.addWidget(self.run_details_header_l)

        self.run_scroll = ScrollWidget()
        self.run_scroll.setMinimumHeight(150)
        self.main_layout.addWidget(self.run_scroll)
        self.run_scroll.scroll_layout.setAlignment(Qt.AlignTop)
        self.run_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.run_scroll.scroll_layout.setStretch(44, 1)

        self.run_details = QLabel('Ready to run.')
        self.run_scroll.scroll_layout.addWidget(self.run_details)

        self.percent_complete_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.percent_complete_hbox)
        self.percent_complete_header_l = QLabel('Percent complete: ')
        self.percent_complete_hbox.addWidget(self.percent_complete_header_l)
        self.percent_complete_l = QLabel('0.0')
        self.percent_complete_hbox.addWidget(self.percent_complete_l)

        self.main_layout.addWidget(QLabel(''))

        self.percent_complete_hbox.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))

        self.run_cancel_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.run_cancel_hbox)
        self.run_pb = QPushButton('Run')
        self.run_pb.clicked.connect(self.run)
        self.run_cancel_hbox.addWidget(self.run_pb)
        self.cancel_pb = QPushButton('Close')
        self.cancel_pb.clicked.connect(self.cancel)
        self.run_cancel_hbox.addWidget(self.cancel_pb)

        if odict:
            self.fill_inputs_from_dict(odict)
        else:
            pass

        self.exec_()

    def fill_inputs_from_dict(self, input_dict):
        for selector in self.input_selectors:
            if selector.name in input_dict:
                selector.set_input(input_dict[selector.name])

    def create_odict_from_inputs(self):
        output_odict = OrderedDict()
        for selector in self.input_selectors:
            output_odict.update({selector.name: selector.get_input()})

        return output_odict

    def save_odict_as_setup_file(self, odict_input, output_uri):
        utilities.iterable_to_json(odict_input, output_uri)

    def update_run_details(self, str_to_add, same_line=False):
        if same_line:
            new_text = str(self.run_details.text()) + str(str_to_add)
        else:
            new_text = str(self.run_details.text()) + '\n' + str(str_to_add)
        self.run_details.setText(new_text)
        self.output_scrollbar = self.run_scroll.scroll_area.verticalScrollBar()
        self.output_scrollbar.setValue(self.output_scrollbar.maximum())

    def run(self):
        self.args = self.create_odict_from_inputs()
        # Because this is a setup run, manually set the output folder
        self.args['output_folder'] = os.path.join(self.root_app.project_folder, 'output/model_setup_runs/nutritional_adequacy')
        self.save_odict_as_setup_file(self.args, self.setup_run_file_uri)
        self.runner = ProcessingThread(self.args, 'nutritional_adequacy', self.root_app, self) # NOTE I run all non InVEST models via ProcessingThreads but not invest ones because they have their own multithreading built in.
        self.root_app.threads.append(self.runner)
        self.runner.start()

    def cancel(self):
        try:
            self.runner.stop()
        except:
            'not needed'
        self.close()