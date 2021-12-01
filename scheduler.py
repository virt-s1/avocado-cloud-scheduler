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
import threading
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

        for k, v in tasks.items():
            v.setdefault('status')
            v.setdefault('return_code')

        LOG.debug(f'Tasks Loaded: {tasks}')

        self.lock = threading.Lock()
        self.tasks = tasks
        self.queue = []

        self.max_threads = 4
        self.threads = []

        # save tasks
        self._save_tasks()

        # TODO: update the hard code
        self.repopath = '/home/cheshi/mirror/codespace/avocado-cloud-scheduler'
        self.logpath = '/home/cheshi/mirror/containers/avocado_scheduler/logs'

        self.producer = threading.Thread(
            target=self.producer, name='Producer', daemon=True)
        self.consumer = threading.Thread(
            target=self.consumer, name='Consumer', daemon=False)

    def producer(self):
        while True:
            time.sleep(1)
            is_save_needed = False

            self.lock.acquire(timeout=60)
            for k, v in self.tasks.items():
                if v['status'] is None:
                    self.queue.append(k)
                    v['status'] = 'WAITING'
                    is_save_needed = True
            self.lock.release()

            if is_save_needed:
                self._save_tasks()

    def consumer(self):
        # Start after producer
        time.sleep(2)

        while True:
            time.sleep(1)

            # Run tasks if possible
            if len(self.threads) < self.max_threads and len(self.queue) > 0:
                flavor = self.queue.pop(0)
                t = threading.Thread(target=self.run_task,
                                     args=(flavor,), name='RunTask')
                t.start()
                self.threads.append(t)

            # Clean up finished tasks
            self.threads = [x for x in self.threads if x.is_alive()]
            LOG.debug(f'Function consumer: Tasks in Queue: {len(self.queue)}; '
                      f'Running Threads: {len(self.threads)}')

            # Exits if no more tasks
            if len(self.threads) == 0 and len(self.queue) == 0:
                LOG.info(
                    'Consumer exits since there are no more tasks to process.')
                break

    def start(self):
        self.producer.start()
        self.consumer.start()

    def stop(self):
        self.consumer.join()
        return 0

    def update_task(self, flavor, status=None, return_code=None):
        """Update the status for a specified task."""
        self.lock.acquire(timeout=60)
        if status is not None:
            self.tasks[flavor]['status'] = status
        if return_code is not None:
            self.tasks[flavor]['return_code'] = return_code
        self.lock.release()

        LOG.debug(f'Function update_task({flavor}) self.tasks: {self.tasks}')
        self._save_tasks()

        return 0

    def _save_tasks(self):
        """Save to the tasklist file."""
        self.lock.acquire(timeout=60)
        try:
            print(self.tasks)
            with open(f'{ARGS.tasklist}', 'w') as f:
                toml.dump(self.tasks, f)
        except Exception as ex:
            LOG.warning(f'Failed to save tasks to {ARGS.tasklist}: {ex}')
            return 1
        finally:
            self.lock.release()

        return 0

    def run_task(self, flavor):
        LOG.info(f'Task for "{flavor}" is started.')
        self.update_task(flavor, status='RUNNING')
        ts = time.strftime('%y%m%d%H%M%S', time.localtime())
        logfile = os.path.join(self.logpath, f'task_{flavor}_{ts}.log')
        #cmd = f'nohup {self.repopath}/executor.py --flavor {flavor} > {logfile}'
        cmd = 'sleep 2; exit 123'
        res = subprocess.run(cmd, shell=True)
        time.sleep(random.random() * 3)

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
            self.update_task(flavor, status='FINISHED',
                             return_code=res.returncode)

        LOG.info(f'Task for "{flavor}" is finished.')

        return res.returncode

    def post_process(self, code):
        LOG.debug(f'Got return code {code} in post_process function.')


if __name__ == '__main__':

    ts = TestScheduler()
    ts.start()
    ts.stop()


exit(0)
