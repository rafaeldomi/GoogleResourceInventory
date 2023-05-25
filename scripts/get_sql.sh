#!/bin/bash

# List the cloudSQL Instances

OUTPUT=../outputs/sql.csv

gcloud sql instances list \
  --format "csv[separator=';'](name,DATABASE_VERSION,LOCATION,TIER,STATUS,settings.dataDiskSizeGb,settings.availabilityType)" > $OUTPUT