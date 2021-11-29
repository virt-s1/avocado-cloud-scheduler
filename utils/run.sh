#!/bin/bash

# Description: Run avocado-cloud test from container.
# Maintainer: Charles Shih <schrht@gmail.com>

function show_usage() {
    echo "Run avocado-cloud test from container." >&2
    echo "$(basename $0) [-h] <-p container_path> \
        <-n container_name> <-m container_image> \
        [-l log_path]" >&2
}

while getopts :hp:n:m:l: ARGS; do
    case $ARGS in
    h)
        # Help option
        show_usage
        exit 0
        ;;
    p)
        # Container path
        container_path=$OPTARG
        ;;
    n)
        # Container name
        container_name=$OPTARG
        ;;
    m)
        # Container image
        container_image=$OPTARG
        ;;
    l)
        # Log path
        log_path=$OPTARG
        ;;
    "?")
        echo "$(basename $0): unknown option: $OPTARG" >&2
        ;;
    ":")
        echo "$(basename $0): option requires an argument -- '$OPTARG'" >&2
        echo "Try '$(basename $0) -h' for more information." >&2
        exit 1
        ;;
    *)
        # Unexpected errors
        echo "$(basename $0): unexpected error -- $ARGS" >&2
        echo "Try '$(basename $0) -h' for more information." >&2
        exit 1
        ;;
    esac
done

[ -z "${container_path}" ] && show_usage && exit 1
[ -z "${container_name}" ] && show_usage && exit 1
[ -z "${container_image}" ] && show_usage && exit 1

# Setup
echo "Setup..." >&2
data_path=${container_path}/${container_name}/data
result_path=${container_path}/${container_name}/job-results

mkdir -p ${data_path} ${result_path} ${log_path}
rm -rf ${result_path}/latest

chcon -R -u system_u -t svirt_sandbox_file_t ${container_path}

# Test
echo "Test..." >&2
podman run --name ${container_name} --rm -it \
    -v ${data_path}:/data:rw \
    -v ${result_path}:/root/avocado/job-results:rw \
    ${container_image} /bin/bash ./container/bin/test_alibaba.sh
result=$?

testinfo_path=${result_path}/latest/testinfo
mkdir -p ${testinfo_path}
cp ${data_path}/*.yaml ${testinfo_path}/

# Teardown
echo "Teardown..." >&2
if [ -d "${log_path}" ]; then
    logdir=$(ls -td ${result_path}/job-* | head -n 1)
    echo "Moving $logdir to ${log_path} ..." >&2
    mv $logdir ${log_path}/
fi

exit $result
