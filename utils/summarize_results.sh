#!/bin/bash

# Description:
#   This script summarize the test results for avocodo-cloud.
# Limiation:
#   Only 1 flavor can be tested each time the avocodo-cloud runs.

function collect_results() {
	fdir=$1
	fres=$fdir/results.json
	flog=$fdir/job.log

	if [ ! -f $fres ] || [ ! -f $flog ]; then
		echo "The necessary files are missing, skip the analysis of '$fdir'." >&2
		SKIPPED="$fdir $SKIPPED"
		return
	fi

	res_t=$(cat $fres | jq -r '.total')
	res_p=$(cat $fres | jq -r '.pass')
	res_c=$(cat $fres | jq -r '.cancel')
	res_e=$(cat $fres | jq -r '.errors')
	res_f=$(cat $fres | jq -r '.failures')
	res_s=$(cat $fres | jq -r '.skip')
	logid=$(cat $fres | jq -r '.debuglog' | sed 's#.*\(job-20.*\)/job.log#\1#')

	flavor=$(grep -m 1 'key=name.*path=.*Flavor.*=>' $flog | cut -d "'" -f 2)
	azone=$(grep -m 1 'key=az.*path=.*VM.*=>' $flog | cut -d "'" -f 2)
	imgname=$(grep -m 1 'key=name.*path=.*Image.*=>' $flog | cut -d "'" -f 2)
	imgid=$(grep -m 1 'key=id.*path=.*Image.*=>' $flog | cut -d "'" -f 2)

	table="${table}$(printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' $logid $flavor $azone $imgname $imgid $res_t $res_p $res_f $res_e $res_c $res_s)\n"
}

# Parse parameters
if [ -z $1 ]; then
	echo "Usage: $(basename $0) <dirs>" >&2
	echo "Notes:" >&2
	echo "  - dirs: avocado-cloud log dirs starts with 'job-'." >&2
	exit 1
fi

dlist="$@"

# Collect results for each avocado-cloud run
unset SKIPPED
for d in $dlist; do
	collect_results $d
done

# Show skipped tests if there is
[ ! -z "$SKIPPED" ] && echo -e "\nSkipped:\n$SKIPPED\n" >&2

# Show the summary as a table
echo -e $table | column -t -s ',' -R 6,7,8,9,10,11 -N LogID,Flavor,AZone,ImageName,ImageID,TOTAL,PASS,FAIL,ERROR,CANCEL,SKIP

exit 0
