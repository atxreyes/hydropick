#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

from __future__ import absolute_import
import logging
import numpy as np

from shapely.geometry import LineString

from . import hdf5
from ..model.depth_line import DepthLine
from ..model.survey_line import SurveyLine
from ..model.lake import Lake

logger = logging.getLogger(__name__)


def import_survey_line_from_file(filename, project_dir, linename):
    hdf5.HDF5Backend(project_dir).import_binary_file(filename)


def import_core_samples_from_file(filename, project_dir):
    logger.info("Importing corestick file '%s'", filename)
    hdf5.HDF5Backend(project_dir).import_corestick_file(filename)


def import_pick_line_from_file(filename, project_dir):
    hdf5.HDF5Backend(project_dir).import_pick_file(filename)


def import_shoreline_from_file(lake_name, filename, project_dir):
    logger.info("Importing shoreline file '%s'", filename)
    hdf5.HDF5Backend(project_dir).import_shoreline_file(lake_name, filename)


def read_core_samples_from_hdf(project_dir):
    return hdf5.HDF5Backend(project_dir).read_core_samples()


def read_shoreline_from_hdf(project_dir):
    shoreline_dict = hdf5.HDF5Backend(project_dir).read_shoreline()
    return Lake(
        crs=shoreline_dict['crs'],
        name=shoreline_dict['lake_name'],
        shoreline=shoreline_dict['geometry'],
        _properties=shoreline_dict['properties'],
    )


def read_survey_line_from_hdf(project_dir, name):
    coords = hdf5.HDF5Backend(project_dir).read_survey_line_coords(name)
    attrs_dict = read_survey_line_attrs_from_hdf(project_dir, name)
    line = SurveyLine(name=name,
                      data_file_path=project_dir,
                      navigation_line=LineString(coords), **attrs_dict)
    return line


def read_survey_line_attrs_from_hdf(project_dir, name):
    return hdf5.HDF5Backend(project_dir).read_survey_line_attrs(name)


def read_survey_line_mask_from_hdf(project_dir, name):
    return hdf5.HDF5Backend(project_dir).read_survey_line_mask(name)


def read_frequency_data_from_hdf(project_dir, name):
    return hdf5.HDF5Backend(project_dir).read_frequency_data(name)


def read_sdi_data_unseparated_from_hdf(project_dir, name):
    return hdf5.HDF5Backend(project_dir).read_sdi_data_unseparated(name)


def read_pick_lines_from_hdf(project_dir, line_name, line_type):
    pick_lines = hdf5.HDF5Backend(project_dir).read_picks(line_name, line_type)

    return dict([
        (name, DepthLine(**pick_line))
        for name, pick_line in pick_lines.iteritems()
    ])


def read_one_pick_line_from_hdf(pic_name, pick_lines=None, project_dir=None,
                                line_name=None, line_type=None):
    if pick_lines is None:
        backend = hdf5.HDF5Backend(project_dir)
        pick_lines = backend.read_picks(line_name, line_type)
    pick_line = pick_lines[pic_name]
    depth_line = DepthLine(**pick_line)
    return depth_line


def write_depth_line_to_hdf(project_dir, depth_line, survey_line_name):
    d = depth_line
    data = dict(
        name=d.name,
        survey_line_name=d.survey_line_name,
        line_type=d.line_type,
        source=d.source,
        source_name=d.source_name,
        args=d.args,
        index_array=d.index_array,
        depth_array=d.depth_array,
        edited=d.edited,
        color=str(d.color.getRgb()),   # so pytables can handle it
        notes=d.notes,
        locked=d.locked,
    )
    if d.line_type == 'current surface':
        line_type = 'current'
    else:
        line_type = 'preimpoundment'
    hdf5.HDF5Backend(project_dir).write_pick(data, survey_line_name, line_type)


def write_survey_line_to_hdf(project_dir, survey_line):
    depth_line_dicts = [
        survey_line.lake_depths,
        survey_line.preimpoundment_depths
    ]
    for depth_line_dict in depth_line_dicts:
        for depth_line in depth_line_dict.values():
            write_depth_line_to_hdf(project_dir, depth_line, survey_line.name)

    attrs_dict = {
        'final_lake_depth': survey_line.final_lake_depth,
        'final_preimpoundment_depth': survey_line.final_preimpoundment_depth,
        'status': survey_line.status,
        'status_string': survey_line.status_string
    }

    hdf5.HDF5Backend(project_dir).write_survey_line_attrs(attrs_dict, survey_line.name)
    hdf5.HDF5Backend(project_dir).write_survey_line_mask(survey_line.mask, survey_line.name)


def check_trace_num_array(trace_num_array, survey_line_name):
    ''' checks for bad points in trace_num array.
    assumes trace num array should be a sequential array, 1 to len(array)
    (as specified in sdi.binary).  Returns bad trace numbers and bad values
    this should be done when loading survey line arrays and associated depth
    lines.
    '''
    ref = np.arange(len(trace_num_array)) + 1
    # this returns index for any traces that don't match ref
    bad_indices = np.nonzero(trace_num_array - ref)[0]
    bad_values = trace_num_array[bad_indices]
    if bad_indices:
        # log the problem
        s = '''trace_num not contiguous for array: {}.
        values of {} at traces {}
        '''.format('name', bad_values, bad_indices + 1)
        logger.warn(s)

    return bad_indices, bad_values


def fix_trace_num_arrays(trace_num_array, bad_indices, freq_trace_num):
    ''' Replaces bad trace num values with the appropriate sequential value,
    then fixes main trace num_array
    This should really be done in sdi binary read but for now this is a fix.
    '''
    for freq, trace_array in freq_trace_num.items():
        # find the trace num indices in the freq trace num subset
        indices_in_freq = np.where(np.in1d(trace_num_array, trace_array))[0]
        # get trace num indices of bad traces in this freq_trace_num array
        bad_in_freq = bad_indices[np.in1d(bad_indices, indices_in_freq)]
        for index in bad_in_freq:
            # find the index in freq trace num where this index should go
            i_in_freq = np.searchsorted(indices_in_freq, index)
            # set the value to correct trace number which is the index + 1
            trace_array[i_in_freq] = index + 1
    trace_num_array = np.arange(1, len(trace_num_array) + 1)

    return trace_num_array, freq_trace_num
