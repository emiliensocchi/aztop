import arm
import csv
import os
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of all inbound connections in all Network Security Groups (NSGs) in an environment.

        Provides the following information for each NSG:
            • The list of allowed destination ports
            • The list of allowed source IP address(es)

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
        self._resource_type = "Microsoft.Network/networkSecurityGroups"


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
        
        nsg_overview = dict()
        subscriptions = subscription_ids if subscription_ids else arm.get_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            for subscription in subscriptions:
                nsgs = arm.get_resources_of_type_within_subscription(self._access_token, subscription, self._resource_type)

                for nsg in nsgs:
                    spinner.next()
                    api_versions = arm.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)
                    nsg_content = arm.get_resource_content_using_multiple_api_versions(self._access_token, nsg, api_versions, spinner)

                    if not nsg_content:
                        self._has_errors = True
                        error_text = f"Could not retrieve content of NSG: {nsg} ; API versions: {api_versions}"
                        utils.log_to_file(self._log_file_path, error_text)
                        continue

                    #-- Initializing variables
                    nsg_name = str()
                    nsg_properties = dict()
                    nsg_inbound_rules = dict()
                    
                    #-- Gather general metadata
                    nsg_name = nsg_content['name']
                    nsg_properties = nsg_content['properties']

                    #-- Gather inbound data
                    nsg_property_name = 'securityRules'
                    nsg_security_rules = nsg_properties[nsg_property_name]
  
                    for security_rule in nsg_security_rules:
                        security_rule_property_name = 'name'
                        security_rule_name = security_rule[security_rule_property_name]
                        security_rule_property_name = 'properties'
                        security_rule_properties = security_rule[security_rule_property_name]
                        security_rule_property_name = 'direction'
                        security_rule_direction = security_rule_properties[security_rule_property_name].lower()
                        security_rule_property_name = 'access'
                        security_rule_access_type = security_rule_properties[security_rule_property_name].lower()
                        allow_access = 'allow'                     
                        direction_inbound = 'inbound'

                        if security_rule_direction == direction_inbound and security_rule_access_type == allow_access:
                            #-- Collect allowed source IPs
                            allowed_ips = list()
                            security_rule_property_name = 'sourceAddressPrefix'

                            if security_rule_property_name in security_rule_properties:
                                # 1 source IP is whitelisted
                                security_rule_source_prefix = security_rule_properties[security_rule_property_name]
                                if security_rule_source_prefix:
                                    allowed_ips.append(security_rule_source_prefix)

                            security_rule_property_name = 'sourceAddressPrefixes'

                            if security_rule_property_name in security_rule_properties:
                                # Multiple source IPs are whitelisted
                                security_rule_source_prefixes = security_rule_properties[security_rule_property_name]
                                if security_rule_source_prefixes:
                                    allowed_ips = allowed_ips + security_rule_source_prefixes 

                            #-- Collect destination ports
                            allowed_dst_ports = list()
                            security_rule_property_name = 'destinationPortRange'

                            if security_rule_property_name in security_rule_properties:
                                # 1 destination port is exposed
                                security_rule_destination_port = security_rule_properties[security_rule_property_name]
                                if security_rule_destination_port:
                                    allowed_dst_ports.append(security_rule_destination_port)

                            security_rule_property_name = 'destinationPortRanges'

                            if security_rule_property_name in security_rule_properties:
                                # Multiple destination ports are exposed
                                security_rule_destination_ports = security_rule_properties[security_rule_property_name]
                                if security_rule_destination_ports:
                                    allowed_dst_ports = allowed_dst_ports + security_rule_destination_ports

                            nsg_inbound_rules[security_rule_name] = { 'ips': ', '.join(allowed_ips), 'ports': ', '.join(allowed_dst_ports) }

                    nsg_property_name = 'securityRules'
                    nsg_default_security_rules = nsg_properties[nsg_property_name]

                    for security_rule in nsg_default_security_rules:
                        security_rule_property_name = 'properties'
                        security_rule_properties = security_rule[security_rule_property_name]
                        security_rule_property_name = 'direction'
                        security_rule_direction = security_rule_properties[security_rule_property_name].lower()
                        security_rule_property_name = 'access'
                        security_rule_access_type = security_rule_properties[security_rule_property_name].lower()
                        allow_access = 'allow'                     
                        direction_inbound = 'inbound'

                        if security_rule_direction == direction_inbound and security_rule_access_type == allow_access:
                            #-- Collect allowed source IPs
                            allowed_ips = list()
                            security_rule_property_name = 'sourceAddressPrefix'

                            if security_rule_property_name in security_rule_properties:
                                # 1 source IP is allowed
                                security_rule_source_prefix = security_rule_properties[security_rule_property_name]
                                if security_rule_source_prefix:
                                    allowed_ips.append(security_rule_source_prefix)

                            security_rule_property_name = 'sourceAddressPrefixes'

                            if security_rule_property_name in security_rule_properties:
                                # Multiple source IPs are allowed
                                security_rule_source_prefixes = security_rule_properties[security_rule_property_name]
                                if security_rule_source_prefixes:
                                    allowed_ips = allowed_ips + security_rule_source_prefixes 

                            #-- Collect destination ports
                            allowed_dst_ports = list()
                            security_rule_property_name = 'destinationPortRange'

                            if security_rule_property_name in security_rule_properties:
                                # 1 destination port is exposed
                                security_rule_destination_port = security_rule_properties[security_rule_property_name]
                                if security_rule_destination_port:
                                    allowed_dst_ports.append(security_rule_destination_port)

                            security_rule_property_name = 'destinationPortRanges'

                            if security_rule_property_name in security_rule_properties:
                                # Multiple destination ports are exposed
                                security_rule_destination_ports = security_rule_properties[security_rule_property_name]
                                if security_rule_destination_ports:
                                    allowed_dst_ports = allowed_dst_ports + security_rule_destination_ports

                            nsg_inbound_rules[security_rule_name] = { 'ips': ', '.join(allowed_ips), 'ports': ', '.join(allowed_dst_ports) }

                    #-- Structure all the gathered data
                    nsg_overview[nsg_name] = { 
                        'inboundrules': nsg_inbound_rules
                    }

                bar.next()

        #-- Export data to csv file
        column_1 = 'Name'
        column_2 = 'Inbound port'
        column_3 = 'Allow access from'
        column_names = [column_1, column_2, column_3]

        os.makedirs(os.path.dirname(self._output_file_path), exist_ok = True)

        with open(self._output_file_path, 'w') as file:
            writer = csv.writer(file)
            writer.writerow(column_names)

            for resource_name, resource_properties in nsg_overview.items():
                inbound_rules = resource_properties['inboundrules']

                for inbound_rule in list(inbound_rules.values()):
                    allowed_src_ips = inbound_rule['ips']
                    allowed_dst_ports = inbound_rule['ports']
                    inbound_rule_row = [resource_name, allowed_dst_ports, allowed_src_ips]
                    writer.writerow(inbound_rule_row)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
