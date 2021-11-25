#!/bin/bash

# Description: Provision the flavor data for testing.
# Maintainer: Charles Shih <schrht@gmail.com>

function show_usage() {
    echo -e "Usage: $0 <instance family or instance type> [YAML file]"
}

function json2yaml() {
    python -c 'import sys, yaml, json; print(yaml.dump(json.loads(sys.stdin.read())))'
}

if [ -z "$1" ]; then
    echo "Arg1: An instance family name or specific type name should be given."
    show_usage
    exit 1
fi

if [ -z "$2" ]; then
    echo "Arg2: YAML file is not spcified, using './alibaba_flavors.yaml'."
    file=./alibaba_flavors.yaml
else
    file=$2
fi

if [ ! -z "$(echo $1 | cut -d. -f3)" ]; then
    # instance type provisioned
    type_name=$1
    family_name=${1%.*}
    family_name=${family_name%-*}
else
    # instance family provisioned
    type_name=""
    family_name=$1
fi

echo -e "\nQuerying information for $family_name family..."

# get the json block for instance family
x=$(aliyun ecs DescribeInstanceTypes --InstanceTypeFamily $family_name)
[ $? = 0 ] || exit 1
family_block=$(echo $x | jq -r '.InstanceTypes.InstanceType[]')

# get instance type list
instance_types=$(echo $family_block | jq -r '.InstanceTypeId')

# prepare yaml file
yamlf=/tmp/alibaba_flavors.yaml.tmp$$
echo "Flavor: !mux" >$yamlf

# handle specified instance types
for instance_type in $instance_types; do
    if [ ! -z "$type_name" ] && [ "$type_name" != "$instance_type" ]; then
        # skip the mismatched ones for specified instance type
        continue
    fi

    # get the json block for instance type
    type_block=$(echo $family_block | jq -r ". | select( \
.InstanceTypeId==\"$instance_type\")")

    # gather information
    InstanceTypeId=$(echo $type_block | jq -r '.InstanceTypeId')
    CpuCoreCount=$(echo $type_block | jq -r '.CpuCoreCount')
    MemorySize=$(echo $type_block | jq -r '.MemorySize')
    EniQuantity=$(echo $type_block | jq -r '.EniQuantity')
    LocalStorageAmount=$(echo $type_block | jq -r '.LocalStorageAmount')
    LocalStorageCapacity=$(echo $type_block | jq -r '.LocalStorageCapacity')
    LocalStorageCategory=$(echo $type_block | jq -r '.LocalStorageCategory')

    # convert and dump to the yaml file
    echo >>$yamlf
    echo "    $InstanceTypeId:" >>$yamlf
    echo "        name: $InstanceTypeId" >>$yamlf
    echo "        cpu: $CpuCoreCount" >>$yamlf
    echo "        memory: $MemorySize" >>$yamlf

    echo "        nic_count: $EniQuantity" >>$yamlf

    if [ "$LocalStorageAmount" != "null" ]; then
        echo "        disk_count: $LocalStorageAmount" >>$yamlf
        echo "        disk_size: $LocalStorageCapacity" >>$yamlf
        if [ "$LocalStorageCategory" = "local_ssd_pro" ]; then
            echo "        disk_type: ssd" >>$yamlf
        else
            echo "Error: unknown LocalStorageCategory ($LocalStorageCategory)"
            exit 1
        fi
    fi
done

# move the yaml file
#mv $file $file.bak 2>/dev/null
mv $yamlf $file

exit 0
