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

    def __init__(self, config={}):
        container_path = config.get('container_path', '/tmp')
        container_pool = config.get('container_pool', [])
        container_image = config.get('container_image')

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
        self.container_image = container_image

    def list_all_containers(self):
        return self.container_pool

    def list_available_containers(self):
        available_containers = []
        for container_name in self.container_pool:
            cmd = f'podman ps -a --format "{{{{.Names}}}}" \
                | grep -q -x {container_name}'
            res = subprocess.run(cmd, shell=True)
            LOG.debug(res)
            if res.returncode > 0:
                available_containers.append(container_name)

        LOG.debug(f'available_containers: {available_containers}')
        return available_containers

    def get_available_container(self):
        available_containers = self.list_available_containers()

        if len(available_containers) > 0:
            container = available_containers[0]
            LOG.debug(f'Got container "{container}"')
            return container
        else:
            LOG.debug('No available container left.')
            return None

    def trigger_container_run(self, container_name):
        # Prepare environment
        container_data_path = os.path.join(
            self.container_path, container_name, 'data')
        container_result_path = os.path.join(
            self.container_path, container_name, 'job-results')

        os.makedirs(container_data_path, exist_ok=True)
        os.makedirs(container_result_path, exist_ok=True)

        #os.unlink(os.path.join(container_result_path, 'latest'))

        subprocess.run(f'chcon -R -u system_u -t svirt_sandbox_file_t \
            {self.container_path}', shell=True)

        # Execute the test
        LOG.info(f'Run test in container "{container_name}"...')
        cmd = f'podman run --name {container_name} --rm -it \
            -v {container_data_path}:/data:rw \
            -v {container_result_path}:/root/avocado/job-results:rw \
            {self.container_image} /bin/bash ./container/bin/test_alibaba.sh'

        LOG.info(f'Run container with command: \n{cmd}')
        test_result = subprocess.run(cmd, shell=True)

        # Postprocess the logs
        import time
        time.sleep(10)
        LOG.info('Postprocessing logs...')
        os.makedirs(os.path.join(container_result_path,
                    'latest', 'testinfo'), exist_ok=True)
        shutil.copy(os.path.join(container_data_path, 'alibaba_common.yaml'),
                    os.path.join(container_result_path, 'latest', 'testinfo',
                                 'alibaba_common.yaml'))
        shutil.copy(os.path.join(container_data_path, 'alibaba_testcases.yaml'),
                    os.path.join(container_result_path, 'latest', 'testinfo',
                    'alibaba_testcases.yaml'))
        shutil.copy(os.path.join(container_data_path, 'alibaba_flavors.yaml'),
                    os.path.join(container_result_path, 'latest', 'testinfo',
                    'alibaba_flavors.yaml'))

        if test_result.returncode == 0:
            LOG.info(f'Test succeed in container "{container_name}".')
            return 0
        else:
            LOG.warning(f'Test failed in container "{container_name}".')
            return 1


class CloudAssistant():
    """Deal with cloud resources."""

    def __init__(self):
        # Query all available flavors in the cloud
        distribution_file = '/tmp/aliyun_flavor_distribution.txt'
        if not os.path.exists(distribution_file):
            exec = os.path.join(UTILS_PATH, 'query_flavors.sh')
            cmd = f'{exec} -o {distribution_file}'
            subprocess.run(cmd, shell=True)

        # TODO: consider make this process more frequently
        with open(distribution_file, 'r') as f:
            _list = f.readlines()

        location = {}
        for _entry in _list:
            _entry = _entry.strip().split(',')
            _azone = _entry[0]
            _flavor = _entry[1]

            if _flavor in location:
                location[_flavor].append(_azone)
            else:
                location[_flavor] = [_azone]

        #LOG.debug(f'flavor location: {location}')
        self.location = location

    def list_possible_azones(self, flavor):
        possible_azones = self.location.get(flavor, [])
        LOG.debug(f'possible_azones: {possible_azones}')
        return possible_azones

    def get_available_azone(self, flavor, enabled_regions):
        # Get possible AZs (all the AZs with the flavor in stock)
        possible_azones = self.list_possible_azones(flavor)
        if not possible_azones:
            LOG.error(f'Flavor "{flavor}" is NoStock.')
            return 1

        # Get eligible AZs (possible AZs in enabled regions)
        if '*' in possible_azones:
            # This will disable this feature
            eligible_azones = possible_azones
        else:
            # Get eligible AZs
            eligible_azones = []
            for zone in possible_azones:
                for region in enabled_regions:
                    if region in zone:
                        eligible_azones.append(zone)
                        break

        if not eligible_azones:
            LOG.error(f'The flavor "{flavor}" is InStock but it is outside '
                      f'the enabled regions. Please consider enabling more '
                      f'regions! Information: Possible AZs: {possible_azones} '
                      f'Enabled regions: {enabled_regions}')
            return 1
        else:
            LOG.debug(f'eligible_azones: {eligible_azones}')

        # Randomly pick an AZ
        idx = random.randint(0, len(eligible_azones)-1)
        available_azone = eligible_azones[idx]
        LOG.info(
            f'Randomly picked AZ "{available_azone}" for flavor "{flavor}".')

        return available_azone


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

        enabled_regions = self.config.get('enabled_regions')
        if not enabled_regions or not isinstance(enabled_regions, list):
            LOG.error('Cannot get valid enabled_regions from the config file.')
            exit(1)
        else:
            LOG.debug(f'enabled_regions: {enabled_regions}')

        image_name = self.config.get('image_name')
        if not image_name or not isinstance(image_name, str):
            LOG.error('Cannot get valid image_name from the config file.')
            exit(1)
        else:
            LOG.debug(f'image_name: {image_name}')

        container_path = container.get('container_path', '/tmp')
        self.container_assistant = ContainerAssistant(container)
        self.config_assistant = ConfigAssistant(container_path)
        self.cloud_assistant = CloudAssistant()

        self.container = container
        self.container_path = container_path
        self.log_path = self.config.get(
            'log_path', os.path.join(container_path, 'logs'))
        self.enabled_regions = enabled_regions

        self.image_name = image_name
        self.keypair = 'cheshi-docker'  # TODO

    def _get_azone(self, flavor, in_used_azones=[]):
        """Get an available AZone for the specified flavor."""
        return self.cloud_assistant.get_available_azone(
            flavor=flavor,
            enabled_regions=self.enabled_regions)

    def _get_container(self):
        return self.container_assistant.get_available_container()

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

    def signle_test(self, flavor):

        # Get AZone
        azone = self._get_azone(flavor)

        # Get container
        container = self._get_container()

        # Provision data
        self._provision_test(container_name=container,
                             flavor=flavor, azone=azone)

        # Execute the test
        res = self._execute_test(container)

        # Collect the logs
        self._collect_log(container)

        return None


class TestWorker():
    """Execute the containerized avocado-cloud testing."""
    pass


if __name__ == '__main__':
    scheduler = TestScheduler(ARGS)
    scheduler.signle_test(flavor='ecs.i2.xlarge')

exit(0)
