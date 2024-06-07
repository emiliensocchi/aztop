"""
    Simple template implementing the core worflow of a module.
    Should be used as a based to develop new modules.

    Note:
        The name of a new module should follow the following format: 
            • get_<resource-name>_overview

"""
import arm
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all <RESOURCES_NAME> in an environment.

        Provides the following information for each <RESOURCE_NAME>:
            • Whether the <RESOURCE_NAME> is exposed to All networks or Selected networks
                - For Selected networks, IP ranges, VNet and subnet names are provided
            • Whether the <RESOURCE_NAME> is exposed to private endpoints (VNet, subnet names and private IP addresses are provided)
            • [insert information]
            • [insert information]

        Note:
            Refract the following strings for quick refraction:
                <RESOURCES_NAME> (e.g. refract with 'Key Vaults')
                <RESOURCE_NAME>  (e.g. refract with 'Key Vault')
                resources_xyz    (e.g. refract with 'keyvaults')
                resource_xyz     (e.g. refract with 'keyvault')

            [insert information]
            [insert information]

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
        self._resource_type = "<COMPLETE>"


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
        
        resource_xyz_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                resources_xyz = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for resource_xyz in resources_xyz:
                    spinner.next()
                    resource_xyz_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, resource_xyz, api_versions, spinner)

                    if not resource_xyz_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of <RESOURCE_NAME>: {resource_xyz} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables - MAKE SURE ALL OUTPUTS ARE STRINGS!
                    resource_xyz_properties = dict()
                    resource_xyz_network_exposure = dict()
                    resource_xyz_name = str()
                    resource_xyz_example_data_1 = str()
                    resource_xyz_example_data_2 = str()

                    #-- Gather general metadata
                    resource_xyz_name = resource_xyz_content['name']
                    resource_xyz_properties = resource_xyz_content['properties']

                    #-- Gather more stuff - <COMPLETE>
                    resource_xyz_property_name = 'InterestingProperty1'
                    resource_xyz_example_data_1 = resource_xyz_properties[resource_xyz_property_name]

                    #-- Gather more stuff - <COMPLETE>
                    resource_xyz_property_name = 'InterestingProperty2'
                    resource_xyz_example_data_2 = resource_xyz_properties[resource_xyz_property_name]

                    #-- Gather networking data
                    resource_xyz_network_exposure = arm.get_resource_network_exposure(self._access_token, subscription, resource_xyz_properties, spinner)

                    if not resource_xyz_network_exposure:
                        self._has_errors = True
                        error_text = f"Could not retrieve network exposure for <RESOURCE_NAME> with properties: {resource_xyz_properties}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Structure all the gathered data - MAKE SURE 'network' IS ALWAYS FIRST!
                    resource_xyz_overview[resource_xyz_name] = { 
                        'network': resource_xyz_network_exposure, 
                        'exampledata1': resource_xyz_example_data_1,
                        'exampledata2' : resource_xyz_example_data_2
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Allow access from'
        column_3 = 'Example 1'
        column_4 = 'Example 2'
        column_names = [column_1, column_2, column_3, column_4]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, resource_xyz_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
