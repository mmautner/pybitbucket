# -*- coding: utf-8 -*-

from __future__ import print_function

import os
import sys
import time
import subprocess

# Import parameters from the setup file.
sys.path.append('.')
from setup import (
    setup_dict, get_project_files, print_success_message,
    print_failure_message, _lint, _test, _test_all,
    CODE_DIRECTORY, DOCS_DIRECTORY, TESTS_DIRECTORY, PYTEST_FLAGS)

from paver.easy import options, task, needs, consume_args
from paver.setuputils import install_distutils_tasks
from contextlib import contextmanager
from io import BytesIO

options(setup=setup_dict)

install_distutils_tasks()

# Miscellaneous helper functions


def print_passed():
    # generated on http://patorjk.com/software/taag/#p=display&f=Small&t=PASSED
    print_success_message(r'''  ___  _   ___ ___ ___ ___
 | _ \/_\ / __/ __| __|   \
 |  _/ _ \\__ \__ \ _|| |) |
 |_|/_/ \_\___/___/___|___/
''')


def print_failed():
    # generated on http://patorjk.com/software/taag/#p=display&f=Small&t=FAILED
    print_failure_message(r'''  ___ _   ___ _    ___ ___
 | __/_\ |_ _| |  | __|   \
 | _/ _ \ | || |__| _|| |) |
 |_/_/ \_\___|____|___|___/
''')


class cwd(object):
    """Class used for temporarily changing directories. Can be though of
    as a `pushd /my/dir' then a `popd' at the end.
    """
    def __init__(self, newcwd):
        """:param newcwd: directory to make the cwd
        :type newcwd: :class:`str`
        """
        self.newcwd = newcwd

    def __enter__(self):
        self.oldcwd = os.getcwd()
        os.chdir(self.newcwd)
        return os.getcwd()

    def __exit__(self, type_, value, traceback):
        # This acts like a `finally' clause: it will always be executed.
        os.chdir(self.oldcwd)


# Task-related functions

def _doc_make(*make_args):
    """Run make in sphinx' docs directory.

    :return: exit code
    """
    if sys.platform == 'win32':
        # Windows
        make_cmd = ['make.bat']
    else:
        # Linux, Mac OS X, and others
        make_cmd = ['make']
    make_cmd.extend(make_args)

    # Account for a stupid Python "bug" on Windows:
    # <http://bugs.python.org/issue15533>
    with cwd(DOCS_DIRECTORY):
        retcode = subprocess.call(make_cmd)
    return retcode

@contextmanager
def stdout_redirector(stream):
    old_stdout = sys.stdout
    sys.stdout = stream
    try:
        yield
    finally:
        sys.stdout = old_stdout

def git_check_master():
    current_branch = subprocess.check_output(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip()
    if current_branch != 'master':
        print_failure_message(
            'The current branch is {}. '
            'Release tasks can only be performed on master. '
            'Use `git checkout master` to switch. '
            .format(current_branch))
        raise SystemExit(1)

def git_check_remote():
    local = subprocess.check_output(
        ['git', 'rev-parse', '@'])
    remote = subprocess.check_output(
        ['git', 'rev-parse', '@{u}'])
    base = subprocess.check_output(
        ['git', 'merge-base', '@', '@{u}'])
    if local == remote:
        print('Local and remote are the same.')
    elif local == base:
        print_failure_message(
            'The current branch is behind the remote. '
            'Use `git pull` to bring the local branch current. ')
        raise SystemExit(1)
    elif remote == base:
        print_failure_message(
            'The current branch is ahead of the remote. '
            'Use `git push` to bring the remote branch current. ')
        raise SystemExit(1)
    else:
        print_failure_message(
            'The current branch has diverged from remote. '
            'Use `git pull` to bring the remote branch current, '
            'then merge and use `git push` to synchronize branches.')
        raise SystemExit(1)

def version_bump(part):
    try:
        import bumpversion
    except ImportError:
        print_failure_message(
            'Install bumpversion to use this task, '
            "i.e., `pip install --upgrade bumpversion`.")
        raise SystemExit(1)
    f = BytesIO()
    with stdout_redirector(f):
        bumpversion.main([part, '--commit', '--tag', '--list'])
        for i in f.getvalue().split():
            for j in i.split('='):
                head, tail = j[0], j[1]
                if head == 'new_version':
                    version = tail
    return version

def release(part):
    # Perform any pre-flight checks
    git_check_master()
    git_check_remote()
    # _test_all() returns the number of failed tests,
    # so when _test_all() is true, there were failed tests.
    if _test_all():
        print_failure_message(
            'Cannot release if tests do not pass.')
        raise SystemExit(1)
    # Bump the version, create a bump commit, and tag
    version = version_bump(part)
    print(
        'Created new commit and tag for version bump. '
        'Use `git reset --hard HEAD~1` to rollback the commit, '
        'and `git tag -d {}` to rollback the tag.'
        .format(version))
    # Build the pip package, upload to PyPI, and push
    sdist()
    distutils.command.upload()
    subprocess.check_call(['git', 'push'])


# Tasks

@task
def dep_install():
    """Install or upgrade development dependencies."""
    try:
        import pip
    except ImportError:
        print_failure_message(
            'Install pip to use this task, '
            "i.e., `sudo apt-get install python-pip`.")
        raise SystemExit(1)

    pip.main(['install', '--upgrade', '-r', 'requirements-dev.txt'])


@task
@needs('dep_install')
def prepare():
    """ Prepare complete environment """
    sh("python setup.py develop")


@task
def dep_check():
    """Check if any installed dependencies have newer versions."""
    try:
        import pip
    except ImportError:
        print_failure_message(
            'Install pip to use this task, '
            "i.e., `sudo apt-get install python-pip`.")
        raise SystemExit(1)
    f = BytesIO()
    with stdout_redirector(f):
        pip.main(['list', '--outdated'])
    if not f.getvalue():
        print_passed()
    else:
        print('Outdated pip dependencies:')
        print('{0}'.format(f.getvalue()))
        print_failed()
    raise SystemExit(len(f.getvalue()))


@task
@needs('doc_html', 'setuptools.command.sdist')
def sdist():
    """Build the HTML docs and the tarball."""
    pass


@task
def test():
    """Run the unit tests."""
    raise SystemExit(_test())


@task
def lint():
    # This refuses to format properly when running `paver help' unless
    # this ugliness is used.
    ('Perform PEP8 style check, run PyFlakes, and run McCabe complexity '
     'metrics on the code.')
    raise SystemExit(_lint())


@task
def test_all():
    """Perform a style check and run all unit tests."""
    retcode = _test_all()
    if retcode == 0:
        print_passed()
    else:
        print_failed()
    raise SystemExit(retcode)


@task
@consume_args
def run(args):
    """Run the package's main script. All arguments are passed to it."""
    # The main script expects to get the called executable's name as
    # argv[0]. However, paver doesn't provide that in args. Even if it did (or
    # we dove into sys.argv), it wouldn't be useful because it would be paver's
    # executable. So we just pass the package name in as the executable name,
    # since it's close enough. This should never be seen by an end user
    # installing through Setuptools anyway.
    from pybitbucket.main import main
    raise SystemExit(main([CODE_DIRECTORY] + args))


@task
def commit():
    """Commit only if all the tests pass."""
    if _test_all() == 0:
        subprocess.check_call(['git', 'commit'])
    else:
        print_failure_message('\nTests failed, not committing.')


@task
def release_major():
    """Test, package, and release a major version change."""
    release('major')


@task
def release_minor():
    """Test, package, and release a minor version change."""
    release('minor')


@task
def release_patch():
    """Test, package, and release a patch version change."""
    release('patch')


@task
def coverage():
    """Run tests and show test coverage report."""
    try:
        import pytest_cov  # NOQA
    except ImportError:
        print_failure_message(
            'Install the pytest coverage plugin to use this task, '
            "i.e., `pip install pytest-cov'.")
        raise SystemExit(1)
    import pytest
    pytest.main(PYTEST_FLAGS + [
        '--cov', CODE_DIRECTORY,
        '--cov-report', 'term-missing',
        '--cov-report', 'xml',
        TESTS_DIRECTORY])


@task  # NOQA
def doc_watch():
    """Watch for changes in the docs and rebuild HTML docs when changed."""
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        print_failure_message(
            'Install the watchdog package to use this task, '
            "i.e., `pip install watchdog`.")
        raise SystemExit(1)

    class RebuildDocsEventHandler(FileSystemEventHandler):
        def __init__(self, base_paths):
            self.base_paths = base_paths

        def dispatch(self, event):
            """Dispatches events to the appropriate methods.
            :param event: The event object representing the file system event.
            :type event: :class:`watchdog.events.FileSystemEvent`
            """
            for base_path in self.base_paths:
                if event.src_path.endswith(base_path):
                    super(RebuildDocsEventHandler, self).dispatch(event)
                    # We found one that matches. We're done.
                    return

        def on_modified(self, event):
            print_failure_message('Modification detected. Rebuilding docs.')
            # # Strip off the path prefix.
            # import os
            # if event.src_path[len(os.getcwd()) + 1:].startswith(
            #         CODE_DIRECTORY):
            #     # sphinx-build doesn't always pick up changes on code files,
            #     # even though they are used to generate the documentation. As
            #     # a workaround, just clean before building.
            doc_html()
            print_success_message('Docs have been rebuilt.')

    print_success_message(
        'Watching for changes in project files, press Ctrl-C to cancel...')
    handler = RebuildDocsEventHandler(get_project_files())
    observer = Observer()
    observer.schedule(handler, path='.', recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()


@task
@needs('doc_html')
def doc_open():
    """Build the HTML docs and open them in a web browser."""
    doc_index = os.path.join(DOCS_DIRECTORY, 'build', 'html', 'index.html')
    if sys.platform == 'darwin':
        # Mac OS X
        subprocess.check_call(['open', doc_index])
    elif sys.platform == 'win32':
        # Windows
        subprocess.check_call(['start', doc_index], shell=True)
    elif sys.platform == 'linux2':
        # All freedesktop-compatible desktops
        subprocess.check_call(['xdg-open', doc_index])
    else:
        print_failure_message(
            "Unsupported platform. Please open `{0}' manually.".format(
                doc_index))


@task
def get_tasks():
    """Get all paver-defined tasks."""
    from paver.tasks import environment
    for t in environment.get_tasks():
        print(t.shortname)


@task
def doc_html():
    """Build the HTML docs."""
    retcode = _doc_make('html')

    if retcode:
        raise SystemExit(retcode)


@task
def doc_clean():
    """Clean (delete) the built docs."""
    retcode = _doc_make('clean')

    if retcode:
        raise SystemExit(retcode)
