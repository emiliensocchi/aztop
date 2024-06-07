import arm
import os
import utils
import requests
import progress.bar
import progress.spinner
import xmltodict


class Module():
    """
        Module providing an overview of all Storage Accounts in an environment.

        Provides the following information for each Storage Account:
            • Whether the Storage Account is exposed to All networks or Selected networks
                - For Selected networks, IP ranges, VNet and subnet names are provided
            • Whether the Storage Account is exposed to private endpoints (VNet, subnet names and private IP addresses are provided)
            • Whether secure transfer is required (HTTP/HTTPS)
            • The minimum TLS version required for HTTPS connections to the Storage Account
            • Which storage services the Storage Account currently uses (Blob, File, Queue, Table)
            • The determined purpose of the Storage Account (Cloud Shell, Logging, Static Web site)
            • If the Blob service is in use, provides the following information:
                - The containers present in the Blob service 
                - Whether containers and/or blobs are publicly exposed
                - Whether Blob versioning is enabled
                - Whether soft delete is enabled for containers and how long
                - Whether soft delete is enabled for individual blobs and how long
                - Whether immutability is enabled 
            • Which data-plane authorization model the Storage Account is using (Entra ID or Shared Access Signature - SAS) 

    """
    _output_file_path = str()
    _log_file_path = str()
    _has_errors = bool
    _resource_type = str()    
    _access_token = str()


    def __init__(self):
        module_path = os.path.realpath(__file__)
        module_name_with_extension = module_path.rsplit('/', maxsplit = 1)[1] if os.name == 'posix' else module_path.rsplit('\\', maxsplit = 1)[1]
        module_name = module_name_with_extension.split('.')[0]
        output_file_name = module_name
        self._output_file_path = utils.get_csv_file_path(output_file_name)
        self._log_file_path = utils.get_log_file_path()
        self._has_errors = False
        self._resource_type = "Microsoft.Storage/storageAccounts"


    def exec(self, access_token, subscription_ids):
        """
            Starts the module's execution.

            Args:
                access_token (str): a valid access token issued for the ARM API and tenant to analyze
                subscription_ids (str): comma-separated list of subscriptions to analyze or None

        """
        self._access_token = access_token

        if (self._access_token is None):
            print ('FATAL ERROR!')
            print ('Could not retrieve a valid access token. Set the token manually and retry')
            os._exit(0)
        
        storage_account_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                storage_accounts = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                # CHECK THE NUMBER OF STORAGE ACCOUNTS AND TAKE A SMALL SAMPLE IF MANY

                for storage_account in storage_accounts:
                    spinner.next()
                    storage_account_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, storage_account, api_versions, spinner)

                    if not storage_account_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of Storage Account: {storage_account} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue


                    #-- Initializing variables
                    storage_account_properties = dict()
                    storage_account_name = str()

                    #-- Gather general metadata
                    storage_account_name = storage_account_content['name']
                    storage_account_properties = storage_account_content['properties']

                    #-- Acquire SAS token to access Storage-Account content
                    sas_token_generation_path = '/listaccountsas'
                    storage_account_sas_token_generation_path = f"{storage_account}{sas_token_generation_path}"
                    sas_token = arm.generate_storageaccount_sas_token(self._access_token, storage_account_sas_token_generation_path, api_versions, spinner)

                    if not sas_token:
                        self._has_errors = True
                        error_text = f"Could not retrieve SAS token for Storage Account: {storage_account} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Enumerate the storage service(s) used by the Storage Account
                    # Gather Blob service data
                    blob_service_container_path = '/blobServices/default/containers'
                    storage_account_containers_path = f"{storage_account}{blob_service_container_path}"
                    resource_type = f"{self._resource_type}/blobServices"
                    api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, resource_type)
                    containers = arm.get_resource_content_using_multiple_api_versions(self._access_token, storage_account_containers_path, api_versions, spinner)

                    if containers:
                        # The Storage Account uses the Blob Service
                        containers = containers['value']

                        for container in containers:
                            container_name = container['name']
                            url = f"https://{storage_account_name}.blob.core.windows.net/{container_name}?restype=container&comp=list&{sas_token}"
                            response = requests.get(url)

                            # WHAT IF PUBLIC ACCESS IS DISABLED !?!?!?!?!?!?!!?!?!?!?!?!?!?!?!?!?!

                            if response.status_code == 200:
                                # The resource has been retrieved successfully
                                container_content = xmltodict.parse(response.content)

                                container_property_name = 'EnumerationResults'
                                container_enumeration_results = container_content[container_property_name]

                                container_property_name = 'Blobs'
                                container_blobs = container_enumeration_results[container_property_name]

                                container_property_name = 'Blob'
                                container_blobs = container_blobs[container_property_name]

                                for blob in container_blobs:
                                    blob_property_name = 'Properties'
                                    blob_properties = blob[blob_property_name]
                                    blob_property_name = 'Content-MD5'
                                    blob_md5_content = blob[blob_property_name]

                                    if blob_md5_content:
                                        # The blob is a file with actual content
                                        blob_property_name = 'Name'
                                        blob_name = blob[blob_property_name]
                                        url = f"https://{storage_account_name}.blob.core.windows.net/{container_name}/{blob_name}?restype=container&comp=list&{sas_token}"
                                        response = requests.get(url)

                                        # Retrieve Blob content
                                        # Check for secrets

                                        if response.status_code == 200:
                                            blob_raw_content = response.content



                            """
                            #-- Determine if the container and/or its blobs are public
                            container_property_name = 'allowBlobPublicAccess'
                            is_blob_public_access_enabled = storage_account_properties[container_property_name]
                            staticwebsite_container_name = '$web'
                            container_access_name = 'container'
                            blob_access_name = 'blob'

                            if is_blob_public_access_enabled:
                                if container_name == staticwebsite_container_name or container_public_access == container_access_name:
                                    # The container is publicly accessible (i.s. blobs are enumerable and publicly accessible)
                                    public_containers_and_blobs['containers'].append(container_name)

                                elif container_public_access == blob_access_name:
                                    # Blobs within the container are publicly accessible (not enumerable, but publicly accessible)
                                    public_containers_and_blobs['blobs'].append(container_name)

                                else:
                                    # Public access to the Storage Account's blob service is enabled, but all container and blobs have their public access level set to private
                                    storage_account_blob_service_public_access_level = 'Private'

                            elif container_name == staticwebsite_container_name:
                                # Public access to the Storage Account's blob service is disabled, but the the container is used to host a static website and is therefore public regardless of the public access setting
                                public_containers_and_blobs['containers'].append(container_name)

                            else:
                                # The Storage Account has no public access for the Blob Service
                                storage_account_blob_service_public_access_level = 'Private'

                            #-- Determine additional purpose of the Storage Account
                            # Determine if used for static website
                            is_purpose_staticwebsite = container_name == staticwebsite_container_name
                            """
                       

                    # Gather File service data
                    file_service_share_path = '/fileServices/default/shares'
                    storage_account_fileshares_path = f"{storage_account}{file_service_share_path}"
                    resource_type = f"{self._resource_type}/fileServices"
                    api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, resource_type)
                    fileshares = arm.get_resource_content_using_multiple_api_versions(self._access_token, storage_account_fileshares_path, api_versions, spinner)

                    if fileshares:
                        fileshares_keys = fileshares
                        content_key = 'value'
                        
                        if content_key in fileshares_keys and fileshares[content_key]:
                            # The Storage Account uses the File Service
                            #storage_account_service_type = 'File' if not storage_account_service_type else f"{storage_account_service_type}, File"
                            pass
 
                    # Gather Queue service data
                    queue_service_share_path = '/queueServices/default/queues'
                    storage_account_queues_path = f"{storage_account}{queue_service_share_path}"
                    resource_type = f"{self._resource_type}/queueServices"
                    api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, resource_type)
                    queues = arm.get_resource_content_using_multiple_api_versions(self._access_token, storage_account_queues_path, api_versions, spinner)

                    if queues:
                        queues_keys = queues
                        content_key = 'value'
                    
                        if content_key in queues_keys and queues[content_key]:
                            # The Storage Account uses the Queue Service
                            #storage_account_service_type = 'Queue' if not storage_account_service_type else f"{storage_account_service_type}, Queue"
                            pass

                    # Gather Table service data
                    table_service_share_path = '/tableServices/default/tables'
                    storage_account_tables_path = f"{storage_account}{table_service_share_path}"
                    resource_type = f"{self._resource_type}/tableServices"
                    api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, resource_type)
                    tables = arm.get_resource_content_using_multiple_api_versions(self._access_token, storage_account_tables_path, api_versions, spinner)

                    if tables:
                        tables_keys = tables
                        content_key = 'value'
                        
                        if content_key in tables_keys and tables[content_key]:
                            # The Storage Account uses the Table Service
                            #storage_account_service_type = 'Table' if not storage_account_service_type else f"{storage_account_service_type}, Table"
                            pass



                    #-- Structure all the gathered data
                    #storage_account_overview[storage_account_name] = { }

                bar.next()

        #-- Export data to CSV file
        column_1 = 'Name'
        column_2 = 'Allow access from'
        column_3 = 'Secure transfer'
        column_4 = 'Minimum TLS version'
        column_5 = 'Storage service in use'
        column_6 = 'Determined purpose'
        column_7 = 'Containers'
        column_8 = 'Public access level'
        column_9 = 'Blob versioning'
        column_10 = 'Container soft delete'
        column_11 = 'Blob soft delete'
        column_12 = 'Immutable'
        column_13 = 'Data-plane authorization'
        
        column_names = [column_1, column_2, column_3, column_4, column_5, column_6, column_7, column_8, column_9, column_10, column_11, column_12, column_13]

        utils.export_resource_overview_to_csv(self._output_file_path, column_names, storage_account_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
