#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#
from __future__ import absolute_import

import os
import logging
import numpy as np
from shapely.geometry import LineString

from traits.api import (HasTraits, Array, Dict, Event, List, Supports, Str,
                        provides, CFloat, Instance, Bool, Enum, Property)

from .i_core_sample import ICoreSample
from .i_survey_line import ISurveyLine
from .i_depth_line import IDepthLine
from .depth_line import DepthLine

logger = logging.getLogger(__name__)

CURRENT_SURFACE_FROM_BIN_NAME = 'current_surface_from_bin'


@provides(ISurveyLine)
class SurveyLine(HasTraits):
    """ A class representing a single survey line """

    #==========================================================================
    #  THESE TRAITS ARE FROM DATA FILES
    #==========================================================================

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

    #: The navigation track of the survey line in map coordinates
    navigation_line = Instance(LineString)

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

    #==========================================================================
    # REMAINING TRAITS ARE USER GENERATED
    #==========================================================================

    #: depth of the lake at each location as generated by various soruces
    lake_depths = Dict(Str, Supports(IDepthLine))

    #: name of final choice current lake depth line for volume calculations
    final_lake_depth = Str

    # and event fired when the lake depths are updated
    lake_depths_updated = Event

    #: pre-impoundment depth at each location as generated by various soruces
    preimpoundment_depths = Dict(Str, Supports(IDepthLine))

    #: name of final choice for pre-impoundment depth to track sedimentation
    final_preimpoundment_depth = Str

    # and event fired when the lake depth is updated
    preimpoundment_depths_updated = Event

    # status of line determined by user analysis
    status = Enum('pending', 'approved', 'bad')

    # user comment on status (who approved it or why its bad fore example)
    status_string = Str('')

    # mask is bool array, size trace_num,  indicating bad traces.
    # True is bad/masked
    mask = Array(Bool)

    # indicated if mask has been defined for this line
    masked = Property(Bool, depends_on='mask')

    # project directory where this survey line will save itself
    project_dir = Str

    def _final_lake_depth_default(self):
        default = self.lake_depths.get(
            CURRENT_SURFACE_FROM_BIN_NAME, None)
        return default.name

    def _get_masked(self):
        ''' rather than being externally set this trait is set when mask
        is not empty
        '''
        masked = False
        if self.mask is not None:
            size = self.mask.size
            if size > 0:
                masked = True
        return masked

    def save_to_disk(self, project_dir=None):
        ''' saves this survey line to disk 
        This will save all the trait data list above in the "user generated"
        traits section
        If the project dir is set in the survey line, this method does not 
        need to have it passed by the caller
        '''
        if project_dir is None:
            project_dir = self.project_dir
        if os.path.isdir(project_dir):
            logger.warn('this would save survey line {} to disk if it could'
                        .format(self.name))
        else:
            logger.error('project directory is not valid')

    def load_data(self, hdf5_file):
        ''' Called by UI to load this survey line when selected to edit
        '''
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
        # check consistent arrays
        self.array_sizes_ok()
        filename = os.path.basename(sdi_dict_raw['filepath'])
        sdi_surface = DepthLine(
            name='current_surface_from_bin',
            survey_line_name=self.name,
            line_type='current surface',
            source='sdi_file',
            source_name=filename,
            index_array=self.trace_num - 1,
            depth_array=sdi_dict_raw['depth_r1'],
            lock = True
        )
        survey_io.write_depth_line_to_hdf(hdf5_file, sdi_surface, self.name)
        # depth lines stored separately
        self.lake_depths = survey_io.read_pick_lines_from_hdf(
            hdf5_file, self.name, 'current')
        self.preimpoundment_depths = survey_io.read_pick_lines_from_hdf(
            hdf5_file, self.name, 'preimpoundment')

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

    def array_sizes_ok(self):
        ''' this is an check that the arrays for this line make sense
        All the non-separated arrays should be the same size and the
        trace_num array should be range(1,N).  This could be slightly
        more general by assuming and order array instead of contiguous'''
        name = self.name
        logger.info('Checking all array integrity for line {}'.format(name))
        arrays = ['trace_num', 'locations', 'lat_long', 'heave', 'power',
                  'gain']

        from ..io import survey_io
        bad_indices, bad_vals = survey_io.check_trace_num_array(self.trace_num,
                                                                self.name)
        tn, fn = survey_io.fix_trace_num_arrays(self.trace_num,
                                                bad_indices,
                                                self.freq_trace_num)
        self.trace_num = tn
        self.freq_trace_num = fn
        N = len(tn)
        for a in arrays:
            if getattr(self, a).shape[0] != N:
                s = '{} is not size {}'.format(a, N)
                logger.warn(s)
                self.bad_survey_line = "Array sizes don't match on load"

