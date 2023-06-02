#!/usr/bin/python3

# https://discovery.googleapis.com/discovery/v1/apis
# https://developers.google.com/discovery/v1/reference?hl=en

import argparse
import csv
import json
import os
import pandas as pd
import subprocess
import datetime
import warnings
from collections import defaultdict
from google.cloud import compute_v1
from googleapiclient import discovery
from google.cloud import monitoring_v3
from easydict import EasyDict

warnings.filterwarnings("ignore", "Your application has authenticated using end user credentials")

class Logger:
    level = 1  # Default log level

    @classmethod
    def set_level(cls, level):
        cls.level = level

    @classmethod
    def log(cls, level, message):
        if cls.level >= level:
            print(message)

def GetHumanReadable(size,precision=2):
    suffixes=['B','KB','MB','GB','TB']
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1 #increment the index of the suffix
        size = size/1024.0 #apply the division
    return "%.*f%s"%(precision,size,suffixes[suffixIndex])

def check_api_is_enabled(project_id, api):
    service = discovery.build('serviceusage', 'v1')
    request = service.services().get(
        name=f"projects/{project_id}/services/{api}.googleapis.com"
    )
    response = request.execute()

    return True if response.get('state') != "DISABLED" else False

def get_logged_in_project():
    result = subprocess.run(['gcloud', 'config', 'get-value', 'project'], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    else:
        raise RuntimeError(f"Failed to retrieve logged-in project: {result.stderr.strip()}")

def list_vm_instances(project_id):
    def get_vm_metrics(vm_name):
        # Set the time range for the metrics query (last month)
        end_time = datetime.datetime.utcnow()
        start_time = end_time - datetime.timedelta(days=30)

        interval = monitoring_v3.TimeInterval(
            {
                "start_time":{"seconds": int(start_time.timestamp())},
                "end_time":{"seconds": int(end_time.timestamp())}
            }
        )

        # Define the resource for the VM instance
        resource = f"projects/{project_id}/zones/{zone}/instances/{vm_name}"

        metric_filter=f'metric.type = "compute.googleapis.com/instance/cpu/utilization" AND resource.type="gce_instance" AND metric.label.instance_name="{vm_name}"'

        #print(metric_filter)

        # Prepare the request
        monitoring_client = monitoring_v3.MetricServiceClient()
        response = monitoring_client.list_time_series(
            request={
                "name": f'projects/{project_id}',
                "filter": metric_filter,
                "interval": interval,
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            }
        )

        # Extract the data points
        data_points = [point.value.double_value for series in response.time_series for point in series.points]

        # Store the metric values
        results = {}
        results['compute.googleapis.com/instance/cpu/utilization'] = data_points

        return results

    def calculate_average_usage(metric_data):
        # Calculate the average CPU and memory usage
        cpu_usage = metric_data['compute.googleapis.com/instance/cpu/utilization']
        avg_cpu_usage = sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0
        return avg_cpu_usage

    def calculate_p95_usage(metric_data):
        cpu_usage = metric_data['compute.googleapis.com/instance/cpu/utilization']
        p95_cpu_usage = sorted(cpu_usage)[int(len(cpu_usage) * 0.95)] if cpu_usage else 0
        return p95_cpu_usage

    # -----------
    # Start
    Logger.log (1, f"PRJ: {project_id} - Compute Machines")

    instances = []

    if not check_api_is_enabled(project_id,'compute'):
        Logger.log(2, "  | Compute API is not enabled")
        return instances

    compute_client = compute_v1.InstancesClient()
    machineClient = compute_v1.MachineTypesClient()

    request = compute_v1.AggregatedListInstancesRequest()
    request.project = project_id
    # Use the `max_results` parameter to limit the number of results that the API returns per response page.
    request.max_results = 50

    agg_list = compute_client.aggregated_list(request=request)

    #all_instances = defaultdict(list)
    for zone, response in agg_list:
        if response.instances:
            #all_instances[zone].extend(response.instances)
            Logger.log (2, f" |- Found {len(response.instances)} in zone {zone}")
            total=len(response.instances)
            i=0
            end='\r'

            for instance in response.instances:
                print(f'Reading: {i+1}/{total} Zone: {zone} Name: {instance.name}', end=f'{end}')
                i+=1
                if i==total:
                    print()

                # Get the metrics of the vm, to calculate avg and p95 cpu usage
                metric_data = get_vm_metrics(instance.name)
                avg_cpu_usage = calculate_average_usage(metric_data)
                p95_cpu_usage = calculate_p95_usage(metric_data)

                Logger.log (3, f"Avg: {avg_cpu_usage} - p95: {p95_cpu_usage}")

                parts=instance.machine_type.split('/')
                machine_type=parts[-1]

                # Get Size and Type of OS
                diskSize=0
                SO="NOT Win"
                for disk in instance.disks:
                    diskSize += disk.disk_size_gb
                    contains_windows = any("WINDOWS" in feature.type for feature in disk.guest_os_features)
                    if contains_windows:
                        SO="Windows"

                # Check for the goog-gke-node label
                IS_GKE=True if 'goog-gke-node' in instance.labels else False

                # Check if preemptible
                PREEMPTIBLE=False
                if 'scheduling' in instance:
                    PREEMPTIBLE=instance.scheduling.preemptible

                # Find the type of the machinetype
                machine=machineClient.get(
                        project=project_id,
                        zone=zone.split('/')[-1],
                        machine_type=machine_type
                    )

                instance_data = {
                    'project': project_id,
                    'name': instance.name,
                    'zone': zone.split('/')[-1],
                    'status': instance.status,
                    'machine_type': machine_type,
                    'Cpu': machine.guest_cpus,
                    'MemMb': machine.memory_mb,
                    'diskSizeGb': diskSize,
                    'SO': SO,
                    'IsGke': IS_GKE,
                    'Preemptible': PREEMPTIBLE,
                    'labels': instance.labels,
                    'cpu_avg': avg_cpu_usage,
                    'cpu_p95': p95_cpu_usage
                }
                instances.append(instance_data)

    return instances

def list_cloudsql_instances(project_id):
    Logger.log (1, f"PRJ: {project_id} - CloudSQL")

    # -----
    # https://stackoverflow.com/questions/69658130/how-can-i-get-list-of-all-cloud-sql-gcp-instances-which-are-stopped-in-pytho
    instances = []

    # Look for the instances in this project
    sql_client = discovery.build('sqladmin', 'v1beta4')
    raw_resp = sql_client.instances().list(project=project_id).execute()
    resp = EasyDict(raw_resp)

    if not 'items' in resp:
        return instances

    Logger.log(2, f' |- Found {len(resp.items)}')

    for inst in resp.items:
        #print(inst)
        # Search for the CPU metrics

        instance_data = {
            'project': project_id,
            'name': inst.name,
            'database_version': inst.databaseVersion
        }
        instances.append(instance_data)

    return instances

def list_functions(project_id):
    Logger.log (1, f"PRJ: {project_id} - Functions")

    functions = []

    if not check_api_is_enabled(project_id,'cloudfunctions'):
        Logger.log (2, "  | cloudfunctions API not enabled")
        return functions

    client = discovery.build('cloudfunctions', 'v1')
    # Note the use of - (dash) indicating all locations
    raw_resp = client.projects().locations().functions().list(
            parent=f"projects/{project_id}/locations/-"
        ).execute()
    resp = EasyDict(raw_resp)

    Logger.log(2, f' |- Found {len(resp.functions)}')

    for fnc in resp.functions:
        #print(f'|{fnc}|')
        parts = fnc.name.split('/')
        location_id = parts[3]
        function_name = parts[5]

        function_data = {
            'project': project_id,
            'location': location_id,
            'name': function_name,
            'status': fnc.status,
            'runtime': fnc.runtime,
            'availableMemoryMb': fnc.availableMemoryMb
        }
        functions.append(function_data)

    return functions

def list_gcs_buckets(project_id):
    def get_bucket_size():
        client = monitoring_v3.MetricServiceClient()

        # Set the time range for the metrics query (last month)
        end_time   = datetime.datetime.utcnow()
        start_time = end_time - datetime.timedelta(days=1)

        interval = monitoring_v3.TimeInterval(
            {
                "start_time":{"seconds": int(start_time.timestamp())},
                "end_time":{"seconds": int(end_time.timestamp())}
            }
        )

        results = client.list_time_series(
            request={
                "name": f'projects/{project_id}',
                "filter": 'metric.type = "storage.googleapis.com/storage/total_bytes"',
                "interval": interval,
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            }
        )

        #print(results)

        return results
    
    def get_metric_by_bucket(metrics, bucket_name):
        value=0
        for metric in metrics:
            bkt = metric.resource.labels['bucket_name']
            if bkt != bucket_name:
                continue

            if len(metric.points) > 0:
                value=metric.points[0].value.double_value
                break
        return value

    # ------
    # Start
    Logger.log (1, f"PRJ: {project_id} - GCS")

    buckets = []

    metrics_res = get_bucket_size()

    client = discovery.build('storage', 'v1')
    raw_resp = client.buckets().list(project=project_id).execute()
    resp = EasyDict(raw_resp)

    for bkt in resp.items:
        sizeb = get_metric_by_bucket(metrics_res, bkt.name)
        size = GetHumanReadable(sizeb)

        bucket_data = {
            'project': project_id,
            'name': bkt.name,
            'location': bkt.location,
            'storageClass': bkt.storageClass,
            'sizeb': sizeb,
            'size': size
        }
        buckets.append(bucket_data)

    return buckets

def list_gke_clusters(project_id):
    Logger.log (1, f"PRJ: {project_id} - GKE")

    clusters = []
    client = discovery.build('container', 'v1')
    # Note the use of dash (-) to get from all locations
    raw_resp = client.projects().locations().clusters().list(
            parent=f'projects/{project_id}/locations/-'
        ).execute()

    resp = EasyDict(raw_resp)

    if not 'clusters' in resp:
        return clusters

    Logger.log(2, f" |- Found {len(resp.clusters)} GKE clusters")

    for cluster in resp.clusters:
        #print(cluster)

        for np in cluster.nodePools:
            minNodeCount = 0
            maxNodeCount = 0
            initialNodeCount = 0
            if 'autoscaling' in np:
                if 'minNodeCount' in np.autoscaling:
                    minNodeCount = np.autoscaling.minNodeCount
                if 'maxNodeCount' in np.autoscaling:
                    maxNodeCount = np.autoscaling.maxNodeCount
            if 'initialNodeCount' in np:
                initialNodeCount = np.initialNodeCount

            cluster_data = {
                'project': project_id,
                'name': cluster.name,
                'location': cluster.location,
                'nodepool': np.name,
                'currentMasterVersion': cluster.currentMasterVersion,
                'status': cluster.status,
                'totalNodes': cluster.currentNodeCount,
                'machineType': np.config.machineType,
                'diskSizeGb': np.config.diskSizeGb,
                'preemptible': np.get('np.config.preemptible', False),
                'version': np.version,
                'minNodeCount': minNodeCount,
                'maxNodeCount': maxNodeCount,
                'initialNodeCount': initialNodeCount
            }
            clusters.append(cluster_data)

    return clusters

def list_artifact_registry_repos(project_id):
    # https://cloud.google.com/artifact-registry/docs/reference/rest/v1/projects.locations.repositories/list
    Logger.log (1, f"PRJ: {project_id} - Artifact Registry")

    repositories = []

    if not check_api_is_enabled(project_id,'artifactregistry'):
        Logger.log(2, "  | Artifact Registry API is not enabled")
        return repositories
    
    client = discovery.build('artifactregistry', 'v1')

    # get all locations
    raw_resp = client.projects().locations().list(
            name=f'projects/{project_id}'
        ).execute()
    resp_location = EasyDict(raw_resp)

    for location in resp_location.locations:
        Logger.log (3, f'  | Location: {location}')
    
        raw_resp = client.projects().locations().repositories().list(
            parent=f'projects/{project_id}/locations/{location.locationId}'
        ).execute()
        resp = EasyDict(raw_resp)

        # There is not repository in this location
        if not 'repositories' in resp:
            continue

        Logger.log(2, f' |- Found {len(resp.repositories)}')

        for rep in resp.repositories:
            print(rep)

            sizeB=0
            if 'sizeBytes' in rep:
                sizeB = rep.sizeBytes

            parts=rep.name.split('/')
            name=parts[-1]

            repository_data = {
                'project': project_id,
                'name': name,
                'location': location.locationId,
                'format': rep.format,
                'sizeBytes': sizeB
            }
            repositories.append(repository_data)

    return repositories

def list_pubsub_topics(project_id):
    Logger.log (1, f"PRJ: {project_id} - PubSub")

    topics = []

    client = discovery.build('pubsub', 'v1')
    raw_resp = client.projects().topics().list(
            project=f'projects/{project_id}'
        ).execute()
    resp = EasyDict(raw_resp)

    if not 'topics' in resp:
        return topics

    Logger.log (2, f' |- Found {len(resp.topics)}')

    for topic in resp.topics:
        parts = topic.name.split('/')
        topic_name = parts[3]

        topic_data = {
            'project': project_id,
            'name': topic_name,
        }
        topics.append(topic_data)

    return topics

def list_networks(project_id):
    Logger.log (1, f"PRJ: {project_id} - Networks")

    networks = {}
    networks['net'] = []
    networks['peer'] = []

    if not check_api_is_enabled(project_id,'compute'):
        Logger.log (2, "  | Compute API is not enabled")
        return networks
    
    client = discovery.build('compute', 'v1')
    raw_resp = client.networks().list(project=project_id).execute()
    vpc_resp = EasyDict(raw_resp)

    for vpc in vpc_resp.items:
        #print(vpc)
        network_data = {
            'project': project_id,
            'name': vpc.name
        }
        networks['net'].append(network_data)

        if 'peerings' in vpc:
            for peer in vpc.peerings:
                peer_data = {
                    'project': project_id,
                    'network': vpc.name,
                    'peer_network': peer.network
                }
                networks['peer'].append(peer_data)

    return networks

def save_to_json(data, resource_type, output_directory):
    if len(data) == 0:
        return

    output_path = os.path.join(output_directory, f"output_{resource_type}.json")
    with open(output_path, "w") as json_file:
        json.dump(data, json_file)

def save_to_csv(data, resource_type, output_directory):
    if len(data) == 0:
        #Logger.log(2, f'{resource_type} with no data')
        return

    output_path = os.path.join(output_directory, f"output_{resource_type}.csv")
    with open(output_path, 'w', newline='') as csvfile:
        # Write a line (commented) that has some metadata info about this file
        today = datetime.datetime.today()
        date=today.strftime('%d/%m/%y %H:%M:%S')
        csvfile.write(f'# Type: {resource_type} Date: {date}\n')

        # Dump the Dict variable
        writer = csv.DictWriter(csvfile, fieldnames=data[0].keys())
        # Write the header
        writer.writeheader()
        # Plot the data
        writer.writerows(data)

def save_to_xls(data, resource_type, writer):
    df = pd.DataFrame(data)
    df.to_excel(writer, sheet_name=resource_type, index=False)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--file', help='File with a list of GCP projects')
    parser.add_argument('-o', '--output', action='append', dest='output', choices=['csv', 'xls'], default=['csv'], help='Type of output (csv or xls) (can be used multiple times)')
    parser.add_argument('-l', '--log-level', choices=['1', '2', '3'], default='1', help='Log level (1: normal, 2: verbose, 3: debug)')
    parser.add_argument('-r', action='append', dest='options', default=[], help='Specify a resource (compute, sql, functions, gcs, gke, art_repo, pubsub) (can be used multiple times)')
    args = parser.parse_args()

    Logger.set_level (int(args.log_level))

    # Check if a file is provided, otherwise use the default project
    if args.file:
        with open(args.file, 'r') as file:
            projects = file.read().splitlines()
    else:
        # If no file is provided, use the current logged-in project
        projects = [get_logged_in_project()]
        Logger.log(2, f"Going to use the already logged-in project {projects}")

    # Create the variables that will be used further
    all_instances = []
    all_cloudsql = []
    all_functions = []
    all_gcs_buckets = []
    all_gke_clusters = []
    all_artifact_repos = []
    all_pubsub_topics = []  
    all_networks = {}
    all_networks['net'] = []
    all_networks['peer'] = []

    for project in projects:
        Logger.log(1, f"** Processing project: {project} **")

        # Network VPC and subnets
        if not args.options or 'network' in args.options:
            networks = list_networks(project)
            all_networks['net'].extend(networks['net'])
            all_networks['peer'].extend(networks['peer'])

        # Compute Machines
        if not args.options or 'compute' in args.options:
            instances = list_vm_instances(project)
            all_instances.extend(instances)
        
        # CloudSQL
        if not args.options or 'sql' in args.options:
            cloudsql = list_cloudsql_instances(project)
            all_cloudsql.extend(cloudsql)

        # Functions
        if not args.options or 'functions' in args.options:
            functions = list_functions(project)
            all_functions.extend(functions)

        # GCS Bucket
        if not args.options or 'gcs' in args.options:
            gcs_buckets = list_gcs_buckets(project)
            all_gcs_buckets.extend(gcs_buckets)

        # GKE Clusters
        if not args.options or 'gke' in args.options:
            gke_clusters = list_gke_clusters(project)
            all_gke_clusters.extend(gke_clusters)

        # Artifact Repository
        if not args.options or 'art_repo' in args.options:
            artifact_repos = list_artifact_registry_repos(project)
            all_artifact_repos.extend(artifact_repos)

        # PubSub
        if not args.options or 'pubsub' in args.options:
            pubsub_topics = list_pubsub_topics(project)
            all_pubsub_topics.extend(pubsub_topics)

    Logger.log(1, "Saving to output")
    output_directory = 'output'
    os.makedirs(output_directory, exist_ok=True)

    if 'csv' in args.output:
        Logger.log(1, " |- Saving to csv")

        save_to_csv(all_networks['net'], 'network', output_directory)
        save_to_csv(all_networks['peer'], 'network_peer', output_directory)
        save_to_csv(all_instances, 'compute', output_directory)
        save_to_csv(all_cloudsql, 'cloudsql', output_directory)
        save_to_csv(all_functions, 'functions', output_directory)
        save_to_csv(all_gcs_buckets, 'gcs', output_directory)
        save_to_csv(all_gke_clusters, 'gke', output_directory)
        save_to_csv(all_artifact_repos, 'artifact', output_directory)
        save_to_csv(all_pubsub_topics, 'pubsub', output_directory)
    if 'xls' in args.output:
        Logger.log(1, " |- Saving to xls")

        xls_path = os.path.join(output_directory, 'output.xlsx')
        with pd.ExcelWriter(xls_path) as writer:
            save_to_xls(all_networks['net'], 'network', writer)
            save_to_xls(all_networks['peer'], 'network_peer', writer)
            save_to_xls(all_instances, 'compute', writer)
            save_to_xls(all_cloudsql, 'cloudsql', writer)
            save_to_xls(all_functions, 'functions', writer)
            save_to_xls(all_gcs_buckets, 'gcs', writer)
            save_to_xls(all_gke_clusters, 'gke', writer)
            save_to_xls(all_artifact_repos, 'artifact', writer)
            save_to_xls(all_pubsub_topics, 'pubsub', writer)

    Logger.log(1, 'Finished')

if __name__ == '__main__':
    main()
