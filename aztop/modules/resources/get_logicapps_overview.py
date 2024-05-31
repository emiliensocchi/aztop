import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all Logic Apps in an environment.

        Provides the following information for each Logic App:
            • The actions making up the Logic App and whether they are using secure input and output
            • The triggers of the Logic App
            • The network location from which the Logic App can be triggered from
            • The network location from which the run history of the Logic App can be accessed from
            • The access point of the Logic App

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
        self._resource_type = "Microsoft.Logic/workflows"


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
        
        logicapp_overview = dict()
        subscriptions = subscription_ids if subscription_ids else utils.get_all_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                logicapps = utils.get_all_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = utils.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for logicapp in logicapps:
                    spinner.next()
                    logicapp_content = utils.get_resource_content_using_multiple_api_versions(self._access_token, logicapp, api_versions, spinner)

                    if not logicapp_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of Logic App: {logicapp} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables
                    logicapp_properties = dict()
                    logicapp_name = str()
                    logicapp_triggers = str()
                    logicapp_trigger_network_exposure = str()
                    logicapp_run_history_network_exposure = str()
                    logicapp_actions_list = []
                    logicapp_access_point = str()

                    #-- Gather general metadata
                    logicapp_name = logicapp_content['name']
                    logicapp_properties = logicapp_content['properties']
                    logicapp_definition = logicapp_properties['definition']

                    #-- Gather trigger type data
                    logicapp_property_name = 'triggers'        

                    if logicapp_property_name in logicapp_definition:
                        logicapp_triggers = logicapp_definition[logicapp_property_name]
                        logicapp_triggers = ', '.join(list(logicapp_triggers))
                    else:
                        logicapp_triggers = 'None'

                    #-- Gather actions and secure input/output configuration
                    logicapp_property_name = 'actions'

                    if logicapp_property_name in logicapp_definition:
                        logicapp_actions = logicapp_definition[logicapp_property_name]

                        for action_name in logicapp_actions:
                            logicapp_action_content = logicapp_actions[action_name]
                            logicapp_property_name_1 = 'runtimeConfiguration'
                            logicapp_property_name_2 = 'properties'

                            if logicapp_property_name_1 in logicapp_action_content and logicapp_property_name_2 in logicapp_action_content:
                                secure_input_property_name = 'inputs'
                                secure_output_property_name = 'outputs'
                                logicapp_action_runtime_configuration = logicapp_action_content[logicapp_property_name_1][logicapp_property_name_2]
                                has_secure_input = 'Yes' if secure_input_property_name in logicapp_action_runtime_configuration else 'No'
                                has_secure_output = 'Yes' if secure_output_property_name in logicapp_action_runtime_configuration else 'No'

                                logicapp_actions_list.append(f"{action_name} ({has_secure_input}/{has_secure_output})")
                            else:
                                logicapp_actions_list.append(f"{action_name} (No/No)")
                    else:
                        logicapp_actions_list.append('None')

                    #-- Gather network exposure for run history and Logic App triggers
                    logicapp_property_name = 'accessControl'

                    if logicapp_property_name in logicapp_properties:
                        logicapp_access_control = logicapp_properties[logicapp_property_name]
                        #-- Run history           
                        logicapp_property_name = 'contents'

                        if logicapp_property_name in logicapp_access_control:
                            logicapp_access_control_contents = logicapp_access_control[logicapp_property_name]
                            logicapp_property_name = 'allowedCallerIpAddresses'
                            logicapp_allowed_caller_Ips = logicapp_access_control_contents[logicapp_property_name]
                            
                            whitelisted_ips = []

                            for caller_ip in logicapp_allowed_caller_Ips:
                                logicapp_property_name = 'addressRange'
                                allowed_ip = caller_ip[logicapp_property_name]
                                whitelisted_ips.append(allowed_ip)

                            logicapp_run_history_network_exposure = ", ".join(whitelisted_ips)
                        else:
                            logicapp_run_history_network_exposure = 'All networks'

                        #-- Logic App triggers
                        logicapp_property_name = 'triggers'
  
                        if logicapp_property_name in logicapp_access_control:
                            logicapp_access_control_contents = logicapp_access_control[logicapp_property_name]
                            logicapp_property_name = 'allowedCallerIpAddresses'

                            if logicapp_property_name in logicapp_access_control_contents:
                                logicapp_allowed_caller_Ips = logicapp_access_control_contents[logicapp_property_name]
                                
                                whitelisted_ips = []

                                for caller_ip in logicapp_allowed_caller_Ips:
                                    logicapp_property_name = 'addressRange'
                                    allowed_ip = caller_ip[logicapp_property_name]
                                    whitelisted_ips.append(allowed_ip)

                                logicapp_trigger_network_exposure = ", ".join(whitelisted_ips)
                            else:
                                logicapp_trigger_network_exposure = 'All networks'        
                        else:
                            logicapp_trigger_network_exposure = 'All networks'    
                    else:
                        logicapp_run_history_network_exposure = 'All networks'
                        logicapp_trigger_network_exposure = 'All networks'

                    #-- Gather access point data
                    logicapp_property_name = 'accessEndpoint'
                    logicapp_access_point = logicapp_properties[logicapp_property_name]

                    #-- Structure all the gathered data
                    logicapp_overview[logicapp_name] = { 
                        'actionlist': logicapp_actions_list, 
                        'triggertype': logicapp_triggers,
                        'triggernetworkexposure': logicapp_trigger_network_exposure,
                        'runhistorynetworkexposure': logicapp_run_history_network_exposure,
                        'accesspoint' : logicapp_access_point
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Actions (secure input/ secure output)'
        column_3 = 'Trigger(s)'
        column_4 = 'Allow triggering from'
        column_5 = 'Allow access to run history from'
        column_6 = 'Access point'
        column_names = [column_1, column_2, column_3, column_4, column_5, column_6]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, logicapp_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
