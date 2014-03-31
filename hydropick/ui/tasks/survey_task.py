#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

from __future__ import absolute_import

import os
import logging

from traits.api import (Bool, Property, Supports, List, on_trait_change, Dict,
                        Str, Instance)

from pyface.api import ImageResource
from pyface.tasks.api import Task, TaskLayout, PaneItem, VSplitter, HSplitter
from pyface.tasks.action.api import DockPaneToggleGroup, SMenuBar, SMenu, \
    SGroup, SToolBar, TaskAction, CentralPaneAction
from apptools.undo.i_undo_manager import IUndoManager
from apptools.undo.i_command_stack import ICommandStack

from ...model.i_survey import ISurvey
from ...model.i_survey_line import ISurveyLine
from ...model.survey_line import SurveyLine
from ...model.i_survey_line_group import ISurveyLineGroup
from ...model import algorithms
from ...ui.survey_data_session import SurveyDataSession

from .task_command_action import TaskCommandAction

logger = logging.getLogger(__name__)

class SurveyTask(Task):
    """ A task for viewing and editing hydrological survey data """

    #### Task interface #######################################################

    id = 'hydropick.survey_task'
    name = 'Survey Editor'

    #### SurveyTask interface #################################################

    # XXX perhaps bundle the survey specific things into survey manager object?

    #: the survey object that we are viewing
    survey = Supports(ISurvey)

    #: the currently active survey line group
    current_survey_line_group = Supports(ISurveyLineGroup)

    #: the currently active survey line that we are viewing
    current_survey_line = Supports(ISurveyLine)# Instance(SurveyLine)#

    # data object for maninpulating data for survey view and depth lines
    current_data_session = Instance(SurveyDataSession)

    #: the selected survey lines
    selected_survey_lines = List(Supports(ISurveyLine))

    #: reference to dictionary of available depth pic algorithms
    # (IAlgorithm Classes)
    algorithms = Dict

    # selected depth line
    selected_depth_line_name = Str

    # traits for managing Action state ########################################

    #: whether the undo stack is "clean"
    dirty = Property(Bool, depends_on='command_stack.clean')

    #: whether or not there are selected lines
    have_selected_lines = Property(Bool, depends_on='selected_survey_lines')

    #: whether or not there is a current group
    have_current_group = Property(Bool, depends_on='current_survey_line_group')

    #: whether or not there is a current survey
    have_survey = Property(Bool, depends_on='survey')

    #: the object that manages Undo/Redo stacks
    undo_manager = Supports(IUndoManager)

    #: the object that holds the Task's commands
    command_stack = Supports(ICommandStack)

    # refernce to this action so that the checked trait can be easily monitored
    zoom_box_action = Instance(CentralPaneAction)

    # refernce to this action so that the checked trait can be easily monitored
    move_legend_action = Instance(CentralPaneAction)

    msg_string = Str

    ###########################################################################
    # 'Task' interface.
    ###########################################################################
    def _zoom_box_action_default(self):
        ''' need to make this a trait to have access to action.checked state
        '''
        action = CentralPaneAction(name='Zoom Box (press "z")',
                                   method='on_zoom_box',
                                   image=ImageResource("magnifier-zoom-fit"),
                                   style='toggle',
                                   enabled_name='show_view')
        return action

    def _move_legend_action_default(self):
        ''' need to make this a trait to have access to action.checked state
        '''
        action = CentralPaneAction(name='disable pan - move legend',
                                   method='on_move_legend',
                                   image=ImageResource("application-export"),
                                   style='toggle',
                                   enabled_name='show_view')
        return action

    def _default_layout_default(self):
        return TaskLayout(left=VSplitter(PaneItem('hydropick.survey_data'),
                                         PaneItem('hydropick.survey_map'),
                                         PaneItem('hydropick.survey_depth_line'),
                                         )
                          )

    def _menu_bar_default(self):
        from apptools.undo.action.api import UndoAction, RedoAction
        menu_bar = SMenuBar(
            SMenu(
                SGroup(
                    TaskAction(name="Import", method='on_import', accelerator='Ctrl+I'),
                    id='New', name='New'
                ),
                SGroup(
                    TaskAction(name="Open", method='on_open', accelerator='Ctrl+O'),
                    id='Open', name='Open'
                ),
                SGroup(
                    TaskAction(name="Load Pic File", method='on_load_pic_file',
                               enabled_name='have_survey'),
                    id='LoadPic', name='Load Pic File'
                ),
                SGroup(
                    TaskAction(name="Load Corestick File", method='on_load_corestick',
                               enabled_name='have_survey'),
                    id='LoadCore', name='Load Corestick File'
                ),
                SGroup(
                    TaskAction(name="Save", method='on_save', accelerator='Ctrl+S',
                               enabled_name='dirty'),
                    TaskAction(name="Save As...", method='on_save_as',
                               accelerator='Ctrl+Shift+S', enabled_name='have_survey'),
                    id='Save', name='Save'
                ),
                id='File', name="&File",
            ),
            SMenu(
                # XXX can't integrate easily with TraitsUI editors :P
                SGroup(
                    UndoAction(undo_manager=self.undo_manager, accelerator='Ctrl+Z'),
                    RedoAction(undo_manager=self.undo_manager, accelerator='Ctrl+Shift+Z'),
                    id='UndoGroup', name="Undo Group",
                ),
                SGroup(
                    TaskCommandAction(name='New Group', method='on_new_group',
                                      accelerator='Ctrl+Shift+N',
                                      enabled_name='have_survey',
                                      command_stack_name='command_stack'),
                    TaskCommandAction(name='Delete Group',
                                      method='on_delete_group',
                                      accelerator='Ctrl+Delete',
                                      enabled_name='have_current_group',
                                      command_stack_name='command_stack'),
                    TaskAction(name='Replace Group with Selected',
                               method='on_replace_group',
                               enabled_name='have_current_group'),
                    id='LineGroupGroup', name="Line Group Group",
                ),
                id='Edit', name="&Edit",
            ),
            SMenu(
                SGroup(
                    TaskAction(name='Next Line',
                               method='on_next_line',
                               enabled_name='survey.survey_lines',
                               accelerator='Ctrl+Right'),
                    TaskCommandAction(name='Previous Line',
                               method='on_previous_line',
                               enabled_name='survey.survey_lines',
                               accelerator='Ctrl+Left'),
                    id='LineGroup', name='Line Group',
                ),
                SGroup(
                    CentralPaneAction(name='Location Data',
                               method='on_show_location_data',
                               enabled_name='show_view',
                               accelerator='Ctrl+Shift+D'),
                    CentralPaneAction(name='Plot View Selection',
                               method='on_show_plot_view_selection',
                               enabled_name='show_view',
                               accelerator='Ctrl+Shift+S'),
                    id='DataGroup', name='Data Group',
                ),
                DockPaneToggleGroup(),
                id='View', name="&View",
            ),
            SMenu(
                SGroup(
                    CentralPaneAction(name='Image Adjustment',
                               method='on_image_adjustment',
                               enabled_name='show_view',
                               accelerator='Ctrl+Shift+I'),
                    CentralPaneAction(name='Change Colormap',
                               method='on_change_colormap',
                               enabled_name='show_view'),
                    CentralPaneAction(name='Survey Line Settings',
                               method='on_change_settings',
                               enabled_name='show_view'),
                    CentralPaneAction(name='Cursor Freeze Key = Alt+c',
                               method='on_cursor_freeze',
                               enabled_name='show_view'),
                    CentralPaneAction(name='Box zoom enable = z'),
                    id='ToolGroup', name='Tool Group',
                ),
                id='Tools', name="&Tools",
            ),
        )
        return menu_bar

    def _tool_bars_default(self):
        toolbars = [
            SToolBar(
                TaskAction(name="Import", method='on_import',
                           image=ImageResource('import')),
                TaskAction(name="Open", method='on_open',
                           image=ImageResource('survey')),
                TaskAction(name="Save", method='on_save',
                           enabled_name='dirty',
                           image=ImageResource('save')),
                id='File', name="File", show_tool_names=False,
                image_size=(24, 24)
            ),
            SToolBar(
                TaskCommandAction(name='New Group', method='on_new_group',
                                  command_stack_name='command_stack',
                                  image=ImageResource('new-group')),
                TaskCommandAction(name='Delete Group',
                                  method='on_delete_group',
                                  enabled_name='have_current_group',
                                  command_stack_name='command_stack',
                                  image=ImageResource('delete-group')),
                TaskAction(name='Previous Line',
                           method='on_previous_line',
                           enabled_name='survey.survey_lines',
                           image=ImageResource("arrow-left")),
                TaskAction(name='Next Line',
                           method='on_next_line',
                           enabled_name='survey.survey_lines',
                           image=ImageResource("arrow-right")),
                self.move_legend_action,
                CentralPaneAction(name='Zoom Extent',
                                  method='on_zoom_extent',
                                  image=ImageResource("zone-resize"),
                                  enabled_name='show_view'),
                self.zoom_box_action,
                CentralPaneAction(name='Zoom Box Once (press "z")',
                                  enabled_name=''),
                id='Survey', name="Survey", show_tool_names=False,
                image_size=(24, 24)
            ),
        ]
        return toolbars

    def activated(self):
        """ Overriden to set the window's title.
        """
        self.window.title = self._window_title()

    def create_central_pane(self):
        """ Create the central pane: the editor pane.
        """
        from .survey_line_pane import SurveyLinePane
        pane = SurveyLinePane(survey_task=self)
        # listen for changes to the current survey line
        self.on_trait_change(lambda new: setattr(pane, 'survey_line', new),
                             'current_survey_line')
        return pane

    def create_dock_panes(self):
        """ Create the map pane and hook up listeners
        """
        from .survey_data_pane import SurveyDataPane
        from .survey_map_pane import SurveyMapPane
        from .survey_depth_pane import SurveyDepthPane
        from .message_pane import MessagePane
        print 'creating dock panes with survey', self.survey
        data = SurveyDataPane(survey=self.survey)
        self.on_trait_change(lambda new: setattr(data, 'survey', new), 'survey')

        map_pane = SurveyMapPane(survey=self.survey)
        self.on_trait_change(lambda new: setattr(map_pane, 'survey', new), 'survey')

        depth = SurveyDepthPane()
        message = MessagePane()

        return [data, map_pane, depth, message]

    def _survey_changed(self):
        from apptools.undo.api import CommandStack
        self.current_survey_line = None
        self.current_survey_line_group = None
        self.selected_survey_lines = []
        # reset undo stack
        self.command_stack = CommandStack(undo_manager=self.undo_manager)
        self.undo_manager.active_stack = self.command_stack

    @on_trait_change('survey.name')
    def update_title(self):
        if self.window and self.window.active_task is self:
            self.window.title = self._window_title()

    @on_trait_change('survey.survey_lines')
    def survey_lines_updated(self):
        if self.current_survey_line not in self.survey.survey_lines:
            self.current_survey_line = None
        self.selected_survey_lines[:] = [line for line in self.selected_survey_lines
                                         if line in self.survey_lines]

    @on_trait_change('survey.survey_line_groups')
    def survey_line_groups_updated(self):
        if self.current_survey_line_group not in self.survey.survey_line_groups:
            self.current_survey_line_group = None

    ###########################################################################
    # 'SurveyTask' interface.
    ###########################################################################

    def on_import(self):
        """ Imports hydrological survey data """
        from pyface.api import DirectoryDialog, OK
        from ...io.import_survey import import_survey

        # ask the user for save if needed
        self._prompt_for_save()

        survey_directory = DirectoryDialog(message="Select survey to import:",
                                           new_directory=False)
        if survey_directory.open() == OK:
            survey = import_survey(survey_directory.path, with_pick_files=True)
            self.survey = survey

    def on_open(self):
        """ Opens a hydrological survey file """
        self._prompt_for_save()
        raise NotImplementedError

    def on_save(self):
        """ Saves a hydrological survey file """
        raise NotImplementedError

    def on_open(self):
        """ Opens a hydrological survey file """
        self._prompt_for_save()
        raise NotImplementedError

    def on_load_pic_file(self):
        """ Saves a hydrological survey file """
        from pyface.api import FileDialog, OK
        from ...io.import_survey import (import_cores)

        dialog = FileDialog(message="Select pic file to import:")
        dialog.open()
        if dialog.return_code == OK:
            hdf5 = self.survey.hdf5_file
            directory = dialog.directory
            pic_file = dialog.filename
            logger.info('loading new pic file "{}"'.format(pic_file))
            pic_path = os.path.join(directory, pic_file)
            pic_depth_line = import_cores(h5file=hdf5, core_file=pic_path)
            self.survey.core_samples =  pic_depth_line
            self.survey.core_samples_updated = True
        print self.survey
        print self.have_survey
        raise NotImplementedError

    def on_load_corestick(self):
        """ Saves a hydrological survey file in a different location """
        from pyface.api import FileDialog, OK
        from ...io.import_survey import (import_cores)

        dialog = FileDialog(message="Select corestick file to import:")
        dialog.open()
        if dialog.return_code == OK:
            hdf5 = self.survey.hdf5_file
            directory = dialog.directory
            core_file = dialog.filename
            logger.info('loading new corestick file "{}"'.format(core_file))
            corestick_path = os.path.join(directory, core_file)
            cores = import_cores(h5file=hdf5, core_file=corestick_path)
            self.survey.core_samples = cores
            self.survey.core_samples_updated = True

    def on_new_group(self):
        """ Adds a new survey line group to a survey """
        from ...model.survey_line_group import SurveyLineGroup
        from ...model.survey_commands import AddSurveyLineGroup

        group = SurveyLineGroup(name='Untitled',
                                survey_lines=self.selected_survey_lines)
        command = AddSurveyLineGroup(data=self.survey, group=group)
        return command

    def on_replace_group(self):
        """ Adds all selected lines to group: 
        easy way to add individual lines to group
        """
        group = self.current_survey_line_group
        group.survey_lines = self.selected_survey_lines

    def on_delete_group(self):
        """ Deletes a survey line group from a survey """
        from ...model.survey_line_group import SurveyLineGroup
        from ...model.survey_commands import DeleteSurveyLineGroup

        group = self.current_survey_line_group
        command = DeleteSurveyLineGroup(data=self.survey, group=group)
        return command

    def on_next_line(self):
        """ Move to the next selected line """
        self.current_survey_line = self._get_next_survey_line()

    def on_previous_line(self):
        """ Move to the previous selected line """
        self.current_survey_line = self._get_previous_survey_line()

    def _get_dirty(self):
        return not self.command_stack.clean

    def _get_have_selected_lines(self):
        return len(self.selected_survey_lines) != 0

    def _get_have_current_group(self):
        return self.current_survey_line_group is not None

    def _get_have_survey(self):
        ''' currently treating new survey like None since we do not have 
        a concept of creating a survey from scratch.
        '''
        return self.survey.name != 'New Survey'

    def _command_stack_default(self):
        """ Return the default undo manager """
        from apptools.undo.api import CommandStack
        command_stack = CommandStack()
        return command_stack

    def _undo_manager_default(self):
        """ Return the default undo manager """
        from apptools.undo.api import UndoManager
        undo_manager = UndoManager(active_stack=self.command_stack)
        self.command_stack.undo_manager = undo_manager
        return undo_manager

    def _survey_default(self):
        from ...model.survey import Survey
        return Survey(name='New Survey')

    def _algorithms_default(self):
        return algorithms.get_algorithm_dict()

    ###########################################################################
    # private interface.
    ###########################################################################

    def _window_title(self):
        """ Get the title of the window """
        name = self.survey.name
        return name if name else 'Untitled'

    def _prompt_for_save(self):
        """ Check if the user wants to save changes """
        from pyface.api import ConfirmationDialog, CANCEL, YES
        if not self.command_stack.clean:
            message = 'The current survey has unsaved changes. ' \
                      'Do you want to save your changes?'
            dialog = ConfirmationDialog(parent=self.window.control,
                                        message=message, cancel=True,
                                        default=CANCEL, title='Save Changes?')
            result = dialog.open()
            if result == CANCEL:
                return False
            elif result == YES:
                if not self._save():
                    return self._prompt_for_save()
        return True

    def _save(self):
        """ Save changes to a survey file """
        raise NotImplementedError

    def _get_next_survey_line(self):
        """ Get the next selected survey line,
            or next line if nothing selected """
        survey_lines = self.selected_survey_lines[:]
        previous_survey_line = self.current_survey_line

        # if nothing selected, use all survey lines
        if len(survey_lines) == 0:
            survey_lines = self.survey.survey_lines[:]

        # if still nothing, can't do anything reasonable, but we shouldn't
        # have been called
        if len(survey_lines) == 0:
            return None

        if previous_survey_line in survey_lines:
            index = (survey_lines.index(previous_survey_line)+1) % \
                len(survey_lines)
            return survey_lines[index]
        else:
            return survey_lines[0]

    def _get_previous_survey_line(self):
        """ Get the previous selected survey line,
            or previous line if nothing selected """
        survey_lines = self.selected_survey_lines[:]
        previous_survey_line = self.current_survey_line

        # if nothing selected, use all survey lines
        if len(survey_lines) == 0:
            survey_lines = self.survey.survey_lines[:]

        # if still nothing, can't do anything reasonable, but we shouldn't
        # have been called
        if len(survey_lines) == 0:
            return None

        if previous_survey_line in survey_lines:
            index = (survey_lines.index(previous_survey_line)-1) % \
                len(survey_lines)
            return survey_lines[index]
        else:
            return survey_lines[-1]
