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
CONFIG_FILE = 'init_config.py'


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

        if set(['-h', '--help']).intersection(options):
            self.print_help()
            raise SystemExit

        self.base_dir = osp.abspath(osp.dirname(__file__))
        self.config_path = osp.join(self.base_dir, 'init_config.py')

        ensure_file(self.config_path, dedent('''\
            def check_python_version(version):
                return version >= (2, 7)
            '''))
        self.config = runpy.run_path(self.config_path)

        self.check_python_version()

        if '--upgrade' in options:
            self.upgrade()

        with change_dir(self.base_dir):
            self.initialize()

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
            - create or update virtualenv
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

    @property
    def config_module(self):
        return osp.splitext(osp.basename(self.config_path))[0]

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

        # Running 'python -m pipenv install' creates virtualenv using the
        # same interpreter. But if the virtualenv already exists and it has
        # different python version, virtualenv won't be recreated
        self.pipenv(['install'])

        venv_py_version = self.get_venv_py_version()

        if venv_py_version != sys.version:
            # TODO: more friendly message
            print(('Recreating virtualenv because its Python version {!r}'
                   ' is different from current Python version {!r}').format(
                venv_py_version, sys.version))
            # Providing --python option forces virtualenv to be recreated
            self.pipenv(['--python', sys.executable, 'run', 'python', '-c', ''],
                        print_command=False)

        self.pipenv(['install', 'invoke>=1.0.0'])

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

        self.pipenv(['run', 'inv', 'init'])

        if self.command:
            status = self.pipenv(['run'] + self.command, raise_error=False)
            raise SystemExit(status)

    def pipenv(self, args, **kwargs):
        try:
            import pipenv  # noqa
        except ImportError:
            raise InitError('pipenv not installed')  # TODO: be helpful

        return run([sys.executable, '-m', 'pipenv'] + args, **kwargs)

    def get_venv_py_version(self):
        cmd = [
            sys.executable, '-m',
            'pipenv', 'run',
            'python', '-c',
            'import sys; sys.stdout.write(str(sys.version))'
        ]
        output = subprocess.check_output(cmd)
        return output.decode(sys.stdout.encoding)


def print_error(message):
    print('ERROR:', message, file=sys.stderr)


def run(cmd, print_command=True, raise_error=True, **kwargs):
    if print_command:
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
            print('cd {!r}  # from {!r}'.format(orig_dir, dirname))
            os.chdir(orig_dir)


def ensure_file(path, content):
    if osp.isfile(path):
        return

    print('File {!r} does not exist, creating it'.format(path))

    with open(path, 'w') as f:
        f.write(content)


if __name__ == '__main__':
    main(sys.argv)
