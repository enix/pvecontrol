import importlib
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import confuse
import yaml
from click.testing import CliRunner

import pvecontrol as pvecontrol_module
from pvecontrol import pvecontrol
from pvecontrol.config import configtemplate, list_clusters, set_config

# pvecontrol/__init__.py does `from pvecontrol.config import config`, which
# overwrites the `config` attribute on the pvecontrol package with the LazyConfig
# instance. importlib.import_module resolves via sys.modules directly, bypassing
# that shadowing, and returns the actual module.
config_module = importlib.import_module("pvecontrol.config")


def _make_cluster(name, node=None, vm=None):
    c = MagicMock()
    c.name = name
    c.node = node if node is not None else {}
    c.vm = vm if vm is not None else {}
    return c


def _make_validconfig(cluster_names):
    vc = MagicMock()
    vc.clusters = [_make_cluster(n) for n in cluster_names]
    vc.node = {"cpufactor": 2.5, "memoryminimum": 8589934592}
    vc.vm = {"max_last_backup": 1500}
    return vc


class TestLoadConfigErrors(unittest.TestCase):

    def test_config_read_error(self):
        with patch.object(config_module, "config") as mock_config:
            mock_config.get.side_effect = confuse.ConfigReadError("config.yaml")
            with self.assertRaises(SystemExit) as cm:
                list_clusters()
            self.assertEqual(cm.exception.code, 1)

    def test_not_found_error(self):
        with patch.object(config_module, "config") as mock_config:
            mock_config.get.side_effect = confuse.NotFoundError()
            with self.assertRaises(SystemExit) as cm:
                list_clusters()
            self.assertEqual(cm.exception.code, 1)

    def test_config_type_error(self):
        with patch.object(config_module, "config") as mock_config:
            mock_config.get.side_effect = confuse.ConfigTypeError()
            with self.assertRaises(SystemExit) as cm:
                list_clusters()
            self.assertEqual(cm.exception.code, 1)


class TestListClusters(unittest.TestCase):

    def test_empty(self):
        with patch.object(config_module, "config") as mock_config:
            mock_config.get.return_value = _make_validconfig([])
            self.assertEqual(list_clusters(), [])

    def test_returns_names(self):
        with patch.object(config_module, "config") as mock_config:
            mock_config.get.return_value = _make_validconfig(["prod", "staging"])
            self.assertEqual(list_clusters(), ["prod", "staging"])


class TestSetConfig(unittest.TestCase):

    def test_case_insensitive_lower_input(self):
        with patch.object(config_module, "config") as mock_config:
            mock_config.get.return_value = _make_validconfig(["PROD"])
            result = set_config("prod")
            self.assertEqual(result.name, "PROD")

    def test_case_insensitive_upper_input(self):
        with patch.object(config_module, "config") as mock_config:
            mock_config.get.return_value = _make_validconfig(["prod"])
            result = set_config("PROD")
            self.assertEqual(result.name, "prod")

    def test_exact_match(self):
        with patch.object(config_module, "config") as mock_config:
            mock_config.get.return_value = _make_validconfig(["prod"])
            result = set_config("prod")
            self.assertEqual(result.name, "prod")

    def test_not_found(self):
        with patch.object(config_module, "config") as mock_config:
            mock_config.get.return_value = _make_validconfig(["prod", "staging"])
            with self.assertRaises(SystemExit) as cm:
                set_config("unknown")
            self.assertEqual(cm.exception.code, 1)

    def test_ambiguous_names(self):
        vc = MagicMock()
        vc.clusters = [_make_cluster("prod"), _make_cluster("PROD")]
        vc.node = {}
        vc.vm = {}
        with patch.object(config_module, "config") as mock_config:
            mock_config.get.return_value = vc
            with self.assertRaises(SystemExit) as cm:
                set_config("prod")
            self.assertEqual(cm.exception.code, 1)

    def test_ambiguous_names_error_lists_conflicts(self):
        vc = MagicMock()
        vc.clusters = [_make_cluster("prod"), _make_cluster("PROD")]
        vc.node = {}
        vc.vm = {}
        with patch.object(config_module, "config") as mock_config:
            mock_config.get.return_value = vc
            with self.assertLogs("root", level="ERROR") as log:
                with self.assertRaises(SystemExit):
                    set_config("prod")
            self.assertTrue(any("prod" in msg and "PROD" in msg for msg in log.output))


def _make_temp_config(overrides=None):
    content = {
        "clusters": [{"name": "test", "host": "127.0.0.1", "user": "root@pam", "password": "secret"}],
        "node": {"cpufactor": 2.5, "memoryminimum": 8589934592},
        "vm": {"max_last_backup": 1500},
    }
    if overrides:
        content.update(overrides)
    f = tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False)
    yaml.dump(content, f)
    f.close()
    return f.name


class TestConfigFileOption(unittest.TestCase):

    def setUp(self):
        # test_pvecontrol.py::test_get_leaf_command calls make_context with --help args,
        # which sets ignoring=True on the shared pvecontrol group instance and never resets it.
        pvecontrol.ignoring = False

    def test_config_option_calls_set_file(self):
        config_path = _make_temp_config()
        try:
            runner = CliRunner()
            with (
                patch.object(pvecontrol_module, "config") as mock_config,
                patch("pvecontrol.actions.cluster.PVECluster.create_from_config", side_effect=SystemExit(0)),
            ):
                runner.invoke(pvecontrol, ["--config", config_path, "--cluster", "test", "status"])
            mock_config.set_file.assert_called_once_with(config_path)
        finally:
            os.unlink(config_path)

    def test_config_option_skips_user_config(self):
        # The given file must be layered on the packaged defaults only (user=False),
        # otherwise confuse merges the user config underneath and keys absent from the
        # given file leak in from ~/.config/pvecontrol/config.yaml.
        config_path = _make_temp_config()
        try:
            runner = CliRunner()
            with (
                patch.object(pvecontrol_module, "config") as mock_config,
                patch("pvecontrol.actions.cluster.PVECluster.create_from_config", side_effect=SystemExit(0)),
            ):
                runner.invoke(pvecontrol, ["--config", config_path, "--cluster", "test", "status"])
            mock_config.read.assert_called_once_with(user=False, defaults=True)
        finally:
            os.unlink(config_path)

    def test_no_config_option_skips_set_file(self):
        runner = CliRunner()
        with (
            patch.object(pvecontrol_module, "config") as mock_config,
            patch("pvecontrol.actions.cluster.PVECluster.create_from_config", side_effect=SystemExit(0)),
        ):
            runner.invoke(pvecontrol, ["--cluster", "test", "status"])
        mock_config.set_file.assert_not_called()
        mock_config.read.assert_not_called()

    def test_autodetect_no_cluster_error_references_custom_config(self):
        # When autodetection finds no cluster, the error must point at the file
        # passed with --config, not at the default user config path.
        config_path = _make_temp_config({"clusters": []})
        try:
            runner = CliRunner()
            with self.assertLogs("root", level="ERROR") as log:
                runner.invoke(pvecontrol, ["--config", config_path, "status"], env={"PVECONTROL_CLUSTER": None})
            assert any(config_path in msg for msg in log.output)
        finally:
            os.unlink(config_path)

    def test_custom_config_file_has_highest_priority(self):
        config_path = _make_temp_config()
        try:
            cfg = confuse.Configuration("pvecontrol_test", read=False)
            cfg.set_file(config_path)
            assert cfg.sources[0].filename == config_path
        finally:
            os.unlink(config_path)

    def test_custom_config_values_are_loaded(self):
        config_path = _make_temp_config({"node": {"cpufactor": 99.0, "memoryminimum": 8589934592}})
        try:
            cfg = confuse.Configuration("pvecontrol_test", read=False)
            cfg.set_file(config_path)
            result = cfg.get(configtemplate)
            assert result.node["cpufactor"] == 99.0
        finally:
            os.unlink(config_path)
