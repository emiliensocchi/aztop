import arm
import csv
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of the usage of all Managed Identities (MIs) in an environment.

        Provides the following information:
            • The MI's type (system-assigned or user-assgined)
            • The set of resources actively using the MI

        Note:
            A user-assigned MI is a standalone resource and can be consumed by multiple resources
            A system-assigned MI has a lifcyle tied to a specific resource and can only be used by the latter

    """
    _output_file_name = str()
    _output_file_path = str()
    _log_file_path = str()
    _has_errors = bool
    _access_token = str()


    def __init__(self):
        module_path = os.path.realpath(__file__)
        module_name_with_extension = module_path.rsplit('/', maxsplit = 1)[1] if os.name == 'posix' else module_path.rsplit('\\', maxsplit = 1)[1]
        module_name = module_name_with_extension.split('.')[0]
        self._output_file_name = module_name
        self._output_file_path = utils.get_csv_file_path(self._output_file_name)
        self._log_file_path = utils.get_log_file_path()
        self._has_errors = False


    def exec(self, access_token, subscription_ids):
        """
            Starts the module's execution.

            Args:
                access_token (str): a valid access token issued for the ARM API and tenant to analyze

        """
        self._access_token = access_token

        if (self._access_token is None):
            print ('FATAL ERROR!')
            print ('Could not retrieve a valid access token. Set the token manually and retry')
            os._exit(0)
        
        mi_assignment_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                resource_providers_with_api_versions = arm.get_resource_types_with_associated_api_versions_within_subscription(self._access_token, subscription)
                resources = arm.get_resources_within_subscription(self._access_token, subscription)

                for resource in resources:
                    spinner.next()
                    resource_provider = (resource.split('providers/')[1].rsplit('/', 1)[0]).lower()
                    resource_content = dict()
                    api_versions = []

                    try:
                        api_versions = resource_providers_with_api_versions[resource_provider]
                    except:
                        # The resource has no corresponding resource provider in the subscription
                        # Normal for private dns zones, database migration services, etc.
                        # Affects only resource that do not support Managed Identities
                        continue   

                    if '#' in resource:
                        # The resource is of one of the rare kinds using a hash mark in its path
                        url_encoded_hashmark = '%23'
                        resource = resource.replace('#', url_encoded_hashmark)
                    
                    resource_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, resource, api_versions, spinner)

                    if not resource_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of Resource: {resource} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    try:
                        resource_type = resource_content['type']
                        resource_name = f"{resource_content['name']} ('{resource_type}')"
                        managed_identity = resource_content['identity']
                        identity_types = managed_identity['type']

                        if 'UserAssigned' in identity_types:
                            user_assigned_identities = managed_identity['userAssignedIdentities'] # list

                            for user_assigned_identity in user_assigned_identities:
                                user_assigned_identity = user_assigned_identity.rsplit('/', 1)[1]
                                try:
                                    # The identity is already associated with resources and has an entry in the dict
                                    mi_assignment_overview[user_assigned_identity]['resources'].append(resource_name)
                                except:
                                    # The identity does not have an entry in the dict
                                    mi_assignment_overview[user_assigned_identity] = { 'type': 'UserAssigned', 'resources': [resource_name]}

                        if 'SystemAssigned' in identity_types:
                            system_assigned_identity = managed_identity['principalId']

                            try:
                                # The identity is already associated with resources and has an entry in the dict
                                mi_assignment_overview[system_assigned_identity]['resources'].append(resource_name)                   
                            except:
                                # The identity does not have an entry in the dict
                                mi_assignment_overview[system_assigned_identity] = { 'type': 'SystemAssigned', 'resources': [resource_name]}
                    except:
                        # The resource has no Managed Identity
                        continue

                bar.next()

        #-- Export data to csv file
        column_1 = 'Managed Identity'
        column_2 = 'Type'
        column_3 = 'Used by'

        column_names = [column_1, column_2, column_3]        

        os.makedirs(os.path.dirname(self._output_file_path), exist_ok = True)

        with open(self._output_file_path, 'w') as file:
            writer = csv.writer(file)
            writer.writerow(column_names)

            for managed_identity, properties in mi_assignment_overview.items():
                mi_type = properties['type'].replace('Assigned', '-assigned')
                associated_resources = properties['resources']
                c = 0

                for associated_resource in associated_resources:
                    if c == 0:
                        writer.writerow([managed_identity, mi_type, associated_resource])
                    else:
                        writer.writerow(['', '', associated_resource])
                    c += 1

        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
