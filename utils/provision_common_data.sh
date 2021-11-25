#!/bin/bash

# Description: Provision the common data for testing.
# Maintainer: Charles Shih <schrht@gmail.com>

function show_usage() {
	echo "Provision the common data for testing."
	echo "$(basename $0) [-h] [-f file] [-i access-key-id] \
[-s access-key-secret] [-k keypair] [-z az-id] [-m image-name] [-l label]"
	echo "Example:"
	echo "$(basename $0) -f ./alibaba_common.yaml"
	echo "$(basename $0) -z cn-beijing-g"
	echo "$(basename $0) -m RHEL-8.3.0-20200811.0"
}

while getopts :hf:i:s:k:z:m:l: ARGS; do
	case $ARGS in
	h)
		# Help
		show_usage
		exit 0
		;;
	f)
		# file
		file=$OPTARG
		;;
	i)
		# access-key-id
		access_key_id=$OPTARG
		;;
	s)
		# access-key-secret
		access_key_secret=$OPTARG
		;;
	k)
		# keypair
		keypair=$OPTARG
		;;
	z)
		# az-id
		az_id=$OPTARG
		;;
	m)
		# image-name
		image_name=$OPTARG
		;;
	l)
		# label
		label=$OPTARG
		;;
	"?")
		echo "$(basename $0): unknown option: $OPTARG" >&2
		echo "Try '$(basename $0) -h' for more information." >&2
		exit 1
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

# Parse params
codepath=$(dirname $(which $0))
source $codepath/cli_utils.sh

if [ -z $file ]; then
	echo "$(basename $0): '-f' was not specified, using default './alibaba_common.yaml'." >&2
	file=./alibaba_common.yaml
fi

if [ -z $access_key_id ] || [ -z $access_key_secret ]; then
	echo "$(basename $0): '-i' or '-s' was not specified, looking up the AliyunCLI credentials." >&2
	access_key_id=$(grep aliyun_access_key_id $HOME/.aliyuncli/credentials | sed 's/.*=\s*\(\w\)/\1/')
	access_key_secret=$(grep aliyun_access_key_secret $HOME/.aliyuncli/credentials | sed 's/.*=\s*\(\w\)/\1/')
fi

if [ -z $keypair ]; then
	echo "$(basename $0): '-k' was not specified, looking up from '$file'." >&2
	keypair=$(read_data $file VM.keypair)
fi

if [ -z $az_id ]; then
	echo "$(basename $0): '-z' was not specified, looking up from '$file'." >&2
	az_id=$(read_data $file VM.az)
fi

_is_az $az_id
if [ "$?" != "0" ]; then
	echo "$(basename $0): invalid az-id -- '$az_id'." >&2
	exit 1
fi

if [ -z $image_name ]; then
	echo "$(basename $0): '-m' was not specified, looking up from '$file'." >&2
	image_name=$(read_data $file Image.name)
fi

if [ -z $label ]; then
	echo "$(basename $0): '-l' was not specified, using random 'r$$'." >&2
	label=r$$
fi

# Get init data
vm_name=$(read_data $file VM.vm_name)
if [ -z "$vm_name" ]; then
	echo "$(basename $0): Cannot get VM Name from '$file', using value 'qeauto-instance-$label'." >&2
	vm_name=qeauto-instance-$label
fi

cloud_disk_name=$(read_data $file Disk.cloud_disk_name)
if [ -z "$cloud_disk_name" ]; then
	echo "$(basename $0): Cannot get Cloud Disk Name from '$file', using value 'qeauto-disk-$label'." >&2
	cloud_disk_name=qeauto-disk-$label
fi

nic_name=$(read_data $file NIC.nic_name)
if [ -z "$nic_name" ]; then
	echo "$(basename $0): Cannot get NIC Name from '$file', using default value 'qeauto-nic-$label'." >&2
	nic_name=qeauto-nic-$label
fi

# Get zone data
region_id=$(az_to_region $az_id)
vsw_id=$(az_to_vsw $az_id)
sg_id=$(az_to_sg $az_id)

[ -z "$region_id" ] && echo "$(basename $0): Failed to get the Region ID." >&2 && exit 1
[ -z "$vsw_id" ] && echo "$(basename $0): Failed to get the VSwitch ID." >&2 && exit 1
[ -z "$sg_id" ] && echo "$(basename $0): Failed to get the Security Group ID." >&2 && exit 1

# Get related data from the Image Name
if [ ! -z "$image_name" ]; then
	echo "$(basename $0): Getting Image ID for '$image_name' in the '$region_id' region." >&2
	image_id=$(image_name_to_id $image_name $region_id)
	if [ -z "$image_id" ]; then
		echo "$(basename $0): Cannot get the Image ID for $image_name in the region $region_id." >&2
		exit 1
	fi

	rehl_ver=$(echo $image_name | sed 's/.*[A-Za-z][._-]\([0-9]\)[._-]\([0-9]\)[._-].*/\1.\2/')

#	if [[ $image_name =~ ^RHEL- ]]; then
#		# For the BYOS images (named as "RHEL-X.Y")
#		image_user=cloud-user
#	else
#		image_user=root
#	fi
	image_user=root

	image_pass=$(read_data $file VM.password)
	if [ -z "$image_pass" ]; then
		echo "$(basename $0): Cannot get image password from '$file', using value 'RedHatQE@r$$'." >&2
		image_pass=RedHatQE@r$$
	fi
fi

# Get disk data
cloud_disk_count=$(read_data $file Disk.cloud_disk_count)
if [ -z "$cloud_disk_count" ]; then
	echo "$(basename $0): Cannot get Cloud Disk Count from '$file', using default value '16'." >&2
	cloud_disk_count=16
fi

cloud_disk_size=$(read_data $file Disk.cloud_disk_size)
if [ -z "$cloud_disk_size" ]; then
	echo "$(basename $0): Cannot get Cloud Disk Size from '$file', using default value '100'." >&2
	cloud_disk_size=100
fi

# Provision data
write_data $file Credential.access_key_id $access_key_id
write_data $file Credential.secretaccess_key $access_key_secret

write_data $file VM.keypair $keypair

write_data $file VM.vm_name $vm_name
write_data $file Disk.cloud_disk_name $cloud_disk_name
write_data $file NIC.nic_name $nic_name

write_data $file VM.az $az_id
write_data $file VM.region $region_id
write_data $file Network.VSwitch.id $vsw_id
write_data $file SecurityGroup.id $sg_id

if [ ! -z "$image_name" ]; then
	write_data $file Image.name $image_name
	write_data $file Image.id $image_id
	write_data $file VM.rhel_ver $rehl_ver
	write_data $file VM.username $image_user
	write_data $file VM.password $image_pass
fi

write_data $file Disk.cloud_disk_count $cloud_disk_count
write_data $file Disk.cloud_disk_size $cloud_disk_size

exit 0
