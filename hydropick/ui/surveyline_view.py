#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

from __future__ import absolute_import
# Std lib imports
import sys
# other imports
import numpy as np

# ETS imports
from enable.api import ComponentEditor
from traits.api import Instance, Enum, DelegatesTo, Str, Property, Dict, List, Tuple, Int, Set

from traitsui.api import ModelView, View, Item, ToolBar, EnumEditor, Group, HGroup,HGroup,UItem,InstanceEditor, VGroup, CheckListEditor, HSplit
from traitsui.menu import Action, OKCancelButtons, StandardMenuBar
from chaco.api import Plot, ArrayPlotData, jet, PlotAxis, create_scatter_plot,\
                        create_line_plot, LinePlot, Legend, PlotComponent, Greys

from chaco.tools.api import PanTool, ZoomTool, LegendTool
from pyface.api import ImageResource

# Local imports
from .surveydatasession import SurveyDataSession
from .surveytools import TraceTool, LocationTool
from .surveyviews import ControlView, BigView, InstanceUItem, PlotContainer

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

    # Defines view for all the plot controls and info. Sits by plot container.
    control_view = Instance(ControlView)

    # Dictionary of plots kept for legend and for tools.
    # Will contain all depth lines at least.  This contains components as
    # opposed to the depth_dict{str:array} in the model.
    plot_dict = Dict(Str, PlotComponent, value={})

    # Custom tool for editing depth lines
    trace_tool = Instance(TraceTool)

    location_tool = Instance(LocationTool)

    # List of which lines are visible in plots
    visible_lines = List([])

    # plotdata is the ArrayPlotData instance holding the plot data.
    # for now it contains available images and multiple line plots for depths.
    plotdata = Instance(ArrayPlotData)

    # Pair of combined plots:  main for editing; mini for scanning
    mainplot = Instance(Plot)
    miniplot = Instance(Plot)
    mini_height = Int(100)

    #==========================================================================
    # Define View
    #==========================================================================

    traits_view = View(
        HSplit(
            InstanceUItem('plot_container'),
            InstanceUItem('control_view', width=150),
        ),
        resizable=True,
    )

    #==========================================================================
    # Defaults
    #==========================================================================

    def _plot_dict_default(self):
        ''' To be filled by plot methods'''
        return {}

    def _plot_container_default(self):
        linedict = self.model.depth_dict
        self.mainplot = self.make_plot()
        self.mainplot.y_axis.title = 'Depth (m)'
        self.miniplot = self.make_plot(height=self.mini_height)
        self.miniplot.x_axis.title = 'Distance (m)'
        contnr = PlotContainer(mainplot= self.mainplot, miniplot= self.miniplot)
        if self.model.depth_dict:
            self.add_lines(**self.model.depth_dict)
        if self.model.frequencies:
            self.add_images(**self.model.frequencies)
        return contnr

    def _control_view_default(self):
        ''' Creates ControlView object filled with associated traits'''

        cv = ControlView(target_choices=self.model.target_choices,
                         line_to_edit=self.model.selected_target,
                         visible_lines= [],        ###self.visible_lines,
                         freq_choices=self.model.freq_choices,
                         image_freq=self.model.selected_freq,
                         latitude = self.model.E_N_positions[50][0],
                         longitude = self.model.E_N_positions[50][1]
                         )
        # set default values for widgets
        cv.visible_lines = self.model.target_choices###
        cv.image_freq = self.model.selected_freq

        # Add notifications
        cv.on_trait_change(self.select_line, name='visible_lines')
        cv.on_trait_change(self.change_target, name='line_to_edit')
        cv.on_trait_change(self.change_image, name='image_freq')
        return cv

    def _plotdata_default(self):
        ''' Provides initial plotdata object'''
        if self.model.x_array.any():
            return ArrayPlotData(x_array=self.model.x_array)
        else:
            return ArrayPlotData()

    def _trace_tool_default(self):
        ''' Sets up trace tool for editing lines'''
        tool =  TraceTool(self.mainplot)
        tool.on_trait_change(self.update_depth, 'depth')
        self.mainplot.tools.append(tool)
        return tool

    #==========================================================================
    # Helper functions
    #==========================================================================

    def add_lines(self,**kw):
        ''' Take arbitrary number of key=array pairs.
        Adds them to
        self.plotdata then self.depth_dict,
        adds them to mainplot and miniplot,
        adds the comonents to self.plot_dict'''
        for key, array in kw.items():
            self.plotdata.set_data(key, array)
        self.model.depth_dict.update(kw)
        self.update_main_mini_lines(kw.keys())


    def add_images(self,**kw):
        ''' Adds images same way as lines to plotdata and plots first one
        '''
        for key, array in kw.items():
            print 'adding image',key
            self.plotdata.set_data(key, array)
        self.model.frequencies.update(kw)
        imagelist = [kw.keys()[0]]
        self.update_main_mini_image(imagelist)

    def make_plot(self, height=None):
        ''' Creates one Plot instance with all depthlines and one image plot.
        Used for mainplot and miniplot to make identical plots apart from
        height.
        '''

        plot = Plot(self.plotdata,
                    border_visible=True,
                    bgcolor="white",
                    padding=0,
                    origin ='top left'
                    )
        if height:
            plot.height=height
            plot.resizable='h'

        return plot

    def update_main_mini_lines(self, keylist=[]):
        ''' Add specified lineplots already in self.plotdata to both plots
        Assumes x_array from model.x_array is already in plotdata as well.
        '''
        main = self.mainplot
        mini = self.miniplot
        for key in keylist:
            newplot = main.plot(('x_array',key), color='blue', name=key)
            self.plot_dict[key] = newplot[0]
            mini.plot(('x_array',key), color='blue', name=key)


    def update_main_mini_image(self, keylist=[], remove=None):
        ''' Add specified image plots from self.plotdata to both plots.
        Should be done after lineplots to set plot axis ranges automatically
        '''
        main = self.mainplot
        mini = self.miniplot
        for key in keylist:
            print 'key is ',key,
            newplot = main.img_plot(key, colormap=Greys,
                                    xbounds=self.model.xbounds,
                                    ybounds=self.model.ybounds,
                                    name=key)
            # self.location_tool = LocationTool(newplot[0])
            # newplot[0].tools.append(self.location_tool)
            self.trace_tool.image = newplot[0]
            self.location_tool = LocationTool(newplot[0])
            self.location_tool.on_trait_change(self.update_locations,
                                               'image_index')
            newplot[0].tools.append(self.location_tool)

            self.plot_dict[key] = newplot[0]
            mini.img_plot(key, colormap=Greys,
                          xbounds=self.model.xbounds,
                          ybounds=self.model.ybounds,
                          name=key)
        if remove:
            component1 = mini.plots.pop(remove)[0]
            component2 = main.plots.pop(remove)[0]
        self.mainplot.invalidate_and_redraw()

    #==========================================================================
    # Get/Set methods
    #==========================================================================

    #==========================================================================
    # Notifications
    #==========================================================================

    def update_locations(self, image_index):
        cv = self.control_view
        lat, long = self.model.locations[image_index]
        east, north = self.model.E_N_positions[image_index]
        cv.latitude =lat
        cv.longitude = long
        cv.easting = east
        cv.northing = north

    def update_depth(self, depth):
        self.control_view.depth = depth

    def change_target(self, object, name, old, new_target):
        # update trace tool target line attribute.
        print 'new target name is ', new_target
        new_target_line = self.plot_dict[new_target]
        new_target_line.color = 'red'
        old_target_line = self.plot_dict.get(old, None)
        if old_target_line:
            old_target_line.color = 'blue'
        # make selected plot visible
        if new_target not in self.control_view.visible_lines:
            newset = set(self.control_view.visible_lines).union(set([new_target]))
            self.control_view.visible_lines=list(newset)
        self.mainplot.invalidate_and_redraw()
        self.trace_tool.target_line = new_target_line

    def change_image(self, object, name, old, new):
        # update trace tool target line attribute.
        print 'new image name is ', new
        if old in self.plot_dict:
            self.update_main_mini_image([new],remove=old)
        else:
            self.update_main_mini_image([new])

    def select_line(self,object, name, old, visible_lines):
        ''' Called when controlview.visible_lines changes in order to actually
        change the visibility of the lines.  Need to make sure the new list
        includes the selected lines which means if someone unchecks it we have
        to not only make it visible but add it to visible lines which will
        re-call this method'''

        print 'visible depthlines changed ************* '
        newset = set(visible_lines)
        cv = self.control_view

        if cv.line_to_edit:
            # If there is line to edit, make sure its in visible lines list.
            # Temporarily disable notification so we don't re-call this method.
            fullset = newset.union(set([cv.line_to_edit]))
            cv.on_trait_change(self.select_line, name='visible_lines', remove=True)
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



if __name__ == "__main__":
    datasession = SurveyDataSession()
    print 'datasession object=',datasession
    print 'starting GUI'
    window = SurveyLineView(model=datasession)
    window.configure_traits()

    #import ipdb; ipdb.set_trace()
