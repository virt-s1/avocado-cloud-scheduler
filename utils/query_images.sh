#!/bin/bash

# Description: Query images from the specified region.
# Maintainer: Charles Shih <schrht@gmail.com>

function show_usage() {
    echo "Query images from the specified region."
    echo "$(basename $0) [-h] <-r region> [-a] [-M]"
    echo "-a: query images for all platforms rather than Red Hat."
    echo "-M: query images from Marketplace."
}

while getopts :hr:aM ARGS; do
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
    a)
        # all
        all=true
        ;;
    M)
        # marketplace
        marketplace=true
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

if [ -z $region ]; then
    show_usage
    exit 1
fi

# Main
codepath=$(dirname $(which $0))
source $codepath/cli_utils.sh

_is_region $region
if [ "$?" != "0" ]; then
    echo "$(basename $0): invalid region id -- $region" >&2
    exit 1
fi

# Query and get image info
cmd="aliyun ecs DescribeImages --RegionId $region --PageSize 100"
[ "$marketplace" = "true" ] && cmd="$cmd --ImageOwnerAlias marketplace"

for ((p = 1; p < 100; p++)); do
    x=$($cmd --PageNumber $p)
    if [ "$?" != "0" ]; then
        echo "$(basename $0): Failed to run Aliyun API." >&2
        exit 1
    fi
    image=$(echo $x | jq -r '.Images.Image[]')
    [ -z "$image" ] && break
    images="$images $image"
done

if [ "$all" = "true" ]; then
    id_list=$(echo $images | jq -r '.ImageId')
else
    # Platform is "Red Hat" only
    id_list=$(echo $images | jq -r 'select(.Platform=="Red Hat") | .ImageId')
fi

# Query image one-by-one and add data into a table
for id in $id_list; do
    block=$(echo $images | jq -r "select(.ImageId==\"$id\")")
    if [ "$?" != "0" ]; then
        echo "$(basename $0): Error while looking for the specific image -- $id" >&2
        exit 1
    fi

    name=$(echo $block | jq -r '.ImageName' | tr ' ' '_')
    id=$(echo $block | jq -r '.ImageId')
    ostype=$(echo $block | jq -r '.OSType')
    platform=$(echo $block | jq -r '.Platform' | tr ' ' '_')
    status=$(echo $block | jq -r '.Status')

    table="${table}$(printf '%s,%s,%s,%s,%s' $name $id $ostype $platform $status)\n"
done

# Show the table contents with format
echo -e $table | sort | sort -t , -k 4 |
    column -t -s , -N ImageName,ImageId,OSType,Platform,Status

exit 0
