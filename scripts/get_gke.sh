#!/bin/bash

# Get the GKE clusters

. var
. internal

# The CSV File to output
OUTPUT="../outputs/gke.csv"

# Header of the csv file
echo "cluster;node_group;qtd;disk_size;machine_type" > $OUTPUT

IFS=$'\n'
for cluster in $(gcloud container clusters list --format "csv[no-heading,separator=';'](name,location,NODE_VERSION,status,locations[0])"); do
    IFS=';' read -r -a acluster <<< "$cluster"

	#readarray -td '' acluster < <(awk '{ gsub(/, /,"\0"); print; }' <<<"$cluster, ")
	#declare -p acluster
	# $0 = name
	# $1 = location
	# $2 = node_version
	# $3 = status
	# $4 = locations[0]

	log "Cluster: ${acluster[0]} - Region: ${acluster[1]}"
	JSON=$(gcloud container node-pools list --cluster=${acluster[0]} --region=${acluster[1]} --format=json)
	TOTALND=$(echo "$JSON" | jq '. | length')
	
	if [ $TOTALND == 0 ]; then
		log "Found 0 NodePool. Next"
		continue
	fi

	log "Found $TOTALND NodePools"

	let TOTALND--

	# For each nodepool we need:
	# - Total nodes
	# - Machine type
	# - Total GB
	for i in `seq 0 $TOTALND`; do
		ng_name=$(echo "$JSON"      | jq -r ".[$i].name")
		ng_disk_size=$(echo "$JSON" | jq -r ".[$i].config.diskSizeGb")
		ng_machine=$(echo "$JSON"   | jq -r ".[$i].config.machineType")

		# Find the autoscaling data
		autosc_enabled=$(echo "$JSON" | jq -r ".[$i].autoscaling.enabled")
		autosc_max=$(echo "$JSON" | jq -r ".[$i].autoscaling.maxNodeCount")
		autosc_min=$(echo "$JSON" | jq -r ".[$i].autoscaling.minNodeCount")

		ng_total=0
		# Search fo the instances names and get the storage size
		INSG=$(gcloud container node-pools describe $ng_name --cluster=${acluster[0]} --zone=${acluster[1]} --format=json | jq -r '.instanceGroupUrls')
		SIZE=$(echo "$INSG" | jq ". | length")

		let SIZE--
		for v in `seq 0 $SIZE`; do
			URL=$(echo "$INSG" | jq -r ".[$v]")

			GR=$(echo $URL | cut -d/ -f 11)
			ng_nd=$(gcloud compute instance-groups list --filter "name:$GR" --format=json | jq -r ".[].size" | awk '{sum=sum+$0} END{print sum}')
			let ng_total=$ng_total+$ng_nd
		done # Loop instance-groups inside node-pools

		log "Name: $ng_name - Total: $ng_total - SizeGb: $ng_disk_size - Machine: $ng_machine"
		echo "$ng_machine;${acluster[4]};get_gke.sh" >> $OUTPUT_HELPER_MT

		# "cluster;node_group;qtd;disk_size;machine_type"
		echo "${acluster[0]};${ng_name};${ng_total};${ng_disk_size};${ng_machine}" >> $OUTPUT
	done # Loop node-pools
done # Loop Cluster