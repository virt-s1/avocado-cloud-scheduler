#!/usr/bin/env python
"""
Schedule containerized avocado-cloud tests for Alibaba Cloud.
"""

import argparse
import logging
import toml
import os
import subprocess

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

    def __init__(self, config={}):
        pass

    


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
        exit(1)

        flavors = ARGS.flavors or self.config.get('flavors')
        if isinstance(flavors, str):
            self.flavors = flavors.split(' ')
        elif isinstance(flavors, list):
            self.flavors = flavors
        else:
            logging.error('Can not get FLAVORS.')
            exit(1)

        return None

if __name__ == '__main__':
    scheduler = AvocadoScheduler(ARGS)
    scheduler.show_vars()

exit(0)
