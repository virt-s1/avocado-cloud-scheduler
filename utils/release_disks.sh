#!/bin/bash

# Description: Query and release Cloud Disk resources.
# Maintainer: Charles Shih <schrht@gmail.com>
#
# Dependence:
#   aliyun - CLI tool for Alibaba Cloud
#   jq     - Command-line JSON processor

function show_usage() {
    echo "Query and release Cloud Disk resources." >&2
    echo "$(basename $0) [-r REGION_LIST] <-p PREFIX>" >&2
}

while getopts :hr:p: ARGS; do
    case $ARGS in
    h)
        # Help option
        show_usage
        exit 0
        ;;
    r)
        # Region list option
        regions=$OPTARG
        ;;
    p)
        # Resource prefix option
        prefix=$OPTARG
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

# Main
if [ -z "$prefix" ]; then
    show_usage
    exit 1
fi

if [ -z "$regions" ]; then
    x=$(aliyun ecs DescribeRegions)
    [ "$?" != "0" ] && echo $x >&2 && exit 1
    regions=$(echo $x | jq -r '.Regions.Region[].RegionId')
fi

# Query
echo -e "\nQuerying Cloud Disks..." >&2

disks=()

for region in $regions; do
    x=$(aliyun ecs DescribeDisks --RegionId $region --PageSize 100)
    [ "$?" != "0" ] && echo $x >&2 && continue

    tuples=$(echo $x | jq -r '.Disks.Disk')
    length=$(echo $x | jq -r '.Disks.Disk | length')

    for ((i = 0; i < $length; i++)); do
        tuple=$(echo $tuples | jq -r ".[$i]")

        # Ex. tuple:
        # {
        # "Category": "cloud_essd",
        # "CreationTime": "2022-01-12T11:34:36Z",
        # "DiskId": "d-uf66ddu4v4ykp8pwp5uu",
        # "DiskName": "qeauto-disk-ac05",
        # "InstanceId": "",
        # "PerformanceLevel": "PL1",
        # "RegionId": "cn-shanghai",
        # "Size": 100,
        # "Status": "Available",
        # "ZoneId": "cn-shanghai-l"
        # ......
        # }

        _region_id=$(echo $tuple | jq -r '.RegionId')
        _disk_id=$(echo $tuple | jq -r '.DiskId')
        _disk_name=$(echo $tuple | jq -r '.DiskName')
        _status=$(echo $tuple | jq -r '.Status')

        echo "${_region_id}: ${_disk_id}(${_disk_name}) [${_status}]" >&2
        disks+=("${_region_id};${_disk_id};${_disk_name};${_status}")
    done
done

# Release
echo -e "\nTrying to release Cloud Disks..." >&2

for disk in ${disks[@]}; do
    # Unpack varibles
    _region_id=$(echo $disk | cut -d ';' -f 1)
    _disk_id=$(echo $disk | cut -d ';' -f 2)
    _disk_name=$(echo $disk | cut -d ';' -f 3)
    _status=$(echo $disk | cut -d ';' -f 4)

    #echo "${_region_id}: ${_disk_id}(${_disk_name}) [${_status}]" >&2

    # Criteria check
    if [[ ! "${_disk_name}" =~ ^"$prefix" ]]; then
        echo "${_region_id}: ${_disk_id}(${_disk_name}): SKIP (Not start with '$prefix')"
        continue
    fi

    if [ "${_status}" != "Available" ]; then
        echo "${_region_id}: ${_disk_id}(${_disk_name}): SKIP (Status: ${_status})"
        continue
    fi

    # Try to release
    aliyun ecs DeleteDisk --DiskId ${_disk_id} 1>/dev/null && sleep 2

    x=$(aliyun ecs DescribeDisks --RegionId ${_region_id} --DiskIds "['${_disk_id}']")
    if [ "$?" != "0" ]; then
        echo $x >&2
        echo "${_region_id}: ${_disk_id}(${_disk_name}): FAIL (DescribeDisks)"
        continue
    fi

    _length=$(echo $x | jq -r '.Disks.Disk | length')
    if [ "${_length}" -eq 0 ]; then
        echo "${_region_id}: ${_disk_id}(${_disk_name}): RELEASED"
    else
        echo "${_region_id}: ${_disk_id}(${_disk_name}): FAIL (Still Exists)"
    fi
done

exit 0
