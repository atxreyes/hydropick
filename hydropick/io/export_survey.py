import datetime
import os.path

import pandas as pd
import ulmo

from . import survey_io


def export_survey_points(survey, path):
    """Write out survey points to a csv for use in interpolation pipeline."""
    survey_point_data = [
        _extract_survey_points(survey_line)
        for survey_line in survey.survey_lines
    ]

    return survey_point_data


def generate_tide_file(gauge_code, survey):
    """Generate tide file to use as a source when exporting survey points."""
    tide_file_path = _get_tide_file_path(survey)
    instantaneous_code = '00062:00011'
    midnight_code = '00062:32400'
    daily_mean_code = '00062:00003'

    parameter_codes = [instantaneous_code, midnight_code, daily_mean_code]
    data = ulmo.usgs.nwis.hdf5.get_site_data(gauge_code, parameter_code=parameter_codes)

    line_names = sorted([survey_line.name for survey_line in survey.survey_lines])
    start = str(_date_from_line_name(line_names[0]))

    # go forward two days so we have something to interpolate to
    end = str(_date_from_line_name(line_names[-1]) + datetime.timedelta(days=2))

    if not data:
        ulmo.usgs.nwis.hdf5.update_site_data(gauge_code, start=start, end=end)
        data = ulmo.usgs.nwis.hdf5.get_site_data(gauge_code)

    df = pd.DataFrame()

    for code in parameter_codes:
        daily_mean = code == daily_mean_code
        df = df.combine_first(_df_for_code(data, code, start, end, daily_mean))

    df = df.rename(columns={'value': 'water_surface_elevation'})[['water_surface_elevation']]
    df.to_csv(tide_file_path, index_label='datetime')


def _date_from_line_name(line_name):
    return datetime.datetime.strptime(line_name[:6], '%y%m%d').date()


def _df_for_code(data, code, start, end, daily_mean=False):
    if code in data:
        df = pd.DataFrame(data[code]['values']).set_index('datetime')
        df.index = pd.DatetimeIndex(df.index)
        if daily_mean:
            df.index = df.index + datetime.timedelta(hours=12)
        df.value = df.value.astype(float)
        df = df[start:end]
    else:
        df = pd.DataFrame()
    return df


def _extract_survey_points(survey_line):
    survey_line.load_data(survey_line.project_dir)
    survey_line.unload_data()


def _get_tide_file_path(survey):
    return os.path.join(survey.project_dir, 'tide_file.txt')
