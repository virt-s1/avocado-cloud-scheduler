#!/bin/bash

# Description: Run avocado-cloud test from container.
# Maintainer: Charles Shih <schrht@gmail.com>
#
# Exit code:
# - 0: test succeed
# - 1: test error due to general error
# - 2: test error due to container error
# - 3: test error due to log delivery error
# - 4: test failed due to general error
# - 5: test failed due to error cases
# - 6: test failed due to failure cases (no error case)

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
echo "INFO: Setup..." >&2
data_path=${container_path}/${container_name}/data
result_path=${container_path}/${container_name}/job-results

mkdir -p ${data_path} ${result_path} ${log_path}
rm -rf ${result_path}/latest

chcon -R -u system_u -t svirt_sandbox_file_t ${container_path}

# Test
echo "INFO: Test..." >&2
podman run --name ${container_name} --rm -it \
    -v ${data_path}:/data:rw \
    -v ${result_path}:/root/avocado/job-results:rw \
    ${container_image} /bin/bash ./container/bin/test_alibaba.sh
result=$?
echo "DEBUG: return code from podman triggering: $result"

# Get log directory
logdir_by_link=$(file ${result_path}/latest | sed "s#^.*link to #${result_path}/#")
if [ -d "${logdir_by_link}" ]; then
    echo "DEBUG: Use logdir_by_link (${logdir_by_link})" >&2
    logdir="${logdir_by_link}"
else
    echo "WARNING: it seems that avocado-cloud test was not triggered." >&2
    logdir=""
fi

echo "INFO: Log directory: ${logdir:-'Not Found'}" >&2

if [ $result -eq 0 ]; then
    # 0 - test succeed
    echo "INFO: Test finished (return=$result), test succeed." >&2
    code=0
elif [ $result -eq 125 ]; then
    # 125 - contianer error
    echo "INFO: Test finished (return=$result), contianer error." >&2
    code=2
else
    # others - do further analysis
    echo "INFO: Test finished (return=$result), do furthur analysis..." >&2

    results_json=$logdir/results.json
    if [ ! -f ${results_json} ]; then
        echo "WARNING: Cannot found ${results_json}." >&2
    fi

    error_num=$(cat ${results_json} | jq -r '.errors')
    fail_num=$(cat ${results_json} | jq -r '.failures')
    echo "INFO: Statistics from results.json: errors=$error_num; failures=$fail_num;" >&2

    if [ -z "$error_num" ] || [ "$fail_num" = "null" ]; then
        code=4 # test failed due to general error
    elif [ -z "$error_num" ] || [ "$error_num" = "null" ]; then
        code=4
    elif [ $error_num -gt 0 ]; then
        code=5 # test failed due to error cases
    elif [ $fail_num -gt 0 ]; then
        code=6 # test failed due to failure cases
    else
        code=4
    fi
fi

echo "INFO: Return code: $code" >&2

# Teardown
echo "INFO: Teardown..." >&2

if [ -d "$logdir" ]; then
    echo "INFO: Moving *.yaml to $logdir/testinfo ..." >&2
    mkdir -p $logdir/testinfo
    cp ${data_path}/*.yaml $logdir/testinfo/
else
    echo "DEBUG: Skip moving *.yaml to $logdir/testinfo ..." >&2
fi

if [ -d "$logdir" ] && [ -d "${log_path}" ]; then
    echo "INFO: Moving $logdir to ${log_path} ..." >&2
    mv $logdir ${log_path}/ || exit 3
else
    echo "DEBUG: Skip moving $logdir to ${log_path} ..." >&2
fi

exit $code
