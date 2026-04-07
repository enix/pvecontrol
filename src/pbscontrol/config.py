import logging
import sys
import confuse

configtemplate = {
    "servers": confuse.Sequence(  # pylint: disable=abstract-class-instantiated
        {
            "name": str,
            "host": str,
            "user": str,
            "password": confuse.Optional(str, None),
            "token_name": confuse.Optional(str, None),
            "token_value": confuse.Optional(str, None),
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
            "port": confuse.Optional(int, default=8007),
            "timeout": confuse.Optional(int, default=60),
            "ssl_verify": confuse.Optional(bool, False),
        }
    ),
}


config = confuse.LazyConfig("pbscontrol", __name__)


def set_config(server_name):
    validconfig = config.get(configtemplate)
    logging.debug("configuration is %s", validconfig)

    serverconfig = False
    for s in validconfig.servers:
        if s.name == server_name:
            serverconfig = s
    if not serverconfig:
        logging.error('No such server "%s"', server_name)
        sys.exit(1)
    logging.debug("serverconfig is %s", serverconfig)

    return serverconfig
