import arm
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all Service Buses in an environment.

        Provides the following information for each Service Bus:
            • Whether the Service Bus is exposed to All networks or Selected networks
                - For Selected networks, IP ranges, VNet and subnet names are provided
            • Whether the Service Bus is exposed to private endpoints (VNet, subnet names and private IP addresses are provided)
            • Which data-plane authorization model the Service Bus is using (Entra ID or Shared Access Signature - SAS)

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
        self._resource_type = "Microsoft.ServiceBus/namespaces"


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
        
        service_bus_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                service_buses = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for service_bus in service_buses:
                    spinner.next()
                    networkrulesets_path = '/networkrulesets/default'
                    service_bus_networkrulesets_path = f"{service_bus}/{networkrulesets_path}"
                    service_bus_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, service_bus, api_versions, spinner)
                    service_bus_networkrulesets_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, service_bus_networkrulesets_path, api_versions, spinner)

                    if not service_bus_content or not service_bus_networkrulesets_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of Service Bus: {service_bus} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables
                    service_bus_properties = dict()
                    service_bus_network_exposure = dict()
                    service_bus_name = str()
                    service_bus_data_plane_authz_mode = str()

                    #-- Gather general metadata
                    service_bus_name = service_bus_content['name']
                    service_bus_properties = service_bus_content['properties']
                    service_bus_networkrulesets_properties = service_bus_networkrulesets_content['properties']

                    #-- Gather data-plane authorization data
                    property_name = 'disableLocalAuth'
                    service_bus_data_plane_authz_mode = 'Entra ID' if service_bus_properties[property_name] else 'Shared Access Signatures (SAS)'

                    #-- Gather networking data
                    property_name = 'publicNetworkAccess'
                    public_network_access = service_bus_networkrulesets_properties.pop(property_name)
                    service_bus_properties[property_name] = public_network_access

                    property_name = 'networkAcls'
                    service_bus_properties[property_name] = service_bus_networkrulesets_properties

                    service_bus_network_exposure = arm.get_resource_network_exposure(self._access_token, subscription, service_bus_properties, spinner)

                    if service_bus_network_exposure == 'hidden':
                        # The resource attempted to be retrieved is managed by Microsoft
                        continue

                    if not service_bus_network_exposure:
                        self._has_errors = True
                        error_text = f"Could not retrieve network exposure for Service Bus with properties: {service_bus_properties}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Structure all the gathered data
                    service_bus_overview[service_bus_name] = { 
                        'network': service_bus_network_exposure,
                        'authorization': service_bus_data_plane_authz_mode
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Allow access from'
        column_3 = 'Data-plane authorization'
        column_names = [column_1, column_2, column_3]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, service_bus_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
