#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

""" View definitions for controlling layout of survey line editor task
"""

# Std lib imports
import logging

# other imports
import numpy as np

# ETS imports
from enable.api import ComponentEditor
from traits.api import (Instance, Str, List, HasTraits, Float, Property,
                        Enum, Bool, Dict, on_trait_change, Trait,
                        Callable, Tuple, CFloat, Event)
from traitsui.api import (View, Item, EnumEditor, UItem, InstanceEditor,
                          TextEditor, RangeEditor, Label, HGroup, VGroup,
                          CheckListEditor, Group, ButtonEditor)
from chaco import default_colormaps
from chaco.api import (Plot, ArrayPlotData, VPlotContainer, HPlotContainer,
                       Legend, create_scatter_plot, PlotComponent,
                       create_line_plot)
from chaco.tools.api import (PanTool, ZoomTool, RangeSelection, LineInspector,
                             RangeSelectionOverlay, LegendHighlighter)

# Local imports
from .survey_tools import InspectorFreezeTool
from .survey_data_session import SurveyDataSession

# global constants
# these still need to be tweaked to get the right look
logger = logging.getLogger(__name__)
COLORMAPS = default_colormaps.color_map_name_dict.keys()
DEFAULT_COLORMAP = 'Spectral'
TITLE_FONT = 'swiss 10'
MINI_HEIGHT = 100
SLICE_PLOT_WIDTH = 75
ZOOMBOX_COLOR = 'lightgreen'
ZOOMBOX_ALPHA = 0.3

HPLOT_PADDING = 0
HPLOT_PADDING_BOTTOM = 0
MINI_PADDING = 15
MINI_PADDING_BOTTOM = 20
MAIN_PADDING = 15
MAIN_PADDING_BOTTOM = 20
MAIN_PADDING_LEFT = 25

CONTRAST_MAX = float(20)

CORE_VISIBILITY_CRITERIA = 200.0
CORE_LINE_WIDTH = 2

MASK_EDGE_COLOR = 'black'
MASK_FACE_COLOR = 'black'
MASK_ALPHA = 0.5

# used to remove this from choices of lines to edit
CURRENT_SURFACE_FROM_BIN_NAME = 'current_surface_from_bin'
CURRRENT_SURFACE_FROM_BIN_LABEL = 'POST_' + CURRENT_SURFACE_FROM_BIN_NAME


class InstanceUItem(UItem):
    '''Convenience class for inluding instance in view as Item'''

    style = Str('custom')
    editor = Instance(InstanceEditor, ())


class ColormapEditView(HasTraits):
    ''' provides dialog box to select colormap'''

    colormap = Enum(COLORMAPS)

    traits_view = View(
        Group(Label('Frequency to Edit'),
              Item('colormap')
              ),
        buttons=["OK", "Cancel"],
    )


class PlotContainer(HasTraits):
    ''' miniplot must have at least one plot with an index.
        therefore there should be a check in the plot dictionary
        that there is a plot with an index
    '''

    #==========================================================================
    # Traits Attributes
    #==========================================================================

    # data objects recived from model_view
    model = Instance(SurveyDataSession)
    data = Instance(ArrayPlotData)

    # main plot component returned
    vplot_container = Instance(VPlotContainer)

    ###### storage structures for listener access to these objects via lookup
    # dict of hplots (main-edit-plot|slice plot) keyed by freq like intensities
    hplot_dict = Dict(Str, Instance(HPlotContainer))

    # dict of all core plots so we can set visibility
    core_plots_dict = Dict

    # hplots visible in main vplotcontainer. Set by checkbox.
    selected_hplots = List

    # show intensity slice profiles
    show_intensity_profiles = Bool(True)

    # legends for each hplot:main.  Used to set visibility
    legend_dict = Dict

    # need to toggle pantool
    pan_tool_dict = Dict

    # shared dict of line_plot objects, mostly for when edit target changes
    plot_dict = Dict(Str, PlotComponent)

    # tool used to toggle active state of cursor via keyboard ()
    inspector_freeze_tool = Instance(InspectorFreezeTool)

    img_colormap = Enum(COLORMAPS)

    # private traits
    _cmap = Trait(default_colormaps.Spectral, Callable)

    # color for mask plot edge
    mask_color = Str(MASK_EDGE_COLOR)

    zoom_tools = Dict

    legend_drag = Event
    #==========================================================================
    # Define Views
    #==========================================================================

    traits_view = View(UItem('vplot_container',
                             editor=ComponentEditor(),
                             show_label=False
                             )
                       )

    #==========================================================================
    # Defaults
    #==========================================================================
    def _vplot_container_default(self):
        vpc = self.create_empty_plot()
        return vpc

    def _inspector_freeze_tool_default(self):
        # sets up keybd shortcut and tool for freezing cursor activity
        tool = InspectorFreezeTool(tool_set=set(),
                                   main_key="c",
                                   modifier_keys=["alt"],
                                   ignore_keys=[]
                                   )
        return tool

    def _core_plot_dict_default(self):
        d = {}
        for core in self.model.core_samples:
            d[core.core_id] = []

    def __cmap_default(self):
        cm = default_colormaps.color_map_name_dict[self.img_colormap]
        return cm

    def _img_colormap_default(self):
        return DEFAULT_COLORMAP

    #==========================================================================
    # Helper functions
    #==========================================================================
    def create_empty_plot(self):
        ''' place filler
        '''
        vpc = VPlotContainer(bgcolor='lightgrey', height=1000, width=800)
        self.vplot_container = vpc
        return vpc

    def create_vplot(self):
        ''' fill vplot container with 1 mini plot for range selection
        and N main plots ordered from to top to bottom by freq
        '''
        vpc = VPlotContainer(bgcolor='lightgrey')
        if self.model.freq_choices:
            # create mini plot using the highest freq as background
            keys = self.model.freq_choices
            mini = self.create_hplot(key=keys[-1], mini=True)
            self.mini_hplot = mini
            vpc.add(mini)

            # create hplot containers for each freq and add to dict.
            # dictionary will be used to access these later to individually
            # address them to turn them on or off etc.
            # note these are added with lowest freq on bottom
            for freq in self.model.freq_choices:
                hpc = self.create_hplot(key=freq)
                self.hplot_dict[freq] = hpc
                vpc.add(hpc)

        # add tool to freeze line inspector cursor when in desired position
        vpc.tools.append(self.inspector_freeze_tool)

        self.vplot_container = vpc
        self.set_hplot_visibility(all=True)
        self.set_intensity_profile_visibility()

    def set_hplot_visibility(self, all=False):
        ''' to be called when selected hplots are changed
        For selected hplots set the hplot, legend, and axis visibility'''
        if all:
            self.selected_hplots = self.model.freq_choices

        # get sorted list of hplots to add on top of mini
        sorted_hplots = [f for f in self.model.freq_choices
                         if f in self.selected_hplots]

        if sorted_hplots:
            bottom = sorted_hplots[0]
            top = sorted_hplots[-1]
            for freq, hpc in self.hplot_dict.items():
                hpc.visible = ((freq in sorted_hplots) or (freq == 'mini'))
                main = hpc.components[0]
                if freq == bottom or freq == 'mini':
                    main.x_axis.visible = True
                    hpc.padding_bottom = HPLOT_PADDING_BOTTOM
                else:
                    main.x_axis.visible = False
                    hpc.padding_bottom = HPLOT_PADDING_BOTTOM

                legend, highlighter = self.legend_dict.get(freq, [None, None])
                if legend:
                    legend.visible = (freq == top)

        else:
            logger.info('no hplot containers')

        self.reset_all()

    def reset_all(self):
        for k, hpc in self.hplot_dict.items():
            if k != 'mini':
                profile = hpc.components[1]
                main = hpc.components[0]
                profile.visible = False
                main.visible = False
                hpc.visible = False
                hpc.invalidate_and_redraw()

        for k, hpc in self.hplot_dict.items():
            if k != 'mini':
                profile = hpc.components[1]
                main = hpc.components[0]
                if k in self.selected_hplots:
                    main.visible = True
                    profile.visible = self.show_intensity_profiles
                    hpc.visible = True
                hpc.invalidate_and_redraw()
        self.vplot_container.invalidate_and_redraw()

    def set_intensity_profile_visibility(self, show=True):
        ''' sets intensity profile visibility for all hplots '''
        self.reset_all()

    def create_hplot(self, key=None, mini=False):
        if mini:
            hpc = HPlotContainer(bgcolor='darkgrey',
                                 height=MINI_HEIGHT,
                                 resizable='h',
                                 padding=HPLOT_PADDING
                                 )
        else:
            hpc = HPlotContainer(bgcolor='lightgrey',
                                 padding=HPLOT_PADDING,
                                 resizable='hv'
                                 )

        # make slice plot for showing intesity profile of main plot
        #************************************************************
        slice_plot = Plot(self.data,
                          width=SLICE_PLOT_WIDTH,
                          orientation="v",
                          resizable="v",
                          padding=MAIN_PADDING,
                          padding_left=MAIN_PADDING_LEFT,
                          padding_bottom=MAIN_PADDING_BOTTOM,
                          bgcolor='beige',
                          origin='top left'
                          )
        mini_slice = Plot(self.data,
                          width=SLICE_PLOT_WIDTH,
                          orientation="v",
                          resizable="v",
                          padding=MAIN_PADDING,
                          padding_left=MAIN_PADDING_LEFT,
                          padding_bottom=MAIN_PADDING_BOTTOM,
                          bgcolor='beige',
                          origin='top left'
                          )
        slice_plot.x_axis.visible = True
        slice_key = key + '_slice'
        ydata_key = key + '_y'
        slice_plot.plot((ydata_key, slice_key), name=slice_key)

        # make plot to show line at depth of cursor.  y values constant
        slice_depth_key = key + '_depth'
        slice_plot.plot(('slice_depth_depth', 'slice_depth_y'),
                        name=slice_depth_key, color='red')
        self.update_slice_depth_line_plot(slice_plot, depth=0)

        # make main plot for editing depth lines
        #************************************************************
        main = Plot(self.data,
                    border_visible=True,
                    bgcolor='beige',
                    origin='top left',
                    padding=MAIN_PADDING,
                    padding_left=MAIN_PADDING_LEFT,
                    padding_bottom=MAIN_PADDING_BOTTOM
                    )
        if mini:
            #main.padding = MINI_PADDING
            main.padding_bottom = MINI_PADDING_BOTTOM

        # add intensity img to plot and get reference for line inspector
        #************************************************************
        img_plot = main.img_plot(key, name=key,
                                 xbounds=self.model.xbounds[key],
                                 ybounds=self.model.ybounds[key],
                                 colormap=self._cmap
                                 )[0]

        # add line plots: use method since these may change
        #************************************************************
        self.update_line_plots(key, main, update=True)
        self.plot_mask_array(key, main)

        # set slice plot index range to follow main plot value range
        #************************************************************
        slice_plot.index_range = main.value_range

        # add vertical core lines to main plots and slices
        #************************************************************
        # save pos and distance in session dict for view info and control
        for core in self.model.core_samples:
            # add boundarys to slice plot
            self.plot_core_depths(slice_plot, core, ref_depth_line=None)
            # add positions to main plots
            self.plot_core(main, core, ref_depth_line=None)

        # now add tools depending if it is a mini plot or not
        #************************************************************
        if mini:
            # add range selection tool only
            # first add a reference line to attach it to
            reference = self.make_reference_plot()
            main.add(reference)
            main.plots['reference'] = [reference]
            # attache range selector to this plot
            range_tool = RangeSelection(reference)
            reference.tools.append(range_tool)
            range_overlay = RangeSelectionOverlay(reference,
                                                  metadata_name="selections")
            reference.overlays.append(range_overlay)
            range_tool.on_trait_change(self._range_selection_handler,
                                       "selection")
            # add zoombox to mini plot
            main.plot(('zoombox_x', 'zoombox_y'), type='polygon',
                      face_color=ZOOMBOX_COLOR, alpha=ZOOMBOX_ALPHA)
            # add to hplot and dict
            hpc.add(main, mini_slice)
            self.hplot_dict['mini'] = hpc

        else:
            # add zoom tools
            zoom = ZoomTool(main, tool_mode='box', axis='both', alpha=0.5,
                            drag_button="left")
            main.tools.append(zoom)
            main.overlays.append(zoom)
            self.zoom_tools[key] = zoom
            main.value_mapper.on_trait_change(self.zoom_all_value, 'updated')
            main.index_mapper.on_trait_change(self.zoom_all_index, 'updated')
            
            # add line inspector and attach to freeze tool
            #*********************************************
            line_inspector = LineInspector(component=img_plot,
                                           axis='index_x',
                                           inspect_mode="indexed",
                                           is_interactive=True,
                                           write_metadata=True,
                                           metadata_name='x_slice',
                                           is_listener=True,
                                           color="white")

            img_plot.overlays.append(line_inspector)
            self.inspector_freeze_tool.tool_set.add(line_inspector)

            # add listener for changes to metadata made by line inspector
            #************************************************************
            img_plot.on_trait_change(self.metadata_changed, 'index.metadata')

            # set slice plot index range to follow main plot value range
            #************************************************************
            slice_plot.index_range = main.value_range

            # add clickable legend ; must update legend when depth_dict updated
            #******************************************************************
            legend = Legend(component=main, padding=0,
                            align="ur", font='modern 8')
            legend_highlighter = LegendHighlighter(legend,
                                                   drag_button="right")
            legend.tools.append(legend_highlighter)
            self.legend_dict[key] = [legend, legend_highlighter]
            self.update_legend_plots(legend, main)
            legend.visible = False
            main.overlays.append(legend)
            legend_highlighter.on_trait_change(self.legend_moved, '_drag_state')

            # add pan tool
            pan_tool = PanTool(main, drag_button="right")
            main.tools.append(pan_tool)
            self.pan_tool_dict[key] = pan_tool

            # add main and slice plot to hplot container and dict
            #****************************************************
            main.title = 'frequency = {} kHz'.format(key)
            main.title_font = TITLE_FONT
            hpc.add(main, slice_plot)
            self.hplot_dict[key] = hpc

        return hpc

    def legend_moved(self, new):
        logger.debug('legend moved {}'.format(new))
        self.legend_drag = new

    def update_legend_plots(self, legend, plot):
        ''' update legend if lines added or changed
        use depth_dict as key source since we only want depth lines'''
        legend.plots = {}
        for k in self.model.depth_dict:
            legend.plots[k] = plot.plots[k]

    def disable_pan(self, action):
        ''' adds or removes pan from main plots depending on toolbar icon
        state
        '''
        logger.debug('pan disable action is {}'.format(action.checked))
        mains = [(key, h.components[0]) for key, h in self.hplot_dict.items()
                 if key != 'mini']
        for key, main in mains:
            pantool = self.pan_tool_dict[key]
            if action.checked:
                # remove pan
                if pantool in main.tools:
                    main.tools.remove(pantool)
            else:
                if pantool not in main.tools:
                    main.tools.append(pantool)


    def update_all_line_plots(self, update=False):
        ''' reload all line plots when added or changed.
        updates all hplot containers and legends.
        calls "update_line_plots" for each hplot'''
        for key in self.model.freq_choices:
            hpc = self.hplot_dict[key]
            plot = hpc.components[0]
            self.update_line_plots(key, plot, update=update)
            legend, highlighter = self.legend_dict[key]
            self.update_legend_plots(legend, plot)
            legend_highlighter = LegendHighlighter(legend,
                                                   drag_button="right")
            if highlighter in legend.tools:
                legend.tools.remove(highlighter)
            legend_highlighter.on_trait_change(self.legend_moved, '_drag_state')
            legend.tools.append(legend_highlighter)
            plot.invalidate_and_redraw()

    def update_slice_depth_line_plot(self, slice_plot=None, depth=0):
        ''' this updates the depth data for the slice depth indicator
        line in the slice plot.  This can be called by any source that
        can get the depth (currently updated by the depth tool)'''
        if slice_plot:
            full_range = slice_plot.value_range
            y_range = np.array([full_range.low, full_range.high])
            self.data.update_data(slice_depth_y=y_range)
        depth_values = np.array([depth, depth])
        self.data.update_data(slice_depth_depth=depth_values)

    def plot_mask_array(self, key, main):
        ''' adds filled line plot to this Plot container showing mask
        data comes from survey_line.  Usually empty until someone
        edits bad points.  Then the x data is distance array and
        y data is mask * y_max '''
        plot_key = key + '_mask'
        if self.model.survey_line.masked:
            x, y = self.model.get_mask_xy()
            self.data.update_data(mask_x=x, mask_y=y)
        mask_plot = main.plot(('mask_x', 'mask_y'),
                              type='filled_line',
                              name=plot_key,
                              edge_color=MASK_EDGE_COLOR,
                              face_color=MASK_FACE_COLOR,
                              alpha=MASK_ALPHA)[0]
        self.plot_dict[plot_key] = mask_plot

    def update_line_plots(self, key, plot, update=False):
        ''' Updates all Line plots on ONE plot container.
        takes a Plot object and adds all available line plots to it.
        Each Plot.plots has one img plot labeled by freq key and the rest are
        line plots.  When depth_dict is updated, check all keys to see all
        lines are plotted.  Update=True will replot all lines even if already
        there (for style changes)'''
        lineplots = [item for item in  plot.plots.items() if
                     (item[0].startswith('PRE') or item[0].startswith('POST'))]
        for line_key, line_plot in lineplots:
            line_plot_deleted = line_key not in self.model.depth_dict.keys()
            if line_plot_deleted:
                # remove from plot dict
                plot_key = key + '_' + line_key
                self.plot_dict.pop(plot_key)
                # remove from plot
                plot.delplot(line_key)

        for line_key, depth_line in self.model.depth_dict.items():
            not_plotted = line_key not in plot.plots
            not_image = line_key not in self.model.freq_choices
            if (not_plotted or update) and not_image:
                line_plot = self.plot_depth_line(key, line_key,
                                                 depth_line, plot)
                # note: plot dict needs 3 entries for every line since each
                # freq has a copy using the same plotdata source
                plot_key = key + '_' + line_key
                self.plot_dict[plot_key] = line_plot

    def plot_depth_line(self, key, line_key, depth_line, plot):
        ''' plot a depth_line using a depth line object'''

        # add data to ArrayPlotData if not there
        if line_key not in self.data.arrays.keys():
            x = self.model.distance_array[depth_line.index_array]
            y_raw = depth_line.depth_array
            # limit range of plot to ybounds of image/model
            ybounds = self.model.ybounds[key]
            y = np.clip(y_raw, *ybounds)
            key_x, key_y = line_key + '_x', line_key + '_y'
            self.data.update({key_x: x, key_y: y})

        # now plot
        line_plot = plot.plot((key_x, key_y),
                              color=depth_line.color,
                              name=line_key
                              )[0]
        # match vertical to ybounds in case there are pathological points
        line_plot.value_range = plot.plots[key][0].index_range.y_range

        return line_plot

    def make_reference_plot(self):
        ''' make reference plot for mini plot range selector'''
        x_pts = np.array([self.model.distance_array.min(),
                          self.model.distance_array.max()
                          ]
                         )

        y_pts = 0 * x_pts
        ref_plot = create_scatter_plot((x_pts, y_pts), color='black')
        return ref_plot

    #==========================================================================
    # Notifiers and Handlers
    #==========================================================================

    @on_trait_change('model')
    def update(self):
        ''' make new vplot when a new survey line is selected'''
        self.create_vplot()

    def zoom_all_value(self, obj, name, old, new):
        ''' gets value_mapper object from notification'''
        low, high = obj.range.low, obj.range.high
        # change y values of zoombox in mini
        self.data.update_data(zoombox_y=np.array([low, low, high, high]))
        for key, hpc in self.hplot_dict.items():
            if key != 'mini':
                vmapper = hpc.components[0].value_mapper
                if vmapper.range.low != low:
                    vmapper.range.low = low
                if vmapper.range.high != high:
                    vmapper.range.high = high

    def zoom_all_index(self, obj, name, old, new):
        ''' gets index_mapper object from notification'''
        low, high = obj.range.low, obj.range.high
        # change x values of zoombox
        self.data.update_data(zoombox_x=np.array([low, high, high, low]))
        for key, hpc in self.hplot_dict.items():
            if key != 'mini':
                mapper = hpc.components[0].index_mapper
                if mapper.range.low != low:
                    mapper.range.low = low
                if mapper.range.high != high:
                    mapper.range.high = high

    def _range_selection_handler(self, event):
        ''' updates the main plots when the range selector in the mini plot is
        adjusted.  The event obj should be a tuple (low, high) in data space
        '''
        if event is not None:
            #adjust index range for main plots
            low, high = event
            for key, hpc in self.hplot_dict.items():
                if key != 'mini':
                    this_plot = hpc.components[0]
                    this_plot.index_range.low = low
                    this_plot.index_range.high = high
        else:
            # reset range back to full/auto for main plots
            for key, hpc in self.hplot_dict.items():
                if key != 'mini':
                    this_plot = hpc.components[0]
                    this_plot.index_range.set_bounds("auto", "auto")

    def metadata_changed(self, obj, name, old, new):
        ''' handler for line inspector tool.
        provides changed "index" trait of intensity image whose meta data
        was changed by the line inspector.  The line inspector sets the
        "x_slice" key in the meta data.  We then retrieve this and use it
        to update the metadata for the intensity plots for all freqs'''
        selected_meta = obj.metadata
        slice_meta = selected_meta.get("x_slice", None)
        for key, hplot in self.hplot_dict.items():
            if key != 'mini':
                self.update_hplot_slice(key, hplot, slice_meta)

    def update_hplot_slice(self, key, hplot, slice_meta):
        ''' when meta data changes call this with relevant hplots to update
        slice from cursor position'''

        slice_key = key + '_slice'
        img = hplot.components[0].plots[key][0]

        # get slice plot and sinc the value to the img plot
        slice = hplot.components[1]
        low, high = img.value_range.low, img.value_range.high
        slice.value_range.low_setting = low
        slice.value_range.high_setting = high
        self.data.set_data('slice_depth_y', np.array([low, high]))

        if slice_meta:    # set metadata and data

            # check hplot img meta != new meta. if !=, change it.
            # this will update tools for other frequencies
            this_meta = img.index.metadata
            if this_meta.get('x_slice', None) is not slice_meta:
                this_meta.update({"x_slice": slice_meta})

            x_index, y_index = slice_meta
            try:
                if x_index:
                    # now updata data array which will updata slice plot
                    slice_data = img.value.data[:, x_index]
                    self.data.update_data({slice_key: slice_data})
                else:
                    self.data.update_data({slice_key: np.array([])})
            except IndexError:
                self.data.update_data({slice_key: np.array([])})

            # now get x position to see if we are close to a core
            try:
                # abs_index is the trace number for the selected image index
                if x_index:
                    abs_index = self.model.freq_trace_num[key][x_index] - 1
                else:
                    abs_index = 0
                x_pos = self.model.distance_array[abs_index]
            except IndexError:
                # if for some reason the tool returns a crazy index then bound
                # it to array limits.
                logger.info('cursor index out of bounds: value set to limit')
                indices = self.model.freq_trace_num[key] - 1
                x_ind_max = indices.size - 1
                x_ind_clipped = np.clip(x_index, 0, x_ind_max)
                abs_index = indices[x_ind_clipped]
                x_pos = self.model.distance_array[abs_index]

            # check if cursor is 'near' core, and set visibility in sliceplot
            for core in self.model.core_samples:
                # show core if cursor within range of core location
                loc_index, loc, dist = self.model.core_info_dict[core.core_id]
                core_plot_list = self.core_plots_dict[core.core_id]
                for core_plot in core_plot_list:
                    try:
                        if np.abs(x_pos - loc) < CORE_VISIBILITY_CRITERIA:
                            core_plot.visible = True
                            self.model.current_core = [core.core_id, dist]
                        else:
                            core_plot.visible = False
                            self.model.current_core = [-1, -1]
                    except ValueError:
                        debug = 'core dist check xpos,loc,abs(x-l)\n={},{},{}'
                        absdiff = np.abs(x_pos - loc)
                        logger.debug(debug.format(x_pos[:3], loc, absdiff[:3]))

        else:   # clear all slice plots
            self.data.update_data({slice_key: np.array([])})

    def update_core_plots(self):
        for core in self.model.core_samples:
            old_core_layer_plots = self.core_plots_dict.pop(core.core_id)
            for key, hplot in self.hplot_dict.items():
                main = hplot.components[0]
                slice = hplot.components[1]
                self.plot_core(main, core, ref_depth_line=None)
                # since we are replotting all of the slice plot core layers
                # remove all existing plots from all slices
                # (stored in core_plot_dict)
                for old_plot in old_core_layer_plots:
                    if old_plot in slice.components:
                        slice.components.remove(old_plot)
                if key != 'mini':
                    self.plot_core_depths(slice, core, ref_depth_line=None)

    def plot_core(self, main, core, ref_depth_line=None):
        ''' plot core info on main plot'''
        logger.debug('replotting main cores')
        loc_index, loc, dist = self.model.core_info_dict[core.core_id]
        # first plot vertical line
        y_range = main.value_range
        ys = np.array([y_range.low, y_range.high])
        xs = ys * 0 + loc
        line = create_line_plot((xs, ys), color='lightgreen',
                                width=CORE_LINE_WIDTH)
        line.origin = 'top left'
        line.index_range = main.index_range
        main.add(line)
        # then plot boundary layers as dots on line
        if ref_depth_line is None:
            ref_depth_line = self.model.survey_line.core_depth_reference
        if ref_depth_line:
            ref_depth = ref_depth_line.depth_array[loc_index]
        else:
            ref_depth = 0
        layer_depths = core.layer_boundaries
        ys = ref_depth + layer_depths
        xs = ys * 0 + loc
        scatter = create_scatter_plot((xs, ys), color='darkgreen',
                                      marker='circle',
                                      marker_size=CORE_LINE_WIDTH + 1)
        scatter.origin = 'top left'
        scatter.value_range = main.value_range
        scatter.index_range = main.index_range
        old_scatter = main.plots.get('core_plot', [])
        if old_scatter:
            main.components.remove(old_scatter[0])
        main.add(scatter)
        main.plots['core_plot'] = [scatter]

    def plot_core_depths(self, slice_plot, core, ref_depth_line=None):
        ''' plot a set of core depths to the given slice plot
        set to not visible by default but then show when within
        show_core_range'''
        logger.debug('replotting slice cores')
        x_range = slice_plot.index_range
        xs = np.array([x_range.low, x_range.high])
        loc_index, loc, dist = self.model.core_info_dict[core.core_id]
        if ref_depth_line is None:
            ref_depth_line = self.model.survey_line.core_depth_reference
        if ref_depth_line:
            ref_depth = ref_depth_line.depth_array[loc_index]
        else:
            ref_depth = 0

        for boundary in core.layer_boundaries:
            ys = xs * 0 + (ref_depth + boundary)
            line = create_line_plot((xs, ys), orientation='h',
                                    color='lightgreen', width=CORE_LINE_WIDTH)
            line.origin = 'top left'
            line.value_range = slice_plot.index_range
            self.core_plots_dict.setdefault(core.core_id, []).append(line)
            slice_plot.add(line)

            # for i, boundary in enumerate(core.layer_boundaries):
            # core_layer_name = 'core_layer_{}'.format(i)
            # old_line = slice_plot.plots.get(core_layer_name, None)

            # if old_line:
            #     print old_line in slice_plot.components
            #     slice_plot.del_plot(core_layer_name)

            # print old_line in slice_plot.components, core_layer_name, slice_plot.plots.has_key(core_layer_name)
            # ys = xs * 0 + (ref_depth + boundary)
            # line = create_line_plot((xs, ys), orientation='h',
            #                         color='lightgreen', width=CORE_LINE_WIDTH)
            # line.origin = 'top left'
            # line.value_range = slice_plot.index_range
            # self.core_plots_dict.setdefault(core.core_id, []).append(line)
            # slice_plot.add(line)
            # slice_plot.plots[core_layer_name] = line

    def _img_colormap_changed(self):
        ''' updates colormap in images when img_colormap changes'''
        self._cmap = default_colormaps.color_map_name_dict[self.img_colormap]
        for key, hpc in self.hplot_dict.items():
            main = hpc.components[0]
            if key == 'mini':
                key = self.model.freq_choices[-1]
            img_plot = main.plots[key][0]
            if img_plot is not None:
                value_range = img_plot.color_mapper.range
                img_plot.color_mapper = self._cmap(value_range)
            main.invalidate_and_redraw()


class ControlView(HasTraits):
    ''' Define controls and info subview with size control'''
    ''' Allows user to set/view certain survey line attributes'''

    # survey data session object
    model = Instance(SurveyDataSession)

    target_choices = Property(depends_on='model.depth_lines_updated')

    # used to explicitly get edit mode
    edit = Enum('Editing', 'Not Editing', 'Mark Bad Data')

    # records current sub-mode of Mark Bad Data edit mode.  Toggle with buttons
    # this can also be toggled by tool with t key. watched by main pane to
    # change tool.
    mark_bad_data_mode = Enum('off', 'Mark', 'Unmark')

    # button event to toggle state editing state of Bad Data Edit
    bad_data_mode_toggle = Event

    # provide to disable editing if zoom icon is enabled
    zoom_checked = Bool(False)

    traits_view = View(
        VGroup(
            HGroup(
                UItem('edit',
                      tooltip='select editing depthline, or editing bad ',
                      enabled_when='not zoom_checked'
                ),
                Item('object.model.selected_target',
                     editor=EnumEditor(name='target_choices'),
                     tooltip='Edit red line with right mouse button',
                     visible_when='edit=="Editing"'
                ),
                UItem('bad_data_mode_toggle',
                      editor=ButtonEditor(label='Marking as bad'),
                      tooltip='click again to set to unmark mode',
                      visible_when='mark_bad_data_mode=="Mark"'
                ),
                UItem('bad_data_mode_toggle',
                      editor=ButtonEditor(label='Unmarking bad data'),
                      tooltip='click again to set to mark mode',
                      visible_when='mark_bad_data_mode=="Unmark"'
                ),
                Item('object.model.status'),
                Item('object.model.status_string', label='Comment',
                     editor=TextEditor(auto_set=False)),
            ),
            HGroup(
                Item('object.model.final_lake_depth',
                     editor=EnumEditor(name='object.model.lake_depth_choices')),
                Item('object.model.final_preimpoundment_depth',
                     editor=EnumEditor(name='object.model.preimpoundment_depth_choices')),
                Item('object.model.survey_line.core_depth_reference_str',
                     editor=EnumEditor(name='object.model.core_reference_choices'))
            )
        ),
        resizable=True
    )

    def _anytrait_changed(self, name, old, new):
        logger.debug('CONTROL_VIEW_trait changed: {}'.format((name, old, new)))

    def _edit_default(self):
        return 'Not Editing'

    def _bad_data_mode_toggle_fired(self):
        self.toggle_mark_bad_data_mode()

    def toggle_mark_bad_data_mode(self):
        if self.mark_bad_data_mode == 'Mark':
            self.mark_bad_data_mode = 'Unmark'
        elif self.mark_bad_data_mode == 'Unmark':
            self.mark_bad_data_mode = 'Mark'

    def _edit_changed(self):
        if self.edit == 'Mark Bad Data':
            self.mark_bad_data_mode = 'Unmark'
            self.bad_data_mode_toggle = True
        elif self.edit == 'Not Editing':
            self.mark_bad_data_mode = 'off'
        else:
            self.mark_bad_data_mode = 'off'

    def _get_target_choices(self):
        ''' returns list of available depth lines with "none" prepended
        '''
        if self.model:
            choices = ['None'] + self.model.target_choices
        if CURRRENT_SURFACE_FROM_BIN_LABEL in choices:
            choices.remove(CURRRENT_SURFACE_FROM_BIN_LABEL)
        self.model.selected_target = 'None'
        return choices or ['None']


class LineSettingsView(HasTraits):
    ''' Allows user to set/view certain survey line attributes'''
    model = Instance(SurveyDataSession)

    traits_view = View(
        Label('View or Set current final depth line choices for this survey' +\
              ' line'),
        Item('object.model.final_lake_depth',
             editor=EnumEditor(name='object.model.lake_depth_choices')),
        Item('object.model.final_preimpoundment_depth',
             editor=EnumEditor(name='object.model.preimpoundment_depth_choices')),
        Label('View or Set status and comment for this survey line'),
        Item('object.model.status'),
        Item('object.model.status_string'),
        resizable=True,
        kind='live',
        buttons=['Cancel', 'OK']
    )


class ImageAdjustView(HasTraits):
    # brightness contrast controls
    freq_choices = List
    frequency = Str
    brightness = Float(0.0)
    contrast = Float(1.0)
    contrast_brightness = Property(depends_on=['brightness', 'contrast'])
    invert = Bool

    traits_view = View(
        Label('Frequency to Edit'),
        UItem('frequency', editor=EnumEditor(name='freq_choices')),
        Label('Brightness and Contrast'),
        Item('brightness', editor=RangeEditor(low=0.0, high=1.0), label='B'),
        Item('contrast',
             editor=RangeEditor(low=1.0, high=CONTRAST_MAX), label='C'),
        Item('invert'),
        resizable=True,
        kind='livemodal'
    )

    def _get_contrast_brightness(self):
        return (self.contrast, self.brightness)


class HPlotSelectionView(HasTraits):
    ''' provide checkbox pop up to set visibilty of hplots'''

    # hplots/freqs visible in main vplotcontainer. Set by checkbox.
    hplot_choices = Tuple
    visible_frequencies = List

    # show intensity profiles on the side or not
    intensity_profile = Bool

    traits_view = View(Label('Select Frequencies to View'),
                       UItem('visible_frequencies',
                             editor=CheckListEditor(name='hplot_choices'),
                             style='custom'
                             ),
                       Label('Show Intensity Profiles'),
                       UItem('intensity_profile'),
                       kind='livemodal',
                       resizable=True
                       )


class DataView(HasTraits):
    ''' Show location data as cursor moves about'''

    # latitude, longitude for current cursor
    latitude = Float(0)
    longitude = Float(0)

    # latitude, longitude for current cursor
    easting = Float(0)
    northing = Float(0)

    # depth of current mouse position
    depth = Float(0)

    # power & gain at current cursor
    power = CFloat(0)
    gain = CFloat(0)

    # id and distance of current core shown in slice view
    core_id = CFloat(-1)
    core_distance = CFloat(-1)

    traits_view = View(
        Item('latitude'),
        Item('longitude'),
        Item('_'),
        Item('easting'),
        Item('northing'),
        Item('_'),
        Item('depth'),
        Item('_'),
        Item('power'),
        Item('gain'),
        Item('_'),
        Item('core_id'),
        Item('core_distance'),
        resizable=True
    )


class MsgView(HasTraits):
    msg = Str('my msg')
    traits_view = View(Item('msg', editor=TextEditor(), style='custom'),
                       buttons=['OK', 'Cancel'],
                       kind='modal',
                       resizable=True
                       )


if __name__ == '__main__':
    pass
