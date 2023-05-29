#!/bin/bash

# List the pubsub topics

OUTPUT=../outputs/pubsub.csv
> $OUTPUT

gcloud pubsub topics list --format "csv[separator=';'](name)" > $OUTPUT