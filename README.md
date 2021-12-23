# Proxmox inventory source [![CI](https://github.com/MrSuicideParrot/proxmox-inventory-plugin/actions/workflows/main.yml/badge.svg)](https://github.com/MrSuicideParrot/proxmox-inventory-plugin/actions/workflows/main.yml)

An ansible plugin to source an inventory from a Proxmox Cluster.

## Installation

```bash
ansible-galaxy install mrsuicideparrot.proxmox_plugin
```

## Metadata

You can use the Notes field on Proxmox to define variables. To leverage this feature the notes should be a valid JSON.

This feature can also be used to assign groups to a machine.

```JSON
{ "groups": ["windows", "utils"] }
```

If the VM has the qemu guest agent working or ,in the case of a container, it has a static IP configured, the variable `ansible_host` will be defined with the IP address of the machine.

## How to use it

If you want to use this plugin in a project, you first need to install it. Then, create a new  inventory ending with `proxmox.yaml`, for example `my.proxmox.yaml`. 

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

---
#### Acknowledgments

This project was based on [xezpeleta/Ansible-Proxmox-inventory](https://github.com/xezpeleta/Ansible-Proxmox-inventory). Ansible is deprecating inventory scripts. The new recomended way is to create an inventory plugin and package it as an Ansible collection. 