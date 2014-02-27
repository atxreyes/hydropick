#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

from __future__ import absolute_import

import os
import numpy as np
from shapely.geometry import LineString

from traits.api import (HasTraits, Array, Dict, Event, List, Supports, Str,
                        provides, CFloat, Instance)

from .i_core_sample import ICoreSample
from .i_survey_line import ISurveyLine
from .i_depth_line import IDepthLine
from .depth_line import DepthLine


@provides(ISurveyLine)
class SurveyLine(HasTraits):
    """ A class representing a single survey line """

    #: the user-visible name for the line
    name = Str

    #: sample locations, an Nx2 array (example: easting/northing?)
    locations = Array(shape=(None, 2))

    #: specifies unit for values in locations array
    locations_unit = Str('feet')

    #: array of associated lat/long available for display
    lat_long = Array(shape=(None, 2))

    #: a dictionary mapping frequencies to intensity arrays
    frequencies = Dict

    #: complete trace_num set. array = combined freq_trace_num arrays
    trace_num = Array

    #: array of trace numbers corresponding to each intensity pixel/column
    #: ! NOTE ! starts at 1, not 0, so need to subtract 1 to use as index
    freq_trace_num = Dict

    #: relevant core samples
    core_samples = List(Supports(ICoreSample))

    #: depth of the lake at each location as generated by various soruces
    lake_depths = Dict(Str, Supports(IDepthLine))

    #: final choice for line used as current lake depth for volume calculations
    final_lake_depth = Instance(DepthLine)

    # and event fired when the lake depths are updated
    lake_depths_updated = Event

    #: The navigation track of the survey line in map coordinates
    navigation_line = Instance(LineString)

    #: pre-impoundment depth at each location as generated by various soruces
    preimpoundment_depths = Dict(Str, Supports(IDepthLine))

    #: final choice for pre-impoundment depth to track sedimentation
    final_pre_imp_depth = Instance(DepthLine)

    # and event fired when the lake depth is updated
    preimpoundment_depths_updated = Event

    # power values for entire trace set
    power = Array

    # gain values for entire trace set
    gain = Array

    #: Depth corrections:
    #:  depth = (pixel_number_from_top * pixel_resolution) + draft - heave
    #: distance from sensor to water. Constant offset added to depth
    draft = CFloat

    #: array of depth corrections.  Changes vertical offset of each column.
    heave = Array

    #: pixel resolution, depth/pixel
    pixel_resolution = CFloat

    # XXX probably other metadata should be here

    def load_data(self, hdf5_file):
        ''' Called by UI to load this survey line when selected to edit
        '''
        # read in sdi dictionary.  Only use 'frequencies' item.
        # sdi_dict_separated = binary.read(self.data_file_path)
        # sdi_dict_raw = binary.read(self.data_file_path, separate=False)
        # freq_dict_list = sdi_dict_separated['frequencies']

        from ..io import survey_io

        # read frequency dict from hdf5 file.
        sdi_dict_raw = survey_io.read_sdi_data_unseparated_from_hdf(hdf5_file,
                                                                    self.name)
        freq_dict_list = survey_io.read_frequency_data_from_hdf(hdf5_file,
                                                                self.name)

        # fill frequncies and freq_trace_num dictionaries with freqs as keys.
        for freq_dict in freq_dict_list:
            key = freq_dict['kHz']
            # transpose array to go into image plot correctly oriented
            intensity = freq_dict['intensity'].T
            self.frequencies[str(key)] = intensity
            self.freq_trace_num[str(key)] = freq_dict['trace_num']

        # for all other traits, use un-freq-sorted values
        self.trace_num = sdi_dict_raw['trace_num']
        self.locations = np.vstack([sdi_dict_raw['interpolated_easting'],
                                   sdi_dict_raw['interpolated_northing']]).T
        self.lat_long = np.vstack([sdi_dict_raw['latitude'],
                                  sdi_dict_raw['longitude']]).T
        self.draft = (np.mean(sdi_dict_raw['draft']))
        self.heave = sdi_dict_raw['heave']
        self.pixel_resolution = (np.mean(sdi_dict_raw['pixel_resolution']))
        self.power = sdi_dict_raw['power']
        self.gain = sdi_dict_raw['gain']
        # create depth line from sdi depth_r1 data and add to lakedepth dict
        sdi_depth_line_data = sdi_dict_raw['depth_r1']
        filename = os.path.basename(sdi_dict_raw['filepath'])

        self.lake_depths = survey_io.read_pick_lines_from_hdf(hdf5_file, self.name, 'current')
        self.preimpoundment_depths = survey_io.read_pick_lines_from_hdf(hdf5_file, self.name, 'preimpoundment')

    def nearby_core_samples(self, core_samples, dist_tol=100):
        """ Find core samples from a list of CoreSample instances
        that lie within dist_tol units of this survey line.
        """
        def distance(core, line):
            """ Calculate distance between a core sample and a survey line
            """
            from shapely.geometry import Point
            return self.navigation_line.distance(Point(core.location))
        cores = [core for core in core_samples
                 if distance(core, self) < dist_tol]
        return cores
