#!/bin/bash

# Description: Creat VSwitches for the specified region.
# Maintainer: Charles Shih <schrht@gmail.com>

function show_usage() {
    echo "Creat VSwitches for the specified region." >&2
    echo "$(basename $0) [-h] <-r region>" >&2
}

while getopts :hr: ARGS; do
    case $ARGS in
    h)
        # Help option
        show_usage
        exit 0
        ;;
    r)
        # region
        region=$OPTARG
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

if [ -z "$region" ]; then
    show_usage
    exit 1
fi

function get_available_cidr() {
    # Get available CIDR block
    # $1 - the VPC CIDR block
    # $@ - the list of existing CIDR blocks
    # random=$(((RANDOM % 16) << 4))
    # >> "0 16 32 48 64 80 96 112 128 144 160 176 192 208 224 240"

    vpc_cidr=$1 && shift
    vsw_existing_cidrs=$@
    candidates="0 16 32 48 64 80 96 112 128 144 160 176 192 208 224 240"

    netbits=${vpc_cidr##*/}
    for n in $candidates; do
        cidr=${vpc_cidr/%".0.0/$netbits"/".$n.0/20"}
        [ "$cidr" = "$vpc_cidr" ] && return 1
        if (echo $vsw_existing_cidrs | grep -q -w $cidr); then
            # Go to next one
            continue
        else
            # Found an available one
            echo $cidr
            break
        fi
    done
}

# Main
codepath=$(dirname $(which $0))
source $codepath/cli_utils.sh

_is_region $region
if [ "$?" != "0" ]; then
    echo "$(basename $0): invalid region id -- $region" >&2
    exit 1
fi

endpoint=$(region_to_endpoint $region)

# Get zones
x=$(aliyun --endpoint $endpoint ecs DescribeZones --RegionId $region)
zones=$(echo $x | jq -r '.Zones.Zone[].ZoneId' | sort)
[ -z "$zones" ] && echo "Failed to get Zones." >&2 && exit 1

# Get default VPC
vpc_block=$(aliyun --endpoint $endpoint ecs DescribeVpcs --RegionId $region)
vpc_id=$(echo ${vpc_block} | jq -r '.Vpcs.Vpc[].VpcId')
if [ -z "${vpc_id}" ]; then
    # Create VPC
    aliyun --endpoint $endpoint ecs CreateVpc --RegionId $region
    vpc_block=$(aliyun --endpoint $endpoint ecs DescribeVpcs --RegionId $region)
    vpc_id=$(echo ${vpc_block} | jq -r '.Vpcs.Vpc[].VpcId')
    [ -z "${vpc_id}" ] && echo "Failed to get VPC ID." >&2 && exit 1
fi

vpc_cidr=$(echo ${vpc_block} | jq -r '.Vpcs.Vpc[].CidrBlock')
[ -z "${vpc_cidr}" ] && echo "Failed to get VPC CIDR Block." >&2 && exit 1

# Assert: VPC CIDR in format "x.x.0.0/16"
netbits=${vpc_cidr##*/}
if [ $netbits -le 16 ]; then
    echo "INFO: The vpc_cidr \"${vpc_cidr}\" can be handled (netbits<=16)." >&2
else
    echo "ERROR: The vpc_cidr \"${vpc_cidr}\" cannot be handled (netbits>16)." >&2
    exit 1
fi

# Query all VSwitches from default VPC
vsw_block=$(aliyun --endpoint $endpoint ecs DescribeVSwitches --RegionId $region --VpcId ${vpc_id} --PageSize 50)

# Get all Zones with VSwithch
vsw_zones=$(echo ${vsw_block} | jq -r '.VSwitches.VSwitch[].ZoneId')
vsw_cidrs=$(echo ${vsw_block} | jq -r '.VSwitches.VSwitch[].CidrBlock')

for zone in $zones; do
    if (echo ${vsw_zones} | grep -q -w $zone); then
        # VSwitch exists: show info
        vsw_id=$(echo $vsw_block | jq -r ".VSwitches.VSwitch[] | select(.ZoneId==\"$zone\") | .VSwitchId") || exit 1
        vsw_cidr=$(echo $vsw_block | jq -r ".VSwitches.VSwitch[] | select(.ZoneId==\"$zone\") | .CidrBlock") || exit 1
        echo "$zone: ${vsw_id} [${vsw_cidr}]"
    else
        # VSwitch doesn't exist: Create a new one and show info
        vsw_cidr=$(get_available_cidr $vpc_cidr $vsw_cidrs)
        [ -z "${vsw_cidr}" ] && echo "No more CIDR block candidates." && exit 1
        vsw_cidrs="${vsw_cidrs} $vsw_cidr"
        x=$(aliyun --endpoint $endpoint ecs CreateVSwitch --RegionId $region --ZoneId $zone --VpcId ${vpc_id} \
            --CidrBlock ${vsw_cidr} --VSwitchName qe-auto-vswitch \
            --Description "Created with automation scripts.")

        if [ $? -ne 0 ]; then
            sleep 10
            x=$(aliyun --endpoint $endpoint ecs CreateVSwitch --RegionId $region --ZoneId $zone --VpcId ${vpc_id} \
                --CidrBlock ${vsw_cidr} --VSwitchName qe-auto-vswitch \
                --Description "Created with automation scripts.")
        fi
        if [ "$?" = "0" ]; then
            vsw_id=$(echo $x | jq -r '.VSwitchId') || exit 1
            echo "$zone: ${vsw_id} [${vsw_cidr}] (NEW)"
        else
            # Known issue: CreateVSwitch fails with deprecated Zones
            echo "$zone: ${vsw_id} [CREATION FAILED] (IGNORED)"
        fi
    fi
done

exit 0
