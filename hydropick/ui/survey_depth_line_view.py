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
from traits.api import (Instance, Event, Str, Property, HasTraits, Int, List,
                        on_trait_change, Button, Bool, Supports, Dict)
from traitsui.api import (View, VGroup, HGroup, Item, UItem, EnumEditor,
                          TextEditor, ListEditor, ButtonEditor)

# Local imports
from ..model.depth_line import DepthLine
from ..model.i_survey_line_group import ISurveyLineGroup
from ..model.i_survey_line import ISurveyLine
from ..model.i_algorithm import IAlgorithm
from .algorithm_presenter import AlgorithmPresenter
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

    # name of hdf5_file for this survey in case we need to load survey lines
    hdf5_file = Str

    # current depth line object
    model = Instance(DepthLine)

    # set of arguments for algorithms.  Assume keyword.  makes dict
   # args = Property(Str, depends_on=['model.args', 'model'])

    # arrays to plot
    index_array_size = Property(Int, depends_on=['model.index_array, model'])
    depth_array_size = Property(Int, depends_on=['model.depth_array, model'])

    # create local traits so that these options can be dynamically changed
    source_name = Str
    source_names = Property(depends_on=['model.source'])

    # flag allows line creation/edit to continue in apply method
    no_problem = Bool(False)

    # determines whether to show the list of selected groups and lines
    show_selected = Bool(False)

    # list of selected groups and lines by name str for information only
    selected = Property(List, depends_on=['current_survey_line_group',
                                    'selected_survey_lines'])

    # currently selected group
    current_survey_line_group = Supports(ISurveyLineGroup)

    # Set of selected survey lines (including groups) to apply algorithm to
    selected_survey_lines = List(Supports(ISurveyLine))

    # dict of algorithms
    algorithms = Dict
    
    # convenience property for getting algorithm arguments
    alg_arg_dict = Property()

    # currently configured algorithm
    current_algorithm = Supports(IAlgorithm)

    ##### BUTTONS FOR THE VIEW ####
    # changes model to empty DepthLine for creating new line
    new_button = Button('New Line')

    # updates the data arrays for the selected line.  Apply does not do this
    update_arrays_button = Button('Update Data')

    # applys settings to  DepthLine updating object and updating survey line
    apply_button = Button('Apply')

    # applys settings each survey line in selected lines
    apply_to_group = Button('Apply to Group')

    # button to open algorithm configure dialog
    configure_algorithm = Event()
    configure_algorithm_done = Button('Configure Algorithm (Done)')
    
    # flag to prevent source_name listener from acting when model changes
    model_just_changed = Bool(True)

    # Private algorithm presenter initialized at creation time
    _algorithm_presenter = Instance(AlgorithmPresenter, ())

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

               UItem('configure_algorithm',
                     editor=ButtonEditor(label='Configure Algorithm'),
                     visible_when=('object.model.source=="algorithm" and not current_algorithm')
                     ),
               UItem('configure_algorithm_done',
                     visible_when=('current_algorithm')
                     ),
               # Item('args',
               #      editor=TextEditor(auto_set=False, enter_set=False),
               #      tooltip=ARG_TOOLTIP,
               #      visible_when='object.model.source=="algorithm"'
               #    ),
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
        # these are the buttons to control this pane
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

    @on_trait_change('configure_algorithm, configure_algorithm_done')
    def show_configure_algorithm_dialog(self):
        ''' gets/created current algorithm object and opens configure dialog'''
        alg_name = self.model.source_name
        logger.debug('configuring alg: {}. Alg exists={}, model args={}'
                     .format(alg_name, self.current_algorithm, self.model.args))
        if self.current_algorithm is None:
            self.set_current_algorithm()

        self._algorithm_presenter.algorithm = self.current_algorithm
        self._algorithm_presenter.edit_traits()

    def set_alg_args(self, model_args):
        ''' if possible, sets default arguments for current algorithm configure
        dialog according to model.args dict. Otherwise warns user and continues'''
        alg = self.current_algorithm
        logger.debug('set arg defaults to model: args={}'.format(model_args))
        try:
            for arg in alg.arglist:
                setattr(alg, arg, model_args[arg])
        except Exception as e:
            logger.warning('could not set arguments from model.args')
            print 'Warning: could not set args', e

    @on_trait_change('current_algorithm.+')
    def update_model_args(self, object, name, old, new):
        ''' current algorithm or its arguments have changed
        -  this updates the model.args values to match algorithm args
        -  this zeros out data arrays since the change implies new data
        '''
        alg = self.current_algorithm
        if alg:
            if self.model.args == self.alg_arg_dict:
                # no change to data
                pass
            else:
                logger.debug('updating model with args {}'.format(self.alg_arg_dict))
                self.model.args = self.alg_arg_dict
                self.zero_out_array_data()
            

    @on_trait_change('new_button')
    def load_new_blank_line(self):
        ''' prepare for creation of new line
        if "none" is already selected, change depth line as if view_depth_line
        was "changed" to "none" (call change depth line with "none"). Otherwise
        change selected line to none and listener will handle it'''
        self.no_problem = True
        if self.selected_depth_line_name == 'none':
            self.change_depth_line(new='none')
        else:
            self.selected_depth_line_name = 'none'

    @on_trait_change('update_arrays_button')
    def update_arrays(self, new):
        ''' apply chosen method to fill line arrays
        '''
        logger.info('applying arrays update')
        model = self.model
        if model.lock:
            self.log_problem('locked so cannot change/create anything')

        # if line is 'none' then this is a new line --'added line'--
        # not a changed line. check name is new. if not flag problem.
        if self.selected_depth_line_name == 'none':
            self.check_if_name_already_exists(model)

        if self.no_problem:
            logger.debug('no problem in update. try update')
            line = self.data_session.survey_line
            # name valid.  Try to update data.
            if model.source == 'algorithm':
                alg_name = model.source_name
                logger.debug('applying algorithm :' +
                             '{} to line {}'.format(alg_name, line.name))
                if self.current_algorithm:
                    self.make_from_algorithm()
                else:
                    self.log_problem('need to configure algorithm')
                if self.no_problem:
                    self.check_args()

            elif model.source == 'previous depth line':
                line_name = model.source_name
                self.make_from_depth_line(line_name)

            else:
                # source is sdi line.  create only from sdi data
                s = 'source "sdi" only available at survey load'
                self.log_problem(s)
                self.no_problem = True

            if self.no_problem:
                self.check_arrays()
                self.no_problem = True
            else:
                # allow user to correct problems and continue
                self.no_problem = True
        else:
            # allow user to correct problems and continue
            self.no_problem = True

    @on_trait_change('apply_button')
    def apply_to_current(self, new):
        ''' save current setting and data to current line'''
        model = self.model
        # self.check name is valid
        self.check_printable_name()
        # check arrays are filled and equal
        self.check_arrays()
        # if model name is changed from selected (copy line with new name)
        # or selected is none ( => new line)
        # check that name is if name is taken that line is not locked.
        name = self.selected_depth_line_name.split('_')[1:]
        print 'check name', self.model.name, name, ''.join(name)
        if self.model.name != ''.join(name):
            self.check_if_name_already_exists(model)
        if model.lock:
            self.log_problem('locked so cannot change/create anything')
        # add to the survey line's appropriate dictionary
        if self.no_problem:
            ds = self.data_session
            if model.line_type == 'current surface':
                ds.lake_depths[self.model.name] = model
                ds.final_lake_depth = self.model.name
                key = 'POST_' + model.name
            else:
                ds.preimpoundment_depths[self.model.name] = model
                ds.final_preimpoundment_depth = self.model.name
                key = 'PRE_' + model.name

            # set form to the new line
            self.selected_depth_line_name = key
            self.update_plot()
            logger.info('saving new {} line : {}'.format(model.line_type,
                                                         model.name))
        else:
            # notify user of problem again and reset no problem flag
            s = '''Could not make/change line.
                Did you update Data?  Check log for details'''
            self.log_problem(s)
            self.no_problem = True

    @on_trait_change('apply_to_group')
    def apply_to_selected(self, new):
        ''' Apply current settings to all selected survey lines

        the will step through selected lines list and
        - check that valid algorithm selected
        - check if depth line exists (overwrite?)
        - check if line is approved (apply?)
        - check if line is bad
        - create line with name and algorithm, args color etc.
        - apply data and apply to make line
        - set as final (?)
        '''
        # save current model to duplicate
        model = self.model
        # list of selected lines
        selected = self.selected_survey_lines

        # check that algorithm is selected and valid and configured
        self.check_alg_ready()
        # self.check name is valid
        self.check_printable_name()

        if self.no_problem:
            # log parameters
            lines_str = '\n'.join([line.name for line in selected])
            s = '''Creating depth line for the following surveylines:
            {lines}
            with the following parameters:
            name = {name}
            algorithm = {algorithm}
            args = {args}
            color = {color}
            '''.format(lines=lines_str,
                       name=self.model.name,
                       algorithm=self.source_name,
                       args=self.model.args,
                       color=self.model.color)
            logger.info(s)
            # apply to each survey line
            for line in self.selected_survey_lines:
                if line.trace_num.size == 0:
                    # need to load line
                    line.load_data(self.hdf5_file)
                # create new deep copy of model object for each survey line
                self.model = deepcopy(model)
                self.model.survey_line_name = line.name
                alg_name = model.source_name
                logger.debug('applying algorithm :' +
                             '{} to line {}'.format(alg_name, line.name))
                self.make_from_algorithm(survey_line=line)
                self.check_arrays()
                if self.no_problem:
                    lname = line.name
                    s = 'saving new depth line to surveyline {}'.format(lname)
                    logger.info(s)
                    print 'saving', self.model.name, line.name
                    # save to appropriate depth line dictionary and change
                    # final line to new line
                    if model.line_type == 'current surface':
                        line.lake_depths[self.model.name] = self.model
                        line.final_lake_depth = self.model.name
                    else:
                        line.preimpoundment_depths[self.model.name] = self.model
                        line.final_preimpoundment_depth = self.model.name
        else:
            # there was a problem.  User should correct based on messages
            # and retry.  Reset no problem flag so user can continue.
            self.no_problem = True
        self.model = model

    @on_trait_change('selected_depth_line_name')
    def change_depth_line(self, new):
        ''' selected line has changed so use the selection to change the
        current model to selected or create new one if none'''
        source_name = self.source_name
        if new != 'none':
            # Existing line: edit copy of line until apply button clicked
            # then it will reploce the line in the line dictionary
            new_line = self.data_session.depth_dict[new]
            selected_line = deepcopy(new_line)
            logger.debug('save copy of line {} and load'
                         .format(selected_line.name))
            if selected_line.source == 'algorithm':
                logger.debug('alg arguments saved in line are {}'
                             .format(selected_line.args))
        else:
            selected_line = self.create_new_line()
        self.model = selected_line
        # keeps arrays from being erased by source_name listener when source
        # changes from changing lines
        if self.source_name != selected_line.source_name:
            self.model_just_changed = True
        self.source_name = selected_line.source_name
        self.current_algorithm = None
        self.no_problem = True

    @on_trait_change('source_name')
    def _update_source_name(self):
        ''' either the algorithm is changed or a new source of data is chosen.
        either way, reset current algorithm and set model source name
        and zero the data arrays since by definition these are being changed
        Note that this is not saved until apply so user can restore original
        data by just reselecting the line'''
        logger.debug('source name changed to {}'.format(self.source_name))
        if not self.model_just_changed:
            logger.debug('reseting alg and arrays due to source name chg')
            self.current_algorithm = None
            self.zero_out_array_data()
        self.model.source_name = self.source_name
        self.model_just_changed = False

    #==========================================================================
    # Helper functions
    #==========================================================================

    #### checking methods ################################
    def check_arrays(self, depth_line=None):
        ''' checks arrays are equal and not empty'''
        if depth_line is None:
            depth_line = self.model
        d_array_size = self._array_size(depth_line.depth_array)
        i_array_size = self._array_size(depth_line.index_array)
        no_depth_array = d_array_size == 0
        no_index_array = i_array_size == 0
        depth_notequal_index = d_array_size != i_array_size
        name = self.survey_line_name
        if no_depth_array or no_index_array or depth_notequal_index:
            s = 'data arrays sizes are 0 or not equal for {}'.format(name)
            self.log_problem(s)

    def check_printable_name(self):
        if self.model.name.strip() == '':
            s = 'depth line has no printable name'
            self.log_problem(s)

    def check_if_name_already_exists(self, proposed_line, data_session=None):
        '''check that name is not in survey line depth lines already.
        Allow same name for PRE and POST lists since these are separate
        '''
        if data_session is None:
            data_session = self.data_session
        p = proposed_line
        # new names should begin and end with printable characters.
        p.name = p.name.strip()
        if p.line_type == 'current surface':
            used = p.name in data_session.lake_depths.keys()
        elif p.line_type == 'pre-impoundment surface':
            used = p.name in data_session.preimpoundment_depths.keys()
        else:
            self.log_problem('problem checking depth_line_name_new')
            used = True
        if used:
            s = 'name already used. To overwrite, select that line, unlock' +\
                ' and edit, then reapply'
            self.log_problem(s)
            self.model.lock = True
        return not used

    def check_alg_ready(self):
        ''' check algorithm is selected and configured'''
        # check that algorithm is selected and valid
        not_alg = self.model.source != 'algorithm'
        alg_choices = self.algorithms.keys()
        good_alg_name = self.model.source_name in alg_choices
        if not_alg or not good_alg_name:
            self.log_problem('must select valid algorithm')
        else:
            self.no_problem = True
        self.set_current_algorithm()
        # check that arguments match model. Otherwise these need to be set.
        self.check_args()

    def check_args(self):
        ''' checks that arguments match the model
        this should be run before allowing apply to complete'''
        alg = self.current_algorithm
        logger.debug('checking args for alg {} with args {}'
                     .format(alg.name, self.alg_arg_dict))
        if alg:
            # tst = [self.model.args.get(arg, None) ==
            #        getattr(alg, arg) for arg in alg.arglist]
            tst = (self.model.args == self.alg_arg_dict)
            # if not all(tst):
            #     s = 'arguments do not match - please configure algorithm.'
            #     self.log_problem(s)
            if not tst:
                s = 'arguments do not match - please configure algorithm.'
                self.log_problem(s) 

    ############################################################
    def set_current_algorithm(self):
        ''' Set current alg based on model.
        setting current alg will update model.args so need to save these
        and apply if neccesary after setting current alg.'''
        alg_name = self.model.source_name
        model_args = self.model.args
        self.current_algorithm = self.algorithms[alg_name]()
        if model_args:
            self.set_alg_args(model_args)
            self.model_args = model_args
            logger.debug('model_args={}, alg args={}'
                         .format(self.model.args, self.alg_arg_dict))

    def zero_out_array_data(self):
        ''' sets depth and index arrays for model to zero'''
        self.model.index_array = np.array([])
        self.model.depth_array = np.array([])
        
    def update_plot(self):
        ''' used as signal to update depth line choices from depth_lines prop
        so that ui choices will update'''
        self.data_session.depth_lines_updated = True

    def message(self, msg='my message'):
        dialog = MsgView(msg=msg)
        dialog.configure_traits()

    def log_problem(self, msg):
        ''' if there is a problem with any part of creating/updating a line,
        log it and notify user and set no_problem flag false'''
        self.no_problem = False
        logger.error(msg)
        self.message(msg)

    def make_from_algorithm(self, model=None, survey_line=None):
        if model is None:
            model = self.model
        if survey_line is None:
            survey_line = self.data_session.survey_line
        algorithm = self.current_algorithm
        trace_array, depth_array = algorithm.process_line(survey_line)
        model.index_array = np.asarray(trace_array, dtype=np.int32) - 1
        model.depth_array = np.asarray(depth_array, dtype=np.float32)
        return model

    def make_from_depth_line(self, line_name):
        source_line = self.data_session.depth_dict[line_name]
        self.model.index_array = source_line.index_array
        self.model.depth_array = source_line.depth_array

    def create_new_line(self):
        ''' fill in some default value and return new depth line object'''
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

    def _array_size(self, array=None):
        if array is not None:
            size = len(array)
        else:
            size = 0
        return size

    #==========================================================================
    # Get/Set methods
    #==========================================================================
    def _get_alg_arg_dict(self):
        if self.current_algorithm:
            alg = self.current_algorithm
            d = dict([(arg, getattr(alg, arg)) for arg in alg.arglist])
        else:
            d = {}
        return d
    
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
        return self._array_size(self.model.index_array)

    def _get_depth_array_size(self):
        return self._array_size(self.model.depth_array)

    def _get_args(self):
        d = self.model.args
        s = ','.join(['{}={}'.format(k, v) for k, v in d.items()])
        return s

    def _set_args(self, args):
        ''' Sets args dict in model'''
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
        #group_string = 'No Group Selected'
        all_lines = []
        # if self.current_survey_line_group:
        #     group_name = self.current_survey_line_group.name
        #     group_string = 'GROUP: ' + group_name
        if self.selected_survey_lines:
            all_lines = [line.name for line in self.selected_survey_lines]
            num_lines = len(all_lines)
        else:
            num_lines = 0
        # return [group_string] + ['LINES: {}'.format(num_lines)] + all_lines
        return ['LINES: {}'.format(num_lines)] + all_lines
