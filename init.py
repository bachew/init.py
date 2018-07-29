# -*- coding: utf-8 -*-
from __future__ import print_function
from functools import wraps
from os import path as osp
from subprocess import CalledProcessError, list2cmdline
from textwrap import dedent
import errno
import os
import runpy
import shutil
import subprocess
import sys


try:
    from urllib.request import urlopen  # noqa
except ImportError:
    from urllib2 import urlopen  # noqa


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
    version = '0.0.5'
    help_url = 'https://github.com/bachew/init.py'
    script_url = 'https://raw.githubusercontent.com/bachew/init.py/master/init.py'
    script_path = osp.abspath(__file__)
    script_basename = osp.basename(script_path)
    base_dir = osp.dirname(script_path)
    config_path = osp.join(base_dir, 'init_config.py')

    @InitError.system_exit
    def __init__(self, argv):
        self.script = argv[0]
        options, self.command = self.split_args(argv[1:])

        def has_flag(*flags):
            return bool(set(flags).intersection(options))

        if has_flag('-h', '--help'):
            self.print_help()
            raise SystemExit

        if has_flag('-v', '--version'):
            print('{} version {}'.format(self.script_basename, self.version))
            raise SystemExit

        ensure_file(self.config_path, dedent('''\
            def check_python_version(version):
                if version[:2] != (2, 7) and version < (3, 4):
                    raise ValueError('requires either 2.7 or >=3.4')
            '''))
        self.config = runpy.run_path(self.config_path)

        self.check_python_version()

        if has_flag('--upgrade'):
            self.upgrade()
            raise SystemExit

        try:
            self.pipenv(['--version'])
        except ProgramNotFound as e:
            raise InitError('{}\nTo install pipenv, see https://docs.pipenv.org'.format(e))

        try:
            venv_dir = self.check_output(['pipenv', '--venv'])
        except CalledProcessError:
            venv_dir = None  # not yet created

        if has_flag('--clean') and venv_dir:
            print('Removing virtualenv {!r}'.format(venv_dir))
            shutil.rmtree(venv_dir)
            venv_dir = None

        self.fresh_venv = venv_dir is None

        change_dir = False

        if not osp.samefile(self.base_dir, os.getcwd()):
            print('cd {!r}'.format(self.base_dir))
            os.chdir(self.base_dir)
            change_dir = True

        # Have to be in base dir for pipenv to work
        self.initialize()

        if change_dir:
            print('Please note that working directory was {!r}'.format(self.base_dir))

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
            Initialize directory {base_dir!r} by:
            - create or update virtualenv using pipenv
            - run 'inv init'
            - and run the command in virtualenv

            For more info, see {help_url}

            Arguments:
              command     Command to execute in virtualenv

            Options:
              -v, --version  Show version and exit
              -h, --help     Show this help message and exit
              --upgrade      Upgrade {script} and exit, source URL:
                             {script_url}
              --clean        Remove virtualenv before creating it
        '''.format(base_dir=self.base_dir,
                   help_url=self.help_url,
                   script=self.script_basename,
                   script_url=self.script_url)
        print(dedent(details))

    def print_usage(self):
        print('Usage: {} [-v/--version] [-h/--help] [--upgrade] [--clean] [command]'.format(self.script))

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
        version = tuple(sys.version_info)
        print('>>> {}.{}({!r})'.format(self.config_module, key, version))
        try:
            check(version)
        except ValueError as e:
            version_str = '.'.join([str(v) for v in sys.version_info])
            raise InitError('Unsupported Python version {}: {}'.format(version_str, e))

    def upgrade(self):
        print('Downloading {!r}'.format(self.script_url))

        encoding = 'utf-8'
        fobj = urlopen(self.script_url)

        try:
            script = fobj.read().decode(encoding)
        finally:
            fobj.close()

        # Write in one go
        block_size = os.stat(__file__).st_size * 2

        with open(self.script_path, 'wb', buffering=block_size) as fobj:
            fobj.write(script.encode(encoding))

        print('Upgraded {!r}'.format(self.script_path))

    def check_output(self, cmd):
        output = subprocess.check_output(cmd)
        return str(output.decode(sys.stdout.encoding)).strip()

    def initialize(self):
        ensure_file('Pipfile', dedent('''\
            [[source]]
            url = "https://pypi.org/simple"
            verify_ssl = true
            name = "pypi"
            '''))

        recreate = False

        if self.fresh_venv:
            recreate = True
        else:
            venv_py_version = self.check_output([
                'pipenv', 'run',
                'python', '-c',
                'import sys; sys.stdout.write(str(sys.version))'
            ])
            same_py_versions = venv_py_version == sys.version

            if not same_py_versions:
                print('Changing virtualenv Python version from {!r} to {!r}'.format(venv_py_version, sys.version))

            recreate = not same_py_versions

        if recreate:
            # --python option forces virtualenv to be recreated
            self.pipenv(['--python', sys.executable, 'run', 'python', '--version'])
            # Pipenv doesn't upgrade pip automatically
            self.pipenv(['run', 'pip', 'install', '-U', 'pip'])

        self.pipenv(['install'])

        ensure_file('invoke.py', dedent('''\
            debug = True
            run = {
                'echo': True,
                'pty': True,
            }
            '''))
        ensure_file('tasks/__init__.py', dedent('''\
            from invoke import task


            @task
            def init(ctx):
                ctx.run('echo tasks.py says hi')
            '''))
        self.pipenv(['install', 'invoke>=1.0.0'])
        self.pipenv(['run', 'inv', 'init'])

        if self.command:
            status = self.pipenv(['run'] + self.command, raise_error=False)
            raise SystemExit(status)

    def upgrade_pip(self):
        self.pipenv(['run', 'pip', 'install', '-U', 'pip'])

    def pipenv(self, args, **kwargs):
        return run(['pipenv'] + args, **kwargs)


class CommandFailed(InitError):
    def __init__(self, cmd, error):
        msg = 'Command {!r} failed with error code {!r}'.format(list2cmdline(cmd), error)
        super(CommandFailed, self).__init__(msg)


class ProgramNotFound(InitError):
    def __init__(self, cmd):
        msg = 'Program {!r} not found in command {!r}'.format(cmd[0], list2cmdline(cmd))
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

    try:
        os.makedirs(osp.dirname(path))
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    with open(path, 'w') as f:
        f.write(content)


if __name__ == '__main__':
    Init(sys.argv)
