#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

from __future__ import absolute_import

from copy import deepcopy
import logging
import numpy as np

# ETS imports
from traits.api import (Instance, Str, Property, HasTraits, Int, List,
                        on_trait_change, Button, Bool, Supports)
from traitsui.api import (View, VGroup, HGroup, Item, UItem, EnumEditor,
                          TextEditor, ListEditor)

# Local imports
from ..model.depth_line import DepthLine
from ..model.i_survey_line_group import ISurveyLineGroup
from ..model.i_survey_line import ISurveyLine
from .survey_data_session import SurveyDataSession
from .survey_views import MsgView

logger = logging.getLogger(__name__)

ARG_TOOLTIP = 'comma separated keyword args -- x=1,all=True,s="Tom"'
UPDATE_ARRAYS_TOOLTIP = \
    'updates array data in form but does not apply to line'
APPLY_TOOLTIP = \
    'applies current setting to line, but does not update data'


class DepthLineView(HasTraits):
    """ View Class for working with survey line data to find depth profile.

    Uses a Survey class as a model and allows for viewing of various depth
    picking algorithms and manual editing of depth profiles.
    """

    #==========================================================================
    # Traits Attributes
    #==========================================================================

    # current data session with relevant info for the current line
    data_session = Instance(SurveyDataSession)

    # name of current line in editor
    survey_line_name = Property(depends_on=['data_session']
                                )

    # list of available depth lines extracted from survey line
    depth_lines = Property(depends_on=['data_session',
                                       'data_session.depth_lines_updated']
                           )

    # name of depth_line to view chosen from pulldown of all available lines.
    selected_depth_line_name = Str

    # current depth line object
    model = Instance(DepthLine)

    # set of arguments for algorithms.  Assume keyword.  makes dict
    args = Property(Str, depends_on=['model.args', 'model'])

    # arrays to plot
    index_array_size = Property(Int, depends_on=['model.index_array, model'])
    depth_array_size = Property(Int, depends_on=['model.depth_array, model'])

    # changes model to empty DepthLine for creating new line
    new_button = Button('New Line')

    # updates the data arrays for the selected line.  Apply does not do this
    update_arrays_button = Button('Update Data')

    # applys settings to  DepthLine updating object and updating survey line
    apply_button = Button('Apply')

    # applys settings each survey line in selected lines
    apply_to_group = Button('Apply to Group')

    source_name = Str
    source_names = Property(depends_on=['model.source'])

    # flag allows line creation/edit to continue in apply method
<<<<<<< HEAD
    no_problem = Bool

    # determines whether to show the list of selected groups and lines
    show_selected = Bool(False)

    # list of selected groups and lines by name str for information only
    selected = Property(List, depends_on=['current_survey_line_group',
                                    'selected_survey_lines'])

    # currently selected group
    current_survey_line_group = Supports(ISurveyLineGroup)

    # Set of selected survey lines (including groups) to apply algorithm to
    selected_survey_lines = List(Supports(ISurveyLine))

=======
    no_problem = Bool(False)
>>>>>>> bug/index-errors
    #==========================================================================
    # Define Views
    #==========================================================================

    traits_view = View(
        'survey_line_name',
        HGroup(
            Item('show_selected', label='Selected(show)'),
            UItem('selected',
                  editor=ListEditor(style='readonly'),
                  style='readonly',
                  visible_when='show_selected')
                   ),
        Item('selected_depth_line_name', label='View Depth Line',
             editor=EnumEditor(name='depth_lines')),
        Item('_'),
        VGroup(Item('object.model.survey_line_name', style='readonly'),
               Item('object.model.name'),
               Item('object.model.line_type'),
               Item('object.model.source'),
               Item('source_name',
                    editor=EnumEditor(name='source_names')),
               Item('args',
                    editor=TextEditor(auto_set=False, enter_set=False),
                    tooltip=ARG_TOOLTIP,
                    visible_when='object.model.source=="algorithm"'
                    ),
               Item('index_array_size', style='readonly'),
               Item('depth_array_size', style='readonly'),
               Item('object.model.edited', style='readonly'),
               Item('object.model.color'),
               Item('object.model.notes',
                    editor=TextEditor(auto_set=False, enter_set=False),
                    style='custom',
                    height=75, resizable=True
                    ),
               Item('object.model.lock'),
               ),
        HGroup(UItem('new_button'),
               UItem('update_arrays_button',
                     tooltip=UPDATE_ARRAYS_TOOLTIP),
               UItem('apply_button',
                     tooltip=APPLY_TOOLTIP),
               UItem('apply_to_group',
                     tooltip=APPLY_TOOLTIP)
               ),
        height=500,
        resizable=True,
    )

    #==========================================================================
    # Defaults
    #==========================================================================

    def _selected_depth_line_name_default(self):
        ''' provide initial value for selected depth line in view'''
        return 'none'

    #==========================================================================
    # Notifications or Callbacks
    #==========================================================================
    def update_plot(self):
        self.data_session.depth_lines_updated = True

    @on_trait_change('new_button')
    def load_new_blank_line(self):
        if self.selected_depth_line_name == 'none':
            self.change_depth_line(new='none')
        else:
            self.selected_depth_line_name = 'none'

    def depth_line_name_new(self, proposed_line):
        '''check that name is not in survey line depth lines already.
        Allow same name for PRE and POST lists since these are separate
        '''
        p = proposed_line
        # new names should begin and end with printable characters.
        p.name = p.name.strip()
        if p.line_type == 'current surface':
            used = p.name in self.data_session.lake_depths.keys()
        elif p.line_type == 'pre-impoundment surface':
            used = p.name in self.data_session.preimpoundment_depths.keys()
        else:
            self.log_problem('problem checking depth_line_name_new')
            used = True
        if used:
            s = 'name already used. Unlock to edit existing line'
            self.log_problem(s)
            self.model.lock = True
        return not used

    @on_trait_change('update_arrays_button')
    def update_arrays(self, new):
        ''' apply chosen method to fill line arrays
        '''
        model = self.model
        if model.lock:
            self.log_problem('locked so cannot change/create anything')

        # if line is 'none' then this is a new line --'added line'--
        # not a changed line. check name is new
        if self.selected_depth_line_name == 'none':
            self.depth_line_name_new(model)

        if self.no_problem:
            # name valid.  Try to update data.
            if model.source == 'algorithm':
                alg_name = model.source_name
                args = model.args
                logger.info('applying algorithm : {}'.format(alg_name))
                self.make_from_algorithm(alg_name, args)

            elif model.source == 'previous depth line':
                line_name = model.source_name
                self.make_from_depth_line(line_name)

            else:
                # source is sdi line.  create only from sdi data
                s = 'source "sdi" only available at survey load'
                self.log_problem(s)

    @on_trait_change('apply_button')
    def apply(self, new):
        ''' save current setting and data to current line'''
        model = self.model
        no_depth_array = self.depth_array_size == 0
        no_index_array = self.index_array_size == 0
        depth_notequal_index = self.depth_array_size != self.index_array_size
        if no_depth_array or no_index_array or depth_notequal_index :
            self.no_problem = False
            s = 'data arrays sizes are 0 or not equal'
            self.log_problem(s)
        if self.model.name.strip() == '':
            self.no_problem = False
            s = 'depth line has no printable name'
            self.log_problem(s)
        if self.model.name != self.selected_depth_line_name:
            self.depth_line_name_new(model)
        if model.lock:
            self.log_problem('locked so cannot change/create anything')
        # add to the survey line's appropriate dictionary
        if self.no_problem:
            logger.info('saving new line')
            ds = self.data_session
            if model.line_type == 'current surface':
                ds.lake_depths[self.model.name] = model
                key = 'POST_' + model.name
            else:
                ds.preimpoundment_depths[self.model.name] = model
                key = 'PRE_' + model.name
            # set form to new line
            self.selected_depth_line_name = key
            self.update_plot()
        else:
            s = '''Could not make new line.
            Did you update Data?
            Check log for details'''
            self.log_problem(s)

    @on_trait_change('selected_depth_line_name')
    def change_depth_line(self, new):
        if new != 'none':
            new_line = self.data_session.depth_dict[new]
            selected_line = deepcopy(new_line)
        else:
            selected_line = self.create_new_line()
        self.model = selected_line
        self.source_name = selected_line.source_name

    @on_trait_change('source_name')
    def _update_source_name(self):
        self.model.source_name = self.source_name

    #==========================================================================
    # Helper functions
    #==========================================================================
    def message(self, msg='my message'):
        dialog = MsgView(msg=msg)
        dialog.configure_traits()

    def log_problem(self, msg):
        ''' if there is a problem with any part of creating/updating a line,
        log it and notify user and set no_problem flag false'''
        self.no_problem = False
        logger.error(msg)
        self.message(msg)

    def make_from_algorithm(self, alg_name, args):
        algorithm = self.data_session.algorithms[alg_name]()
        survey_line = self.data_session.survey_line
        trace_array, depth_array = algorithm.process_line(survey_line,
                                                          **args)
        self.model.index_array = np.asarray(trace_array, dtype=np.int32) - 1
        self.model.depth_array = np.asarray(depth_array, dtype=np.float32)

    def make_from_depth_line(self, line_name):
        source_line = self.data_session.depth_dict[line_name]
        self.model.index_array = source_line.index_array
        self.model.depth_array = source_line.depth_array

    def create_new_line(self):
        new_dline = DepthLine(
            survey_line_name=self.survey_line_name,
            name='Type New Name',
            line_type='pre-impoundment surface',
            source='algorithm',
            edited=False,
            lock=False
            )
        logger.info('creating new depthline template')
        return new_dline

    #==========================================================================
    # Get/Set methods
    #==========================================================================
    def _get_source_names(self):
        source = self.model.source
        if source == 'algorithm':
            names = self.data_session.algorithms.keys()
        elif source == 'previous depth line':
            names = self.data_session.depth_dict.keys()
        else:
            # if source is sdi the source name is just the file it came from
            names = [self.model.source_name]
        return names

    def _get_survey_line_name(self):
        if self.data_session:
            name = self.data_session.survey_line.name
        else:
            name = 'No Survey Line Selected'
        return name

    def _get_depth_lines(self):
        # get list of names of depthlines for the UI
        if self.data_session:
            lines = ['none'] + self.data_session.depth_dict.keys()
        else:
            lines = []
        return lines

    def _get_index_array_size(self):
        a = self.model.index_array
        if a is not None:
            size = len(a)
        else:
            size = 0
        return size

    def _get_depth_array_size(self):
        a = self.model.depth_array
        if a is not None:
            size = len(a)
        else:
            size = 0
        return size

    def _get_args(self):
        d = self.model.args
        s = ','.join(['{}={}'.format(k, v) for k, v in d.items()])
        return s

    def _set_args(self, args):
        s = 'dict({})'.format(args)
        d = eval('dict({})'.format(args))
        mod_args = self.model.args
        if isinstance(d, dict):
            if mod_args != d:
                self.model.args = d
        else:
            s = '''Cannot make dictionary out of these arguments,
            Please check the format -- x=1, key=True, ...'''
            self.log_problem(s)
            if mod_args != {}:
                self.model.args = {}

    def _get_selected(self):
        '''make list of selected lines with selected group on top and all lines
        '''
        group_string = 'No Group Selected'
        all_lines = []
        if self.current_survey_line_group:
            group_name = self.current_survey_line_group.name
            group_string = 'GROUP: ' + group_name
        if self.selected_survey_lines:
            all_lines = [line.name for line in self.selected_survey_lines]
        return [group_string] + ['LINES:'] + all_lines
