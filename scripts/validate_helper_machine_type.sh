#!/bin/bash

. var

OUTPUT=../outputs/helper_machine_types.csv
tmp=`mktemp`

sort $OUTPUT_HELPER_MT | uniq  > $tmp

# Iniciando nova lista
echo "Machine_type;zone;cpu;mem" > $OUTPUT

IFS=$'\n'
for i in `cat $tmp`; do
    echo "$i"
    IFS=";"
    aval=($i)
    unset IFS
    # $0 - machine_type
    # $1 - zone

    if [ ${aval[1]} == "" ]; then
        continue
    fi

    OUT=$(gcloud compute machine-types describe ${aval[0]} --zone ${aval[1]} --format=json)
    CPU=$(echo "$OUT" | jq -r ".guestCpus")
    MEM=$(echo "$OUT" | jq -r ".memoryMb")

    echo "${aval[0]};${aval[1]};$CPU;$MEM" >> $OUTPUT
done

rm -f $tmp