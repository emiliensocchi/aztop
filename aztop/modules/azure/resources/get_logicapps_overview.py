import arm
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
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                logicapps = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)
                api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)

                for logicapp in logicapps:
                    spinner.next()
                    logicapp_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, logicapp, api_versions, spinner)

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
                    logicapp_runs = str()
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
                        logicapp_triggers = ', '.join(list(logicapp_triggers.keys()))
                        logicapp_triggers = logicapp_triggers.replace('manual', 'Request')
                    else:
                        logicapp_triggers = ''

                    #-- Gather actions and secure input/output configuration
                    logicapp_property_name = 'actions'

                    if logicapp_property_name in logicapp_definition:
                        logicapp_steps = logicapp_definition[logicapp_property_name]

                        for step_name in logicapp_steps:
                            logicapp_property_name = 'actions'
                            logicapp_content = logicapp_steps[step_name]

                            if logicapp_property_name in logicapp_content:
                                # The action is a step
                                logicapp_actions = logicapp_content[logicapp_property_name]

                                for action_name in logicapp_actions:
                                    has_secure_input = False
                                    has_secure_output = False
                                    logicapp_action_content = logicapp_actions[action_name]
                                    logicapp_property_name = 'type'
                                    logicapp_action_type = logicapp_action_content[logicapp_property_name]
                                    logicapp_sensitive_action_type = '🔥' if logicapp_action_type.lower() == 'http' else ''
                                    logicapp_property_name = 'runtimeConfiguration'
                                    
                                    if logicapp_property_name in logicapp_action_content:
                                        logicapp_action_runtime_configuration = logicapp_action_content[logicapp_property_name]
                                        logicapp_property_name = 'secureData'
                                        if logicapp_property_name in logicapp_action_runtime_configuration:
                                            logicapp_action_secure_data = logicapp_action_runtime_configuration[logicapp_property_name]
                                            logicapp_property_name = 'properties'
                                            if logicapp_property_name in logicapp_action_secure_data:
                                                logicapp_action_properties = logicapp_action_secure_data[logicapp_property_name]
                                                secure_input_property_name = 'inputs'
                                                secure_output_property_name = 'outputs'
                                                has_secure_input = True if secure_input_property_name in logicapp_action_properties else False
                                                has_secure_output = True if secure_output_property_name in logicapp_action_properties else False

                                    secure_input = 'True' if has_secure_input else 'False'
                                    secure_output = 'True' if has_secure_output else 'False'
                                    logicapp_actions_list.append(f"{action_name} ({secure_input}/{secure_output}) {logicapp_sensitive_action_type}")
                            else:
                                # The action is a single action
                                logicapp_property_name = 'type'
                                logicapp_action_type = logicapp_content[logicapp_property_name]
                                logicapp_sensitive_action_type = '🔥' if logicapp_action_type.lower() == 'http' else ''
                                has_secure_input = False
                                has_secure_output = False
                                logicapp_property_name = 'runtimeConfiguration'
                                    
                                if logicapp_property_name in logicapp_action_content:
                                    logicapp_action_runtime_configuration = logicapp_action_content[logicapp_property_name]
                                    logicapp_property_name = 'secureData'
                                    if logicapp_property_name in logicapp_action_runtime_configuration:
                                        logicapp_action_secure_data = logicapp_action_runtime_configuration[logicapp_property_name]
                                        logicapp_property_name = 'properties'
                                        if logicapp_property_name in logicapp_action_secure_data:
                                            logicapp_action_properties = logicapp_action_secure_data[logicapp_property_name]
                                            secure_input_property_name = 'inputs'
                                            secure_output_property_name = 'outputs'
                                            has_secure_input = True if secure_input_property_name in logicapp_action_properties else False
                                            has_secure_output = True if secure_output_property_name in logicapp_action_properties else False
                                            
                                secure_input = 'True' if has_secure_input else 'False'
                                secure_output = 'True' if has_secure_output else 'False'
                                logicapp_actions_list.append(f"{step_name} ({secure_input}/{secure_output}) {logicapp_sensitive_action_type}")
                    else:
                        logicapp_actions_list.append('')

                    #-- Gather the number of run histories
                    logicapp_history = logicapp + '/runs'
                    logicapp_history_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, logicapp_history, api_versions, spinner)
                    logicapp_runs = str(len(logicapp_history_content['value']))

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
                                blockall_ip_range = '0.0.0.0-0.0.0.0'
                                logicapp_property_name = 'addressRange'
                                allowed_ip = 'No network (deny all)' if caller_ip[logicapp_property_name] == blockall_ip_range else caller_ip[logicapp_property_name]
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
                                logicapp_allowed_caller_ips = logicapp_access_control_contents[logicapp_property_name]
                                
                                whitelisted_ips = []

                                for caller_ip in logicapp_allowed_caller_ips:
                                    blockall_ip_range = '0.0.0.0-0.0.0.0'
                                    logicapp_property_name = 'addressRange'
                                    allowed_ip = 'No network (deny all)' if caller_ip[logicapp_property_name] == blockall_ip_range else caller_ip[logicapp_property_name]
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
                        'numberofruns': logicapp_runs,
                        'runhistorynetworkexposure': logicapp_run_history_network_exposure,
                        'accesspoint' : logicapp_access_point
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Actions (secure input/ secure output)'
        column_3 = 'Trigger(s)'
        column_4 = 'Allow triggering from'
        column_5 = 'Number of runs'
        column_6 = 'Allow access to run history from'
        column_7 = 'Access point'
        column_names = [column_1, column_2, column_3, column_4, column_5, column_6, column_7]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, logicapp_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
