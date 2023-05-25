#!/bin/bash

# Get functions

. internal

# The cvs file
OUTPUT=../outputs/functions.csv

# Header of the csv file
echo "name;status;runtime" > $OUTPUT

IFS=$'\n'
for function in $(gcloud functions list --format "csv[no-heading,separator=';'](name,STATUS,REGION)"); do
    log "|$function|"
    IFS='; ' read -r -a afunction <<< "$function"
    # $0 - name

    log "Function: ${afunction[0]}"

    # Get runtime
    runtime=$(gcloud functions describe ${afunction[0]} --region ${afunction[2]} --format "(runtime)" | cut -d: -f2)

    # Save the csv row to the file
    echo "${afunction[0]};${afunction[1]};$runtime" >> $OUTPUT
done