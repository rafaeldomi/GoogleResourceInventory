#!/usr/bin/python3

# Get the Buckets and the size of them
#  - The size of the bucket can be read from 

# https://medium.com/google-cloud/fetching-monitoring-metrics-data-from-gcp-into-your-application-using-python-214358b0047e

# Get Google Cloud Storage
from google.cloud import monitoring_v3
import time
import csv
import sys

# Get the name of the project ($1)
projeto = sys.argv[1]

print("Utilizando projeto: ", projeto)

header=['bucket','size_bytes','size_readable']
fcsv = open('../outputs/gcs.csv', 'w')
writer = csv.writer(fcsv, delimiter=';')
writer.writerow(header)

def GetHumanReadable(size,precision=2):
    suffixes=['B','KB','MB','GB','TB']
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1 #increment the index of the suffix
        size = size/1024.0 #apply the division
    return "%.*f%s"%(precision,size,suffixes[suffixIndex])


client = monitoring_v3.MetricServiceClient()
project_id = projeto
project_name = f"projects/{project_id}"

interval = monitoring_v3.TimeInterval()
from datetime import datetime

start = datetime(2022, 6, 17, 0, 0,0,0)
start_seconds = start.strftime('%s')
start_seconds = int(start_seconds)
nanos = int((int(start_seconds) - start_seconds) * 10 ** 9)

#print(start.strftime('%B/%d/%Y %H:%M:%S'), start_seconds)
#print("Seconds: {} - Nanos: {}".format(start_seconds,nanos))

# 1 Day of interval
seconds_of_interval=86400

interval = monitoring_v3.TimeInterval(
    {
        "start_time": {"seconds": (start_seconds - seconds_of_interval), "nanos": nanos},
        "end_time": {"seconds": start_seconds, "nanos": nanos}
    }
)

results = client.list_time_series(
    request={
        "name": project_name,
        "filter": 'metric.type = "storage.googleapis.com/storage/total_bytes"',
        "interval": interval,
        "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
    }
)

for result in results:
    #print(result)

    bucket_name=result.resource.labels['bucket_name']

    print (" * ", bucket_name)

    # Get a data point

    for point in result.points:
        sizeb=point.value.double_value
        size = GetHumanReadable(sizeb)

        print(' -> {} - {}'.format(point.value.double_value, size))

        writer.writerow([bucket_name,sizeb,size])

        # Break mesmo, é só pra pegar o primeiro datapoint
        break
