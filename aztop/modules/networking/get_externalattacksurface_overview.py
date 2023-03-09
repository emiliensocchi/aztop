import os
import re
import utils
import progress.bar
import progress.spinner


class Module():
    """
        Module providing an overview of the entire external attack surface of an environment.

        Provides the following external-attack-surface information:
            • List of unrestricted public endpoints (i.e. without IP whitelisting)
            • List of public IP addresses currently associated to VMs
            • List of public endpoints requiring manual investigation to figure out if they are restricted (i.e. mostly related to SQL-like servers)

        Note 1: 
            The module is using Azure Resource Graph (ARG) to query resources across subscriptions, but it is mimicking
            subscription scraping to keep the same behavior as other aztop modules.

        Note 2:
            The module does NOT index AKS Services exposed to the Internet via an Ingress controller on purpose, as this is not 
            a reliable solution for clusters managed outside of Azure AD.

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
        self._resource_type = "Microsoft.ResourceGraph/resources"


    def exec(self, access_token, subscription_ids):
        """
            Starts the module's execution.

            Args:
                access_token (str): a valid access token issued for the ARM API and tenant to analyze
                subscription_ids (str): comma-separated list of subscriptions to analyze or None

            Note:
                Although irrelevant in this case, the structure based on subscriptions has been kept for consistency
                througout the tool

        """
        self._access_token = access_token

        if (self._access_token is None):
            print ('FATAL ERROR!')
            print ('Could not retrieve a valid access token. Set the token manually and retry')
            os._exit(0)
        
        external_attacksurface_overview = dict()
        subscriptions = subscription_ids if subscription_ids else utils.get_all_subscriptions(self._access_token)
        progress_text = 'Processing subscriptions'
        spinner = progress.spinner.Spinner(progress_text)

        with progress.bar.Bar(progress_text, max = len(subscriptions)) as bar:
            all_public_endpoints = []
            all_public_endpoints_requiring_manual_investigation = []
            all_public_ips = []
            has_retrieved_endpoints = False

            for subscription in subscriptions:
                if has_retrieved_endpoints:
                    bar.next()
                    continue

                api_versions = utils.get_api_version_for_resource_type(self._access_token, subscription, self._resource_type)
                arg_resource_path = "/providers/Microsoft.ResourceGraph/resources"

                #-- Retrieve public endpoints built into existing resources
                arg_query_public_endpoints = [
                    "Resources",
                    "| where type != 'microsoft.compute/disks' and type != 'microsoft.compute/snapshots'",
                    "| where (properties contains 'fqdn' and (properties !contains 'apiServerAccessProfile' or properties['apiServerAccessProfile']['authorizedIPRanges'] == '[]')) or (properties['publicNetworkAccess'] == 'Enabled' and ((properties !contains 'networkAcls' and properties !contains 'networkRuleSet') or (properties['networkAcls']['ipRules'] == '[]' and properties['networkRuleSet']['ipRules'] == '[]'))) or (properties['networkAcls']['defaultAction'] == 'Allow' and properties['networkAcls']['ipRules'] == '[]') or (properties['networkRuleSet']['defaultAction'] == 'Allow' and properties['networkRuleSet']['ipRules'] == '[]')"
                    "| order by ['type'] asc",
                    "| project properties.['fqdn'], properties.['primaryEndpoints']['blob'], properties.['primaryEndpoints']['file'], properties.['primaryEndpoints']['table'], properties.['primaryEndpoints']['queue'], properties.['vaultUri'], properties.['loginServer'], properties.['fullyQualifiedDomainName']"
                ]

                arg_query_request_body = {
                    'query': ' '.join(arg_query_public_endpoints)
                }

                arg_query_response = utils.modify_resource_content_using_multiple_api_versions(self._access_token, arg_resource_path, arg_query_request_body, api_versions, spinner)
                
                for response_chunk in arg_query_response['data']:
                    raw_public_endpoints = response_chunk.values()
                    formated_public_endpoints = [endpoint.replace('https://', '').replace('http://', '').replace('/', '') for endpoint in raw_public_endpoints if endpoint]
                    all_public_endpoints = all_public_endpoints + formated_public_endpoints

                spinner.next()

                #-- Extracting endpoints requiring manual investigation 
                requires_manual_investigation_pattern = re.compile('.*(\.database\.(windows\.net|azure\.com|cosmos\.azure\.com)|\.azmk8s\.io)')
                all_public_endpoints_requiring_manual_investigation = [endpoint for endpoint in all_public_endpoints if bool(requires_manual_investigation_pattern.match(endpoint))]
                all_public_endpoints = [endpoint for endpoint in all_public_endpoints if not bool(requires_manual_investigation_pattern.match(endpoint))]
                
                spinner.next()

                #-- Retrieve public IP addresses currently associated with a VM (note: 'properties.ipAddress' is empty for IP addresses not associated with a resource)
                arg_query_public_ips = [
                    "Resources",
                    "| where type contains 'publicIPAddresses' and isnotempty(properties.ipAddress)",
                    "| order by ['type'] asc",
                    "| project properties.ipAddress"
                ]

                arg_query_request_body = {
                    'query': ' '.join(arg_query_public_ips)
                }

                arg_query_response = utils.modify_resource_content_using_multiple_api_versions(self._access_token, arg_resource_path, arg_query_request_body, api_versions, spinner)
                
                for response_chunk in arg_query_response['data']:
                    public_ips = list(response_chunk.values())
                    all_public_ips = all_public_ips + public_ips

                #-- Structure all the gathered data
                a = len(all_public_endpoints)
                b = len(all_public_endpoints_requiring_manual_investigation)
                c = len(all_public_ips)
                longest = 0

                if a >= b and a >= c:
                    longest = a
                elif b >= a and b >= c:
                    longest = b
                else:
                    longest = c
                
                for n in range(longest):
                    public_endpoint = all_public_endpoints[n] if n < len(all_public_endpoints) else ''
                    public_ip = all_public_ips[n]  if n < len(all_public_ips) else ''
                    public_endpoints_requiring_manual_investigation = all_public_endpoints_requiring_manual_investigation[n] if n < len(all_public_endpoints_requiring_manual_investigation) else ''
                    external_attacksurface_overview[public_endpoint] = { 
                        'publicip': public_ip,
                        'manual': public_endpoints_requiring_manual_investigation
                    }

                has_retrieved_endpoints = True
                bar.next()

        #-- Export data to csv file
        column_1 = 'Unrestricted public endpoints'
        column_2 = 'Public IP addresses'
        column_3 = 'Requires manual investigation'
        column_names = [column_1, column_2, column_3]
        
        utils.export_resource_overview_to_csv(self._output_file_path, column_names, external_attacksurface_overview)

        #-- Inform the user about completion with eventual errors
        print (f"\nResults successfully exported to: {self._output_file_path}")

        if self._has_errors:
            print (f"WARNING!\nThere has been errors! Full log exported to: {self._log_file_path}")
