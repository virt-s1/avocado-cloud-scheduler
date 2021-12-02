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
        self.dry_run = True
        self.max_retries_testcase = 2
        self.max_retries_resource = 10

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
                if not v.get('status'):
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

    def update_task(self, flavor, ask_retry_testcase=False, ask_retry_resource=False, **args):
        """Update the status for a specified task."""

        if ask_retry_testcase and ask_retry_resource:
            LOG.error(
                'ask_retry_testcase and ask_retry_resource cannot be true at the same time.')
            return 1

        self.lock.acquire(timeout=60)
        _dict = self.tasks[flavor]

        if ask_retry_testcase:
            _remaining_retries = _dict.get(
                'remaining_retries_testcase', self.max_retries_testcase)
            if _remaining_retries > 0:
                # General update
                _dict.update(args)

                # Save history (remove) and remaining retries
                _history = _dict.pop('history', [])
                _dict['remaining_retries_testcase'] = _remaining_retries

                # Append current entry to the history
                _history.append(_dict.copy())

                # Rebuild the task info
                _dict.clear()
                _dict['history'] = _history
                _dict['remaining_retries_testcase'] = _remaining_retries - 1
            else:
                # No more retries, return and keep the task intact
                self.lock.release()
                return 2

        if ask_retry_resource:
            _remaining_retries = _dict.get(
                'remaining_retries_resource', self.max_retries_resource)
            if _remaining_retries > 0:
                # General update
                _dict.update(args)

                # Save history (remove) and remaining retries
                _history = _dict.pop('history', [])
                _dict['remaining_retries_resource'] = _remaining_retries

                # Append current entry to the history
                _history.append(_dict.copy())

                # Rebuild the task info
                _dict.clear()
                _dict['history'] = _history
                _dict['remaining_retries_resource'] = _remaining_retries - 1
            else:
                # No more retries, return and keep the task intact
                self.lock.release()
                return 2

        # General update
        _dict.update(args)

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
        start_sec = time.time()
        time_start = time.strftime(
            '%Y-%m-%d %H:%M:%S', time.localtime(start_sec))

        self.update_task(flavor, status='RUNNING', time_start=time_start)
        ts = time.strftime('%y%m%d%H%M%S', time.localtime(start_sec))
        logfile = os.path.join(self.logpath, f'task_{flavor}_{ts}.log')
        cmd = f'nohup {self.repopath}/executor.py --flavor {flavor} > {logfile}'

        if self.dry_run:
            time.sleep(random.random() * 3 + 2)
            res = random.choice([0, 11, 21, 22, 23, 24, 31, 41])
        else:
            res = subprocess.run(cmd, shell=True)

        stop_sec = time.time()
        time_stop = time.strftime(
            '%Y-%m-%d %H:%M:%S', time.localtime(stop_sec))
        time_used = '{%.2f} s'.format(stop_sec - start_sec)

        # - 0  - Test executed and passed (test_passed)
        # - 11 - Test failed (test_general_error)
        # - 21 - General failure while getting AZ (flavor_general_error)
        # - 22 - Flavor is out of stock (flavor_no_stock)
        # - 23 - Possible AZs are not enabled (flavor_azone_disabled)
        # - 24 - Eligible AZs are occupied (flavor_azone_occupied)
        # - 31 - Cannot get idle container (container_all_busy)
        # - 41 - General failure while provisioning data (provision_error)

        # Update the task
        if res.returncode == 0:
            self.update_task(flavor, status='FINISHED',
                             return_code=res.returncode,
                             time_stop=time_stop,
                             time_used=time_used)

        LOG.info(f'Task for "{flavor}" is finished.')

        return res.returncode

    def post_process(self, code):
        LOG.debug(f'Got return code {code} in post_process function.')


if __name__ == '__main__':

    ts = TestScheduler()
    # ts.start()
    # ts.stop()
    ts.update_task('ecs.hfg5.xlarge', True)


exit(0)
