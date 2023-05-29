#!/bin/bash

# List the PVs from GKE

. internal

# The csv file output
OUTPUT=../outputs/gke_pvc.csv

# Header of the csv
echo "name;sizeGb;inuse" > $OUTPUT

# Get all disks
J_DISKS=$(gcloud compute disks list --format=json)
SZ_DISKS=$(echo "$J_DISKS" | jq '. | length')

let SZ_DISKS--

for i in `seq 0 $SZ_DISKS`; do
    NAME=$(echo "$J_DISKS" | jq -r ".[$i].name")
    GKE=$(echo "$J_DISKS" | jq -r ".[$i].labels | has(\"goog-gke-volume\")")
    DISKGB=$(echo "$J_DISKS" | jq -r ".[$i].sizeGb")
    USED=$(echo "$J_DISKS" | jq -r ".[$i].users | length")

    log "* $NAME"

    if [ $GKE == false ]; then
        log  "Not a GKE disk. Next"
        continue
    fi

    echo "${NAME};${DISKGB};$USED" >> $OUTPUT
done