import arm
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all Disks in an environment.

        Provides the following information for each Disk:
            • Whether the Disk can be imported/exported to/from all locations, private locations or is denied
            • The attachment state of the disk

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
        self._resource_type = "Microsoft.Compute/disks"


    def exec(self, access_token, subscription_ids):
        """
            Starts the module's execution.

            Args:
                access_token (str): a valid access token issued for the ARM API and tenant to analyze
                subscription_ids list(str): list of subscription ids to analyze or None

        """
        self._access_token = access_token

        if (self._access_token is None):
            print ('FATAL ERROR!')
            print ('Could not retrieve a valid access token. Set the token manually and retry')
            os._exit(0)
        
        disk_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                disks = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for disk in disks:
                    spinner.next()
                    disk_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, disk, api_versions, spinner)

                    if not disk_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of Disk: {disk} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables
                    disk_properties = dict()
                    disk_name = str()
                    disk_attachment_state = str()
                    disk_network_access_policy = str()

                    #-- Gather general metadata
                    disk_name = disk_content['name']
                    disk_properties = disk_content['properties']

                    #-- Gather attachment state data
                    disk_property_name = 'diskState'
                    disk_attachment_state = disk_properties[disk_property_name]

                    #-- Gather networking data
                    disk_property_name = 'networkAccessPolicy'
                    disk_network_access_policy = 'All networks' if disk_properties[disk_property_name] == 'AllowAll' else 'Private locations' if disk_properties[disk_property_name] == 'AllowPrivate' else 'Denied'

                    #-- Structure all the gathered data
                    disk_overview[disk_name] = { 
                        'networkaccesspolicy': disk_network_access_policy, 
                        'attachmentstate': disk_attachment_state
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Allow import/export from'
        column_3 = 'Attachment state'
        column_names = [column_1, column_2, column_3]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, disk_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
