def export_survey_points(survey, path):
    """Write out survey points to a csv for use in interpolation pipeline."""
    survey_point_data = [
        _extract_survey_points(survey_line)
        for survey_line in survey.survey_lines
    ]

    return survey_point_data


def _extract_survey_points(survey_line):
    survey_line.load_data(survey_line.project_dir)
    survey_line.unload_data()
