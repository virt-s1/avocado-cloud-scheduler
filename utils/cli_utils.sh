function _is_az() {
	[[ "$1" = *-*-*[a-z] ]] && return 0 || return 1
}

function _is_region() {
	[[ "$1" = *-* ]] && return 0 || return 1
}

function _is_image_id() {
	[[ "$1" = m-* ]] && return 0 || return 1
}

function az_to_region() {
	# Get Region ID by Zone ID
	_is_az "$1" || return 1
	# get region
	if [[ $1 = *[0-9][a-z] ]]; then
		# "us-west-1a" to "us-west-1"
		echo "${1%%[a-z]}"
		return 0
	fi
	if [[ $1 = *-[a-z] ]]; then
		# "cn-beijing-b" to "cn-beijing"
		echo "${1%%-[a-z]}"
		return 0
	fi
	return 1
}

function az_to_vsw() {
	# Get default VSwitch ID by Zone ID
	_is_az "$1" || return 1
	x=$(aliyun ecs DescribeVSwitches --IsDefault true \
		--RegionId $(az_to_region "$1") --ZoneId "$1")
	[ $? = 0 ] || return 1
	echo $x | jq -r '.VSwitches.VSwitch[0].VSwitchId'
}

function az_to_vpc() {
	# Get default VPC ID by Zone ID
	_is_az "$1" || return 1
	x=$(aliyun ecs DescribeVSwitches --IsDefault true \
		--RegionId $(az_to_region "$1") --ZoneId "$1")
	[ $? = 0 ] || return 1
	echo $x | jq -r '.VSwitches.VSwitch[0].VpcId'
}

function az_to_sg() {
	# Get default VPC's Security Group ID by Zone ID
	_is_az "$1" || return 1
	x=$(aliyun ecs DescribeSecurityGroups --RegionId $(az_to_region "$1") \
		--VpcId $(az_to_vpc "$1"))
	[ $? = 0 ] || return 1
	echo $x | jq -r '.SecurityGroups.SecurityGroup[0].SecurityGroupId'
}

function image_id_to_name() {
	# Get image name by image ID
	# Help: $0 <image-id> <region>
	_is_image_id "$1" || return 1
	_is_region "$2" || return 1
	x=$(aliyun ecs DescribeImages --RegionId $2 --ImageId $1)
	[ $? = 0 ] || return 1
	echo $x | jq -r '.Images.Image[].ImageName'
}

function image_name_to_id() {
	# Get image id by image name
	# Help: $0 <image-name> <region>
	_is_region "$2" || return 1
	x=$(aliyun ecs DescribeImages --RegionId $2 --ImageName $1)
	[ $? = 0 ] || return 1
	echo $x | jq -r '.Images.Image[].ImageId'
}

function read_data() {
	# Read specified data from a yaml file
	# Usage: $0 <file> <keypath>
	[ "$#" != "2" ] && return 1
	file=$1
	keypath=$2
	pos=1
	for key in $(echo $keypath | tr '.' ' '); do
		base=$pos
		pos=$(sed -n "$pos,\$p" $file | grep "^\s*$key:" -n -m 1 | cut -d: -f1)
		[ -z "$pos" ] && return 1
		pos=$(($base + $pos - 1))
	done

	sed -n "${pos}p" $file | sed 's/.*:\s*\(\S*\)/\1/' || return 1

	return 0
}

function write_data() {
	# Write specified data from a yaml file
	# Usage: $0 <file> <keypath> <value>
	[ "$#" != "3" ] && return 1
	file=$1
	keypath=$2
	value=$3
	pos=1
	for key in $(echo $keypath | tr '.' ' '); do
		base=$pos
		pos=$(sed -n "$pos,\$p" $file | grep "^\s*$key:" -n -m 1 | cut -d: -f1)
		[ -z "$pos" ] && return 1
		pos=$(($base + $pos - 1))
	done

	sed -i "${pos}s/\(.*:\).*/\1 $value/" $file || return 1

	return 0
}
