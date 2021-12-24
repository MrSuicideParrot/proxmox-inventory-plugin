# Proxmox inventory source [![CI](https://github.com/MrSuicideParrot/proxmox-inventory-plugin/actions/workflows/main.yml/badge.svg)](https://github.com/MrSuicideParrot/proxmox-inventory-plugin/actions/workflows/main.yml)

An ansible plugin to source inventory from a Proxmox Cluster.

## Installation

```bash
ansible-galaxy install mrsuicideparrot.proxmox_plugin
```

## Similar projects

[xezpeleta/Ansible-Proxmox-inventory](https://github.com/xezpeleta/Ansible-Proxmox-inventory) is a inventory scripts. It offers definition of custom variables using Proxmox notes. However, ansible is deprecating inventory scripts, the new recomended way is to create an inventory plugin and package it as an Ansible Collection.

[ansible-collections/community.general](https://github.com/ansible-collections/community.general/blob/2d6816e11e1672df5b2aa485e8af9eaa45d7c5be/plugins/inventory/proxmox.py) is an Ansible Collection that has inventory plugin proxmox. This plugin doesn't support custom variables using Proxmox notes.

## How to use it

If you want to use this plugin in your project, you first need to install it. Then, create a new  inventory ending with `proxmox.yaml`, for example `my.proxmox.yaml`. 

The inventory must have the following content, filled with your credentials:

```
plugin: "mrsuicideparrot.proxmox_plugin.inventory"
url: https://localhost:8006
user: apiuser@pve
password: secure
validate_certs: True
```

Finally, you activate the plugin by creating a `galaxy.cfg` in the repo directory. 

```
[inventory]
enable_plugins = mrsuicideparrot.proxmox_plugin.inventory
```

You are now ready to source dynamically an inventory from your Proxmox Cluster. 

You can check if everything is working by listing the inventory.

```bash
ansible-inventory --list -i my.proxmox.yml
```

You should see a list of nodes from your Proxmox Cluster.

### Custom metadata

You can use the Notes field on Proxmox to define variables. To leverage this feature the notes should be a valid JSON.

This feature can also be used to assign groups to a machine.

```JSON
{ "groups": ["windows", "utils"] }
```

If the VM has the qemu guest agent working or ,in the case of a container, it has a static IP configured, the variable `ansible_host` will be defined with the IP address of the machine.

A definition of multiple variables would be:

```JSON
{ "groups": ["docker", "server"], "ansible_user":"root", "custom_variable":"things" }
```

## Requirements

None

---
#### Acknowledgments

This project was based on [xezpeleta/Ansible-Proxmox-inventory](https://github.com/xezpeleta/Ansible-Proxmox-inventory). 