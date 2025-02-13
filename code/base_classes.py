# coding=utf-8

import sys
import time
from collections import OrderedDict
import os

from PyQt4.QtGui import *
from PyQt4.QtCore import *

from natcap.invest.iui import modelui
from natcap.invest.hydropower.hydropower_water_yield import execute as execute_hydropower_model
from natcap.invest.ndr.ndr import execute as execute_nutrient_model
# from natcap.invest.carbon.carbon_combined import execute as execute_carbon_model
from natcap.invest.carbon import execute as execute_carbon_model
from natcap.invest.pollination.pollination import execute as execute_pollination_model
from natcap.invest.sdr import execute as execute_sdr_model
from natcap.invest.crop_production.crop_production import execute as execute_crop_production_model # NOTE Inconsistent double naming here.
from natcap.invest.globio import execute as execute_globio

from mesh_models.nutritional_adequacy import execute as execute_nutritional_adequacy_model


class ProcessingThread(QThread):
    """
    CPU intensive operations are called as separate processing threads to not lock
    down the UI when running a model. Inherits QT's QThread class to enable easy threading.
    Next steps will be to switch this framing to a multicore processing paradigm.
    """
    def __init__(self, args, model_name, root_app, parent, json_file_name=None):
        QThread.__init__(self)
        self.args = args
        self.stopped = False
        self.model_name = model_name
        self.root_app = root_app
        self.parent = parent
        self.json_file_name = json_file_name
        if hasattr(self.parent, 'listener'):
        # if isinstance(self.parent.listener, Listener):
            self.parent.listener.connect_slots(self)
        sys.excepthook(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]) # Required to have the logger/IDE pick up error messages from other threads.

    def run(self):
        try:
            if self.model_name == 'ndr':
                self.update_run_log('\nStarting Delivery Ratio Model.')
                execute_nutrient_model(self.args)
                self.update_run_log('Finished Nutrient Retention Model.')
            if self.model_name == 'hydropower_water_yield':
                self.update_run_log('\nStarting Water Yield Model.')
                execute_hydropower_model(self.args)
                self.update_run_log('Finished Water Yield Model.')
            if self.model_name == 'carbon':
                self.update_run_log('\nStarting Carbon Model.')
                execute_carbon_model(self.args)
                self.update_run_log('Finished Carbon Model.')
            if self.model_name == 'pollination':
                self.update_run_log('\nStarting Pollination Model.')
                execute_pollination_model(self.args)
                self.update_run_log('Finished Pollination Model.')
            if self.model_name == 'sdr':
                self.update_run_log('\nStarting Sediment Delivery Ratio Model.')
                execute_sdr_model(self.args)
                self.update_run_log('Finished Sediment Delivery Ratio Model.')
            if self.model_name == 'crop_production':
                self.update_run_log('\nStarting Crop Production Model.')
                execute_crop_production_model(self.args)
                self.update_run_log('Finished Crop Production Model.')
            if self.model_name == 'globio':
                self.update_run_log('\nStarting Globio Model.')
                execute_globio(self.args)
                self.update_run_log('Finished Globio Model.')
            if self.model_name == 'nutritional_adequacy':
                self.update_run_log('\nStarting Nutritional Adequacy Model.')
                execute_nutritional_adequacy_model(self.args, self) # NOTE different importing of self
                self.update_run_log('Finished Nutritional Adequacy Model.')

            self.emit_finished()
        except:
            (type_, value, traceback) = sys.exc_info()
            sys.excepthook(type_, value, traceback) # Required to have the logger/IDE pick up error messages from other threads.

    def update_run_log(self, to_update):
        self.parent.update_run_details(str(to_update))

    def emit_finished(self):
        self.emit(SIGNAL('model_finished'))

    def stop(self):
        self.stopped = True
        try:
            self.timer_thread.stop()
        except:
            'not needed'


class Listener(QThread):
    def __init__(self, root_app, parent):
        super(Listener,self).__init__()
        self.root_app = root_app
        self.parent = parent

    def connect_slots(self, sender):
        self.connect(sender, SIGNAL('model_finished'), self.process_model_finished_signal)

    def process_model_finished_signal(self):
        self.root_app.visible_central_widget_name = 'model_runs'
        self.root_app.args_queue.popitem(last=False)  # removes the first item, last=False sets it to be First In First out rather than Last In First Out
        if len(self.root_app.args_queue) > 0:
            self.parent.run_next_in_queue() # Feels awkward
        else:
            self.parent.update_run_details('\n\nAll scenario model pairs finished!')
        self.root_app.update_ui()


class MeshAbstractObject(object):
    """
    Provides global attributes and the skeleton of all other objects in this program. Is never called directly.
    """
    def __init__(self, root_app=None, parent=None):
        super(MeshAbstractObject, self).__init__()
        if root_app:
            self.root_app = root_app
        if parent:
            self.parent = parent


class ScrollWidget(MeshAbstractObject, QWidget):
    """
    A base class for any Widget class that needs to scroll. Anything to be added to the scrollable area should be
    added to the layout self.scroll_laayout
    """
    def __init__(self, root_app=None, parent=None):
        super(ScrollWidget, self).__init__(root_app, parent)
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(0)
        self.main_layout.setMargin(0)

        # Scroll area
        self.scroll_area = QScrollArea()  # It is necessary to create a scroll area widget seperate from the scroll widget. Not sure why.
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumSize(QSize(16, 38))
        self.main_layout.addWidget(self.scroll_area)  # an area is a type of widget required for scroll areas

        self.scroll_layout = QVBoxLayout()
        self.scroll_layout.setSpacing(8)
        self.scroll_layout.setContentsMargins(9, 8, 9, 0)  # Left, top, right, bottom

        self.scroll_widget = QWidget()
        self.scroll_widget.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.scroll_widget)

        self.setLayout(self.main_layout)


class InputSelector(MeshAbstractObject, QWidget):
    """
    Provides a line edit box with the option of clicking an icon to populate it with the file selector
    """
    def __init__(self, name, root_app=None, parent=None, input_type='file'):
        super(InputSelector, self).__init__(root_app, parent)

        self.name = name
        self.uri = ''
        self.input_type = input_type

        self.main_layout = QHBoxLayout()
        self.main_layout.setMargin(0)
        self.setLayout(self.main_layout)

        # self.name_l = QLabel(self.name)
        # self.main_layout.addWidget(self.name_l)
        self.le = QLineEdit()
        self.main_layout.addWidget(self.le)
        if self.input_type == 'file' or self.input_type == 'folder':
            self.select_file_pb = QPushButton()
            self.select_file_icon = QIcon(QPixmap('icons/document-open.png'))
            self.select_file_pb.setIcon(self.select_file_icon)
            self.select_file_pb.connect(self.select_file_pb, SIGNAL("clicked()"), self.select_file)
            #self.select_file_pb.clicked.connect(self.select_file)
            #self.select_file_pb.connect(self.bn, SIGNAL("clicked()")
            self.select_file_pb.setMaximumWidth(32)
            self.main_layout.addWidget(self.select_file_pb)

    def select_file(self):
        if self.input_type == 'file':
            file_uri = str(QFileDialog.getOpenFileName(self, 'Select file', self.root_app.project_folder))
        elif self.input_type == 'folder':
            file_uri = str(QFileDialog.getExistingDirectory(self, 'Select folder', self.root_app.project_folder))
        else:
            raise NameError('Unexpected outcome of InputSelector')

        self.le.setText(file_uri)

    def set_input(self, input_str):
        self.le.setText(input_str)

    def get_input(self):
        return str(self.le.text())


class NamedSpecifyButton(MeshAbstractObject, QWidget):
    """
    Provides a line edit box with the option of clicking an icon to populate it with the file selector
    """
    def __init__(self, name, args=None, specify_function=None, root_app=None, parent=None, input_type='file'):
        super(NamedSpecifyButton, self).__init__(root_app, parent)

        self.name = name

        if args:
            self.args = args
            self.long_name = args['long_name']
        else:
            self.args = OrderedDict()
            self.long_name = self.name

        if specify_function:
            self.specify_function = specify_function
        else:
            self.specify_function = self.default_specify_function

        self.main_layout = QHBoxLayout()
        self.main_layout.setMargin(0)
        self.setLayout(self.main_layout)

        self.long_name_l = QLabel(self.long_name)
        self.main_layout.addWidget(self.long_name_l)

        self.main_layout.addItem(QSpacerItem(0, 0, QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))

        self.create_data_l = QLabel('Create data and link to baseline')
        self.main_layout.addWidget(self.create_data_l)

        self.specify_pb = QPushButton()
        self.specify_pb.setObjectName(self.name)
        self.specify_icon = QIcon()
        plus_icon_path = os.path.join('icons', 'plus.png')
        self.specify_icon.addPixmap(QPixmap(plus_icon_path), QIcon.Normal, QIcon.Off)
        self.specify_pb.setIcon(self.specify_icon)
        #self.specify_pb.setMaximumWidth(32)
        self.specify_pb.connect(self.specify_pb, SIGNAL("clicked()"), self.process_click)
        self.main_layout.addWidget(self.specify_pb)

    def process_click(self):
        self.specify_function(self.args)

    def default_specify_function(self):
        input_text, ok = QInputDialog.getText(self, 'Specify text', 'Text:')
        if ok:
            text = str(input_text)


class InformationButton(QPushButton):
    """This class represents the information that a user will see when pressing
        the information button.  This specific class simply represents an object
        that has a couple of string attributes that may be changed at will, and
        then constructed into a cohesive string by calling self.build_contents.

        Note that this class supports the presentation of an error message.  If
        the error message is to be shown to the end user, it must be set after
        the creation of the InformationPopup instance by calling
        self.set_error().
        """
    def __init__(self, title, body_text=''):
        """This function initializes the InformationPopup class.
            title - a python string.  The title of the element.
            body_text - a python string.  The body of the text

            returns nothing."""

        QPushButton.__init__(self)
        self.title = title
        self.body_text = body_text
        self.pressed.connect(self.show_info_popup)
        self.setFlat(True)
        self.setIcon(QIcon(os.path.join('icons', 'info.png')))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # If the user has set "helpText": null in JSON, deactivate.
        if body_text == None:
            self.deactivate()

    def show_info_popup(self):
        """Show the information popup.  This manually (programmatically) enters
            What's This? mode and spawns the tooltip at the location of trigger,
            the element that triggered this function.
            """

        self.setWhatsThis(self.build_contents())  # set popup text
        QWhatsThis.enterWhatsThisMode()
        QWhatsThis.showText(self.pos(), self.whatsThis(), self)

    def deactivate(self):
        """Visually disable the button: set it to be flat, disable it, and clear
            its icon."""
        self.setFlat(True)
        self.setEnabled(False)
        self.setIcon(QIcon(''))

    def set_title(self, title_text):
        """Set the title of the InformationPopup text.  title_text is a python
            string."""
        self.title = title_text

    def set_body(self, body_string):
        """Set the body of the InformationPopup.  body_string is a python
            string."""
        self.body_text = body_string

    def build_contents(self):
        """Take the python string components of this instance of
            InformationPopup, wrap them up in HTML as necessary and return a
            single string containing HTML markup.  Returns a python string."""
        width_table = '<table style="width:400px"></table>'
        title = '<h3 style="color:black">%s</h3><br/>' % (self.title)
        body = '<div style="color:black">%s</div>' % (self.body_text)

        return title + body + width_table