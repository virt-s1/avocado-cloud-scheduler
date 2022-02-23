#!/usr/bin/env python3
"""
Provision the flavor data for avocado-cloud testing.
Maintainer: Charles Shih <schrht@gmail.com>
"""

import argparse
import logging
import json
import subprocess

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

ARG_PARSER = argparse.ArgumentParser(
    description="Provision the flavor data for avocado-cloud testing.")
ARG_PARSER.add_argument(
    '--file',
    dest='file',
    action='store',
    help='The file to be provisioned.',
    default='./alibaba_flavors.yaml',
    required=False)
ARG_PARSER.add_argument(
    '--flavor',
    dest='flavor',
    action='store',
    help='Type of instance to test.',
    required=True)

ARGS = ARG_PARSER.parse_args()

UTILS_PATH = './utils'
TEMPLATE_PATH = './templates'


def aliyun_cli(self, cmd):
    LOG.debug(f'Aliyun CLI: {cmd}')


def query_spec(flavor):
    """Query instance SPEC."""

    cmd = 'aliyun ecs DescribeInstanceTypes'
    p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
    if p.returncode != 0:
        LOG.error(p.stdout)
        return None

    _data = json.loads(p.stdout)
    specs = _data.get('InstanceTypes', {}).get('InstanceType', [])

    for spec in specs:
        if spec.get('InstanceTypeId') == flavor:
            return spec

    return None


def extract_info(spec):
    """Extract information from the instance SPEC."""

    info = {}
    info['name'] = spec.get('InstanceTypeId')
    info['cpu'] = spec.get('CpuCoreCount')
    info['memory'] = spec.get('MemorySize')
    info['nic_count'] = spec.get('EniQuantity')
    info['disk_quantity'] = spec.get('DiskQuantity')

    if spec.get('LocalStorageAmount'):
        info['disk_count'] = spec.get('LocalStorageAmount')
        info['disk_size'] = spec.get('LocalStorageCapacity')

        if spec.get('LocalStorageCategory') == 'local_ssd_pro':
            info['disk_type'] = 'ssd'
        elif spec.get('LocalStorageCategory') == 'local_hdd_pro':
            info['disk_type'] = 'hdd'

        # Some special families use NVMe as local disks
        _families = ['ecs.i3', 'ecs.g7se']
        if spec.get('InstanceTypeFamily') in _families:
            info['disk_type'] = 'nvme'

    # Some security-enhanced instance families have 50% encrypted memory
    _families = ['ecs.c7t', 'ecs.g7t', 'ecs.r7t']
    if spec.get('InstanceTypeFamily') in _families:
        info['memory'] = int(info['memory'] * 0.5)

    return info


def compile_file(info):
    """Compile the data file."""

    lines = []
    lines.append('Flavor: !mux\n')
    lines.append('\n')
    lines.append('  {}:\n'.format(info.get('name')))

    for k, v in info.items():
        lines.append(f'    {k}: {v}\n')

    return lines


def dump_file(file, lines):
    """Dump the data file."""

    with open(file, 'w') as f:
        f.writelines(lines)


if __name__ == '__main__':

    # Query flavor SPEC
    spec = query_spec(ARGS.flavor)

    if not spec:
        LOG.error(f'Unable to query SPEC for flavor "{ARGS.flavor}".')
        exit(1)

    # Analyse SPEC
    info = extract_info(spec)

    if not info:
        LOG.error(f'Unable to analyse SPEC for flavor "{ARGS.flavor}".')
        exit(1)

    # Compile data file
    lines = compile_file(info)

    # Dump the data file
    dump_file(ARGS.file, lines)

    exit(0)
