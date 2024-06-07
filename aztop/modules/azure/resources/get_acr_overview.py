import arm
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all Azure Container Registries (ACRs) in an environment.

        Provides the following information for each ACR:
            • Whether the ACR is exposed to All networks or Selected networks
                - For Selected networks, IP ranges, VNet and subnet names are provided
            • Whether the ACR is exposed to private endpoints (VNet, subnet names and private IP addresses are provided)
            • Whether the ACR allows anonymous pull access
            • Whether the ACR has Content Trust enabled
            • Whether the ACR has an Admin user

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
        self._resource_type = "Microsoft.ContainerRegistry/registries"


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
        
        acr_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                acrs = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for acr in acrs:
                    spinner.next()
                    acr_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, acr, api_versions, spinner)

                    if not acr_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of ACR: {acr} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables
                    acr_properties = dict()
                    acr_network_exposure = dict()
                    acr_name = str()
                    acr_anonymous_pull_access = str()
                    acr_trust_policy = str()
                    acr_admin_user = str()

                    #-- Gather general metadata
                    acr_name = acr_content['name']
                    acr_properties = acr_content['properties']

                    #-- Gather Anonymous pull access data
                    acr_property_name = 'anonymousPullEnabled'
                    acr_anonymous_pull_access = 'Enabled' if (acr_property_name in acr_properties and acr_properties[acr_property_name]) else 'Disabled'

                    #-- Gather Content Trust data
                    acr_property_name = 'policies'
                    acr_policies = acr_properties[acr_property_name]
                    acr_property_name = 'trustPolicy'
                    acr_trust_policy_property = acr_policies[acr_property_name]
                    acr_property_name = 'status'
                    acr_trust_policy = acr_trust_policy_property[acr_property_name].capitalize()

                    #-- Gather Admin user data
                    acr_property_name = 'adminUserEnabled'
                    acr_admin_user = 'Enabled' if acr_properties[acr_property_name] else 'Disabled'

                    #-- Gather networking data
                    acr_network_exposure = arm.get_resource_network_exposure(self._access_token, subscription, acr_properties, spinner)

                    if acr_network_exposure == 'hidden':
                        # The resource attempted to be retrieved is managed by Microsoft
                        continue

                    if not acr_network_exposure:
                        self._has_errors = True
                        error_text = f"Could not retrieve network exposure for ACR with properties: {acr_properties}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Structure all the gathered data
                    acr_overview[acr_name] = { 
                        'network': acr_network_exposure,                        
                        'anonymouspull': acr_anonymous_pull_access,
                        'trustpolicy': acr_trust_policy,
                        'adminuser' : acr_admin_user
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Allow access from'
        column_3 = 'Anonymous pull access'
        column_4 = 'Content trust'
        column_5 = 'Admin user'
        column_names = [column_1, column_2, column_3, column_4, column_5]

        utils.export_resource_overview_to_csv(self._output_file_path, column_names, acr_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
