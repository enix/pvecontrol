import logging
import sys
import confuse


configtemplate = {
    "clusters": confuse.Sequence(
        {
            "name": str,
            "host": str,
            "user": str,
            "password": str,
            "timeout": confuse.Optional(int, default=0),
            "node": confuse.Optional(
                {
                    "cpufactor": confuse.Optional(float, None),
                    "memoryminimum": confuse.Optional(int, None),
                },
                default={},
            ),
            "vm": confuse.Optional(
                {
                    "max_last_backup": int,
                },
                default={},
            ),
        }
    ),
    "node": {"cpufactor": float, "memoryminimum": int},
    "vm": {"max_last_backup": int},
}


config = confuse.LazyConfig("pvecontrol", __name__)


def set_config(cluster_name):
    validconfig = config.get(configtemplate)
    logging.debug("configuration is %s", validconfig)

    # FIXME trouver une methode plus clean pour recuperer la configuration du bon cluster
    # Peut etre rework la configuration completement avec un dict
    clusterconfig = False
    for c in validconfig.clusters:
        if c.name == cluster_name:
            clusterconfig = c
    if not clusterconfig:
        print("No such cluster %s", cluster_name)
        sys.exit(1)
    logging.debug("clusterconfig is %s", clusterconfig)

    for k, v in validconfig.node.items():
        clusterconfig.node[k] = clusterconfig.node[k] if clusterconfig.node.get(k) else v

    for k, v in validconfig.sanitycheck.items():
        clusterconfig.sanitycheck[k] = clusterconfig.sanitycheck[k] if clusterconfig.sanitycheck.get(k) else v

    return clusterconfig
