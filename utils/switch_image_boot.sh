#!/bin/bash

# Description: Switch image boot mode.
# Maintainer: Charles Shih <schrht@gmail.com>

function show_usage() {
    echo "Switch image boot mode."
    echo "$(basename $0) [-h] <-r region> <-n image-name> <-m boot-mode> "
    echo "Note: 'boot-mode' can be either BIOS or UEFI."
}

while getopts :hr:n:m: ARGS; do
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
    n)
        # image-name
        image_name=$OPTARG
        ;;
    m)
        # boot-mode
        boot_mode=$OPTARG
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

if [ -z $region ] || [ -z $image_name ] || [ -z $boot_mode ]; then
    show_usage
    exit 1
fi

if [ $boot_mode != BIOS ] && [ $boot_mode != UEFI ]; then
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

# Get image ID
image_id=$(image_name_to_id $image_name $region)
if [ -z $image_id ]; then
    echo "$(basename $0): no image named \"$image_name\" in region \"$region\"." >&2
    exit 1
fi

_is_image_id $image_id
if [ "$?" != "0" ]; then
    echo "$(basename $0): invalid image id -- $image_id" >&2
    exit 1
fi

# Modify image attribute
echo "In region \"$region\", switching image \"$image_name\" boot mode to \"$boot_mode\"."
x=$(aliyun ecs ModifyImageAttribute --RegionId $region --ImageId $image_id --BootMode $boot_mode)
if [ "$?" != "0" ]; then
    echo $x
    echo "$(basename $0): Failed to run Aliyun API." >&2
    exit 1
else
    echo $x
    exit 0
fi
