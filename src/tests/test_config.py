import importlib
import unittest
from unittest.mock import MagicMock, patch

import confuse

from pvecontrol.config import list_clusters, set_config

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
