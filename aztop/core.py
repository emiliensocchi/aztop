"""
    Core functionalities.

"""
import argparse
import azure.identity
import importlib
import json
import jwt
import os
import prettytable
import pyfiglet
import re


ARM_BASEURL = 'https://management.azure.com'
ARM_CLASSIC_BASEURL = 'https://management.core.windows.net/'
GRAPH_BASEURL = 'https://graph.microsoft.com'
DEFAULT_SCOPE = '.default'


class ModuleLoader():
    """
        A simple module loader with an interactive interface.

        Attributes:
            _display_name (str): name of the module loader to display as a banner in the interactive interface 
            _modules_dir_name (str): name of the directory containing all the modules to be loaded in the application
            _modules (dict(dict(str, dict(str, <module.object>))): data structure for the modules loaded in the application

        Note:
            Illustration of the data structure used for the '_modules' attribute:
                { 
                    'entra': 
                        { 
                            '<module_category_1>': 
                                { 
                                    '<module_1_name': <module.object>,
                                    '<module_2_name>': <module.object>
                                },
                            'service-principals': 
                                { 
                                    'module1': <module.object>,
                                    'module2': <module.object> 
                                } 
                        },
                    'azure': 
                        { 
                            '<module_category_1>': 
                                { 
                                    '<module_1_name': <module.object>,
                                    '<module_2_name>': <module.object>
                                },
                            'networking': 
                                { 
                                    'module1': <module.object>,
                                    'module2': <module.object> 
                                } 
                        }    
                }

    """
    _display_name = str()
    _entra_modules_dir_name = str()
    _azure_modules_dir_name = str()
    _modules_dir_name = str()
    _modules = { str(): dict() }


    def __init__(self):
        self._display_name = 'aztop'
        self._entra_modules_dir_name = 'entra'
        self._azure_modules_dir_name = 'azure'
        self._modules_dir_name = 'modules'
        self._modules = { self._entra_modules_dir_name: dict(), self._azure_modules_dir_name: dict(), }

        #-- Get all subdirectories of the main module directory
        root_package_path = os.path.dirname(os.path.realpath(__file__))
        modules_package_path = os.path.join(root_package_path, self._modules_dir_name) 
        modules_entra_path = os.path.join(modules_package_path, self._entra_modules_dir_name) 
        modules_azure_path = os.path.join(modules_package_path, self._azure_modules_dir_name) 

        entra_module_categories_paths = [ f.path for f in os.scandir(modules_entra_path) if f.is_dir() ]
        azure_module_categories_paths = [ f.path for f in os.scandir(modules_azure_path) if f.is_dir() ]
        sorted_entra_module_categories_paths = sorted(entra_module_categories_paths)
        sorted_azure_module_categories_paths = sorted(azure_module_categories_paths)
        all_sorted_module_categories_paths = sorted_entra_module_categories_paths + sorted_azure_module_categories_paths

        #-- Import all modules from each directory into a data structure
        for path_to_module_category in all_sorted_module_categories_paths:
            module_paths = [ f.path for f in os.scandir(path_to_module_category) if f.is_file() ]
            sorted_module_paths = sorted(module_paths)

            for path_to_module in sorted_module_paths:
                splited_path = path_to_module.rsplit('/', maxsplit = 4) if os.name == 'posix' else path_to_module.rsplit('\\', maxsplit = 4) # e.g. /home/path/to/package/modules/modulecategory1/module1
                module_root_dir = splited_path[1]                                                           # e.g. modules
                module_type = splited_path[2]                                                               # e.g. entra
                module_category = splited_path[3]                                                           # e.g. modulecategory1
                module_name = splited_path[4].split('.')[0]                                                 # e.g. module1
                full_module_name = '.'.join([module_root_dir, module_type, module_category, module_name])   # e.g. modules.modulecategory1.module1

                modules_dict = self._modules[module_type]
                                    
                if module_category not in modules_dict:
                    modules_dict[module_category] = dict()

                module_category_dict = modules_dict[module_category]
                module_category_dict[module_name] = importlib.import_module(full_module_name).Module()


    def color_text(self, rgb, text):
        """
            Colors the passed text in the color represented by the passed Red, Green and Blue (RGB) combination.

            Args:
                rgb (list(str)): list of red, green and blue intensity to be used
                text (str): text to color

            Returns:
                str: text in the color represented by the passed RGB combination

        """
        r = rgb[0]
        g = rgb[1]
        b = rgb[2]
        return "\033[38;2;{};{};{}m{} \033[38;2;255;255;255m".format(r, g, b, text)


    def clear_screen(self):
        """
            Clears the caller's terminal based on the used platform.

        """
        platform = os.name

        if platform == 'nt':
            _ = os.system('cls')

        elif platform == 'posix':
            _ = os.system('clear')

        else:
            print ('Unsupported platform!')
            print ('Exiting ...')
            os._exit(0)


    def print_banner(self, text):
        """
            Prints a simple banner displaying the passed text.

            Args:
                text (str): text to display as the module loader's banner

        """
        banner = pyfiglet.Figlet(font = 'colossal', width = 200)
        formated_text = "\n".join(text.rsplit(' ', maxsplit = 1))   # replace the last space with CRLF
        space_separated_text = ' '.join(formated_text)              # add space between each character for prettier rendering
        print (banner.renderText(space_separated_text))
  

    def print_menu(self, title_text, options, exit_text):
        """
            Prints a simple menu with the passed title, options and exit text, presented in a table format.

            Args:
                title_text (str): title to be displayed above the menu
                options (list(str)): list of options to display in a numbered fashion 
                exit_text (str): text to display for the exit option

            Returns:
                str: the textual representation of the selected option (e.g. 'modulecategory1', 'module1')
                None: if the exit option has been selected

        """
        table = prettytable.PrettyTable()
        table.field_names = [title_text]
        table.align[title_text] = 'l'
        table.hrules = prettytable.ALL

        number_of_options = len(options)
        exit_input = number_of_options + 1
        user_input = 0

        for i in range(number_of_options):
            n = i + 1
            row = f"{str(n)} -- {options[i]}"
            table.add_row([row])

        row = f"{str(exit_input)} {exit_text}"
        table.add_row([row])

        self.clear_screen()
        self.print_banner(self._display_name)
        print (table)

        while user_input != exit_input:
            try:
                input_text = '\n' + 'Choice: '
                user_input = int(input(input_text))

                if user_input in range(1, exit_input):
                    # Valid input
                    user_input = user_input - 1
                    return options[user_input]

                elif user_input == exit_input:
                    # Exiting input
                    return None

                else:
                    raise IndexError('Index out of range')
            except:
                # Invalid input
                self.clear_screen()
                return self.print_menu(title_text, options, exit_text)


    def validate_input(self):
        """
            Validates the arguments passed to the module loader.

            Returns:
                argparse.Namespace: Namespace object containing the passed argument(s) as attribute(s)

        """
        lines = [
            "AZure Tenant Overview Provider (aztop)",
            "The tool to get an overview of an Azure tenant's configuration in no time!",
            "By Emilien Socchi"
        ]

        parser = argparse.ArgumentParser(
            description     = "\n".join(lines),
            formatter_class = argparse.RawTextHelpFormatter
        )
        
        parser.add_argument(
            '-arm',
            '--arm-access-token',
            help = 'A valid access token issued for the ARM API'
        )

        parser.add_argument(
            '-graph',
            '--graph-access-token',
            help = 'A valid access token issued for the MS Graph API'
        )

        parser.add_argument(
            '-tid',
            '--tenant-id',
            help = 'The id of the tenant to analyze (required if using a guest account)'
        )

        parser.add_argument(
            '-sub',
            '--subscription-ids',
            help = 'Comma-separated list ids for subscriptions to analyze (omitting this parameter scans all subscriptions)'
        )

        return parser.parse_args()


    def get_token_file_path(self):
        """
            Builds a full directory path to a file with a standard name and the .json extension.

            Returns:
                str: full path to the output file in the following format: /home/path/to/package/.tokens.json

        """
        root_package_path = os.path.dirname(os.path.realpath(__file__))
        file_name = 'tokens'
        output_file_extension = 'json'
        output_file_name = f".{file_name}.{output_file_extension}"
        result_file_full_path = os.path.join(root_package_path, output_file_name)
        
        return result_file_full_path


    def export_token_to_file(self, tenant_id, token_scope, token_type, token):
        """
            Writes the passed token of the passed type and issued for the passed scope and tenant to a local file,
            while preserving other tokens already stored in that file.

            Args:
                tenant_id (str): the id of the tenant for which the token has been issued
                token_scope (str): the scope for which the token has been issued (i.e. arm, graph)
                token_type (str): the token's type (i.e. access, refresh)
                token (str): the JWT token to be exported

            Returns:
                None

        """
        loaded_tokens = dict()
        root_package_path = os.path.dirname(os.path.realpath(__file__))
        tokens_file_name = '.tokens.json'
        tokens_file_full_path = os.path.join(root_package_path, tokens_file_name)

        if os.path.exists(tokens_file_full_path) and os.stat(tokens_file_full_path).st_size > 0:
            # The token file already exists and is populated with tokens for some tenants
            with open(tokens_file_full_path, 'r+') as file:
                loaded_tokens = json.load(file)

                if tenant_id in loaded_tokens:
                    # Tokens issued for the passed tenant id are already stored in the file
                    tenant_tokens = loaded_tokens[tenant_id]

                    if token_scope in tenant_tokens:
                        # Tokens issued for the passed scope are already stored in the file
                        tenant_tokens[token_scope][token_type] = token
                    else:
                        # No token has been issued for the passed scope within the passed tenant
                        tenant_tokens[token_scope] = { token_type: token }
                else:
                    # No token has been issued for the passed tenant id
                    decoded_token = jwt.decode(token, options = {"verify_signature": False, "verify_aud": False})
                    tenant_id = decoded_token['tid']
                    loaded_tokens[tenant_id] = { token_scope: { token_type: token }}  

                json_output = json.dumps(loaded_tokens)
                file.seek(0)
                file.write(json_output)
                file.truncate()
        else:
            # The token file does not exist or is empty
            with open(tokens_file_full_path, 'w') as file:
                decoded_token = jwt.decode(token, options = {"verify_signature": False, "verify_aud": False})
                tenant_id = decoded_token['tid']
                loaded_tokens[tenant_id] = { token_scope: { token_type: token }}
                json_output = json.dumps(loaded_tokens)
                file.write(json_output)


    def get_cached_token(self, tenant_id, token_scope, token_type):
        """
            Retrieves the cached token issued for the passed tenant and with the passed scope and type and verifies its validity.

            Args:
                tenant_id (str): the id of the tenant the token to be retrieved is issued for 
                token_scope (str): the scope of the token to be retrieved (i.e. arm, graph)
                token_type (str): the type of the token to be retrieved (i.e. access, refresh)

            Returns:
                str: the retrieved token if existing and valid. None otherwise

        """
        cached_token = None
        token_file_path = self.get_token_file_path()
        loaded_tokens = dict()

        if os.path.exists(token_file_path) and os.stat(token_file_path).st_size > 0:
            # Some tokens for some tenants and API(s) have been acquired previously
            with open(token_file_path, 'r') as file:
                tenant_ids = json.load(file)
    
                if tenant_id and tenant_id in tenant_ids:
                    # Some token for the passed tenant has been acquired previously
                    loaded_tokens = tenant_ids[tenant_id]

                    if token_scope in loaded_tokens:
                        # A token of the passed scope has been acquired previously for the passed tenant (i.e. arm/graph)
                        loaded_scope_tokens = loaded_tokens[token_scope]

                        if token_type in loaded_scope_tokens:
                            # A token for the passed scope and of the passed type has been acquired previously (i.e. access/refresh)
                            loaded_token = loaded_scope_tokens[token_type]
                            audience = ARM_BASEURL if token_scope == 'arm' else GRAPH_BASEURL
                            has_token_expired = False

                            try:
                                jwt.decode(loaded_token, audience = audience, options = {"verify_signature": False})
                            except:
                                if audience == ARM_BASEURL:
                                    # The token might be valid for ARM, but has been issued for the classic ARM API audience
                                    try:
                                        audience = ARM_CLASSIC_BASEURL
                                        jwt.decode(loaded_token, audience = audience, options = {"verify_signature": False})
                                    except:
                                        # The token issued for ARM is definitely invalid (expired, wrong format, etc.)
                                        has_token_expired = True
                                else:
                                    # The token is invalid (expired, wrong format, etc.)
                                    has_token_expired = True

                            if not has_token_expired:
                                # The token is still valid
                                cached_token = loaded_token

        return cached_token


    def get_arm_access_token_via_auth_code_flow(self, tenant_id):
        """
            Verifies whether a valid access token issued for the ARM API exists for the passed tenant and is still valid in the cache, 
            and retrieves a new access token using the interactive authorization code flow otherwise.

            Args:
                tenant_id (str): the id of the tenant to acquire an ARM access token for

            Note:
                https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-auth-code-flow

            Returns:
                str: valid access token upon successful authentication. None otherwise

        """
        access_token = str()
        token_scope = 'arm'
        token_type = 'access'
        cached_token = self.get_cached_token(tenant_id, token_scope, token_type)

        if cached_token:
            access_token = cached_token
        else:
            # No access token for ARM has been acquired previously for the passed tenant or it has expired
            scope = f"{ARM_BASEURL}/{DEFAULT_SCOPE}"
            access_token_obj = azure.identity.InteractiveBrowserCredential().get_token(scope, tenant_id = tenant_id, timeout = 30)
            access_token = access_token_obj.token if access_token_obj else None

            if access_token:
                self.export_token_to_file(tenant_id, token_scope, token_type, access_token)

        return access_token


    def get_graph_access_token_via_auth_code_flow(self, tenant_id):
        """
            Verifies whether a valid access token issued for the Microsoft Graph API exists for the passed tenant and is still valid in the cache, 
            and retrieves a new access token using the interactive authorization code flow otherwise.

            Args:
                tenant_id (str): the id of the tenant to acquire an ARM access token for

            Note:
                https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-auth-code-flow

            Returns:
                str: valid access token upon successful authentication. None otherwise

        """
        access_token = str()
        token_scope = 'graph'
        token_type = 'access'
        cached_token = self.get_cached_token(tenant_id, token_scope, token_type)

        if cached_token:
            access_token = cached_token
        else:
            # No access token for MS Graph has been acquired previously for the passed tenant or it has expired
            scope = f"{GRAPH_BASEURL}/{DEFAULT_SCOPE}"
            access_token_obj = azure.identity.InteractiveBrowserCredential().get_token(scope, tenant_id = tenant_id, timeout = 30)
            access_token = access_token_obj.token if access_token_obj else None

            if access_token:
                self.export_token_to_file(tenant_id, token_scope, token_type, access_token)

        return access_token


    def run(self):
        """
            Starts the interactive menu interface and executes the selected module upon selection.

        """
        if len(self._modules) == 0:
            print ('FATAL ERROR!')
            print (f"No modules were found in the {self._modules_dir_name} directory!")
            print ("Check the directory's content and try again.")
            return

        #-- Validate input arguments
        args = self.validate_input()
        passed_arm_access_token = args.arm_access_token
        passed_graph_access_token = args.graph_access_token
        passed_tenant_id = args.tenant_id
        subscription_ids = args.subscription_ids

        if passed_arm_access_token:
            # An access token for the ARM API has been passed manually
            try:
                decoded_token = jwt.decode(passed_arm_access_token, options = {"verify_signature": False, "verify_aud": False})
                passed_tenant_id = decoded_token['tid']
                token_scope = 'arm'
                token_type = 'access'
                self.export_token_to_file(passed_tenant_id, token_scope, token_type, passed_arm_access_token)
            except:
                # The passed token has expired or is corrupted
                print ('[!] The passed ARM access token has either expired or is in the wrong format')
                os._exit(0)

        if passed_graph_access_token:
            # An access token for the MS Graph API has been passed manually
            try:
                decoded_token = jwt.decode(passed_graph_access_token, options = {"verify_signature": False, "verify_aud": False})
                passed_tenant_id = decoded_token['tid']
                token_scope = 'graph'
                token_type = 'access'
                self.export_token_to_file(passed_tenant_id, token_scope, token_type, passed_graph_access_token)
            except:
                # The passed token has expired or is corrupted
                print ('[!] The passed Graph access token has either expired or is in the wrong format')
                os._exit(0)

        if subscription_ids:
            pattern = re.compile("^[0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}$")
            subscription_ids = [id.strip() for id in subscription_ids.split(',')]
            
            for subscription_id in subscription_ids:
                if not pattern.match(subscription_id):
                    # The passed list of subscription ids is not in the right format
                    print ('[!] The passed list is not a comma-separated list of subscription ids')
                    os._exit(0)

        modules = self._modules
        module_types = list(modules.keys())
        highlighted_text_rgb_color = [0, 137, 214]

        #-- Display interactive menu until exit
        while True:
            #-- Display module types
            title_text = 'Select a category to get overview of:'
            exit_text = 'exit'
            selected_module_type = self.print_menu(title_text, module_types, exit_text)

            if selected_module_type is None:
                # Exit has been selected
                break

            while True:
                #-- Display module categories
                title_text = 'Select a category to get overview of:'
                exit_text = 'back'
                module_categories = list(modules[selected_module_type].keys())
                selected_module_category = self.print_menu(title_text, module_categories, exit_text)

                if selected_module_category is None:
                    # Back has been selected
                    break

                #-- Display modules within the selected category
                highlighted_selected_module_category = self.color_text(highlighted_text_rgb_color, selected_module_category)
                title_text = f"Get overview of: {highlighted_selected_module_category}"
                exit_text = 'back'
                all_text = 'get_all_overviews'
                modules_to_display = list(modules[selected_module_type][selected_module_category].keys())
                modules_to_display.append(all_text)
                selected_module_name = self.print_menu(title_text, modules_to_display, exit_text)

                if selected_module_name is None:
                    # Back has been selected
                    continue

                elif selected_module_name is all_text:
                    # The execution of all modules within the category has been selected
                    modules_to_execute = list(modules[selected_module_type][selected_module_category].keys())
                    self.clear_screen()
                    arm_access_token = self.get_arm_access_token_via_auth_code_flow(passed_tenant_id)

                    for module_to_execute in modules_to_execute:
                        #-- Execute all modules
                        highlighted_module_to_execute_name = self.color_text(highlighted_text_rgb_color, module_to_execute)
                        print (f"Executing module: {highlighted_module_to_execute_name}\n")
                        module_object = modules[selected_module_type][selected_module_category][module_to_execute]
                        module_object.exec(arm_access_token, subscription_ids)
                        print ("\n\n")

                    return

                #-- Execute the selected module
                highlighted_selected_module_name = self.color_text(highlighted_text_rgb_color, selected_module_name)
                module_object = modules[selected_module_type][selected_module_category][selected_module_name]
                self.clear_screen()
                print (f"Executing module: {highlighted_selected_module_name}\n")

                access_token = self.get_graph_access_token_via_auth_code_flow(passed_tenant_id) if selected_module_type == self._entra_modules_dir_name else self.get_arm_access_token_via_auth_code_flow(passed_tenant_id)

                module_object.exec(access_token, subscription_ids)
                return
