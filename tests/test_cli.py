"""Test for CLI functionality.

This module contains tests for the command line interface.
"""

from typer.testing import CliRunner

from homepot_client import __version__
from homepot_client.cli import app


class TestCLI:
    """Test suite for CLI commands."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_version_command(self) -> None:
        """Test the version command."""
        result = self.runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert __version__ in result.stdout
        assert "HOMEPOT Client" in result.stdout

    def test_info_command(self) -> None:
        """Test the info command."""
        result = self.runner.invoke(app, ["info"])

        assert result.exit_code == 0
        assert "HOMEPOT Client" in result.stdout
        assert "Homogenous Cyber Management" in result.stdout
        assert "consortium" in result.stdout.lower()

    def test_help_command(self) -> None:
        """Test the help command."""
        result = self.runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "HOMEPOT Client" in result.stdout
        assert "version" in result.stdout
        assert "info" in result.stdout
