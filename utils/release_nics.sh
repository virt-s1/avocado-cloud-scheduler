#!/bin/bash

# Description: Query and release Network Interface resources.
# Maintainer: Charles Shih <schrht@gmail.com>
#
# Dependence:
#   aliyun - CLI tool for Alibaba Cloud
#   jq     - Command-line JSON processor

function show_usage() {
    echo "Query and release Network Interface resources.." >&2
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
echo -e "\nQuerying NICs..." >&2

nics=()

for region in $regions; do
    x=$(aliyun ecs DescribeNetworkInterfaces --RegionId $region --PageSize 100)
    [ "$?" != "0" ] && echo $x >&2 && continue

    tuples=$(echo $x | jq -r '.NetworkInterfaceSets.NetworkInterfaceSet')
    length=$(echo $x | jq -r '.NetworkInterfaceSets.NetworkInterfaceSet | length')

    for ((i = 0; i < $length; i++)); do
        tuple=$(echo $tuples | jq -r ".[$i]")

        # Ex. tuple:
        # {
        # "AssociatedPublicIp": {},
        # "Attachment": {},
        # "CreationTime": "2021-03-03T13:38:19Z",
        # "InstanceId": "",
        # "MacAddress": "00:16:3e:02:91:ed",
        # "NetworkInterfaceId": "eni-uf65jba7lvguh2osu4s2",
        # "NetworkInterfaceName": "cheshi-nic-ac8",
        # "PrivateIpAddress": "172.19.88.175",
        # "Status": "Available",
        # "Type": "Secondary",
        # "VSwitchId": "vsw-uf6btqbz9nczva8on2y5x",
        # "VpcId": "vpc-uf6whqlr578xn6wyh9bzk",
        # "ZoneId": "cn-shanghai-g"
        # ......
        # }

        _region_id=$region
        _nic_id=$(echo $tuple | jq -r '.NetworkInterfaceId')
        _nic_name=$(echo $tuple | jq -r '.NetworkInterfaceName')
        _status=$(echo $tuple | jq -r '.Status')

        echo "${_region_id}: ${_nic_id}(${_nic_name}) [${_status}]" >&2
        nics+=("${_region_id};${_nic_id};${_nic_name};${_status}")
    done
done

# Release
echo -e "\nTrying to release NICs..." >&2

for nic in ${nics[@]}; do
    # Unpack varibles
    _region_id=$(echo $nic | cut -d ';' -f 1)
    _nic_id=$(echo $nic | cut -d ';' -f 2)
    _nic_name=$(echo $nic | cut -d ';' -f 3)
    _status=$(echo $nic | cut -d ';' -f 4)

    #echo "${_region_id}: ${_nic_id}(${_nic_name}) [${_status}]" >&2

    # Criteria check
    if [[ ! "${_nic_name}" =~ ^"$prefix" ]]; then
        echo "${_region_id}: ${_nic_id}(${_nic_name}): SKIP (Not start with '$prefix')"
        continue
    fi

    if [ "${_status}" != "Available" ]; then
        echo "${_region_id}: ${_nic_id}(${_nic_name}): SKIP (Status: ${_status})"
        continue
    fi

    # Try to release
    aliyun ecs DeleteNetworkInterface --RegionId $_region_id --NetworkInterfaceId ${_nic_id} 1>/dev/null && sleep 2

    x=$(aliyun ecs DescribeNetworkInterfaces --RegionId ${_region_id} --NetworkInterfaceId.1 ${_nic_id})
    if [ "$?" != "0" ]; then
        echo $x >&2
        echo "${_region_id}: ${_nic_id}(${_nic_name}): FAIL (DescribeNetworkInterfaces)"
        continue
    fi

    _length=$(echo $x | jq -r '.NetworkInterfaceSets.NetworkInterfaceSet | length')
    if [ "${_length}" -eq 0 ]; then
        echo "${_region_id}: ${_nic_id}(${_nic_name}): RELEASED"
    else
        echo "${_region_id}: ${_nic_id}(${_nic_name}): FAIL (Still Exists)"
    fi
done

exit 0
