#!/usr/bin/env python3
"""
Execute containerized avocado-cloud tests for Alibaba Cloud.
"""

import argparse
import logging
import toml
import json
import os
import subprocess
import shutil
import random
import time

REPO_PATH = os.path.split(os.path.realpath(__file__))[0]

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

ARG_PARSER = argparse.ArgumentParser(description="Execute containerized \
avocado-cloud tests for Alibaba Cloud.")
ARG_PARSER.add_argument(
    '--config',
    dest='config',
    action='store',
    help='Toml file for test executor configuration.',
    default='./config.toml',
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


class ContainerAssistant():
    """Deal with container resources."""

    def __init__(self, config_file):
        # Load and parse user config
        with open(config_file, 'r') as f:
            _data = toml.load(f)
            config = _data.get('executor', {})
            LOG.debug(f'{ARGS.config}: {config}')

        self.dry_run = config.get('dry_run', False)
        self.container_image = config.get('container_image')
        self.container_path = config.get('container_path')
        container_pool_name = config.get('container_pool_name', 'ac')
        container_pool_size = config.get('container_pool_size', 32)

        LOG.debug(f'Got dry_run: {self.dry_run}')
        LOG.debug(f'Got container_image: {self.container_image}')
        LOG.debug(f'Got container_path: {self.container_path}')
        LOG.debug(f'Got container_pool_name: {container_pool_name}')
        LOG.debug(f'Got container_pool_size: {container_pool_size}')

        # Verify container image
        cmd = f'podman inspect {self.container_image} &>/dev/null'
        res = subprocess.run(cmd, shell=True)
        if res.returncode == 0:
            LOG.debug(f'Container image "{self.container_image}" is valid.')
        else:
            LOG.error(f'Container image "{self.container_image}" is invalid.')
            exit(1)

        # Create container pool
        self.container_pool = [
            f'{container_pool_name}{x:0{len(str(container_pool_size-1))}d}'
            for x in range(container_pool_size)]
        LOG.debug(f'Container Pool: {self.container_pool}')

        # Create container path if needed
        os.makedirs(self.container_path, exist_ok=True)

    def get_container_status(self):
        """Get the status of containers in the pool.

        Input:
            N/A
        Return:
            - dict of the container status
        """
        status = {}
        for name in self.container_pool:
            cmd = f'podman inspect --type container {name} &>/dev/null'
            res = subprocess.run(cmd, shell=True)
            if res.returncode == 0:
                status[name] = 'unavailable'
            else:
                status[name] = 'available'

        LOG.debug(f'Container Status: {status}')

        return status

    def random_pick_container(self, containers):
        """Randomly pick a container from the list of containers.

        Input:
            - containers - List of containers
        Return:
            - container (string) or None if azones is empty.
        """
        if not containers:
            return None

        # Randomly pick a container
        idx = random.randint(0, len(containers)-1)
        container = containers[idx]

        LOG.debug(
            f'Randomly picked container "{container}" from "{containers}".')
        return container

    def _lock_container(self, container, lock_sec=120):
        """Lock the container for specified seconds.

        Input:
            - container - Name of the container
            - lock_sec  - Seconds for keeping container locked
        Return:
            - 0 if succeed or,
            - 1 for errors
        """
        cmd = f'podman run --name {container} --rm -itd \
            {self.container_image} /usr/bin/sleep {lock_sec}'
        LOG.debug(f'Lock container "{container}" by command: {cmd}')
        res = subprocess.run(cmd, shell=True)

        if res.returncode > 0:
            return 1

        return 0

    def _unlock_container(self, container):
        """Unlock the container.

        Input:
            - container - Name of the container
        Return:
            - 0 if succeed or,
            - 1 for errors
        """
        cmd = f'podman kill {container}'
        LOG.debug(f'Unlock container "{container}" by command: {cmd}')
        res = subprocess.run(cmd, shell=True)

        if res.returncode > 0:
            return 1

        # Wait 2 seconds for releasing the resources
        time.sleep(2)

        return 0

    def pick_container(self, lock_sec=120):
        """Pick a container for the test.

        Input:
            - lock_sec - Seconds for keeping container locked
        Return:
            - (0, container) - succeed
            - (1, None)      - general error
            - (2, None)      - no idle container
            - (3, None)      - failed to lock container
        """
        status = self.get_container_status()
        available_containers = [
            x for x in status.keys() if status[x] == 'available']

        if not available_containers:
            LOG.debug('No idle container in the pool.')
            return (2, None)

        # Randomly pick a container
        container = self.random_pick_container(available_containers)
        LOG.info(
            f'Picked container "{container}" from "{available_containers}".')

        # Lock the container if asked
        if lock_sec > 0:
            res = self._lock_container(container, lock_sec)
            if res > 0:
                LOG.error(f'Failed to lock container {container}.')
                return (3, None)

        return (0, container)

    def run_container(self, container_name, flavor='flavor', log_path=None):
        """Trigger a container to run (perform the provisioned test).

        Input:
            - container_name - which container to run
            - flavor         - Instance Type
            - log_path       - where to put the logs
        Return:
            - 0 for a passed test, or
            - !0 for a failed one
        """
        # Unlock the container
        self._unlock_container(container_name)

        # Run tests
        exec = os.path.join(UTILS_PATH, 'run.sh')
        cmd = f'{exec} -p {self.container_path} -n {container_name} \
            -m {self.container_image}'
        if log_path:
            cmd += f' -l {log_path}'

        LOG.info(f'Running test against "{flavor}" from container '
                 f'"{container_name}"...')

        if self.dry_run:
            LOG.info('!!!DRYRUN!!! Generate return code randomly.')
            time.sleep(random.random() * 3 + 2)
            return_code = random.randint(0, 6)
        else:
            res = subprocess.run(cmd, shell=True)
            return_code = res.returncode

        if return_code == 0:
            LOG.info(f'PASSED! Test against "{flavor}" from container '
                     f'"{container_name}".')
        else:
            LOG.info(f'FAILED! Test against "{flavor}" from container '
                     f'"{container_name}".')

        return return_code


class CloudAssistant():
    """Deal with cloud resources."""

    def __init__(self, config_file):
        # Load and parse user config
        with open(config_file, 'r') as f:
            _data = toml.load(f)
            config = _data.get('executor', {})
            LOG.debug(f'{ARGS.config}: {config}')

        self.zone = config.get('zone')
        if self.zone:
            LOG.debug(f'Specify the zone: {self.zone}')
            return

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
            res = subprocess.run(cmd, shell=True)

            if res.returncode == 2:
                LOG.debug(
                    'Another instance of query_flavors.sh is running, wait 60s for it.')
                time.sleep(60)
            elif res.returncode != 0:
                LOG.error(f'Failed to generate {distribution_file}')
                exit(1)

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
        Return:
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
        Return:
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
        Return:
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
        Return:
            - AZ (string) if succeed
            - 2 if flavor is out of stock
            - 3 if AZs are not enabled
            - 4 if AZs are occupied
        """

        # Get all possible AZs
        possible_azones = self.get_possible_azones(flavor)

        if not possible_azones:
            LOG.info(f'Flavor "{flavor}" is out of stock.')
            return 2

        # Get eligible AZs based on possible ones
        eligible_azones = self.get_eligible_azones(possible_azones)

        if not eligible_azones:
            LOG.info(f'''The flavor "{flavor}" is InStock but it is outside \
the enabled regions. Please consider enabling more regions! Information: \
Possible AZs: {possible_azones} Enabled regions: {self.enabled_regions}''')
            return 3

        # Get occupied AZs and filter them out
        occupied_azones = self.get_occupied_azones(azones=eligible_azones)
        available_azones = [
            x for x in eligible_azones if x not in occupied_azones]

        if not available_azones:
            LOG.info(f'''All AZs enabled for "{flavor}" are occupied. \
Please try again later! Information: Eligible Zones: {eligible_azones} \
Occupied Zone: {occupied_azones}''')
            return 4

        # Randomly pick an AZ
        azone = self.random_pick_azone(available_azones)
        LOG.info(f'Picked AZ "{azone}" for flavor "{flavor}" '
                 f'from "{possible_azones}".')

        return azone

    def _aliyun_cli(self, cmd):
        LOG.debug(f'Aliyun CLI: {cmd}')
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        if p.returncode == 0:
            return json.loads(p.stdout)
        else:
            return None

    def _get_all_regions(self):
        data = self._aliyun_cli('aliyun ecs DescribeRegions')
        regions = [x.get('RegionId', '')
                   for x in data.get('Regions', {}).get('Region', [])]

        LOG.debug(f'Function _get_all_regions returns: {regions}')
        return regions

    def _get_endpoint(self, region):
        data = self._aliyun_cli('aliyun ecs DescribeRegions')
        regions_info = data.get('Regions', {}).get('Region', [])
        for x in regions_info:
            if x.get('RegionId', '') == region:
                endpoint = x.get('RegionEndpoint', '')
                break
        return endpoint

    def _get_all_instances(self, regions=None):
        if not regions:
            regions = self._get_all_regions()

        instances = []
        for region in regions:
            endpoint = self._get_endpoint(region)
            data = self._aliyun_cli(
                f'aliyun --endpoint {endpoint} ecs DescribeInstances --RegionId {region} --PageSize 50')
            if data is None:
                continue
            for x in data.get('Instances', {}).get('Instance'):
                instances.append({'InstanceName': x.get('InstanceName'),
                                  'InstanceId': x.get('InstanceId'),
                                  'ZoneId': x.get('ZoneId'),
                                  'Status': x.get('Status')})

        LOG.debug(f'Function _get_all_instances returns: {instances}')
        return instances

    def get_occupied_azones(self, label_prefix='qeauto', azones=None):
        if azones:
            # Convert AZs to regions
            regions = []
            for azone in azones:
                if azone[-2:-1] == '-':
                    # Ex. "cn-beijing-h"
                    region = azone[:-2]
                else:
                    # Ex. "us-west-1a"
                    region = azone[:-1]
                if region not in regions:
                    regions.append(region)
        else:
            regions = None

        instances = self._get_all_instances(regions)

        occupied_azones = []
        for instance in instances:
            if f'{label_prefix}-instance-' in instance['InstanceName']:
                occupied_azones.append(instance['ZoneId'])

        LOG.debug(f'Function get_occupied_azones returns: {occupied_azones}')
        return occupied_azones


class ConfigAssistant():
    """Provision config for avocado-cloud testing."""

    def __init__(self, config_file):
        # Load and parse user config
        with open(config_file, 'r') as f:
            _data = toml.load(f)
            config = _data.get('executor', {})
            LOG.debug(f'{ARGS.config}: {config}')

        container_path = config.get('container_path')
        if not os.path.isdir(container_path):
            LOG.error(f'Container path "{container_path}" does not exist.')
            exit(1)
        else:
            LOG.debug(f'Get user config "container_path": {container_path}')

        self.container_path = container_path

        # Parse test configure
        _test = config.get('test', {})

        self.identity_file = _test.get('identity_file')
        if self.identity_file is None:
            LOG.error('The ssh identity file (test.identity_file) '
                      'is not specified.')
            exit(1)
        if not self.identity_file or not os.path.isfile(self.identity_file):
            LOG.error(f'The ssh identity file ({self.identity_file}) '
                      'cannot be found.')
            exit(1)
        if not self.identity_file.endswith('.pem'):
            LOG.error(f'The ssh identity file ({self.identity_file}) '
                      'must be suffixed with ".pem".')
            exit(1)

        self.keypair = _test.get('ssh_keypair')
        if self.keypair is None:
            LOG.error('The keypair (test.ssh_keypair) is not specified.')
            exit(1)

        self.image_name = _test.get('image_name')
        if self.image_name is None:
            LOG.error('The image name (test.image_name) is not specified.')
            exit(1)

        self.ddh_id = _test.get('ddh_id')
        self.provider = _test.get('provider')
        self.testcases = _test.get('testcases')

    def _aliyun_cli(self, cmd):
        LOG.debug(f'CLI Request: {cmd}')
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        if p.returncode > 0:
            raise "Failed to obtain information from Alibaba Cloud CLI."

        return json.loads(p.stdout)

    def _pre_action(self, container_name):
        # Create directories
        data_path = os.path.join(self.container_path, container_name, 'data')
        result_path = os.path.join(
            self.container_path, container_name, 'job-results')

        # TODO: enhance this logic
        os.makedirs(data_path, exist_ok=True)
        os.makedirs(result_path, exist_ok=True)

        # Deliver configure files
        LOG.debug(f'Copying default data into {data_path}')
        cmd = f'cp {TEMPLATE_PATH}/*.yaml {data_path}/; \
            rm -f {data_path}/*.pem; cp {self.identity_file} {data_path}/'

        res = subprocess.run(cmd, shell=True)
        if res.returncode > 0:
            LOG.error('Failed to deliver configure files.')
            return 1

    def _post_action(self, container_name):
        pass

    def _get_alibaba_credentials(self):
        try:
            # Get credentials from Alibaba CLI tool config
            with open(os.path.expanduser('~/.aliyun/config.json'), 'r') as f:
                cli_config = json.load(f)
            access_key_id = cli_config.get(
                'profiles')[0].get('access_key_id')
            access_key_secret = cli_config.get(
                'profiles')[0].get('access_key_secret')
        except Exception as ex:
            LOG.warning('Unable to get Alibaba credentials from CLI config.')
            access_key_id = 'Null'
            access_key_secret = 'Null'

        return (access_key_id, access_key_secret)

    def provision_data(self, container_name, flavor, azone):
        """Provision config for avocado-cloud testing.

        Input:
            - container_name    - Container Name
            - flavor            - Instance Type
            - azone             - AZ
        Return:
            - 0 if succeed, or
            - 1 if failed
        """
        # Pre-action
        self._pre_action(container_name)

        # Preparation
        data_path = os.path.join(self.container_path, container_name, 'data')
        os.makedirs(data_path, exist_ok=True)

        # Provision config list
        file = os.path.join(data_path, f'test_{self.provider}.yaml')
        lines = [
            f'test:\n',
            f'    !include : {self.provider}_flavors.yaml\n'
            f'    !include : {self.provider}_testcases.yaml\n'
            f'    !include : {self.provider}_common.yaml\n'
        ]
        with open(file, 'w') as f:
            f.writelines(lines)

        # Provision common data
        file = os.path.join(data_path, f'{self.provider}_common.yaml')
        exec = os.path.join(UTILS_PATH, 'provision_common_data.sh')
        access_key_id, access_key_secret = self._get_alibaba_credentials()
        cmd = f'{exec} -f {file} -i {access_key_id} -s {access_key_secret} \
            -k {self.keypair} -z {azone} -m {self.image_name} \
            -l {container_name}'
        if self.ddh_id:
            cmd = cmd + f' -d {self.ddh_id}'

        LOG.debug(f'Update "{file}" by command "{cmd}".')
        res = subprocess.run(cmd, shell=True)
        if res.returncode > 0:
            LOG.error(f'Failed to update "{file}".')
            return 1

        # Provision flavors data
        file = os.path.join(data_path, f'{self.provider}_flavors.yaml')
        exec = os.path.join(UTILS_PATH, 'provision_flavor_data.py')
        cmd = f'{exec} --file {file} --flavor {flavor}'

        LOG.debug(f'Update "{file}" by command "{cmd}".')
        res = subprocess.run(cmd, shell=True)
        if res.returncode > 0:
            LOG.error(f'Failed to update "{file}".')
            return 1

        # Provision testcases data
        file = os.path.join(data_path, f'{self.provider}_testcases.yaml')

        lines = ['cases:\n']
        for _case in self.testcases.split('\n'):
            case = _case.strip()

            if not case:
                continue
            if case.startswith('#'):
                continue

            lines.append(f'  {case.strip()}\n')

        with open(file, 'w') as f:
            f.writelines(lines)

        # Post-action
        self._post_action(container_name)

        return 0


class TestExecutor():
    """Execute the containerized avocado-cloud testing."""

    def __init__(self):
        # Load and parse user config
        with open(ARGS.config, 'r') as f:
            _data = toml.load(f)
            config = _data.get('executor', {})
            LOG.debug(f'{ARGS.config}: {config}')

        self.container_assistant = ContainerAssistant(ARGS.config)
        self.cloud_assistant = CloudAssistant(ARGS.config)
        self.config_assistant = ConfigAssistant(ARGS.config)

        log_path = config.get('log_path', os.path.join(REPO_PATH, 'logs'))
        if not isinstance(log_path, str):
            LOG.error('Invalid log_path (string) in config file.')
            exit(1)
        else:
            LOG.debug(f'Get user config "log_path": {log_path}')

        if not os.path.exists(log_path):
            os.mkdir(log_path)
        self.log_path = log_path

    def _run(self, flavor):
        """Run a single avocado-cloud testing.

        Input:
            - flavor - Instance Type
        Return:
            - 0  - Test executed and passed (test_passed)
            - 11 - Test error due to general error (test_general_error)
            - 12 - Test error due to container error (test_container_error)
            - 13 - Test error due to log delivery error (test_log_delivery_error)
            - 14 - Test failed due to general error (test_failed_general)
            - 15 - Test failed due to error cases (test_failed_error_cases)
            - 16 - Test failed due to failure cases (test_failed_failure_cases)
            - 21 - General failure while getting AZ (flavor_general_error)
            - 22 - Flavor is out of stock (flavor_no_stock)
            - 23 - Possible AZs are not enabled (flavor_azone_disabled)
            - 24 - Eligible AZs are occupied (flavor_azone_occupied)
            - 31 - General failure while getting container (container_error)
            - 32 - Cannot get idle container (container_all_busy)
            - 33 - Lock or Unlock container failed (container_lock_error)
            - 41 - General failure while provisioning data (provision_error)
        """

        if self.cloud_assistant.zone:
            azone = self.cloud_assistant.zone
        else:
            # Get AZ
            try:
                azone = self.cloud_assistant.pick_azone(flavor)
            except Exception as ex:
                LOG.error(f'Failed to get AZ: {ex}')
                return 21

        if isinstance(azone, int):
            return azone + 20

        # Get container
        try:
            res, container = self.container_assistant.pick_container()
        except Exception as ex:
            LOG.error(f'Failed to get container: {ex}')
            return 31

        if res > 0:
            return res + 30

        # Provision data
        try:
            res = self.config_assistant.provision_data(
                container_name=container,
                flavor=flavor,
                azone=azone)
        except Exception as ex:
            LOG.error(f'Failed to provision data: {ex}')
            return 41

        if res > 0:
            return res + 40

        # Execute the test and collect log
        try:
            res = self.container_assistant.run_container(
                container_name=container,
                flavor=flavor,
                log_path=self.log_path)
        except Exception as ex:
            LOG.error(f'Failed to execute test: {ex}')
            return 11

        if res > 0:
            return res + 10

        return 0

    def run(self, flavor):

        code_to_status = {
            0: 'test_passed',
            11: 'test_general_error',
            12: 'test_container_error',
            13: 'test_log_delivery_error',
            14: 'test_failed_general',
            15: 'test_failed_error_cases',
            16: 'test_failed_failure_cases',
            21: 'flavor_general_error',
            22: 'flavor_no_stock',
            23: 'flavor_azone_disabled',
            24: 'flavor_azone_occupied',
            31: 'container_error',
            32: 'container_all_busy',
            33: 'container_lock_error',
            41: 'provision_error'
        }

        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        LOG.info(f'Test Started: {timestamp}')

        return_code = self._run(flavor)

        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        LOG.info(f'Test Finished: {timestamp}')

        status = code_to_status.get(return_code, 'unknown_status')
        LOG.info(f'Exit Code: {return_code} ({status})')

        return return_code


if __name__ == '__main__':

    executor = TestExecutor()
    code = executor.run(ARGS.flavor)

    exit(code)
