#!/usr/bin/env python
"""
Schedule containerized avocado-cloud tests for Alibaba Cloud.
"""

import argparse
import logging
import toml
import json
import subprocess
import shutil

from multiprocessing import Pool
import os
import time
import random


LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

ARG_PARSER = argparse.ArgumentParser(description="Schedule containerized \
avocado-cloud tests for Alibaba Cloud.")
ARG_PARSER.add_argument(
    '--config',
    dest='config',
    action='store',
    help='Toml file for test scheduler configuration.',
    default='./config.toml',
    required=False)
ARG_PARSER.add_argument(
    '--tasklist',
    dest='tasklist',
    action='store',
    help='Toml file for the task list.',
    default='./tasklist.toml',
    required=False)

ARGS = ARG_PARSER.parse_args()

UTILS_PATH = './utils'
TEMPLATE_PATH = './templates'


class TestScheduler():
    """Schedule the containerized avocado-cloud testing."""

    def __init__(self):
        # load tasks
        try:
            with open(f'{ARGS.tasklist}', 'r') as f:
                tasks = toml.load(f)
        except Exception as ex:
            LOG.error(f'Failed to load tasks from {ARGS.tasklist}: {ex}')
            exit(1)

        LOG.debug(f'Tasks Loaded: {tasks}')
        self.tasks = tasks

        # TODO: update the hard code
        self.repopath = '/home/cheshi/mirror/codespace/avocado-cloud-scheduler'
        self.logpath = '/home/cheshi/mirror/containers/avocado_scheduler/logs'

    def _save_tasks(self):
        """Save to the tasklist file."""
        try:
            with open(f'{ARGS.tasklist}', 'w') as f:
                toml.dump(self.tasks, f)
        except Exception as ex:
            LOG.warning(f'Failed to save tasks to {ARGS.tasklist}: {ex}')
            return 1

        return 0

    def _update_task(self, flavor, status=None, return_code=None):
        """Update the status for a specified task."""
        if status is not None:
            self.tasks[flavor]['status'] = status
        if return_code is not None:
            self.tasks[flavor]['return_code'] = return_code

        LOG.debug(self.tasks)
        self._save_tasks()

        return 0

    def run_task(self, flavor):
        ts = time.strftime('%y%m%d%H%M%S', time.localtime())
        logfile = os.path.join(self.logpath, f'task_{flavor}_{ts}.log')
        #cmd = f'{self.repopath}/executor.py --flavor {flavor} &> {logfile}'
        cmd='sleep 10'
        res = subprocess.run(cmd, shell=True)

        # - 0   - Test executed and passed
        # - 1   - Test executed and failed
        # - 101 - General failure while getting AZ
        # - 102 - Flavor is out of stock
        # - 103 - Possible AZs are not enabled
        # - 104 - Eligible AZs are occupied
        # - 111 - Cannot get idle container
        # - 121 - General failure while provisioning data
        if res.returncode > -1:
            # update the tasklist
            self._update_task(flavor, status='FINISHED', return_code=res.returncode)


def long_time_task(name):
    print('Run task %s (%s)...' % (name, os.getpid()))
    start = time.time()
    time.sleep(random.random() * 3)
    end = time.time()
    print('Task %s runs %0.2f seconds.' % (name, (end - start)))


if __name__ == '__main__':

    ts = TestScheduler()
    for f in ts.tasks.keys():
        ts.run_task(f)

    # print('Parent process %s.' % os.getpid())
    # p = Pool(4)
    # for i in range(25):
    #     r = p.apply_async(long_time_task, args=(i,))
    #     # help(r)
    #     # print(f'{i}: {r}')
    # print('Waiting for all subprocesses done...')
    # p.close()

    # p.join()
    # print('All subprocesses done.')


exit(0)
