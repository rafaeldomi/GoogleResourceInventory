#!/bin/bash

# Get the virtual machines

. internal
. var

OUTPUT=../outputs/compute.csv

# Header of the svc file
echo "name;zone;type;preemptible;disksize_gb;SO;labels" > $OUTPUT

IFS=$'\n'
for C in $(gcloud compute instances list --format="csv[no-heading,separator=';	'](name, zone,machine_type,PREEMPTIBLE,labels.list())"); do
	# Split the variable using ; as separator
	IFS=';'
	res=($C)
	unset IFS
	# $0 - name
	# $1 - zone
	# $2 - machine_type
	# $3 - Preemptible
	# $4 - labels

	name="$(echo ${res[0]})"
	zone="$(echo ${res[1]})"
	machine_raw="$(echo ${res[2]})"
	preemptible="$(echo ${res[3]})"
	labels="$(echo ${res[4]})"

	log "Compute: $name"

	# If has a label noting that is a gke node continues the loop
	if [[ $labels =~ goog-gke-node ]]; then
		log "GKE Node. Next"
		continue
	fi

	# Logic to get the machine_type
	if [[ $machine_raw =~ http ]]; then
		# Remove the http prefix
		IFS="/"
		b=($machine_raw)
		size=${#b[@]}
		let size--
		machine=${b[size]}
		unset IFS
	else
		machine=$machine_raw
	fi

	# Set a default value if empty
	if [ "$preemptible" == "" ]; then
		preemptible="false"
	fi

	# Start with a default Linux OS
	OS="Linux"

	# Get the associate disk
	JOUT=$(gcloud compute instances describe $name --zone $zone --format=json)
	SIZE=$(echo "$JOUT" | jq '.disks | length')
	let SIZE--
	SIZE_TOTAL=0
	for i in `seq 0 $SIZE`; do
		VALUE=$(echo "$JOUT" | jq -r ".disks[$i].diskSizeGb")
		let SIZE_TOTAL=$SIZE_TOTAL+$VALUE

		# Loop to check the OS
		T=$(echo "$JOUT" | jq ".disks[$i].guestOsFeatures | length")
		let T--
		for p in `seq 0 $T`; do
			VALUE=$(echo "$JOUT" | jq -r ".disks[$i].guestOsFeatures[$T].type")
			if [[ "$VALUE" =~ WINDOWS ]]; then
				OS="Windows"
				# We dont need to worry with this loop anymore
				break
			fi
		done
	done

	# Generate machine type helper list
	# This list is just a helper that can be used later if needed
	# OUTPUT_HELPER_MT
	echo "$machine;$zone;get_compute.sh" >> $OUTPUT_HELPER_MT

	# Save to SCV file
	echo "$name;$zone;$machine;${preemptible};$SIZE_TOTAL;$OS;$labels" >> $OUTPUT
done