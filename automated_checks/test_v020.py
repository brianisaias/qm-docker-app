"""Offline checks without a graphical session or real credentials."""
import queue
import json
import os
import shlex
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import pyte
from app_code.connection_manager import ConnectionControls
from app_code.terminal_display import TerminalDisplay
from app_code.status_events import StatusEvents
from app_code.interface_layout import InterfaceLayout
from app_code.school_network import detect_school_network, SchoolNetworkControls, parse_vpn_status, vpn_portal_confirmed
from app_code.ssh_login import LoginSecret
from app_code.docker_controls import LocalControls
from app_code.settings import VERSION


class Value:
    def __init__(self, value=''):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class Harness(ConnectionControls, TerminalDisplay, StatusEvents, InterfaceLayout, SchoolNetworkControls):
    def __init__(self):
        for name in ('activity', 'user_status', 'connection_status', 'job_status', 'password', 'bronco_id', 'compose_path', 'docker_status', 'network_status'):
            setattr(self, name, Value())
        self.method = Value('remote')
        self.active = self.connected = self.calculating = self.disconnecting = self.docker_busy = self.closing = False
        self.network_approved = self.network_checking = False
        self.login_secret = None
        self.received = self.location_marker = self.job_marker = ''
        self.ready_marker = 'QM_READY_TEST'
        self.max_marker = 'QM_MAX_TEST'
        self.events = queue.Queue()
        self.write_lock = threading.Lock()
        self.terminal = Mock()
        self.screen = pyte.Screen(100, 24)
        self.stream = pyte.Stream(self.screen)
        self.buttons = {name: Mock() for name in ('Connect', 'Disconnect', 'Check QE', 'Show Files', 'Run Calculation', 'Run pw.x', 'Stop Calculation', 'Check current location', 'List current directory')}
        for name in ('local_radio', 'remote_radio', 'choose_button', 'id_entry', 'password_entry', 'network_button', 'docker_badge', 'stop_docker_button', 'max_button'):
            setattr(self, name, Mock())
        self.after = Mock()
        self.render_terminal = Mock()


class NetworkTests(unittest.TestCase):
    def test_vpn_requires_live_connection_and_correct_portal(self):
        for system in ('Windows', 'Darwin'):
            for live in (False, True):
                for portal in (False, True):
                    def run(args, **kwargs):
                        if args[0] == 'powershell.exe':
                            return 'QM_GP_CONNECTED' if live else ''
                        if '--nc' in args:
                            return '(Connected) UUID "GlobalProtect"' if live else ''
                        return ''
                    approved, message = detect_school_network(system, run, lambda _: portal)
                    self.assertEqual(approved, live and portal)
                    if approved:
                        self.assertIn('GlobalProtect (vpn.connect.cpp.edu)', message)

    def test_vpn_first_skips_wifi(self):
        for system in ('Windows', 'Darwin'):
            calls = []
            def run(args, **kwargs):
                calls.append(args)
                if args[0] == 'powershell.exe':
                    return 'QM_GP_CONNECTED'
                if '--nc' in args:
                    return '(Connected) UUID "GlobalProtect"'
                self.fail('Wi-Fi should not be checked after VPN confirmation')
            self.assertTrue(detect_school_network(system, run, lambda _: True)[0])
            self.assertEqual(len(calls), 1)

    def test_only_eduroam_wifi_qualifies(self):
        for system in ('Windows', 'Darwin'):
            for ssid in ('eduroam', 'GuestNetwork', 'Home', 'eduroam-other'):
                def run(args, **kwargs):
                    if args[0] == 'netsh':
                        return f'Name : Wi-Fi\nState : connected\nSSID : {ssid}'
                    if '-listallhardwareports' in args:
                        return 'Hardware Port: Wi-Fi\nDevice: en0'
                    if '-getairportnetwork' in args:
                        return 'Current Wi-Fi Network: ' + ssid
                    return ''
                approved, message = detect_school_network(system, run, lambda _: False)
                self.assertEqual(approved, ssid == 'eduroam')
                if approved:
                    self.assertIn('Connected Wi-Fi: eduroam', message)

    def test_mac_profiler_fallback_only_uses_connected_network(self):
        for ssid, state, expected in [('eduroam', 'spairport_status_connected', True), ('Home', 'spairport_status_connected', False), ('eduroam', 'spairport_status_off', False), ('<redacted>', 'spairport_status_connected', False)]:
            report = {"SPAirPortDataType": [{"spairport_airport_interfaces": [{
                "spairport_status_information": state,
                "spairport_current_network_information": {"_name": ssid},
                "spairport_airport_other_local_wireless_networks": [{"_name": "eduroam"}],
            }]}]}
            def run(args, **kwargs):
                return json.dumps(report) if args[0] == '/usr/sbin/system_profiler' else ''
            self.assertEqual(detect_school_network('Darwin', run, lambda _: False)[0], expected)

    def test_mac_dynamic_store_also_requires_portal(self):
        def run(args, **kwargs):
            if args[0] == '/bin/sh':
                return 'InterfaceName : utun4'
            if args[0] == '/sbin/ifconfig':
                return 'utun4: flags=8051<UP,POINTOPOINT,RUNNING>\n inet 10.20.1.2 netmask 0xffffffff'
            return ''
        for portal in (True, False):
            self.assertEqual(detect_school_network('Darwin', run, lambda _: portal)[0], portal)

    def test_latest_vpn_status_and_exact_portal(self):
        def response(state, portal):
            return f'<response><type>status</type><status>{state}</status><portal>{portal}</portal></response>'
        good = response('Connected', 'vpn.connect.cpp.edu')
        self.assertTrue(parse_vpn_status(good))
        self.assertTrue(parse_vpn_status(response('Connected', 'https://VPN.CONNECT.CPP.EDU/')))
        for host in ('other.edu', 'vpn.connect.cpp.edu.other.edu', 'vpn.connect.cpp.edu@other.edu', ''):
            self.assertFalse(parse_vpn_status(response('Connected', host)))
        for state in ('Disconnected', 'Connecting', 'Restoring VPN Connection'):
            self.assertFalse(parse_vpn_status(good + response(state, 'vpn.connect.cpp.edu')))
        self.assertFalse(parse_vpn_status(good + '<response><type>status</type><state>Disconnected</state></response>'))
        self.assertFalse(parse_vpn_status('saved portal vpn.connect.cpp.edu'))
        self.assertFalse(parse_vpn_status('<response>broken</response>'))

    def test_missing_status_log_denies_vpn(self):
        with patch.object(Path, 'open', side_effect=PermissionError()):
            self.assertFalse(vpn_portal_confirmed('Darwin'))
            self.assertFalse(vpn_portal_confirmed('Windows'))

    def test_missing_tools_and_invalid_profiler_data_do_not_crash(self):
        for system in ('Windows', 'Darwin', 'Other'):
            self.assertFalse(detect_school_network(system, Mock(side_effect=FileNotFoundError()), lambda _: False)[0])
        for report in ('invalid', 'null', '[]', '{"SPAirPortDataType": null}'):
            self.assertFalse(detect_school_network('Darwin', lambda args, **kw: report, lambda _: False)[0])

    def test_school_controls_and_recheck(self):
        app = Harness()
        for approved in (False, True, False):
            app.events.put(('network_checked', (approved, 'network result')))
            app.poll_events()
            self.assertEqual(app.network_status.get(), 'network result')
            self.assertEqual(app.activity.get(), 'network result')
            state = 'normal' if approved else 'disabled'
            app.id_entry.configure.assert_called_with(state=state)
            app.password_entry.configure.assert_called_with(state=state)
            self.assertIn(unittest.mock.call(state=state), app.buttons['Connect'].configure.call_args_list)
            app.buttons['Connect'].reset_mock()
        app.method.set('local')
        app.update_controls()
        self.assertIn(unittest.mock.call(state='normal'), app.buttons['Connect'].configure.call_args_list)

    def test_direct_connect_cannot_bypass_network(self):
        app = Harness()
        app.password.set('synthetic-secret')
        app.connect()
        self.assertFalse(app.active)
        self.assertEqual(app.password.get(), '')
        self.assertIn('School login unavailable', app.activity.get())


class PasswordTests(unittest.TestCase):
    def test_host_key_prompt_preserved_and_password_sent_once(self):
        secret = LoginSecret('synthetic-secret')
        terminal = Mock()
        host_key = 'Are you sure you want to continue connecting (yes/no/[fingerprint])? '
        self.assertEqual(secret.process(host_key, terminal, 'READY'), host_key)
        terminal.write.assert_not_called()
        secret.process('\r\nstudent@server pass', terminal, 'READY')
        output = secret.process('word: ', terminal, 'READY')
        terminal.write.assert_called_once_with('synthetic-secret\r')
        self.assertNotIn('synthetic-secret', output)
        self.assertEqual(secret.password, '')
        self.assertEqual(secret.process('synthetic-', terminal, 'READY'), '')
        self.assertEqual(secret.process('secret\r\nRE', terminal, 'READY'), '')
        self.assertEqual(secret.process('ADY\r\n$ ', terminal, 'READY'), '\r\nREADY\r\n$ ')
        self.assertEqual(secret.prompt, '')

    def test_failure_and_cancel_clear_secret(self):
        secret = LoginSecret('synthetic-secret')
        secret.process('Password: ', Mock(), 'READY')
        with self.assertRaises(RuntimeError):
            secret.process('Permission denied', Mock(), 'READY')
        self.assertEqual(secret.password, '')
        self.assertEqual(secret.prompt, '')
        app = Harness()
        app.active = True
        app.password.set('synthetic-secret')
        app.login_secret = LoginSecret('synthetic-secret')
        with patch('app_code.connection_manager.threading.Thread'):
            app.disconnect()
        self.assertEqual(app.password.get(), '')
        self.assertEqual(app.login_secret.password, '')

    def test_connect_moves_password_to_memory_only(self):
        app = Harness()
        app.network_approved = True
        app.bronco_id.set('student')
        app.password.set('synthetic-secret')
        with patch('app_code.connection_manager.threading.Thread'), patch.object(Path, 'write_text') as write:
            app.connect()
            write.assert_not_called()
        self.assertEqual(app.password.get(), '')
        self.assertEqual(app.login_secret.password, 'synthetic-secret')
        self.assertNotIn('synthetic-secret', app.activity.get())
        self.assertNotIn('synthetic-secret', repr(list(app.events.queue)))
        app.events.put(('closed', ''))
        app.poll_events()
        self.assertIsNone(app.login_secret)

    def test_worker_failure_clears_password_and_hides_exception(self):
        app = Harness()
        app.login_secret = LoginSecret('synthetic-secret')
        with patch('app_code.connection_manager.detect_school_network', return_value=(True, 'approved')), patch('app_code.connection_manager.find_program', side_effect=RuntimeError('synthetic-secret')):
            app.connection_worker('remote', '', 'student', app.ready_marker)
        self.assertIsNone(app.login_secret)
        self.assertNotIn('synthetic-secret', repr(list(app.events.queue)))

    def test_worker_authentication_events_never_contain_password(self):
        app = Harness()
        app.cancel_connection = False
        app.login_secret = LoginSecret('synthetic-secret')
        terminal = Mock()
        terminal.read.side_effect = ["student@server password: ", "synthetic-", "secret\r\n" + app.ready_marker + "\r\n$ ", EOFError()]
        terminal.alive.return_value = False
        with patch('app_code.connection_manager.detect_school_network', return_value=(True, 'approved')), patch('app_code.connection_manager.find_program', return_value='ssh'), patch('app_code.connection_manager.TerminalProcess', return_value=terminal) as spawn, patch.object(Path, 'write_text') as write:
            app.connection_worker('remote', '', 'student', app.ready_marker)
        terminal.write.assert_called_once_with('synthetic-secret\r')
        self.assertIsNone(app.login_secret)
        self.assertNotIn('synthetic-secret', repr(list(app.events.queue)))
        self.assertNotIn('synthetic-secret', repr(spawn.call_args))
        self.assertNotIn('StrictHostKeyChecking=no', repr(spawn.call_args))
        write.assert_not_called()



class LocationTests(unittest.TestCase):
    def setUp(self):
        self.app = Harness()
        self.app.active = self.app.connected = True

    def frame(self, user, folder):
        return f'\r\n{self.app.location_marker}:{(user + chr(10)).encode().hex()}:{(folder + chr(10)).encode().hex()}:END\r\n'

    def test_auto_check_local_and_school(self):
        for method in ('local', 'remote'):
            self.app.connected = False
            self.app.received = ''
            self.app.method.set(method)
            self.app.process_output('\r\nQM_READY_TEST\r\n')
            self.assertTrue(self.app.connected)
            self.assertTrue(self.app.location_marker)
            self.assertIn('pwd -P', self.app.terminal.write.call_args.args[0])

    def test_split_response_spaces_unicode_refresh_and_stale_reply(self):
        self.app.check_current_location()
        old = self.frame('max', '/home/max/work')
        self.app.check_current_location()
        self.app.process_output(old)
        self.assertEqual(self.app.user_status.get(), 'Current user: checking…')
        frame = self.frame('student', '/home/student/my work/é')
        for char in frame:
            self.app.process_output(char)
        self.assertEqual(self.app.user_status.get(), 'Current user: student | Folder: /home/student/my work/é')
        self.app.check_current_location()
        self.app.process_output(self.frame('root', '/tmp/new folder'))
        self.assertEqual(self.app.user_status.get(), 'Current user: root | Folder: /tmp/new folder')

    def test_echo_does_not_parse_and_closed_clears(self):
        self.app.check_current_location()
        self.app.process_output(self.app.terminal.write.call_args.args[0])
        self.assertEqual(self.app.user_status.get(), 'Current user: checking…')
        self.app.process_output(self.frame('max', '/home/max/work'))
        self.app.events.put(('closed', ''))
        self.app.poll_events()
        self.assertEqual(self.app.user_status.get(), 'Terminal user: not connected')
        self.assertEqual(self.app.location_marker, '')

    @unittest.skipIf(os.name == "nt", "POSIX shell integration check runs on macOS")
    def test_actual_shell_cd_refresh(self):
        with tempfile.TemporaryDirectory(prefix='qm work ') as folder:
            self.app.check_current_location()
            command = self.app.terminal.write.call_args.args[0].strip()
            result = subprocess.run(['/bin/sh', '-c', command], cwd=folder, capture_output=True, text=True, check=True)
            self.app.process_output(result.stdout)
            user = subprocess.check_output(['id', '-un'], text=True).strip()
            self.assertEqual(self.app.user_status.get(), f'Current user: {user} | Folder: {Path(folder).resolve()}')

    @unittest.skipIf(os.name == "nt", "POSIX shell integration check runs on macOS")
    def test_refresh_after_cd_in_same_shell(self):
        with tempfile.TemporaryDirectory(prefix='qm work ') as folder:
            self.app.check_current_location()
            first_command = self.app.terminal.write.call_args.args[0].strip()
            self.app.check_current_location()
            second_command = self.app.terminal.write.call_args.args[0].strip()
            script = first_command + "\ncd " + shlex.quote(folder) + "\n" + second_command
            result = subprocess.run(['/bin/sh'], input=script, capture_output=True, text=True, check=True)
            self.app.process_output(result.stdout)
            self.assertTrue(self.app.user_status.get().endswith('Folder: ' + str(Path(folder).resolve())))

    def test_conpty_rendered_response_wrapping(self):
        self.app.check_current_location()
        frame = self.frame('max', '/home/max/a folder with spaces').strip()
        # ConPTY can replace newlines with cursor-addressing sequences.
        self.app.process_output('\x1b[2;1H' + frame[:70] + '\x1b[3;1H' + frame[70:])
        self.assertEqual(self.app.user_status.get(), 'Current user: max | Folder: /home/max/a folder with spaces')

    def test_list_current_directory_uses_active_terminal(self):
        for method in ('local', 'remote'):
            self.app.method.set(method)
            self.app.list_current_directory()
            self.app.terminal.write.assert_called_with('pwd -P; ls -lah\r')
        self.app.terminal.write.reset_mock()
        for state in ('calculating', 'disconnecting', 'docker_busy'):
            setattr(self.app, state, True)
            self.app.list_current_directory()
            setattr(self.app, state, False)
        self.app.connected = False
        self.app.list_current_directory()
        self.app.terminal.write.assert_not_called()

    def test_busy_does_not_send(self):
        for state in ('calculated', 'disconnecting', 'disconnected'):
            self.app.calculating = state == 'calculated'
            self.app.disconnecting = state == 'disconnecting'
            self.app.connected = state != 'disconnected'
            self.app.check_current_location()
        self.app.terminal.write.assert_not_called()


class ComposeVersionTests(unittest.TestCase):
    def test_yml_yaml_selection_saved_and_cancel_preserved(self):
        for suffix in ('.yml', '.yaml'):
            with tempfile.TemporaryDirectory() as folder:
                settings = Path(folder) / 'compose-path.txt'
                app = Harness()
                selected = str(Path(folder) / ('compose' + suffix))
                with patch('app_code.docker_controls.filedialog.askopenfilename', return_value=selected) as dialog, patch('app_code.docker_controls.SETTINGS_FOLDER', Path(folder)), patch('app_code.docker_controls.SETTINGS_FILE', settings):
                    LocalControls.choose_yaml(app)
                    self.assertEqual(app.compose_path.get(), selected)
                    self.assertEqual(settings.read_text(), selected)
                    self.assertEqual(LocalControls.load_path(app), selected)
                    self.assertEqual(dialog.call_args.kwargs['filetypes'][0][1], ('*.yml', '*.yaml'))
                    dialog.return_value = ''
                    LocalControls.choose_yaml(app)
                    self.assertEqual(app.compose_path.get(), selected)
                    self.assertFalse(Path(selected).exists())

    def test_version_file_and_title_source(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(VERSION, '0.2.0')
        self.assertEqual((root / 'VERSION').read_text().strip(), VERSION)
        self.assertIn('self.title(f"Quantum ESPRESSO Controller v{VERSION}")', (root / 'app_code/window.py').read_text())
