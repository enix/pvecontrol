import confuse
import logging
import sys


configtemplate = {
    'clusters': confuse.Sequence(
        {
            'name': str,
            'host': str,
            'user': str,
            'password': str,
        }
    ),
    'node': {
        'cpufactor': float,
        'memoryminimum': int
      }
}


config = confuse.LazyConfig('pvecontrol', __name__)

validconfig = None

def set_config(cluster_name):
  global validconfig
  validconfig = config.get(configtemplate)
  logging.debug('configuration is %s'%validconfig)

  # FIXME trouver une methode plus clean pour recuperer la configuration du bon cluster
  # Peut etre rework la configuration completement avec un dict
  clusterconfig = False
  for c in validconfig.clusters:
    if c.name == cluster_name:
      clusterconfig = c
  if not clusterconfig:
    print('No such cluster %s'%cluster_name)
    sys.exit(1)
  logging.debug('clusterconfig is %s'%clusterconfig)
  return clusterconfig


def get_config():
  return validconfig
