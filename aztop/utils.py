"""
    Utility functions.

"""
import csv
import datetime
import json
import os
import requests
import time


ARM_BASEURL = 'https://management.azure.com'
GRAPH_BASEURL = 'https://graph.microsoft.com'


def get_log_file_path():
    """
        Builds a full directory path to a file with the .log extension and a name set to the current date and time.

        Returns:
            str: full path to the output file in the following format: /home/path/to/package/logs/yyyy-mm-dd_hh.mm.ss.log

    """
    root_package_path = os.path.dirname(os.path.realpath(__file__))
    output_dir_name = 'logs'
    date = datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S')
    output_file_extension = 'log'
    output_file_name = f"{date}.{output_file_extension}"
    result_file_full_path = os.path.join(root_package_path, output_dir_name, output_file_name)
    
    return result_file_full_path


def get_csv_file_path(file_name):
    """
        Builds a full directory path to a file with the passed name and the .csv extension.
        
        Args:
            file_name (str): name of the file to be used as a base for the csv file

        Returns:
            str: full path to the output file in the following format: /home/path/to/package/output/yyyy-mm-dd_<output_file_name>.csv

    """
    root_package_path = os.path.dirname(os.path.realpath(__file__))
    output_dir_name = 'output'
    date = datetime.datetime.now().strftime('%Y-%m-%d')
    output_file_extension = 'csv'
    output_file_name = f"{date}_{file_name}.{output_file_extension}"
    result_file_full_path = os.path.join(root_package_path, output_dir_name, output_file_name)
    
    return result_file_full_path


def log_to_file(file_path, text):
    """
        Writes the passed text to a file with the passed path.

        Args:
            file_path (str): full path to the file to log to
            text (str): string to be logged
        
        Returns:
            None

    """
    os.makedirs(os.path.dirname(file_path), exist_ok = True)

    with open(file_path, 'a+') as log_file:
        log_file.write(f"{text}\n")


def export_resource_overview_to_csv(output_file_path, column_names, resource_overview):
    """
        Exports the passed resource overview to the passed csv file, using the passed column names as column headers.

        Note:
            The passed resource overview has the following data structure for resources with a *standard network exposure*:
            {
                'resource-name-1':
                {
                    'network': { 'whitelisted': ['ip-1', 'ip-2'] },
                    'property-name-2': 'property-2',
                    'property-name-3': 'property-3'
                }, 
                'resource-name-2':
                {
                    'network': { 'whitelisted': ['ip-1', 'ip-2'] },
                    'property-name-2': 'property-2',
                    'property-name-3': 'property-3'
                },                 
                {...}
            }

        Note: 
            The passed resource overview has the following data structure for resources with a *simplified or no network exposure*:
            {
                'resource-name-1':
                {
                    'property-name-1': 'property-1',
                    'property-name-2': 'property-2',
                    'property-name-3': 'property-3'
                }, 
                'resource-name-2':
                {
                    'property-name-1': 'property-1',
                    'property-name-2': 'property-2',
                    'property-name-3': 'property-3'
                },                 
                {...}
            }
        Args:
            output_file_path (str): full directory path to the csv file where data should be be exported
            column_names (list(str)): list of column names to be used for column headers
            resource_overview (dict(dict(str, str))): resource overview to be exported

        Returns:
            None

    """
    os.makedirs(os.path.dirname(output_file_path), exist_ok = True)

    with open(output_file_path, 'w') as file:
        writer = csv.writer(file)
        writer.writerow(column_names)

        for resource_name, resource_properties in resource_overview.items():
            if 'network' in resource_properties:
                # Resource with a standard network exposure
                network_exposure = resource_properties.pop('network')
                whitelisted_locations = network_exposure['whitelisted']
                network_restriction_name = 'Selected networks' if whitelisted_locations else 'All networks' if network_exposure['ispublic'] else 'Private'
                resource_properties = list(resource_properties.values())
                resource_properties.insert(0, network_restriction_name)
                resource_properties.insert(0, resource_name)
                writer.writerow(resource_properties)

                whitelisted_location_row = [''] * len(resource_properties)

                for whitelisted_location in whitelisted_locations:
                    whitelisted_location_row[1] = whitelisted_location
                    writer.writerow(whitelisted_location_row)
            else:
                # Resource with a simplified or no network exposure
                resource_properties = list(resource_properties.values())
                resource_properties.insert(0, resource_name)
                writer.writerow(resource_properties)                


def get_all_subscriptions(access_token):
    """
        Retrieves the subscription Id of all subscriptions readable by the passed access token.

        Args:
            access_token (str):  a valid access token issued for the ARM API

        Returns:
            list(str): list of subscription Ids

    """
    api_version = 'api-version=2020-01-01'
    url = f"{ARM_BASEURL}/subscriptions?{api_version}"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers = headers)
    subscriptions = response.json()['value']

    if not subscriptions:
        # Create a mechanism to retry until working if this becomes an issue
        print ('DEBUG: Trying to get subscriptions returned NotAbleToCalculate')
        os._exit(0)         

    subscription_ids = []

    for subscription in subscriptions:
        subscription_id = subscription['subscriptionId']
        subscription_ids.append(subscription_id)

    return subscription_ids


def get_all_resources_within_subscription(access_token, subscription_id):
    """
        Retrieves the resource path of all resources within the passed subscription.

        Example of resource path: 
            /subscriptions/6c79977e-36f6-495f-a35a-898a76b720c7/resourceGroups/myRg/providers/Microsoft.Compute/virtualMachines/testVm-ubuntu-1

        Args:
            access_token (str):  a valid access token issued for the ARM API
            subscription_id (str): the Id of the subscription to retrieve resources for
        
        Returns:
            list(str): list of resource paths

    """
    api_version = 'api-version=2021-04-01'
    url = f"{ARM_BASEURL}/subscriptions/{subscription_id}/resources?{api_version}"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers = headers)
    resources = response.json()['value']
    resource_paths = []

    for resource in resources:
        resource_path = resource['id']
        resource_paths.append(resource_path)

    return resource_paths


def get_all_resources_of_type_within_subscription(access_token, subscription_id, resource_type):
    """
        Retrieves the resource path of all resources of the passed type within the passed subscription.

        Example of resource path: 
            /subscriptions/6c79977e-36f6-495f-a35a-898a76b720c7/resourceGroups/myRg/providers/Microsoft.Compute/virtualMachines/testVm-ubuntu-1

        Args:
            access_token (str):  a valid access token issued for the ARM API
            subscription_id (str): the Id of the subscription to retrieve resources for
            resource_type (str): the type of resource to retrieve in the Azure resource type format (e.g. 'Microsoft.KeyVault/vaults')
        
        Returns:
            list(str): list of resource paths
    """
    api_version = 'api-version=2021-04-01'
    filter = f"$filter=resourceType eq '{resource_type}'"
    url = f"{ARM_BASEURL}/subscriptions/{subscription_id}/resources?{filter}&{api_version}"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers = headers)
    response = response.json()
    error_key = 'error'
    error_code_key = 'code'
    error_code_values = ['InvalidSubscriptionId', 'SubscriptionNotFound']

    if error_key in response and response[error_key][error_code_key] in error_code_values:
        # The passed subscription is invalid (probably passed manually to aztop)
        print (f" [!] aztop has stopped! The passed subscription '{subscription_id}' is invalid")
        os._exit(0)        
    
    resources = response['value']
    resource_paths = []

    for resource in resources:
        resource_path = resource['id']
        resource_paths.append(resource_path)

    return resource_paths    


def get_all_resource_types_with_associated_api_versions_within_subscription(access_token, subscription_id):
    """
        Retrieves all resource types within the passed subscription with their associated API versions.

        Args:
            access_token (str):  a valid access token issued for the ARM API
            subscription_id (str): the Id of the subscription to retrieve resources types for
        
        Returns:
            dict(str, list(str)): dictionary mapping resource types (keys) to lists of API versions (values)

    """
    api_version = 'api-version=2017-05-10'
    url = f"{ARM_BASEURL}/subscriptions/{subscription_id}/providers?{api_version}"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers = headers)
    resource_providers = response.json()['value']
    resource_types_with_associated_api_versions = dict()

    for resource_provider in resource_providers:
        namespace = resource_provider['namespace']
        resource_types = resource_provider['resourceTypes']

        for resource_type in resource_types:
            short_resource_type = resource_type['resourceType']
            full_resource_type = (f"{namespace}/{short_resource_type}").lower()  # e.g. Microsoft.Storage/storageAccounts/encryptionScopes
            api_versions = resource_type['apiVersions']          
            resource_types_with_associated_api_versions[full_resource_type] = api_versions

    return resource_types_with_associated_api_versions


def get_api_version_for_resource_type(access_token, subscription_id, resource_type):
    """
        Retrieves the list of API versions valid for the passed resource type, located in the passed subscription.

        Note:
            In case no valid API version can be retrieved for the passed resource type, a fatal error is thrown and the script exits with code 0

        Args:
            access_token (str):  a valid access token issued for the ARM API
            subscription_id (str): the Id of the subscription where the resource type is located
            resource_type (str): the type of resource in the Azure resource type format to get API versions for (e.g. 'Microsoft.KeyVault/vaults')            

        Returns:
            list(str): list of api versions valid for the passed resource type
            None: if the passed resource type has no valid API versions

    """
    resource_provider, resource_type = resource_type.split('/', maxsplit = 1)
    api_version = 'api-version=2021-04-01'
    url = f"{ARM_BASEURL}/subscriptions/{subscription_id}/providers/{resource_provider}/resourceTypes?{api_version}"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers = headers)
    returned_resource_types = response.json()['value']
    api_versions = []
    
    for returned_resource_type in returned_resource_types:
        if returned_resource_type['resourceType'] == resource_type:
            api_versions = returned_resource_type['apiVersions']
            return api_versions

    print ('FATAL ERROR!')
    print (f"Could not retrieve a valid API version for the resource type: '{resource_type}' in subscription '{subscription_id}'")
    os._exit(0)


def get_resource_content_using_multiple_api_versions(access_token, resource_path, api_versions, spinner):
    """
        Attempts to retrieve the content of the resource with the passed resource path, using the passed API versions.

        Note:
            The spinner argument is used to update the user when throttling for the ARM API is occuring
            More info about throttling ARM requests: https://docs.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling

        Example of resource path: 
            /subscriptions/6c79977e-36f6-495f-a35a-898a76b720c7/resourceGroups/myRg/providers/Microsoft.Compute/virtualMachines/testVm-ubuntu-1

        Args:
            access_token (str):  a valid access token issued for the ARM API
            resource_path (str): full path identifying the resource to retrieve
            api_versions (list(str)): list of API versions compatible with the resource type of the resource to be retrieved
            spinner (progress.Spinner): reference to the spinner used to show progress to the user when iterating through multiple resources
    
        Returns:
            dict(): the resource's properties in json format
            None: if the content of the resource could not be retrieved or does not exis

    """
    default_throttling_error_response = 'toomanyrequests'
    default_unsupported_feature_substring = 'featurenotsupported'

    for api_version in api_versions:
        url = f"{ARM_BASEURL}{resource_path}?api-version={api_version}"
        headers = {'Authorization': f"Bearer {access_token}"}
        response = requests.get(url, headers = headers)        

        if response.status_code == 200:
            # The content of the resource has been retrieved successfully
            return response.json()

        error = json.loads(response.text)['error']
        error_code = error['code'].lower()

        if error_code == default_throttling_error_response:
            # Microsoft is throttling requests to the ARM API
            retry_header_name = 'Retry-After'
            seconds_to_sleep = int(response.headers[retry_header_name])

            # Wait until throttling is over, while updating the spinner continuously to inform the user
            original_message = spinner.message

            for i in range(seconds_to_sleep):
                remaining = seconds_to_sleep - i
                spinner.message = f"Throttled for {remaining}s. Be patient ... "
                spinner.update()
                time.sleep(1)
                spinner.next()

            # Reset the spinner's message to its original value
            spinner.message = original_message
            spinner.update()            

        elif default_unsupported_feature_substring in error_code:
            # The content requested is unsupported (applicable only to specific resources such as Storage Accounts)
            return None

    return None


def modify_resource_content_using_multiple_api_versions(access_token, resource_path, request_body, api_versions, spinner):
    """
        Modifies the content of the resource with the passed resource path and API version, using the passed request body.

        Example of resource path: 
            /subscriptions/6c79977e-36f6-495f-a35a-898a76b720c7/resourceGroups/myRg/providers/Microsoft.Compute/virtualMachines/testVm-ubuntu-1

        Args:
            access_token (str): a valid access token issued for the ARM API
            resource_path (str): full path identifying the resource to modify
            request_body (dict): the parameters specifying the changes to be requested in the resource
            api_version (str): an API version compatible with the resource type of the resource to be modified
            spinner (progress.Spinner): reference to the spinner used to show progress to the user when iterating through multiple resources
    
        Returns:
            dict(): the properties of the modified resource in json format
            None: if the resource could not be retrieved (e.g. due to an incompatible API version)

    """
    default_throttling_error_response = 'toomanyrequests'
    default_unsupported_feature_substring = 'featurenotsupported'

    for api_version in api_versions:
        url = f"{ARM_BASEURL}{resource_path}?api-version={api_version}"
        headers = {'Authorization': f"Bearer {access_token}"}
        body = request_body
        response = requests.post(url, headers = headers, json = body)

        if response.status_code == 200:
            # The resource has been modified successfully
            return response.json()

        error = json.loads(response.text)['error']
        error_code = error['code'].lower()

        if error_code == default_throttling_error_response:
            # Microsoft is throttling requests to the ARM API
            retry_header_name = 'Retry-After'
            seconds_to_sleep = int(response.headers[retry_header_name])

            # Wait until throttling is over, while updating the spinner continuously to inform the user
            original_message = spinner.message

            for i in range(seconds_to_sleep):
                remaining = seconds_to_sleep - i
                spinner.message = f"Throttled for {remaining}s. Be patient ... "
                spinner.update()
                time.sleep(1)
                spinner.next()

            # Reset the spinner's message to its original value
            spinner.message = original_message
            spinner.update()            

        elif default_unsupported_feature_substring in error_code:
            # The content requested is unsupported (applicable only to specific resources such as Storage Accounts)
            return None

    return None


def get_resource_content_using_single_api_version(access_token, resource_path, api_version):
    """
        Retrieves the content of the resource with the passed resource path and API version.

        Example of resource path: 
            /subscriptions/6c79977e-36f6-495f-a35a-898a76b720c7/resourceGroups/myRg/providers/Microsoft.Compute/virtualMachines/testVm-ubuntu-1

        Args:
            access_token (str):  a valid access token issued for the ARM API
            resource_path (str): full path identifying the resource to retrieve
            api_version (str):   an API version compatible with the resource type of the resource to be retrieved
    
        Returns:
            dict(): the resource's properties in json format
            None: if the resource could not be retrieved (e.g. due to an incompatible API version)

    """
    url = f"{ARM_BASEURL}{resource_path}?api-version={api_version}"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers = headers)

    if response.status_code == 200:
        return response.json()

    return None


def get_resource_network_exposure(access_token, subscription_id, resource_properties, spinner):
    """
        Determines the complete network exposure of a resource, based on its passed properties.
 
        Args:
            access_token (str):  a valid access token issued for the ARM API
            subscription_id (str): the Id of the subscription where the passed properties belong
            resource_properties (dict): the properties of the resource whose network exposure is to be determined
            spinner (progress.Spinner): reference to the spinner used to show progress to the user when iterating through multiple resources
    
        Returns:
            dict(str: list, str: bool): the network exposure of the resource
            None: in case the resource has private endpoints that fail to be retrieved

    """
    resource_network_exposure = { 'whitelisted': [], 'ispublic': True }

    if 'publicNetworkAccess' in resource_properties:
        # Note: App services with no network restrictions have their 'publicNetworkAccess' property set to None
        has_public_network_access = True if resource_properties['publicNetworkAccess'] is None else True if resource_properties['publicNetworkAccess'] == 'Enabled' else False

        if not has_public_network_access:
            # The resource is completely private
            resource_network_exposure['ispublic'] = False

    if resource_network_exposure['ispublic']:
        acl_options = ['networkRuleSet', 'networkAcls']
        network_acls = None

        for acl_option in acl_options:
            if acl_option in resource_properties:
                network_acls = resource_properties[acl_option]
                break

        if network_acls:
            # The resource is exposed on a public endpoint
            network_rules = []
            default_action = network_acls['defaultAction'].lower()

            if default_action == 'deny':
                # The resource's public endpoint is restricted
                resource_network_exposure['ispublic'] = False
                ip_rules = network_acls['ipRules']  # list of dicts

                if ip_rules:
                    # The resource's public endpoint is restricted to a list of selected public IPs
                    ip_rule_options = ['value', 'ipMask']

                    for ip_rule in ip_rules:
                        for ip_rule_option in ip_rule_options:
                            if ip_rule_option in ip_rule:
                                whitelisted_ip = ip_rule[ip_rule_option]
                                network_rules.append(whitelisted_ip)
                                break

                if 'virtualNetworkRules' in network_acls:
                    vnet_rules = network_acls['virtualNetworkRules']

                    if vnet_rules:
                        # The resource's public endpoint is restricted to a list of subnets located in VNets (i.e. exposed as public service endpoint(s))
                        for vnet_rule in vnet_rules:
                            vnet_rule_path_option = 'id'
                            vnet_rule_path = vnet_rule['id'].lower() if vnet_rule_path_option in vnet_rule else vnet_rule['subnet']['id'].lower()   # e.g. /subscriptions/<id>/resourcegroups/test-resource/providers/microsoft.network/virtualnetworks/testresource-vnet/subnets/testresource_subnet
                            # Extract vnet name
                            start_string = 'microsoft.network/virtualnetworks/'
                            start_index = vnet_rule_path.index(start_string) + len(start_string)
                            end_string = '/subnets/'
                            end_index = vnet_rule_path.index(end_string)
                            vnet_name = vnet_rule_path[start_index:end_index]
                            # Extract subnet name
                            start_string = '/subnets/'
                            start_index = vnet_rule_path.index(start_string) + len(start_string)
                            subnet_name = vnet_rule_path[start_index:]

                            network_rules.append(f"{vnet_name}/{subnet_name}")

                bypassing_azure_services = ''  # Comma separated string: 'AzureServices, Logging, Metrics' or 'None'

                if 'bypass' in network_acls:
                    # Typical for resources without explicit support for denying public access
                    bypassing_azure_services = network_acls['bypass']
                
                elif 'networkRuleBypassOptions' in resource_properties:
                    # Typical for resources with explicit support for denying public access
                    bypassing_azure_services = resource_properties['networkRuleBypassOptions']

                if bypassing_azure_services and bypassing_azure_services != 'None':
                    # Azure services are allowed to bypass all network restrictions
                    network_rules.append(bypassing_azure_services)

                resource_network_exposure['whitelisted'] = resource_network_exposure['whitelisted'] + network_rules

    if 'privateEndpointConnections' in resource_properties:
        # The resource is exposed on private endpoint(s)
        private_endpoint_rules = []
        private_endpoint_connections = resource_properties['privateEndpointConnections']
        resource_type = 'Microsoft.Network/privateEndpoints'
        api_versions = get_api_version_for_resource_type(access_token, subscription_id, resource_type)

        for private_endpoint_connection in private_endpoint_connections:
            private_endpoint_connection_properties = private_endpoint_connection['properties']
            private_endpoint_properties = private_endpoint_connection_properties['privateEndpoint']
            private_endpoint_resource_path = private_endpoint_properties['id']
            private_endpoint_content = get_resource_content_using_multiple_api_versions(access_token, private_endpoint_resource_path, api_versions, spinner)

            if not private_endpoint_content:
                return None

            private_endpoint_properties = private_endpoint_content['properties']
            subnet_path = private_endpoint_properties['subnet']['id'].lower()   # e.g. /subscriptions/<id>/resourcegroups/test-resource/providers/microsoft.network/virtualnetworks/testresource-vnet/subnets/testresource_subnet
            # Extract vnet name
            start_string = 'microsoft.network/virtualnetworks/'
            start_index = subnet_path.index(start_string) + len(start_string)
            end_string = '/subnets/'
            end_index = subnet_path.index(end_string)
            vnet_name = subnet_path[start_index:end_index]
            # Extract subnet name
            start_string = '/subnets/'
            start_index = subnet_path.index(start_string) + len(start_string)
            subnet_name = subnet_path[start_index:]
            # Extract IP address(es)
            private_endpoint_ip_addresses = []
            private_endpoint_dns_configs = private_endpoint_properties['customDnsConfigs']

            for dns_config in private_endpoint_dns_configs:
                private_endpoint_ip_addresses = private_endpoint_ip_addresses + dns_config['ipAddresses']

            if not private_endpoint_ip_addresses:
                # IP addresses could not be retrieved, trying another (more resource-demanding) method
                network_interfaces = private_endpoint_properties['networkInterfaces']
                resource_type = 'Microsoft.Network/networkInterfaces'
                api_versions = get_api_version_for_resource_type(access_token, subscription_id, resource_type)

                for network_interface in network_interfaces:
                    network_interface_path = network_interface['id']
                    network_interface_content = get_resource_content_using_multiple_api_versions(access_token, network_interface_path, api_versions, spinner)

                    if not network_interface_content:
                        return None

                    nic_properties = network_interface_content['properties']
                    nic_ip_configurations = nic_properties['ipConfigurations']

                    for nic_ip_configuration in nic_ip_configurations:
                        nic_ip_configuration_properties = nic_ip_configuration['properties']
                        nic_ip_address = nic_ip_configuration_properties['privateIPAddress']
                        private_endpoint_ip_addresses.append(nic_ip_address)

            private_endpoint_rules.append(f"{vnet_name}/{subnet_name} ({', '.join(private_endpoint_ip_addresses)})")

        resource_network_exposure['whitelisted'] = resource_network_exposure['whitelisted'] + private_endpoint_rules

    return resource_network_exposure


def get_database_server_network_exposure(access_token, subscription_id, resource_properties, firewall_properties, vnet_properties, spinner):
    """
        Determines the complete network exposure of a database server, based on its passed properties.
 
        Args:
            access_token (str):  a valid access token issued for the ARM API
            subscription_id (str): the Id of the subscription where the passed properties belong
            resource_properties (dict): the properties of the resource whose network exposure is to be determined
            firewall_properties (dict): the firewall properties of the resource whose network exposure is to be determined
            vnet_properties (dict): the VNet properties of the resource whose network exposure is to be determined
            spinner (progress.Spinner): reference to the spinner used to show progress to the user when iterating through multiple resources
    
        Returns:
            dict(str: list, str: bool): the network exposure of the resource
            None: in case the resource has private endpoints that fail to be retrieved

    """
    db_server_network_exposure = { 'whitelisted': [], 'ispublic': True }
    firewall_rules = firewall_properties['value']
    vnet_rules = vnet_properties['value']
    has_public_network_access = True

    if 'publicNetworkAccess' in resource_properties:
        has_public_network_access = True if resource_properties['publicNetworkAccess'] == 'Enabled' else False
   
    elif 'network' in resource_properties:
        public_network_access_properties = resource_properties['network']
        has_public_network_access = True if public_network_access_properties['publicNetworkAccess'] == 'Enabled' else False

    if not has_public_network_access:
        # The resource is completely private
        db_server_network_exposure['ispublic'] = False

    if db_server_network_exposure['ispublic']:
        for firewall_rule in firewall_rules:
            azure_backbone_ip = '0.0.0.0'
            firewall_rule_properties = firewall_rule['properties']
            rule_start_ip = firewall_rule_properties['startIpAddress']
            rule_end_ip = firewall_rule_properties['endIpAddress']

            if rule_start_ip == rule_end_ip == azure_backbone_ip:
                # The SQL Server is accessible from the Azure backbone
                azure_backbone_location_name = 'Azure backbone'

                if not azure_backbone_location_name in db_server_network_exposure['whitelisted']:
                    # Avoid populating with duplicate rules that are the same but have different names
                    db_server_network_exposure['whitelisted'].append(azure_backbone_location_name)
            else:
                # The SQL Server is accessible from whitelisted public IPs
                if rule_start_ip == rule_end_ip:
                    db_server_network_exposure['whitelisted'].append(rule_start_ip)
                else:
                    ip_range = f"{rule_start_ip} - {rule_end_ip}"
                    db_server_network_exposure['whitelisted'].append(ip_range)

        if vnet_rules:
            # The SQL Server is exposed on service endpoint(s)
            for vnet_rule in vnet_rules:
                vnet_properties = vnet_rule['properties']
                vnet_rule_path = vnet_properties['virtualNetworkSubnetId'].lower()     # e.g. /subscriptions/<id>/resourcegroups/test-resource/providers/microsoft.network/virtualnetworks/testresource-vnet/subnets/testresource_subnet
                # Extract vnet name
                start_string = 'microsoft.network/virtualnetworks/'
                start_index = vnet_rule_path.index(start_string) + len(start_string)
                end_string = '/subnets/'
                end_index = vnet_rule_path.index(end_string)
                vnet_name = vnet_rule_path[start_index:end_index]
                # Extract subnet name
                start_string = '/subnets/'
                start_index = vnet_rule_path.index(start_string) + len(start_string)
                subnet_name = vnet_rule_path[start_index:]

                db_server_network_exposure['whitelisted'].append(f"{vnet_name}/{subnet_name}")

    #-- Private endpoints
    if 'privateEndpointConnections' in resource_properties:
        # The SQL Server is exposed on private endpoint(s)
        private_endpoint_rules = []
        private_endpoint_connections = resource_properties['privateEndpointConnections']
        resource_type = 'Microsoft.Network/privateEndpoints'
        api_versions = get_api_version_for_resource_type(access_token, subscription_id, resource_type)

        for private_endpoint_connection in private_endpoint_connections:
            private_endpoint_connection_properties = private_endpoint_connection['properties']
            private_endpoint_properties = private_endpoint_connection_properties['privateEndpoint']
            private_endpoint_resource_path = private_endpoint_properties['id']
            private_endpoint_content = get_resource_content_using_multiple_api_versions(access_token, private_endpoint_resource_path, api_versions, spinner)

            if not private_endpoint_content:
                return None

            private_endpoint_properties = private_endpoint_content['properties']
            subnet_path = private_endpoint_properties['subnet']['id'].lower()   # e.g. /subscriptions/<id>/resourcegroups/test-resource/providers/microsoft.network/virtualnetworks/testresource-vnet/subnets/testresource_subnet
            # Extract vnet name
            start_string = 'microsoft.network/virtualnetworks/'
            start_index = subnet_path.index(start_string) + len(start_string)
            end_string = '/subnets/'
            end_index = subnet_path.index(end_string)
            vnet_name = subnet_path[start_index:end_index]
            # Extract subnet name
            start_string = '/subnets/'
            start_index = subnet_path.index(start_string) + len(start_string)
            subnet_name = subnet_path[start_index:]
            # Extract IP address(es)
            private_endpoint_ip_addresses = []
            private_endpoint_dns_configs = private_endpoint_properties['customDnsConfigs']

            for dns_config in private_endpoint_dns_configs:
                private_endpoint_ip_addresses = private_endpoint_ip_addresses + dns_config['ipAddresses']

            if not private_endpoint_ip_addresses:
                # IP addresses could not be retrieved, trying another (more resource-demanding) method
                network_interfaces = private_endpoint_properties['networkInterfaces']
                resource_type = 'Microsoft.Network/networkInterfaces'
                api_versions = get_api_version_for_resource_type(access_token, subscription_id, resource_type)

                for network_interface in network_interfaces:
                    network_interface_path = network_interface['id']
                    network_interface_content = get_resource_content_using_multiple_api_versions(access_token, network_interface_path, api_versions, spinner)

                    if not network_interface_content:
                        return None

                    nic_properties = network_interface_content['properties']
                    nic_ip_configurations = nic_properties['ipConfigurations']

                    for nic_ip_configuration in nic_ip_configurations:
                        nic_ip_configuration_properties = nic_ip_configuration['properties']
                        nic_ip_address = nic_ip_configuration_properties['privateIPAddress']
                        private_endpoint_ip_addresses.append(nic_ip_address)

            private_endpoint_rules.append(f"{vnet_name}/{subnet_name} ({', '.join(private_endpoint_ip_addresses)})")

        db_server_network_exposure['whitelisted'] = db_server_network_exposure['whitelisted'] + private_endpoint_rules

    return db_server_network_exposure
