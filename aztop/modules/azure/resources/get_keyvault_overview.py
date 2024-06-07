import arm
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all Key Vaults in an environment.

        Provides the following information for each Key Vault:
            • Whether the Key Vault is exposed to All networks or Selected networks
                - For Selected networks, IP ranges, VNet and subnet names are provided
            • Whether the Key Vault is exposed to private endpoints (VNet, subnet names and private IP addresses are provided)
            • Which Data-plane authorization model the Key Vault is using (Entra ID or Vault access policies)
            • Whether Purge protection is enabled

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
        self._resource_type = "Microsoft.KeyVault/vaults"


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
        
        keyvault_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                keyvaults = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for keyvault in keyvaults:
                    spinner.next()
                    keyvault_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, keyvault, api_versions, spinner)

                    if not keyvault_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of Key Vault: {keyvault} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables
                    keyvault_properties = dict()
                    keyvault_network_exposure = dict()
                    keyvault_name = str()
                    keyvault_data_plane_authz_mode = str()
                    keyvault_purge_protection = str()

                    #-- Gather general metadata
                    keyvault_name = keyvault_content['name']
                    keyvault_properties = keyvault_content['properties']

                    #-- Gather data-plane authorization data
                    keyvault_data_plane_authz_mode = ''
                    keyvault_property_name = 'enableRbacAuthorization'

                    if keyvault_property_name in keyvault_properties:
                        keyvault_data_plane_authz_mode = 'Entra ID' if  keyvault_properties[keyvault_property_name] else 'Vault access policies'
                    else:
                        # Support for older Key Vaults
                        keyvault_data_plane_authz_mode = 'Vault access policies'

                    #-- Gather purge protection data
                    keyvault_property_name = 'enablePurgeProtection'
                    keyvault_purge_protection = 'Enabled' if keyvault_property_name in keyvault_properties else 'Disabled'

                    #-- Gather networking data
                    keyvault_network_exposure = arm.get_resource_network_exposure(self._access_token, subscription, keyvault_properties, spinner)

                    if keyvault_network_exposure == 'hidden':
                        # The resource attempted to be retrieved is managed by Microsoft
                        continue

                    if not keyvault_network_exposure:
                        self._has_errors = True
                        error_text = f"Could not retrieve network exposure for Key Vault with properties: {keyvault_properties}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Structure all the gathered data
                    keyvault_overview[keyvault_name] = { 
                        'network': keyvault_network_exposure, 
                        'authorization': keyvault_data_plane_authz_mode,
                        'purge' : keyvault_purge_protection
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Allow access from'
        column_3 = 'Data-plane authorization'
        column_4 = 'Purge protection'
        column_names = [column_1, column_2, column_3, column_4]

        utils.export_resource_overview_to_csv(self._output_file_path, column_names, keyvault_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
