#!/bin/bash

# Description: Get a list of available flavors.
# Maintainer: Charles Shih <schrht@gmail.com>
#
# Dependence:
#   aliyun - CLI tool for Alibaba Cloud
#   jq     - Command-line JSON processor

function show_usage() {
    echo "Get a list of available flavors." >&2
    echo "$(basename $0) [-o OUTPUT_FILE] [-r REGION_LIST]" >&2
}

while getopts :ho:r: ARGS; do
    case $ARGS in
    h)
        # Help option
        show_usage
        exit 0
        ;;
    o)
        # Output file option
        output=$OPTARG
        ;;
    r)
        # Region list option
        regions=$OPTARG
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

: ${output:=/tmp/aliyun_flavor_distribution.txt}

# Main
lckfile=/tmp/aliyun_flavor_distribution.lck
if [ -f $lckfile ]; then
    pid=$(cat $lckfile)
    if (ps -q $pid &>/dev/null); then
        echo "Another instance of this script is running as PID $pid, exit!"
        exit 2
    fi
fi
echo $$ > $lckfile

tmpfile=/tmp/aliyun_flavor_distribution.tmp
: >$tmpfile

# Get all regions if not specified
if [ -z "$regions" ]; then
    x=$(aliyun ecs DescribeRegions | jq -r '.Regions.Region[].RegionId')
    [ "$?" != "0" ] && echo $x >&2 && exit 1
    regions=$x
fi

# Query flavors in each region
for region in $regions; do
    # Get AvailableResource
    echo -e "\nQuerying resource from the region $region ..." >&2
    x=$(aliyun ecs DescribeAvailableResource --RegionId $region \
        --DestinationResource InstanceType)
    if [ "$?" != "0" ]; then
        echo "$(basename $0): warning: aliyun ecs DescribeAvailableResource --RegionId $region" >&2
        echo $x >&2
        continue
    fi

    # Filter eligible AvailableZones
    x=$(echo $x | jq -r ".AvailableZones.AvailableZone[] | \
        select(.StatusCategory==\"WithStock\") | select(.Status==\"Available\")")
    zones=$(echo $x | jq -r '.ZoneId')

    for zone in $zones; do
        # Filter eligible Flavors
        flavors=$(echo $x | jq -r "select(.ZoneId==\"$zone\") | \
            .AvailableResources.AvailableResource[].SupportedResources.SupportedResource[] | \
            select(.Status==\"Available\") | select(.StatusCategory==\"WithStock\") | .Value")

        # Dump results
        for flavor in $flavors; do
            echo "$zone,$flavor" >>$tmpfile
        done
    done
done

echo -e "\nSaving resource matrix to $output ..." >&2
mv $tmpfile $output
rm $lckfile

echo -e "\nDone!" >&2

exit 0
