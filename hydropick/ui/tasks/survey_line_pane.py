#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

from __future__ import absolute_import

from traits.api import Instance, Property, Bool, Dict, Str
from traitsui.api import View, Item
from pyface.tasks.api import TraitsTaskPane

from ...model.i_survey_line import ISurveyLine
from ..surveydatasession import SurveyDataSession
from ..surveyline_view import SurveyLineView

class SurveyLinePane(TraitsTaskPane):
    """ The dock pane holding the map view of the survey """

    id = 'hydropick.survey_line'
    name = "Survey Line"

    survey_line = Instance(ISurveyLine)

    # provides string with name of line for keys or info.
    line_name = Property(depends_on='survey_line.name')
    def _get_line_name(self):
        if self.survey_line:
            return self.survey_line.name
        else:
            return 'None'

    # instance of survey_line view which displays selected surveyline
    survey_line_view = Instance(SurveyLineView)
        
    # once a valid survey line is selected a datasession will
    # created and stored for quick retrieval on line changes
    datasession_dict = Dict(Str, Instance(SurveyDataSession))

    # set when survey_line is none to prevent showing invalid view.
    show_view = Bool(False)

    def _survey_line_changed(self):
        ''' handle loading of survey line view if valid line provide or else
        provide an empty view.
        '''
        if self.survey_line is None:
            self.show_view = False
            self.survey_line_view = None
        else:
            datasession = self.datasession_dict.get(self.line_name, None)
            if datasession is None:
                # create new datasession object and entry for this surveyline.
                self.survey_line.load_data()
                datasession = SurveyDataSession(surveyline=self.survey_line)
                self.datasession_dict[self.line_name]=datasession
            self.survey_line_view = SurveyLineView(model=datasession)
            self.show_view = True

    view = View(
                Item('survey_line_view', style='custom', show_label=False,
                     visible_when='show_view')
    )
