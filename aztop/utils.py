"""
    Utility functions.

"""
import csv
import datetime
import json
import os


def get_log_file_path():
    """
        Builds a full directory path to a file with the .log extension and a name set to the current date and time.

        Returns:
            str: full path to the output file in the following format: /home/path/to/package/logs/yyyy-mm-dd_hh.mm.ss.log

    """
    root_package_path = os.path.dirname(os.path.realpath(__file__))
    output_dir_name = 'logs'
    date = datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S')
    output_file_extension = 'log'
    output_file_name = f"{date}.{output_file_extension}"
    result_file_full_path = os.path.join(root_package_path, output_dir_name, output_file_name)
    
    return result_file_full_path


def get_csv_file_path(file_name):
    """
        Builds a full directory path to a file with the passed name and the .csv extension.
        
        Args:
            file_name (str): name of the file to be used as a base for the csv file

        Returns:
            str: full path to the output file in the following format: /home/path/to/package/output/yyyy-mm-dd_<output_file_name>.csv

    """
    root_package_path = os.path.dirname(os.path.realpath(__file__))
    output_dir_name = 'output'
    date = datetime.datetime.now().strftime('%Y-%m-%d')
    output_file_extension = 'csv'
    output_file_name = f"{date}_{file_name}.{output_file_extension}"
    result_file_full_path = os.path.join(root_package_path, output_dir_name, output_file_name)
    
    return result_file_full_path


def log_to_file(file_path, text):
    """
        Writes the passed text to a file with the passed path.

        Args:
            file_path (str): full path to the file to log to
            text (str): string to be logged
        
        Returns:
            None

    """
    os.makedirs(os.path.dirname(file_path), exist_ok = True)

    with open(file_path, 'a+') as log_file:
        log_file.write(f"{text}\n")


def export_resource_overview_to_csv(output_file_path, column_names, resource_overview):
    """
        Exports the passed resource overview to the passed csv file, using the passed column names as column headers.

        Note:
            The passed resource overview has the following data structure for resources with a *standard network exposure*:
            {
                'resource-name-1':
                {
                    'network': { 'whitelisted': ['ip-1', 'ip-2'] },
                    'property-name-2': 'property-2',
                    'property-name-3': 'property-3'
                }, 
                'resource-name-2':
                {
                    'network': { 'whitelisted': ['ip-1', 'ip-2'] },
                    'property-name-2': 'property-2',
                    'property-name-3': 'property-3'
                },                 
                {...}
            }

        Note: 
            The passed resource overview can have a special the following data structure for resources with a *simplified or no network exposure*:
            {
                'resource-name-1':
                {
                    'property-name-1': 'property-1',
                    'property-name-2': 'property-2',
                    'property-name-3': 'property-3'
                }, 
                'resource-name-2':
                {
                    'property-name-1': 'property-1',
                    'property-name-2': 'property-2',
                    'property-name-3': 'property-3'
                },                 
                {...}
            }

        Note: 
            Resource properties can also be lists, as long as their property name contains the substring 'list'
          
        Args:
            output_file_path (str): full directory path to the csv file where data should be be exported
            column_names (list(str)): list of column names to be used for column headers
            resource_overview (dict(dict(str, str/list))): resource overview to be exported

        Returns:
            None

    """
    os.makedirs(os.path.dirname(output_file_path), exist_ok = True)

    with open(output_file_path, 'w') as file:
        writer = csv.writer(file)
        writer.writerow(column_names)

        for resource_name, resource_properties in resource_overview.items():
            contains_a_list_property = False
            list_property_elements = []
            list_property_first_element = str()

            if any('list' in resource_property_name for resource_property_name in resource_properties):
                # Resource with a list property
                contains_a_list_property = True
                list_key = ''

                for property in resource_properties:
                    if 'list' in property:
                        list_key = property
                        break

                list_property_elements = resource_properties.pop(list_key)

                if list_property_elements:
                    list_property_first_element = list_property_elements.pop(0)

            if 'network' in resource_properties:
                # Resource with a standard network exposure
                network_exposure = resource_properties.pop('network')
                whitelisted_locations = network_exposure['whitelisted']
                network_restriction_name = 'Selected networks' if whitelisted_locations else 'All networks' if network_exposure['ispublic'] else 'Private'
                resource_properties = list(resource_properties.values())
                
                if contains_a_list_property:
                    if list_property_first_element:
                        resource_properties.insert(0, list_property_first_element)
                    else: 
                        resource_properties.insert(0, '')

                resource_properties.insert(0, network_restriction_name)
                resource_properties.insert(0, resource_name)
                writer.writerow(resource_properties)

                if contains_a_list_property:
                    combined_row = [''] * len(resource_properties)
                    longest_property = whitelisted_locations if len(whitelisted_locations) > len(list_property_elements) else list_property_elements

                    for i in range(longest_property):
                        combined_row[1] = whitelisted_locations[i] if len(whitelisted_locations) > i else ''
                        combined_row[2] = list_property_elements[i] if len(list_property_elements) > i else ''
                        writer.writerow(combined_row)
                else:
                    whitelisted_location_row = [''] * len(resource_properties)

                    for whitelisted_location in whitelisted_locations:
                        whitelisted_location_row[1] = whitelisted_location
                        writer.writerow(whitelisted_location_row)
            else:
                # Resource with a simplified or no network exposure
                resource_properties = list(resource_properties.values())

                if contains_a_list_property:
                    if list_property_first_element:
                        resource_properties.insert(0, list_property_first_element)
                    else: 
                        resource_properties.insert(0, '')

                resource_properties.insert(0, resource_name)
                writer.writerow(resource_properties)
                
                if contains_a_list_property:
                    list_property_row = [''] * len(resource_properties)

                    for list_property_element in list_property_elements:
                        list_property_row[1] = list_property_element
                        writer.writerow(list_property_row)         


def handle_http_error(http_response):
    """
        Handles unsuccessful HTTP requests.

    Args:
        http_response (dict): the HTTP response body to the failed request

    Returns
        None
    
    """
    token_expired_error = 'the token is expired'
    token_invalid_audience_error = 'invalid audience'
    invalid_subscription_error_code_values = ['InvalidSubscriptionId', 'SubscriptionNotFound']
    invalid_token_error_code_value = ['ExpiredAuthenticationToken']

    error = json.loads(http_response.text)['error']
    error_code = error['code'].lower()
    error_message = error['message'].lower()

    if error_code in invalid_token_error_code_value or token_expired_error in error_message:
        print ('FATAL ERROR: The provided token has expired')
        os._exit(0)

    if token_invalid_audience_error in error_message:
        print ('FATAL ERROR: The provided token has an invalid audience')
        os._exit(0)

    if error_code in invalid_subscription_error_code_values:
        print (f"FATAL ERROR: The passed subscription is invalid")
        os._exit(0)  

    if error_code == 'InternalServerError':
        print (f"FATAL ERROR: Azure APIs are experiencing problems")
        os._exit(0)  
