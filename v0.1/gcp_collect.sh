#!/bin/bash

. var.inc
. functions.inc
. const.inc
. collect.inc

help() {
    echo "$PROGRAM_NAME"
    echo "Version: $VERSION"
    echo ""
    echo "Options:"
    echo "  -? | -h     Show this help"
    echo "  -p [file]   A file that contains a list of gcp projects"
    echo ""
    echo "This is NOT a official Google product"
    echo ""

    finish 0
}

work() {
    if [ ! -z PROJECT_FILE && ! -f $PROJECT_FILE ]; then
        echo "File $PROJECT_FILE not found"
        finish 1
    fi

    do_prereq

    if [ ! -z PROJECT_FILE ]; then
        for prj in $(cat $PROJECT_FILE); do
            PROJECT="$prj"

            # [ collect.inc ]
            collect_project $PROJECT
        done
    else
        # [ collect.inc ]
        PROJECT=$(gcloud config get-value project)
        collect_project $PROJECT
    fi 
}

main() {
    # Check parameters options
    while getopts "?hp:" arg; do
      case $arg in
        \?|h) help
              ;;
        p) declare -g PROJECT_FILE
           PROJECT_FILE="${OPTARG}"
           ;;
        *) echo "Parameter $arg not recognized. Exiting"
           finish 1
           ;;
      esac
    done

    # Lets do the work
    work
}

main "$@"