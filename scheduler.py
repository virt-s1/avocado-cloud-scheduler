#!/usr/bin/env python
"""
Schedule containerized avocado-cloud tests for Alibaba Cloud.
"""

import argparse
import logging
import toml
import json
import os
import subprocess
import shutil
import random

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

ARG_PARSER = argparse.ArgumentParser(description="Schedule containerized \
avocado-cloud tests for Alibaba Cloud.")
ARG_PARSER.add_argument(
    '--config',
    dest='config',
    action='store',
    help='The toml file for the scheduler configuration.',
    default='./config.toml',
    required=False)

ARGS = ARG_PARSER.parse_args()

UTILS_PATH = './utils'


class ContainerAssistant():
    """Deal with container resources."""

    def __init__(self, config_file):
        # Load and parse user config
        with open(config_file, 'r') as f:
            config = toml.load(f)
            LOG.debug(f'{ARGS.config}: {config}')

        container_image = config.get('containers', {}).get('container_image')
        container_path = config.get('containers', {}).get('container_path')
        container_pool = config.get('containers', {}).get('container_pool')

        # Verify container image
        cmd = f'podman inspect {container_image} &>/dev/null'
        res = subprocess.run(cmd, shell=True)
        if res.returncode == 0:
            LOG.debug(f'Container image "{container_image}" is valid.')
        else:
            LOG.error(f'Container image "{container_image}" is invalid.')
            exit(1)

        # Create container path if needed
        os.makedirs(container_path, exist_ok=True)
        LOG.debug(f'Get user config "container_path": {container_path}')

        # Verify container pool
        if not isinstance(container_pool, list):
            LOG.error('The container_pool (should be list) is invalid.')
            exit(1)
        else:
            LOG.debug(f'Get user config "container_pool": {container_pool}')

        self.container_image = container_image
        self.container_path = container_path
        self.container_pool = container_pool

    def get_container_status(self):
        """Get the status of containers in the pool.

        Input:
            N/A
        Output:
            - dict of the container status
        """
        status = {}
        for name in self.container_pool:
            cmd = f'podman inspect {name} &>/dev/null'
            res = subprocess.run(cmd, shell=True)
            if res.returncode == 0:
                status[name] = 'unavailable'
            else:
                status[name] = 'available'

        LOG.debug(f'Container Status: {status}')

        return status

    def pick_container(self):
        """Pick an container for the test.

        Input:
            N/A
        Output:
            - container (string) or '' if no available ones
        """
        status = self.get_container_status()
        for name in status.keys():
            if status[name] == 'available':
                LOG.info(f'Picked container "{name}" '
                         f'from "{self.container_pool}".')
                return name

    # def trigger_container_run(self, container_name):
    #     # Prepare environment
    #     container_data_path = os.path.join(
    #         self.container_path, container_name, 'data')
    #     container_result_path = os.path.join(
    #         self.container_path, container_name, 'job-results')

    #     os.makedirs(container_data_path, exist_ok=True)
    #     os.makedirs(container_result_path, exist_ok=True)

    #     #os.unlink(os.path.join(container_result_path, 'latest'))

    #     subprocess.run(f'chcon -R -u system_u -t svirt_sandbox_file_t \
    #         {self.container_path}', shell=True)

    #     # Execute the test
    #     LOG.info(f'Run test in container "{container_name}"...')
    #     cmd = f'podman run --name {container_name} --rm -it \
    #         -v {container_data_path}:/data:rw \
    #         -v {container_result_path}:/root/avocado/job-results:rw \
    #         {self.container_image} /bin/bash ./container/bin/test_alibaba.sh'

    #     LOG.info(f'Run container with command: \n{cmd}')
    #     test_result = subprocess.run(cmd, shell=True)

    #     # Postprocess the logs
    #     import time
    #     time.sleep(10)
    #     LOG.info('Postprocessing logs...')
    #     os.makedirs(os.path.join(container_result_path,
    #                 'latest', 'testinfo'), exist_ok=True)
    #     shutil.copy(os.path.join(container_data_path, 'alibaba_common.yaml'),
    #                 os.path.join(container_result_path, 'latest', 'testinfo',
    #                              'alibaba_common.yaml'))
    #     shutil.copy(os.path.join(container_data_path, 'alibaba_testcases.yaml'),
    #                 os.path.join(container_result_path, 'latest', 'testinfo',
    #                 'alibaba_testcases.yaml'))
    #     shutil.copy(os.path.join(container_data_path, 'alibaba_flavors.yaml'),
    #                 os.path.join(container_result_path, 'latest', 'testinfo',
    #                 'alibaba_flavors.yaml'))

    #     if test_result.returncode == 0:
    #         LOG.info(f'Test succeed in container "{container_name}".')
    #         return 0
    #     else:
    #         LOG.warning(f'Test failed in container "{container_name}".')
    #         return 1


class CloudAssistant():
    """Deal with cloud resources."""

    def __init__(self, config_file):
        # Load and parse user config
        with open(config_file, 'r') as f:
            config = toml.load(f)
            LOG.debug(f'{ARGS.config}: {config}')

        enabled_regions = config.get('enabled_regions')
        if not isinstance(enabled_regions, list):
            LOG.error('Invalid enabled_regions (list) in config file.')
            exit(1)
        else:
            LOG.debug(f'Get user config "enabled_regions": {enabled_regions}')

        # Query all available flavors in the cloud
        distribution_file = '/tmp/aliyun_flavor_distribution.txt'
        if not os.path.exists(distribution_file):
            exec = os.path.join(UTILS_PATH, 'query_flavors.sh')
            cmd = f'{exec} -o {distribution_file}'
            subprocess.run(cmd, shell=True)

        with open(distribution_file, 'r') as f:
            _list = f.readlines()

        location_info = {}
        for _entry in _list:
            _entry = _entry.strip().split(',')
            _azone = _entry[0]
            _flavor = _entry[1]

            if _flavor in location_info:
                location_info[_flavor].append(_azone)
            else:
                location_info[_flavor] = [_azone]

        self.enabled_regions = enabled_regions
        self.location_info = location_info

    def get_possible_azones(self, flavor):
        """Get possible AZ for the specified flavor.

        Input:
            - flavor - Instance Type
        Output:
            - A list of AZs or []
        """
        possible_azones = self.location_info.get(flavor, [])
        if possible_azones:
            LOG.debug(f'Get Possible AZs for "{flavor}": {possible_azones}')
        else:
            LOG.debug(f'Flavor "{flavor}" is out of stock.')
        return possible_azones

    def get_eligible_azones(self, azones):
        """Get eligible AZs by filtering out the non-enabled AZs.

        Input:
            - azones - List of AZs
        Output:
            - A list of eligible AZs or []
        """
        if not azones:
            return []

        # Get eligible AZs (AZs in enabled regions)
        if '*' in self.enabled_regions:
            # This will disable this feature
            eligible_azones = azones
        else:
            # Get eligible AZs
            eligible_azones = []
            for azone in azones:
                for region in self.enabled_regions:
                    if region in azone:
                        eligible_azones.append(azone)
                        break

        if eligible_azones:
            LOG.debug(f'Get Eligible AZs: {eligible_azones}')
        else:
            LOG.debug(f'No Eligible AZs was found.')

        return eligible_azones

    def random_pick_azone(self, azones):
        """Randomly pick an AZ from the list of AZs.

        Input:
            - azones - List of AZs
        Output:
            - AZ (string) or '' if azones is empty.
        """
        if not azones:
            return ''

        # Randomly pick an AZ
        idx = random.randint(0, len(azones)-1)
        azone = azones[idx]
        LOG.debug(f'Randomly picked AZ "{azone}" from "{azones}".')

        return azone

    def pick_azone(self, flavor):
        """Pick an AZ for the test.

        Input:
            - flavor - Instance Type
        Output:
            - AZ (string) if succeed
            - 2 if flavor is out of stock
            - 3 if AZ is not enabled
        """

        # Get all possible AZs
        possible_azones = self.get_possible_azones(flavor)

        if not possible_azones:
            LOG.info(f'Flavor "{flavor}" is out of stock.')
            return 2

        # Get eligible AZs based on possible ones
        eligible_azones = self.get_eligible_azones(possible_azones)

        if not eligible_azones:
            LOG.info(f'The flavor "{flavor}" is InStock but it is outside '
                     f'the enabled regions. Please consider enabling more '
                     f'regions! Information: Possible AZs: {possible_azones} '
                     f'Enabled regions: {enabled_regions}')
            return 3

        # Randomly pick an AZ
        azone = self.random_pick_azone(eligible_azones)
        LOG.info(f'Picked AZ "{azone}" for flavor "{flavor}" '
                 f'from "{possible_azones}".')

        return azone


class ConfigAssistant():
    """Provision config for avocado-cloud testing."""

    def __init__(self, container_path='/tmp', template_path='./templates'):
        self.container_path = container_path
        self.template_path = template_path

    def _copy_default_data(self, container_name):
        container_data_path = os.path.join(
            self.container_path, container_name, 'data')

        LOG.debug(f'Copying default data into {container_data_path}')
        os.makedirs(container_data_path, exist_ok=True)
        shutil.copy(os.path.join(self.template_path, 'alibaba_common.yaml'),
                    os.path.join(container_data_path, 'alibaba_common.yaml'))
        shutil.copy(os.path.join(self.template_path, 'alibaba_testcases.yaml'),
                    os.path.join(container_data_path, 'alibaba_testcases.yaml'))
        shutil.copy(os.path.join(self.template_path, 'alibaba_flavors.yaml'),
                    os.path.join(container_data_path, 'alibaba_flavors.yaml'))

    def provision_data(self, container_name, flavor, keypair, azone, image_name):
        self._copy_default_data(container_name)

        container_data_path = os.path.join(
            self.container_path, container_name, 'data')

        # Provision common data
        try:
            # Try to get credentials from Alibaba CLI tool config
            with open(os.path.expanduser('~/.aliyun/config.json'), 'r') as f:
                cli_config = json.load(f)
            access_key_id = cli_config.get('profiles')[0].get('access_key_id')
            access_key_secret = cli_config.get(
                'profiles')[0].get('access_key_secret')
        except Exception as ex:
            LOG.warning('Unable to get Alibaba credentials.')
            access_key_id = 'Null'
            access_key_secret = 'Null'

        exec = os.path.join(UTILS_PATH, 'provision_common_data.sh')
        file = os.path.join(container_data_path, 'alibaba_common.yaml')
        cmd = f'{exec} -f {file} -i {access_key_id} -s {access_key_secret} \
            -k {keypair} -z {azone} -m {image_name} -l {container_name}'

        LOG.debug(f'Shell Command: \n {cmd}')
        res = subprocess.run(cmd, shell=True)
        if res.returncode > 0:
            LOG.error('Failed to provison common data.')
            return 1

        # Provision flavor data
        exec = os.path.join(UTILS_PATH, 'provision_flavor_data.sh')
        file = os.path.join(container_data_path, 'alibaba_flavors.yaml')
        cmd = f'{exec} {flavor} {file}'

        res = subprocess.run(cmd, shell=True)
        if res.returncode > 0:
            LOG.error('Failed to provison flavor data.')
            return 1

        return 0


class TestScheduler():
    """Schedule the containerized avocado-cloud testing."""
    pass


class TestWorker():
    """Execute the containerized avocado-cloud testing."""

    def __init__(self):

        self.container_assistant = ContainerAssistant(ARGS.config)
        self.cloud_assistant = CloudAssistant(ARGS.config)
        self.config_assistant = ConfigAssistant(ARGS.config)

    def _get_azone(self, flavor, in_used_azones=[]):
        """Get an available AZone for the specified flavor."""
        return self.cloud_assistant.get_available_azone(flavor)

    def _get_container(self):
        return

    def _provision_test(self, container_name, flavor, azone):
        self.config_assistant.provision_data(
            container_name=container_name,
            flavor=flavor,
            keypair=self.keypair,
            azone=azone,
            image_name=self.image_name)

        return None

    def _execute_test(self, container_name):
        return self.container_assistant.trigger_container_run(container_name)

    def _collect_log(self, container_name):
        result_path = os.path.join(self.container_path,
                                   container_name, 'job-results')
        for dirname in os.listdir(result_path):
            if dirname.startswith('job-'):
                shutil.move(os.path.join(result_path, dirname),
                            os.path.join(self.log_path, dirname))

    def start(self, flavor):

        # Get AZone
        azone = self.cloud_assistant.pick_azone(flavor)

        # Get container
        container = self.container_assistant.pick_container()

        exit(0)
        # Provision data
        self._provision_test(container_name=container,
                             flavor=flavor, azone=azone)

        # Execute the test
        res = self._execute_test(container)

        # Collect the logs
        self._collect_log(container)


if __name__ == '__main__':
    # Load and parse user config
    with open(ARGS.config, 'r') as f:
        config = toml.load(f)
        LOG.debug(f'{ARGS.config}: {config}')

    containers = config.get('containers')
    if not isinstance(containers, dict):
        LOG.error('Cannot get valid containers from the config file.')
        exit(1)
    else:
        LOG.debug(f'Get user config "containers": {containers}')

    enabled_regions = config.get('enabled_regions')
    if not isinstance(enabled_regions, list):
        LOG.error('Cannot get valid enabled_regions from the config file.')
        exit(1)
    else:
        LOG.debug(f'Get user config "enabled_regions": {enabled_regions}')

    image_name = config.get('image_name')
    if not isinstance(image_name, str):
        LOG.error('Cannot get valid image_name from the config file.')
        exit(1)
    else:
        LOG.debug(f'image_name: {image_name}')

    container_path = containers.get('container_path', '/tmp')

    scheduler = TestScheduler()
    worker = TestWorker()

    worker.start('ecs.i2.xlarge')


exit(0)
