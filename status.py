#!/usr/bin/env python3
"""
Show task status of avocado-cloud scheduler by reading tasklist.
"""

from tabulate import tabulate
import argparse
import logging
import toml
import time


LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

ARG_PARSER = argparse.ArgumentParser(description="Show task status of \
avocado-cloud scheduler by reading tasklist.")
ARG_PARSER.add_argument(
    '--tasklist',
    dest='tasklist',
    action='store',
    help='Toml file for the task list.',
    default='./tasklist.toml',
    required=False)

ARGS = ARG_PARSER.parse_args()


if __name__ == '__main__':

    # Load tasks
    try:
        with open(f'{ARGS.tasklist}', 'r') as f:
            tasks = toml.load(f)
    except Exception as ex:
        LOG.error(f'Failed to load tasks from {ARGS.tasklist}: {ex}')
        exit(1)

    LOG.debug(f'Loaded {len(tasks)} task(s): {tasks}')

    # Analysis tasks
    status = []

    for k, v in tasks.items():

        # v_ex = {'status': 'FINISHED',
        #         'remaining_retries_testcase': 3,
        #         'remaining_retries_resource': 10,
        #         'time_start': '2021-12-07 11:17:48',
        #         'return_code': 0,
        #         'status_code': 'test_passed',
        #         'time_stop': '2021-12-07 11:18:00',
        #         'time_used': 11.76,
        #         'test_log': 'task_211207111748_ecs.t5-lc2m1.nano.log',
        #         'history': [
        #             {'status': 'FINISHED', '...': 'older...'},
        #             {'status': 'FINISHED', '...': 'newer...'},
        #         ]}

        LOG.debug(f'Analyzing task {k}: {v}')

        task = {}
        last_v = v.get('history', [{}])[-1]

        task['Flavor'] = k
        task['Status'] = v.get('status', 'None')
        task['StatusCode'] = v.get('status_code', 'None')
        rr_t = v.get("remaining_retries_testcase", 'None')
        rr_r = v.get("remaining_retries_resource", 'None')
        task['RR(T/R)'] = f'{rr_t}/{rr_r}'
        task['RetryStatusCode'] = last_v.get('status_code', 'None')
        task['LogFile'] = v.get('test_log') or last_v.get('test_log', 'None')

        if v.get('time_used'):
            # Status: FINISHED
            task['TimeUsed'] = v.get('time_used')
        elif v.get('time_start'):
            # Status: RUNNING
            _start_time = time.mktime(
                time.strptime(v.get('time_start'), '%Y-%m-%d %H:%M:%S'))
            task['TimeUsed'] = f'{(time.time() - _start_time):.2f}'
        else:
            # Status: WAITING
            task['TimeUsed'] = last_v.get('time_used', 'None')

        status.append(task)

    # Show status in table
    table = tabulate(status, headers='keys', tablefmt='simple',
                     showindex='always', disable_numparse=True)
    print(table)

    exit(0)
