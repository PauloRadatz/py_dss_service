"""Tests for py_dss_service.common.records."""

from py_dss_service.common.records import cols_to_named


class TestColsToNamed:
    def test_none_input_returns_none(self):
        assert cols_to_named(None) is None

    def test_empty_dict_returns_none(self):
        assert cols_to_named({}) is None

    def test_missing_key_column_returns_none(self):
        assert cols_to_named({"bus1": ["a"]}) is None

    def test_single_element(self):
        records = {"name": ["line1"], "bus1": ["sourcebus"], "bus2": ["loadbus"]}
        result = cols_to_named(records)
        assert result == {"line1": {"bus1": "sourcebus", "bus2": "loadbus"}}

    def test_multiple_elements(self):
        records = {
            "name": ["line1", "line2"],
            "bus1": ["a", "c"],
            "bus2": ["b", "d"],
        }
        result = cols_to_named(records)
        assert result == {
            "line1": {"bus1": "a", "bus2": "b"},
            "line2": {"bus1": "c", "bus2": "d"},
        }

    def test_custom_key(self):
        records = {"id": ["bus1", "bus2"], "kv_base": [12.47, 4.16]}
        result = cols_to_named(records, key="id")
        assert result == {
            "bus1": {"kv_base": 12.47},
            "bus2": {"kv_base": 4.16},
        }

    def test_name_column_excluded_from_values(self):
        records = {"name": ["line1"], "bus1": ["a"]}
        result = cols_to_named(records)
        assert "name" not in result["line1"]

    def test_len_gives_element_count(self):
        records = {
            "name": ["a", "b", "c"],
            "x": [1, 2, 3],
            "y": [4, 5, 6],
        }
        result = cols_to_named(records)
        assert len(result) == 3
