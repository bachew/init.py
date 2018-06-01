# -*- coding: utf-8 -*-
from __future__ import print_function
from functools import wraps
from os import path as osp
from subprocess import list2cmdline
from textwrap import dedent
import errno
import os
import runpy
import subprocess
import sys


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


class Init(object):
    version = '0.0.1'
    help_url = 'https://github.com/bachew/init.py'
    script_url = 'https://github.com/bachew/init.py/blob/master/init.py'
    base_dir = osp.abspath(osp.dirname(__file__))
    config_path = osp.join(base_dir, 'init_config.py')

    @InitError.system_exit
    def __init__(self, argv):
        self.script = argv[0]
        options, self.command = self.split_args(argv[1:])

        if set(['-h', '--help']).intersection(options):
            self.print_help()
            raise SystemExit

        ensure_file(self.config_path, dedent('''\
            def check_python_version(version):
                return version >= (2, 7)
            '''))
        self.config = runpy.run_path(self.config_path)

        self.check_python_version()

        if '--upgrade' in options:
            self.upgrade()

        changed_dir = False

        if not osp.samefile(self.base_dir, os.getcwd()):
            print('cd {!r}'.format(self.base_dir))
            os.chdir(self.base_dir)
            changed_dir = True

        # Have to to be in base dir for pipenv to work
        self.initialize()

        if changed_dir:
            print('Note that working directory was {!r}'.format(self.base_dir))

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
            init.py version {version} ({help_url})

            Initialize project by:
            - create or update virtualenv
            - run 'inv init'
            - run the provided command in virtualenv

            Arguments:
              command     Command to execute after initialization

            Options:
              -h, --help  Show this help message and exit
              --upgrade   Upgrade {init_py} to the latest version
                          ({script_url})
        '''.format(version=self.version,
                   help_url=self.help_url,
                   init_py=__file__,
                   script_url=self.script_url)
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

        print('Checking Python version')
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

        self.check_pipenv()

        # Running 'python -m pipenv install' creates virtualenv using the
        # same interpreter. But if the virtualenv already exists and it has
        # different python version, virtualenv won't be recreated
        self.pipenv(['install'])

        venv_py_version = self.get_venv_py_version()

        if venv_py_version != sys.version:
            msg = dedent('''\
                Updating virtualenv Python version from:
                {}

                To:
                {}
                ''').format(venv_py_version, sys.version)
            print(msg)
            # Providing --python option forces virtualenv to be recreated
            self.pipenv(['--python', sys.executable, 'run', 'python', '-c', '# update virtualenv Python version'])

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

    def check_pipenv(self):
        try:
            import pipenv  # noqa
        except ImportError as e:
            msg = dedent('''\
                {error}
                You can install pipenv module by running:
                  sudo {python} -m pip install pipenv\
            ''').format(error=e,
                        python=sys.executable)
            raise InitError(msg)

        # TODO: check pipenv version, similar to check_python_version()

    def pipenv(self, args, **kwargs):
        return run([sys.executable, '-m', 'pipenv'] + args, **kwargs)

    def get_venv_py_version(self):
        cmd = [
            sys.executable, '-m',
            'pipenv', 'run',
            'python', '-c',
            'import sys; sys.stdout.write(str(sys.version))'
        ]
        output = subprocess.check_output(cmd)
        return str(output.decode(sys.stdout.encoding))


class CommandFailed(InitError):
    def __init__(self, cmd, error):
        msg = 'Command {!r} failed with error code {!r}'.format(list2cmdline(cmd), error)
        super(CommandFailed, self).__init__(msg)


class ProgramNotFound(InitError):
    def __init__(self, cmd):
        msg = 'Program {!r} not found, command: {}'.format(cmd[0], list2cmdline(cmd))
        super(ProgramNotFound, self).__init__(msg)


def print_error(message):
    print('ERROR:', message, file=sys.stderr)


def run(cmd, raise_error=True, **kwargs):
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


def ensure_file(path, content):
    path = osp.abspath(path)

    if osp.isfile(path):
        return

    print('File {!r} does not exist, creating it'.format(path))

    with open(path, 'w') as f:
        f.write(content)


if __name__ == '__main__':
    Init(sys.argv)
