import arm
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all Redis databases in an environment.

        Provides the following information for each Redis database:
            • Whether the Redis database is exposed to All networks or Selected networks
                - For Selected networks, IP ranges, VNet and subnet names are provided
            • Whether the Redis database is exposed to private endpoints (VNet, subnet names and private IP addresses are provided)
            • Whether the non-SSL port for the Redis database is enabled
            • The minimum TLS version required for HTTPS connections to the Redis database

        Note:
            By default, a Redis database is exposed to the public Internet. 
            However, exposing a database on a private endpoint automatically sets its publicNetworkAccess flag to Disabled, denying all traffic from public networks.
            Note that this is note clearly visible in the portal!
            More info: https://docs.microsoft.com/en-us/azure/azure-cache-for-redis/cache-network-isolation#advantages-of-private-link

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
        self._resource_type = "Microsoft.Cache/Redis"


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
        
        redis_database_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                redis_databases = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for redis_database in redis_databases:
                    spinner.next()
                    redis_database_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, redis_database, api_versions, spinner)

                    if not redis_database_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of Redis database: {redis_database} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables
                    redis_database_properties = dict()
                    redis_database_network_exposure = dict()
                    redis_database_name = str()
                    redis_database_ssl_port_status = str()
                    redis_database_minimum_tls_version = str()

                    #-- Gather general metadata
                    redis_database_name = redis_database_content['name']
                    redis_database_properties = redis_database_content['properties']

                    #-- Gather non-SSL port data
                    property_name = 'enableNonSslPort'
                    redis_database_ssl_port_status = 'Enabled' if redis_database_properties[property_name] else 'Disabled'

                    #-- Gather minimum TLS version data 
                    property_name = 'minimumTlsVersion'
                    redis_database_minimum_tls_version = 'TLS 1.0 (unset)' if (not property_name in redis_database_properties) else f"TLS {redis_database_properties[property_name]}"

                    #-- Gather networking data
                    redis_database_network_exposure = arm.get_resource_network_exposure(self._access_token, subscription, redis_database_properties, spinner)

                    if redis_database_network_exposure == 'hidden':
                        # The resource attempted to be retrieved is managed by Microsoft
                        continue

                    if not redis_database_network_exposure:
                        self._has_errors = True
                        error_text = f"Could not retrieve network exposure for Redis database with properties: {redis_database_properties}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Structure all the gathered data
                    redis_database_overview[redis_database_name] = { 
                        'network': redis_database_network_exposure, 
                        'nonsslport': redis_database_ssl_port_status,
                        'minimumtlsversion' : redis_database_minimum_tls_version
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Allow access from'
        column_3 = 'Non-SSL port (6379)'
        column_4 = 'Minimum TLS version for SSL port (6380)'
        column_names = [column_1, column_2, column_3, column_4]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, redis_database_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
