#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

from __future__ import absolute_import

# 3rd party imports
import numpy as np

# ETS imports
from chaco.api import (ArrayPlotData, ArrayDataSource, LinearMapper,
                       Plot, PolygonPlot)
from chaco.tools.api import PanTool, ZoomTool
from enable.component_editor import ComponentEditor
from traits.api import Float, Instance, List, Property, Str
from traitsui.api import View, Item, ModelView, InstanceEditor, HSplit

# local imports
from hydropick.model.i_survey import ISurvey
from hydropick.ui.line_select_tool import LineSelectTool


class SurveyMapView(ModelView):
    """ View Class for working with survey line data to find depth profile.

    Uses a Survey class as a model and allows for viewing of various depth
    picking algorithms and manual editing of depth profiles.
    """
    #: The current survey
    model = Instance(ISurvey)

    # TODO: this will be a list of surveys instead of geometries
    #: Survey lines
    lines = Property(List)

    def _get_lines(self):
        return [line.navigation_line for line in self.model.survey_lines]

    #: the plot objects for each survey line
    line_plots = List

    #: This should fix the x and y scale to maintain aspect ratio
    #: (not yet implemented)
    aspect_ratio = Float(1.0)

    #: Color to draw the lake
    lake_color = Str('lightblue')

    #: Color to draw the land
    land_color = Str('khaki')

    #: Color to draw the shoreline
    shore_color = Str('black')

    #: Color to draw the survey lines
    line_color = Str('blue')

    #: The Chaco plot object
    plot = Property(Instance(Plot), depends_on='model')

    def _get_plot(self):
        plotdata = ArrayPlotData()
        plot = Plot(plotdata,
                    auto_grid=False,
                    bgcolor=self.land_color)
        plot.x_axis.visible = False
        plot.y_axis.visible = False
        plot.padding = (0, 0, 0, 0)
        plot.border_visible = False
        index_mapper = LinearMapper(range=plot.index_range)
        value_mapper = LinearMapper(range=plot.value_range)
        # XXX: want to fix the pixel aspect ratio, not the window aspect ratio
        #plot.aspect_ratio = self.aspect_ratio
        if self.model.lake is not None:
            for num, l in enumerate(self.model.lake.shoreline):
                line = np.array(l.coords)
                x = line[:,0]
                y = line[:,1]
                polyplot = PolygonPlot(index=ArrayDataSource(x),
                                       value=ArrayDataSource(y),
                                       edge_color=self.shore_color,
                                       face_color=self.lake_color,
                                       index_mapper=index_mapper,
                                       value_mapper=value_mapper)
                plot.add(polyplot)
        for num, l in enumerate(self.lines):
            line = np.array(l.coords)
            x = line[:,0]
            y = line[:,1]
            x_key = 'x-line' + str(num)
            y_key = 'y-line' + str(num)
            plotdata.set_data(x_key, x)
            plotdata.set_data(y_key, y)
            self.line_plots.append(plot.plot((x_key, y_key),
                                             color=self.line_color))
        plot.tools.append(PanTool(plot))
        plot.tools.append(ZoomTool(plot))
        plot.tools.append(LineSelectTool(plot, line_plots=self.line_plots))
        return plot

