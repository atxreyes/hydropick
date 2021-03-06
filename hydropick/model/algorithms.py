#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#
"""
Define algorithm classes following the model and place the class name in the
ALGORITHM_LIST constant at the top.  Each algorithm must have a unique name
string or it will not be recognized.

"""

from __future__ import absolute_import
import logging

import numpy as np

from traits.api import provides, Str, HasTraits, Float, Range, Enum

from scipy.signal import medfilt
from skimage.filter import threshold_otsu
from sklearn.mixture import GMM
from skimage.morphology import binary_opening, disk

from .i_algorithm import IAlgorithm

logger = logging.getLogger(__name__)


ALGORITHM_LIST = [
    'ThresholdCurrentSurface',
    'ThresholdPreImpoundmentSurface',
]


@provides(IAlgorithm)
class ThresholdCurrentSurface(HasTraits):
    """ Algorithm to pick current surface from 200Khz Intensity Image

    """

    #: a user-friendly name for the algorithm
    name = Str('Current Surface Threshold Algorithm')

    # list of names of traits defined in this class that the user needs
    # to set when the algorithm is applied
    arglist = ['frequency', 'threshold', 'threshold_offset', 'blank_above_distance', 'blank_below_distance']

    # instructions for user (description of algorithm and required args def)
    instructions = Str('Algorithm to autodetect current surface from selected intensity image. \n' +
                       '----------------------------------------------------------------------------- \n' +
                       'Algorithm has following steps: \n' +
                       '  1) Removes noise at top & bottom of image \n' +
                       '  2) Find location of line of maximum intensity (approx center of sediment signal) \n' +
                       '  3) Calculates a threshold intensity using OTSU algorithm or using user value\n' +
                       '  4) Create binary mask using threshold intensity \n' +
                       '  5) Despeckle binary mask using a binary opening \n' +
                       '  6) Find location of edge of binary mask above center line\n' +
                       '----------------------------------------------------------------------------- \n' +
                       'Parameters:\n' +
                       '  frequency = frequncy to use (200 (default), 50 or 24)\n' +
                       '  threshold = 0.0 - 1.0 (if negative then automatically determine threshold using OTSU)\n' +
                       '  threshold_offset = +/- value (default = 0.0, adjust the automatically determined threshold by this offset, ignore for manual threshold)\n' +
                       '  blank_above_distance = value (ignore image above this depth, if negative, detect automatically)\n' +
                       '  blank_below_distance = value (ignore image below this depth, if negative, detect automatically)\n' +
                       '----------------------------------------------------------------------------- \n')

    # args
    frequency = Enum(['200', '50', '24'])
    threshold = Range(value=-0.1, low=-0.1, high=1.0)
    threshold_offset = Float(0.0)
    blank_above_distance = Float(-1.0)
    blank_below_distance = Float(-1.0)

    def process_line(self, survey_line):
        """ returns all zeros to provide a blank line to edit.
        Size matches horizontal pixel number of intensity arrays
        """
        trace_array = survey_line.trace_num
        depth_array = np.empty(len(trace_array))
        depth_array.fill(np.nan)

        intensity, freq_trace_array = _get_intensity(survey_line, self.frequency)
        top, bot = _find_top_bottom(intensity, buf=5)
        if self.blank_above_distance > 0.0:
            top = (self.blank_above_distance/survey_line.pixel_resolution).astype(np.int)

        if self.blank_below_distance > 0.0:
            bot = (self.blank_below_distance/survey_line.pixel_resolution).astype(np.int)

        if self.threshold < 0.0:
            actual_threshold = _auto_threshold(intensity) + self.threshold_offset
        else:
            actual_threshold = self.threshold

        binary_img = _apply_threshold(intensity, actual_threshold)
        centers = _find_centers(intensity[top:bot, :]) + top

        depth_array[freq_trace_array-1] = _find_edge(binary_img,
                                                     centers,
                                                     surface='upper')

        depth_array = _convert_to_depth(depth_array,
                                        survey_line.pixel_resolution,
                                        survey_line.draft,
                                        survey_line.heave)

        return trace_array, depth_array


@provides(IAlgorithm)
class ThresholdPreImpoundmentSurface(HasTraits):
    """ Algorithm to pick PreImpoundment surface from selected Intensity Image

    """

    #: a user-friendly name for the algorithm
    name = Str('PreImpoundment Threshold Algorithm')

    # list of names of traits defined in this class that the user needs
    # to set when the algorithm is applied
    arglist = ['frequency', 'threshold', 'threshold_offset', 'current_surface_line']

    # instructions for user (description of algorithm and required args def)
    instructions = Str('Algorithm to autodetect preimpoundment surface from selected intensity image. \n' +
                       '----------------------------------------------------------------------------- \n' +
                       'Algorithm has following steps: \n' +
                       '  1) Clears image above selected current surface line \n' +
                       '  2) Find location of line of maximum intensity (approx center of sediment signal) \n' +
                       '  3) Calculates a threshold intensity using OTSU algorithm\n' +
                       '  4) Create binary mask using threshold intensity \n' +
                       '  5) Despeckle binary mask using a binary opening \n' +
                       '  6) Find location of edge of binary mask below center line\n' +
                       '----------------------------------------------------------------------------- \n' +
                       'Parameters:\n' +
                       '  frequency = frequncy to use (200 (default), 50 or 24)\n' +
                       '  threshold = 0.0 - 1.0 (if negative then automatically determine threshold using OTSU)\n' +
                       '  threshold_offset = +/- value (default = 0.0, adjust the automatically determined threshold by this offset)\n' +
                       '  current_surface_line = name of line to use as current surface (case sensitive without POST_ / _PRE prefix)\n' +
                       '----------------------------------------------------------------------------- \n')

    # args
    frequency = Enum(['200', '50', '24'])
    threshold = Range(value=-0.1, low=-0.1, high=1.0)
    threshold_offset = Float(0.0)
    current_surface_line = Str('current_surface_from_bin')

    def process_line(self, survey_line):
        """ returns all zeros to provide a blank line to edit.
        Size matches horizontal pixel number of intensity arrays
        """
        trace_array = survey_line.trace_num
        depth_array = np.empty(len(trace_array))
        depth_array.fill(np.nan)

        intensity, freq_trace_array = _get_intensity(survey_line, self.frequency)
        current_surface_locs = _get_current_surface(survey_line, self.current_surface_line)
        current_surface_locs = current_surface_locs[freq_trace_array-1]
        intensity = _clear_image_above_line(intensity, current_surface_locs)

        if self.threshold < 0.0:
            threshold = _auto_threshold(intensity) + self.threshold_offset
        else:
            threshold = self.threshold

        binary_img = _apply_threshold(intensity, threshold)
        centers = _find_centers(intensity)
        depth_array[freq_trace_array-1] = _find_edge(binary_img,
                                                     centers,
                                                     surface='lower')

        depth_array = _convert_to_depth(depth_array,
                                        survey_line.pixel_resolution,
                                        survey_line.draft,
                                        survey_line.heave)

        return trace_array, depth_array


def _find_top_bottom(img, buf=5):
    x = np.mean(img, axis=1)
    classif = GMM(n_components=2, covariance_type='full')
    fit = classif.fit(x.reshape((x.size, 1)))
    bot = np.where(x > fit.means_.min())[0][-1] + buf
    top = np.where(x < fit.means_.mean())[0][0]
    try:
        fit.fit(x[top:top+100].reshape((x[top:top+100].size, 1)))
        top += np.where(x[top:top+100] < fit.means_.min())[0][0]
    except:
        top += buf

    return top, bot


def _first_point_above(x, p):
    x = np.where(x[:p])[0]
    if len(x) > 0:
        return x[-1]

    return np.nan


def get_algorithm_dict():
    name_list = ALGORITHM_LIST
    classes = [globals()[cls_name] for cls_name in name_list]
    names = [cls().name for cls in classes]
    logger.debug('found these algorithms: {}'.format(names))
    return dict(zip(names, classes))


def _first_point_below(x, p):
    x = np.where(x[p:])[0]
    if len(x) > 0:
        return x[0] + p

    return np.nan


def _auto_threshold(img):
    return threshold_otsu(img)


def _apply_threshold(img, threshold):
    binary_img = img < threshold
    #remove small speckles
    binary_img = binary_opening(binary_img, disk(3))

    return binary_img


def _get_current_surface(survey_line, current_surface_line_name):
    depth_line = survey_line.lake_depths[current_surface_line_name]
    current_depths = depth_line.depth_array.copy()
    current_depths += survey_line.heave - survey_line.draft

    return (current_depths / survey_line.pixel_resolution).astype(np.int)


def _clear_image_above_line(intensity, current_surface_locs):
    for i, p in enumerate(current_surface_locs):
        intensity[:p, i] = np.median(intensity[:p, i])

    return intensity


def _convert_to_depth(depth_array, pixel_resolution, draft, heave):
    depth_array = _interpolate_nans(depth_array) * pixel_resolution

    return depth_array + draft - heave


def _find_centers(img, kernel_size=9):
    centers = medfilt(np.argmax(img, axis=0), kernel_size=kernel_size)

    return centers.astype(np.int)


def _find_edge(binary_img, centers, surface='upper'):
    cur_pics = 1.0*np.empty_like(centers)
    cur_pics.fill(np.nan)
    if surface == 'upper':
        edge_fn = _first_point_above
    else:
        edge_fn = _first_point_below

    for i in range(len(centers)):
        cur_pics[i] = edge_fn(binary_img[:, i], centers[i])

    return cur_pics


def _freq_dict(keys):
    key_24, key_50, key_200 = sorted([float(k) for k in keys])

    return {'200': str(key_200), '50': str(key_50), '24': str(key_24)}


def _get_intensity(survey_line, freq):
    freq = _freq_dict(survey_line.frequencies.keys())[freq]
    freq_trace_array = survey_line.freq_trace_num[freq]
    intensity = survey_line.frequencies[freq].copy()
    #fill nans with median value
    intensity[np.isnan(intensity)] = np.median(intensity)

    return intensity, freq_trace_array


def _interpolate_nans(y):
    nans, x = np.isnan(y), lambda z: z.nonzero()[0]
    y[nans] = np.interp(x(nans), x(~nans), y[~nans])
    return y.round(0).astype(np.int)
