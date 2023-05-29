#!/bin/bash

# Paramters
# $1 - Project name
collect_project() {
    local PRJ="$1"

    echo "Project to collect resources data: $PRJ"

    # Variables point to folders as if they are inside this folder
    # So put manipulations beyond this point
    cd scripts

    SC=(get_compute.sh \
        get_functions.sh \
        get_gcs.py \
        get_gke.sh \
        get_gke_vpc.sh \
        get_sql.sh \
        get_images_repo.sh \
        get_pubsub.sh)

    # Clean helper file
    > $OUTPUT_HELPER_MT

    for script in ${SC[@]}; do
        if [ ! -f $script ]; then
            continue
        fi

        echo "Running $script"

        ./$script $PRJ > /dev/null
    done
}