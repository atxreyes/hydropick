""" View definitions for controlling layout of survey line editor task

Views are:
*BigView:
    Sets overall layout with Controls on left and Plots on right and
    datafile selector on top.
*PlotView:
    Sets plot view which may be just the plot component and legend.
*ControlView:
    Set layout of controls and information displays
"""
# Std lib imports

# other imports
import numpy as np

# ETS imports
from enable.api import ComponentEditor
from traits.api import Instance, Enum, DelegatesTo, Str, Property, Dict, List, HasTraits, File
from traitsui.api import ModelView, View, Item, ToolBar, EnumEditor, Group, HGroup,UItem,InstanceEditor, VGroup, CheckListEditor, HSplit
from traitsui.menu import Action, OKCancelButtons, StandardMenuBar
from chaco.api import Plot, ArrayPlotData, jet, PlotAxis, create_scatter_plot,\
     create_line_plot, LinePlot, Legend, PlotComponent, VPlotContainer, CMapImagePlot, ScatterPlot, ColorBar, LinearMapper, HPlotContainer
from chaco.tools.api import PanTool, ZoomTool, LegendTool, RangeSelection, \
                            RangeSelectionOverlay
from pyface.api import ImageResource

# Local imports
from surveydatasession import SurveyDataSession
from surveytools import TraceTool

class InstanceUItem(UItem):
    '''Convenience class for inluding instance in view as Item'''

    style = Str('custom')
    editor = Instance(InstanceEditor,())

class PlotView(HasTraits):
    ''' Define plot subview with size control'''
    legend = Str('legend')
    plot = Instance(Plot)
    traits_view = View(
                 UItem('plot', editor=ComponentEditor()),
                 HGroup(Item('legend')),
                 resizable=True
        		 )

class PlotContainer(HasTraits):
    ''' miniplot must have at least one plot with an index.
        therefore there should be a check in the plot dictionary
        that there is a plot with an index
    '''

    #==========================================================================
    # Traits Attributes
    #==========================================================================

    # These two plots should have the same data.  The miniplot will provide a
    # continuous full view of data set.
    mainplot = Instance(Plot)
    miniplot = Instance(Plot)
    # Vplotcontainer will have mmainplot on top for working and small miniplot
    # below for reference
    plotcontainer = Instance(VPlotContainer)

    # View for the plot container
    traits_view = View(UItem('plotcontainer', editor=ComponentEditor()))

    #==========================================================================
    # Defaults
    #==========================================================================

    def _mainplot_default(self):
        return self.default_plot()

    def _miniplot_default(self):
        return self.default_plot()

    def default_plot(self):
        # Provides initial line plot to satisfy range tool.  Subsequent plots
        # should have at least one line plot
        y = np.arange(10)
        data = ArrayPlotData(x=x)
        plot = Plot(data)
        plot.plot(('y'))
        return plot


    # Add a range overlay to the miniplot that is hooked up to the range
    # of the main plot.

    def _plotcontainer_default(self):
        ''' Define plot container tools and look.
        '''
        self.mainplot.tools.append(PanTool(self.mainplot))#
        self.mainplot.tools.append(ZoomTool(self.mainplot,
                                            tool_mode='range',
                                            axis='value')
                                    )
        has_img = False
        if 'image plot' in self.mainplot.plots:
            has_img = True
            imgplot = self.mainplot.plots['image plot'][0]
            self.img_data = imgplot.value
            colormap = imgplot.color_mapper
            colorbar = ColorBar(index_mapper=LinearMapper(range=colormap.range),
                            color_mapper=colormap,
                            plot=imgplot,
                            orientation='v',
                            resizable='v',
                            width=30,
                            padding=20)

            colorbar.padding_top = self.mainplot.padding_top
            colorbar.padding_bottom = self.mainplot.padding_bottom

            # create a range selection for the colorbar
            range_selection = RangeSelection(component=colorbar)
            colorbar.tools.append(range_selection)
            colorbar.overlays.append(RangeSelectionOverlay(component=colorbar,
                                                           border_color="white",
                                                           alpha=0.8,
                                                           fill_color="lightgray"))

            # we also want to the range selection to inform the cmap plot of
            # the selection, so set that up as well
            range_selection.listeners.append(imgplot)
            #range_selection.on_trait_change(self.adjust_img, 'selection')

            # Create a container to position the plot and the colorbar side-by-side
            container = HPlotContainer(use_backbuffer = True)
            container.add(self.mainplot)
            container.add(colorbar)
            container.bgcolor = "lightgray"



        firstplot = self.a_plot_with_index()
        # connect plots with range tools
        if firstplot:
            range_tool = RangeSelection(firstplot)
            firstplot.tools.append(range_tool)
            range_overlay = RangeSelectionOverlay(firstplot, metadata_name="selections")
            firstplot.overlays.append(range_overlay)
            range_tool.on_trait_change(self._range_selection_handler, "selection")

        # add to container and fine tune spacing
        spacing = 25
        padding = 50
        width, height = (1000,600)
        plotcontainer = VPlotContainer(bgcolor = "lightgray",
                                     spacing = spacing,
                                     padding = padding,
                                     fill_padding=False,
                                     width=width, height=height,
                                     )
        if has_img:
            plotcontainer.add(self.miniplot, container)
        else:
            plotcontainer.add(self.miniplot, self.mainplot)

        return plotcontainer

    def a_plot_with_index(self):
        ''' Find first plot in data with an index or create one from img
        '''
        plots = self.miniplot.plots.values()
        indexplot = None
        imgplot = None
        for [plot] in plots:
            if isinstance(plot, LinePlot) or isinstance(plot, ScatterPlot):
                indexplot = plot

            elif isinstance(plot, CMapImagePlot):
                imgplot = plot
            if indexplot: break

        if not indexplot:
            if imgplot:
                Nxvalues = imgplot.value.get_data().shape[1]
                xvalues = np.arange(N)
                data = self.miniplot.data
                data.set_data('default plot', xvalues)
                plot = self.miniplot.plot(('default plot'))
            else:
                print 'NO SUITABLE PLOTS'
        return indexplot

    def adjust_img(self, event):
        print 'adjusting img'
        if event is not None:
            low, high = event
            imgplot = self.mainplot.plots['image plot'][0]
            newdata = np.clip()
            imgplot.value.get_data()
            new
            imgplot.value_range.low = low
            imgplot.value_range.high = high
        else:
            self.mainplot.index_range.set_bounds("auto", "auto")

    def _range_selection_handler(self, event):
        # The event obj should be a tuple (low, high) in data space
        if event is not None:
            low, high = event
            self.mainplot.index_range.low = low
            self.mainplot.index_range.high = high
        else:
            self.mainplot.index_range.set_bounds("auto", "auto")

class ControlView(HasTraits):
    ''' Define controls and info subview with size control'''

    # list of keys for target depth lines to edit (changes if list does)
    target_choices = List(Str)

    # chosen key for depth line to edit
    line_to_edit = Str

    # list of chosen lines to view in plots
    visible_lines = List(Str)

    # frequency choices for images
    freq_choices = List(Str)

    # selected freq for which image to view
    image_freq = Str

    traits_view = View(
                       VGroup(
                            Item('image_freq', editor=EnumEditor(
                                        name='freq_choices')),
                            Item('line_to_edit',
                                 editor=EnumEditor(name='target_choices'),
                                 tooltip='Edit red line with rt mouse button'),
                            Item('_'),
                            Item('visible_lines',
                                 editor=CheckListEditor(name='target_choices'),
                                 style='custom'),

                            Item('_'),
                            show_border=True,
                            ),
                       resizable=True
             		   )

class BigView(HasTraits):
    datafile = File
    controlview = Instance(ControlView)
    plotview = Instance(PlotView)
    traits_view = View(
                      Item('_'),
                      Item('datafile',padding=15),
                      HSplit(
                          InstanceUItem('controlview', width=150),
                          InstanceUItem('plotview', width=700),
                          show_border=True
                          ),
                      resizable=True,
                      )

#==========================================================================
# create individual views to check independently
#==========================================================================
def get_plotview():
    data = ArrayPlotData(x=np.arange(10),y=np.arange(10)**2)
    plot = Plot(data)
    plot.plot(('x','y'))
    view = PlotView(plot=plot)
    return view

def get_controlview():
    view = ControlView(freqs=[], choices=['a','b','c'], survey_binary='file')
    return view

def get_bigview():
    pv = get_plotview()
    cv = get_controlview()
    view = BigView(datafile='file', plotview=pv, controlview=cv)
    return view

if __name__ == '__main__':
    #view = get_plotview()
    #view = get_controlview()
    view = get_bigview()
    view.configure_traits()