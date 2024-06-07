import csv
import graph
import os
import utils
import progress.bar


class Module():
    """
        Module providing an overview of the service principals in a tenant with their associated granted application permissions.

        Provides the following information for each service principal:
            • The type of service principal
            • The resource(s) for which the permissions are granted for
            • The list of granted application permission for each resource
            • Whether a permission might be sensitive

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
                access_token (str): a valid access token issued for the Graph API and tenant to analyze

        """
        self._access_token = access_token

        if (self._access_token is None):
            print ('FATAL ERROR!')
            print ('Could not retrieve a valid access token. Set the token manually and retry')
            os._exit(0)
        
        granted_application_permission_overview = dict()
        service_principals = graph.get_service_principals(self._access_token)
        progress_text = 'Processing service principals'

        with progress.bar.Bar(progress_text, max = len(service_principals)) as bar:
            for service_principal_id, service_principal in service_principals.items():
                #-- Gather general metadata
                service_principal_name = service_principal['name']
                service_principal_type = service_principal['type']

                #-- Gather application permissions per resource
                granted_application_permissions_per_resource = graph.get_service_principal_application_permissions(self._access_token, service_principal_id)

                #-- Structure all the gathered data
                granted_application_permission_overview[service_principal_name] = { 
                    'permissiondict': granted_application_permissions_per_resource, 
                    'type': service_principal_type
                }

                bar.next()
   
        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Type'
        column_3 = 'Resource'
        column_4 = 'Granted application permission(s)'
        column_5 = 'Potentially sensitive'

        column_names = [column_1, column_2, column_3, column_4, column_5]        

        os.makedirs(os.path.dirname(self._output_file_path), exist_ok = True)

        with open(self._output_file_path, 'w') as file:
            sensitive_permission = 'write'
            writer = csv.writer(file)
            writer.writerow(column_names)

            for service_principal_name, properties in granted_application_permission_overview.items():
                service_principal_type = properties['type']
                service_principal_permissions_per_resource = properties['permissiondict']

                for resource_name, permissions in service_principal_permissions_per_resource.items():
                    first_permission = permissions.pop(0)
                    first_permission_sensitivity='🔥' if sensitive_permission in first_permission.lower() else ''
                    first_row = [service_principal_name, service_principal_type, resource_name, first_permission, first_permission_sensitivity]
                    writer.writerow(first_row)

                    list_property_row = [''] * len(column_names)

                    for permission in permissions:
                        permission_sensitivity='🔥' if sensitive_permission in permission.lower() else ''
                        list_property_row[1] = service_principal_type
                        list_property_row[2] = resource_name
                        list_property_row[3] = permission
                        list_property_row[4] = permission_sensitivity
                        writer.writerow(list_property_row)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
