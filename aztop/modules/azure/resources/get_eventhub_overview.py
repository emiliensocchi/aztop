import arm
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all Event Hub Namespaces in an environment.

        Provides the following information for each Event Hubs Namespace:
            • Whether the Namespace exposes its Event Hubs to All networks or Selected networks
                - For Selected networks, IP ranges, VNet and subnet names are provided
            • Whether the Namespace exposes its Event Hubs to private endpoints (VNet, subnet names and private IP addresses are provided)
            • The minimum TLS version required for HTTPS connections to the Event Hubs Namespace
            • Which Data-plane authorization model the Event Hubs Namespace is using (Entra ID or Shared Access Signature - SAS)

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
        self._resource_type = "Microsoft.EventHub/namespaces"


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
        
        eventhub_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                eventhubs = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for eventhub in eventhubs:
                    spinner.next()
                    networkrulesets_path = '/networkrulesets/default'
                    eventhub_networkrulesets_path = f"{eventhub}/{networkrulesets_path}"
                    eventhub_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, eventhub, api_versions, spinner)
                    eventhub_networkrulesets_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, eventhub_networkrulesets_path, api_versions, spinner)

                    if not eventhub_content or not eventhub_networkrulesets_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of Service Bus: {eventhub} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables
                    eventhub_properties = dict()
                    eventhub_network_exposure = dict()
                    eventhub_name = str()
                    eventhub_minimum_tls_version = str()
                    eventhub_data_plane_authz_mode = str()

                    #-- Gather general metadata
                    eventhub_name = eventhub_content['name']
                    eventhub_properties = eventhub_content['properties']
                    eventhub_networkrulesets_properties = eventhub_networkrulesets_content['properties']

                    #-- Gather minimum TLS version data
                    eventhub_property_name = 'minimumTlsVersion'
                    eventhub_minimum_tls_version = f"TLS {eventhub_properties[eventhub_property_name]}"

                    #-- Gather data-plane authorization data
                    eventhub_property_name = 'disableLocalAuth'
                    eventhub_data_plane_authz_mode = 'Entra ID' if eventhub_properties[eventhub_property_name] else 'Shared Access Signature (SAS)'

                    #-- Gather networking data
                    property_name = 'publicNetworkAccess'
                    public_network_access = eventhub_networkrulesets_properties.pop(property_name)
                    eventhub_properties[property_name] = public_network_access

                    property_name = 'networkAcls'
                    eventhub_properties[property_name] = eventhub_networkrulesets_properties

                    eventhub_network_exposure = arm.get_resource_network_exposure(self._access_token, subscription, eventhub_properties, spinner)

                    if eventhub_network_exposure == 'hidden':
                        # The resource attempted to be retrieved is managed by Microsoft
                        continue

                    if not eventhub_network_exposure:
                        self._has_errors = True
                        error_text = f"Could not retrieve network exposure for Service Bus with properties: {eventhub_properties}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Structure all the gathered data
                    eventhub_overview[eventhub_name] = { 
                        'network': eventhub_network_exposure, 
                        'tlsversion': eventhub_minimum_tls_version,
                        'authorization' : eventhub_data_plane_authz_mode
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Allow access from'
        column_3 = 'Minimum TLS version'
        column_4 = 'Data-plane authorization'
        column_names = [column_1, column_2, column_3, column_4]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, eventhub_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
