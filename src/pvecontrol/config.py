import logging
import sys
import confuse

configtemplate = {
    "clusters": confuse.Sequence(  # pylint: disable=abstract-class-instantiated
        {
            "name": str,
            "host": str,
            "user": str,
            "password": confuse.Optional(str, None),
            "proxy_certificate": confuse.Optional(
                confuse.OneOf(
                    [
                        str,
                        {
                            "cert": str,
                            "key": str,
                        },
                    ]
                ),
                None,
            ),
            "token_name": confuse.Optional(str, None),
            "token_value": confuse.Optional(str, None),
            "timeout": confuse.Optional(int, default=60),
            "ssl_verify": confuse.Optional(bool, False),
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


def _load_config():
    try:
        validconfig = config.get(configtemplate)
    except confuse.ConfigReadError as e:
        logging.error("Cannot read configuration file: %s", e)
        sys.exit(1)
    except confuse.NotFoundError as e:
        logging.error("Missing required configuration key: %s", e)
        sys.exit(1)
    except confuse.ConfigError as e:
        logging.error("Invalid configuration: %s", e)
        sys.exit(1)
    return validconfig


def list_clusters():
    validconfig = _load_config()
    return [c.name for c in validconfig.clusters]


def set_config(cluster_name):
    validconfig = _load_config()
    logging.debug("configuration is %s", validconfig)

    # FIXME trouver une methode plus clean pour recuperer la configuration du bon cluster
    # Peut etre rework la configuration completement avec un dict
    matches = [c for c in validconfig.clusters if c.name.lower() == cluster_name.lower()]
    if not matches:
        logging.error('No such cluster "%s"', cluster_name)
        sys.exit(1)
    if len(matches) > 1:
        logging.error('Ambiguous cluster name "%s": matches %s', cluster_name, [c.name for c in matches])
        sys.exit(1)
    clusterconfig = matches[0]
    logging.debug("clusterconfig is %s", clusterconfig)

    for k, v in validconfig.node.items():
        clusterconfig.node[k] = clusterconfig.node[k] if clusterconfig.node.get(k) else v

    for k, v in validconfig.vm.items():
        clusterconfig.vm[k] = clusterconfig.vm[k] if clusterconfig.vm.get(k) else v

    return clusterconfig
