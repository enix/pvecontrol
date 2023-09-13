Proxmox VE Control
===

`pvecontrol` software allow management of a cluster proxmox using it's remote API.

It is designed to easy usage of multiple large clusters and get some detailled informations not easily available on the UI and integrated tools.

Installation
---

Need python 3.7+

Install python requirements and directly use the script

```bash
pip3 instal -r requirements.txt
python3 src/pvecontrol.py help
```

Configuration
---

Configuration is a yaml file in `$HOME/.config/pvecontrol/conig.yaml`. It contains configuration needed by proxmoxer to connect to a cluster. `pvecontrol` curently only use the http API and so work with an pve realm user or token (and also a `@pam` user but is not required).

Default configuration template is available in `src/config_default.yaml`. Use this file to build your own configuration file.
