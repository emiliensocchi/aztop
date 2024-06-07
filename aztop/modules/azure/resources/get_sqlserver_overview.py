import arm
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all SQL Servers in an environment.

        Provides the following information for each SQL Server:
            • Whether the SQL Server is accessible from the Azure backbone
            • Whether the SQL Server is accessible from selected networks (IP ranges, VNet and subnet names are provided)
            • Whether the SQL Server is exposed to private endpoints (VNet, subnet names and private IP addresses are provided)
            • The minimum TLS version required for HTTPS connections to the SQL Server
            • Which data-plane authorization model the SQL Server is using (Entra ID or SQL credentials)

        Note:
            • The retrieval of network data is implemented manually here, due to the externalization of firewall and VNet data
            • By default, public IPs allowed to connect to a SQL server need to be specified explicitly, even though "Deny Public Network Access" is set to "No"
              More info: https://techcommunity.microsoft.com/t5/azure-database-support-blog/lesson-learned-126-deny-public-network-access-allow-azure/ba-p/1244037

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
        self._resource_type = "Microsoft.Sql/servers"


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
        
        sql_server_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                sql_servers = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for sql_server in sql_servers:
                    spinner.next()
                    sql_server_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, sql_server, api_versions, spinner)

                    if not sql_server_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of SQL Server: {sql_server} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables
                    sql_server_properties = dict()
                    sql_server_network_exposure = dict()
                    sql_server_name = str()
                    sql_server_minimum_tls_version = str()
                    sql_server_data_plane_authz_mode = str()

                    #-- Gather general metadata
                    sql_server_name = sql_server_content['name']
                    sql_server_properties = sql_server_content['properties']

                    #-- Gather minimum TLS version data
                    sql_server_property_name = 'minimalTlsVersion'

                    if sql_server_property_name in sql_server_properties:
                        sql_server_minimum_tls_version = f"TLS {sql_server_properties[sql_server_property_name]}"
                    else:
                        # The minimal TLS version is unset. Default is to allow all versions
                        sql_server_minimum_tls_version = 'TLS 1.0'

                    #-- Gather data-plane authorization data
                    sql_server_property_name = 'administrators'

                    if sql_server_property_name in sql_server_properties:
                        sql_server_admin_properties = sql_server_properties[sql_server_property_name]
                        sql_server_property_name = 'azureADOnlyAuthentication'
                        sql_server_data_plane_authz_mode = 'Entra ID' if (sql_server_property_name in sql_server_admin_properties and sql_server_admin_properties[sql_server_property_name]) else 'SQL credentials'
                    else:
                        sql_server_data_plane_authz_mode = 'SQL credentials'

                    #-- Gather networking data
                    firewall_rules_path = '/firewallrules'
                    sql_server_firewall_rules_path = f"{sql_server}{firewall_rules_path}"
                    sql_server_firewall_rules_properties = arm.get_resource_content_using_multiple_api_versions(self._access_token, sql_server_firewall_rules_path, api_versions, spinner)

                    if not sql_server_firewall_rules_properties:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of Firewall rules for SQL Server: {sql_server_firewall_rules_path} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    vnet_rules_path = '/virtualNetworkRules'
                    sql_server_vnet_rules_path = f"{sql_server}{vnet_rules_path}"
                    sql_server_vnet_rules_properties = arm.get_resource_content_using_multiple_api_versions(self._access_token, sql_server_vnet_rules_path, api_versions, spinner)

                    if not sql_server_vnet_rules_properties:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of VNet rules for SQL Server: {sql_server_vnet_rules_path} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue
                    
                    sql_server_network_exposure = arm.get_database_server_network_exposure(self._access_token,subscription, sql_server_properties, sql_server_firewall_rules_properties, sql_server_vnet_rules_properties, spinner)

                    if sql_server_network_exposure == 'hidden':
                        # The resource attempted to be retrieved is managed by Microsoft
                        continue

                    if not sql_server_network_exposure:
                        self._has_errors = True
                        error_text = f"Could not retrieve network exposure for SQL Server with properties: {sql_server_properties}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Structure all the gathered data
                    sql_server_overview[sql_server_name] = { 
                        'network': sql_server_network_exposure, 
                        'tlsversion': sql_server_minimum_tls_version,
                        'authorization' : sql_server_data_plane_authz_mode
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Allow access from'
        column_3 = 'Minimum TLS Version'
        column_4 = 'Data-plane authorization'
        column_names = [column_1, column_2, column_3, column_4]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, sql_server_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
