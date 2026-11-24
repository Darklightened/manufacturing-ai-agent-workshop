"""Command/preflight tests only; no SSH connection, remote changes or public listener."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import socket
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location('classroom_tunnel', Path(__file__).resolve().parents[1] / 'scripts/start_classroom_tunnel.py')
tunnel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tunnel)


class TunnelTests(unittest.TestCase):
    def test_loopback_and_noninteractive_command(self):
        cmd, _ = tunnel.ssh_command('teacher@public.example', known_hosts='/tmp/trusted_hosts')
        self.assertIn('127.0.0.1:18921:127.0.0.1:8921', cmd)
        for option in ['BatchMode=yes', 'StrictHostKeyChecking=yes', 'ExitOnForwardFailure=yes', 'ForwardAgent=no', 'ControlPath=none']:
            self.assertIn(option, cmd)
        self.assertEqual(cmd[-1], 'teacher@public.example')
        self.assertNotIn('0.0.0.0', ' '.join(cmd))

    def test_argument_injection_rejected(self):
        for target in ['-oProxyCommand=bad', 'host;touch file', 'host$(command)', 'host user', 'a\nb', 'a@@b']:
            with self.assertRaises(ValueError):
                tunnel.ssh_command(target)
        for port in [0, -1, 65536]:
            with self.assertRaises(ValueError):
                tunnel.ssh_command('host', local_port=port)

    def test_missing_key_has_no_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            cmd, hosts = tunnel.ssh_command('host', known_hosts=Path(directory) / 'missing')
            with patch.object(tunnel.subprocess, 'run') as call:
                self.assertFalse(tunnel.check_known_host(cmd, hosts)['verified_entry_exists'])
                call.assert_not_called()
            with redirect_stdout(io.StringIO()), patch.object(tunnel, 'run_tunnel') as launch:
                tunnel.main(['--ssh-target', 'host', '--known-hosts', str(hosts)])
                launch.assert_not_called()
            with redirect_stderr(io.StringIO()), patch.object(tunnel, 'run_tunnel') as launch:
                with self.assertRaises(SystemExit):
                    tunnel.main(['--ssh-target', 'host', '--known-hosts', str(hosts), '--run'])
                launch.assert_not_called()

    def test_known_key_lookup_honors_nonstandard_port(self):
        with tempfile.NamedTemporaryFile() as hosts:
            cmd, path = tunnel.ssh_command('alias', known_hosts=hosts.name)
            results = [subprocess.CompletedProcess([], 0, 'hostname public.example\nport 2222\nremoteforward 127.0.0.1:18921 [127.0.0.1]:8921\n', ''), subprocess.CompletedProcess([], 0, 'public host key', '')]
            with patch.object(tunnel.subprocess, 'run', side_effect=results) as calls:
                self.assertTrue(tunnel.check_known_host(cmd, path)['verified_entry_exists'])
                self.assertIn('[public.example]:2222', calls.call_args_list[1].args[0])

    def test_cpu_child_reconnect_budget_and_expiry(self):
        # Harmless Python child processes, no SSH or remote requests.
        for mode, expected_attempts, expected_rc in [('retry', 3, 1), ('fatal', 1, 255), ('expiry', 1, 0)]:
            listener = socket.socket()
            listener.bind(('127.0.0.1', 0))
            listener.listen(2)
            output = io.StringIO()
            code = {'retry': 'import sys;sys.exit(1)', 'fatal': 'import sys;sys.stderr.write("Permission denied");sys.exit(255)', 'expiry': 'import time;time.sleep(30)'}[mode]
            try:
                with redirect_stdout(output), patch.object(tunnel.signal, 'signal'):
                    rc = tunnel.run_tunnel([sys.executable, '-c', code], listener.getsockname()[1], .0001 if mode == 'expiry' else .01, reconnects=2, reconnect_delay=.01)
                rows = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertEqual(rc, expected_rc)
                self.assertEqual(sum(row['state'] == 'ssh_started' for row in rows), expected_attempts)
                if mode == 'expiry':
                    self.assertEqual(rows[-1]['reason'], 'expired')
            finally:
                listener.close()

    def test_extra_inherited_forwarding_is_rejected(self):
        with tempfile.NamedTemporaryFile() as hosts:
            cmd, path = tunnel.ssh_command('alias', known_hosts=hosts.name)
            result = subprocess.CompletedProcess([], 0, 'hostname host\nport 22\nremoteforward [127.0.0.1]:18921 [127.0.0.1]:8921\nlocalforward 8080 127.0.0.1:80\n', '')
            with patch.object(tunnel.subprocess, 'run', return_value=result):
                self.assertFalse(tunnel.check_known_host(cmd, path)['verified_entry_exists'])

    def test_exited_child_cleanup_race(self):
        child = Mock(pid=999999)
        child.poll.return_value = None
        with patch.object(tunnel.os, 'killpg', side_effect=ProcessLookupError):
            tunnel.stop_owned_child(child)
        child.wait.assert_called_once_with(timeout=5)

    def test_limits_fail_before_launch(self):
        for option, value in [('--hours', '0'), ('--hours', '169'), ('--hours', 'nan'), ('--reconnects', '6')]:
            with redirect_stderr(io.StringIO()), patch.object(tunnel, 'run_tunnel') as launch:
                with self.assertRaises(SystemExit):
                    tunnel.main(['--ssh-target', 'alias', option, value, '--run'])
                launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
