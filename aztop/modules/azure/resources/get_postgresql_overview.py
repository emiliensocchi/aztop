import arm
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all PostgreSQL servers in an environment.

        Provides the following information for each PostgreSQL server:
            • Whether the PostgreSQL server is exposed to All networks or Selected networks
                - For Selected networks, IP ranges, VNet and subnet names are provided
            • Whether the PostgreSQL server is exposed to private endpoints (VNet, subnet names and private IP addresses are provided)
            • Whether SSL is enforced on the PostgreSQL server
            • The minimum TLS version required for HTTPS connections to the PostgreSQL Server

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
        self._resource_type = "Microsoft.DBforPostgreSQL"


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
        
        postgresql_server_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                single_postgresql_server_path = f"{self._resource_type}/servers"
                flexible_postgresql_server_path = f"{self._resource_type}/flexibleServers"
                single_postgresql_servers = arm.get_resources_of_type_within_subscription(self._access_token, subscription, single_postgresql_server_path)
                flexible_postgresql_servers = arm.get_resources_of_type_within_subscription(self._access_token, subscription, flexible_postgresql_server_path)
                postgresql_servers = single_postgresql_servers + flexible_postgresql_servers

                for postgresql_server in postgresql_servers:
                    spinner.next()
                    is_simple_server = False
                    postgresql_server_splitted_path = postgresql_server.rsplit('/', maxsplit = 3)
                    resource_provider = postgresql_server_splitted_path[1]
                    resource_type = postgresql_server_splitted_path[2]
                    resource_path = f"{resource_provider}/{resource_type}"
                    api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, resource_path)
                    postgresql_server_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, postgresql_server, api_versions, spinner)

                    if not postgresql_server_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of PostgreSQL server: {postgresql_server} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    if resource_type == 'servers':
                        is_simple_server = True

                    #-- Initializing variables
                    postgresql_server_properties = dict()
                    postgresql_server_network_exposure = dict()
                    postgresql_server_name = str()
                    postgresql_server_ssl_enforcement = str()
                    postgresql_server_minimum_tls_version = str()

                    #-- Gather general metadata
                    postgresql_server_name = postgresql_server_content['name']
                    postgresql_server_properties = postgresql_server_content['properties']


                    if is_simple_server:
                        #-- Gather SSL enforcement data
                        property_name = 'sslEnforcement'
                        postgresql_server_ssl_enforcement = postgresql_server_properties[property_name]

                        #-- Gather minimum TLS version data
                        property_name = 'minimalTlsVersion'
                        minimum_tls_version_raw = postgresql_server_properties[property_name]
                        version_raw = minimum_tls_version_raw.split('TLS')[1]
                        version = version_raw.replace('_', '.')
                        postgresql_server_minimum_tls_version = f"TLS {version}"
                    else:
                        # The PostgreSQL Server is flexible
                        postgresql_server_configuration_path = f"{postgresql_server}/configurations"
                        postgresql_server_configuration_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, postgresql_server_configuration_path, api_versions, spinner)

                        if not postgresql_server_configuration_content:
                            self._has_errors = True
                            error_text = f"Could not retrieve content of PostgreSQL server: {postgresql_server_configuration_path} ; API versions: {api_versions}"
                            utils.log_to_file(self._log_file_path, error_text)
                            continue

                        postgresql_server_configurations = postgresql_server_configuration_content['value']

                        is_minimum_tls_version_retrieved = False
                        is_ssl_enforcement_retrieved = False

                        for postgresql_server_configuration in postgresql_server_configurations:
                            #-- Gather SSL enforcement and minimum TLS version data
                            ssl_enforcement_configuration_name = 'require_secure_transport'
                            minminum_tls_configuration_name = 'ssl_min_protocol_version'
                            property_name = 'name'
                            configuration_name = postgresql_server_configuration[property_name]

                            if configuration_name == ssl_enforcement_configuration_name:
                                configuration_properties = postgresql_server_configuration['properties']
                                property_name = 'value'
                                postgresql_server_ssl_enforcement = 'Enabled' if configuration_properties[property_name] == 'on' else 'Disabled'
                                is_ssl_enforcement_retrieved = True

                            elif configuration_name == minminum_tls_configuration_name:
                                configuration_properties = postgresql_server_configuration['properties']
                                property_name = 'value'
                                minimum_tls_version_raw = configuration_properties[property_name]
                                version = minimum_tls_version_raw.split('TLSv')[1]
                                postgresql_server_minimum_tls_version = f"TLS {version}"
                                is_minimum_tls_version_retrieved = True

                            if is_minimum_tls_version_retrieved and is_ssl_enforcement_retrieved:
                                break

                    #-- Gather networking data
                    firewall_rules_path = '/firewallrules'
                    postgresql_server_firewall_rules_path = f"{postgresql_server}{firewall_rules_path}"
                    postgresql_server_firewall_rules_properties = arm.get_resource_content_using_multiple_api_versions(self._access_token, postgresql_server_firewall_rules_path, api_versions, spinner)

                    if not postgresql_server_firewall_rules_properties:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of Firewall rules for PostgreSQL Server: {postgresql_server_firewall_rules_path} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    postgresql_server_vnet_rules_properties = dict()

                    if is_simple_server:
                        vnet_rules_path = '/virtualNetworkRules'
                        postgresql_server_vnet_rules_path = f"{postgresql_server}{vnet_rules_path}"
                        postgresql_server_vnet_rules_properties = arm.get_resource_content_using_multiple_api_versions(self._access_token, postgresql_server_vnet_rules_path, api_versions, spinner)
                    else:
                        # The PostgreSQL Server is flexible
                        property_name = 'network'
                        postgresql_server_network_properties = postgresql_server_properties[property_name]
                        property_name = 'publicNetworkAccess'
                        postgresql_server_public_access = postgresql_server_network_properties[property_name].lower()
                        disabled_public_access_name = 'disabled'

                        if postgresql_server_public_access == disabled_public_access_name:
                            # Public access is disabled and VNet integration is enforced
                            property_name = 'delegatedSubnetResourceId'
                            postgresql_server_vnet_path = postgresql_server_network_properties[property_name]
                            postgresql_server_vnet_rules_properties = { 'value': [{ 'properties': { 'virtualNetworkSubnetId': postgresql_server_vnet_path }}] }
                        else:
                            # Public access is enabled and VNet integration cannot be used
                            postgresql_server_vnet_rules_properties = { 'value': [] }

                    if not postgresql_server_vnet_rules_properties:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of VNet rules for PostgreSQL Server: {postgresql_server_vnet_rules_path} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    postgresql_server_network_exposure = arm.get_database_server_network_exposure(self._access_token,subscription, postgresql_server_properties, postgresql_server_firewall_rules_properties, postgresql_server_vnet_rules_properties, spinner)

                    if postgresql_server_network_exposure == 'hidden':
                        # The resource attempted to be retrieved is managed by Microsoft
                        continue

                    if not postgresql_server_network_exposure:
                        self._has_errors = True
                        error_text = f"Could not retrieve network exposure for PostgreSQL Server with properties: {postgresql_server_properties}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Structure all the gathered data
                    postgresql_server_overview[postgresql_server_name] = { 
                        'network': postgresql_server_network_exposure, 
                        'sslenforcement': postgresql_server_ssl_enforcement,
                        'tlsversion' : postgresql_server_minimum_tls_version
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Allow access from'
        column_3 = 'SSL enforcement'
        column_4 = 'Minimum TLS version'
        column_names = [column_1, column_2, column_3, column_4]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, postgresql_server_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
