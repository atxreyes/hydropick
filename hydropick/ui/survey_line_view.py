#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

from __future__ import absolute_import

import logging
import numpy as np

# ETS imports
from traits.api import (Instance, Dict, List, on_trait_change)
from traitsui.api import ModelView, View, VGroup

from chaco.api import (ArrayPlotData)

# Local imports
from .survey_data_session import SurveyDataSession
from .survey_tools import TraceTool, LocationTool, DepthTool
from .survey_views import (ControlView, InstanceUItem, PlotContainer, DataView,
                           ImageAdjustView, MsgView, LineSettingsView,
                           HPlotSelectionView, ColormapEditView)

logger = logging.getLogger(__name__)

EDIT_COLOR = 'black'
EDIT_OFF_ON_CHANGE = False
AUTOSAVE_EDIT_ON_CHANGE = True

EDIT_MASK_TOGGLE_STATE_CHAR = 't'


class SurveyLineView(ModelView):
    """ View Class for working with survey line data to find depth profile.

    Uses a Survey class as a model and allows for viewing of various depth
    picking algorithms and manual editing of depth profiles.
    """

    #==========================================================================
    # Traits Attributes
    #==========================================================================

    # Data model is SurveyDataSession class which starts with SurveyLine object
    # containing core data, SDI survey data, lake data.
    model = Instance(SurveyDataSession)

    # Defines view for all the plots.  Place beside control view
    plot_container = Instance(PlotContainer)

    # plotdata is the ArrayPlotData instance holding the plot data.
    # for now it contains available images and multiple line plots for depths.
    plotdata = Instance(ArrayPlotData)

    # dict to remember image control (b&c) settings for each freq
    image_settings = Dict

    ############## View classes used by editor ########################

    # Defines view for all the plot controls and info. Sits by plot container.
    control_view = Instance(ControlView)

    # Defines view for pop up location data window
    data_view = Instance(DataView)

    # Defines view for pop up location data window
    plot_selection_view = Instance(HPlotSelectionView)

    # Defines view for pop up image adjustments window
    image_adjust_view = Instance(ImageAdjustView)

    # Defines view for pop up image adjustments window
    cmap_edit_view = Instance(ColormapEditView)

    # Defines view for pop up window for  survey line settings
    line_settings_view = Instance(LineSettingsView)

    ######## SAVE FOR NOW - MAY GO BACK TO THIS ########
    # List of which lines are visible in plots
    visible_lines = List([])

    ############## Tools used by editor ########################

    # Custom tool for editing depth lines
    trace_tools = Dict

    # Custom tool for showing location info at mouse position for each freq
    location_tools = Dict

    # Custom tool for showing depth values at mouse position for each freq
    depth_tools = Dict

    #==========================================================================
    # Define Views
    #==========================================================================

    traits_view = View(
        VGroup(
            InstanceUItem('control_view'),
            InstanceUItem('plot_container'),
        ),
        resizable=True,
    )

    #==========================================================================
    # Defaults
    #==========================================================================

    def _plot_container_default(self):
        ''' Create initial plot container'''
        container = PlotContainer()
        container.on_trait_change(self.legend_capture,
                                  name='legend_drag')

        return container

    def _plotdata_default(self):
        ''' Provides initial plotdata object'''
        return ArrayPlotData()

    ############## View defaults ########################

    def _control_view_default(self):
        ''' Creates ControlView object filled with associated traits'''
        cv = ControlView(model=self.model,
                         mark_bad_data_mode='off',
                         edit='Not Editing',
                         )
        # set default values for widgets
        cv.image_freq = ''

        # Add notifications
        self.model.on_trait_change(self.change_target, name='selected_target')
        cv.on_trait_change(self.set_edit_enabled, name='edit')
        return cv

    def _plot_selection_view_default(self):
        freq_choices = self.model.freq_choices
        return HPlotSelectionView(hplot_choices=freq_choices,
                                  visible_frequencies=freq_choices,
                                  intensity_profile=True
                                  )

    def _data_view_default(self):
        return DataView()

    def _line_settings_view_default(self):
        return self.update_line_settings_view()

    def _cmap_edit_view_default(self):
        return ColormapEditView()

    def _image_adjust_view_default(self):
        iav = ImageAdjustView()
        iav.freq_choices = self.model.freq_choices
        iav.on_trait_change(self.adjust_image, name='contrast_brightness')
        iav.on_trait_event(self.adjust_image, name='invert')
        iav.on_trait_event(self.adjust_image, name='frequency')
        return iav

    ############## Tool defaults ########################

    def _trace_tools_default(self):
        ''' Sets up trace tool for editing lines'''
        tools = {}
        for key, hpc in self.plot_container.hplot_dict.items():
            if key is not 'mini':
                main = hpc.components[0]
                ybounds = self.model.ybounds[key]
                tool = TraceTool(main, drag_button="left")
                tool.ybounds = ybounds
                tool.toggle_character = EDIT_MASK_TOGGLE_STATE_CHAR
                tool.on_trait_change(self.toggle_mask_edit,
                                     'toggle_mask_edit_mode')
                main.tools.append(tool)
                tools[key] = tool
        return tools

    def _location_tools_default(self):
        ''' Sets up location tools for intensity images'''
        tools = {}
        for key, hpc in self.plot_container.hplot_dict.items():
            if key is not 'mini':
                main = hpc.components[0]
                img = main.plots[key][0]
                tool = LocationTool(img)
                tool.on_trait_change(self.update_locations, 'image_index')
                img.tools.append(tool)
                tools[key] = tool
        return tools

    def _depth_tools_default(self):
        ''' Sets up location tools for intensity images'''
        tools = {}
        for key, hpc in self.plot_container.hplot_dict.items():
            if key is not 'mini':
                ybounds = self.model.ybounds[key]
                main = hpc.components[0]
                tool = DepthTool(main)
                tool.ybounds = ybounds
                tool.on_trait_change(self.update_depth, 'depth')
                main.tools.append(tool)
                tools[key] = tool
        return tools

    #==========================================================================
    # Helper functions
    #==========================================================================

    def update_line_settings_view(self):
        ''' called by default method or by model update notification'''
        if self.model:
            view = LineSettingsView(model=self.model)
        else:
            view = LineSettingsView()
        return view

    def message(self, msg='my message'):
        dialog = MsgView(msg=msg)
        dialog.configure_traits()

    def create_data_array(self):
        '''want data array to have all data in it :
            3x img    min=1  (1 per hplot)
            3x img depth value array (1 per hplot, used for slice plotting)
            3x x_slice min=3 (1 per hplot)
            nx lines  min=0  (all on each hplot)

            data keys:
            intensity images key = freq
            img depth arrays key = freq_y
            slice line key = freq_slice
            depth line key = prefix_line_name_x

        '''

        if self.plotdata is None:
            self.plotdata = ArrayPlotData()
        d = self.plotdata

        if self.model:
            # add the freq dependent (3@) data
            for k, img in self.model.frequencies.items():
                y_key = k+'_y'
                slice_key = k+'_slice'
                kw = {k: self.model.frequencies[k],
                      y_key: self.model.y_arrays[k],
                      slice_key: np.array([]),
                      }
                d.update_data(**kw)

            # add zoom box points for showing zoom box in mini
            d.update_data(zoombox_x=np.array([0, 0, 0, 0]),
                          zoombox_y=np.array([0, 0, 0, 0]))

            # add horizontal line to display depth of cursor in slice
            # these are 2 pt line plots with the x value being the depth
            # and the y value being the full value range limits
            d.update_data(slice_depth_depth=np.array([0, 0]),
                          slice_depth_y=np.array([0, 0]))

            # add arrays to display mask
            d.update_data(mask_x=np.array([]))
            d.update_data(mask_y=np.array([]))

            # add the depth line data
            for line_key, depth_line in self.model.depth_dict.items():
                x = self.model.distance_array[depth_line.index_array]
                y = depth_line.depth_array
                key_x, key_y = line_key + '_x',  line_key + '_y'
                kw = {key_x: x, key_y: y}
                d.update_data(**kw)
        return d

    #==========================================================================
    # Get/Set methods
    #==========================================================================

    #==========================================================================
    # Notifications, Handlers or Callbacks
    #==========================================================================
    @on_trait_change('model:[final_lake_depth, final_preimpoundment_depth,
                     status, status_string]')
    def save_survey_line(self, obj, name, old, new):
        logger.info('survey_line {} attribute {} changed: saving'
                    .format(self.model.survey_line.name, name))
        self.model.survey_line.save_to_disk()

    @on_trait_change('model.anytrait')
    def logchange(self, obj, name, old, new):
        logger.debug('DATASESSION trait changed: {}'
                     .format((obj, name, old, new)))

    def toggle_mask_edit(self, obj, name, old, new):
        ''' if key toggle event fires from a tool, toggle the control view
        which should set tools accordingly'''
        cv = self.control_view
        cv.toggle_mark_bad_data_mode()
        #self.set_trace_tools_mask_edit()

    @on_trait_change('control_view.mark_bad_data_mode')
    def update_trace_tools(self):
        self.set_trace_tools_mask_edit()

    def set_trace_tools_mask_edit(self):
        ''' this should always correspond to control view mode'''
        mode = self.control_view.mark_bad_data_mode
        for tool in self.trace_tools.values():
            tool.set_mask_mode(mode)

    def zoom_box_toggle(self, action):
        ''' called if zoom box icon is clicked. state given by action.checked
        If zoom engaged make sure editing is turned off
        '''
        if action.checked:
            self.control_view.edit = 'Not Editing'
        self.control_view = action.checked
        for zoom_tool in self.plot_container.zoom_tools.values():
            zoom_tool.always_on = action.checked

    def move_legend(self, action):
        logger.debug('pan tool toggled')
        pc = self.plot_container
        pc.disable_pan(action)

    def set_edit_enabled(self, object, name, old, new):
        ''' enables editing tool based on ui edit selector
        '''
        # anytime we change editing mode we want to change tgt back to None
        # This may call change tgt if a tgt was selected - in that case line is
        # saved
        self.model.selected_target = 'None'

        # now set trace tool state based on edit state
        cv = self.control_view
        if cv.edit == 'Editing':
            edit_allowed = True
            edit_mask = False
        elif cv.edit == 'Mark Bad Data':
            edit_allowed = True
            edit_mask = True
        else:
            # 'Not Editing'
            edit_allowed = False
            edit_mask = False
        logger.debug('setting edit tools with allowed/mask = {}/{}'
                     .format(edit_allowed, edit_mask))
        for tool in self.trace_tools.values():
            tool.edit_allowed = edit_allowed
            tool.edit_mask = edit_mask
            if edit_mask:
                ymax = self.model.ybounds[self.model.freq_choices[-1]][1]
                logger.debug('set ymax for trace tool to {}'.format(ymax))
                tool.mask_value_max = ymax
        if edit_mask:
            self.set_trace_tools_mask_edit()

        # if Edit Mask selected need to change line to mask
        if cv.edit == 'Mark Bad Data':
            # first time this is called we need to set mask data
            if not self.model.survey_line.masked:
                logger.debug('initialize mask arrays to zero')
                self.model.initialize_mask_xy()
                x, y = self.model.get_mask_xy()
                self.plotdata.update_data(mask_x=x, mask_y=y)

            # if tgt was None then tgt is still None. Calling change tgt with
            # None, None will set tgt to 'mask' if in "Mark Bad Data" mode
            if self.model.selected_target == 'None':
                # explicitly call _change_target
                self._change_target('None', 'None')
            # else:
            #     # tgt not None: change to None will call change_target
            #     self.model.selected_target = 'None'

        # otherwise it is Editing or Not
        else:
            if old == 'Mark Bad Data':
                # edit changed out of Edit Mask => change tool tgts to None
                # need to call change mask explicitly to save mask data
                self._change_target('mask','None')
            # if selected_target is not None, then this was reached by
            # changing the line so we don't need to do anything else
        logger.debug('selectedtgt {}'.format(self.model.selected_target))

    @on_trait_change('model')
    def update_plot_container(self):
        ''' makes plot container.  usually called ones per survey line'''
        self.create_data_array()
        c = self.plot_container
        c.data = self.plotdata
        c.model = self.model
        logger.info('cores={}'.format(self.model.core_samples))
        # need to call tools to activate defaults
        start_tools = self.location_tools
        start_tools = self.depth_tools
        self.line_settings_view = self.update_line_settings_view()
        c.vplot_container.invalidate_and_redraw()

    def update_control_view(self):
        ''' update controls when new line added'''
        cv = self.control_view
        cv.model = self.model
        cv.edit = 'Not Editing'

    def legend_capture(self, obj, name, old, new):
        ''' stop editing depth line when moving legend (rt mouse button)'''
        self.control_view.edit = 'Not Editing'

    ##############  open dialogs when requestion by user  #################

    def zoom_extent(self):
        '''reset all zoom tools'''
        for zoom_tool in self.plot_container.zoom_tools.values():
            zoom_tool._reset_state_pressed()
            mini = self.plot_container.hplot_dict['mini'].components[0]
            range_sel_tool = mini.plots['reference'][0].tools[0]
            range_sel_tool.deselect()

    def image_adjustment_dialog(self):
        ''' brings up image C&B edit dialog. close to continue'''
        self.image_adjust_view.configure_traits()

    def show_data_dialog(self):
        ''' cannot make modal if want to monitor so should be pane.
        for now must remember to close independent of app'''
        self.data_view.configure_traits()

    def cmap_edit_dialog(self):
        ''' brings up cmap edit dialog. close to continue'''
        self.cmap_edit_view.configure_traits(kind='livemodal')

    def plot_view_selection_dialog(self):
        ''' called from view menu to edit which plots to view'''
        self.plot_selection_view.configure_traits()

    def line_settings_dialog(self):
        ''' called from view menu to edit which plots to view'''
        self.line_settings_view.configure_traits()

    ############## other handlers/notifiers  #################

    @on_trait_change('model.depth_lines_updated')
    def update_lines(self):
        self.update_control_view()
        self.plot_container.update_all_line_plots(update=True)

    @on_trait_change('cmap_edit_view.colormap')
    def cmap_edit(self):
        self.plot_container.img_colormap = self.cmap_edit_view.colormap

    @on_trait_change('plot_selection_view.visible_frequencies')
    def change_visible_frequencies(self):
        ''' update visible hplots based on visible freq checkboxes
        this will reset zoom and edit modes'''
        cv = self.control_view
        cv.edit = 'Not Editing'
        vis_hplots = self.plot_selection_view.visible_frequencies
        self.plot_container.selected_hplots = vis_hplots
        self.plot_container.set_hplot_visibility()
        self.zoom_extent()

    @on_trait_change('plot_selection_view.intensity_profile')
    def change_intensity_profile_visibility(self):
        ''' update visible hplots based on visible freq checkboxes'''
        show_profile = self.plot_selection_view.intensity_profile
        self.plot_container.show_intensity_profiles = show_profile
        self.plot_container.set_intensity_profile_visibility(show_profile)

    def update_locations(self, image_index):
        ''' Called by location_tool to update display readouts as mouse moves
        '''
        dv = self.data_view
        lat, long = self.model.lat_long[image_index]
        east, north = self.model.locations[image_index]
        power = self.model.survey_line.power[image_index]
        gain = self.model.survey_line.gain[image_index]
        dv.latitude = lat
        dv.longitude = long
        dv.easting = east
        dv.northing = north
        dv.power = power
        dv.gain = gain

    def adjust_image(self, obj, name, old, new):
        ''' Given a tuple (contrast, brightness) with values
        from 0 to CONTRAST_MAX, 0 to 1
        if frequency is changed, update view which will update plots.
        if other values are changed and there is a freq, it will
        update data with new values and save settings
        '''
        iav = self.image_adjust_view
        if name is 'frequency':
            # changed freq : update settings
            freq = new
            c, b, i = self.image_settings.setdefault(freq, [1, 0, True])
            iav.contrast, iav.brightness, iav.invert = c, b, i
        else:
            if iav.frequency:
                freq = iav.frequency
                if name == 'invert':
                    self.image_settings[freq][2] = new
                    self.apply_image_settings(freq)
                elif name == 'contrast_brightness':
                    self.image_settings[freq][:2] = new
                self.apply_image_settings(freq)

    def apply_image_settings(self, freq):
        ''' apply saved image settings to this freq (or set default).
        always reapply changes from original data.
        apply to plot data
        called by adjust image
        '''
        c, b, invert = self.image_settings.setdefault(freq, [1, 0, True])
        data = self.model.frequencies[freq]
        data = c * data
        b2 = c * b - b
        b3 = b2 + 1
        data = np.clip(data, b2, b3)
        if invert:
            data = 1-data
        self.plot_container.data.update_data({freq: data})

    def update_depth(self, depth):
        ''' Called by trace tool to update depth readout display'''
        self.data_view.depth = depth
        self.plot_container.update_slice_depth_line_plot(depth=depth)

    def change_target(self, object, name, old, new_target):
        ''' update trace tool target line attribute.
        change line colors back and set edit flag and save data as requrire
        old and new will be strings from the seleted target editor
        in the control_view (choices are depthline.name strings)
        '''
        self._change_target(old, new_target)

    def _change_target(self, old, new_target):
        ''' Implements editing target change normally activated by
        change target handler from selected_target listener, but can
        also be called by set_edit handler when set to Edit Mask.
        if target goes from None to None this will only be called
        directly by the set_edit handler, otherwise through the tgt
        change handler.
        '''
        logger.debug('change edit target from {} to {}'
                     .format(old, new_target))
        plot_dict = self.plot_container.plot_dict
        if self.control_view.edit == 'Mark Bad Data':
            # need to change target to 'mask' and revert 'old if needed
            if new_target != 'None':
                # someone changed selected target from None while in Edit Mask
                # normally this is not possible so probably err in program
                logger.error('IN CHANGE_TARGET:  target changed while in ' +
                             'Mark Bad Data mode. Investigate')
                #self.control_view.edit = 'Not Editing'
                #old = 'mask'
            else:
                # get old and None with Edit Mask:  => set tgt to mask
                # if tgt was None then old is None. Else old is last line set.
                new_target = 'mask'
        # elif new_target == 'None' and :
        #     # this may always happens if edit is not Edit Mask
        #     self.control_view.edit = 'Not Editing'

        # otherwise:  not edit mask and not None means tgt is new line
        # from selected_target editor.  old is whatever was there before

        # change colors and tool tgt for each freq plot
        edited = []
        for key in self.model.freq_choices:
            # if new tgt, change its color, else set none
            if new_target != 'None':
                new_plot_key = key + '_' + new_target
                new_target_plot = plot_dict[new_plot_key]
                if new_target == 'mask':
                    # set edge color
                    new_target_plot.edge_color = EDIT_COLOR
                else:
                    new_target_plot.color = EDIT_COLOR
            else:
                new_target_plot = None
            # if old tgt exists, change back color, else skip
            old_plot_key = key + '_' + old
            old_target_plot = plot_dict.get(old_plot_key, None)
            if old_target_plot:
                if old == 'mask':
                    # mask is not in depth dict need to get mask color
                    old_color = self.plot_container.mask_color
                    old_target_plot.edge_color = old_color
                else:
                    old_target_depth_line = self.model.depth_dict[old]
                    old_color = old_target_depth_line.color
                    old_target_plot.color = old_color
            # update trace_tool target for this freq.
            tool = self.trace_tools[key]
            edited.append(tool.data_changed)
            tool.target_line = new_target_plot
            tool.key = new_target

        if AUTOSAVE_EDIT_ON_CHANGE and old_target_plot:
            edited_data = old_target_plot.value.get_data()
            if old == 'mask':
                # mask is saved as array in survey_line
                self.model.array_to_mask(edited_data)
            else:
                # depth arrays are stored in depthline objects
                old_target_depth_line.depth_array = edited_data
                if old_target_depth_line.edited is False:
                    # never edited so set to edited if and tool has edited it.
                    old_target_depth_line.edited = any(edited)
            # update survey_line on disk
            self.model.survey_line.save_to_disk()

        self.plot_container.vplot_container.invalidate_and_redraw()

    def select_line(self, object, name, old, visible_lines):
        #### KEEP THIS BECAUSE WE MAY GO BACK TO IT FOR VISIBILITY  #########
        ''' Called when controlview.visible_lines changes in order to actually
        change the visibility of the lines.  Need to make sure the new list
        includes the selected lines which means if someone unchecks it we have
        to not only make it visible but add it to visible lines which will
        re-call this method'''

        newset = set(visible_lines)
        cv = self.control_view

        if cv.line_to_edit:
            # If there is line to edit, make sure its in visible lines list.
            # Temporarily disable notification so we don't re-call this method.
            fullset = newset.union(set([cv.line_toedit]))
            cv.on_trait_change(self.select_line, name='visible_lines',
                               remove=True)
            cv.visible_lines = list(fullset)
            cv.on_trait_change(self.select_line, name='visible_lines')

        else:
            fullset = newset

        # now set correct visibilties
        for name in self.model.depth_dict:
            this_plot = self.mainplot.plots[name][0]
            if name in fullset:
                this_plot.visible = True
            else:
                this_plot.visible = False
        self.mainplot.invalidate_and_redraw()
