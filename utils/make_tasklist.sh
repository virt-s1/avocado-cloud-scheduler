#!/bin/bash

# Description: Make tasklist file for the scheduler.
# Maintainer: Charles Shih <schrht@gmail.com>

function show_usage() {
	echo "Make tasklist file for the scheduler." >&2
	echo "$(basename $0) [-h] [-o output-file] <-f list-of-flavors>" >&2
}

while getopts :ho:f: ARGS; do
	case $ARGS in
	h)
		# Help option
		show_usage
		exit 0
		;;
	o)
		# output-file
		file=$OPTARG
		;;
	f)
		# list-of-flavors
		flavors=$OPTARG
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

[ -z "${file}" ] && file="./tasklist.toml"
[ -z "${flavors}" ] && show_usage && exit 1

# Main

: >$file
for flavor in $flavors; do
	echo "['$flavor']" >>$file
done

exit 0
