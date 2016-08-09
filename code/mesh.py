# coding=utf-8

"""
Mapping Ecosystem Services to Human wellbeing, MESH, is a toolkit that helps calculate the values that nature provides
to humans in the form of ecosystem services (ES). MESH combines existing ES production function models from InVEST
(more to come soon) into a combined framework that enables creating input data to define scenarios, interaction between
the ES models, and reporting/visualization of the results.


"""

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
from PyQt4.QtGui import *
from PyQt4.QtCore import *

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


class MeshApplication(MeshAbstractObject, QMainWindow):
    """
    Main application, an instance of which is passed to all other objects as root_app. hh
    """

    def __init__(self):
        super(MeshApplication, self).__init__()

        # Application state variables
        self.visible_central_widget_name = 'model_runs'  # State variable called in update_ui to see which widget should be the visible one in the central column.
        self.args_queue = OrderedDict()  # When MESH runs a model, it adds an args dictionaryt into this and uses run_next_in_queue() to run the models sequentially.
        self.visible_matrix = None  # Stored array ready for display in Matplotlib
        self.project_to_load_on_launch = ''
        self.project_name = ''
        self.project_aoi = ''
        self.threads = []  # Processing threads get added here.
        self.settings_folder = '../settings/'
        self.default_setup_files_folder = '../settings/default_setup_files'
        self.initialization_preferences_uri = os.path.join(self.settings_folder, 'initialization_preferences.csv')  # This file is the main input/initialization points of it all.

        # Project state variables
        self.decision_contexts = OrderedDict()
        self.external_drivers = OrderedDict()
        self.assessment_times = OrderedDict()

        # Initialize application from preferences files and build UI
        self.load_or_create_application_settings_files()

        # build UI elements
        self.create_application_window()
        self.create_docks()
        self.create_central_widgets()

        # Launch model from preferences file and load/create model_elements settings files
        if self.project_to_load_on_launch:
            self.load_project_by_name(self.project_to_load_on_launch)
        else:
            self.new_project_widget.setVisible(True)

    def load_or_create_application_settings_files(self):
        # Create project-independent settings
        # Note that here an below I use a paradigm where I check for a CSV full of preferences, load it if it's present,
        # or if it's not present, I create it from a hard-coded function that specifies exactly what the preferences might be.
        if not os.path.exists(self.initialization_preferences_uri):
            self.create_initialization_preferences_from_default()
        self.initialize_model_from_preferences(self.initialization_preferences_uri)

        if not os.path.exists(self.application_args['baseline_generators_settings_uri']):
            # TODO DOUG 6 check that THIS one is done exactly like the other CSV loading things, just generally
            # debug this, try to get it to fail with deleting settings files, etc
            self.create_baseline_generators_settings_file_from_default()
        self.baseline_generators_settings = utilities.file_to_python_object(
            self.application_args['baseline_generators_settings_uri'])

        if not os.path.exists(self.application_args['scenario_generators_settings_uri']):
            self.create_scenario_generators_settings_file_from_default()
        self.scenario_generators_settings = utilities.file_to_python_object(
            self.application_args['scenario_generators_settings_uri'])

    def create_initialization_preferences_from_default(self):
        """
        Creates default initialization preferences from hard-coded defaults. This should not be called unless the user
        accidentally deletes the initialization_preferences.csv file
        """
        initialization_preferences = OrderedDict()
        initialization_preferences.update({'project_to_load_on_launch': ''})
        initialization_preferences.update({'project_folder_location': '../projects/'})
        initialization_preferences.update({'base_data_folder': '../base_data/'})
        initialization_preferences.update(
            {'scenario_generators_settings_uri': os.path.join(self.settings_folder, 'scenario_generators.csv')})
        initialization_preferences.update(
            {'baseline_generators_settings_uri': os.path.join(self.settings_folder, 'baseline_generators.csv')})
        initialization_preferences.update({'loaded_plugins': ''})
        utilities.python_object_to_csv(initialization_preferences, self.initialization_preferences_uri)

    def initialize_model_from_preferences(self, initialization_preferences_uri):
        """
        The values saved in initialization_preferences_uri (in the root dir by default) initially populate user variables that are independent of which project is being worked on.
        """
        self.application_args = utilities.file_to_python_object(initialization_preferences_uri)
        if self.application_args['project_to_load_on_launch']:
            self.project_to_load_on_launch = self.application_args['project_to_load_on_launch']
            self.project_name = self.project_to_load_on_launch
            self.project_folder = os.path.join(self.application_args['project_folder_location'], self.project_name)
            config.global_folder = self.project_folder  # config provides a global set of variables shared across py files
        # TODO JUSTIN Had to disable this due to fresh install problem.
        # else: # No project was defined, so force the user to make a new one.
        #     self.create_new_project()


        self.base_data_folder = self.application_args['base_data_folder']

    def create_application_window(self):
        if 'window_size' in self.application_args:
            'NYI in updating the preferences csv, but could be done manually.'
            rectangle = QApplication.desktop().screenGeometry()
            self.resize(rectangle.width(), rectangle.height())
        else:
            self.resize(1550, 850)

        self.setWindowTitle(
            'MESH Model: Mapping Ecosystem Services to Human well-being')
        self.mainWindowIcon = QIcon()
        self.mainWindowIcon.addPixmap(QPixmap('icons/mesh_green.png'), QIcon.Normal, QIcon.Off)
        self.setWindowIcon(self.mainWindowIcon)

        # Add Actions. Actions define BOTH toolbar items and menu items.
        self.new_project_qaction = QAction(self)
        self.new_project_qaction.setText("New")
        self.new_project_icon = QIcon()
        self.new_project_icon.addPixmap(QPixmap("icons/document-new-3.png"), QIcon.Normal, QIcon.Off)
        self.new_project_qaction.setIcon(self.new_project_icon)
        self.new_project_qaction.triggered.connect(self.create_new_project)
        self.open_project_qaction = QAction(self)
        self.open_project_qaction.setText("Open")
        self.open_project_icon = QIcon()
        self.open_project_icon.addPixmap(QPixmap("icons/document-open-7.png"), QIcon.Normal, QIcon.Off)
        self.open_project_qaction.setIcon(self.open_project_icon)
        self.open_project_qaction.triggered.connect(self.select_project_to_load)
        self.save_project_qaction = QAction(self)
        self.save_project_qaction.setText("Save")
        self.save_project_icon = QIcon()
        self.save_project_icon.addPixmap(QPixmap("icons/document-export.png"), QIcon.Normal, QIcon.Off)
        self.save_project_qaction.setIcon(self.save_project_icon)
        self.save_project_qaction.triggered.connect(self.save_project)
        self.unload_project_qaction = QAction(self)
        self.unload_project_qaction.setText("Unload project")
        self.unload_project_icon = QIcon()
        self.unload_project_icon.addPixmap(QPixmap("icons/crab16.png"), QIcon.Normal, QIcon.Off)
        self.unload_project_qaction.setIcon(self.unload_project_icon)
        self.unload_project_qaction.triggered.connect(self.unload_project)

        # By default, MESH assumes you have the base data set in ../base_data. However, you can override that by manually setting it here.
        self.configure_base_data_folder_qaction = QAction(self)
        self.configure_base_data_folder_qaction.setText("Set base data location")
        self.configure_base_data_folder_icon = QIcon()
        self.configure_base_data_folder_icon.addPixmap(QPixmap("icons/crab16.png"), QIcon.Normal, QIcon.Off)
        self.configure_base_data_folder_qaction.setIcon(self.configure_base_data_folder_icon)
        self.configure_base_data_folder_qaction.triggered.connect(self.create_configure_base_data_dialog)

        self.qaction_state_actiongroup = QActionGroup(self)
        self.run_models_qaction = QAction(self)
        self.qaction_state_actiongroup.addAction(self.run_models_qaction)
        self.run_models_qaction.triggered.connect(self.place_model_runs_widget)
        self.run_models_qaction.setText("Run MESH Model")
        self.run_models_qaction.setCheckable(True)
        self.map_viewer_qaction = QAction(self)
        self.qaction_state_actiongroup.addAction(self.map_viewer_qaction)
        self.map_viewer_qaction.triggered.connect(self.set_map_viewer_as_central_widget)
        self.map_viewer_qaction.setText("View Maps")
        self.map_viewer_qaction.setCheckable(True)
        self.create_report_qaction = QAction(self)
        self.qaction_state_actiongroup.addAction(self.create_report_qaction)
        self.create_report_qaction.triggered.connect(self.set_report_generator_as_central_widget)
        self.create_report_qaction.setText("View/Create Report")
        self.create_report_qaction.setCheckable(True)

        # Create menubar and top-level menu items
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)
        self.file_menu = QMenu(self.menu_bar)
        self.file_menu.setTitle("File")
        self.view_menu = QMenu(self.menu_bar)
        self.view_menu.setTitle("View")
        self.help_menu = QMenu(self.menu_bar)
        self.help_menu.setTitle("Help")

        # Add actions under each top-level menu item
        self.file_menu.addAction(self.new_project_qaction)
        self.file_menu.addAction(self.open_project_qaction)
        self.file_menu.addAction(self.save_project_qaction)
        self.file_menu.addAction(self.unload_project_qaction)
        self.file_menu.addAction(self.configure_base_data_folder_qaction)
        self.view_menu.addAction(self.run_models_qaction)
        self.view_menu.addAction(self.map_viewer_qaction)
        self.view_menu.addAction(self.create_report_qaction)

        # Add the top-level actions to the menu
        self.menu_bar.addAction(self.file_menu.menuAction())
        self.menu_bar.addAction(self.view_menu.menuAction())
        self.menu_bar.addAction(self.help_menu.menuAction())

        # Create toolbars
        self.file_tool_bar = QToolBar(self)
        self.file_tool_bar.setWindowTitle("File toolbar")
        self.addToolBar(Qt.TopToolBarArea, self.file_tool_bar)
        self.file_tool_bar.addAction(self.new_project_qaction)
        self.file_tool_bar.addAction(self.open_project_qaction)
        self.file_tool_bar.addAction(self.save_project_qaction)

        self.view_tool_bar = QToolBar(self)
        self.view_tool_bar.setWindowTitle("View toolbar")
        self.addToolBar(Qt.TopToolBarArea, self.view_tool_bar)
        self.view_tool_bar.addAction(self.run_models_qaction)
        self.view_tool_bar.addAction(self.map_viewer_qaction)
        self.view_tool_bar.addAction(self.create_report_qaction)

        # Statusbar
        self.statusbar = QStatusBar(self)
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage('Ready')

        # Center column
        self.center_column_widget = QWidget()
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 3, 0, 0)  # Left, top, right, bottom
        self.main_layout.setSpacing(0)

        # In the following lines, I set the object name so that i can reference it in a stylesheet string.
        self.center_column_widget.setObjectName('center_column_widget_green')
        self.center_column_widget.setStyleSheet('#center_column_widget_green { background:rgb(222,228,229) }')

        self.center_column_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.center_column_widget)

    def create_docks(self):
        self.create_models_dock()
        self.create_scenarios_dock()
        self.create_map_widget()

        # self.tabifyDockWidget(self.models_dock, self.map_widget)

    def create_central_widgets(self):
        self.new_project_widget = NewProjectWidget(self, self)
        self.new_project_widget.setVisible(False)
        self.main_layout.addWidget(self.new_project_widget)

        self.model_runs_widget = ModelRunsWidget(self, self)
        self.model_runs_widget.setVisible(False)
        self.main_layout.addWidget(self.model_runs_widget)

        self.map_canvas_holder_widget = MapCanvasHolderWidget(self, self)
        self.map_canvas_holder_widget.setVisible(False)
        self.main_layout.addWidget(self.map_canvas_holder_widget)

        self.reports_widget = ReportsWidget(self, self)
        self.reports_widget.setVisible(False)
        self.main_layout.addWidget(self.reports_widget)

    def create_baseline_generators_settings_file_from_default(self):
        to_write = BaselinePopulatorDialog.default_state.copy()
        utilities.python_object_to_csv(to_write, self.application_args['baseline_generators_settings_uri'])

    def create_scenario_generators_settings_file_from_default(self):
        to_write = ScenarioPopulatorDialog.default_state.copy()
        utilities.python_object_to_csv(to_write, self.application_args['scenario_generators_settings_uri'])

    def create_default_project_settings_file_for_name(self, name):
        self.project_args = OrderedDict()
        self.project_args.update({'project_name': name})
        self.project_args.update({'project_aoi': ''})
        self.project_args.update(
            {'scenarios_settings_uri': os.path.join(self.project_folder, 'settings/scenarios.csv')})
        self.project_args.update({'models_settings_uri': os.path.join(self.project_folder, 'settings/models.csv')})
        self.project_args.update({'maps_settings_uri': os.path.join(self.project_folder, 'settings/maps.csv')})
        self.project_args.update(
            {'model_runs_settings_uri': os.path.join(self.project_folder, 'settings/model_runs.csv')})
        self.project_args.update({'reports_settings_uri': os.path.join(self.project_folder, 'settings/reports.csv')})
        utilities.python_object_to_csv(self.project_args,
                                       os.path.join(self.project_folder, 'settings/project_settings.csv'))

    def create_default_model_elements_settings_files(self, files_to_recreate='all'):
        if files_to_recreate == 'all' or files_to_recreate == 'scenarios':
            to_write = ScenariosWidget.default_state.copy()
            utilities.python_object_to_csv(to_write, self.project_args['scenarios_settings_uri'])

        if files_to_recreate == 'all' or files_to_recreate == 'models':
            to_write = ModelsWidget.default_state.copy()
            utilities.python_object_to_csv(to_write, self.project_args['models_settings_uri'])

        if files_to_recreate == 'all' or files_to_recreate == 'maps':
            to_write = MapWidget.default_state.copy()
            utilities.python_object_to_csv(to_write, self.project_args['maps_settings_uri'])

        if files_to_recreate == 'all' or files_to_recreate == 'model_runs':
            to_write = ModelRunsWidget.default_state.copy()
            utilities.python_object_to_csv(to_write, self.project_args['model_runs_settings_uri'])

        if files_to_recreate == 'all' or files_to_recreate == 'reports':
            to_write = ReportsWidget.default_state.copy()
            utilities.python_object_to_csv(to_write, self.project_args['reports_settings_uri'])

    def set_project_args_from_name(self, project_name):
        self.project_name = project_name
        self.project_folder = os.path.join('../projects/', self.project_name)
        config.global_folder = self.project_folder
        self.project_settings_folder = os.path.join(self.project_folder, 'settings')
        self.project_settings_file_uri = os.path.join(self.project_settings_folder, 'project_settings.csv')
        self.project_to_load_on_launch = self.project_name

        if os.path.exists(self.project_settings_file_uri):
            self.project_args = utilities.file_to_python_object(self.project_settings_file_uri)
        else:
            LOGGER.info('Recreated project_settings_file_uri. Ensure that was desired.')
            self.create_default_project_settings_file_for_name(project_name)
            self.project_args = utilities.file_to_python_object(self.project_settings_file_uri)

    def load_project_by_name(self, project_name):
        """
        Based on the project_name, the project root folder is identified. In that folder is a project_args.csv file that
        defines parameters to load specific to the project. project_args and application_args exist independent.
        """
        self.set_project_args_from_name(project_name)

        # Check each of the model element settings files and recreate from default if they don't exist.
        for key, value in self.project_args.items():
            if key == 'project_aoi':
                self.project_aoi = value
            if key.endswith('settings_uri'):
                if not os.path.exists(value):
                    type_of_file_to_recreate = os.path.splitext(os.path.split(value)[1])[0]
                    self.create_default_model_elements_settings_files(files_to_recreate=type_of_file_to_recreate)

        # Once the parject args are set/created/loaded, then call UI-element specific project loader functions.
        self.models_dock.models_widget.load_from_disk()
        self.map_widget.load_from_disk()
        self.scenarios_dock.scenarios_widget.load_from_disk()
        self.model_runs_widget.load_from_disk()
        self.reports_widget.load_from_disk()

        self.visible_central_widget_name = 'model_runs'

        self.update_ui()

    def set_project_aoi(self, aoi_uri):
        self.project_aoi = aoi_uri
        self.update_ui()

    def set_model_runs_as_central_widget(self):
        self.visible_central_widget_name = 'model_runs'
        self.update_ui()

    def set_report_generator_as_central_widget(self):
        self.visible_central_widget_name = 'report_generator'
        self.update_ui()

    def set_map_viewer_as_central_widget(self):
        self.visible_central_widget_name = 'map_viewer'
        self.update_ui()

    def update_ui(self):
        self.models_dock.models_widget.current_project_l.setText(self.project_name)
        if self.project_aoi:
            self.models_dock.models_widget.area_of_interest_l.setText(os.path.split(self.project_aoi)[1])
        else:
            self.models_dock.models_widget.area_of_interest_l.setText('--need to set area of interest--')

        if self.visible_central_widget_name == 'model_runs':
            self.place_model_runs_widget()
            self.model_runs_widget.update_runs_table()
        elif self.visible_central_widget_name == 'report_generator':
            self.place_report_generator()
        elif self.visible_central_widget_name == 'map_viewer':
            self.place_map_viewer()
        else:
            self.place_model_runs_widget()

        self.reports_widget.update_ui()

    def choose_set_aoi_method(self):
        self.choose_set_aoi_method_dialog = ChooseSetAOIMethodDialog(self, self)

    def process_finish_message(self, message, args=None):
        if message == 'model_finished':
            self.scenarios_dock.scenarios_widget.create_element(args['clipped_uri'])

    def create_models_dock(self):
        self.models_dock = ModelsDock(self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.models_dock)

    def create_scenarios_dock(self):
        self.scenarios_dock = ScenariosDock(
            self)  # Note that you have to have this extra self here as an arg to __init__
        self.addDockWidget(Qt.RightDockWidgetArea, self.scenarios_dock)

    def create_map_widget(self):
        self.map_widget = MapWidget(self, self)  # Note that you have to have this extra self here as an arg to __init__
        self.addDockWidget(Qt.RightDockWidgetArea, self.map_widget)

    def create_new_project(self):
        input_text, ok = QInputDialog.getText(self, 'Create new project', 'Name of new project:')
        input_text = str(input_text)

        if ok:
            if os.path.exists(os.path.join('..', 'projects', input_text)):
                QMessageBox.warning(
                    self, 'Project Already Exists',
                    "Project '%s' already exists. Specify a different name." % input_text)
            else:
                # TODO Justin, check that unload_project works even on fresh install.
                self.unload_project()

                self.project_args = OrderedDict()
                self.project_name = input_text
                self.project_args.update({'project_name': input_text})
                self.project_args['project_aoi'] = ''
                self.project_folder = os.path.join(
                    '..', 'projects', self.project_args['project_name'])

                config.global_folder = self.project_folder

                # Make the  directories
                try:
                    os.makedirs(os.path.join('../projects/', input_text))
                except:
                    LOGGER.debug('Couldn\'t make directory. Does it already exist?')

                try:
                    os.makedirs(os.path.join('../projects/', input_text, 'input/'))
                except:
                    LOGGER.debug('Couldn\'t make directory. Does it already exist?')

                try:
                    os.makedirs(os.path.join('../projects/', input_text, 'output/'))
                except:
                    LOGGER.debug('Couldn\'t make directory. Does it already exist?')

                try:
                    os.makedirs(os.path.join('../projects/', input_text, 'output/runs'))
                except:
                    LOGGER.debug('Couldn\'t make directory. Does it already exist?')

                try:
                    os.makedirs(os.path.join('../projects/', input_text, 'output/reports'))
                except:
                    LOGGER.debug('Couldn\'t make directory. Does it already exist?')

                try:
                    os.makedirs(os.path.join('../projects/', input_text, 'output/model_setup_runs'))
                except:
                    LOGGER.debug('Couldn\'t make directory. Does it already exist?')

                try:
                    os.makedirs(os.path.join('../projects/', input_text, 'settings/'))
                except:
                    LOGGER.debug('Couldn\'t make directory. Does it already exist?')

                self.create_default_project_settings_file_for_name(input_text)
                self.create_default_model_elements_settings_files()

                self.save_application_settings()
                self.load_project_by_name(self.project_args['project_name'])

    def select_project_to_load(self):
        project_uri = str(QFileDialog.getExistingDirectory(self, 'Select Project Directory', '../projects'))
        # The only requirement i have on something being a project is the folder exists and there is a settings subfolder. All other things, folders or files, will be recreated.
        if os.path.exists(project_uri) and os.path.exists(os.path.join(project_uri, 'settings')):
            self.unload_project()
            self.project_name = os.path.split(project_uri)[1]
            self.project_folder = project_uri
            config.global_folder = self.project_folder
            self.load_project_by_name(self.project_name)
        elif project_uri:
            self.message_box = QMessageBox(QMessageBox.Information, 'Error', 'Not a valid project folder.').exec_()

    def save_project(self):
        self.save_application_settings()
        self.save_project_settings()
        self.scenarios_dock.scenarios_widget.save_to_disk()
        self.map_widget.save_to_disk()
        self.models_dock.models_widget.save_to_disk()
        self.model_runs_widget.save_to_disk()
        self.reports_widget.save_to_disk()
        self.statusbar.showMessage('Project saved')

    def save_application_settings(self):
        self.application_args['project_to_load_on_launch'] = self.project_to_load_on_launch
        self.application_args['base_data_folder'] = self.base_data_folder
        utilities.python_object_to_csv(self.application_args, self.initialization_preferences_uri)

    def save_project_settings(self):
        self.project_args['project_aoi'] = self.project_aoi
        utilities.python_object_to_csv(self.project_args, self.project_settings_file_uri)

    def unload_project(self):
        self.project_name = ''
        self.project_folder = ''
        self.models_dock.models_widget.current_project_l.setText('--no project selected--')
        self.models_dock.models_widget.area_of_interest_l.setText('--no AOI selected--')

        self.models_dock.models_widget.unload_elements()
        self.map_widget.unload_elements()
        self.scenarios_dock.scenarios_widget.unload_elements()
        self.model_runs_widget.unload_elements()
        self.reports_widget.unload_elements()
        self.set_all_widgets_in_main_layout_invisible()

        self.new_project_widget.setVisible(True)

    def set_visible_matrix_by_name(self, name):
        self.uri_of_target = self.map_widget.elements[name].source_uri
        ds = gdal.Open(self.uri_of_target)
        band = ds.GetRasterBand(1)
        cols = ds.RasterXSize
        rows = ds.RasterYSize
        size = cols * rows

        if size > 5000000:
            max_side_length = 2048
            # TODO JUSTIN I did not write a memory robust plotting method. However, I've implemented this elsewhere so it can be added easily.
            LOGGER.critical(
                'Attempting to load very large array. May not display correctly or fail. Array set to the top left 2048 by 2048 cells.')
            self.visible_matrix = band.ReadAsArray(0, 0, max_side_length, max_side_length)
        else:
            self.visible_matrix = band.ReadAsArray()
        self.visible_map = self.map_widget.elements[name]
        del band
        del ds

        self.map_canvas_holder_widget.map_viewer_canvas.draw_visible_array()

    def set_all_widgets_in_main_layout_invisible(self):
        for i in reversed(range(self.main_layout.count())):
            self.main_layout.itemAt(i).widget().setVisible(False)

    def place_map_viewer(self):
        self.set_all_widgets_in_main_layout_invisible()
        self.map_canvas_holder_widget.setVisible(True)
        self.map_widget.raise_()
        self.map_viewer_qaction.setChecked(True)

    def place_model_runs_widget(self):
        self.set_all_widgets_in_main_layout_invisible()
        self.model_runs_widget.setVisible(True)
        self.models_dock.raise_()
        self.run_models_qaction.setChecked(True)

    def place_report_generator(self):
        self.set_all_widgets_in_main_layout_invisible()
        self.reports_widget.setVisible(True)

    def create_load_plugin_dialog(self):
        self.load_plugin_dialog = InstallPluginsDialog(self, self)

    def create_configure_base_data_dialog(self):
        self.configure_base_data_dialog = ConfigureBaseDataDialog(self, self)

    def create_define_decision_context_dialog(self):
        self.define_decision_context_dialog = DefineDecisionContextDialog(self, self)

    # TODO DOUG COMMENT 7 Implement a generalized version of this that verifies the base data is actually there and
    # installed.
    # Doug says: I think the update below is sufficient for now.
    # The sub directory list can be updated easily without creating a CSV
    # file mapping out the data. File IO errors should be handled in a dialogue
    def is_base_data_valid(self):
        """Verify Base Data folder is set up properly.

        Check to make sure that the base data folder exists and that is has
        major subfolders which are not empty

        Returns:
            True if setup, False otherwise
        """

        base_data_folder = self.base_data_folder
        # Major sub directories that should be present and not empty
        sub_directories = ['lulc', 'hydrosheds', 'models']

        for sub_dir in sub_directories:
            sub_dir_path = os.path.join(base_data_folder, sub_dir)
            if os.path.isdir(sub_dir_path):
                if not os.listdir(sub_dir_path):
                    return False
            else:
                return False
        return True


class ScenariosDock(MeshAbstractObject, QDockWidget):
    """
    Created by dock to hold Scenarios Widget.
    """

    def __init__(self, root_app=None, parent=None):
        super(ScenariosDock, self).__init__(root_app, parent)

        # Create dock window
        self.setMinimumSize(QSize(450, 250))
        self.setMaximumSize(QSize(2600, 10500))
        self.setSizePolicy(config.size_policy)
        self.setWindowTitle('Scenarios')
        self.scenarios_widget = ScenariosWidget(self.root_app)
        self.setWidget(self.scenarios_widget)


class ScenariosWidget(ScrollWidget):
    """
    Specifies which scenarios should be run in the full model and lets the user define new scenarios
    """
    default_element_args = OrderedDict()
    default_element_args['name'] = ''
    default_element_args['long_name'] = ''
    default_element_args['folder'] = ''
    default_element_args['sources'] = ''
    default_element_args['checked'] = ''
    default_element_args['is_baseline'] = ''
    default_element_args['needs_validation'] = ''
    default_element_args['validated'] = ''

    default_state = OrderedDict()
    default_state['Baseline'] = default_element_args.copy()
    default_state['Baseline']['name'] = 'Baseline'
    default_state['Baseline']['long_name'] = 'Baseline'
    default_state['Baseline']['checked'] = True
    default_state['Baseline']['is_baseline'] = True

    def __init__(self, root_app=None, parent=None):
        super(ScenariosWidget, self).__init__(root_app, parent)
        self.default_state = ScenariosWidget.default_state.copy()
        self.elements = OrderedDict()
        self.create_ui()

    def create_ui(self):

        self.scenarios_title_l = QLabel()
        self.scenarios_title_l.setText('Define Scenarios')
        self.scenarios_title_l.setFont(config.heading_font)
        self.scroll_layout.addWidget(self.scenarios_title_l)

        self.elements_vbox = QVBoxLayout()
        self.scroll_layout.addLayout(self.elements_vbox)

        # Add Scenarios and Group Scenarios
        self.add_scenarios_hbox = QHBoxLayout()
        self.elements_vbox.addLayout(self.add_scenarios_hbox)
        self.new_scenario_pb = QPushButton('New Scenario')
        self.new_scenario_icon = QIcon(QPixmap('icons/mesh_green.png'))
        self.new_scenario_pb.setIcon(self.new_scenario_icon)
        self.new_scenario_pb.clicked.connect(self.create_element_from_name_dialog)
        self.add_scenarios_hbox.addWidget(self.new_scenario_pb)
        self.load_scenario_pb = QPushButton('Load Scenario')
        self.load_scenario_icon = QIcon(QPixmap('icons/document-open.png'))
        self.load_scenario_pb.setIcon(self.load_scenario_icon)
        self.load_scenario_pb.clicked.connect(self.load_element_from_file_select_dialog)
        self.add_scenarios_hbox.addWidget(self.load_scenario_pb)
        self.validate_baseline_pb = QPushButton('Check if ready')
        self.unvalidated_icon = QIcon(QPixmap('icons/dialog-cancel-2.png'))
        self.validate_baseline_pb.setIcon(self.unvalidated_icon)
        self.validate_baseline_pb.clicked.connect(self.validate_baseline)
        self.add_scenarios_hbox.addWidget(self.validate_baseline_pb)
        # horizontal_line = QFrame()
        # horizontal_line.setFrameStyle(QFrame.HLine)
        # self.elements_vbox.addWidget(horizontal_line)
        self.scroll_layout.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))

    def load_element(self, name, args):
        if not name:
            LOGGER.warn('Asked to load an element with a blank name.')
        elif name in self.elements:
            LOGGER.warn('Attempted to add element that already exists.')
        else:
            element = Scenario(name, args, self.root_app, self)
            self.elements[name] = element
            self.elements_vbox.addWidget(element)

    def create_element(self, name, args=None):
        if not args:
            args = self.create_default_element_args(name)
        element = Scenario(name, args, self.root_app, self)
        self.elements[name] = element
        self.elements_vbox.addWidget(element)

    def create_default_element_args(self, name):
        args = ScenariosWidget.default_element_args.copy()
        args['long_name'] = name.replace('_', ' ')
        args['folder'] = os.path.join(self.root_app.project_folder, 'input/', name)
        return args

    def create_element_from_name_dialog(self):
        input_text, ok = QInputDialog.getText(self, 'Add scenario', 'Name of new or existing folder:')
        if ok:
            name = str(input_text)
            self.create_element(name)

    def load_from_disk(self):
        self.unload_elements()
        self.save_uri = self.root_app.project_args['scenarios_settings_uri']
        loaded_object = utilities.file_to_python_object(self.save_uri)

        if isinstance(loaded_object, list):
            self.elements = OrderedDict()
        else:
            for name, args in loaded_object.items():
                default_args = self.create_default_element_args(name)
                for default_key, default_value in default_args.items():
                    if default_key not in args or not args[default_key]:
                        args[default_key] = default_value
                self.load_element(name, args)

    def load_element_from_file_select_dialog(self):
        input_text = str(QFileDialog.getExistingDirectory(self, 'Select folder of maps', self.root_app.project_folder))
        if input_text:
            name = os.path.split(input_text)[1]
            args = self.create_default_element_args(name)
            self.load_element(name, args)

    def unload_elements(self):
        for element in self.elements.values():
            element.remove_self()

    def save_to_disk(self):
        if len(self.elements) == 0:
            print('This code should not be run because the default always contains at least the Baseline scenario.')
            to_write = ','.join([name for name in self.default_state[''].keys()])
        else:
            to_write = OrderedDict()
            for name, element in self.elements.items():
                to_write.update({name: element.get_element_state_as_args()})
        utilities.python_object_to_csv(to_write, self.save_uri)

    def get_checked_elements(self):
        checked_elements = []
        for element in self.elements.values():
            if element.cb.isChecked():
                checked_elements.append(element)
        return checked_elements

    def validate_baseline(self):
        validates = True
        for model in self.root_app.models_dock.models_widget.elements.values():
            if model.cb.isChecked():
                if model.model_status_l.text() == 'Not ready':
                    validates = False
        if validates:
            self.validated_icon = QIcon(QPixmap('icons/dialog-ok-2.png'))
            self.validate_baseline_pb.setIcon(self.validated_icon)
            self.validate_baseline_pb.setText('Ready!')


class Scenario(MeshAbstractObject, QWidget):
    """
    Scenarios can be etierh baseline or scenario scenarios and are a reference to a folder and a set of inputs that
    define the scenario.
    """

    def __init__(self, name, args, root_app=None, parent=None):
        super(Scenario, self).__init__(root_app, parent)
        self.name = name
        self.args = args
        self.initialize_from_args()

        self.create_ui()

        try:
            os.makedirs(self.folder)
        except:
            LOGGER.debug('Couldn\'t make directory. Does it already exist?')

        self.set_state_from_args()

    def create_ui(self):
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)
        self.cb = QCheckBox(self.long_name)
        self.main_layout.addWidget(self.cb)
        self.main_layout.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        self.elements_vbox = QVBoxLayout()
        self.elements_vbox.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addLayout(self.elements_vbox)

        # if self.name == 'Baseline':
        #     self.baseline_validation_status_l = QLabel('--No data specified for Baseline--')
        #     #self.num_sources_l = QLabel()
        #     self.elements_vbox.addWidget(self.baseline_validation_status_l)

        # if self.name != 'Baseline':
        #     self.populate_scenario_source_pb = QPushButton()
        #     self.add_icon = QIcon()
        #     self.add_icon.addPixmap(QPixmap('icons/db_add.png'), QIcon.Normal, QIcon.Off)
        #     self.populate_scenario_source_pb.setIcon(self.add_icon)
        #     self.populate_scenario_source_pb.setMaximumWidth(32)
        #     self.main_layout.addWidget(self.populate_scenario_source_pb)
        #     self.populate_scenario_source_pb.clicked.connect(self.create_populate_scenario_source_dialog)

        self.populate_scenario_source_pb = QPushButton()
        self.add_icon = QIcon()
        self.add_icon.addPixmap(QPixmap('icons/db_add.png'), QIcon.Normal, QIcon.Off)
        self.populate_scenario_source_pb.setIcon(self.add_icon)
        self.populate_scenario_source_pb.setMaximumWidth(32)
        self.main_layout.addWidget(self.populate_scenario_source_pb)

        if self.name == 'Baseline':
            self.populate_scenario_source_pb.clicked.connect(self.create_populate_baseline_sources_dialog)
        else:
            self.populate_scenario_source_pb.clicked.connect(self.create_populate_scenario_source_dialog)

        self.add_to_maps_pb = QPushButton()
        self.add_to_maps_icon = QIcon()
        self.add_to_maps_icon.addPixmap(QPixmap('icons/arrow-right.png'), QIcon.Normal, QIcon.Off)
        self.add_to_maps_pb.setIcon(self.add_to_maps_icon)
        self.main_layout.addWidget(self.add_to_maps_pb)
        self.add_to_maps_pb.clicked.connect(self.add_map_signal_wrapper)
        self.delete_scenario_pb = QPushButton()
        self.delete_icon = QIcon(QPixmap('icons/dialog-cancel-5.png'))
        self.delete_scenario_pb.setIcon(self.delete_icon)
        if self.name == 'Baseline':
            self.delete_scenario_pb.clicked.connect(self.unload_elements)
        else:
            self.delete_scenario_pb.clicked.connect(self.remove_self)
        self.main_layout.addWidget(self.delete_scenario_pb)

        # if self.name == 'Baseline':
        #     self.delete_scenario_pb.setEnabled(False)

    def initialize_from_args(self):
        self.long_name = self.args['long_name']
        self.folder = self.args['folder']
        self.elements = OrderedDict()
        self.is_baseline = utilities.convert_to_bool(self.args['is_baseline'])
        self.needs_validation = utilities.convert_to_bool(self.args['needs_validation'])
        self.validated = utilities.convert_to_bool(self.args['validated'])

    def set_state_from_args(self):
        if utilities.convert_to_bool(self.args['checked']):
            self.cb.setChecked(True)
        else:
            self.cb.setChecked(False)

        if isinstance(self.args['sources'], str):
            self.load_element(self.args['sources'], self.args['sources'])  # NOTE This line is trouble because of my shortcut to have the name == the uri.
        elif isinstance(self.args['sources'], list):
            for name in self.args['sources']:
                self.load_element(name,  name)  # NOTE This line is trouble because of my shortcut to have the name == the uri.

    def get_element_state_as_args(self):
        to_return = OrderedDict()
        to_return['name'] = self.name
        to_return['long_name'] = self.long_name
        to_return['folder'] = self.folder

        # The code below is tricky. Initially, I did not have sources fully implemented in their own CSV save file,
        # this messes up when loading a source from a non-project folder because it crops the beginning of the path.
        # I fixed it by just requireing that uri == name
        to_return['sources'] = [self.elements[i].uri for i in self.elements]
        if self.cb.isChecked():
            to_return['checked'] = 'True'
        else:
            to_return['checked'] = 'False'
        to_return['is_baseline'] = str(self.is_baseline)
        to_return['needs_validation'] = str(self.needs_validation)
        to_return['validated'] = str(self.validated)
        return to_return

    def remove_self(self):
        del self.parent.elements[self.name]
        self.setParent(None)
        # TODO JUSTIN Implement a good way to safely remove files from OS safely. Currently, many files are created with ramndom names rather than temp files.

    def load_element(self, name, uri):
        if not name:
            LOGGER.debug('Asked to load an element with a blank name.')
        elif name in self.elements:
            LOGGER.debug('Attempted to add element that already exists.')
        else:
            element = Source(name, uri, self.root_app, self)
            self.elements[name] = element
            self.elements_vbox.addWidget(element)

            # if not self.name == 'Baseline':
            #     self.elements_vbox.addWidget(element)
            # else:
            #     self.update_baseline_elements()

    def update_baseline_elements(self):
        num_elements_in_baseline = len(self.elements)
        if num_elements_in_baseline:
            self.num_sources_l.setText('Data files in Baseline: ' + str(num_elements_in_baseline))
        else:
            self.num_sources_l.setText('--need to add maps to baseline--')

    def create_populate_baseline_sources_dialog(self):
        self.create_baseline_data_dialog = BaselinePopulatorDialog(self.root_app, self)
        # self.create_baseline_data_dialog = CreateBaselineDataDialog(self.root_app, self)

        # OLD CODE: This was from before i had data-source specific generation methods.
        # self.populate_baseline_dialog = BaselinePopulatorDialog(self.root_app, self)

    def create_populate_scenario_source_dialog(self):
        self.populate_scenario_dialog = ScenarioPopulatorDialog(self.root_app, self)

    def paintEvent(self, e):
        """
        custom widgets in QT cannnot be styled unless they are given a paintEvent
        see http://zetcode.com/gui/pyqt4/customwidgets/
        """
        qp = QPainter()
        qp.begin(self)
        qp.setPen(QColor(255, 255, 255))
        qp.setBrush(QColor(255, 255, 255))
        qp.drawRect(0, 0, 100000, 100000)  # set large so that expands when widget expands
        qp.end()

    def validate_baseline(self):
        """I think i made this unneeded but check"""
        validates = True
        for model in self.root_app.models_dock.models_widget.elements.values():
            if model.cb.isChecked():
                if model.model_status_l.text() == 'Not ready':
                    validates = False

        if validates:
            self.validated_icon = QIcon(QPixmap('icons/dialog-ok-2.png'))
            self.validate_baseline_pb.setIcon(self.validated_icon)
            self.validate_baseline_pb.setText('Ready!')

    def update_args_with_difference(self, input_args):
        """
        Checks to see what about the (non-baseline) scenario is different from the baseline and then modifies the input_args
        (probably from the baseline args construction) to be a new args dict specific to the scenario run parameters.
        """
        output_args = input_args
        baseline_sources = self.root_app.scenarios_dock.scenarios_widget.elements['Baseline'].elements
        for name, element in self.elements.items():
            if element.name not in baseline_sources:
                output_args['lulc_uri'] = element.uri
                output_args['cur_lulc_raster'] = element.uri
                output_args['lulc_cur_uri'] = element.uri
        return output_args

    def unload_elements(self):
        for element in self.elements.values():
            element.remove_self()

    def add_map_signal_wrapper(self):
        for element in self.elements.values():
            if os.path.splitext(element.name)[1] == '.tif':
                self.root_app.statusbar.showMessage('Added ' + element.name + ' to map viewer.')
                args = self.root_app.map_widget.create_default_element_args(element.name)
                args['source_uri'] = element.uri
                self.root_app.map_widget.create_element(element.name, args)


class ModelsDock(MeshAbstractObject, QDockWidget):
    """
    Provides a docking space for the Models widget.
    """

    def __init__(self, root_app=None, parent=None):
        super(ModelsDock, self).__init__(root_app, parent)

        # Create dock window
        self.setMinimumSize(QSize(450, 250))
        self.setMaximumSize(QSize(2600, 10500))
        self.setWindowTitle('Models')
        self.models_widget = ModelsWidget(self.root_app, parent)
        self.setWidget(self.models_widget)


class ModelsWidget(ScrollWidget):
    """
    Widget to choose which models should run and set them up for the baseline.
    """
    default_element_args = OrderedDict()
    default_element_args['name'] = ''
    default_element_args['long_name'] = ''
    default_element_args['model_type'] = ''
    default_element_args['model_args'] = ''
    default_element_args['checked'] = ''

    default_state = OrderedDict()
    default_state['ndr'] = default_element_args.copy()
    default_state['ndr']['name'] = 'ndr'
    default_state['ndr']['long_name'] = 'Nutrient Retention'
    default_state['ndr']['model_type'] = 'InVEST Model'

    default_state['hydropower_water_yield'] = default_element_args.copy()
    default_state['hydropower_water_yield']['name'] = 'hydropower_water_yield'
    default_state['hydropower_water_yield']['long_name'] = 'Hydropower Water Yield'
    default_state['hydropower_water_yield']['model_type'] = 'InVEST Model'

    default_state['carbon'] = default_element_args.copy()
    default_state['carbon']['name'] = 'carbon'
    default_state['carbon']['long_name'] = 'Carbon Storage'
    default_state['carbon']['model_type'] = 'InVEST Model'

    default_state['pollination'] = default_element_args.copy()
    default_state['pollination']['name'] = 'pollination'
    default_state['pollination']['long_name'] = 'Pollination'
    default_state['pollination']['model_type'] = 'InVEST Model'

    default_state['sdr'] = default_element_args.copy()
    default_state['sdr']['name'] = 'sdr'
    default_state['sdr']['long_name'] = 'Sediment Delivery'
    default_state['sdr']['model_type'] = 'InVEST Model'

    def __init__(self, root_app=None, parent=None):
        super(ModelsWidget, self).__init__(root_app, parent)
        self.default_state = ScenariosWidget.default_state.copy()
        self.elements = OrderedDict()
        self.running_setup_uis = []
        self.create_ui()

    def create_ui(self):
        self.scroll_layout.setAlignment(Qt.AlignTop)

        self.project_frame = QFrame()
        self.project_frame.setObjectName('project_frame')
        self.project_frame.setStyleSheet("#project_frame { border: 1px solid grey; }")
        self.scroll_layout.addWidget(self.project_frame)
        self.project_vbox = QVBoxLayout()
        self.project_frame.setLayout(self.project_vbox)

        self.title_l = QLabel()
        self.title_l.setText('Project Details')
        self.title_l.setFont(config.heading_font)
        self.project_vbox.addWidget(self.title_l)
        self.project_name_hbox = QHBoxLayout()
        self.project_vbox.addLayout(self.project_name_hbox)
        self.current_project_header_l = QLabel('Project name: ')
        self.current_project_header_l.setFont(config.italic_font)
        self.project_name_hbox.addWidget(self.current_project_header_l)
        self.project_name_hbox.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        self.current_project_l = QLabel(self.root_app.project_name)
        self.current_project_l.setFont(config.minor_heading_font)
        self.project_name_hbox.addWidget(self.current_project_l)

        self.project_aoi_hbox = QHBoxLayout()
        self.project_vbox.addLayout(self.project_aoi_hbox)
        self.area_of_interest_header_l = QLabel('Area of interest: ')
        self.area_of_interest_header_l.setFont(config.italic_font)
        self.project_aoi_hbox.addWidget(self.area_of_interest_header_l)
        self.project_aoi_hbox.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        self.area_of_interest_l = QLabel('--need to set area of interest--')
        # self.area_of_interest_l.setFont(config.bold_font)
        self.project_aoi_hbox.addWidget(self.area_of_interest_l)
        self.choose_set_aoi_method_pb = QPushButton()
        self.choose_set_aoi_method_icon = QIcon()
        self.choose_set_aoi_method_icon.addPixmap(QPixmap('icons/db_add.png'), QIcon.Normal, QIcon.Off)
        self.choose_set_aoi_method_pb.setIcon(self.choose_set_aoi_method_icon)
        self.project_aoi_hbox.addWidget(self.choose_set_aoi_method_pb)
        self.choose_set_aoi_method_pb.clicked.connect(self.root_app.choose_set_aoi_method)

        self.creation_hbox = QHBoxLayout()
        self.project_vbox.addLayout(self.creation_hbox)

        self.define_decision_context_pb = QPushButton('Define decision context')
        self.define_decision_context_icon = QIcon()
        self.define_decision_context_icon.addPixmap(QPixmap('icons/filter.png'), QIcon.Normal, QIcon.Off)
        self.define_decision_context_pb.setIcon(self.define_decision_context_icon)
        self.define_decision_context_pb.clicked.connect(self.root_app.create_define_decision_context_dialog)
        self.creation_hbox.addWidget(self.define_decision_context_pb)

        self.create_data_pb = QPushButton('Generate your data')
        self.create_data_icon = QIcon()
        self.create_data_icon.addPixmap(QPixmap('icons/db_add.png'), QIcon.Normal, QIcon.Off)
        self.create_data_pb.setIcon(self.create_data_icon)
        self.creation_hbox.addWidget(self.create_data_pb)

        self.create_data_pb.clicked.connect(self.create_data)

        self.scroll_layout.addWidget(QLabel())
        self.title_l = QLabel()
        self.title_l.setText('Setup Baseline model runs')
        self.title_l.setFont(config.heading_font)
        self.scroll_layout.addWidget(self.title_l)
        self.setup_explanation_l = QLabel('Click Setup for each selected model to specify which data to use in the Baseline scenario.')
        self.setup_explanation_l.setWordWrap(True)
        self.setup_explanation_l.setFont(config.italic_font)
        self.scroll_layout.addWidget(self.setup_explanation_l)
        self.elements_vbox = QVBoxLayout()
        self.scroll_layout.addLayout(self.elements_vbox)

        self.scroll_layout.addWidget(QLabel())

        self.create_data_hbox = QHBoxLayout()
        self.scroll_layout.addLayout(self.create_data_hbox)
        self.create_data_l = QLabel('Create data for selected models:*')
        self.create_data_hbox.addWidget(self.create_data_l)

        self.asterisk_nyi_l = QLabel('Here and elsewhere, * denotes a feature that is partially implemented. Along with '
                                     'greyed-out buttons, these features will be fully implemented in the forthcoming MESH 1.0 release.')
        self.asterisk_nyi_l.setWordWrap(True)
        self.asterisk_nyi_l.setFont(config.italic_font)
        self.scroll_layout.addWidget(self.asterisk_nyi_l)



        self.scroll_layout.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))
        self.additional_models_l = QLabel('\nAdditional models can be added as plugins.')
        self.additional_models_l.setFont(config.italic_font)
        self.additional_models_l.setFont(config.italic_font)
        self.scroll_layout.addWidget(self.additional_models_l)
        self.add_plugins_pb = QPushButton('Install Plugins')
        self.add_plugins_pb.clicked.connect(self.root_app.create_load_plugin_dialog)
        self.scroll_layout.addWidget(self.add_plugins_pb)
        self.scroll_layout.addWidget(QLabel())

    def load_from_disk(self):
        self.unload_elements()
        self.save_uri = self.root_app.project_args['models_settings_uri']
        loaded_object = utilities.file_to_python_object(self.save_uri)

        if isinstance(loaded_object, list):
            self.elements = OrderedDict()
        else:
            for name, args in loaded_object.items():
                default_args = self.create_default_element_args(name)
                for default_key, default_value in default_args.items():
                    if default_key not in args or not args[default_key]:
                        args[default_key] = default_value
                self.load_element(name, args)

    def load_element(self, name, args):
        if name in self.elements:
            LOGGER.warn('Attempted to add element that already exists.')
        else:
            element = Model(name, args, self.root_app, self)
            self.elements[name] = element
            self.elements_vbox.addWidget(element)

    def create_element(self, name, args=None):
        """NYI"""

    def create_default_element_args(self, name):
        """NYI"""
        return OrderedDict()

    def unload_elements(self):
        for element in self.elements.values():
            element.remove_self()

    def save_to_disk(self):
        if len(self.elements) == 0:
            to_write = ','.join([name for name in self.default_state[''].keys()])
        else:
            to_write = OrderedDict()
            for name, element in self.elements.items():
                to_write.update({name: element.get_element_state_as_args()})
        utilities.python_object_to_csv(to_write, self.save_uri)

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
        if isinstance(self.sender, Scenario):
            # If a call from Scenario the sender.name is going to be the name
            # of the user labeled scenario and not the InVEST model name
            model_name = 'scenario_generator'
        else:
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
            self.root_app.project_folder, 'output', 'model_setup_runs',
            model_name, '%s_setup_file.json' % model_name)
        # Path to the MESH default json parameters.
        default_last_run_uri = os.path.join(
            self.root_app.default_setup_files_folder,
            '%s_setup_file.json' % model_name)
        # Check to see if an existing json file exists from a previous
        # setup run
        if os.path.exists(existing_last_run_uri):
            new_json_path = existing_last_run_uri
        else:
            # Read in MESH setup json to a dictionary
            default_args = utilities.file_to_python_object(
                default_last_run_uri)
            # Get the location of the InVEST model json file, which is
            # distributed with InVEST in IUI package
            invest_model_json_path = os.path.join(
                os.path.split(natcap.invest.iui.__file__)[0], json_file_name)
            # Path to copy InVEST json file to
            invest_json_copy = os.path.join(
                self.root_app.project_folder, json_file_name)
            shutil.copy(invest_model_json_path, invest_json_copy)
            # Read in copied InVEST Json to dictionary
            invest_json_dict = utilities.file_to_python_object(
                invest_json_copy)
            # Update the dictionary based on MESH setup json and input mapping
            # files
            new_json_args = self.modify_invest_args(
                invest_json_dict, default_args, model_name, input_mapping)
            # Write updated dictionary to new json file.
            new_json_path = os.path.join(
                self.root_app.project_folder, model_name + '_setup_file.json')
            with open(new_json_path, 'w') as fp:
                json.dump(new_json_args, fp)
            # Don't need to keep arounnd copied InVEST Json file, delete.
            os.remove(invest_json_copy)

        self.running_setup_uis.append(modelui.main(new_json_path))

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
                    if isinstance(self.sender, Scenario):
                        args_copy["defaultValue"] = os.path.join(
                            self.root_app.project_folder, 'input', 'Baseline',
                            input_mapping[key]['save_location'])
                    else:
                        args_copy["defaultValue"] = os.path.join(
                            self.root_app.project_folder,
                            input_mapping[key]['save_location'])
                # I THINK this should only  be needed for setting the workspace.
                elif vals[args_copy["args_id"]] == 'set_based_on_model_setup_runs_folder':
                    args_copy["defaultValue"] = os.path.join(
                        self.root_app.project_folder, 'output',
                        'model_setup_runs', model_name)
                elif vals[args_copy["args_id"]] == 'set_based_on_scenario':
                        args_copy["defaultValue"] = os.path.join(
                            self.root_app.project_folder, 'input',
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

    def setup_mesh_model(self, model_name):
        if os.path.exists(os.path.join(self.root_app.project_folder, 'output/model_setup_runs', model_name,
                                       model_name + '_setup_file.json')):
            last_run_uri = os.path.join(self.root_app.project_folder, 'output/model_setup_runs/', model_name,
                                        model_name + '_setup_file.json')
        else:
            last_run_uri = os.path.join(self.root_app.default_setup_files_folder, model_name + '_setup_file.json')

        if os.path.exists(last_run_uri):
            override_args = utilities.file_to_python_object(last_run_uri)
        else:
            override_args = None

        if model_name == 'nutrition':
            self.running_setup_uis.append(
                nutrition_ui.NutritionModelDialog(self.root_app, self, last_run_override=override_args))

    def setup_waterworld_model(self, model_name):
        """
        run ww model
        """

    def create_data(self):
        if self.root_app.is_base_data_valid():
            self.create_baseline_data_dialog = CreateBaselineDataDialog(self.root_app, self)
        else:
            self.create_baseline_data_dialog = ConfigureBaseDataDialog(self.root_app, self)

    def get_checked_elements(self):
        checked_elements = []
        for element in self.elements.values():
            if element.cb.isChecked():
                checked_elements.append(element)
        return checked_elements

    def get_elements_validated_and_checked(self):
        """
        returns 2 numbers, the number of models that hvae been validated and the number that have been checked. this is useful
        for updating the baseline scenario label.
        """
        num_validated = 0
        checked_elements = self.get_checked_elements()
        num_checked = len(checked_elements)

        for element in checked_elements:
            if element.check_if_validated():
                num_validated += 1

        return num_validated, num_checked


class Model(MeshAbstractObject, QWidget):
    """
    Contains the name and link to installed model, along with the input-output dictionary that is used to incorporate
    models outside MESH's model framework (such asexisting InVEST ui based models
    """

    def __init__(self, name, args, root_app=None, parent=None):
        super(Model, self).__init__(root_app, parent)
        self.name = name
        self.args = args
        self.initialize_from_args()

        self.create_ui()
        self.set_state_from_args()

    # --- Required element I/O  functions
    def create_ui(self):
        self.main_layout = QHBoxLayout()
        self.main_layout.setSpacing(5)
        self.main_layout.setMargin(0)
        self.setLayout(self.main_layout)
        self.cb = QCheckBox(self.long_name)
        self.cb.toggled.connect(self.toggle_model)
        # Left in as example of how to add action on a toggle. self.cb.toggled.connect(self.parent.toggle? not sure if i need any action on toggle.)
        self.main_layout.addWidget(self.cb)
        self.main_layout.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        self.model_status_image_l = QLabel()
        self.model_status_image_l.setVisible(False)
        self.main_layout.addWidget(self.model_status_image_l)
        self.model_status_l = QLabel()
        self.model_status_l.setVisible(False)
        self.main_layout.addWidget(self.model_status_l)
        self.check_if_ready_pb = QPushButton('Check if ready')
        self.unvalidated_icon = QIcon(QPixmap('icons/dialog-cancel-2.png'))
        self.check_if_ready_pb.setIcon(self.unvalidated_icon)
        self.check_if_ready_pb.clicked.connect(self.check_if_ready)
        self.check_if_ready_pb.setVisible(False)
        self.main_layout.addWidget(self.check_if_ready_pb)
        self.setup_model_pb = QPushButton('Setup')
        self.setup_model_icon = QIcon()
        self.setup_model_icon.addPixmap(QPixmap('icons/system-run-3.png'), QIcon.Normal, QIcon.Off)
        self.setup_model_pb.setIcon(self.setup_model_icon)
        self.main_layout.addWidget(self.setup_model_pb)
        if self.model_type == 'InVEST Model':
            self.setup_model_pb.clicked.connect(self.setup_invest_model_signal_wrapper)
        elif self.model_type == 'MESH Model':
            self.setup_model_pb.clicked.connect(self.setup_mesh_model_signal_wrapper)
        elif self.model_type == 'Waterworld Model':
            self.setup_model_pb.clicked.connect(self.setup_waterworld_model_signal_wrapper)

    def initialize_from_args(self):
        self.name = self.args['name']
        self.long_name = self.args['long_name']
        self.model_type = self.args['model_type']
        self.model_args = self.args['model_args']

    def set_state_from_args(self):
        if utilities.convert_to_bool(self.args['checked']):
            self.cb.setChecked(True)
        else:
            self.cb.setChecked(False)

    def get_element_state_as_args(self):
        to_return = OrderedDict()
        to_return['name'] = self.name
        to_return['long_name'] = self.long_name
        to_return['model_type'] = self.model_type
        to_return['model_args'] = self.model_args
        if self.cb.isChecked():
            to_return['checked'] = 'True'
        else:
            to_return['checked'] = 'False'
        return to_return

    def remove_self(self):
        del self.parent.elements[self.name]
        self.setParent(None)

    # def edit(self):
    #     self.editor_dialog = MapEditDialog(self.root_app, self)

    def toggle_model(self, state):
        """
        When checked, checks if the model "validates" and displays the approproate icon.
        """
        if state:
            self.draw_model_state()
        else:
            self.clear_model_state()
        scenarios_ready = False

        try:
            self.root_app.scenarios_dock
            scenarios_ready = True
        except:
            print("Exception hit on: self.root_app.scenarios_dock")
            raise

        if scenarios_ready:
            num_validated, num_checked = self.parent.get_elements_validated_and_checked()
            if num_checked == 0:
                to_update = '--Select models to run in the Models window--'
            elif num_validated == num_checked:
                to_update = 'Ready!'
            else:
                to_update = str(num_validated) + ' of ' + str(num_checked) + ' checked models are set up for Baseline'

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
            self.root_app.project_folder, 'output', 'model_setup_runs',
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
            if success_string in open(newest_log_path).read():
                invest_run_valid = True

        return invest_run_valid and archive_params_valid

    def place_check_if_ready_button(self):
        self.clear_model_state()
        self.check_if_ready_pb.setVisible(True)

    def check_if_ready(self):
        self.check_if_ready_pb.setVisible(False)
        self.draw_model_state()

    def draw_model_state(self):
        is_validated = self.check_if_validated()
        self.model_status_l.setVisible(True)
        self.model_status_image_l.setVisible(True)
        if is_validated:
            self.model_status_pixmap = QPixmap('icons/dialog-ok-2.png')
            self.model_status_scaled_pixmap = self.model_status_pixmap.scaled(QSize(16, 16))
            self.model_status_image_l.setPixmap(self.model_status_scaled_pixmap)
            self.model_status_l.setText('Ready')
        else:
            self.model_status_pixmap = QPixmap('icons/dialog-cancel-2.png')
            self.model_status_scaled_pixmap = self.model_status_pixmap.scaled(QSize(16, 16))
            self.model_status_image_l.setPixmap(self.model_status_scaled_pixmap)
            self.model_status_l.setText('Not ready')

    def clear_model_state(self):
        self.model_status_l.setVisible(False)
        self.model_status_image_l.setVisible(False)

    def setup_invest_model_signal_wrapper(self):
        self.place_check_if_ready_button()
        self.parent.setup_invest_model(self)  # NOTE This is a second self.

    def setup_mesh_model_signal_wrapper(self):
        self.place_check_if_ready_button()
        self.parent.setup_mesh_model(self.name)

    def setup_waterworld_model_signal_wrapper(self):
        self.place_check_if_ready_button()
        self.parent.setup_waterworld_model(self.name)


class ModelRunsWidget(MeshAbstractObject, QWidget):
    """
    Widget that can be displayed as the centraWidget of MeshApplication. Contains manyt Runs. Presents information on
    results of the whole MESH model.
    """
    default_element_args = OrderedDict()
    default_element_args['name'] = ''
    default_element_args['run_id'] = ''
    default_element_args['run_folder'] = ''
    default_element_args['scenarios_in_run'] = ''
    default_element_args['models_in_run'] = ''

    default_state = OrderedDict()
    default_state[''] = default_element_args.copy()

    def __init__(self, root_app=None, parent=None):
        super(ModelRunsWidget, self).__init__(root_app, parent)
        # Define the column headings that will go into the self.elements odict. Necessary to use as a default or writng a blank file.
        self.default_state = ModelRunsWidget.default_state.copy()

        self.elements = OrderedDict()
        self.create_ui()

        self.update_runs_table()

    def create_ui(self):
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.title_l = QLabel()
        self.title_l.setText('Run MESH model')
        self.title_l.setFont(config.heading_font)
        self.main_layout.addWidget(self.title_l)

        self.title_l = QLabel()
        self.title_l.setText('Add scenarios, select models, and click \'Run\' to see results.')
        self.title_l.setFont(config.italic_font)
        self.main_layout.addWidget(self.title_l)

        self.run_button_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.run_button_hbox)

        self.run_name_l = QLabel('Run name:')
        self.run_button_hbox.addWidget(self.run_name_l)
        self.run_name_le = QLineEdit('')
        self.run_button_hbox.addWidget(self.run_name_le)

        self.run_mesh_model_pb = QPushButton('Run')
        self.run_mesh_model_icon = QIcon()
        self.run_mesh_model_icon.addPixmap(QPixmap('icons/system-run-3.png'), QIcon.Normal, QIcon.Off)
        self.run_mesh_model_pb.setIcon(self.run_mesh_model_icon)
        self.run_mesh_model_pb.setMaximumWidth(180)
        self.run_button_hbox.addWidget(self.run_mesh_model_pb)
        self.run_mesh_model_pb.clicked.connect(self.run_mesh_model)

        # BUG possible. it creates a folder WITH a timestamp even if it names it one without if there is a folder that already exists of that name (even if not in project)
        self.add_existing_run_pb = QPushButton('Add existing run')
        self.add_existing_run_icon = QIcon()
        self.add_existing_run_icon.addPixmap(QPixmap('icons/document-open.png'), QIcon.Normal, QIcon.Off)
        self.add_existing_run_pb.setIcon(self.add_existing_run_icon)
        self.add_existing_run_pb.setMaximumWidth(200)
        self.run_button_hbox.addWidget(self.add_existing_run_pb)
        self.add_existing_run_pb.clicked.connect(self.create_element_from_folder_select_dialog)

        self.runs_table_header = QLabel('Existing Runs')
        self.runs_table_header.setFont(config.minor_heading_font)
        self.main_layout.addWidget(self.runs_table_header)

        self.runs_table_hbox = QHBoxLayout()
        self.runs_table_hbox.setMargin(0)
        self.runs_table_hbox.setAlignment(Qt.AlignCenter)

        self.runs_table_vbox = QVBoxLayout()
        self.runs_table_hbox.addLayout(self.runs_table_vbox)

        self.runs_scrollbox = ScrollWidget(self, self)
        self.runs_scrollbox.setMinimumSize(550, 450)

        self.elements_vbox = QVBoxLayout()
        self.runs_scrollbox.scroll_layout.addLayout(self.elements_vbox)

        self.runs_scrollbox.scroll_layout.addItem(
            QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))
        self.runs_table_vbox.addWidget(self.runs_scrollbox)
        self.runs_table_vbox.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))
        self.main_layout.addLayout(self.runs_table_hbox)

        self.logo_hbox = QHBoxLayout()
        self.logo_hbox.setAlignment(Qt.AlignCenter)
        self.main_layout.addLayout(self.logo_hbox)
        self.faded_logo_pixmap = QPixmap('icons/mesh_green_faded.png')
        self.faded_logo_l = QLabel()
        self.faded_logo_l.setVisible(False)
        self.faded_logo_l.setPixmap(self.faded_logo_pixmap)
        self.logo_hbox.addWidget(self.faded_logo_l)

        self.main_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Fixed, QSizePolicy.MinimumExpanding))

    def load_from_disk(self):
        self.unload_elements()
        self.save_uri = self.root_app.project_args['model_runs_settings_uri']
        loaded_object = utilities.file_to_python_object(self.save_uri)

        if isinstance(loaded_object, list):
            self.elements = OrderedDict()
        else:
            for name, args in loaded_object.items():
                default_args = self.create_default_element_args(name)
                for default_key, default_value in default_args.items():
                    if default_key not in args or not args[default_key]:
                        args[default_key] = default_value
                self.load_element(name, args)
        self.update_runs_table()

    def load_element(self, name, args):
        if not name:
            LOGGER.warn('Asked to load an element with a blank name.')
        elif name in self.elements:
            LOGGER.warn('Attempted to add element that already exists.')
        else:
            element = ModelRun(name, args, self.root_app, self)
            self.elements[name] = element
            self.elements_vbox.addWidget(element)

    def create_element(self, name, args=None):
        if not args or not name:
            args = self.create_default_element_args(name)
        element = ModelRun(name, args, self.root_app, self)
        self.elements[name] = element
        self.elements_vbox.addWidget(element)

    def create_default_element_args(self, name):
        args = ModelRunsWidget.default_element_args.copy()
        args['name'] = name
        args['run_id'] = utilities.pretty_time()
        args['folder'] = os.path.join(self.root_app.project_folder, 'input/', name)
        return args

    def create_element_from_folder_select_dialog(self):
        selected_uri = str(QFileDialog.getExistingDirectory(self, 'Select existing run', self.root_app.project_folder))
        if selected_uri:
            name = os.path.splitext(os.path.split(selected_uri)[1])[0]
            name_just_folder = os.path.split(name)[1]
            self.create_element(name_just_folder)
            self.update_runs_table()

    def unload_elements(self):
        for element in self.elements.values():
            element.remove_self()

    def save_to_disk(self):
        if len(self.elements) == 0:
            to_write = ','.join([name for name in self.default_state[''].keys()])
        else:
            to_write = OrderedDict()
            for name, element in self.elements.items():
                to_write.update({name: element.get_element_state_as_args()})
        utilities.python_object_to_csv(to_write, self.save_uri)

    def run_mesh_model(self):
        self.run_mesh_model_dialog = RunMeshModelDialog(self.root_app, self)

    def process_finish_message(self, message):
        finished_model = message
        self.root_app.statusbar.showMessage('Finished model run of ' + finished_model + '!')
        self.update_runs_table()

    def update_runs_table(self):
        if len(self.elements) == 0:
            self.faded_logo_l.setVisible(True)
            self.runs_scrollbox.setVisible(False)
        else:
            self.faded_logo_l.setVisible(False)
            self.runs_scrollbox.setVisible(True)


class ModelRun(MeshAbstractObject, QWidget):
    """
    Contains the name and link to outputted results. Is displayed by the Runs_widget in the central column.
    """
    # class that dealt with I/O from args, and setting attributs
    def __init__(self, name, args, root_app=None, parent=None, load_existing=False):
        super(ModelRun, self).__init__(root_app, parent)
        self.name = name
        self.args = args

        self.initialize_from_args()

        self.create_ui()
        self.set_state_from_args()

    def create_ui(self):
        self.main_layout = QHBoxLayout()
        self.main_layout.setSpacing(5)
        self.main_layout.setMargin(0)

        self.setLayout(self.main_layout)
        self.cb = QCheckBox(self.name)

        self.main_layout.addWidget(self.cb)
        self.main_layout.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))

        self.image_size = QSize(16, 16)

        self.data_explorer_pb = QPushButton('Data Explorer')
        self.data_explorer_icon = QIcon()
        self.data_explorer_icon.addPixmap(QPixmap('icons/emblem-package.png'), QIcon.Normal, QIcon.Off)
        self.data_explorer_pb.setIcon(self.data_explorer_icon)
        self.main_layout.addWidget(self.data_explorer_pb)
        self.data_explorer_pb.setEnabled(False)
        self.data_explorer_pb.clicked.connect(self.data_explorer_signal_wrapper)

        self.add_run_to_map_viewer_pb = QPushButton('Map')
        self.add_run_to_map_viewer_icon = QIcon()
        self.add_run_to_map_viewer_icon.addPixmap(QPixmap('icons/arrow-right.png'), QIcon.Normal, QIcon.Off)
        self.add_run_to_map_viewer_pb.setIcon(self.add_run_to_map_viewer_icon)
        self.main_layout.addWidget(self.add_run_to_map_viewer_pb)
        self.add_run_to_map_viewer_pb.clicked.connect(self.add_run_to_map_viewer_signal_wrapper)

        self.use_run_to_create_report_pb = QPushButton('Report')
        self.use_run_to_create_report_icon = QIcon()
        self.use_run_to_create_report_icon.addPixmap(QPixmap('icons/document-new-6.png'), QIcon.Normal, QIcon.Off)
        self.use_run_to_create_report_pb.setIcon(self.use_run_to_create_report_icon)
        self.main_layout.addWidget(self.use_run_to_create_report_pb)

        # NEXT RELEASE Connect this to a more robust dialog for selecting the report and the generation of report ready objects.
        self.use_run_to_create_report_pb.clicked.connect(self.use_run_to_load_choose_report_dialog)

        self.delete_run_pb = QPushButton()
        self.delete_run_icon = QIcon()
        self.delete_run_icon.addPixmap(QPixmap('icons/dialog-cancel-5.png'), QIcon.Normal, QIcon.Off)
        self.delete_run_pb.setIcon(self.delete_run_icon)
        self.main_layout.addWidget(self.delete_run_pb)
        self.delete_run_pb.clicked.connect(self.remove_self)

    def initialize_from_args(self):
        self.name = self.args['name']
        self.long_name = self.name.title()
        self.run_id = self.args['run_id']
        self.run_folder = self.args['run_folder']

        if isinstance(self.args['scenarios_in_run'], str):
            self.scenarios_in_run_names = [self.args['scenarios_in_run']]  # NOTE the wrapping in a list
        else:
            self.scenarios_in_run_names = [name for name in self.args['scenarios_in_run']]

        self.scenarios_in_run = []
        for scenario_name in self.scenarios_in_run_names:
            try:
                self.scenarios_in_run.append(self.root_app.scenarios_dock.scenarios_widget.elements[scenario_name])
            except:
                warnings.warn(scenario_name + ' added to scenarios_widget.elements, but something broke.')

        if isinstance(self.args['models_in_run'], str):
            self.models_in_run_names = [self.args['models_in_run']]  # NOTE the wrapping in a list
        else:
            self.models_in_run_names = [name for name in self.args['models_in_run']]

        self.models_in_run = []
        for model_name in self.models_in_run_names:
            self.models_in_run.append(self.root_app.models_dock.models_widget.elements[model_name])

    def set_state_from_args(self):
        """NYI but is hook for report creation stuff"""

    def get_element_state_as_args(self):
        to_return = OrderedDict()
        to_return['name'] = self.name
        to_return['run_id'] = self.run_id
        to_return['run_folder'] = self.run_folder
        to_return['scenarios_in_run'] = [i.name for i in self.scenarios_in_run]
        to_return['models_in_run'] = [i.name for i in self.models_in_run]
        return to_return

    def remove_self(self):
        del self.parent.elements[self.name]
        self.setParent(None)

    # --- Element specific UI functions
    def add_run_to_map_viewer_signal_wrapper(self):
        for scenario in self.scenarios_in_run:
            for model in self.models_in_run:
                # TODO JUSTIN SHORTCUT I manually decided which reports are actually interesting outputs. Have this be programatic.
                # And link to the "generate_report_ready_object()" functionality here to fix this.
                uris_to_add = []
                current_folder = os.path.join(self.run_folder, scenario.name, model.name)
                if model.name == 'carbon':
                    uris_to_add.append(os.path.join(current_folder, 'output', 'tot_c_cur.tif'))
                if model.name == 'hydropower_water_yield':
                    uris_to_add.append(os.path.join(current_folder, 'output/per_pixel', 'aet.tif'))
                    uris_to_add.append(os.path.join(current_folder, 'output/per_pixel', 'fractp.tif'))
                    uris_to_add.append(os.path.join(current_folder, 'output/per_pixel', 'wyield.tif'))
                #if model.name == 'nutrient':
                #    uris_to_add.append(os.path.join(current_folder, 'output', 'n_export_.tif'))
                #    uris_to_add.append(os.path.join(current_folder, 'output', 'n_retention_.tif'))
                #    uris_to_add.append(os.path.join(current_folder, 'output', 'p_export_.tif'))
                #    uris_to_add.append(os.path.join(current_folder, 'output', 'p_retention_.tif'))
                if model.name == 'pollination':
                    uris_to_add.append(os.path.join(current_folder, 'output', 'frm_avg_cur.tif'))
                    uris_to_add.append(os.path.join(current_folder, 'output', 'sup_tot_cur.tif'))
                if model.name == 'sdr':
                    uris_to_add.append(os.path.join(current_folder, 'output', 'rkls.tif'))
                    uris_to_add.append(os.path.join(current_folder, 'output', 'sed_export.tif'))
                    uris_to_add.append(os.path.join(current_folder, 'output', 'sed_retention_index.tif'))
                    uris_to_add.append(os.path.join(current_folder, 'output', 'usle.tif'))
                if model.name == 'nutrition':
                    for i in os.listdir(os.path.join(current_folder)):
                        # NEXT RELEASE I currently save a shitton of files that are duplicate and take space. Perhaps create a data_stash folder to share across runs?
                        if i.endswith('.tif'):
                            uris_to_add.append(os.path.join(current_folder, i))

                for uri in uris_to_add:
                    name_of_map_to_add = self.name + ' ' + scenario.name + ' ' + model.name + ' ' + os.path.split(uri)[
                        1]
                    args = self.root_app.map_widget.create_default_element_args(name_of_map_to_add)
                    args['source_uri'] = uri
                    self.root_app.map_widget.create_element(name_of_map_to_add, args)

    # TODO JUSTIN. This beta release does not include the full report_generator tool and it's integration in the generate_report_ready_object()
    # Instead I just used some placeholder, hardcoded BS for time-sake.
    def use_run_to_load_choose_report_dialog(self):
        self.choose_report_type_dialog = ChooseReportTypeDialog(self.root_app, self)
        # NEXT RELEASE add in the report generator code from next release

    def data_explorer_signal_wrapper(self):
        self.data_explorer_dialog = DataExplorerDialog(self.root_app, self)

    def create_report_from_this_run(self, report_type):
        args = OrderedDict()
        args['name'] = self.name + '_report'
        args['run_name'] = self.name
        args['long_name'] = self.long_name + ' Report'
        args['markdown_uri'] = os.path.join('../settings/reports/', report_type + '.txt')
        args['report_type'] = report_type

        self.root_app.reports_widget.elements.update({self.name: Report(self.name, args, self.root_app, self)})

        self.root_app.reports_widget.update_ui()
        self.root_app.create_report_qaction.trigger()


class ReportsWidget(MeshAbstractObject, QWidget):
    """
    Central widget that shows the currently generated report and provides IO options.
    """
    default_element_args = OrderedDict()
    default_element_args['name'] = ''
    default_element_args['markdown_uri'] = ''
    default_element_args['report_type'] = ''

    default_state = OrderedDict()
    default_state[''] = default_element_args.copy()

    def __init__(self, root_app=None, parent=None):
        super(ReportsWidget, self).__init__(root_app, parent)
        self.default_state = ReportsWidget.default_state.copy()
        self.elements = OrderedDict()
        self.create_ui()
        self.update_ui()
        # self.set_state???

    def create_ui(self):
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignTop)
        self.setLayout(self.main_layout)
        self.title_l = QLabel()
        self.title_l.setText('Report Generator')
        self.title_l.setFont(config.heading_font)
        self.main_layout.addWidget(self.title_l)

        self.subtitle_l = QLabel()
        self.subtitle_l.setText('Generate custom reports based on your results.')
        self.subtitle_l.setFont(config.italic_font)
        self.main_layout.addWidget(self.subtitle_l)

        self.create_or_load_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.create_or_load_hbox)

        self.runs_available_header_l = QLabel('Selected run:')
        self.runs_available_header_l.setFont(config.bold_font)
        self.create_or_load_hbox.addWidget(self.runs_available_header_l)

        self.runs_available_combobox = QComboBox()
        self.create_or_load_hbox.addWidget(self.runs_available_combobox)

        self.create_report_pb = QPushButton('Create report')
        self.create_report_icon = QIcon()
        self.create_report_icon.addPixmap(QPixmap('icons/document-new-6.png'), QIcon.Normal, QIcon.Off)
        self.create_report_pb.setIcon(self.create_report_icon)
        # self.create_report_pb.setMaximumWidth(180)
        self.create_or_load_hbox.addWidget(self.create_report_pb)
        self.create_report_pb.clicked.connect(self.create_choose_report_type_dialog)

        # self.create_or_load_hbox.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))

        # BUG possible. it creates a folder WITH a timestamp even if it names it one without if there is a folder that already exists of that name (even if not in project)
        self.load_existing_report_pb = QPushButton('Load existing')
        self.load_existing_report_icon = QIcon()
        self.load_existing_report_icon.addPixmap(QPixmap('icons/document-open.png'), QIcon.Normal, QIcon.Off)
        self.load_existing_report_pb.setIcon(self.load_existing_report_icon)
        # self.load_existing_report_pb.setMaximumWidth(200)
        self.create_or_load_hbox.addWidget(self.load_existing_report_pb)
        self.load_existing_report_pb.clicked.connect(self.load_existing_report_from_file_dialog)

        # self.selected_run_hbox = QHBoxLayout()
        # self.main_layout.addLayout(self.selected_run_hbox)

        self.scroll_widget = ScrollWidget(self.root_app, self)
        self.scroll_widget.scroll_layout.setAlignment(Qt.AlignTop)
        # self.scroll_upper_vbox = QVBoxLayout()
        # self.scroll_widget.scroll_layout.addLayout(self.scroll_upper_vbox)
        self.elements_vbox = QVBoxLayout()
        self.scroll_widget.scroll_layout.addLayout(self.elements_vbox)

        self.no_reports_l = QLabel()
        self.no_reports_l.setText('No reports yet created.')
        self.no_reports_l.setFont(config.italic_font)
        self.no_reports_l.setVisible(False)
        self.scroll_widget.scroll_layout.addWidget(self.no_reports_l)

        self.main_layout.addWidget(self.scroll_widget)  # Eventually holds the main report, loaded via functions below

    def load_from_disk(self):
        self.unload_elements()
        self.save_uri = self.root_app.project_args['reports_settings_uri']
        loaded_object = utilities.file_to_python_object(self.save_uri)

        if isinstance(loaded_object, list):
            self.elements = OrderedDict()
        else:
            for name, args in loaded_object.items():
                default_args = self.create_default_element_args(name)
                for default_key, default_value in default_args.items():
                    if default_key not in args or not args[default_key]:
                        args[default_key] = default_value
                self.load_element(name, args)

    def load_element(self, name, args):
        if not name:
            LOGGER.warn('Asked to load an element with a blank name.')
        elif name in self.elements:
            LOGGER.warn('Attempted to add element that already exists.')
        elif name not in args:
            warnings.warn("Warning, run name not in loaded CSV.")
        else:
            model_run = self.root_app.model_runs_widget.elements[args['run_name']]
            element = Report(name, args, self.root_app, model_run)
            self.elements[name] = element
            self.elements_vbox.addWidget(element)

    def create_element(self, name, args=None):
        if not args:
            args = self.create_default_element_args(name)
        model_run = self.root_app.model_runs_widget.elements[args['run_name']]
        element = Report(name, args, self.root_app, model_run)
        self.elements[name] = element
        self.elements_vbox.addWidget(element)

    def create_default_element_args(self, name):
        args = ReportsWidget.default_element_args.copy()
        args['name'] = name
        args['run_name'] = str(self.runs_available_combobox.currentText())
        return args

    def unload_elements(self):
        for element in self.elements.values():
            element.remove_self()

    # TODO DOUG COMMENT 5 For consistency, rename/combine update_ui here with the set_state_to_args in other widgets?
    def update_ui(self):
        if not len(self.elements):
            self.no_reports_l.setVisible(True)
        else:
            self.no_reports_l.setVisible(False)
            for report in self.elements.values():
                self.elements_vbox.addWidget(report)

        self.runs_available = self.root_app.model_runs_widget.elements.keys()
        if len(self.runs_available):
            self.runs_available_combobox.clear()
            self.runs_available_combobox.addItems(self.runs_available)
            self.runs_available_combobox.setCurrentIndex(self.runs_available.index(self.runs_available[0]))
        else:
            self.runs_available_combobox.clear()
            self.runs_available_combobox.addItem('--no runs yet created--')

    def save_to_disk(self):
        if len(self.elements) == 0:
            to_write = ','.join([name for name in self.default_state[''].keys()])
        else:
            to_write = OrderedDict()
            for name, element in self.elements.items():
                to_write.update({name: element.get_element_state_as_args()})
        utilities.python_object_to_csv(to_write, self.save_uri)

    def save_report_as_text_document(self):
        for element in self.elements.values():
            55

    def create_choose_report_type_dialog(self):
        self.choose_report_type_dialog = ChooseReportTypeDialog(self.root_app, self)

    def load_existing_report_from_file_dialog(self):
        selected_uri = str(QFileDialog.getOpenFileName(self, 'Select existing report to load',
                                                       os.path.join(self.root_app.project_folder, 'output', 'reports')))
        args = None
        self.load_element(selected_uri, args)


class Report(MeshAbstractObject, QFrame):
    """
    Contains an assemblage of report-ready objects. The MESH Beta release does not fully implement reports, so this is
    partially implemented.
    """

    def __init__(self, name, args=None, root_app=None, parent=None):
        super(Report, self).__init__(root_app, parent)
        self.name = name
        self.args = args

        self.initialize_from_args()
        self.create_ui()
        self.update_ui()

    def initialize_from_args(self):
        self.run_name = self.args['run_name']
        self.long_name = self.args['long_name']
        self.markdown_uri = self.args['markdown_uri']
        self.report_type = self.args['report_type']

        self.markdown_lines = []
        with open(self.markdown_uri) as f:
            for line in f:
                self.markdown_lines.append(markdown(line))

        self.html = self.parse_markdown_to_html(self.markdown_lines)

    def create_ui(self):
        self.setObjectName('report_frame')
        self.setStyleSheet('#report_frame { background:rgb(255,255,255) }')

        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(2)
        self.main_layout.setMargin(5)
        self.setLayout(self.main_layout)

        self.top_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.top_hbox)
        self.main_layout.setContentsMargins(20, 15, 20, 15)

        # self.report_name_l = QLabel(self.long_name)
        # self.report_name_l.setFont(config.minor_heading_font)
        # self.top_hbox.addWidget(self.report_name_l)
        #
        # self.report_preview_l = QLabel('Preview:')
        # self.report_preview_l.setFont(config.italic_font)
        # self.main_layout.addWidget(self.report_preview_l)

        self.html_l = QLabel()
        self.html_l.setVisible(False)
        self.html_l.setWordWrap(True)
        self.main_layout.addWidget(self.html_l)

        self.preview_l = QLabel('\n...\n\nView or edit report to see the rest of the report.\n')
        self.preview_l.setFont(config.italic_font)
        self.main_layout.addWidget(self.preview_l)

        self.report_actions_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.report_actions_hbox)

        self.view_or_edit_report_pb = QPushButton('View or edit report')
        self.view_or_edit_report_icon = QIcon()
        self.view_or_edit_report_icon.addPixmap(QPixmap('icons/configure-2.png'), QIcon.Normal, QIcon.Off)
        self.view_or_edit_report_pb.setIcon(self.view_or_edit_report_icon)
        self.view_or_edit_report_pb.setMaximumWidth(260)
        self.report_actions_hbox.addWidget(self.view_or_edit_report_pb)
        self.view_or_edit_report_pb.clicked.connect(self.view_or_edit_report)


        self.save_report_as_html_pb = QPushButton('Save report')
        self.save_report_as_html_icon = QIcon()
        self.save_report_as_html_icon.addPixmap(QPixmap('icons/document-new-6.png'), QIcon.Normal, QIcon.Off)
        self.save_report_as_html_pb.setIcon(self.save_report_as_html_icon)
        self.save_report_as_html_pb.setMaximumWidth(260)
        self.report_actions_hbox.addWidget(self.save_report_as_html_pb)
        self.save_report_as_html_pb.clicked.connect(self.save_report_as_html)


        # self.save_report_as_text_document_pb = QPushButton('Save report as doc')
        # self.save_report_as_text_document_icon = QIcon()
        # self.save_report_as_text_document_icon.addPixmap(QPixmap('icons/document-new-6.png'), QIcon.Normal, QIcon.Off)
        # self.save_report_as_text_document_pb.setIcon(self.save_report_as_text_document_icon)
        # self.save_report_as_text_document_pb.setMaximumWidth(260)
        # self.report_actions_hbox.addWidget(self.save_report_as_text_document_pb)
        # self.save_report_as_text_document_pb.clicked.connect(self.save_report_as_text_document)
        #
        self.save_report_as_pdf_pb = QPushButton('Save report as PDF')
        self.save_report_as_pdf_icon = QIcon()
        self.save_report_as_pdf_icon.addPixmap(QPixmap('icons/document-new-3.png'), QIcon.Normal, QIcon.Off)
        self.save_report_as_pdf_pb.setIcon(self.save_report_as_pdf_icon)
        self.save_report_as_pdf_pb.setMaximumWidth(260)
        self.report_actions_hbox.addWidget(self.save_report_as_pdf_pb)
        self.save_report_as_pdf_pb.clicked.connect(self.save_report_as_pdf)

        self.clear_pb = QPushButton()
        self.clear_pb.clicked.connect(self.remove_self)
        self.report_actions_hbox.addWidget(self.clear_pb)
        self.clear_icon = QIcon(QPixmap('icons/dialog-cancel-5.png'))
        self.clear_pb.setFixedWidth(32)
        self.clear_pb.setIcon(self.clear_icon)

    def update_ui(self):
        if len(self.html):
            number_of_preview_lines = 3
            self.html_l.setText('\n'.join(self.html[0:number_of_preview_lines]))
            self.html_l.setVisible(True)

            # self.report_title_l = QLabel('Report Title')
            # self.report_title_l.setFont(config.bold_font)
            # self.main_layout.addWidget(self.report_title_l)

    def parse_markdown_to_html(self, markdown_lines):
        html = []
        for line in markdown_lines:
            content, tags = self.split_tags_and_content_from_line(line)
            if not len(tags):
                html.append(content)
            else:
                modified_line = ''
                for i in range(len(content)):
                    modified_line += content[i]
                    if len(tags) > i:
                        dynamic_content = self.parse_tag(tags[i])
                        if not dynamic_content:
                            dynamic_content = ' '
                        modified_line += dynamic_content
                html.append(modified_line)
        return html

    def split_tags_and_content_from_line(self, line):
        """
        Report files use markdown, but extended with tag-delimiters '<^' and '^> which swithc between content and code.
        This function splits a markdown line to return two lists with content and tags, in that order. This allows for conditional
        adding of elements via a tag, such as 'add_results_table'
        """
        tags = []
        content = []
        num_tags = line.count('&lt;^')
        if not num_tags:
            content = line
            return content, tags
        else:
            fragments = []
            left_split_line = line.split('&lt;^')
            for fragment in left_split_line:
                split_fragment = fragment.split('^&gt;')
                fragments.extend(split_fragment)
            tags = fragments[1::2]  # get every other.
            content = fragments[::2]

            return content, tags

    def parse_tag(self, tag):
        dynamic_content = ''
        if tag == 'report_type':
            dynamic_content = self.report_type.title().replace('_', ' ')
        elif tag == 'run_name':
            dynamic_content = self.run_name
        elif tag == 'project_name':
            dynamic_content = self.root_app.project_name
        elif tag == 'models_string':
            dynamic_content = self.build_models_string()
        elif tag == 'model_results_table':
             dynamic_content = self.build_results_table()
        # elif tag == 'model_primary_indicator_map':
        #     dynamic_content = 'model_primary_indicator_map'
        # elif tag == 'scenario_results_comparison_table':
        #     dynamic_content = 'REPLACE THIS WITH THE TABLE'
        # elif tag == 'scenario_difference_map':
        #     dynamic_content = 'REPLACE THIS WITH THE TABLE'
        return dynamic_content

    def build_models_list(self):
        models_list = []
        for model in self.parent.models_in_run:
            models_list.append(model)
        return models_list

    def build_models_string(self):
        models_list = self.build_models_list()
        num_models = len(models_list)
        for i in range(num_models):
            if i == 0:
                models_string = models_list[i].long_name
            elif i < num_models - 1:
                models_string += ', ' + models_list[i].long_name
            else:
                models_string += ' and ' + models_list[i].long_name
        return models_string

    def build_scenarios_list(self):
        scenarios_list = []
        for scenario in self.parent.scenarios_in_run:
            scenarios_list.append(scenario)
        return scenarios_list

    def build_scenarios_string(self):
        scenarios_list = self.build_scenarios_list()
        num_scenarios = len(scenarios_list)
        for i in range(num_scenarios):
            if i == 0:
                scenarios_string = scenarios_list[i].long_name
            elif i < num_scenarios - 1:
                scenarios_string += ', ' + scenarios_list[i].long_name
            else:
                scenarios_string += ' and ' + scenarios_list[i].long_name
        return scenarios_string

    def build_results_table(self):
        st = ''
        models_list = self.build_models_list()
        scenarios_list = self.build_scenarios_list()
        num_rows = len(scenarios_list) + 1
        num_cols = len(models_list)
        row = 0
        col = 0

        for scenario in scenarios_list:
            st += '<h2>Scenario: ' + scenario.long_name + '</h2>'
            scenario_folder = os.path.join(self.root_app.project_folder, 'output/runs/', self.run_name, scenario.name)
            for model in models_list:
                st += '<h3>Model: ' + model.long_name + '</h3>'
                model_output_folder = os.path.join(scenario_folder, model.name, 'output')
                if model.name == 'carbon':
                    output_uri = os.path.join(model_output_folder, 'tot_C_cur.tif')
                    if os.path.exists(output_uri):
                        value = str(utilities.get_raster_sum(output_uri))
                        st += '<p>Tons of carbon storage: ' + value + '</p>'
                        for filename in os.listdir(model_output_folder):
                            if os.path.splitext(filename)[1] == '.png':

                                st += '<p><img src=\"' + os.path.join(model_output_folder, filename) + '\" width=\"600\"></p>'

                if model.name == 'hydropower_water_yield':
                    output_uri = os.path.join(model_output_folder, 'per_pixel/wyield.tif')
                    if os.path.exists(output_uri):
                        value = str(utilities.get_raster_sum(output_uri))
                        st += '<p>Total water yield: ' + value
                        for filename in os.listdir(model_output_folder):
                            if os.path.splitext(filename)[1] == '.png':
                                st += '<p><img src=\"' + os.path.join(model_output_folder, filename) + '\" width=\"600\"></p>'


        return st


        # for row in range(num_rows):
        #     if row == 0:
        #         table += '<tr><td></td>'  # Blank UL cell
        #     else:
        #         table += '<tr>'
        #     for col in range(num_cols):
        #         if row == 0:
        #             table += '<td>' + models_list[col - 1].long_name + '</td>'
        #         else:
        #             if col == 0:
        #                 table += '<td>' + scenarios_list[row - 1].long_name + '</td>'
        #             else:
        #                 value_to_record = self.get_value_from_scenario_model_pair(scenarios_list[row - 1], models_list[row - 1])
        #                 table += '<td>' + value_to_record + '</td>'
        #     table += '</tr>'
        # table += '</table>'
        # return table

    def build_results_table_REAL(self):
        table = '<table>'
        models_list = self.build_models_list()
        scenarios_list = self.build_scenarios_list()
        num_rows = len(scenarios_list) + 1
        num_cols = len(models_list)
        row = 0
        col = 0
        for row in range(num_rows):
            if row == 0:
                table += '<tr><td></td>'  # Blank UL cell
            else:
                table += '<tr>'
            for col in range(num_cols):
                if row == 0:
                    table += '<td>' + models_list[col - 1].long_name + '</td>'
                else:
                    if col == 0:
                        table += '<td>' + scenarios_list[row - 1].long_name + '</td>'
                    else:
                        value_to_record = self.get_value_from_scenario_model_pair(scenarios_list[row - 1], models_list[row - 1])
                        table += '<td>' + value_to_record + '</td>'
            table += '</tr>'
        table += '</table>'
        return table

    def get_value_from_scenario_model_pair(self, scenario, model, value_to_get=None):
        if model.name == 'carbon':
            return 'carbon_value'
        elif model.name == 'hydropower_water_yield':
            return 'hydropower'
        else:
            return 'output value here'

    def set_state_from_args(self):
        55

    def get_element_state_as_args(self):
        args = OrderedDict()
        args['name'] = self.name
        args['run_name'] = self.run_name
        args['long_name'] = self.long_name
        args['markdown_uri'] = self.markdown_uri
        args['report_type'] = self.report_type
        return args

    def add_report_list(self, uri):
        # TODO JUSTIN SHORTCUT make this per project.
        reports_folder = os.path.join(self.root_app.project_folder, '../volta_demo/output/reports')

        # TODO JUSTIN SHORTCUT Here is probably the silliest shortcut I took but I implemented it on the plane to Rome the day before I presented it.
        # Ultimatly this should draw from XML or JSON files that define a report type and the images should be based on the
        # define_report_ready_object() from upcoming release.
        qt_objects = utilities.read_txt_file_as_serialized_headers(uri)
        for qt_object in qt_objects:
            if not isinstance(qt_object, str):
                self.main_layout.addWidget(qt_object)
            else:
                qt_object = qt_object.replace('\n', '').replace('\\n', '')
                self.add_image_to_report_by_uri(os.path.join(reports_folder, qt_object + '.png'), 650)

    def add_image_to_report_by_uri(self, uri, width=None):
        centered_hbox = QHBoxLayout()
        self.main_layout.addLayout(centered_hbox)
        image_l = QLabel()
        image_pixmap = QPixmap(uri)
        scaled_pixmap = image_pixmap
        if width:
            scaled_pixmap = image_pixmap.scaledToWidth(width)
        image_l.setPixmap(scaled_pixmap)
        centered_hbox.addWidget(image_l)

    def remove_self(self):
        del self.root_app.reports_widget.elements[self.name]
        self.setParent(None)

    def view_or_edit_report(self):
        self.editor = QTextEdit()
        self.editor.setMinimumSize(QSize(500, 600))
        self.editor.setHtml('\n'.join(self.html))
        self.editor.show()

    def save_report_as_html(self):
        to_write = str(self.html)
        dst = os.path.join(self.root_app.project_folder, 'output/reports', 'report_at_' + utilities.pretty_time() + '.html')
        open(dst, 'w').write(to_write)

    def save_report_as_pdf(self):
        """Save the generated html report from 'self.html' as a PDF file.

        Returns:
            Nothing
        """
        # Default path for where the user "should" save the report
        # Copied from how HTML reports paths are hardcoded
        pdf_default_path = os.path.join(
            self.root_app.project_folder, 'output/reports',
            'report_at_' + utilities.pretty_time() + '.pdf')
        # Open a file dialogue and let the user select where to save
        # pdf file
        pdf_out_path = QFileDialog.getSaveFileName(
            self, 'Save File', pdf_default_path, "*.pdf")

        html = str(self.html)

        doc = QTextDocument()
        doc.setHtml(html)

        printer = QPrinter()
        printer.setOutputFileName(pdf_out_path)
        printer.setOutputFormat(QPrinter.PdfFormat)
        # Set page size to standard A4
        printer.setPageSize(QPrinter.A4)
        # Set page margins to be reasonable
        printer.setPageMargins(15, 15, 15, 15, QPrinter.Millimeter)

        doc.print_(printer)

class MapWidget(MeshAbstractObject, QDockWidget):
    """
    Dock that holds the map viewer CONTROLS (not the actual map canvas)
    """
    default_element_args = OrderedDict()
    default_element_args['name'] = ''
    default_element_args['source_uri'] = ''
    default_element_args['source_name'] = ''
    default_element_args['parent_scenario_name'] = ''
    default_element_args['title'] = ''
    default_element_args['cbar_label'] = ''
    default_element_args['checked'] = ''
    default_element_args['vmin'] = ''
    default_element_args['vmax'] = ''
    default_element_args['ignore_values_list'] = ''
    default_element_args['color_scheme'] = ''

    default_state = OrderedDict()
    default_state[''] = default_element_args.copy()

    def __init__(self, root_app=None, parent=None):
        super(MapWidget, self).__init__(root_app, parent)
        self.default_state = MapWidget.default_state.copy()
        self.elements = OrderedDict()
        self.create_ui()
        self.name_of_toggled = None

    def create_ui(self):
        # Create dock window
        self.setMinimumSize(QSize(100, 50))
        self.setMaximumSize(QSize(1200, 10500))
        self.setSizePolicy(config.size_policy)
        dock_name = "Map Viewer"
        # self.setToolTip(dock_name)
        self.setWindowTitle(dock_name)

        # Structure of window starts here Main window comprises a static top region and a scroll window below it
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout()
        self.main_layout.setMargin(0)

        # Top area
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.main_layout.addWidget(self.top_widget)

        self.top_l = QLabel('Display Maps from Scenarios')
        self.top_l.setFont(config.heading_font)
        self.tools_layout = QHBoxLayout()
        self.top_layout.addWidget(self.top_l)
        self.top_layout.addLayout(self.tools_layout)

        self.add_maps_hbox = QHBoxLayout()
        self.top_layout.addLayout(self.add_maps_hbox)

        self.create_element_from_file_select_dialog_pb = QPushButton('Add external file')
        self.create_element_from_file_select_dialog_pb.clicked.connect(self.create_element_from_file_select_dialog)
        self.add_maps_hbox.addWidget(self.create_element_from_file_select_dialog_pb)
        self.create_element_from_file_select_dialog_icon = QIcon(QPixmap('icons/document-new-6.png'))
        self.create_element_from_file_select_dialog_pb.setIcon(self.create_element_from_file_select_dialog_icon)
        self.clear_maps_pb = QPushButton('Clear maps')
        self.clear_maps_pb.clicked.connect(self.unload_elements)
        self.add_maps_hbox.addWidget(self.clear_maps_pb)
        self.clear_maps_icon = QIcon(QPixmap('icons/dialog-cancel-5.png'))
        self.clear_maps_pb.setIcon(self.clear_maps_icon)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumSize(QSize(160, 50))

        self.scroll_widget = QWidget()
        self.elements_vbox = QVBoxLayout()
        self.elements_vbox.setAlignment(Qt.AlignTop)

        self.radio_buttons_group = QButtonGroup()

        self.scroll_widget.setLayout(self.elements_vbox)
        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area)  # an area is a type of widget required for scroll areas
        self.main_widget.setLayout(self.main_layout)
        self.setWidget(self.main_widget)

    def load_from_disk(self):
        self.unload_elements()
        self.save_uri = self.root_app.project_args['maps_settings_uri']
        loaded_object = utilities.file_to_python_object(self.save_uri)

        if isinstance(loaded_object, list):
            self.elements = OrderedDict()
        else:
            for name, args in loaded_object.items():
                default_args = self.create_default_element_args(name)
                for default_key, default_value in default_args.items():
                    if default_key not in args or not args[default_key]:
                        args[default_key] = default_value
                self.load_element(name, args)

    def load_element(self, name, args):
        if not name:
            LOGGER.warn('Asked to load an element with a blank name.')
        elif name in self.elements:
            LOGGER.warn('Attempted to add element that already exists.')
        else:
            element = Map(name, args, self.root_app, self)
            self.elements[name] = element
            self.elements_vbox.addWidget(element)

    def create_element(self, name, args=None):
        if not args:
            args = self.create_default_element_args(name)
        element = Map(name, args, self.root_app, self)
        self.elements[name] = element
        self.elements_vbox.addWidget(element)

    def create_default_element_args(self, name):
        args = MapWidget.default_element_args.copy()
        args['name'] = name
        return args

    def create_element_from_file_select_dialog(self):
        """Adds from a file not defined in sources"""
        selected_uri = str(
            QFileDialog.getOpenFileName(self, 'Select spatial file to add to map', self.root_app.project_folder))
        if selected_uri:
            folder, filename = os.path.split(selected_uri)
            subpath = os.path.basename(os.path.normpath(folder))
            display_name = subpath + '/' + filename

            args = MapWidget.default_element_args.copy()
            args['name'] = display_name
            args['source_uri'] = selected_uri
            self.create_element(display_name, args)

    def unload_elements(self):
        for element in self.elements.values():
            element.remove_self()

    def save_to_disk(self):
        if len(self.elements) == 0:
            to_write = ','.join([name for name in self.default_state[''].keys()])
        else:
            to_write = OrderedDict()
            for name, element in self.elements.items():
                to_write.update({name: element.get_element_state_as_args()})
        utilities.python_object_to_csv(to_write, self.save_uri)

    def map_cb_toggle(self, state):
        # TODO DOUG 1 BUG If the user clicks a checkbox before the matplotlib canvas had been loaded by other means, there
        # is a probability of a concurrency error. Fix this by making the canvas be preloaded?
        toggled_signal = str(self.sender().text())
        if state:
            self.name_of_toggled = toggled_signal
            self.root_app.set_visible_matrix_by_name(self.name_of_toggled)
            self.root_app.place_map_viewer()


class Map(MeshAbstractObject, QWidget):
    """
    A map displays a specific source or external spatial map. It does not remake the files but instead contains
    formatting parameters and buttons for manipulation.
    """

    def __init__(self, name, args, root_app=None, parent=None):
        super(Map, self).__init__(root_app, parent)
        self.name = name
        self.args = args

        self.initialize_from_args()

        self.create_ui()
        self.set_state_from_args()

    def create_ui(self):
        self.main_hbox = QHBoxLayout()
        self.main_hbox.setSpacing(0)
        self.main_hbox.setMargin(0)

        self.setLayout(self.main_hbox)
        # self.display_map_cb = QCheckBox(self.name)
        self.cb = QRadioButton(self.name)
        self.parent.radio_buttons_group.addButton(self.cb)

        self.cb.toggled.connect(self.parent.map_cb_toggle)
        self.main_hbox.addWidget(self.cb)
        self.main_hbox.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))

        self.icon_size = QSize(16, 16)

        self.edit_pb = QPushButton()
        self.edit_icon = QIcon(QPixmap('icons/configure-4.png'))
        self.edit_pb.setIcon(self.edit_icon)
        self.edit_pb.setIconSize(self.icon_size)
        self.edit_pb.clicked.connect(self.edit)
        self.main_hbox.addWidget(self.edit_pb)

        self.use_pb = QPushButton()
        self.use_icon = QIcon(QPixmap('icons/bookmark.png'))
        self.use_pb.setIcon(self.use_icon)
        self.use_pb.setIconSize(self.icon_size)
        self.use_pb.clicked.connect(self.use)
        self.main_hbox.addWidget(self.use_pb)

        self.remove_pb = QPushButton()
        self.remove_icon = QIcon(QPixmap('icons/edit-delete-2.png'))
        self.remove_pb.setIcon(self.remove_icon)
        self.remove_pb.setIconSize(self.icon_size)
        self.remove_pb.clicked.connect(self.remove_self)
        self.main_hbox.addWidget(self.remove_pb)

    def initialize_from_args(self):
        self.name = self.args['name']
        self.source_uri = self.args['source_uri']
        self.source_name = self.args['source_name']
        self.parent_scenario_name = self.args['parent_scenario_name']
        self.title = self.args['title']
        self.cbar_label = self.args['cbar_label']
        self.checked = self.args['checked']

        if not self.args['vmin'] or self.args['vmin']:
            self.vmin = utilities.get_raster_min_max(self.source_uri, "min")
            self.vmax = utilities.get_raster_min_max(self.source_uri, "max")
        else:
            self.vmin = self.args['vmin']
            self.vmax = self.args['vmax']

        ignore_values_list = self.args['ignore_values_list'].split(',')
        self.ignore_values = ' '.join(ignore_values_list)
        if self.args['color_scheme']:
            self.color_scheme = self.args['color_scheme']
        else:
            self.color_scheme = 'Spectral'

    def set_state_from_args(self):
        """nyi because this only worked if i was on the correct map viewer central widget."""
        # if self.checked:
        #     self.cb.setChecked(True)
        # else:
        #     self.cb.setChecked(False)

    def get_element_state_as_args(self):
        to_return = OrderedDict()
        to_return['name'] = self.name
        to_return['source_uri'] = self.source_uri
        to_return['source_name'] = self.source_name
        to_return['parent_scenario_name'] = ''
        to_return['title'] = self.title
        to_return['cbar_label'] = self.cbar_label
        to_return['checked'] = self.checked
        to_return['vmin'] = float(self.vmin)
        to_return['vmax'] = float(self.vmax)
        to_return['ignore_values_list'] = self.ignore_values
        to_return['color_scheme'] = self.color_scheme

        return to_return

    def edit(self):
        self.editor_dialog = MapEditDialog(self.root_app, self)

    def use(self):
        """NYI"""
        print('NYI, but a good place to start would be making self.root_app.reports_widget.create_element()')

    def remove_self(self):
        del self.parent.elements[self.name]
        self.setParent(None)


class MapCanvasHolderWidget(MeshAbstractObject, QWidget):
    """
    Qt-enabled object ready to hold the MapCanvas.
    """

    def __init__(self, root_app=None, parent=None):
        super(MapCanvasHolderWidget, self).__init__(root_app, parent)

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        # self.setMaximumSize(222, 222)

        self.title_l = QLabel()
        self.title_l.setText('View Input and Output Maps')
        self.title_l.setFont(config.heading_font)
        self.main_layout.addWidget(self.title_l)

        self.graph_widget = QWidget()
        self.map_viewer_canvas = MapCanvas(self.root_app, parent)
        self.map_viewer_canvas.fig.set_tight_layout(True)
        self.map_viewer_nav = NavigationToolbar(self.map_viewer_canvas, self.graph_widget)
        self.main_layout.addWidget(self.map_viewer_canvas)
        self.main_layout.addWidget(self.map_viewer_nav)


class ShapefileViewerCanvas(FigureCanvas):
    # TODO DOUG 2 Make better. Work with bigger files without crashing.
    def __init__(self, root_app=None, parent=None):
        self.fig = Figure(figsize=(100, 100), dpi=75)
        super(ShapefileViewerCanvas, self).__init__(self.fig)
        self.root_app = root_app
        self.parent = parent

        self.ax = self.fig.add_subplot(111)
        self.shapefile = None

        cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)

    def draw_shapefile(self, shapefile_uri):
        """Function currently unimplemented after removing dependency on
            mpl_toolkits.basemap
        """
        self.ds = ogr.Open(shapefile_uri)
        self.n_layers = self.ds.GetLayerCount()
        self.layer = self.ds.GetLayer(0)
        self.extent = self.layer.GetExtent()
        self.x_center = (self.extent[3] - self.extent[2]) / 2.0
        self.y_center = (self.extent[1] - self.extent[0]) / 2.0

        # After removing basemap dependency, currenly unfinished function
        self.draw()


    def onclick(self, event):
        if event.button == 1:
            self.select_feature_by_point(event.xdata, event.ydata)

    def select_feature_by_point(self, x, y):
        wkt = 'POINT (' + str(x) + ' ' + str(y) + ')'

        # In a clever turn of events, turns out you can select a specific polygon by filtering on a point wkt.
        self.layer.SetSpatialFilter(ogr.CreateGeometryFromWkt(wkt))
        for feature in self.layer:
            selected_id = feature.GetField("HYBAS_ID")
        self.parent.select_id(selected_id)


class MapCanvas(FigureCanvas):  # Objects created from this class generate a FigureCanvas QTWidget that displays a MatPlotLib Figure. Benefits of MPL is that it allows easy navigation and formatting, but is quite slow at rendering. Good for final outputs that are static.
    """
    Subclass to represent the FigureCanvas widget. This gets added to the MapCanvasHolderWidget which connects it to the Nav
    and adds Qt controsl.
    """

    def __init__(self, root_app=None, parent=None):
        """
        Because FigureCanvas requires that a Figure is created first and passed to it on creation, and given the complexity of having the HolderWidget so that the NavBar connects
        to the Canvas, I had to make MapCanvas NOT inherit MeshAbstractObject. Thus, i manually set self.root_app and self.parent
        and call self.root_app to access the other parts of MeshAbstractObject.
        """
        self.fig = Figure(figsize=(100, 100), dpi=75)  # Must be created before super is called becuase FigureCanvas needs it, figsize sets the maximium size but it will be scaled as a qwidget if smalller, dpi affects relatives sizes within the figure, esp font sizes relative to mapa.
        super(MapCanvas, self).__init__(self.fig)
        self.root_app = root_app
        self.parent = parent

        self.ax = self.fig.add_subplot(111)
        self.ax.xaxis.set_visible(False)
        self.ax.yaxis.set_visible(False)
#        self.fig.set_lod(True)

    def draw_visible_array(self):
        try:
            self.cax.set_array(self.root_app.visible_matrix)
        except:
            self.cax = self.ax.imshow(self.root_app.visible_matrix, interpolation='nearest')  # vmin=0, vmax=255
            self.cbar = self.fig.colorbar(self.cax, orientation="horizontal", fraction=.045, pad=.05,
                                          aspect=20)  # extend="both", anchor=(1,-5), panchor=(0.0, 0.0) ticks = [0,1,2,3]

        self.cax.set_clim(float(self.root_app.visible_map.vmin), float(self.root_app.visible_map.vmax))
        self.ax.set_title(self.root_app.visible_map.title)
        self.cbar.set_label(self.root_app.visible_map.cbar_label)
        self.cax.set_cmap(self.root_app.visible_map.color_scheme)
        # TODO JUSTIN Incorporate auto-interpolation.
        self.draw()


class Source(MeshAbstractObject, QWidget):
    """
    A label, link and uri to one of the scenarioSources that go into the Scenario object's self.sources ordered dict

    This element type is not fully implemented and only uses URI to link the name to the file. It does not yet read/write from the
    sources file.
    """

    def __init__(self, name, uri, root_app=None, parent=None):
        super(Source, self).__init__(root_app, parent)
        self.name = name
        self.uri = uri
        if parent:
            self.parent_scenario_name = parent.name
        else:
            self.parent_scenario_name = None

        self.create_ui()

    # --- Required element I/O  functions
    def create_ui(self):
        self.main_hbox = QHBoxLayout()
        self.main_hbox.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_hbox)
        # TODO JUSTIN CONSIDER I took a shortcut here: rather than have it save to the sources.csv file, i assumed all names are the last bit of their uri.
        shortened_name = os.path.split(self.name)[1]
        self.source_l = QLabel(shortened_name)
        self.source_l.setContentsMargins(0, 0, 2, 0)  # L T R B. Because sources are itallic, this doesn't work without a tiny bit of padding.
        self.source_l.setFont(config.italic_font)
        self.main_hbox.addWidget(self.source_l)

    def remove_self(self):
        del self.parent.elements[self.name]
        self.setParent(None)

class WarningPopupWidget(QMessageBox):
    def __init__(self, message_text):
        QMessageBox.__init__(self)
        self.widget = QWidget()
        self.warning(self.widget, 'Warning', message_text)
        self.setMinimumHeight(400)
        self.setMinimumWidth(600)
        # self.message_box.exec_()

class NewProjectWidget(MeshAbstractObject, QWidget):
    """
    Loads when there is no project set. Prompts user to create or load a project.
    """

    def __init__(self, root_app=None, parent=None):
        super(NewProjectWidget, self).__init__(root_app, parent)

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.title_l = QLabel()
        self.title_l.setText('No project selected')
        self.title_l.setFont(config.heading_font)
        self.main_layout.addWidget(self.title_l)

        self.subtitle_l = QLabel()
        self.subtitle_l.setText('Load existing project or create a new project using the tool buttons above or the buttons here.')
        self.subtitle_l.setFont(config.italic_font)
        self.main_layout.addWidget(self.subtitle_l)

        self.button_box = QHBoxLayout()
        self.main_layout.addLayout(self.button_box)

        self.new_project_pb = QPushButton('Create new project')
        self.new_project_pb.clicked.connect(self.root_app.create_new_project)
        self.button_box.addWidget(self.new_project_pb)

        self.new_project_pb = QPushButton('Load existing project')
        self.new_project_pb.clicked.connect(self.root_app.select_project_to_load)
        self.button_box.addWidget(self.new_project_pb)

        self.main_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Fixed, QSizePolicy.MinimumExpanding))

        self.logo_hbox = QHBoxLayout()
        self.logo_hbox.setAlignment(Qt.AlignCenter)
        self.main_layout.addLayout(self.logo_hbox)
        self.faded_logo_pixmap = QPixmap('icons/mesh_green_faded.png')
        self.faded_logo_l = QLabel()
        self.faded_logo_l.setPixmap(self.faded_logo_pixmap)
        self.logo_hbox.addWidget(self.faded_logo_l)

        self.main_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Fixed, QSizePolicy.MinimumExpanding))


class ChooseReportTypeDialog(MeshAbstractObject, QDialog):
    """
    Dialog that prompts user on how to create a report.
    """

    def __init__(self, root_app=None, parent=None):
        super(ChooseReportTypeDialog, self).__init__(root_app, parent)
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle('Create a report from this run')
        self.description = QLabel('Choose which type of report to make from this run.\n')
        self.main_layout.addWidget(self.description)

        self.how_to_add_images = QLabel('To add formatted, cropped or zoomed images, use the map viewer to produce the desired map, then save the map in the model\'s output folder\n')
        self.how_to_add_images.setWordWrap(True)
        self.main_layout.addWidget(self.how_to_add_images)

        self.report_types = ['Executive Summary', 'Policy Brief', 'In-depth Scenario Comparison',
                             'Full Technical Report']
        # TODO JUSTIN SHORTCUT I didn't follow the approach i used for the other things, like scenario generators, of having this be an external file, though, i am not sure that was the best choice anyhow.
        # TODO JUSTIN SHORTCUT I also didn't follow the OrderedDict.name, .longname notation

        self.pbs = OrderedDict()
        for report_type in self.report_types:
            self.pbs.update({report_type: QPushButton(report_type)})
            self.main_layout.addWidget(self.pbs[report_type])

        self.pbs['Executive Summary'].clicked.connect(self.create_executive_summary)
        self.pbs['Policy Brief'].clicked.connect(self.create_policy_brief)
        self.pbs['Policy Brief'].setEnabled(False)
        self.pbs['In-depth Scenario Comparison'].clicked.connect(self.create_in_depth_scenario_comparison)
        self.pbs['In-depth Scenario Comparison'].setEnabled(False)
        self.pbs['Full Technical Report'].clicked.connect(self.create_full_technical_report)
        self.pbs['Full Technical Report'].setEnabled(False)

        self.additional_reports_l = QLabel('\n\nAdditional report types can be added as plugins.')
        self.additional_reports_l.setFont(config.italic_font)
        self.main_layout.addWidget(self.additional_reports_l)

        self.add_plugins_pb = QPushButton('Install Plugins')
        self.add_plugins_pb.clicked.connect(self.root_app.create_load_plugin_dialog)
        self.main_layout.addWidget(self.add_plugins_pb)

        self.show()

    def create_executive_summary(self):
        if isinstance(self.parent, ModelRun):
            self.parent.create_report_from_this_run('executive_summary')
        elif isinstance(self.parent, ReportsWidget):
            selected_model_name = str(self.parent.runs_available_combobox.currentText())
            selected_model = self.root_app.model_runs_widget.elements[selected_model_name]
            selected_model.create_report_from_this_run('executive_summary')

        self.close()

    def create_policy_brief(self):
        self.parent.create_report_from_this_run(model_run, 'executive_summary')
        self.close()

    def create_in_depth_scenario_comparison(self):
        self.parent.create_report_from_this_run(model_run, 'executive_summary')
        self.close()

    def create_full_technical_report(self):
        self.parent.create_report_from_this_run('model_run, executive_summary')
        self.close()


class BaselinePopulatorDialog(MeshAbstractObject, QDialog):
    """
    Dialog prompting user on how the Baseline scenario can be filled with data.
    """
    default_element_args = OrderedDict()
    default_element_args['name'] = ''
    default_element_args['long_name'] = ''
    default_element_args['model_type'] = ''
    default_element_args['model_args'] = ''
    default_element_args['enabled'] = ''

    default_state = OrderedDict()
    default_state['user_defined_file'] = default_element_args.copy()
    default_state['user_defined_file']['name'] = 'user_defined_file'
    default_state['user_defined_file']['long_name'] = 'User defined file'
    default_state['user_defined_file']['model_type'] = 'MESH_built_in'
    default_state['user_defined_file']['model_args'] = ''
    default_state['user_defined_file']['enabled'] = True

    default_state['mesh_data_generator'] = default_element_args.copy()
    default_state['mesh_data_generator']['name'] = 'mesh_data_generator'
    default_state['mesh_data_generator']['long_name'] = 'Use MESH data generator'
    default_state['mesh_data_generator']['model_type'] = 'MESH_built_in'
    default_state['mesh_data_generator']['model_args'] = ''
    default_state['mesh_data_generator']['enabled'] = True

    def __init__(self, root_app=None, parent=None):
        super(BaselinePopulatorDialog, self).__init__(root_app, parent)
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle('Data for Baseline')
        self.description = QLabel('Define or create data for the baseline scenario')
        self.main_layout.addWidget(self.description)

        self.pbs = OrderedDict()

        for name, settings in self.root_app.baseline_generators_settings.items():
            self.pbs.update({name: QPushButton(settings['long_name'])})
            self.main_layout.addWidget(self.pbs[name])
            if settings['enabled'] == 'False':  # This might fail due to string to bool parsing
                self.pbs[name].setEnabled(False)

        self.additional_generators_l = QLabel(
            '\n\nAdditional baseline generation methods or models\ncan be added as plugins.')
        self.additional_generators_l.setFont(config.italic_font)
        self.main_layout.addWidget(self.additional_generators_l)

        self.add_plugins_pb = QPushButton('Install Plugins')
        self.add_plugins_pb.clicked.connect(self.root_app.create_load_plugin_dialog)
        self.main_layout.addWidget(self.add_plugins_pb)

        self.pbs['user_defined_file'].clicked.connect(self.set_to_user_defined_file)
        self.pbs['mesh_data_generator'].clicked.connect(self.load_mesh_data_generator)

        self.show()

    def set_to_user_defined_file(self):
        file_uri = str(QFileDialog.getOpenFileName(self, 'Select file to add to baseline',
                                                   os.path.join(self.root_app.project_folder, 'input', 'Baseline')))
        if file_uri:
            self.parent.load_element(file_uri, file_uri)

    def load_mesh_data_generator(self):
        self.root_app.baseline_data_dialog = CreateBaselineDataDialog(self.root_app, self)


class ChooseSetAOIMethodDialog(MeshAbstractObject, QDialog):
    """
    Dialog prompting user on how the Baseline scenario can be filled with data.
    """
    default_element_args = OrderedDict()
    default_element_args['name'] = ''
    default_element_args['long_name'] = ''
    default_element_args['model_type'] = ''
    default_element_args['model_args'] = ''
    default_element_args['enabled'] = ''

    default_state = OrderedDict()
    default_state['set_as_user_defined_shapefile'] = default_element_args.copy()
    default_state['set_as_user_defined_shapefile']['name'] = 'set_as_user_defined_shapefile'
    default_state['set_as_user_defined_shapefile']['long_name'] = 'Set as User-Defined Shapefile'
    default_state['set_as_user_defined_shapefile']['enabled'] = True

    default_state['set_as_hydrosheds_watershed'] = default_element_args.copy()
    default_state['set_as_hydrosheds_watershed']['name'] = 'set_as_hydrosheds_watershed'
    default_state['set_as_hydrosheds_watershed']['long_name'] = 'Set as HydroSHEDS Watershed*'
    default_state['set_as_hydrosheds_watershed']['enabled'] = True

    # default_state['set_as_administrative_boundary'] = default_element_args.copy()
    # default_state['set_as_administrative_boundary']['name'] = 'set_as_administrative_boundary'
    # default_state['set_as_administrative_boundary']['long_name'] = 'Set as Administrative Boundary'
    # default_state['set_as_administrative_boundary']['enabled'] = False

    def __init__(self, root_app=None, parent=None):
        super(ChooseSetAOIMethodDialog, self).__init__(root_app, parent)
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle('Define/create baseline scenario')
        self.description = QLabel('Define or create the data that defines the baseline scenario')
        self.main_layout.addWidget(self.description)

        self.pbs = OrderedDict()

        for name, settings in ChooseSetAOIMethodDialog.default_state.items():
            self.pbs.update({name: QPushButton(settings['long_name'])})
            self.main_layout.addWidget(self.pbs[name])
            if settings['enabled'] == 'False':  # This might fail due to string to bool parsing
                self.pbs[name].setEnabled(False)

        self.pbs['set_as_user_defined_shapefile'].clicked.connect(self.set_as_user_defined_shapefile)
        self.pbs['set_as_hydrosheds_watershed'].clicked.connect(self.set_as_hydrosheds_watershed)
        # self.pbs['set_as_administrative_boundary'].clicked.connect(self.set_as_administrative_boundary)

        self.show()

    def set_as_user_defined_shapefile(self):
        aoi_uri = str(
            QFileDialog.getOpenFileName(self, 'Select shape file of desired extent', self.root_app.project_folder))
        if aoi_uri:
            if ' ' in os.path.split(aoi_uri)[1]:
                self.warning = WarningPopupWidget('Shapefile cannot have spaces in the name.')
            elif aoi_uri.endswith('.shp'):
                self.root_app.set_project_aoi(aoi_uri)

            else:
                self.warning = WarningPopupWidget('Invalid file selected. Must be a .shp file.')

    def set_as_hydrosheds_watershed(self):
        if not os.path.exists(self.root_app.base_data_hydrosheds_folder):
            self.root_app.create_configure_base_data_dialog()
        else:
            self.root_app.clip_from_hydrosheds_watershed_dialog = ClipFromHydroshedsWatershedDialog(self.root_app, self)

    def set_as_administrative_boundary(self):
        self.root_app.clip_from_hydrosheds_watershed_dialog = ClipFromAdministrativeBoundaryDialog(self.root_app, self)


class ScenarioPopulatorDialog(MeshAbstractObject, QDialog):
    """
    Dialog prompting user on how a scenario can be filled with inputs.
    """
    default_element_args = OrderedDict()
    default_element_args['name'] = ''
    default_element_args['long_name'] = ''
    default_element_args['model_type'] = ''
    default_element_args['model_args'] = ''
    default_element_args['enabled'] = ''

    default_state = OrderedDict()
    default_state['user_defined_folder'] = default_element_args.copy()
    default_state['user_defined_folder']['name'] = 'user_defined_folder'
    default_state['user_defined_folder']['long_name'] = 'User Defined Folder'
    default_state['user_defined_folder']['model_type'] = 'MESH_built_in'
    default_state['user_defined_folder']['model_args'] = ''
    default_state['user_defined_folder']['enabled'] = True

    default_state['invest_scenario_generator'] = default_element_args.copy()
    default_state['invest_scenario_generator']['name'] = 'invest_scenario_generator'
    default_state['invest_scenario_generator']['long_name'] = 'InVEST Scenario Generator'
    default_state['invest_scenario_generator']['model_type'] = 'MESH_built_in'
    default_state['invest_scenario_generator']['model_args'] = ''
    default_state['invest_scenario_generator']['enabled'] = True

    default_state['climate_scenario'] = default_element_args.copy()
    default_state['climate_scenario']['name'] = 'climate_scenario'
    default_state['climate_scenario']['long_name'] = 'Climate scenario generator'
    default_state['climate_scenario']['model_type'] = 'MESH_built_in'
    default_state['climate_scenario']['model_args'] = ''
    default_state['climate_scenario']['enabled'] = False

    default_state['invest_lcm'] = default_element_args.copy()
    default_state['invest_lcm']['name'] = 'invest_lcm'
    default_state['invest_lcm']['long_name'] = 'InVEST Land-Change Model'
    default_state['invest_lcm']['model_type'] = 'MESH_built_in'
    default_state['invest_lcm']['model_args'] = ''
    default_state['invest_lcm']['enabled'] = False

    default_state['roi_maximizer'] = default_element_args.copy()
    default_state['roi_maximizer']['name'] = 'roi_maximizer'
    default_state['roi_maximizer']['long_name'] = 'Return-on-Investment (ROI) maximizer'
    default_state['roi_maximizer']['model_type'] = 'MESH_built_in'
    default_state['roi_maximizer']['model_args'] = ''
    default_state['roi_maximizer']['enabled'] = False

    default_state['tradeoff_frontier_maximizer'] = default_element_args.copy()
    default_state['tradeoff_frontier_maximizer']['name'] = 'tradeoff_frontier_maximizer'
    default_state['tradeoff_frontier_maximizer']['long_name'] = 'Tradeoff frontier maximizer'
    default_state['tradeoff_frontier_maximizer']['model_type'] = 'MESH_built_in'
    default_state['tradeoff_frontier_maximizer']['model_args'] = ''
    default_state['tradeoff_frontier_maximizer']['enabled'] = False

    default_state['market_change_simulator'] = default_element_args.copy()
    default_state['market_change_simulator']['name'] = 'market_change_simulator'
    default_state['market_change_simulator']['long_name'] = 'Market change simulator'
    default_state['market_change_simulator']['model_type'] = 'MESH_built_in'
    default_state['market_change_simulator']['model_args'] = ''
    default_state['market_change_simulator']['enabled'] = False

    def __init__(self, root_app=None, parent=None):
        super(ScenarioPopulatorDialog, self).__init__(root_app, parent)
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle('Define scenario')
        self.description = QLabel('Specify how this scenario differs from the baseline')
        self.main_layout.addWidget(self.description)

        self.pbs = OrderedDict()

        for scenario_generation_method in self.root_app.scenario_generators_settings.values():
            self.pbs.update({scenario_generation_method['name']: QPushButton(scenario_generation_method['long_name'])})
            self.main_layout.addWidget(self.pbs[scenario_generation_method['name']])
            if scenario_generation_method['enabled'] == 'False':  # This might fail due to string to bool parsing
                self.pbs[scenario_generation_method['name']].setEnabled(False)

            # NEXT RELEASE Create a proper signal-slot relationship so that it adds the generated file to the scenario upon completion.
            if scenario_generation_method['name'] == 'invest_scenario_generator':
                self.pbs[scenario_generation_method['name']].setText(
                    str(self.pbs[scenario_generation_method['name']].text()) + ' *')

        self.asterisk_l = QLabel('\n\n* Click "User Defined Scenario" after running this model to add it.')
        self.main_layout.addWidget(self.asterisk_l)

        self.additional_generators_l = QLabel(
            '\n\nAdditional scenario generation methods or models\ncan be added as plugins.')
        self.additional_generators_l.setFont(config.italic_font)
        self.main_layout.addWidget(self.additional_generators_l)

        self.add_plugins_pb = QPushButton('Install Plugins')
        self.add_plugins_pb.clicked.connect(self.root_app.create_load_plugin_dialog)
        self.main_layout.addWidget(self.add_plugins_pb)

        self.pbs['user_defined_folder'].clicked.connect(self.populate_with_existing_file)
        self.pbs['invest_scenario_generator'].clicked.connect(self.setup_invest_model_signal_wrapper)

        self.show()

    def setup_invest_model_signal_wrapper(self):
        if self.sender() is self.pbs['invest_scenario_generator']:
            self.root_app.models_dock.models_widget.setup_invest_model(self.parent)

    def populate_with_existing_file(self):
        source_uri = str(QFileDialog.getOpenFileName(self, 'Select map file to attach', self.root_app.project_folder))
        if source_uri:
            source_name = os.path.split(source_uri)[1]
            self.parent.load_element(source_name, source_uri)

    def populate_with_scenario_generator(self):
        """
        Calls the InVEST scenario generator on a separate thread, and then adds a new source to the target scenario.
        This works by loading an args dict from a pre-defined json file, and then using the suffix blank on the UI form
        as the name of the source. There are many ways this could be improved, but I didn't want to modify scenario_generator.py
        """
        default_scenario_generator_setup_file_uri = os.path.join(self.root_app.default_setup_files_folder,
                                                                 'scenario_generator_setup_file.json')  # note that json files for some reason have - not _
        save_folder = os.path.join(self.root_app.project_folder, 'input', self.parent.name)
        scenario_specific_scenario_generator_setup_file_uri = os.path.join(save_folder,
                                                                           'scenario_generator_setup_file.json')

        if os.path.exists(scenario_specific_scenario_generator_setup_file_uri):
            override_args = utilities.file_to_python_object(scenario_specific_scenario_generator_setup_file_uri)
        else:
            override_args = utilities.file_to_python_object(default_scenario_generator_setup_file_uri)

        override_args['workspace_dir'] = save_folder
        scenario_generator_iui_json_file = 'scenario-generator.json'
        modelui.main(scenario_generator_iui_json_file, last_run_override=override_args)
        uri = os.path.join(save_folder, 'scenario_' + override_args['suffix'] + '.tif')


class ClipFromHydroshedsWatershedDialog(MeshAbstractObject, QDialog):
    """
    Dialog for baseline generator.
    """
    def __init__(self, root_app=None, parent=None):
        super(ClipFromHydroshedsWatershedDialog, self).__init__(root_app, parent)
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle('Create baseline data for selected models using HydroBASINS ID')
        self.title_l = QLabel('Create baseline data for selected models using HydroBASINS ID')
        self.title_l.setFont(config.heading_font)
        self.main_layout.addWidget(self.title_l)

        self.main_layout.addWidget(QLabel())

        self.search_for_hybas_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.search_for_hybas_hbox)
        self.select_continent_l = QLabel('Select HydroBASINS continent and scale:')
        self.search_for_hybas_hbox.addWidget(self.select_continent_l)

        self.continents = ['Africa', 'Arctic', 'Asia', 'Australia', 'Europe', 'Greenland', 'North America',
                           'South America', 'Siberia']
        self.continents_combobox = QComboBox()
        self.continents_combobox.addItems(self.continents)
        self.search_for_hybas_hbox.addWidget(self.continents_combobox)
        #        self.continents_combobox.setCurrentIndex(self.continents.index('--select--'))

        self.hybas_levels = ['1', '2', '3', '4', '5', '6']
        self.hybas_level_combobox = QComboBox()
        self.hybas_level_combobox.addItems(self.hybas_levels)
        self.search_for_hybas_hbox.addWidget(self.hybas_level_combobox)
        self.hybas_level_combobox.setCurrentIndex(self.hybas_levels.index('3'))

        self.display_hybas_shapefile_pb = QPushButton('Display')
        self.search_for_hybas_hbox.addWidget(self.display_hybas_shapefile_pb)
        self.display_hybas_shapefile_pb.clicked.connect(self.show_map)
        self.display_hybas_shapefile_pb.setMaximumWidth(160)

        self.main_layout.addWidget(QLabel())

        self.click_to_select_l = QLabel('Click the map below to select your project\'s watershed.')
        self.main_layout.addWidget(self.click_to_select_l)


        self.main_layout.addWidget(QLabel())

        self.scroll_widget = ScrollWidget(self.root_app, self)
        self.main_layout.addWidget(self.scroll_widget)
        self.scroll_widget.setMinimumSize(800, 700)

        self.shapefile_viewer_canvas = ShapefileViewerCanvas(self.root_app, self)
        self.scroll_widget.scroll_layout.addWidget(self.shapefile_viewer_canvas)

        self.shapefile_viewer_nav = NavigationToolbar(self.shapefile_viewer_canvas, QWidget())
        self.scroll_widget.scroll_layout.addWidget(self.shapefile_viewer_nav)

        self.select_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.select_hbox)
        self.id_header_l = QLabel('Alternatively, you can select your watershed by typing its HydroBASINS ID.')
        self.select_hbox.addWidget(self.id_header_l)
        self.id_le = QLineEdit()
        self.select_hbox.addWidget(self.id_le)
        self.select_pb = QPushButton('Select ID')
        self.select_hbox.addWidget(self.select_pb)
        self.select_pb.clicked.connect(self.select_id)
        self.select_pb.setMaximumWidth(100)

        self.show()

    def show_map(self):
        selected_shapefile_uri = self.get_selected_hybas_uri()

        self.shapefile_viewer_canvas.close()
        self.shapefile_viewer_nav.close()
        self.shapefile_viewer_canvas = ShapefileViewerCanvas(self.root_app, self)
        self.scroll_widget.scroll_layout.addWidget(self.shapefile_viewer_canvas)

        self.shapefile_viewer_nav = NavigationToolbar(self.shapefile_viewer_canvas, QWidget())
        self.scroll_widget.scroll_layout.addWidget(self.shapefile_viewer_nav)

        # Commenting out this line becasue the function being called is
        # unfinished after removing dependency on basemap
        #self.shapefile_viewer_canvas.draw_shapefile(selected_shapefile_uri)


    def get_selected_hybas_uri(self):
        selected_continent = str(self.continents_combobox.currentText())
        selected_level = str(self.hybas_level_combobox.currentText())

        if selected_continent == 'Africa':
            hybas_uri = os.path.join(self.root_app.base_data_hydrosheds_folder,
                                     'hybas_af_lev01-06_v1c/hybas_af_lev0' + selected_level + '_v1c.shp')
        if selected_continent == 'Arctic':
            hybas_uri = os.path.join(self.root_app.base_data_hydrosheds_folder,
                                     'hybas_ar_lev01-06_v1c/hybas_ar_lev0' + selected_level + '_v1c.shp')
        if selected_continent == 'Asia':
            hybas_uri = os.path.join(self.root_app.base_data_hydrosheds_folder,
                                     'hybas_as_lev01-06_v1c/hybas_as_lev0' + selected_level + '_v1c.shp')
        if selected_continent == 'Australia':
            hybas_uri = os.path.join(self.root_app.base_data_hydrosheds_folder,
                                     'hybas_au_lev01-06_v1c/hybas_au_lev0' + selected_level + '_v1c.shp')
        if selected_continent == 'Europe':
            hybas_uri = os.path.join(self.root_app.base_data_hydrosheds_folder,
                                     'hybas_eu_lev01-06_v1c/hybas_eu_lev0' + selected_level + '_v1c.shp')
        if selected_continent == 'Greenland':
            hybas_uri = os.path.join(self.root_app.base_data_hydrosheds_folder,
                                     'hybas_gr_lev01-06_v1c/hybas_gr_lev0' + selected_level + '_v1c.shp')
        if selected_continent == 'North America':
            hybas_uri = os.path.join(self.root_app.base_data_hydrosheds_folder,
                                     'hybas_na_lev01-06_v1c/hybas_na_lev0' + selected_level + '_v1c.shp')
        if selected_continent == 'South America':
            hybas_uri = os.path.join(self.root_app.base_data_hydrosheds_folder,
                                     'hybas_sa_lev01-06_v1c/hybas_sa_lev0' + selected_level + '_v1c.shp')
        if selected_continent == 'Siberia':
            hybas_uri = os.path.join(self.root_app.base_data_hydrosheds_folder,
                                     'hybas_si_lev01-06_v1c/hybas_si_lev0' + selected_level + '_v1c.shp')

        return hybas_uri

    def select_id(self, id=None):
        if not id:
            id = str(self.id_le.text())
        selected_continent = str(self.continents_combobox.currentText())
        selected_level = str(self.hybas_level_combobox.currentText())
        hybas_uri = self.get_selected_hybas_uri()

        output_shp_uri = os.path.join(self.root_app.project_folder, 'input',
                                      selected_continent.replace(' ', '_').lower() + '_' + selected_level + '_' + str(id) + '.shp')

        data_creation.save_shp_feature_by_attribute(hybas_uri, id, output_shp_uri)

        self.root_app.set_project_aoi(output_shp_uri)
        self.parent.close()
        self.close()


class DataExplorerDialog(MeshAbstractObject, QDialog):
    """
    Dialog for baseline generator.
    """
    def __init__(self, root_app=None, parent=None):
        super(DataExplorerDialog, self).__init__(root_app, parent)
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle('Data explorer for run ' + self.parent.name)
        self.title_l = QLabel('Explore data for run ' + self.parent.name)
        self.title_l.setFont(config.heading_font)
        self.main_layout.addWidget(self.title_l)

        self.main_layout.addWidget(QLabel())

        self.scenarios_in_run = self.parent.scenarios_in_run
        self.models_in_run = self.parent.models_in_run

        self.models_in_run_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.models_in_run_hbox)
        self.models_in_run_header_l = QLabel('Models in run:')
        self.models_in_run_header_l.setMaximumWidth(160)
        self.models_in_run_header_l.setFont(config.italic_font)
        self.models_in_run_hbox.addWidget(self.models_in_run_header_l)
        self.models_in_run_l = QLabel()
        self.models_in_run_hbox.addWidget(self.models_in_run_l)
        self.models_in_run_l.setWordWrap(True)
        selected_models_strings = [i.long_name for i in self.models_in_run]
        self.models_in_run_l.setText(', '.join(selected_models_strings))

        self.scenarios_in_run_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.scenarios_in_run_hbox)
        self.scenarios_in_run_header_l = QLabel('Scenarios in run:')
        self.scenarios_in_run_header_l.setMaximumWidth(160)
        self.scenarios_in_run_header_l.setFont(config.italic_font)
        self.scenarios_in_run_hbox.addWidget(self.scenarios_in_run_header_l)
        self.scenarios_in_run_l = QLabel()
        self.scenarios_in_run_hbox.addWidget(self.scenarios_in_run_l)
        self.scenarios_in_run_l.setWordWrap(True)
        selected_models_strings = [i.long_name for i in self.scenarios_in_run]
        self.scenarios_in_run_l.setText(', '.join(selected_models_strings))

        self.main_layout.addWidget(QLabel())

        self.scroll_widget = ScrollWidget(self.root_app, self)
        self.main_layout.addWidget(self.scroll_widget)
        self.scroll_widget.setMinimumSize(800, 700)
        self.scroll_widget.scroll_layout.setAlignment(Qt.AlignTop)

        for model in self.models_in_run:
            model_name_l = QLabel(model.long_name)
            model_name_l.setFont(config.heading_font)
            self.scroll_widget.scroll_layout.addWidget(model_name_l)

            for scenario in self.scenarios_in_run:
                scenario_name_l = QLabel(scenario.long_name)
                scenario_name_l.setFont(config.minor_heading_font)
                self.scroll_widget.scroll_layout.addWidget(scenario_name_l)

                for folder_triplet in os.walk(
                        os.path.join(self.root_app.project_folder, 'output/runs', self.parent.name, scenario.name)):
                    if folder_triplet[2]:
                        for filename in folder_triplet[2]:
                            hbox = QHBoxLayout()
                            self.scroll_widget.scroll_layout.addLayout(hbox)
                            hbox.addWidget(QLabel(filename))
                            hbox.addWidget(QPushButton('Select as report ready object - NOT YET IMPLEMENTED'))
        self.show()


class MapEditDialog(MeshAbstractObject, QDialog):
    """
    Dialog that lets user modify how the map is displayed.
    """

    def __init__(self, root_app=None, parent=None):
        super(MapEditDialog, self).__init__(root_app, parent)

        self.color_schemes = []
        self.color_schemes.extend(
            ['Spectral', 'Spectral_r', 'Blues', 'Blues_r', 'Greens', 'Reds', 'cool', 'hot', 'terrain', 'terrain_r',
             'BuGn', 'PuRd', 'YlOrRd', 'afmhot', 'RdYlBu', 'jet',
             'Blues', 'BuGn', 'BuPu', 'GnBu', 'Greens', 'Greys', 'Oranges', 'OrRd', 'PuBu', 'PuBuGn', 'PuRd', 'Purples',
             'RdPu',
             'Reds', 'YlGn', 'YlGnBu', 'YlOrBr', 'YlOrRd', 'afmhot', 'autumn', 'bone', 'cool', 'copper',
             'gist_heat', 'gray', 'hot', 'pink', 'spring', 'summer', 'winter', 'BrBG', 'bwr', 'coolwarm', 'PiYG',
             'PRGn', 'PuOr',
             'RdBu', 'RdGy', 'RdYlBu', 'RdYlGn', 'Spectral', 'seismic', 'Accent', 'Dark2', 'Paired', 'Pastel1',
             'Pastel2', 'Set1', 'Set2', 'Set3', 'gist_earth', 'terrain', 'ocean', 'gist_stern',
             'brg', 'CMRmap', 'cubehelix', 'gnuplot', 'gnuplot2', 'gist_ncar', 'nipy_spectral', 'jet', 'rainbow',
             'gist_rainbow', 'hsv', 'flag', 'prism'])

        self.vbox = QVBoxLayout()
        self.setLayout(self.vbox)
        self.setWindowTitle('Edit ' + self.parent.name)
        self.title_l = QLabel('Change how the map is displayed')
        self.title_l.setFont(config.minor_heading_font)
        self.vbox.addWidget(self.title_l)

        self.set_range_hbox = QHBoxLayout()
        self.vbox.addLayout(self.set_range_hbox)
        self.set_range_l = QLabel('Range:')
        self.set_range_hbox.addWidget(self.set_range_l)
        # NEXT RELEASE this with the stats calculated when lvisible matrix is toggled.

        self.vmin_le = QLineEdit(str(self.parent.vmin))
        self.set_range_hbox.addWidget(self.vmin_le)
        self.vmax_le = QLineEdit(str(self.parent.vmax))
        self.set_range_hbox.addWidget(self.vmax_le)

        self.set_ignore_values_hbox = QHBoxLayout()
        self.vbox.addLayout(self.set_ignore_values_hbox)
        self.ignore_values_l = QLabel('Ignore values (separate with spaces):')
        self.set_ignore_values_hbox.addWidget(self.ignore_values_l)
        self.ignore_values_le = QLineEdit(str(self.parent.ignore_values))
        self.set_ignore_values_hbox.addWidget(self.ignore_values_le)

        self.set_color_scheme_hbox = QHBoxLayout()
        self.vbox.addLayout(self.set_color_scheme_hbox)
        self.color_scheme_l = QLabel('Color scheme:')
        self.set_color_scheme_hbox.addWidget(self.color_scheme_l)
        self.color_scheme_combobox = QComboBox()
        self.color_scheme_combobox.addItems(self.color_schemes)
        self.color_scheme_combobox.view().setMinimumHeight(350)
        self.color_scheme_combobox.setCurrentIndex(self.color_schemes.index(str(self.parent.color_scheme)))
        self.set_color_scheme_hbox.addWidget(self.color_scheme_combobox)

        self.set_title_hbox = QHBoxLayout()
        self.vbox.addLayout(self.set_title_hbox)
        self.set_title_l = QLabel('Title:')
        self.set_title_hbox.addWidget(self.set_title_l)
        self.set_title_le = QLineEdit(str(self.parent.title))
        self.set_title_hbox.addWidget(self.set_title_le)

        self.set_cbar_label_hbox = QHBoxLayout()
        self.vbox.addLayout(self.set_cbar_label_hbox)
        self.set_cbar_label_l = QLabel('Colorbar label:')
        self.set_cbar_label_hbox.addWidget(self.set_cbar_label_l)
        self.set_cbar_label_le = QLineEdit(str(self.parent.cbar_label))
        self.set_cbar_label_hbox.addWidget(self.set_cbar_label_le)

        self.checked_hbox = QHBoxLayout()
        self.vbox.addLayout(self.checked_hbox)
        self.checked_l = QLabel('Checked?')
        self.checked_hbox.addWidget(self.checked_l)
        self.checked_cb = QCheckBox()
        if str(self.parent.checked):
            self.checked_cb.setChecked(True)
        self.checked_hbox.addWidget(self.checked_cb)

        self.save_cancel_hbox = QHBoxLayout()
        self.vbox.addLayout(self.save_cancel_hbox)
        self.save_pb = QPushButton('Save')
        self.save_pb.clicked.connect(self.save_changes_handler)
        self.save_cancel_hbox.addWidget(self.save_pb)
        self.cancel_pb = QPushButton('Cancel')
        self.cancel_pb.clicked.connect(self.cancel_changes)
        self.save_cancel_hbox.addWidget(self.cancel_pb)

        self.exec_()

    def populate_with_current_values(self):
        """NYI"""

    def save_changes_handler(self):
        self.save_changes()

    def save_changes(self, replot_after_save=True):
        self.parent.vmin = self.vmin_le.text()
        self.parent.vmax = self.vmax_le.text()
        self.parent.ignore_values = ' '.join(str(self.ignore_values_le.text()).split(' '))
        self.parent.color_scheme = str(
            self.color_scheme_combobox.currentText())  # self.color_scheme_combobox.itemData(self.color_scheme_combobox.currentIndex())
        self.parent.title = self.set_title_le.text()
        self.parent.cbar_label = self.set_cbar_label_le.text()
        self.parent.checked = str(self.checked_cb.isChecked())

        if replot_after_save:
            self.root_app.map_canvas_holder_widget.map_viewer_canvas.draw_visible_array()

        self.close()

    def cancel_changes(self):
        self.close()


class RunMeshModelDialog(MeshAbstractObject, QDialog):
    """
    Generates a dialog that includes selected scenario-model pairs, a runtimebox for watching output from the models,
    and a run button that calls the approporate execution method.
    """

    def __init__(self, root_app=None, parent=None):
        super(RunMeshModelDialog, self).__init__(root_app, parent)

        self.main_layout = QVBoxLayout()
        self.setMinimumSize(400, 500)
        self.setLayout(self.main_layout)
        self.setWindowTitle('Run MESH Model')
        self.title_l = QLabel('Run MESH Model for the following scenario-model pairs\n')
        self.title_l.setFont(config.minor_heading_font)
        self.main_layout.addWidget(self.title_l)

        self.draw_scenario_model_pairs_gridlayout()

        self.run_cancel_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.run_cancel_hbox)
        self.run_pb = QPushButton('Run')
        self.run_pb.clicked.connect(self.run)
        self.run_cancel_hbox.addWidget(self.run_pb)
        self.cancel_pb = QPushButton('Close')
        self.cancel_pb.clicked.connect(self.cancel)
        self.run_cancel_hbox.addWidget(self.cancel_pb)

        self.listener = Listener(self.root_app, self)  # Give the dialog it's OWN listener so that the run_in_next_queue fn can update the info box during run time.
        self.listener.start()

        self.exec_()

    def run_next_in_queue(self):
        current_args = self.root_app.args_queue.items()[0][1]
        current_model_name, current_scenario_name = self.root_app.args_queue.items()[0][0].split(' -- ', 1)
        self.update_run_details(
            'Starting to run ' + current_model_name + ' model for scenario ' + current_scenario_name + '.')
        runner = ProcessingThread(current_args, self.root_app.args_queue.items()[0][0].split(' -- ', 1)[0],
                                  self.root_app, self)
        self.root_app.threads.append(runner)
        runner.start()

    def draw_scenario_model_pairs_gridlayout(self):
        try:
            self.scenario_model_pairs_gridlayout.setParent(None)
        except:
            LOGGER.debug('scenario_model_pairs_gridlayout Does not exist')
        self.scenario_model_pairs_gridlayout = QGridLayout()
        self.main_layout.addLayout(self.scenario_model_pairs_gridlayout)

        self.scenario_model_pairs_labels = []
        self.scenarios_in_run = self.root_app.scenarios_dock.scenarios_widget.get_checked_elements()
        self.models_in_run = self.root_app.models_dock.models_widget.get_checked_elements()
        for scenario in self.scenarios_in_run:
            for model in self.models_in_run:
                scenario_model_pair_string = scenario.name + ' - ' + model.name
                label = QLabel(scenario_model_pair_string)
                self.scenario_model_pairs_labels.append(label)
                self.scenario_model_pairs_gridlayout.addWidget(label)
        if len(self.scenarios_in_run) == 0 or len(self.models_in_run) == 0:
            label = QLabel('No scenario-model pairs found.\nSelect at least 1 scenario and 1 model before running.')
            self.scenario_model_pairs_labels.append(label)
            self.scenario_model_pairs_gridlayout.addWidget(label)

        self.main_layout.addWidget(QLabel(''))

        self.run_details_header_l = QLabel('Run details')
        self.run_details_header_l.setFont(config.minor_heading_font)
        self.main_layout.addWidget(self.run_details_header_l)

        self.run_scroll = ScrollWidget()
        self.main_layout.addWidget(self.run_scroll)
        self.run_scroll.scroll_layout.setAlignment(Qt.AlignTop)
        self.run_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.run_scroll.scroll_layout.setStretch(44, 1)

        self.run_details = QLabel('Ready to run.')
        self.run_scroll.scroll_layout.addWidget(self.run_details)

    def update_run_details(self, str_to_add, same_line=False):
        if same_line:
            new_text = str(self.run_details.text()) + str(str_to_add)
        else:
            new_text = str(self.run_details.text()) + '\n' + str(str_to_add)
        self.run_details.setText(new_text)
        self.output_scrollbar = self.run_scroll.scroll_area.verticalScrollBar()
        self.output_scrollbar.setValue(self.output_scrollbar.maximum())

    def run(self):
        """
        Main Entrance into iteratively running all combos of models
        """
        # Create a unique name based on input, or a modified version of the input if that name had already been used.
        name = str(self.parent.run_name_le.text())
        run_id = utilities.pretty_time()
        if name == '':
            name = 'run_at_' + run_id
        elif name in self.parent.elements:
            name = name + '_at_' + run_id

        args = self.root_app.model_runs_widget.create_default_element_args(name)
        args['run_id'] = run_id
        args['run_folder'] = os.path.join(self.root_app.project_folder, 'output/runs',
                                          name)  # self.parent.elements[run_name].run_folder
        args['scenarios_in_run'] = [i.name for i in self.scenarios_in_run]
        args['models_in_run'] = [i.name for i in self.models_in_run]
        self.parent.create_element(name, args)
        self.root_app.args_queue = OrderedDict()

        args = {}
        for scenario in self.scenarios_in_run:
            for model in self.models_in_run:
                if model.model_type == 'InVEST Model':
                    # Directory where archived json file is saved
                    setup_file_dir = os.path.join(
                        self.root_app.project_folder, 'output',
                        'model_setup_runs', model.name)

                    # Find the archive json file, load and grab arguments
                    for file in os.listdir(setup_file_dir):
                        if file.endswith('.json') and "archive" in file:
                            json_archive = open(os.path.join(setup_file_dir, file)).read()
                            archive_args = json.loads(json_archive)
                            args = archive_args["arguments"]
                            print args
                            break

                    args['workspace_dir'] = os.path.join(
                        self.parent.elements[name].run_folder, scenario.name, model.name)
                    if not os.path.isdir(args['workspace_dir']):
                        os.mkdirs(args['workspace_dir'])

                    if scenario.name != 'Baseline':
                        args = self.root_app.scenarios_dock.scenarios_widget.elements[
                            scenario.name].update_args_with_difference(args)

                if model.model_type == 'MESH Model':
                    setup_file_uri = os.path.join(self.root_app.project_folder, 'output/model_setup_runs', model.name,
                                                  model.name + '_setup_file.json')
                    args = utilities.file_to_python_object(setup_file_uri)
                    args['workspace_dir'] = os.path.join(self.parent.elements[name].run_folder, scenario.name,
                                                         model.name)

                    if scenario.name != 'Baseline':
                        args = self.root_app.scenarios_dock.scenarios_widget.elements[
                            scenario.name].update_args_with_difference(args)
                    self.root_app.args_queue.update({model.name + ' -- ' + scenario.name: args})

                # Got lazy and used string manupulation for splitting models from scenarios
                self.root_app.args_queue.update({model.name + ' -- ' + scenario.name: args})
        self.run_next_in_queue()

    def cancel(self):
        self.close()


class InstallPluginsDialog(MeshAbstractObject, QDialog):
    """
    Dialog (placeholder) for how plugins can be added.
    """
    def __init__(self, root_app=None, parent=None):
        super(InstallPluginsDialog, self).__init__(root_app, parent)
        self.plugin_folder = None

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle('Add plugins to MESH')
        self.title_l = QLabel('Add plugins to MESH')
        self.title_l.setFont(config.heading_font)
        self.main_layout.addWidget(self.title_l)

        self.main_layout.addWidget(QLabel())
        self.nyi_description_l = QLabel(
            'Automated installation of plugins is not yet implemented. In the short-term, plugins can be added manually by importing the plugin as a python module in the MESH source code. Models currently under development can be hosted on the \"Experimental Software\" section of the Natural Capital website.')
        self.nyi_description_l.setWordWrap(True)
        self.nyi_description_l.setFont(config.italic_font)
        self.main_layout.addWidget(self.nyi_description_l)
        self.main_layout.addWidget(QLabel())

        self.add_plugin_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.add_plugin_hbox)

        self.add_plugin_hbox.addWidget(QLabel('Add plugin by folder name'))
        self.plugin_path_le = QLineEdit()
        self.add_plugin_hbox.addWidget(self.plugin_path_le)

        self.select_folder_pb = QPushButton()
        #self.select_folder_pb.setMaximumWidth(32)
        self.select_folder_icon = QIcon(QPixmap('icons/document-open-7.png'))
        self.select_folder_pb.setIcon(self.select_folder_icon)
        self.add_plugin_hbox.addWidget(self.select_folder_pb)
        self.select_folder_pb.clicked.connect(self.select_folder)

        self.install_plugin_pb = QPushButton('Install')
        self.install_plugin_icon = QIcon(QPixmap('icons/emblem-package.png'))
        self.install_plugin_pb.setIcon(self.install_plugin_icon)
        self.add_plugin_hbox.addWidget(self.install_plugin_pb)
        self.install_plugin_pb.clicked.connect(self.install_plugin)

        self.main_layout.addWidget(QLabel())
        self.main_layout.addWidget(QLabel('Currently installed plugins:'))

        self.scroll_widget = ScrollWidget(self.root_app, self)
        self.scroll_widget.scroll_layout.setAlignment(Qt.AlignTop)
        self.main_layout.addWidget(self.scroll_widget)
        self.scroll_widget.setMinimumSize(800, 700)

        for plugin in self.root_app.models_dock.models_widget.elements:
            self.scroll_widget.scroll_layout.addWidget(QLabel(plugin))


        self.show()

    def select_folder(self):
        self.plugin_folder = str(QFileDialog.getExistingDirectory(self, 'Select plugin\'s folder', 'plugins'))
        self.plugin_path_le.setText(self.plugin_folder)


    def install_plugin(self):
        # TODO JUSTIN NYI
        self.scroll_widget.scroll_layout.addWidget(QLabel('Not yet implemented.'))


class CreateBaselineDataDialog(MeshAbstractObject, QDialog):
    """
    Dialog (placeholder) for how plugins can be added.
    """
    # NEXT RELEASE I have a deep conceptual problem insofar as not all data that would have generators are baseline. How, for instance, would the Scenario generator know to create it's own transition_table.csv?
    def __init__(self, root_app=None, parent=None):
        super(CreateBaselineDataDialog, self).__init__(root_app, parent)
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.setWindowTitle('Create Baseline Data')
        self.title_l = QLabel('Create baseline data for selected models')
        self.title_l.setFont(config.heading_font)
        self.main_layout.addWidget(self.title_l)

        self.main_layout.addWidget(QLabel())
        self.subtitle_l = QLabel(
            'The table below shows the which datasets are required to run the models you selected. Click the PLUS icon to create the data.')
        self.subtitle_l.setWordWrap(True)
        self.subtitle_l.setFont(config.italic_font)
        self.main_layout.addWidget(self.subtitle_l)
        self.main_layout.addWidget(QLabel())

        self.scroll_widget = ScrollWidget(self.root_app, self)
        self.main_layout.addWidget(self.scroll_widget)
        self.scroll_widget.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_widget.setMinimumSize(800, 700)

        self.root_app.project_aoi
        checked_models = self.root_app.models_dock.models_widget.get_checked_elements()
        if checked_models and self.root_app.project_aoi:
            self.required_l = QLabel('Required Inputs')
            self.required_l.setFont(config.minor_heading_font)
            self.scroll_widget.scroll_layout.addWidget(self.required_l)

            self.required_model_headers = OrderedDict()
            self.required_specify_buttons = OrderedDict()
            for model in checked_models:
                self.scroll_widget.scroll_layout.addWidget(QLabel(''))
                self.required_model_headers[model.name] = QLabel(model.long_name)
                self.required_model_headers[model.name].setFont(config.bold_font)
                self.scroll_widget.scroll_layout.addWidget(self.required_model_headers[model.name])

                self.input_mapping_uri = os.path.join('../settings/default_setup_files',
                                                      model.name + '_input_mapping.csv')
                input_mapping = utilities.file_to_python_object(self.input_mapping_uri)
                for key, value in input_mapping.items():
                    if utilities.convert_to_bool(value['required']):
                        self.required_specify_buttons[value['name']] = NamedSpecifyButton(value['name'], value,
                                                                                          specify_function=self.create_data_from_args,
                                                                                          root_app=self.root_app,
                                                                                          parent=self)
                        self.scroll_widget.scroll_layout.addWidget(self.required_specify_buttons[value['name']])

            self.scroll_widget.scroll_layout.addWidget(QLabel(''))
            self.scroll_widget.scroll_layout.addWidget(QLabel(''))
            self.optional_l = QLabel('Optional Inputs')
            self.optional_l.setFont(config.minor_heading_font)
            self.scroll_widget.scroll_layout.addWidget(self.optional_l)

            self.optional_model_headers = OrderedDict()
            self.optional_specify_buttons = OrderedDict()
            for model in checked_models:
                self.scroll_widget.scroll_layout.addWidget(QLabel(''))
                self.optional_model_headers[model.name] = QLabel(model.long_name)
                self.optional_model_headers[model.name].setFont(config.bold_font)
                self.scroll_widget.scroll_layout.addWidget(self.optional_model_headers[model.name])

                self.input_mapping_uri = os.path.join('../settings/default_setup_files',
                                                      model.name + '_input_mapping.csv')
                input_mapping = utilities.file_to_python_object(self.input_mapping_uri)

                for key, value in input_mapping.items():
                    if not utilities.convert_to_bool(value['required']):
                        self.optional_specify_buttons[value['name']] = NamedSpecifyButton(value['long_name'],
                                                                                          specify_function=self.create_data_from_args,
                                                                                          root_app=self.root_app,
                                                                                          parent=self)
                        self.scroll_widget.scroll_layout.addWidget(self.optional_specify_buttons[value['name']])
        else:
            if not self.root_app.project_aoi:
                self.no_aoi_selected_l = QLabel('No Area of Interest selected. Specify AOI before creating data.')
                self.no_aoi_selected_l.setFont(config.minor_heading_font)
                self.scroll_widget.scroll_layout.addWidget(self.no_aoi_selected_l)

            if not checked_models:
                self.no_models_selected_l = QLabel('No models selected. Select models before creating data.')
                self.no_models_selected_l.setFont(config.minor_heading_font)
                self.scroll_widget.scroll_layout.addWidget(self.no_models_selected_l)

        self.show()

    def create_data_from_args(self, args):
        save_location = os.path.join(
            self.root_app.project_folder, args['save_location'])
        default_value = os.path.join(
            self.root_app.base_data_folder, args['default_value'])
        # save_location = args['save_location']
        if args['load_method'] == 'copy_default':
            data_creation.copy_from_base_data(default_value, save_location)
        if args['load_method'] == 'clip_from_global':
            data_creation.clip_geotiff_from_base_data(self.root_app.project_aoi, default_value, save_location)
        self.root_app.scenarios_dock.scenarios_widget.elements['Baseline'].load_element(save_location, save_location)
        self.root_app.statusbar.showMessage('Data created and saved to ' + save_location + '.')


class ConfigureBaseDataDialog(MeshAbstractObject, QDialog):
    """
    Choose where to set base_data folder and give info on how to download data if not yet available.
    """
    def __init__(self, root_app=None, parent=None):
        super(ConfigureBaseDataDialog, self).__init__(root_app, parent)
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.setMinimumWidth(650)

        self.setWindowTitle('Configure Base Data')
        self.title_l = QLabel('You need to obtain or configure your base data')
        self.title_l.setFont(config.heading_font)
        self.main_layout.addWidget(self.title_l)

        self.main_layout.addWidget(QLabel())
        self.subtitle_l = QLabel(
            'MESH creates data for your project from global base data. Configure that base data here.')
        self.subtitle_l.setWordWrap(True)
        self.subtitle_l.setFont(config.italic_font)
        self.main_layout.addWidget(self.subtitle_l)
        self.main_layout.addWidget(QLabel())

        self.download_data_l = QLabel('When you installed MESH, you should have downloaded or made a local version of the MESH Base Data.  '
                                      'By default, this folder is installed at <your mesh root directory>/base_data. If you do not have the base data, '
                                      'go to the Natural Capital Project forum, Experimental Software section to find a link to the latest download link. '
                                      ' Once you have the data, put the base_data folder in your mesh root directory as specified above. The dataset only works if '
                                      'it is in exactly the right location, so that for instance the default land-use, land-cover map is located at (for example) '
                                      'C:/mesh/base_data/lulc/lulc_modis_2012.tif.'

                                      )
        self.download_data_l.setWordWrap(True)
        self.main_layout.addWidget(self.download_data_l)

        self.set_base_data_folder_decription_l = QLabel('If you would like to change where the data is located (perhaps to an external hard-drive), '
                                                        ', click \'Select Folder.\ and then save and restart MESH.'
                                                        '\n')
        self.set_base_data_folder_decription_l.setWordWrap(True)
        self.main_layout.addWidget(self.set_base_data_folder_decription_l)

        self.buttons_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.buttons_hbox)

        self.set_folder_to_default_pb = QPushButton('Set folder to default')
        self.set_folder_to_default_pb.clicked.connect(self.set_folder_to_default)
        self.buttons_hbox.addWidget(self.set_folder_to_default_pb)

        self.select_folder_pb = QPushButton('Select folder')
        self.select_folder_pb.clicked.connect(self.select_folder)
        self.buttons_hbox.addWidget(self.select_folder_pb)


        self.show()

    def set_folder_to_default(self):
        self.root_app.base_data_folder = '../base_data'
        self.root_app.save_application_settings()
        self.close()

    def select_folder(self):
        self.root_app.base_data_folder = str(QFileDialog.getExistingDirectory(self, 'Select folder', self.root_app.project_folder))
        self.root_app.save_application_settings()
        self.close()

class DefineDecisionContextDialog(MeshAbstractObject, QDialog):
    """
    Choose where to set base_data folder and give info on how to download data if not yet available.
    """
    def __init__(self, root_app=None, parent=None):
        super(DefineDecisionContextDialog, self).__init__(root_app, parent)

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.setWindowTitle('Define Decision Context')
        self.title_l = QLabel('Define the options, drivers and timeframe of your decision')
        self.title_l.setFont(config.heading_font)
        self.main_layout.addWidget(self.title_l)
        self.main_layout.addWidget(QLabel())

        self.add_decision_option_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.add_decision_option_hbox)
        self.add_decision_option_pb = QPushButton('Add decision option')
        self.add_decision_option_icon = QIcon(QPixmap('icons/document-properties.png'))
        self.add_decision_option_pb.setIcon(self.add_decision_option_icon)
        self.add_decision_option_pb.setMaximumWidth(250)
        self.add_decision_option_pb.clicked.connect(self.add_decision_option)
        self.add_decision_option_hbox.addWidget(self.add_decision_option_pb)
        self.add_decision_option_description_l = QLabel('Choose a name for one of the decisions being considered, e.g. reforestation, business-as-usual, agricultural expansion.')
        self.add_decision_option_description_l.setWordWrap(True)
        self.add_decision_option_hbox.addWidget(self.add_decision_option_description_l)


        self.define_external_driver_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.define_external_driver_hbox)
        self.define_external_driver_pb = QPushButton('Define external driver')
        self.define_external_driver_icon = QIcon(QPixmap('icons/office-chart-area.png'))
        self.define_external_driver_pb.setIcon(self.define_external_driver_icon)
        self.define_external_driver_pb.setMaximumWidth(250)
        self.define_external_driver_pb.clicked.connect(self.define_external_driver)
        self.define_external_driver_hbox.addWidget(self.define_external_driver_pb)
        self.define_external_driver_description_l = QLabel('Define any external drivers that might affect your decision, e.g. climate change, price changes.')
        self.define_external_driver_description_l.setWordWrap(True)
        self.define_external_driver_hbox.addWidget(self.define_external_driver_description_l)


        self.add_assessment_time_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.add_assessment_time_hbox)
        self.add_assessment_time_pb = QPushButton('Add assessment time')
        self.add_assessment_time_icon = QIcon(QPixmap('icons/edit-clear-history-3.png'))
        self.add_assessment_time_pb.setIcon(self.add_assessment_time_icon)
        self.add_assessment_time_pb.setMaximumWidth(250)
        self.add_assessment_time_pb.clicked.connect(self.add_assessment_time)
        self.add_assessment_time_hbox.addWidget(self.add_assessment_time_pb)
        self.add_assessment_time_description_l = QLabel('Specify which moments in time you want to assess the outcomes of your decision, e.g. 2010, 2015, 2020.')
        self.add_assessment_time_description_l.setWordWrap(True)
        self.add_assessment_time_hbox.addWidget(self.add_assessment_time_description_l)

        self.main_layout.addWidget(QLabel())

        self.use_these_pathways_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.use_these_pathways_hbox)
        self.use_these_pathways_pb = QPushButton('Use these pathways')
        self.use_these_pathways_icon = QIcon(QPixmap('icons/crab16.png'))
        self.use_these_pathways_pb.setIcon(self.use_these_pathways_icon)
        self.use_these_pathways_pb.setMaximumWidth(250)
        self.use_these_pathways_pb.clicked.connect(self.use_these_pathways)
        self.use_these_pathways_hbox.addWidget(self.use_these_pathways_pb)

        self.clear_pathways_pb = QPushButton('Clear pathways')
        self.clear_pathways_icon = QIcon(QPixmap('icons/dialog-cancel-2.png'))
        self.clear_pathways_pb.setIcon(self.clear_pathways_icon)
        self.clear_pathways_pb.setMaximumWidth(250)
        self.clear_pathways_pb.clicked.connect(self.clear_pathways)
        self.use_these_pathways_hbox.addWidget(self.clear_pathways_pb)






        self.scroll_widget = ScrollWidget(self.root_app, self)
        self.main_layout.addWidget(self.scroll_widget)
        self.scroll_widget.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_widget.setMinimumSize(800, 700)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabel(QString('Decision Contexts'))
        self.scroll_widget.scroll_layout.addWidget(self.tree)

        self.show()

    def add_decision_option(self):
        input_text, ok = QInputDialog.getText(self, 'Add decision', 'Name of decision option:')
        if ok:
            name = str(input_text)
            tree_item = QTreeWidgetItem()
            self.root_app.decision_contexts[name] = tree_item
            self.root_app.external_drivers[name] = OrderedDict()



            tree_item.setText(0, QString(name))
            self.tree.addTopLevelItem(tree_item)

    def define_external_driver(self):
        input_text, ok = QInputDialog.getText(self, 'Add external driver', 'Name of external driver:')
        if ok:
            for decision_option_name, decision_option_item in self.root_app.decision_contexts.items():
                name = str(input_text)
                tree_item = QTreeWidgetItem()
                tree_item.setText(0, QString(name))
                self.root_app.external_drivers[decision_option_name][name] = tree_item
                decision_option_item.addChild(tree_item)


    def add_assessment_time(self):
        input_text, ok = QInputDialog.getText(self, 'Add assessment time', 'Add assessment time moment')
        if ok:
            name = str(input_text)
            for decision_option_name, decision_option_dict in self.root_app.external_drivers.items():
                # self.root_app.assessment_times[decision_option_name] = OrderedDict()
                # self.root_app.assessment_times[decision_option_name][driver_name] = OrderedDict()
                for driver_name, driver_item in decision_option_dict.items():
                    name = str(input_text)
                    tree_item = QTreeWidgetItem()
                    tree_item.setText(0, QString(name))

                    # [name] = tree_item
                    driver_item.addChild(tree_item)


    def create_data_from_args(self, args):
        save_location = os.path.join(
            self.root_app.project_folder, args['save_location'])
        default_value = os.path.join(
            self.root_app.base_data_folder, args['default_value'])
        # save_location = args['save_location']
        if args['load_method'] == 'copy_default':
            data_creation.copy_from_base_data(default_value, save_location)
        if args['load_method'] == 'clip_from_global':
            data_creation.clip_geotiff_from_base_data(self.root_app.project_aoi, default_value, save_location)
        self.root_app.scenarios_dock.scenarios_widget.elements['Baseline'].load_element(save_location, save_location)
        self.root_app.statusbar.showMessage('Data created and saved to ' + save_location + '.')

    def use_these_pathways(self):
        root = self.tree.invisibleRootItem()
        child_count = root.childCount()
        for i in range(child_count):
            self.root_app.scenarios_dock.scenarios_widget.create_element(str(root.child(i).text(0)))

    def clear_pathways(self):
        root = self.tree.invisibleRootItem()
        child_count = root.childCount()
        for i in range(child_count):
            item = root.child(i)
            root.removeChild(item)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mesh_app = MeshApplication()
    mesh_app.show()

    sys.exit(app.exec_())
