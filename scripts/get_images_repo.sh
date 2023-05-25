#!/bin/bash

# List the Image Repository

OUTPUT=../outputs/images_repository.csv

gcloud container images list --format "csv[separator=';'](name)" > $OUTPUT