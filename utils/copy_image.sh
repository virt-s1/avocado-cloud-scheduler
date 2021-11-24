#!/bin/bash

# Description: Copy image to the other region.
# Maintainer: Charles Shih <schrht@gmail.com>

function show_usage() {
    echo "Copy image to the other region."
    echo "$(basename $0) [-h] <-r from-region> <-R to-region> \
<-i from-image-id | -n from-image-name> [-N to-image-name] [-q]"
    echo "Note: '-i' will overwrite '-n' if both provided."
}

while getopts :hr:R:i:n:N:q ARGS; do
    case $ARGS in
    h)
        # Help option
        show_usage
        exit 0
        ;;
    r)
        # from-region
        region=$OPTARG
        ;;
    R)
        # to-region
        to_region=$OPTARG
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

if [ -z $region ] || [ -z $to_region ]; then
    show_usage
    exit 1
fi

if [ -z $image_id ] && [ -z $image_name ]; then
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

_is_region $to_region
if [ "$?" != "0" ]; then
    echo "$(basename $0): invalid region id -- $to_region" >&2
    exit 1
fi

if [ -z $image_id ]; then
    image_id=$(image_name_to_id $image_name $region)
    if [ -z $image_id ]; then
        echo "$(basename $0): no image named \"$image_name\" in region \"$region\"." >&2
        exit 1
    fi
fi

_is_image_id $image_id
if [ "$?" != "0" ]; then
    echo "$(basename $0): invalid image id -- $image_id" >&2
    exit 1
fi

if [ -z $to_image_name ]; then
    to_image_name=$(image_id_to_name $image_id $region)
fi

description="Copied from image $image_id in the $region region by $(basename $0)."

# Confirm
if [ "$quiet" != "true" ]; then
    echo "Please confirm the following information."
    echo "FROM-REGION          : $region"
    echo "TO-REGION            : $to_region"
    echo "FROM-IMAGE-ID        : $image_id"
    echo "FROM-IMAGE-NAME      : $image_name"
    echo "TO-IMAGE-NAME        : $to_image_name"
    echo "TO-IMAGE-DESCRIPTION : $description"
    read -p "Do you want to process the image copy [Y/n]? " answer
    echo
    if [ "$answer" = "N" ] || [ "$answer" = "n" ]; then
        echo "Cancelled."
        exit 0
    fi
fi

# Copy
x=$(aliyun ecs CopyImage --RegionId $region --ImageId $image_id \
    --DestinationRegionId $to_region --DestinationImageName $to_image_name \
    --DestinationDescription "$description")
if [ "$?" != "0" ]; then
    echo $x
    echo "$(basename $0): Failed to run Aliyun API." >&2
    exit 1
else
    echo $x
    to_image_id=$(echo $x | jq -r '.ImageId')
fi

# Helper
if [ "$quiet" != "true" ]; then
    echo ""
    echo "What's Next?"
    echo "* Cancel the copy process:"
    echo "$ aliyun ecs CancelCopyImage --RegionId $to_region --ImageId $to_image_id"
    echo "* Check status of the image:"
    echo "$ aliyun ecs DescribeImages --RegionId $to_region --ImageId $to_image_id"
fi

exit 0
