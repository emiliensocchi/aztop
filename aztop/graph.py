"""
    Microsoft Graph functions.

"""
import os
import requests
import utils


GRAPH_BASEURL = 'https://graph.microsoft.com'


def get_service_principals(access_token):
    """
        Retrieves object id, display name and type of all service principals readable by the passed access token.

        Args:
            access_token (str): a valid access token issued for the Graph API

        Returns:
            dict(): ['objectid-1': {'name': 'name-1', 'type': 'type-1'}, 'objectid-2': {'name': 'name-2', 'type': 'type-2'}, ]

    """
    api_version = 'v1.0'
    url = f"{GRAPH_BASEURL}/{api_version}/servicePrincipals?$top=999"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers = headers)

    if response.status_code != 200:
        utils.handle_http_error(response)

    all_service_principals = []    # includes 'Application', 'ManagedIdentity', 'Legacy', 'SocialIdp'
    paginated_service_principals = response.json()['value']
    all_service_principals = paginated_service_principals
    next_page = response.json()['@odata.nextLink'] if '@odata.nextLink' in response.json() else ''

    while next_page:
        response = requests.get(next_page, headers = headers)

        if response.status_code != 200:
            utils.handle_http_error(response)

        paginated_service_principals = response.json()['value']
        next_page = response.json()['@odata.nextLink'] if '@odata.nextLink' in response.json() else ''
        all_service_principals = all_service_principals + paginated_service_principals

    all_striped_service_principals = dict()

    for service_principal in all_service_principals:
        service_principal_id = service_principal['id']
        service_principal_name = service_principal['displayName']
        service_principal_type = service_principal['servicePrincipalType']

        all_striped_service_principals[service_principal_id] = {'name': service_principal_name, 'type': service_principal_type}

    return all_striped_service_principals


def get_service_principal_name_from_id(access_token, service_principal_oid):
    """
        Retrieves the human-readable name of the service principal with the passed object Id.

        Args:
            access_token (str): a valid access token issued for the Graph API
            service_principal_oid (str): the object Id of the service principal to retrieve the name for
        
        Returns:
            str: the name of the service principal
    
    """
    api_version = 'v1.0'
    url = f"{GRAPH_BASEURL}/{api_version}/servicePrincipals/{service_principal_oid}"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers = headers)

    if response.status_code != 200:
        utils.handle_http_error(response)

    service_principal = response.json()   
    service_principal_name = service_principal['appDisplayName']
    return service_principal_name


def get_application_permission_name_from_id(access_token, resource_id, app_permission_id):
    """
        Retrieves the human-readable name of the application permission in the passed resource with the passed role Id.

        Args:
            access_token (str): a valid access token issued for the Graph API
            resource_id (str): the object Id of the the resource server for which the passed permission applies for
            app_permission_id (str): the object Id of the application permission to retrieve the name for
        
        Returns:
            str: the name of the application permission
    
    """
    api_version = 'v1.0'
    url = f"{GRAPH_BASEURL}/{api_version}/servicePrincipals(id='{resource_id}')?$select=appRoles"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers = headers)

    if response.status_code != 200:
        utils.handle_http_error(response)

    all_application_permissions = response.json()['appRoles']

    if not all_application_permissions:
        # Create a mechanism to retry until working if this becomes an issue
        print ('DEBUG: Trying to get Graph app roles returned an error')
        os._exit(0)         

    all_application_permission_ids = [app_role['id']  for app_role in all_application_permissions]

    if app_permission_id in all_application_permission_ids:
        passed_application_permission_index = all_application_permission_ids.index(app_permission_id)
        passed_application_permission_object = all_application_permissions[passed_application_permission_index]
        passed_application_permission_name = passed_application_permission_object['value']
    else:
        # The application permission has no name (possible for App Roles)
        passed_application_permission_name = ''

    return passed_application_permission_name


def get_service_principal_application_permissions(access_token, service_principal_oid):
    """
        Retrieves all the application permissions assigned to the passed service principal.

        Args:
            access_token (str): a valid access token issued for the Graph API
            service_principal_oid (str): the object Id of the service principal to retrieve the permissions for
        
        Returns:
            dict(): the application permissions granted to passed service principal per resource

    """
    api_version = 'v1.0'
    url = f"{GRAPH_BASEURL}/{api_version}/servicePrincipals/{service_principal_oid}/appRoleAssignments"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers = headers)

    if response.status_code != 200:
        utils.handle_http_error(response)

    application_permissions = response.json()['value']
    granted_application_permissions_per_resource = dict()

    for application_permission in application_permissions:
        resource_id = application_permission['resourceId']
        resource_name = application_permission['resourceDisplayName']
        application_permission_id = application_permission['appRoleId']
        application_permission_name = get_application_permission_name_from_id(access_token, resource_id, application_permission_id)

        if resource_name in granted_application_permissions_per_resource:
            granted_application_permissions_per_resource[resource_name].append(application_permission_name)
        else:
            granted_application_permissions_per_resource[resource_name] = [application_permission_name]

    return granted_application_permissions_per_resource
