#!/usr/bin/env python
"""
Schedule containerized avocado-cloud tests for Alibaba Cloud.
"""

import argparse
import logging
import toml
import os
import subprocess
import shutil

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

ARG_PARSER = argparse.ArgumentParser(description="Schedule containerized \
avocado-cloud tests for Alibaba Cloud.")
ARG_PARSER.add_argument('--config',
                        dest='config',
                        action='store',
                        help='The toml file for the scheduler configuration.',
                        default='./config.toml',
                        required=False)

ARGS = ARG_PARSER.parse_args()


class ContainerMaster():
    """Handle containers."""

    def __init__(self, config={}):
        container_path = config.get('container_path', '/tmp')
        container_pool = config.get('container_pool', [])
        for container_name in container_pool:
            # check the status
            _path = os.path.join(container_path, container_name)
            if os.path.isdir(_path):
                pass
            else:
                LOG.error(f'Invalid container path "{_path}".')
                exit(1)

        self.container_path = container_path
        self.container_pool = container_pool

    def list_all_containers(self):
        return self.container_pool

    def list_available_containers(self):
        available_containers = []
        for container_name in self.container_pool:
            cmd = f'podman ps -a --format "{{{{.Names}}}}" | grep -q -x {container_name}'
            res = subprocess.run(cmd, shell=True)
            LOG.debug(res)
            if res.returncode > 0:
                available_containers.append(container_name)

        LOG.debug(f'available_containers: {available_containers}')
        return available_containers

    def get_available_container(self):
        available_containers = self.list_available_containers()

        if len(available_containers) > 0:
            LOG.debug(f'Got container "{available_containers[0]}"')
            return available_containers[0]
        else:
            LOG.debug('No available container left.')
            return None


class ConfigAssistant():
    """Provision config for avocado-cloud testing."""

    def __init__(self, container_path='/tmp', template_path='./templates', utils_path='./utils'):
        self.container_path = container_path
        self.template_path = template_path
        self.utils_path = utils_path

    def _copy_default_data(self, container_name):
        container_data_path = os.path.join(
            self.container_path, container_name, 'data')

        LOG.debug(f'Copying default data into {container_data_path}')
        os.makedirs(container_data_path, exist_ok=True)
        shutil.copy(os.path.join(self.template_path, 'alibaba_common.yaml'), os.path.join(
            container_data_path, 'alibaba_common.yaml'))
        shutil.copy(os.path.join(self.template_path, 'alibaba_testcases.yaml'), os.path.join(
            container_data_path, 'alibaba_testcases.yaml'))
        shutil.copy(os.path.join(self.template_path, 'alibaba_flavors.yaml'), os.path.join(
            container_data_path, 'alibaba_flavors.yaml'))

    def provision_data(self, container_name, flavor):
        self._copy_default_data(container_name)

        container_data_path = os.path.join(
            self.container_path, container_name, 'data')

        # Provision flavor data
        exec = os.path.join(self.utils_path, 'provision_flavor_data.sh')
        file = os.path.join(container_data_path, 'alibaba_flavors.yaml')
        cmd = f'{exec} {flavor} {file}'

        res = subprocess.run(cmd, shell=True)
        if res.returncode > 0:
            LOG.error('Failed to provison flavor data.')


class AvocadoScheduler():
    """Schedule containerized avocado-cloud tests for Alibaba Cloud."""

    def __init__(self, ARGS):
        # Load config
        with open(ARGS.config, 'r') as f:
            self.config = toml.load(f)
            LOG.debug(f'{ARGS.config}: {self.config}')

        container = self.config.get('container')
        if not container or not isinstance(container, dict):
            LOG.error('Cannot get valid container from the config file.')
            exit(1)
        else:
            LOG.debug(f'container: {container}')

        azone_pool = self.config.get('azone_pool')
        if not azone_pool or not isinstance(azone_pool, list):
            LOG.error('Cannot get valid azone_pool from the config file.')
            exit(1)
        else:
            LOG.debug(f'azone_pool: {azone_pool}')

        image = self.config.get('image')
        if not image or not isinstance(image, dict):
            LOG.error('Cannot get valid image from the config file.')
            exit(1)
        else:
            LOG.debug(f'image: {image}')

        # Get container
        cm = ContainerMaster(container)
        c = cm.get_available_container()
        LOG.debug(c)

        # Provision data
        ca = ConfigAssistant(container_path=self.config.get(
            'container', {}).get('container_path', '/tmp'))
        ca.provision_data(c, 'ecs.g5.xlarge')

        return None


if __name__ == '__main__':
    scheduler = AvocadoScheduler(ARGS)

exit(0)
