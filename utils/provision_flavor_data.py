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

    cmd = 'aliyun ecs DescribeInstanceTypes --InstanceTypes.1 ' + flavor
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
    info['private_ip_quantity'] = spec.get('EniPrivateIpAddressQuantity')

    if spec.get('LocalStorageAmount'):
        info['disk_count'] = spec.get('LocalStorageAmount')
        info['disk_size'] = spec.get('LocalStorageCapacity')
        info['disk_type'] = spec.get('LocalStorageCategory')

    # Some special families use NVMe driver for local disks
    _families = ['ecs.i3', 'ecs.i3g', 'ecs.i4', 'ecs.i4g', 'ecs.d3s']
    if spec.get('InstanceTypeFamily') in _families:
        info['local_disk_driver'] = 'nvme'
    else:
        info['local_disk_driver'] = 'virtio_blk'

    # Some special families use NVMe driver for cloud disks
    _families = ['ecs.g7se', 'ecs.ebmg7se', 'ecs.g8y', 'ecs.c8y', 'ecs.r8y', 'ecs.g8i', 'ecs.c8i', 'ecs.r8i', \
                 'ecs.g8a', 'ecs.c8a', 'ecs.r8a', 'ecs.g8ae', 'ecs.c8ae', 'ecs.r8ae', 'ecs.hfg8i', 'ecs.hfr8i', \
                 'ecs.hfc8i', 'ecs.g8ise', 'ecs.c8ise', 'ecs.r8ise', 'ecs.ebmg8y', 'ecs.ebmc8y', 'ecs.ebmr8y', \
                 'ecs.ebmg8i', 'ecs.ebmc8i', 'ecs.ebmhfc8i', 'ecs.ebmhfg8i', 'ecs.ebmhfr8i', 'ecs.ebmc8a', \
                 'ecs.ebmg8a', 'ecs.ebmr8a', 'ecs.ebmc8ae', 'ecs.ebmg8ae', 'ecs.ebmr8ae', 'ecs.g9i', 'ecs.c9i', \
                 'ecs.r9i', 'ecs.g9a', 'ecs.c9a', 'ecs.r9a', 'ecs.g9ae', 'ecs.c9ae', 'ecs.r9ae', 'ecs.g9as', \
                 'ecs.g9a-flex', 'ecs.c9a-flex']
    if spec.get('InstanceTypeFamily') in _families:
        info['cloud_disk_driver'] = 'nvme'
    else:
        info['cloud_disk_driver'] = 'virtio_blk'

    # Some security-enhanced instance families have 50% encrypted memory
    _families = ['ecs.c7t', 'ecs.g7t', 'ecs.r7t']
    if spec.get('InstanceTypeFamily') in _families:
        info['memory'] = int(info['memory'] * 0.5)

    _families = ['ecs.ebmg6a', 'ecs.ebmc6a', 'ecs.ebmr6a', 'ecs.ebmg7a', 'ecs.ebmc7a', 'ecs.ebmr7a', \
        'ecs.g6t', 'ecs.c6t', 'ecs.r6t', 'ecs.g7t', 'ecs.c7t', 'ecs.r7t', 'ecs.g6r', 'ecs.c6r', \
        'ecs.g8y', 'ecs.c8y', 'ecs.r8y', 'ecs.ebmg8y','ecs.ebmc8y', 'ecs.ebmr8y']
    if spec.get('InstanceTypeFamily') in _families:
        info['boot_mode'] = 'uefi'
    else:
        info['boot_mode'] = 'bios'

    _families = ['ecs.g6r', 'ecs.c6r', 'ecs.g8y', 'ecs.c8y', 'ecs.r8y', 'ecs.ebmg8y', \
                 'ecs.ebmc8y', 'ecs.ebmr8y']
    if spec.get('InstanceTypeFamily') in _families:
        info['arch'] = 'aarch64'
    else:
        info['arch'] = 'x86_64'

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
