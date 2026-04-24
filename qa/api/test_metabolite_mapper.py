from streamlit_app.core.metabolite_mapper import MetaboliteMapper


def test_exact_metabolite_names_are_not_treated_as_time_columns():
    mapper = MetaboliteMapper()

    mappings = mapper.map_dataframe_columns(["Time_days", "EGLC", "ELAC", "ATP"])

    assert mappings["Time_days"]["method"] == "time_column"
    assert mappings["EGLC"]["method"] == "exact"
    assert mappings["EGLC"]["metabolite"] == "EGLC"
    assert mappings["ELAC"]["method"] == "exact"
    assert mappings["ELAC"]["metabolite"] == "ELAC"
    assert mappings["ATP"]["method"] == "exact"
    assert mappings["ATP"]["metabolite"] == "ATP"
