import unittest
from unittest.mock import patch, Mock
from app_code import startup_setup as setup


class StartupTests(unittest.TestCase):
    def test_installed_packages_skip_setup(self):
        with patch.object(setup, "missing_packages", return_value=[]), patch.object(setup, "install_packages") as install:
            self.assertTrue(setup.ensure_dependencies())
            install.assert_not_called()

    def test_install_targets_current_interpreter(self):
        with patch.object(setup.subprocess, "run", return_value=Mock(returncode=0)), patch.object(setup, "missing_packages", return_value=[]):
            setup.install_packages()
            self.assertEqual(setup.subprocess.run.call_args.args[0][:3], [setup.sys.executable, "-m", "pip"])

    def test_install_failure_preserves_error(self):
        with patch.object(setup.subprocess, "run", return_value=Mock(returncode=1, stderr="Network unavailable", stdout="")):
            with self.assertRaisesRegex(RuntimeError, "Network unavailable"):
                setup.install_packages()
