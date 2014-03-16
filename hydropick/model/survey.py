#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

from __future__ import absolute_import

import logging

from traits.api import Directory, Event, HasTraits, List, Str, Supports, provides

from .i_survey import ISurvey
from .i_lake import ILake
from .i_survey_line import ISurveyLine
from .i_survey_line_group import ISurveyLineGroup
from .i_core_sample import ICoreSample

logger = logging.getLogger(__name__)


@provides(ISurvey)
class Survey(HasTraits):
    """ The a basic implementation of the ISurvey interface

    A survey has a lake, a set of survey lines, and a collection of
    user-assigned line groups.

    """
    #: The name of the survey
    name = Str

    #: Notes about the survey as a whole
    comments = Str

    #: The lake being surveyed
    lake = Supports(ILake)

    #: The lines in the survey
    survey_lines = List(Supports(ISurveyLine))

    #: The groupings of survey lines
    survey_line_groups = List(Supports(ISurveyLineGroup))

    #: The core samples taken in the survey
    core_samples = List(Supports(ICoreSample))

    #: used to signal change in core samples list
    core_samples_updated = Event

    #: backend project directory
    project_dir = Directory

    def add_survey_line_group(self, group):
        """ Create a new line group, optionally with a set of lines """
        self.survey_line_groups.append(group)
        self.save_to_disk()
        logger.debug("Added survey line group '{}'".format(group.name))

    def insert_survey_line_group(self, index, group):
        """ Create a new line group, optionally with a set of lines """
        self.survey_line_groups.insert(index, group)

    def save_to_disk(self):
        ''' it was decided all changes should be immediately saved so
        this is provide to eaily do that'''
        logger.debug('this would save to disk if it could')
