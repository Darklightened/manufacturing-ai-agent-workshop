#!/usr/bin/env python3
"""Prepare or run a finite SSH reverse tunnel; remote listening is loopback only."""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import threading
import time


def ssh_command(target, local_port=8921, remote_port=18921, known_hosts=None, ssh_port=None, identity_file=None, ssh_config="/dev/null"):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]*', target) or target.count('@') > 1:
        raise ValueError('use a known SSH alias or user@hostname; no shell expression')
    if not all(type(p) is int and 1 <= p <= 65535 for p in (local_port, remote_port)):
        raise ValueError('local/remote ports must be1–65535')
    known_hosts = Path(known_hosts or Path.home() / '.ssh/known_hosts').expanduser().absolute()
    cmd = ['ssh', '-F', str(Path(ssh_config).expanduser().absolute()), '-NT', '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes',
           '-o', 'StrictHostKeyChecking=yes', '-o', 'UpdateHostKeys=no',
           '-o', 'GlobalKnownHostsFile=/dev/null', '-o', f'UserKnownHostsFile={known_hosts}',
           '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=2',
           '-o', 'ConnectTimeout=15', '-o', 'ConnectionAttempts=1',
           '-o', 'ControlMaster=no', '-o', 'ControlPath=none',
           '-o', 'PermitLocalCommand=no', '-o', 'ForwardAgent=no',
           '-o', 'ForwardX11=no', '-o', 'RequestTTY=no']
    if identity_file is not None:
        identity = Path(identity_file).expanduser().absolute()
        if not identity.is_file():
            raise ValueError('identity file missing')
        cmd += ['-i', str(identity), '-o', 'IdentitiesOnly=yes']
    if ssh_port is not None:
        if not 1 <= ssh_port <= 65535:
            raise ValueError('SSH port must be1–65535')
        cmd += ['-p', str(ssh_port)]
    cmd += ['-R', f'127.0.0.1:{remote_port}:127.0.0.1:{local_port}', target]
    return cmd, known_hosts


def check_known_host(cmd, known_hosts):
    if not known_hosts.is_file():
        return {'verified_entry_exists': False, 'reason': 'known_hosts file missing'}
    # Resolve an existing user's alias without opening a connection.
    result = subprocess.run([cmd[0], '-G', *cmd[1:]], capture_output=True, text=True, timeout=15)
    if result.returncode:
        return {'verified_entry_exists': False, 'reason': 'SSH configuration unavailable'}
    config = {}
    forwards = []
    for line in result.stdout.splitlines():
        if ' ' in line:
            key, value = line.split(' ', 1)
            config.setdefault(key, value)
            if key in ('localforward', 'dynamicforward', 'remoteforward'):
                forwards.append((key, value))
    requested = cmd[cmd.index('-R') + 1].split(':')
    expected = f'{requested[0]}:{requested[1]} {requested[2]}:{requested[3]}'
    if len(forwards) != 1 or forwards[0][0] != 'remoteforward' or forwards[0][1].replace('[', '').replace(']', '') != expected:
        return {'verified_entry_exists': False, 'reason': 'unexpected inherited forwarding; use the default empty SSH config'}
    host, port = config.get('hostname'), config.get('port', '22')
    alias = config.get('hostkeyalias')
    if alias == 'none':
        alias = None
    if not host:
        return {'verified_entry_exists': False, 'reason': 'SSH hostname unavailable'}
    lookup = alias or (host if port == '22' else f'[{host}]:{port}')
    found = subprocess.run(['ssh-keygen', '-F', lookup, '-f', str(known_hosts)], capture_output=True, text=True, timeout=10)
    return {'verified_entry_exists': found.returncode == 0, 'host': host, 'port': int(port),
            'reason': 'known entry found; SSH still verifies the actual peer' if found.returncode == 0 else 'trusted host key not found; verify separately before running'}


def stop_owned_child(child):
    if child is None or child.poll() is not None:
        return
    # This is a newly created process group owned by this invocation, never a shared control socket.
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        child.wait(timeout=5)
        return
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait(timeout=5)


def run_tunnel(cmd, local_port, hours, reconnects=3, reconnect_delay=5):
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    with socket.create_connection(('127.0.0.1', local_port), timeout=3):
        pass
    deadline = time.monotonic() + hours * 3600
    expires = datetime.fromtimestamp(time.time() + hours * 3600, timezone.utc).isoformat()
    child = None
    try:
        for attempt in range(reconnects + 1):
            if stop.is_set() or time.monotonic() >= deadline:
                break
            # stderr is kept in memory only long enough to classify startup errors.
            child = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.PIPE, text=True, start_new_session=True)
            chunks = deque(maxlen=64)
            def drain_errors(stream=child.stderr, output=chunks):
                while True:
                    chunk = stream.read(2048)
                    if not chunk:
                        break
                    output.append(chunk)
            drain = threading.Thread(target=drain_errors, daemon=True)
            drain.start()
            print(json.dumps({'state': 'ssh_started', 'attempt': attempt + 1, 'pid': child.pid,
                              'expires_utc': expires, 'public_reachability': 'unverified'}), flush=True)
            while child.poll() is None and not stop.is_set() and time.monotonic() < deadline:
                stop.wait(min(1, max(0, deadline - time.monotonic())))
            if child.poll() is None:
                stop_owned_child(child)
                print(json.dumps({'state': 'stopped', 'reason': 'signal' if stop.is_set() else 'expired'}), flush=True)
                return 0
            drain.join(timeout=2)
            stderr = ''.join(chunks)
            child.stderr.close()
            fatal = any(s in stderr.lower() for s in ('host key verification failed', 'remote port forwarding failed',
                                                       'permission denied', 'bad configuration option', 'offending'))
            print(json.dumps({'state': 'ssh_exited', 'attempt': attempt + 1, 'returncode': child.returncode,
                              'retry': not fatal and attempt < reconnects}), flush=True)
            if child.returncode == 0 or fatal or attempt == reconnects:
                return child.returncode or 0
            stop.wait(min(reconnect_delay, max(0, deadline - time.monotonic())))
        return 0
    finally:
        stop_owned_child(child)
        if child is not None and child.stderr is not None:
            child.stderr.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh-target', required=True, help='Known SSH alias or user@hostname')
    parser.add_argument('--ssh-port', type=int)
    parser.add_argument('--known-hosts', '--known-hosts-file', dest='known_hosts', type=Path, default=Path.home() / '.ssh/known_hosts')
    parser.add_argument('--identity-file', type=Path)
    parser.add_argument('--ssh-config', type=Path, default=Path('/dev/null'), help='Default ignores inherited/shared SSH config')
    parser.add_argument('--local-port', type=int, default=8921)
    parser.add_argument('--remote-port', type=int, default=18921)
    parser.add_argument('--hours', type=float, default=72)
    parser.add_argument('--reconnects', type=int, default=3)
    parser.add_argument('--run', action='store_true', help='Actually connect; omission prints checked configuration only')
    args = parser.parse_args(argv)
    if not 0 < args.hours <= 168 or not 0 <= args.reconnects <= 5:
        parser.error('hours must be (0,168] and reconnects0–5')
    try:
        cmd, known_hosts = ssh_command(args.ssh_target, args.local_port, args.remote_port, args.known_hosts, args.ssh_port, args.identity_file, args.ssh_config)
    except ValueError as exc:
        parser.error(str(exc))
    host_status = check_known_host(cmd, known_hosts)
    if not args.run:
        print(json.dumps({'mode': 'configuration_only', 'command': cmd, 'host_key': host_status,
                          'hours': args.hours, 'maximum_attempts': args.reconnects + 1,
                          'remote_bind': f'127.0.0.1:{args.remote_port}', 'public_reachability': 'not tested'}), flush=True)
        return 0
    if not host_status['verified_entry_exists']:
        parser.error(host_status['reason'])
    return run_tunnel(cmd, args.local_port, args.hours, args.reconnects)


if __name__ == '__main__':
    raise SystemExit(main())
