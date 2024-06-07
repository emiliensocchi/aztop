import arm
import os
import utils
import re
import progress.bar
import progress.spinner


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
                    storage_account_network_exposure = dict()
                    storage_account_name = str()
                    storage_account_secure_transfer = str()
                    storage_account_minimum_tls_version = str()
                    storage_account_service_type = str()
                    storage_account_purpose = str()
                    storage_account_containers = str()
                    storage_account_blob_service_public_access_level = str()
                    storage_account_blob_versioning = str()
                    storage_account_container_soft_delete = str()
                    storage_account_blob_soft_delete = str()
                    storage_account_immutability = str()
                    storage_account_data_plane_authz_mode = str()

                    #-- Gather general metadata
                    storage_account_name = storage_account_content['name']
                    storage_account_properties = storage_account_content['properties']
                    storage_account_kind = storage_account_content['kind']
                    
                    #-- Gather secure transfer data
                    storage_account_propery_name = 'supportsHttpsTrafficOnly'
                    storage_account_secure_transfer = 'Enabled' if storage_account_properties[storage_account_propery_name] else 'Disabled'

                    #-- Gather minimum TLS version data
                    storage_account_propery_name = 'minimumTlsVersion'
                    minimum_tls_version_raw = storage_account_properties[storage_account_propery_name]
                    version_raw = minimum_tls_version_raw.split('TLS')[1]
                    version = version_raw.replace('_', '.')
                    storage_account_minimum_tls_version = f"TLS {version}"
            
                    #-- Determine the purpose of the Storage Account

                    # Determine if Cloud Shell
                    ms_cloudshell_tag = 'azure-cloud-shell'
                    storage_account_tags = list(storage_account_content['tags'].values())
                    storage_account_purpose = 'Cloud shell' if ms_cloudshell_tag in storage_account_tags else ''

                    # Determine if Logging
                    logging_in_name_pattern = re.compile('.*log.*')
                    is_purpose_logging = bool(logging_in_name_pattern.match(storage_account_name))
                    if is_purpose_logging:
                        storage_account_purpose = 'Logging' if not storage_account_purpose else f"{storage_account_purpose}, Logging"

                    #-- Enumerate the storage service(s) used by the Storage Account
                    storage_account_container_soft_delete = 'Disabled'
                    storage_account_blob_soft_delete = 'Disabled'
                    storage_account_immutability = 'Disabled'

                    # Gather Blob service data
                    blob_service_container_path = '/blobServices/default/containers'
                    storage_account_containers_path = f"{storage_account}{blob_service_container_path}"
                    resource_type = f"{self._resource_type}/blobServices"
                    api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, resource_type)
                    containers = arm.get_resource_content_using_multiple_api_versions(self._access_token, storage_account_containers_path, api_versions, spinner)

                    if containers:
                        # The Storage Account uses the Blob Service
                        all_containers = []
                        public_containers_and_blobs = { 'containers': [], 'blobs': [] }
                        is_purpose_staticwebsite = False

                        # Retrieving Blob Service properties
                        blob_service_path = '/blobServices/default'
                        storage_account_blob_service_path = f"{storage_account}{blob_service_path}"
                        storage_account_blob_service = arm.get_resource_content_using_multiple_api_versions(self._access_token, storage_account_blob_service_path, api_versions, spinner)

                        if not storage_account_blob_service:
                            self._has_errors = True
                            error_text = f"Could not retrieve content of Blob Service: {storage_account_blob_service_path} ; API versions: {api_versions}"
                            utils.log_to_file(self._log_file_path, error_text)
                            break

                        blob_service_properties = storage_account_blob_service['properties']

                        #-- Gather container soft delete data
                        container_soft_delete_property_name = 'containerDeleteRetentionPolicy'
                        is_container_soft_delete_enabled = False

                        if container_soft_delete_property_name in blob_service_properties:
                            container_soft_delete_properties = blob_service_properties[container_soft_delete_property_name]
                            container_soft_delete_property_name = 'enabled'
                            is_container_soft_delete_enabled = container_soft_delete_properties[container_soft_delete_property_name]

                        if is_container_soft_delete_enabled:
                            container_soft_delete_property_name = 'days'
                            container_retention_in_days = container_soft_delete_properties[container_soft_delete_property_name]
                            storage_account_container_soft_delete = f"{container_retention_in_days} days"

                        #-- Gather blob soft delete data
                        blob_soft_delete_property_name = 'deleteRetentionPolicy'
                        is_blob_soft_delete_enabled = False

                        if blob_soft_delete_property_name in blob_service_properties:
                            blob_soft_delete_properties = blob_service_properties[blob_soft_delete_property_name]
                            blob_soft_delete_property_name = 'enabled'
                            is_blob_soft_delete_enabled = blob_soft_delete_properties[blob_soft_delete_property_name]

                        if is_blob_soft_delete_enabled:
                            blob_soft_delete_property_name = 'days'
                            blob_retention_in_days = blob_soft_delete_properties[blob_soft_delete_property_name]
                            storage_account_blob_soft_delete = f"{blob_retention_in_days} days"

                        #-- Gather blob versioning data
                        blob_versioning_property_name = 'isVersioningEnabled'

                        if blob_versioning_property_name in blob_service_properties:
                            storage_account_blob_versioning = 'Enabled' if blob_service_properties[blob_versioning_property_name] else 'Disabled'
                        else:
                            storage_account_blob_versioning = 'Disabled'

                        #-- Gather immutability data
                        immutability_property_name = 'immutableStorageWithVersioning'

                        if immutability_property_name in storage_account_properties:
                            storage_account_immutability = 'Enabled' if immutability_property_name in storage_account_properties else 'Disabled'
                        else:
                            storage_account_immutability = 'Disabled'

                        #-- Gather default data-plane authorization data
                        storage_account_propery_name = 'allowSharedKeyAccess'

                        if storage_account_propery_name in storage_account_properties:
                            storage_account_data_plane_authz_mode = 'Shared Access Signatures (SAS)' if storage_account_properties[storage_account_propery_name] else 'Entra ID'
                        else:
                            storage_account_data_plane_authz_mode = 'Shared Access Signatures (SAS)'

                        #-- Enumerate publicly exposed containers and/or blobs
                        containers = containers['value']

                        for container in containers:
                            container_name = container['name']
                            container_properties = container['properties']          
                            container_public_access = container_properties['publicAccess'].lower()
                            all_containers.append(container_name)

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

                        #-- Convert the gathered container data to strings
                        storage_account_containers = ', '.join(all_containers)

                        if is_purpose_staticwebsite:
                            storage_account_purpose = 'Static website' if not storage_account_purpose else f"{storage_account_purpose}, Static website"

                        if public_containers_and_blobs['containers']:
                            # The Storage Account has containers with public access
                            storage_account_blob_service_public_access_level = f"Container: {', '.join(public_containers_and_blobs['containers'])}"
                        
                        if storage_account_blob_service_public_access_level:
                            # The Storage Account has containers with public access
                            if public_containers_and_blobs['blobs']:
                                # The Storage Account has both containers and blobs with public access
                                storage_account_blob_service_public_access_level = f"{storage_account_blob_service_public_access_level} ; Blob within: {', '.join(public_containers_and_blobs['blobs'])}"

                        elif public_containers_and_blobs['blobs']:
                            # The Storage Account has only blobs with public access (no containers)
                            storage_account_blob_service_public_access_level = f"Blob within: {', '.join(public_containers_and_blobs['blobs'])}"

                        #-- Set that the Storage Account uses the Blob Service at the end, to avoid errors when reporting to csv if storage_account_blob_service could not be retrieved
                        storage_account_service_type = 'Blob'

                    if not storage_account_kind == 'BlobStorage':
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
                                storage_account_service_type = 'File' if not storage_account_service_type else f"{storage_account_service_type}, File"
    
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
                                storage_account_service_type = 'Queue' if not storage_account_service_type else f"{storage_account_service_type}, Queue"

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
                                storage_account_service_type = 'Table' if not storage_account_service_type else f"{storage_account_service_type}, Table"

                    #-- Gather networking data
                    storage_account_network_exposure = arm.get_resource_network_exposure(self._access_token, subscription, storage_account_properties, spinner)

                    if storage_account_network_exposure == 'hidden':
                        # The resource attempted to be retrieved is managed by Microsoft
                        continue

                    if not storage_account_network_exposure:
                        self._has_errors = True
                        error_text = f"Could not retrieve network exposure for Storage Account with properties: {storage_account_properties}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Structure all the gathered data
                    storage_account_overview[storage_account_name] = { 
                        'network': storage_account_network_exposure, 
                        'securetransfer': storage_account_secure_transfer,
                        'tlsversion' : storage_account_minimum_tls_version,
                        'servicetype': storage_account_service_type,
                        'purpose': storage_account_purpose,
                        'containers': storage_account_containers,
                        'publicaccesslevel': storage_account_blob_service_public_access_level,
                        'blobversioning': storage_account_blob_versioning,
                        'containersoftdelete': storage_account_container_soft_delete,
                        'blobsoftdelete': storage_account_blob_soft_delete,
                        'immutability': storage_account_immutability,
                        'authorization': storage_account_data_plane_authz_mode
                    }

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
