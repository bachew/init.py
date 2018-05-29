# -*- coding: utf-8 -*-
from __future__ import print_function
from os import path as osp
from textwrap import dedent
import errno
import runpy
import subprocess
import sys


class main(object):
    HELP_URL = 'https://github.com/bachew/init.py'
    SCRIPT_URL = 'https://github.com/bachew/init.py/blob/master/init.py'

    def __init__(self, argv):
        self.script = argv[0]
        options, self.command = self.split_args(argv[1:])
        self.command_str = subprocess.list2cmdline(self.command)

        if set(['-h', '--help']).intersection(options):
            self.print_help()
            raise SystemExit

        self.base_dir = osp.dirname(__file__)
        self.config_path = osp.join(self.base_dir, 'init_config.py')
        self.config_module = osp.splitext(self.config_path)[0]
        self.config = self.load_config()
        self.check_python_version()

        if '--upgrade' in options:
            self.upgrade()

        self.initialize()

        if self.command:
            self.run(self.command, exit=True)

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
            Initialize this project by:
            - running pipenv
            - add and install required dependencies
            - run 'inv init'
            - run the provided command

            See {help_url} for more info

            Arguments:
              command     Command to execute after initialization

            Options:
              -h, --help  Show this help message and exit
              --upgrade   Upgrade {init_py} to the latest version
                          ({script_url})
        '''.format(help_url=self.HELP_URL, init_py=__file__, script_url=self.SCRIPT_URL)
        print(dedent(details))

    def print_usage(self):
        print('Usage: {} [-h/--help] [--upgrade] [command]'.format(self.script))

    def error(self, message):
        print('ERROR:', message, file=sys.stderr)
        raise SystemExit(1)

    def load_config(self):
        if not osp.isfile(self.config_path):
            print('Config file {!r} does not exist, creating it'.format(self.config_path))

            with open(self.config_path, 'w') as f:
                f.write(dedent('''
                    def check_python_version(version):
                        return version >= (3, 4)
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
            self.error('Python version not OK')

    def upgrade(self):
        print('TODO: upgrade {!r} from {!r}'.format(__file__, self.SCRIPT_URL))

    def initialize(self):
        print('TODO: initialize')

    def run(self, cmd, exit=False):
        print('$ {}'.format(subprocess.list2cmdline(cmd)))

        try:
            status = subprocess.call(self.command)
        except OSError as e:
            if e.errno == errno.ENOENT:
                print('Command {!r} not found'.format(cmd[0]))
        else:
            if exit:
                raise SystemExit(status)


if __name__ == '__main__':
    main(sys.argv)
