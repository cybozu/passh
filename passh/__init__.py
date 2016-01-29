# Copyright (c) 2015 Cybozu.
# Released under the MIT license
# http://opensource.org/licenses/mit-license.php
'''
Execute SSH in parallel.
'''

import argparse
import asyncio
import functools
from os.path import exists
import sys


# Constants
__all__ = ['PAssh']
_SSH = ('ssh', '-T', '-o', 'LogLevel=ERROR', '-o', 'ConnectTimeout=6')
_INSECURE_OPTS = (
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'UserKnownHostsFile=/dev/null',
)


# Implementation
class PAsshProtocol(asyncio.SubprocessProtocol):
    '''An asyncio.SubprocessProtocol for PAssh.'''
    def __init__(self, hostname: str,
                 exit_future: asyncio.Future, use_stdout: bool):
        self._hostname = hostname
        self._prefix = b'[' + hostname.encode('utf-8') + b'] '
        self._exit_future = exit_future
        self._use_stdout = use_stdout
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._exited = False
        self._closed_stdout = False
        self._closed_stderr = False

    @property
    def finished(self):
        return self._exited and self._closed_stdout and self._closed_stderr

    def signal_exit(self):
        if not self.finished:
            return
        self.flush()
        self._exit_future.set_result(True)

    def pipe_data_received(self, fd, data):
        if fd == 1:
            self._stdout.extend(data)
            if self._use_stdout:
                return
            self.flush_line(self._stdout, sys.stdout.buffer)
        elif fd == 2:
            self._stderr.extend(data)
            self.flush_line(self._stderr, sys.stderr.buffer)

    def pipe_connection_lost(self, fd, exc):
        if fd == 1:
            self._closed_stdout = True
        elif fd == 2:
            self._closed_stderr = True
        self.signal_exit()

    def process_exited(self):
        self._exited = True
        self.signal_exit()

    def get_stdout(self) ->bytes:
        return bytes(self._stdout)

    def flush_line(self, buf: bytearray, out):
        pos = buf.rfind(b'\n')
        if pos == -1:
            return
        b = bytearray()
        for line in buf[0:pos+1].splitlines(True):
            b.extend(self._prefix)
            b.extend(line)
            out.write(b)
            b.clear()
        out.flush()
        del buf[0:pos+1]

    def _flush(self, buf: bytearray, out):
        if len(buf) == 0:
            return
        b = bytearray()
        b.extend(self._prefix)
        b.extend(buf)
        b.extend(b'\n')
        out.write(b)
        out.flush()

    def flush(self):
        if not self._use_stdout:
            self._flush(self._stdout, sys.stdout.buffer)
        self._flush(self._stderr, sys.stderr.buffer)


class PAssh:
    '''Executes SSH in parallel for given hosts.

    This will run SSH on multiple hosts in parallel and output or
    gather the command outputs.

    Command outputs are normally forwarded to the local stdout and
    stderr.  Every output line is prefixed by the remote hostname.

    If "infile" is not None, it should be the path to an existing
    file.  The file will be opened for read and passed as stdin
    for each SSH process.

    If "use_stdout" is True, outputs to stdout are not printed;
    instead, they are gathered in memory which can be retrieved later
    through "outputs" property.

    "nprocs" is the maximum number of processes run in parallel.
    If "nprocs" is 0, unlimited number of processes will run.

    If your environment is insecure, specify "insecure=True" to turn
    on SSH known host verification.

    Args:
        hosts: list of remote hostnames.
        args: list of str representing the remote command.
        infile: path to an existing file.
        use_stdout: True to gather stdout.  False to print them.
        nprocs: the maximum number of processes run in parallel.
        insecure: True to check remote host keys.
    '''

    def __init__(self, hosts: list, args: list, *, infile=None,
                 use_stdout: bool=False, nprocs: int=100, insecure=False):
        self._loop = asyncio.get_event_loop()
        self._hosts = hosts
        self._args = args
        self._infile = infile
        self._use_stdout = use_stdout
        self._nprocs = nprocs
        self._sem = None
        self._secure = not insecure

        self._failures = []
        self._outputs = {}
        self._exc = None
        self._cancel_on_error = False

    @property
    def failed_hosts(self) ->list:
        '''List of hostnames where SSH failed.'''
        return self._failures

    @property
    def outputs(self) ->dict:
        '''A dict between hostname and SSH stdout (bytes).
        Available only when constructed with use_stdout=True.'''
        return self._outputs

    @asyncio.coroutine
    def _run1(self, host: str):
        exit_future = asyncio.Future(loop=self._loop)
        stdin = None
        if self._infile is not None:
            stdin = open(self._infile, 'rb')
            exit_future.add_done_callback(lambda x: stdin.close())
        cmd = list(_SSH)
        if self._secure:
            cmd.extend(_INSECURE_OPTS)
        cmd.append(host)
        cmd += self._args
        proc = self._loop.subprocess_exec(
            functools.partial(
                PAsshProtocol, host, exit_future, self._use_stdout,
            ), *cmd, stdin=stdin)
        transport, protocol = yield from proc
        yield from exit_future
        transport.close()
        if transport.get_returncode() != 0:
            self._failures.append(host)
            return
        if self._use_stdout:
            self._outputs[host] = protocol.get_stdout()

    @asyncio.coroutine
    def _run(self, host: str):
        try:
            if self._nprocs == 0:
                yield from self._run1(host)
                return
            if self._sem is None:
                self._sem = asyncio.Semaphore(self._nprocs, loop=self._loop)
            with (yield from self._sem):
                yield from self._run1(host)
        except Exception as e:
            if not self._cancel_on_error:
                raise e
            self._exc = e
            for task in asyncio.Task.all_tasks(self._loop):
                task.cancel()

    def wait(self, *, timeout=None, return_when=asyncio.ALL_COMPLETED):
        '''Calls asyncio.wait to wait all SSH processes.

        Use asyncio.async (or asyncio.ensure_future) to embed passh
        in your asyncio applications:

            p = passh.PAssh([host1, host2], ['date'])
            task = asyncio.async(p.wait())
            task.add_done_callback(...)  # use PAssh results

        Or you can use "yield from" of cousrse:

            p = passh.PAssh([host1, host2], ['date'])
            done, _ = yield from p.wait()
            for task in done:
                task.result()  # check the result

        Returns:
            A coroutine.
        '''
        return asyncio.wait([self._run(h) for h in self._hosts],
                            loop=self._loop, timeout=timeout,
                            return_when=return_when)

    def run(self) ->bool:
        '''Run SSH in parallel.

        This invokes loop.run_until_complete() to wait completion
        of all SSH processes.  If you want to embed passh in your
        asyncio application, use wait().

        Returns:
            True if no SSH process fails; False otherwise.
        '''
        if len(self._hosts) == 0:
            return True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._cancel_on_error = True
            self._loop.run_until_complete(self.wait())
        except asyncio.CancelledError:
            pass
        finally:
            self._loop.close()
        if self._exc is not None:
            # pylint: disable=E0702
            raise self._exc
        return len(self._failures) == 0


def main():
    p = argparse.ArgumentParser(
        description='Run SSH in parallel',
        usage='%(prog)s [-n PROCS] [-i FILE] host1[,host2,...] CMD [ARG1 ...]')
    p.add_argument('-n', dest='procs', metavar='PROCS', type=int, default=50)
    p.add_argument('-i', dest='infile', metavar='FILE', default=None)
    p.add_argument('hosts')
    p.add_argument('cmd')
    p.add_argument('args', nargs=argparse.REMAINDER)
    ns = p.parse_args()
    hosts = ns.hosts.split(',')
    if ns.infile is not None and not exists(ns.infile):
        print('No such file:', ns.infile, file=sys.stderr)
        sys.exit(1)
    ssh = PAssh(hosts, [ns.cmd]+ns.args, infile=ns.infile, nprocs=ns.procs)
    if not ssh.run():
        print("failed at: {}".format(' '.join(ssh.failed_hosts)),
              file=sys.stderr)
        sys.exit(2)


# main
if __name__ == '__main__':
    main()
