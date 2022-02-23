#!/usr/bin/env python3
"""
Update tasks of avocado-cloud scheduler by patching tasklist.
"""

from tabulate import tabulate
import argparse
import logging
import toml
import os


LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

ARG_PARSER = argparse.ArgumentParser(description='Update tasks of \
avocado-cloud scheduler by patching tasklist.')
ARG_PARSER.add_argument(
    '--tasklist',
    dest='tasklist',
    action='store',
    help='Toml file for the task list.',
    default='./tasklist.toml',
    required=False)
ARG_PARSER.add_argument(
    '--flavor',
    dest='flavor',
    action='store',
    help='Flavor (task) in the task list.',
    default=None,
    required=True)
ARG_PARSER.add_argument(
    '--action',
    dest='action',
    action='store',
    help='The action to perform.',
    choices=('SCHEDULE', 'WITHDRAW'),
    default=None,
    required=False)
ARG_PARSER.add_argument(
    '--remaining_retries_testcase',
    dest='remaining_retries_testcase',
    action='store',
    help='The "remaining_retries_testcase" to update to.',
    type=int,
    default=None,
    required=False)
ARG_PARSER.add_argument(
    '--remaining_retries_resource',
    dest='remaining_retries_resource',
    action='store',
    help='The "remaining_retries_resource" to update to.',
    type=int,
    default=None,
    required=False)

ARGS = ARG_PARSER.parse_args()


if __name__ == '__main__':

    # Check the tasklist file
    if not os.path.exists(ARGS.tasklist):
        LOG.error(f'Cannot found tasklist ({ARGS.tasklist}) to be patched.')
        exit(1)

    patch_file = f'{ARGS.tasklist}.patch'
    if os.path.exists(patch_file):
        LOG.error(f'Patch file ({patch_file}) already exists.')
        exit(1)

    # Create patch
    patch_name = ARGS.flavor
    patch_args = {}

    if ARGS.action:
        patch_args['action'] = ARGS.action

    if ARGS.remaining_retries_testcase is not None:
        patch_args['remaining_retries_testcase'] = ARGS.remaining_retries_testcase

    if ARGS.remaining_retries_resource is not None:
        patch_args['remaining_retries_resource'] = ARGS.remaining_retries_resource

    # Save the patch
    if patch_args:
        content = {patch_name: patch_args}

        try:
            with open(patch_file, 'w') as f:
                toml.dump(content, f)
        except Exception as ex:
            LOG.error(f'Failed to dump patches to {patch_file}: {ex}')
            exit(1)

    exit(0)
