#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

# 3rd party imports
import numpy as np

# ETS imports
from enable.api import BaseTool
from traits.api import Float, List, Str


class LineSelectTool(BaseTool):
    """ A tool for selecting navigation lines.

    Currently very crude and only changes line color.  In the future
    this will actually be connected to selections in application.
    """

    #: distance tolerance in data units on map (feet by default)
    tol = Float(100.0)

    # ughly
    line_plots = List

    def _select(self, token, append=True):
        pass

    def _deselect(self, token, append=True):
        pass

    def normal_left_down(self, event):
        """ Select a line if it is within 100 ft """
        tol2 = self.tol ** 2
        plot = self.component
        x = plot.index_mapper.map_data(event.x)
        y = plot.value_mapper.map_data(event.y)
        for lp, in self.line_plots:
            x_line = lp.index.get_data()
            y_line = lp.value.get_data()
            dist = np.min((x_line - x)**2 + (y_line - y)**2)
            if dist < tol2:
                print 'Select', lp, x, y
                # FIXME: This is an ugly way to decide if selected
                if lp.color == 'blue':
                    lp.color = 'red'
                    self._select(lp)
                else:
                    lp.color = 'blue'
                    self._deselect(lp)