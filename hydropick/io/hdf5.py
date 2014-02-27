import contextlib
import json

import fiona
import numpy as np
import sdi
from shapely.geometry import MultiLineString, shape, mapping
import tables


class HDF5Backend(object):
    """Read/write access for HDF5 data store."""

    def __init__(self, filepath):
        self.filepath = filepath
        self.hydropick_format_version = 1

    def import_binary_file(self, bin_file):
        data = sdi.binary.read(bin_file)
        data_raw = sdi.binary.read(bin_file, separate=False)
        x = data['frequencies'][-1]['interpolated_easting']
        y = data['frequencies'][-1]['interpolated_northing']
        coords = np.vstack((x, y)).T
        line_name = data['survey_line_number']
        with self._open_file('a') as f:
            line_group = self._get_survey_line_group(f, line_name)
            f.createArray(line_group, 'navigation_line', coords)
            f.flush()

        self._write_freq_dicts(line_name, data['frequencies'])
        self._write_raw_sdi_dict(line_name, data_raw)

    def import_corestick_file(self, corestick_file):
        core_sample_dicts = sdi.corestick.read(corestick_file)
        self._write_core_samples(core_sample_dicts)

    def import_shoreline_file(self, lake_name, shoreline_file):
        """ Load the shoreline from GIS file.

        NB: Currently has side effects, loading crs and properties traits.
        """
        with fiona.open(shoreline_file) as f:
            crs = f.crs
            geometries = []
            for rec in f:
                geometries.append(rec['geometry'])
            # XXX: assuming that the properties aren't varying by geometry
            properties = rec['properties']

            if len(geometries) == 1:
                geom = shape(geometries[0])
            else:
                # XXX: this assumes we'll always get lines, not polygons or other
                geom = MultiLineString([
                    shape(geometry) for geometry in geometries])

        with self._open_file('a') as f:
            shoreline_group = self._get_shoreline_group(f)
            shoreline_group._v_attrs.crs = self._safe_serialize(crs)
            shoreline_group._v_attrs.lake_name = self._safe_serialize(lake_name)
            shoreline_group._v_attrs.original_shapefile = self._safe_serialize(shoreline_file)
            shoreline_group._v_attrs.properties = self._safe_serialize(properties)
            geometry_str = self._safe_serialize(mapping(geom))
            f.createArray(shoreline_group, 'geometry', np.array(geometry_str))

    def read_core_samples(self):
        try:
            with self._open_file('r') as f:
                core_samples_group = self._get_core_samples_group(f)
                core_samples = self._safe_unserialize(core_samples_group._v_attrs.core_samples)
        except tables.FileModeError:
            raise tables.NoSuchNodeError
        return core_samples

    def read_shoreline(self):
        try:
            with self._open_file('r') as f:
                shoreline_group = self._get_shoreline_group(f)
                crs = self._safe_unserialize(shoreline_group._v_attrs.crs)
                lake_name = self._safe_unserialize(shoreline_group._v_attrs.lake_name)
                original_shapefile = self._safe_unserialize(shoreline_group._v_attrs.original_shapefile)
                properties = self._safe_unserialize(shoreline_group._v_attrs.properties)
                geometry_str = str(shoreline_group.geometry.read())
                geometry = shape(self._safe_unserialize(geometry_str))
        except tables.FileModeError:
            raise tables.NoSuchNodeError

        return {
            'crs': crs,
            'geometry': geometry,
            'lake_name': lake_name,
            'original_shapefile': original_shapefile,
            'properties': properties,
        }

    def read_sdi_data_unseparated(self, line_name):
        try:
            with self._open_file('r') as f:
                unsep_grp = self._get_sdi_data_unseparated_group(f, line_name)
                data = [(array.name, array.read()) for array in unsep_grp]
                sdi_data = dict(data)
        except tables.FileModeError:
            raise tables.NoSuchNodeError
        return sdi_data

    def read_frequency_data(self, line_name):
        try:
            with self._open_file('r') as f:
                frequencies_group = self._get_frequencies_group(f, line_name)
                freq_data = [
                    dict([
                        (array.name, array.read())
                        for array in freq
                    ] + [('kHz', np.float(freq._v_name[4:].replace('_', '.')))])
                    for freq in frequencies_group
                ]
        except tables.FileModeError:
            raise tables.NoSuchNodeError
        return freq_data

    def read_survey_line_coords(self, line_name):
        try:
            with self._open_file('r') as f:
                line_group = self._get_survey_line_group(f, line_name)
                coords = line_group.navigation_line.read()
        except tables.FileModeError:
            raise tables.NoSuchNodeError
        return coords

    def _get_core_samples_group(self, f):
        """returns the group for the collection of core_sample data for a
        survey. Core samples could be attached to f.root, but giving core
        samples a group node allows the len(f.listNodes('/')) to still work as
        simple check for whether or not the file is new.
        """
        name = 'core_samples'
        try:
            core_sample_group = f.getNode('/', name)
        except tables.NoSuchNodeError:
            core_sample_group = f.createGroup('/', name)
        return core_sample_group

    def _get_frequency_group(self, f, line_name, khz):
        """returns the group for the collection of frequency data for a survey line"""
        frequencies_group = self._get_frequencies_group(f, line_name)
        frequency_label = 'khz_' + str(khz).replace('.', '_')
        try:
            frequency_group = f.getNode(frequencies_group, frequency_label)
        except tables.NoSuchNodeError:
            frequency_group = f.createGroup(frequencies_group, frequency_label)
        return frequency_group

    def _get_frequencies_group(self, f, line_name):
        """returns the group for the collection of frequency data for a survey line"""
        survey_line_group = self._get_survey_line_group(f, line_name)
        try:
            frequency_group = f.getNode(survey_line_group, 'frequencies')
        except tables.NoSuchNodeError:
            frequency_group = f.createGroup(survey_line_group, 'frequencies')
        return frequency_group

    def _get_or_create_group(self, f, parent, name):
        try:
            group = f.getNode(parent, name)
        except tables.NoSuchNodeError:
            group = f.createGroup(parent, name)
        return group

    def _get_sdi_data_unseparated_group(self, f, line_name):
        """returns the group for the collection of frequency data for a survey line"""
        survey_line_group = self._get_survey_line_group(f, line_name)
        try:
            sdi_data_unseparated_group = f.getNode(survey_line_group, 'sdi_data_unseparated')
        except tables.NoSuchNodeError:
            sdi_data_unseparated_group = f.createGroup(survey_line_group, 'sdi_data_unseparated')
        return sdi_data_unseparated_group

    def _get_shoreline_group(self, f):
        """returns the group for lake shoreline"""
        return self._get_or_create_group(f, f.root, 'shoreline')

    def _get_survey_lines_group(self, f):
        """returns the group for the collection of survey_lines - creating it if necessary"""
        try:
            survey_lines_group = f.getNode('/survey_lines')
        except tables.NoSuchNodeError:
            survey_lines_group = f.createGroup(f.root, 'survey_lines')
        return survey_lines_group

    def _get_survey_line_group(self, f, line_name):
        """returns a group for a specific survey_line - creating it if necessary"""
        survey_lines = self._get_survey_lines_group(f)
        group_label = 'line_' + line_name
        try:
            line_group = f.getNode(survey_lines, group_label)
        except tables.NoSuchNodeError:
            line_group = f.createGroup(survey_lines, group_label)
        return line_group

    @contextlib.contextmanager
    def _open_file(self, mode):
        """context manager that opens a file and also checks that the hydropick
        version number is correct
        """
        with tables.openFile(self.filepath, mode) as f:
            if len(f.listNodes('/')) == 0:
                f.root._v_attrs.version = self.hydropick_format_version
            if not hasattr(f.root._v_attrs, 'version') or f.root._v_attrs.version != self.hydropick_format_version:
                # TODO: implement upgrade code
                raise NotImplementedError(
                    "Unsupported version of hdf5 backend file. Delete file and try again."
                )
            else:
                yield f

    def _safe_serialize(self, obj):
        """
        Serialize to a native datatype that can be safely stored and
        unserialized from a pytables AttributeSet class (node._v_attrs). This
        is important for security because AttributeSet falls back to pickled
        strings and unpickling malicious strings allows arbitrary code
        execution (see:
            http://lincolnloop.com/blog/playing-pickle-security/)
        """
        return json.dumps(obj)

    def _safe_unserialize(self, string):
        """
        Unserialize data from a string. See note in _safe_serialize docstring for more.
        """
        return json.loads(string)

    def _write_core_samples(self, core_sample_dicts):
        with self._open_file('a') as f:
            core_samples_group = self._get_core_samples_group(f)
            core_samples_group._v_attrs.core_samples = self._safe_serialize(core_sample_dicts)
            f.flush()

    def _write_freq_dicts(self, line_name, freq_dicts):
        with self._open_file('a') as f:
            for freq_dict in freq_dicts:
                khz = freq_dict.pop('kHz')
                freq_group = self._get_frequency_group(f, line_name, khz)
                for key, value in freq_dict.iteritems():
                    f.createArray(freq_group, key, value)
            f.flush()

    def _write_raw_sdi_dict(self, line_name, raw_dict):
        with self._open_file('a') as f:
            sdi_unsep_grp = self._get_sdi_data_unseparated_group(f, line_name)
            for key, value in raw_dict.iteritems():
                if key is not 'intensity':
                    if key is 'filepath':
                        value = str(value)    # to avoid unicode error
                    if key is 'date':
                        value = line_name
                    f.createArray(sdi_unsep_grp, key, value)
            f.flush()
