import datetime
import os.path

import pandas as pd
import ulmo

from . import survey_io


def export_survey_points(survey, path, with_pre=True):
    """Write out survey points to a csv for use in interpolation pipeline."""
    tide_file_path = _get_tide_file_path(survey)
    tide_data = pd.read_csv(tide_file_path, index_col='datetime')
    tide_data.index = pd.DatetimeIndex(tide_data.index)

    start_columns = [
        # (name, decimals, string_fmt)
        ('x', 8, '%13.8f'),
        ('y', 8, '%13.8f'),
        ('latitude', 8, '%13.8f'),
        ('longitude', 8, '%13.8f'),
        ('z', 2, '%5.2f'),
        ('lake_elevation', 2, '%5.2f'),
        ('current_surface_elevation', 2, '%5.2f'),
    ]

    if with_pre:
        preimpoundment_columns = [
            ('pre_impoundment_elevation', 2, '%5.2f'),
            ('sediment_thickness', 2, '%5.2f'),
        ]
    else:
        preimpoundment_columns = []

    end_columns = [
        ('sdi_filename', None, None),
        ('date', None, None),
        ('time', None, None),
    ]

    column_info = start_columns + preimpoundment_columns + end_columns

    with open(path, 'wb') as f:
        first = True

        for survey_line in survey.survey_lines:
            if survey_line.status == 'bad':
                continue
            df = _extract_survey_points(survey_line, tide_data, with_pre=with_pre)
            for name, decimals, fmt in column_info:
                if decimals is not None:
                    df[name] = df[name].round(decimals=decimals)
                if fmt is not None:
                    df[name] = df[name].apply(lambda f: fmt % f)

            cols = [name for name, decimals, pad in column_info]
            df.to_csv(f, cols=cols, header=first, index=False)
            first = False


def generate_tide_file(gauge_code, survey):
    """Generate tide file to use as a source when exporting survey points."""
    tide_file_path = _get_tide_file_path(survey)
    instantaneous_code = '00062:00011'
    midnight_code = '00062:32400'
    daily_mean_code = '00062:00003'

    parameter_codes = [instantaneous_code, midnight_code, daily_mean_code]

    line_names = sorted([survey_line.name for survey_line in survey.survey_lines])
    start = str(_date_from_line_name(line_names[0]))

    # go forward two days so we have something to interpolate to
    end = str(_date_from_line_name(line_names[-1]) + datetime.timedelta(days=2))

    data = ulmo.usgs.nwis.get_site_data(gauge_code, start=start, end=end)

    df = pd.DataFrame()

    for code in parameter_codes:
        daily_mean = code == daily_mean_code
        df = df.combine_first(_df_for_code(data, code, start, end, daily_mean))

    df = df.rename(columns={'value': 'water_surface_elevation'})[['water_surface_elevation']]
    df.to_csv(tide_file_path, index_label='datetime')


def _date_from_line_name(line_name):
    return datetime.datetime.strptime(line_name[:6], '%y%m%d').date()


def _df_for_code(data, code, start, end, daily_mean=False):
    if code not in data:
        return pd.DataFrame()

    df = pd.DataFrame(data[code]['values'])

    if df.empty:
        return pd.DataFrame()

    df = df.set_index('datetime')
    df.index = pd.DatetimeIndex(df.index)

    if daily_mean:
        df.index = df.index + datetime.timedelta(hours=12)

    df.value = df.value.astype(float)

    return df[start:end]


def _extract_survey_points(survey_line, tide_data, with_pre):
    survey_line.load_data(survey_line.project_dir)

    lake_depth = survey_line.lake_depths.get(survey_line.final_lake_depth)
    preimpoundment_depth = survey_line.preimpoundment_depths.get(
        survey_line.final_preimpoundment_depth)

    if lake_depth is None:
        raise LookupError(
            "Survey line %s does not have a final lake depth set" % survey_line.name)
    if with_pre and preimpoundment_depth is None:
        raise LookupError(
            "Survey line %s does not have a final preimpoundment depth set" % survey_line.name)

    sdi_dict_raw = survey_io.read_sdi_data_unseparated_from_hdf(
        survey_line.project_dir,
        survey_line.name)

    x = sdi_dict_raw['interpolated_easting']
    y = sdi_dict_raw['interpolated_northing']
    latitude = sdi_dict_raw['interpolated_latitude']
    longitude = sdi_dict_raw['interpolated_longitude']

    datetime = _parse_datetimes(sdi_dict_raw)

    lake_elevation = _interpolate_water_surface(tide_data, datetime)

    current_surface_z = _meters_to_feet(lake_depth.depth_array)

    data_dict = dict(
        x=x,
        y=y,
        latitude=latitude,
        longitude=longitude,
        lake_elevation=lake_elevation,
        current_surface_z=current_surface_z,
        sdi_filename=survey_line.name,
        date=datetime.date,
        time=datetime.time,
    )

    if with_pre:
        data_dict['pre_impoundment_z'] = _meters_to_feet(preimpoundment_depth.depth_array)

    df = pd.DataFrame(data_dict, index=datetime)

    df['current_surface_elevation'] = df['lake_elevation'] - df['current_surface_z']

    if with_pre:
        df['pre_impoundment_elevation'] = df['lake_elevation'] - df['pre_impoundment_z']
        df['sediment_thickness'] = df['current_surface_elevation'] - df['pre_impoundment_elevation']

    df = df.rename(columns={
        'current_surface_z': 'z',
    })

    # apply mask
    if len(survey_line.mask):
        df = df[~survey_line.mask.astype(bool)]

    survey_line.unload_data()
    return df


def _get_tide_file_path(survey):
    return os.path.join(survey.project_dir, 'tide_file.txt')


def _interpolate_water_surface(water_surface, datetime):
    wse = water_surface['water_surface_elevation']
    nans = pd.Series(index=datetime.unique())
    return wse.combine_first(nans).interpolate(method='time')[datetime]


def _meters_to_feet(arr):
    return arr * 3.28083989501312


def _parse_datetimes(sdi_dict_raw):
    date = datetime.datetime.strptime(sdi_dict_raw['date'][:6], '%y%m%d')

    # note: be wary of using timedelta64; it's more efficient but inconsisent
    # and weirdly broken in some versions of numpy
    datetimes = [
        date + datetime.timedelta(hours=int(t[0]), minutes=int(t[1]), seconds=int(t[2]), microseconds=int(t[3]))
        for t in zip(sdi_dict_raw['hour'], sdi_dict_raw['minute'], sdi_dict_raw['second'], sdi_dict_raw['microsecond'])
    ]

    return pd.DatetimeIndex(datetimes)
