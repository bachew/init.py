# -*- coding: utf-8 -*-
from __future__ import print_function
from contextlib import contextmanager
from functools import wraps
from os import path as osp
from subprocess import list2cmdline
from textwrap import dedent
import errno
import os
import runpy
import subprocess
import sys


VERSION = '0.0.1'
HELP_URL = 'https://github.com/bachew/init.py'
SCRIPT_URL = 'https://github.com/bachew/init.py/blob/master/init.py'


class InitError(Exception):
    @classmethod
    def system_exit(cls, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except cls as e:
                print_error(e)
                raise SystemExit(1)

        return wrapper


class CommandFailed(InitError):
    def __init__(self, cmd, error):
        msg = 'Command {!r} failed with error code {!r}'.format(list2cmdline(cmd), error)
        super(CommandFailed, self).__init__(msg)


class ProgramNotFound(InitError):
    def __init__(self, cmd):
        msg = 'Program {!r} not found, command: {}'.format(cmd[0], list2cmdline(cmd))
        super(ProgramNotFound, self).__init__(msg)


class main(object):
    @InitError.system_exit
    def __init__(self, argv):
        self.script = argv[0]
        options, self.command = self.split_args(argv[1:])
        self.command_str = list2cmdline(self.command)

        if set(['-h', '--help']).intersection(options):
            self.print_help()
            raise SystemExit

        self.base_dir = osp.abspath(osp.dirname(__file__))
        self.config_path = osp.join(self.base_dir, 'init_config.py')
        self.config_module = osp.splitext(self.config_path)[0]
        self.config = self.load_config()
        self.check_python_version()

        if '--upgrade' in options:
            self.upgrade()

        # TODO: cd is quite confusing, maybe force user to cd manually
        with change_dir(self.base_dir):
            # TODO: consider setting PIPENV_VENV_IN_PROJECT=true for pipenv commands
            self.initialize()

            if self.command:
                status = run(['pipenv', 'run'] + self.command, raise_error=False)
                raise SystemExit(status)

    def split_args(self, args):
        i = 0

        for arg in args:
            if not arg.startswith('-'):
                break

            i += 1

        return args[:i], args[i:]

    def print_help(self):
        self.print_usage()

        details = '''
            init.py v{version} ({help_url})

            Initialize project by:
            - create or update virtual env
            - run 'inv init'
            - run the provided command

            Arguments:
              command     Command to execute after initialization

            Options:
              -h, --help  Show this help message and exit
              --upgrade   Upgrade {init_py} to the latest version
                          ({script_url})
        '''.format(version=VERSION,
                   help_url=HELP_URL,
                   init_py=__file__,
                   script_url=SCRIPT_URL)
        print(dedent(details))

    def print_usage(self):
        print('Usage: {} [-h/--help] [--upgrade] [command]'.format(self.script))

    def load_config(self):
        ensure_file(self.config_path, dedent('''\
            def check_python_version(version):
                return version >= (2, 7)
            '''))
        return runpy.run_path(self.config_path)

    def check_python_version(self):
        key = 'check_python_version'
        check = self.config.get(key)

        if not check:
            name = '{}:{}'.format(self.config_path, key)
            print('Config {!r} not found, skip checking'.format(name))
            return

        version = sys.version_info
        print('>>> {}.{}({!r})'.format(self.config_module, key, version))
        ok = check(version)
        print('>>> {!r}'.format(ok))

        if not ok:
            raise InitError('Python version not OK, see {!r}'.format(self.config_path))

        print('Python version OK')

    def upgrade(self):
        print('TODO: upgrade {!r} from {!r}'.format(__file__, self.SCRIPT_URL))

    def initialize(self):
        ensure_file('Pipfile', dedent('''\
            [[source]]
            url = "https://pypi.org/simple"
            verify_ssl = true
            name = "pypi"
            '''))
        run(['pipenv', 'install'])
        run(['pipenv', 'install', 'invoke>=1.0.0'])

        ensure_file('invoke.py', dedent('''\
            debug = True
            run = {
                'echo': True,
                'pty': True,
            }
            '''))
        ensure_file('tasks.py', dedent('''\
            from invoke import task

            @task
            def init(ctx):
                ctx.run('echo tasks.py says hi')
            '''))
        run(['pipenv', 'run', 'inv', 'init'])


def print_error(message):
    print('ERROR:', message, file=sys.stderr)


def run(cmd, raise_error=True):
    print('$ {}'.format(list2cmdline(cmd)))

    try:
        error = subprocess.call(cmd)
    except OSError as e:
        if e.errno == errno.ENOENT:
            raise ProgramNotFound(cmd)
        else:
            raise

    if error:
        raise CommandFailed(cmd, error)


@contextmanager
def change_dir(dirname):
    orig_dir = os.getcwd()
    same = osp.samefile(dirname, orig_dir)

    if not same:
        print('cd {!r}'.format(dirname))
        os.chdir(dirname)

    try:
        yield
    finally:
        if not same:
            print('cd {!r} from {!r}'.format(orig_dir, dirname))
            os.chdir(orig_dir)


def ensure_file(path, content):
    if osp.isfile(path):
        return

    print('File {!r} does not exist, creating it'.format(path))

    with open(path, 'w') as f:
        f.write(content)


if __name__ == '__main__':
    main(sys.argv)
