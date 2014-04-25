#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#
from __future__ import absolute_import

import logging
import glob
import os
import warnings

import tables

from hydropick.io import survey_io
from hydropick.io.survey_io import (import_survey_line_from_file,
                                    read_survey_line_from_hdf)

logger = logging.getLogger(__name__)


def get_name(directory):
    # name defaults to parent and grandparent directory names
    directory = os.path.abspath(directory)
    parent, dirname = os.path.split(directory)
    grandparent, parent_name = os.path.split(parent)
    great_grandparent, grandparent_name = os.path.split(grandparent)
    if parent_name and grandparent_name:
        name = grandparent_name + '_' + parent_name
    elif parent_name:
        name = parent_name
    else:
        name = "Untitled"
    return name


def get_number_of_bin_files(path):
    file_names = []
    for root, dirs, files in os.walk(path):
        files_bin = [f for f in files if os.path.splitext(f)[1] == '.bin']
        file_names += files_bin
    return len(file_names)


def import_cores(directory=None, project_dir=None, core_file=None):
    from ..model.core_sample import CoreSample
    if core_file:
        survey_io.import_core_samples_from_file(core_file, project_dir)
        core_dicts = survey_io.read_core_samples_from_hdf(project_dir)
    else:
        try:
            core_dicts = survey_io.read_core_samples_from_hdf(project_dir)
        except (IOError, tables.exceptions.NoSuchNodeError):
            for filename in os.listdir(directory):
                if os.path.splitext(filename)[1] == '.txt':
                    logger.debug('found corestick file {}'
                                 .format(filename))
                    corestick_file = os.path.join(directory, filename)
                    survey_io.import_core_samples_from_file(corestick_file, project_dir)
            core_dicts = survey_io.read_core_samples_from_hdf(project_dir)

    # this is a corestick file
    return [
        CoreSample(
            core_id=core_id,
            location=(core['easting'], core['northing']),
            layer_boundaries=[0] + core['layer_interface_depths'],
        )
        for core_id, core in core_dicts.items()
    ]


def import_pick_files(directory, project_dir):
    # find the GIS file in the directory
    for path in glob.glob(directory + '/*/*/*[pic,pre]'):
        name = os.path.basename(path)
        logger.info('importing pick file {}'.format(name))
        survey_io.import_pick_line_from_file(path, project_dir)


def import_lake(name, directory, project_dir):
    try:
        shoreline = survey_io.read_shoreline_from_hdf(project_dir)
    except (IOError, tables.exceptions.NoSuchNodeError):
        # find the GIS file in the directory
        for filename in os.listdir(directory):
            if os.path.splitext(filename)[1] == '.shp':
                shp_file = os.path.join(directory, filename)
                survey_io.import_shoreline_from_file(name, shp_file, project_dir)
                logger.info('imported shp file:{}'.format(filename))
                break
        shoreline = survey_io.read_shoreline_from_hdf(project_dir)
    return shoreline


def import_sdi(directory, project_dir):
    from hydropick.model.survey_line_group import SurveyLineGroup
    survey_lines = []
    survey_line_groups = []

    location, proj_dir = os.path.split(directory)
    N_bin_total = get_number_of_bin_files(directory)
    i_total = 0
    for root, dirs, files in os.walk(directory):
        group_lines = []
        currentd = root.split(location)[1]
        if 'Bad_data' in currentd:
            files_bin = []
        else:
            files_bin = [f for f in files if os.path.splitext(f)[1] == '.bin']
        N_dir = len(dirs)
        N_files = len(files_bin)
        logger.info('\nchecking project folder: "{}"\n with {} sub-directories'
                    .format(currentd, N_dir))
        logger.info('loading {} .bin files'.format(N_files))
        i = 0
        for filename in files_bin:
            # log status
            i += 1
            i_total += 1
            linename = os.path.splitext(filename)[0]
            logger.info('{}  ({}/{} in folder : {}/{} total)'
                        .format(linename, i, N_files, i_total, N_bin_total))
            # try to read line
            try:
                line = read_survey_line_from_hdf(project_dir, linename)
            except (IOError, tables.exceptions.NoSuchNodeError):
                logger.info("Importing sdi file '%s'", filename)
                try:
                    import_survey_line_from_file(os.path.join(root,
                                                              filename),
                                                 project_dir, linename)
                    line = read_survey_line_from_hdf(project_dir, linename)
                except Exception as e:
                    # XXX: blind except to read all the lines we can for now
                    s = 'Reading file {} failed with error "{}"'
                    msg = s.format(filename, e)
                    warnings.warn(msg)
                    logger.warning(msg)
                    line = None
            if line:
                line.project_dir = project_dir
                group_lines.append(line)

        if group_lines:
            dirname = os.path.basename(root)
            group = SurveyLineGroup(name=dirname, survey_lines=group_lines)
            survey_lines += group_lines
            survey_line_groups.append(group)
    return survey_lines, survey_line_groups


def import_survey(directory, with_pick_files=False):
    """ Read in a project from the current directory-based format """
    from ..model.survey import Survey

    name = get_name(directory)

    # project directory for survey
    project_dir = os.path.join(directory, name + '-project')
    logger.info('project directory is {}'.format(project_dir))

    # read in core samples
    core_samples = import_cores(os.path.join(directory, 'Coring'), project_dir)

    # read in lake
    lake = import_lake(name, os.path.join(directory, 'ForSurvey'), project_dir)

    # read in sdi data
    lines, grps = import_sdi(os.path.join(directory, 'SDI_Data'), project_dir)
    survey_lines, survey_line_groups = lines, grps

    # read in edits to sdi data
    if with_pick_files:
        import_pick_files(os.path.join(directory, 'SDI_Edits'), project_dir)

    survey = Survey(
        name=name,
        lake=lake,
        survey_lines=survey_lines,
        survey_line_groups=survey_line_groups,
        core_samples=core_samples,
        project_dir=project_dir,
    )

    return survey
