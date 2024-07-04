import arm
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all App Services in an environment.

        Provides the following information for each App Service:
            • Whether the App Service is exposed to All networks or Selected networks
                - For Selected networks, IP ranges, VNet and subnet names are provided
            • Whether the App Service is exposed to private endpoints (VNet, subnet names and private IP addresses are provided)
            • Whether the App Service is a Function App or an App Service
            • Whether the App Service has FTP and/or FTPS enabled
            • Whether HTTPS is enforced on the App Service
            • The minimum TLS version required for HTTPS connections to the App Service

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
        self._resource_type = "Microsoft.Web/sites"


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
        
        app_service_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                app_services = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for app_service in app_services:
                    spinner.next()  
                    app_service_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, app_service, api_versions, spinner)

                    if not app_service_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of App Service: {app_service} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables
                    app_service_properties = dict()
                    app_service_config_properties = dict()
                    app_service_network_exposure = dict()
                    app_service_name = str()
                    app_service_type = str()
                    app_service_https_only = str()
                    app_service_minimum_tls_version = str()
                    app_service_ftp_state = str()

                    #-- Gather general metadata
                    app_service_name = app_service_content['name']
                    app_service_type = 'Function App ' if 'functionapp' in app_service_content['kind'] else 'App Service'

                    #-- Gather HTTPS only data
                    property_name = 'properties'
                    app_service_properties = app_service_content[property_name]
                    property_name = 'httpsOnly'
                    app_service_https_only = 'Yes' if app_service_properties[property_name] else 'No'

                    #-- Gather hostname data
                    property_name = 'defaultHostName'
                    app_service_hostname = f"https://{app_service_properties[property_name]}"

                    #-- Acquire App Service configuration
                    app_service_config_path = f"{app_service}/config"
                    app_service_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, app_service_config_path, api_versions, spinner)

                    if not app_service_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of App Service: {app_service} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    app_service_content = app_service_content['value'][0]
                    app_service_config_properties = app_service_content['properties']

                    #-- Gather minimum TLS version data
                    property_name = 'minTlsVersion'
                    minimum_tls_version = app_service_config_properties[property_name] 
                    app_service_minimum_tls_version = f"TLS {minimum_tls_version}"

                    #-- Gather FTP state data
                    property_name = 'ftpsState'
                    state = app_service_config_properties[property_name].lower()
                    app_service_ftp_state = 'FTP, FTPS' if state == 'allallowed' else 'FTPS' if state == 'ftpsonly' else 'Disabled' 

                    #-- Gather networking data
                    network_acls = { 'networkAcls': dict() }
                    network_acls['defaultAction'] = 'Allow'

                    # Service endpoint (i.e. subnet within VNet)
                    property_name = 'virtualNetworkSubnetId'
                    app_service_vnet_path = app_service_properties[property_name] 

                    if app_service_vnet_path:
                        # The App Service uses VNet integration and is exposed as a service endpoint
                        network_acls['virtualNetworkRules'] = [ { 'id': app_service_properties.pop(property_name) } ]
                    else:
                        # The App Service does not use VNet integration
                        network_acls['virtualNetworkRules'] = []

                    # Whitelisted public IP(s)
                    ip_rules = list()
                    is_network_restricted = False
                    property_name = 'ipSecurityRestrictions'
                    ip_restrictions = app_service_config_properties[property_name]

                    for ip_restriction in ip_restrictions:
                        if not 'ipAddress' in ip_restriction:
                            continue

                        default_deny_action_name = 'deny'
                        default_any_ip_address = 'any'
                        action = ip_restriction['action'].lower()
                        src_ip_address = ip_restriction['ipAddress'].lower()

                        if (action == default_deny_action_name and src_ip_address == default_any_ip_address):
                            network_acls['defaultAction'] = 'Deny'
                            is_network_restricted = True
                            break

                    if is_network_restricted:
                        # The App Service is only reachable from whitelisted public IPs
                        for ip_restriction in ip_restrictions:
                            if not 'ipAddress' in ip_restriction:
                                continue

                            default_deny_action_name = 'deny'
                            action = ip_restriction['action'].lower()
                            src_ip_address = ip_restriction['ipAddress']

                            if action == default_deny_action_name:
                                continue

                            ip_rules.append({ 'value': src_ip_address })
                        
                        network_acls['ipRules'] = ip_rules
                    else:
                        # The App Service is reachable from the Internet
                        network_acls['ipRules'] = []

                    app_service_properties['networkAcls'] = network_acls
                    app_service_network_exposure = arm.get_resource_network_exposure(self._access_token, subscription, app_service_properties, spinner)

                    if app_service_network_exposure == 'hidden':
                        # The resource attempted to be retrieved is managed by Microsoft
                        continue

                    elif not app_service_network_exposure:
                        self._has_errors = True
                        error_text = f"Could not retrieve network exposure for App Service with properties: {app_service_properties}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Structure all the gathered data
                    app_service_overview[app_service_name] = { 
                        'network': app_service_network_exposure,
                        'type': app_service_type,
                        'ftpstate': app_service_ftp_state, 
                        'httpsonly': app_service_https_only,
                        'tlsversion' : app_service_minimum_tls_version,
                        'hostname': app_service_hostname
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Allow access from'
        column_3 = 'Type'
        column_4 = 'FTP State'
        column_5 = 'HTTPS only'
        column_6 = 'Minimum TLS version'
        column_7 = 'URL'
        column_names = [column_1, column_2, column_3, column_4, column_5, column_6, column_7]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, app_service_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
