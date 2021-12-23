from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.module_utils.urls import open_url

from six.moves.urllib import parse
from six.moves.urllib.error import HTTPError
from six import iteritems


try:
    import json
except ImportError:
    import simplejson as json

import socket
import re

ANSIBLE_METADATA = {
    'metadata_version': '0.0.2',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
name: mrsuicideparrot.proxmox_plugin
plugin_type: inventory
short_description: Proxmox inventory source
version_added: "2.11.5"
description:
- Get inventory hosts from a proxmox cluster.
- "Uses a configuration file as an inventory source, it must end in ``.proxmox.yml`` or ``.proxmox.yaml`` and has a ``plugin: proxmox`` entry."
options:
    plugin:
        description: Token that ensures this is a source file for the plugin.
        required: True
        choices: ['mrsuicideparrot.proxmox_plugin.inventory']
    url:
        description: url to proxmox
        type: str
        required: True
        env:
            - name: PROXMOX_URL
    user:
        description: proxmox authentication user
        type: str
        required: True
        env:
            - name: PROXMOX_USER
    password:
        description: proxmox authentication password
        type: str
        required: True
        env:
            - name: PROXMOX_PASSWORD
    validate_certs:
        description: verify SSL certificate if using https
        type: boolean
        default: true
'''

EXAMPLES = '''
# my.proxmox.yml
plugin: "mrsuicideparrot.proxmox_plugin.inventory"
url: https://localhost:8006
user: apiuser@pve
password: secure
validate_certs: True
'''

class SystemInfo(object):
    id = ""
    name = ""
    machine = ""
    kernel = ""
    version_id = ""
    ip_address = ""

class ProxmoxNodeList(list):
    def get_names(self):
        return [node['node'] for node in self]


class ProxmoxVM(dict):
    def get_variables(self):
        variables = {}
        for key, value in iteritems(self):
            variables['proxmox_' + key] = value
        return variables


class ProxmoxVMList(list):
    def __init__(self, data=[], pxmxver=0.0):
        self.ver = pxmxver
        for item in data:
            self.append(ProxmoxVM(item))

    def get_names(self):
        if self.ver >= 4.0:
            return [vm['name'] for vm in self if 'template' in vm and vm['template'] != 1]
        else:
            return [vm['name'] for vm in self]

    def get_by_name(self, name):
        results = [vm for vm in self if vm['name'] == name]
        return results[0] if len(results) > 0 else None

    def get_variables(self):
        variables = {}
        for vm in self:
            variables[vm['name']] = vm.get_variables()

        return variables


class ProxmoxPoolList(list):
    def get_names(self):
        return [pool['poolid'] for pool in self]


class ProxmoxVersion(dict):
    def get_version(self):
        return float(self['version'].split('-')[0])


class ProxmoxPool(dict):
    def get_members_name(self):
        return [member['name'] for member in self['members'] if (member['type'] == 'qemu' or member['type'] == 'lxc') and member['template'] != 1]


class ProxmoxAPI(object):
    def __init__(self, url: str, username: str, password: str, tls_validate: bool):
        self.options = {}
        self.credentials = None

        if not url:
            raise Exception('Missing mandatory parameter "url".')
        elif not username:
            raise Exception(
                'Missing mandatory parameter "username".')
        elif not password:
            raise Exception(
                'Missing mandatory parameter "password".')

        self.options['url'] = url
        self.options['username'] = username
        self.options['password'] = password
        self.options['tls_validate'] = tls_validate
        
        # URL should end with a trailing slash
        if not url.endswith("/"):
            self.options['url'] = url + "/"

    def _auth(self):
        request_path = '{0}api2/json/access/ticket'.format(self.options['url'])

        request_params = parse.urlencode({
            'username': self.options['username'],
            'password': self.options['password'],
        })

        data = json.load(open_url(request_path, data=request_params,
                                  validate_certs=self.options['tls_validate']))

        self.credentials = {
            'ticket': data['data']['ticket'],
            'CSRFPreventionToken': data['data']['CSRFPreventionToken'],
        }

    def _get(self, url, data=None):
        if not self.credentials:
            self._auth()

        request_path = '{0}{1}'.format(self.options['url'], url)

        headers = {'Cookie': 'PVEAuthCookie={0}'.format(self.credentials['ticket'])}
        request = open_url(request_path, data=data, headers=headers,
                           validate_certs=self.options['tls_validate'])

        response = json.load(request)
        return response['data']

    def nodes(self):
        return ProxmoxNodeList(self._get('api2/json/nodes'))

    def vms_by_type(self, node, type):
        return ProxmoxVMList(self._get('api2/json/nodes/{0}/{1}'.format(node, type)), self.version().get_version())

    def vm_description_by_type(self, node, vm, type):
        return self._get('api2/json/nodes/{0}/{1}/{2}/config'.format(node, type, vm))

    def node_qemu(self, node):
        return self.vms_by_type(node, 'qemu')

    def node_qemu_description(self, node, vm):
        return self.vm_description_by_type(node, vm, 'qemu')

    def node_lxc(self, node):
        return self.vms_by_type(node, 'lxc')

    def node_lxc_description(self, node, vm):
        return self.vm_description_by_type(node, vm, 'lxc')

    def node_openvz(self, node):
        return self.vms_by_type(node, 'openvz')

    def node_openvz_description(self, node, vm):
        return self.vm_description_by_type(node, vm, 'openvz')

    def pools(self):
        return ProxmoxPoolList(self._get('api2/json/pools'))

    def pool(self, poolid):
        return ProxmoxPool(self._get('api2/json/pools/{0}'.format(poolid)))
    
    def qemu_agent(self, node, vm):
        try:
            info = self._get('api2/json/nodes/{0}/qemu/{1}/agent/info'.format(node, vm))
            if info is not None:
                return True
        except HTTPError as error:
            return False

    def openvz_ip_address(self, node, vm):
        try:
            config = self._get('api2/json/nodes/{0}/lxc/{1}/config'.format(node, vm))
        except HTTPError:
            return False
        
        try:
            ip_address = re.search('ip=(\d*\.\d*\.\d*\.\d*)', config['net0']).group(1)
            return ip_address
        except:
            return False
    
    def version(self):
        return ProxmoxVersion(self._get('api2/json/version'))

    def qemu_agent_info(self, node, vm):
        system_info = SystemInfo()
        osinfo = self._get('api2/json/nodes/{0}/qemu/{1}/agent/get-osinfo'.format(node, vm))['result']
        if osinfo:
            if 'id' in osinfo:
                system_info.id = osinfo['id']

            if 'name' in osinfo:
                system_info.name = osinfo['name']

            if 'machine' in osinfo:
                system_info.machine = osinfo['machine']

            if 'kernel-release' in osinfo:
                system_info.kernel = osinfo['kernel-release']

            if 'version-id' in osinfo:
                system_info.version_id = osinfo['version-id']

        ip_address = None
        networks = self._get('api2/json/nodes/{0}/qemu/{1}/agent/network-get-interfaces'.format(node, vm))['result']
        if networks:
            if type(networks) is dict:
                for network in networks:
                    for ip_address in ['ip-address']:
                        try:
                            # IP address validation
                            if socket.inet_aton(ip_address):
                                # Ignore localhost
                                if ip_address != '127.0.0.1':
                                    system_info.ip_address = ip_address
                        except socket.error:
                            pass
            elif type(networks) is list:
                for network in networks:
                    if 'ip-addresses' in network:
                        for ip_address in network['ip-addresses']:
                            try:
                                # IP address validation
                                if socket.inet_aton(ip_address['ip-address']):
                                    # Ignore localhost
                                    if ip_address['ip-address'] != '127.0.0.1':
                                        system_info.ip_address = ip_address['ip-address']
                            except socket.error:
                                pass

        return system_info


class InventoryModule(BaseInventoryPlugin):
    NAME = 'mrsuicideparrot.proxmox_inventory_plugin'

    def verify_file(self, path):
        if super(InventoryModule, self).verify_file(path):
            if path.endswith(('proxmox.yaml', 'proxmox.yml')):
                return True
            else:
                self.display.vvv('Skipping due to inventory source not ending in "proxmox.yaml" nor "proxmox.yml"')
        return False

    def _process_list(self, olist):
        for i in olist:
            self.inventory.add_host(i['name'])
            for key, val in i.get_variables().items():
                self.inventory.set_variable(i['name'], key, val)


    def parse(self, inventory, loader, path, cache=None):
        super(InventoryModule, self).parse(inventory, loader, path)

        self._read_config_data(path)

        proxmoxInstance = ProxmoxAPI(self.get_option('url'), self.get_option('user'), self.get_option('password'), self.get_option('validate_certs'))

        for node in proxmoxInstance.nodes().get_names():
            try:
                qemu_list = proxmoxInstance.node_qemu(node)
            except HTTPError as error:
                # the API raises code 595 when target node is unavailable, skip it
                if error.code == 595 or error.code == 596:
                    continue
                # if it was some other error, reraise it
                raise error

            self._process_list(qemu_list)
                        
            container_list = None
            if proxmoxInstance.version().get_version() >= 4.0:
                container_list = proxmoxInstance.node_lxc(node)
            else:
                container_list = proxmoxInstance.node_openvz(node)

            self._process_list(container_list)

            node_hostvars = qemu_list.get_variables().copy()
            node_hostvars.update(container_list.get_variables())

            # Check only VM/containers from the current node
            for vm in node_hostvars:
                vmid = self.inventory.get_host(vm).vars['proxmox_vmid']
                try:
                    type = self.inventory.get_host(vm).vars['proxmox_type']
                except KeyError:
                    type = 'qemu'
                    self.inventory.set_variable(vm, 'proxmox_type', 'qemu')
                try:
                    description = proxmoxInstance.vm_description_by_type(node, vmid, type)['description']
                except KeyError:
                    description = None

                try:
                    metadata = json.loads(description)
                except TypeError:
                    metadata = {}
                except ValueError:
                    metadata = {
                        'notes': description
                    }
                
                if type == 'qemu':
                    # Retrieve information from QEMU agent if installed
                    if proxmoxInstance.qemu_agent(node, vmid):
                        system_info = proxmoxInstance.qemu_agent_info(node, vmid)
                        self.inventory.set_variable(vm, 'ansible_host', system_info.ip_address)
                        self.inventory.set_variable(vm, 'proxmox_os_id', system_info.id)
                        self.inventory.set_variable(vm, 'proxmox_os_name', system_info.name)
                        self.inventory.set_variable(vm, 'proxmox_os_machine', system_info.machine)
                        self.inventory.set_variable(vm, 'proxmox_os_kernel', system_info.kernel)
                        self.inventory.set_variable(vm, 'proxmox_os_version_id', system_info.version_id)
                else:
                    self.inventory.set_variable(vm, 'ansible_host', proxmoxInstance.openvz_ip_address(node, vmid))
                
                if 'groups' in metadata:
                    for group in metadata['groups']:
                        self.inventory.add_group(group)
                        self.inventory.add_child(group, vm)

                status = self.inventory.get_host(vm).vars['proxmox_status']
                if status == 'running':
                    self.inventory.add_group('running')
                    self.inventory.add_child('running',vm)
        
                try:
                    osid = self.inventory.get_host(vm).vars['proxmox_os_id']
                    if osid:
                        self.inventory.add_group(osid)
                        self.inventory.add_child(osid,vm)
                except KeyError:
                    pass
                  
                for key, val in metadata.items():
                    self.inventory.set_variable(vm, key, val)

        for pool in proxmoxInstance.pools().get_names():
            self.inventory.add_group(pool)
            for i in proxmoxInstance.pool(pool).get_members_name():
                self.inventory.add_child(pool, i)

