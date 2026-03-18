"""Tests for py_dss_service.engine.validation."""

import pytest

from py_dss_service.common.errors import ScriptValidationError
from py_dss_service.engine.validation import (
    FORBIDDEN_COMMANDS,
    get_script_lines,
    validate_dss_script,
)


# ---------------------------------------------------------------------------
# validate_dss_script
# ---------------------------------------------------------------------------

class TestValidateDssScript:
    """Tests for validate_dss_script."""

    def test_valid_script_returns_none(self):
        result = validate_dss_script("new object=line.l1 bus1=a bus2=b")
        assert result is None

    def test_empty_script_raises(self):
        with pytest.raises(ScriptValidationError, match="empty"):
            validate_dss_script("")

    def test_whitespace_only_script_raises(self):
        with pytest.raises(ScriptValidationError, match="empty"):
            validate_dss_script("   \n\t\n  ")

    def test_script_exceeding_max_length_raises(self):
        long_script = "new object=line.l1\n" * 20_000
        with pytest.raises(ScriptValidationError, match="exceeds maximum length"):
            validate_dss_script(long_script, max_length=1024)

    def test_custom_max_length(self):
        script = "a" * 100
        with pytest.raises(ScriptValidationError, match="exceeds maximum length"):
            validate_dss_script(script, max_length=50)

    @pytest.mark.parametrize("cmd", FORBIDDEN_COMMANDS)
    def test_forbidden_command_at_start_of_line(self, cmd):
        script = f"{cmd} somefile.dss"
        with pytest.raises(ScriptValidationError, match="forbidden command"):
            validate_dss_script(script)

    @pytest.mark.parametrize("cmd", FORBIDDEN_COMMANDS)
    def test_forbidden_command_case_insensitive(self, cmd):
        script = f"{cmd.upper()} somefile.dss"
        with pytest.raises(ScriptValidationError, match="forbidden command"):
            validate_dss_script(script)

    @pytest.mark.parametrize("cmd", FORBIDDEN_COMMANDS)
    def test_forbidden_command_with_leading_whitespace(self, cmd):
        script = f"  {cmd} somefile.dss"
        with pytest.raises(ScriptValidationError, match="forbidden command"):
            validate_dss_script(script)

    @pytest.mark.parametrize("cmd", FORBIDDEN_COMMANDS)
    def test_forbidden_command_on_later_line(self, cmd):
        script = f"new object=line.l1\n{cmd} somefile.dss"
        with pytest.raises(ScriptValidationError, match="forbidden command"):
            validate_dss_script(script)

    def test_forbidden_word_inside_value_is_allowed(self):
        """'compile' as part of a value (not a command) should pass."""
        result = validate_dss_script("new object=line.compiled_thing bus1=a bus2=b")
        assert result is None

    def test_multiline_valid_script(self):
        script = (
            "new circuit.test\n"
            "new line.l1 bus1=a bus2=b\n"
            "solve\n"
        )
        assert validate_dss_script(script) is None


# ---------------------------------------------------------------------------
# get_script_lines
# ---------------------------------------------------------------------------

class TestGetScriptLines:
    """Tests for get_script_lines."""

    def test_splits_by_newlines(self):
        script = "line1\nline2\nline3"
        assert get_script_lines(script) == ["line1", "line2", "line3"]

    def test_strips_whitespace(self):
        script = "  line1  \n\tline2\t\n  line3  "
        assert get_script_lines(script) == ["line1", "line2", "line3"]

    def test_skips_empty_lines(self):
        script = "line1\n\n\nline2\n\n"
        assert get_script_lines(script) == ["line1", "line2"]

    def test_skips_bang_comments(self):
        script = "line1\n! this is a comment\nline2"
        assert get_script_lines(script) == ["line1", "line2"]

    def test_skips_double_slash_comments(self):
        script = "line1\n// this is a comment\nline2"
        assert get_script_lines(script) == ["line1", "line2"]

    def test_keeps_inline_comments(self):
        """Lines with content before a comment delimiter are kept."""
        script = "new line.l1 ! inline comment"
        result = get_script_lines(script)
        assert result == ["new line.l1 ! inline comment"]

    def test_empty_script_returns_empty_list(self):
        assert get_script_lines("") == []

    def test_only_comments_returns_empty_list(self):
        script = "! comment1\n// comment2\n! comment3"
        assert get_script_lines(script) == []

    def test_mixed_content(self):
        script = (
            "! header comment\n"
            "\n"
            "new circuit.test\n"
            "// another comment\n"
            "  new line.l1 bus1=a bus2=b  \n"
            "\n"
            "solve\n"
        )
        expected = [
            "new circuit.test",
            "new line.l1 bus1=a bus2=b",
            "solve",
        ]
        assert get_script_lines(script) == expected
