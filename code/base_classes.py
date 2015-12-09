# coding=utf-8

import sys
import time
from collections import OrderedDict

from PyQt4.QtGui import *
from PyQt4.QtCore import *

from invest_natcap.iui import modelui
from invest_natcap.hydropower.hydropower_water_yield import execute as execute_hydropower_model
from invest_natcap.nutrient.nutrient import execute as execute_nutrient_model
from invest_natcap.carbon.carbon_combined import execute as execute_carbon_model
from invest_natcap.pollination.pollination import execute as execute_pollination_model
from invest_natcap.sdr.sdr import execute as execute_sdr_model

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

        self.parent.listener.connect_slots(self)


        sys.excepthook(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]) # Required to have the logger/IDE pick up error messages from other threads.

    def run(self):
        try:
            # SHORTCUT I only instantiated this subset of models and i did it non-programatically with horrible horrible hard-coding..
            # BUG Critical. If you run InVEST as a setup model, and then without closing MESH, run the full model, the tmpfile module
            # in InVEST throws an Errno2. This may be a threading issue?

            if self.model_name == 'nutrition':
                self.update_run_log('Starting Food Security and Nutrition Model.')
                nutrition.execute(self.args, self)
                self.update_run_log('Finished Food Security and Nutrition Model.')
            if self.model_name == 'nutrient':
                self.update_run_log('Starting Nutrient Retention Model.')
                execute_nutrient_model(self.args)
                self.update_run_log('Finished Nutrient Retention Model.')
            if self.model_name == 'hydropower_water_yield':
                self.update_run_log('Starting Water Yield Model.')
                execute_hydropower_model(self.args)
                self.update_run_log('Finished Water Yield Model.')
            if self.model_name == 'carbon_combined':
                self.update_run_log('Starting Carbon Model.')
                print 'self.args', self.args
                execute_carbon_model(self.args)
                self.update_run_log('Finished Carbon Model.')
            if self.model_name == 'pollination':
                self.update_run_log('Starting Pollination Model.')
                execute_pollination_model(self.args)
                self.update_run_log('Finished Pollination Model.')
            if self.model_name == 'sdr':
                self.update_run_log('Starting Sediment Delivery Ratio Model.')
                execute_sdr_model(self.args)
                self.update_run_log('Finished Sediment Delivery Ratio Model.')

            # This one is different because it's not calling the python library bu tthe fulll modelui iui file.
            if self.model_name == 'scenario_generator':
                modelui.main(self.json_file_name, last_run_override=self.args)

            self.emit_finished()
        except:
            (type_, value, traceback) = sys.exc_info()
            sys.excepthook(type_, value, traceback) # Required to have the logger/IDE pick up error messages from other threads.

    def update_run_log(self, to_update):
        self.parent.update_run_details(str(to_update))

    def emit_finished(self):
        self.emit(SIGNAL('model_finished'))


    # def send_finish_message(self):
    #     self.emit('finished')
        # try:
        #     self.parent.args_queue.popitem(last=False)  # removes the first item, last=False sets it to be First In First out rather than Last In First Out
        #     if len(self.parent.args_queue) > 0:
        #         self.parent.run_next_in_queue()
        # except:
        #     'Probably was not called as an args_queue item'
        # self.root_app.model_runs_widget.process_finish_message(self.model_name)
        # ATTEMPTED FAILURE self.parent.process_finish_messages(self.model_name)

    def stop(self):
        self.stopped = True
        try:
            self.timer_thread.stop()
        except:
            'not needed'


class TimerThread(QThread):
    """
    Can be used to update the UI according to time. NYI fully.
    """

    # TODO SHORTCUT Rather than learn how threads were implemented in IUI, I just use the timer thread here to check if a file
    # exists in the OS rather than have a proper "model finished" message sent.

    def __init__(self, root_app=None, parent=None):
        sys.excepthook(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]) # Required to have the logger/IDE pick up error messages from other threads.

        QThread.__init__(self)
        self.root_app = root_app
        self.parent = parent
        self.stopped = False

    def run(self):
        while not self.stopped:
            self.root_app.update_ui()

            time.sleep(.2)

    def stop(self):
        self.stopped = True

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

        # try:
        #     self.root_app.args_queue.popitem(last=False)  # removes the first item, last=False sets it to be First In First out rather than Last In First Out
        #     if len(self.root_app.args_queue) > 0:
        #         self.parent.run_next_in_queue() # Feels awkward
        # except:
        #     print('Probably was not called as an args_queue item')
        #     raise

        self.root_app.update_ui()
#
# class Sender(QThread):
#     def __init__(self):
#         super(Sender,self).__init__()
#
#     def emit_finished(self):
#         self.emit(SIGNAL('model_finished'))
#





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
            raise

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
        self.specify_icon.addPixmap(QPixmap('icons/plus.ico'), QIcon.Normal, QIcon.Off)
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
            print('Text inputed: ' + text)


