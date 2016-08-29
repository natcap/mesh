import sys
import os
import logging
from collections import OrderedDict
import warnings
import shutil
import json
import re
from datetime import datetime

from markdown import markdown
from osgeo import gdal, ogr
import numpy as np
from PyQt4 import QtGui
from PyQt4 import QtCore

import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
import zipfile

# EXE BUILD NOTE, THIS MAY NEED TO BE MANUALLY FOUND
#os.environ['GDAL_DATA'] = 'C:/Anaconda2/Library/share/gdal'

from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib import rcParams  # Used below to make Matplotlib automatically adjust to window size.
#from matplotlib.patches import Polygon
#from matplotlib.collections import PatchCollection
#from matplotlib.patches import PathPatch

from mesh_models.data_creation import data_creation
from mesh_utilities import config
from mesh_utilities import utilities
from base_classes import MeshAbstractObject, ScrollWidget, ProcessingThread, NamedSpecifyButton, Listener
from natcap.invest.iui import modelui
import natcap.invest.iui


LOGGER = config.LOGGER  # I store all variables that need to be used across modules in config
LOGGER.setLevel(logging.WARN)
rcParams.update({'figure.autolayout': True})  # This line makes matplotlib automatically change the fig size according to legends, labels etc.

class InvestPluginButton(QtGui.QPushButton):
    """ """

    def __init__(self, parent=None):
        super(InvestPluginButton, self).__init__()
        self.parent = parent
        print "InvestPluginButton"
        print parent

        self.setText("InVEST Models")
        #connect the button (self) with the filename function.
        self.clicked.connect(self.launch_invest_models_dialog)

    def launch_invest_models_dialog(self):
        InvestModelChoicesDialog(self.parent)


class InvestModelChoicesDialog(QtGui.QDialog):
    """ """
    def __init__(self, parent=None):
        super(InvestModelChoicesDialog, self).__init__()
        # Create the layout for the Dialog
        self.main_layout = QtGui.QVBoxLayout()
        self.setLayout(self.main_layout)
        print "InvestModelChoicesDialog"
        print parent

        self.setWindowTitle('Available Plugins')
        self.title_l = QtGui.QLabel('Select from the following model choices')
        #self.title_l.setFont(config.heading_font)
        self.main_layout.addWidget(self.title_l)

        scroll_widget = ScrollWidget(self, self)
        self.main_layout.addWidget(scroll_widget)
        scroll_widget.scroll_layout.setAlignment(QtCore.Qt.AlignTop)
        scroll_widget.setMinimumSize(400, 500)

        invest_models_mapped_dir = os.path.join(
            '..', 'settings', 'default_setup_files')

        invest_models = []

        for file in os.listdir(invest_models_mapped_dir):
            if file.endswith('.json') and 'setup_file' in file:

                model_name_search = re.search("(.*)_setup_file.json", file)
                model_name = model_name_search.group(1)
                invest_models.append(model_name)

        # New layout to hold Submit / Cancel button
        vertical_layout = QtGui.QVBoxLayout()

        for invest_model in invest_models:
            # Don't add padding to left of Submit button
            #horizontal_layout.addStretch(0)
            #invest_button = QtGui.QPushButton(invest_model)
            invest_button = InvestModelButton(invest_model, parent)

            #self.cb = QCheckBox(self.long_name)
            #self.main_layout.addWidget(self.cb)

            #invest_button.clicked.connect(self.invest_model_choices)
            vertical_layout.addWidget(invest_button)

        scroll_widget.scroll_layout.addLayout(vertical_layout)

        self.show()

class InvestModelButton(QtGui.QPushButton):
    """ """
    def __init__(self, model_name, parent=None):
        super(InvestModelButton, self).__init__()
        self.model_name = model_name
        print "InvestModelButton"
        print parent
        self.parent = parent

        self.setText(model_name)
        #connect the button (self) with the filename function.
        self.clicked.connect(self.create_new_invest_model)

    def create_new_invest_model(self):
        new_model = InvestModel(self.model_name, self.parent)
        self.parent.models_dock.models_widget.load_plugin_element(new_model.name, new_model.args, new_model)


class InvestModel(QtGui.QWidget):
    """
    """

    def __init__(self, name, parent=None):
        super(InvestModel, self).__init__()
        self.mesh_app = parent
        self.name = name
        self.json_file = self.copy_json_file()
        self.args = self.setup_args()

    def copy_json_file(self):
        json_file_name = "%s.json" % self.name
        # Get the location of the InVEST model json file, which is
        # distributed with InVEST in IUI package
        invest_model_json_path = os.path.join(
            os.path.split(natcap.invest.iui.__file__)[0], json_file_name)
        # Path to copy InVEST json file to
        invest_json_copy = os.path.join(
            self.mesh_app.project_folder, json_file_name)
        shutil.copy(invest_model_json_path, invest_json_copy)
        # Read in copied InVEST Json to dictionary
        return invest_json_copy

    def setup_args(self):
        args = {}
        args['name'] = self.name
        args['model_type'] = 'InVEST Model'
        args['model_args'] = ''
        args['checked'] = ''
        json_dump = open(self.json_file).read()
        json_dict = json.loads(json_dump)
        args['long_name'] = json_dict['label']
        args['execute'] = json_dict['targetScript']

        # the module name needs to be extracted differently if it's a python
        # module or if it's a file on disk.  While we're at it, we can also
        # locate the model to be loaded.
        #try:
        #    if os.path.isfile(module):
        #        model = importlib.import_module(
        #            imp.load_source('model', module))
        #    else:
        #        model = importlib.import_module(module)
        #        LOGGER.debug('Loading %s in frozen environment', model)
        #except ImportError as exception:
        #    LOGGER.error('ImportError found when locating %s', module)
        #    self.printTraceback()
        #    self.setThreadFailed(True, exception)
        #    return


        return args

    def check_if_validated(self):
        """Makes sure that a given InVEST setup run has completed successfully.

        Success is determined by two parts, the first being the log file
        from the InVEST run. If the latest file has
        "Operations completed successfully", then the first part is validated.
        The second part to check is that the user saved a json archive of
        the parameters that were used for the run. If that file exists in
        the correct location the second part is validated.

        Returns
            True if a run for the associated model completed successfully
            and the json archive file exists, False otherwise
        """
        # Get path for InVEST model logfile and archive
        log_file_dir = os.path.join(
            self.mesh_app.project_folder, 'output', 'model_setup_runs',
            self.name)
        # String to match to verify a valid run of an InVEST model
        success_string = "Operations completed successfully"

        # Initialize validators to False
        invest_run_valid = False
        archive_params_valid = False

        if os.path.isdir(log_file_dir):
            # Initialize variables to track latest log
            date = ""
            newest_log_path = ""
            for file in os.listdir(log_file_dir):
                if file.endswith('.txt') and "log" in file:
                    log_file_path = os.path.join(log_file_dir, file)
                    # Search for and capture the values comprising the date
                    result = re.search("log-([0-9-_]*)", log_file_path)
                    # Convert from string to Datetime object for comparisons
                    new_date = datetime.strptime(
                        result.group(1), "%Y-%m-%d--%H_%M_%S")
                    if date == "" or new_date > date:
                        # Either first log or the newest log
                        date = new_date
                        newest_log_path = log_file_path
                elif file.endswith('.json') and "archive" in file:
                    archive_params_valid = True
            if newest_log_path != "" and success_string in open(newest_log_path).read():
                invest_run_valid = True

        return invest_run_valid and archive_params_valid

    def setup_invest_model(self, sender):
        """
        There are two basic ways a model might be run in MESH. The setup run, which in the case of invest models creates
        the json file of model run parameters. Setup runs use the UI of invest, or a custom MESH dialog.
        Next is the full run, which uses the json setup files and calls the selected models iteratively without bringing up the ui
         and instead uses the values defined in scenarios. This method calls the ProcessingThread class to handle calculations.
        """
        self.sender = sender

        # Check if trying to create a differenct scenario with
        # InVEST Scenario generator
        #if isinstance(self.sender, Scenario):
            # If a call from Scenario the sender.name is going to be the name
            # of the user labeled scenario and not the InVEST model name
        #    model_name = 'scenario_generator'
        #else:
        model_name = self.sender.name

        # Json file name with extension for InVEST model model.name
        json_file_name = model_name + '.json'
        # Path to CSV file for mapping MESH input data to the model model.name
        input_mapping_uri = os.path.join(
            '../settings/default_setup_files',
            '%s_input_mapping.csv' % model_name)
        # Read the input mapping CSV into a dictionary
        input_mapping = utilities.file_to_python_object(input_mapping_uri)
        # Path where an InVEST setup run json file is saved. If the model
        # has already been run and this file exists, use this as default.
        existing_last_run_uri = os.path.join(
            self.mesh_app.project_folder, 'output', 'model_setup_runs',
            model_name, '%s_setup_file.json' % model_name)
        # Path to the MESH default json parameters.
        default_last_run_uri = os.path.join(
            self.mesh_app.default_setup_files_folder,
            '%s_setup_file.json' % model_name)
        # Check to see if an existing json file exists from a previous
        # setup run
        if os.path.exists(existing_last_run_uri):
            new_json_path = existing_last_run_uri
        else:
            # Read in MESH setup json to a dictionary
            default_args = utilities.file_to_python_object(
                default_last_run_uri)
            # Read in copied InVEST Json to dictionary
            invest_json_dict = utilities.file_to_python_object(
                self.json_file)
            # Update the dictionary based on MESH setup json and input mapping
            # files
            new_json_args = self.modify_invest_args(
                invest_json_dict, default_args, model_name, input_mapping)
            # Make the model directory, which will also be the InVEST workspace
            # In order to place the json file in that location
            if not os.path.isdir(os.path.dirname(existing_last_run_uri)):
                os.mkdir(os.path.dirname(existing_last_run_uri))
            # Write updated dictionary to new json file.
            new_json_path = existing_last_run_uri
            with open(new_json_path, 'w') as fp:
                json.dump(new_json_args, fp)
            # Don't need to keep arounnd copied InVEST Json file, delete.
            os.remove(self.json_file)
            self.json_file = new_json_path

        self.mesh_app.models_dock.models_widget.running_setup_uis.append(modelui.main(new_json_path))

    def modify_invest_args(self, args, vals, model_name, input_mapping=None):
        """Walks a dictionary and updates the values.

        Specifically copies the dictionary 'args', and walks the dictionary
        looking for the key "args_id". This key is a specific InVEST key.
        When found it updates the corresponding "defaultValue" from 'vals'
        and / or 'input_mapping'.

        Parameters:
            args (dict) - a dictionary representing an InVEST UI json file.
                This is the dictionary to walk and update.
            vals (dict) - a single level dictionary with keys matching
                'args' keys "args_id" values. 'vals' values determine
                how 'args' should be updated.
            model_name (string) - a string for the InVEST model name being
                updated
            input_mapping (dict) - a dictionary with keys matching
                'args' keys "args_id" values. The values update 'args'.

        Return:
            A copied, modified dictionary of args
        """
        return_args = args.copy()

        def recursive_update(args_copy, vals, model_name, input_mapping):
            """Recursive function to walk dictionary."""
            if ("args_id" in args_copy) and (args_copy["args_id"] in vals):
                key = args_copy["args_id"]
                if vals[args_copy["args_id"]] == 'set_based_on_project_input':
                    #if isinstance(self.sender, Scenario):
                    #    args_copy["defaultValue"] = os.path.join(
                    #        self.root_app.project_folder, 'input', 'Baseline',
                    #        input_mapping[key]['save_location'])
                    #else:
                    args_copy["defaultValue"] = os.path.join(
                            self.mesh_app.project_folder,
                            input_mapping[key]['save_location'])
                # I THINK this should only  be needed for setting the workspace.
                elif vals[args_copy["args_id"]] == 'set_based_on_model_setup_runs_folder':
                    args_copy["defaultValue"] = os.path.join(
                        self.mesh_app.project_folder, 'output',
                        'model_setup_runs', model_name)
                elif vals[args_copy["args_id"]] == 'set_based_on_scenario':
                        args_copy["defaultValue"] = os.path.join(
                            self.mesh_app.project_folder, 'input',
                            self.sender.name)
                # Check to see if there's another list of dictionaries and
                # if so, walk them.
                if "elements" in args_copy:
                    for sub_args in args_copy["elements"]:
                        recursive_update(
                            sub_args, vals, model_name, input_mapping)
            elif "elements" in args_copy:
                for sub_args in args_copy["elements"]:
                    recursive_update(
                        sub_args, vals, model_name, input_mapping)
            else:
                # It's possible that a dictionary doesn't have either
                # 'args_id' or 'elements', in which case we don't care
                pass

        # Start recursive walk of dictionary
        recursive_update(return_args, vals, model_name, input_mapping)

        return return_args

