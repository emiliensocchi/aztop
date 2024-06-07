import arm
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all hostnames handled by all Load Balancers in an environment.

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
        self._resource_type = "Microsoft.Network/applicationGateways"


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
        
        loadbalancer_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                loadbalancers = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for loadbalancer in loadbalancers:
                    spinner.next()
                    loadbalancer_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, loadbalancer, api_versions, spinner)

                    if not loadbalancer_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of Load Balancer: {loadbalancer} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables
                    loadbalancer_properties = dict()
                    loadbalancer_name = str()
                    loadbalancer_hostnames= str()

                    #-- Gather general metadata
                    loadbalancer_name = loadbalancer_content['name']
                    loadbalancer_properties = loadbalancer_content['properties']

                    #-- Gather hostname data
                    loadbalancer_hostnames_list = []
                    loadbalancer_property_name = 'httpListeners'
                    loadbalancer_listeners = loadbalancer_properties[loadbalancer_property_name]

                    for loadbalancer_listener in loadbalancer_listeners:
                        loadbalancer_listener_properties = loadbalancer_listener['properties']
                        loadbalancer_listener_property_name = 'hostName'

                        if loadbalancer_listener_property_name in loadbalancer_listener_properties:

                            hostname = loadbalancer_listener_properties['hostName']
                            loadbalancer_hostnames_list.append(hostname)

                    loadbalancer_hostnames = '\n'.join(loadbalancer_hostnames_list)
                    
                    #-- Structure all the gathered data
                    loadbalancer_overview[loadbalancer_name] = { 
                        'hostnames': loadbalancer_hostnames
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Associated hostnames (from listener rules)'
        column_names = [column_1, column_2]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, loadbalancer_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
