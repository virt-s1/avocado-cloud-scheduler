#!/bin/bash

# Description: Rename image in a specified region.
# Maintainer: Charles Shih <schrht@gmail.com>

function show_usage() {
    echo "Rename image in a specified region."
    echo "$(basename $0) [-h] <-r region> <-i from-image-id | \
-n from-image-name> [-N to-image-name] [-q]"
    echo "Note: '-i' will overwrite '-n' if both provided."
}

while getopts :hr:i:n:N:q ARGS; do
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
    i)
        # from-image-id
        image_id=$OPTARG
        ;;
    n)
        # from-image-name
        image_name=$OPTARG
        ;;
    N)
        # to-image-name
        to_image_name=$OPTARG
        ;;
    q)
        # quiet
        quiet=true
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

if [ -z "$image_id" ] && [ -z "$image_name" ]; then
    show_usage
    exit 1
fi

if [ -z "$to_image_name" ]; then
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

if [ -z "$image_id" ]; then
    image_id=$(image_name_to_id $image_name $region)
    if [ -z "$image_id" ]; then
        echo "$(basename $0): no image named \"$image_name\" in region \"$region\"." >&2
        exit 1
    fi
fi

_is_image_id $image_id
if [ "$?" != "0" ]; then
    echo "$(basename $0): invalid image id -- $image_id" >&2
    exit 1
fi

if [ -z "$image_name" ]; then
    image_name=$(image_id_to_name $image_id $region)
    if [ -z "$image_name" ]; then
        echo "$(basename $0): no image associated with id \"$image_id\" in region \"$region\"." >&2
        exit 1
    fi
fi

# Confirm
if [ "$quiet" != "true" ]; then
    echo "Please confirm the following information."
    echo "REGION          : $region"
    echo "FROM-IMAGE-ID   : $image_id"
    echo "FROM-IMAGE-NAME : $image_name"
    echo "TO-IMAGE-NAME   : $to_image_name"
    read -p "Do you want to process the image copy [Y/n]? " answer
    echo
    if [ "$answer" = "N" ] || [ "$answer" = "n" ]; then
        echo "Cancelled."
        exit 0
    fi
fi

# Copy
x=$(aliyun ecs ModifyImageAttribute --RegionId $region --ImageId $image_id \
    --ImageName $to_image_name)
if [ "$?" != "0" ]; then
    echo $x
    echo "$(basename $0): Failed to run Aliyun API." >&2
    exit 1
else
    echo $x
fi

# Helper
if [ "$quiet" != "true" ]; then
    echo ""
    echo "What's Next?"
    echo "* Check status of the image:"
    echo "$ aliyun ecs DescribeImages --RegionId $region --ImageId $image_id"
    echo "$ aliyun ecs DescribeImages --RegionId $region --ImageName $to_image_name"
fi

exit 0
