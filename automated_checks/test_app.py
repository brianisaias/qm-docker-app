import unittest
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
import pyte
import app_code.window as module


class DisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            subprocess.run([sys.executable, "-c", "import tkinter as tk; root=tk.Tk(); root.destroy()"], check=True, capture_output=True, timeout=10)
        except (subprocess.SubprocessError, OSError) as error:
            raise unittest.SkipTest(f"Tk graphical session unavailable: {type(error).__name__}")

    def setUp(self):
        self.no_poll = patch.object(module.QuantumApp, 'refresh_docker_status')
        self.no_poll.start()
        self.app = module.QuantumApp()
        self.app.geometry('850x720')
        self.app.update()
        self.app.screen = pyte.Screen(100, 24)
        self.app.stream = pyte.Stream(self.app.screen)
        self.app.ready_marker = 'TEST_READY'

    def tearDown(self):
        for callback in self.app.tk.call('after', 'info'):
            self.app.after_cancel(callback)
        self.app.destroy()
        self.no_poll.stop()

    def test_version_password_and_compose_widgets(self):
        self.assertEqual(self.app.title(), 'Quantum ESPRESSO Controller v0.4.0')
        self.assertEqual(str(self.app.password_entry['show']), '*')
        self.assertEqual(str(self.app.choose_button['text']), 'Choose Docker Compose File')

    def test_password_prompt_visible_and_connection_not_assumed(self):
        self.app.method.set('remote')
        self.app.process_output('\x1b[24;1Huser@server pass')
        self.app.process_output('word: ')
        self.app.render_terminal()
        self.app.update()
        self.assertIsNotNone(self.app.terminal_view.bbox('24.0'))
        self.assertIn('PASSWORD REQUIRED', self.app.activity.get())
        self.assertFalse(self.app.connected)

    def test_docker_status_distinguishes_running_and_stopped(self):
        self.assertIn('RUNNING', self.app.docker_description('id', {'Running': True})[0])
        self.assertIn('STOPPED', self.app.docker_description('id', {'Running': False})[0])
        self.assertIn('NOT CREATED', self.app.docker_description(None, {})[0])

    def test_session_close_does_not_claim_docker_stopped(self):
        self.app.docker_status.set('Docker: RUNNING')
        self.app.events.put(('closed', ''))
        self.app.poll_events()
        self.assertEqual(self.app.connection_status.get(), 'Terminal: DISCONNECTED')
        self.assertEqual(self.app.docker_status.get(), 'Docker: RUNNING')

    def test_stop_failure_is_not_reported_as_stopped(self):
        self.app.events.put(('docker_stop_error', 'Cannot connect to Docker'))
        self.app.poll_events()
        self.assertIn('STOP FAILED', self.app.docker_status.get())
        self.assertIn('Cannot connect', self.app.activity.get())

    def test_function_tabs_and_terminal_fit_window(self):
        tabs = self.app.sections.tabs()
        self.assertEqual([self.app.sections.tab(tab, 'text') for tab in tabs],
                         ['1. Connection', '2. Calculations', '3. Files & User'])
        for tab in tabs:
            self.app.sections.select(tab)
            self.app.update()
            self.assertGreater(self.app.terminal_view.winfo_height(), 80)
            for key in ("Check current location", "List current directory", "Stop Calculation"):
                self.assertEqual(self.app.buttons[key].master, self.app.quick_actions)
                self.assertTrue(self.app.buttons[key].winfo_ismapped())
        self.assertEqual(str(self.app.buttons['Run pw.x']['text']), 'Start pw.x without a file')
        self.assertEqual(str(self.app.buttons['Run Calculation']['text']), '4. Run input and save output')
        self.assertEqual(str(self.app.buttons['Check Results']['text']), '5. Check results')

    def test_remote_disables_local_stop(self):
        self.app.method.set('remote')
        self.app.update_controls()
        self.assertEqual(str(self.app.stop_docker_button['state']), 'disabled')

    def test_local_marker_with_cursor_movement_enables_controls(self):
        self.app.active = True
        self.app.method.set('local')
        self.app.process_output('\x1b[2;1HTEST_')
        self.assertFalse(self.app.connected)
        self.app.process_output('READY\x1b[3;1Hmax@container:~/work$ ')
        self.assertTrue(self.app.connected)
        self.assertEqual(str(self.app.buttons['Run Calculation']['state']), 'normal')

    def test_local_start_is_available_when_disconnected(self):
        self.app.active = False
        self.app.docker_busy = False
        self.app.method.set('local')
        self.app.update_controls()
        self.assertEqual(str(self.app.buttons['Connect']['state']), 'normal')

    def test_echoed_marker_in_command_does_not_connect(self):
        self.app.process_output("max$ printf TEST_READY\r\n")
        self.assertFalse(self.app.connected)

    def test_connect_button_dispatches_school_server(self):
        self.app.method.set('remote')
        self.app.bronco_id.set('testuser')
        self.app.update_controls()
        with patch.object(module.threading, 'Thread') as thread:
            self.app.buttons['Connect'].invoke()
            thread.return_value.start.assert_called_once()
            self.assertEqual(thread.call_args.kwargs['args'][0], 'remote')
        self.assertTrue(self.app.active)
        self.assertIn('CONNECTING', self.app.connection_status.get())

    def test_connect_button_dispatches_local(self):
        self.app.method.set('local')
        self.app.compose_path.set(__file__)
        self.app.update_controls()
        with patch.object(module.threading, 'Thread') as thread:
            self.app.buttons['Connect'].invoke()
            thread.return_value.start.assert_called_once()
            self.assertEqual(thread.call_args.kwargs['args'][0], 'local')

    def test_missing_id_produces_visible_feedback(self):
        self.app.method.set('remote')
        self.app.bronco_id.set('')
        self.app.update_controls()
        self.app.buttons['Connect'].invoke()
        self.assertFalse(self.app.active)
        self.assertIn('Bronco ID', self.app.connection_log.get('1.0', 'end'))

    def test_run_pw_direct_has_no_input_dialog(self):
        self.app.connected = True
        self.app.active = True
        self.app.update_controls()
        with patch.object(self.app, 'send') as send, patch.object(module.simpledialog, 'askstring') as dialog:
            self.app.buttons['Run pw.x'].invoke()
            dialog.assert_not_called()
            command = send.call_args.args[0]
            self.assertIn('pw.x;', command)
            self.assertNotIn('pw.x -in', command)
            self.assertTrue(self.app.calculating)

    def test_guided_calculation_saves_matching_output(self):
        self.app.connected = True
        self.app.active = True
        self.app.update_controls()
        with patch.object(self.app, 'send') as send, patch.object(module.simpledialog, 'askstring', return_value='basic.in'):
            self.app.buttons['Run Calculation'].invoke()
        command = send.call_args.args[0]
        self.assertIn('pw.x -input basic.in > basic.out 2>&1', command)
        self.assertEqual(self.app.last_output_file, 'basic.out')
        self.assertTrue(self.app.calculating)

    def test_create_folder_and_review_files_use_current_terminal(self):
        self.app.connected = True
        self.app.active = True
        self.app.update_controls()
        with patch.object(self.app, 'send') as send, patch.object(module.simpledialog, 'askstring', return_value='basic'):
            self.app.buttons['Create Calculation Folder'].invoke()
            self.assertIn("mkdir -p -- basic && cd -- basic", send.call_args.args[0])
            send.reset_mock()
            self.app.review_calculation_files()
            self.assertIn("-name '*.in'", send.call_args.args[0])
            self.assertIn("-name '*.UPF'", send.call_args.args[0])

    def test_check_results_looks_for_completion_and_energy(self):
        self.app.connected = True
        self.app.active = True
        self.app.last_output_file = 'basic.out'
        self.app.update_controls()
        with patch.object(self.app, 'send') as send, patch.object(module.simpledialog, 'askstring', return_value='basic.out'):
            self.app.buttons['Check Results'].invoke()
        command = send.call_args.args[0]
        self.assertIn('JOB DONE', command)
        self.assertIn('total energy', command)
        self.assertIn('basic.out', command)

    def test_local_file_navigation_and_import(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as incoming:
            root = Path(folder)
            (root / 'inputs').mkdir()
            source = Path(incoming) / 'example.in'
            source.write_text('test input')
            window = module.LocalFilesWindow(self.app, root, True)
            try:
                key = next(k for k, v in window.entries.items() if v.name == 'inputs')
                window.tree.selection_set(key)
                window.enter()
                self.assertEqual(window.folder, root / 'inputs')
                with patch.object(module.filedialog, 'askopenfilenames', return_value=[str(source)]):
                    window.import_files()
                    self.assertEqual((root / 'inputs/example.in').read_text(), 'test input')
                    with self.assertRaises(FileExistsError):
                        window.import_files()
                window.up()
                window.up()
                self.assertEqual(window.folder, root)
            finally:
                window.destroy()

    def test_local_file_deletion_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'example.in'
            target.write_text('test')
            window = module.LocalFilesWindow(self.app, Path(folder), True)
            try:
                window.tree.selection_set(next(iter(window.entries)))
                with patch.object(module.messagebox, 'askyesno', return_value=False):
                    window.delete()
                self.assertTrue(target.exists())
                with patch.object(module.messagebox, 'askyesno', return_value=True):
                    window.delete()
                self.assertFalse(target.exists())
                with self.assertRaises(RuntimeError):
                    window.checked(Path(folder).parent)
            finally:
                window.destroy()


if __name__ == '__main__':
    unittest.main()
