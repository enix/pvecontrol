import logging
import time
import sys

from prettytable import PrettyTable
from collections import OrderedDict
from humanize import naturalsize


# Pretty output a table from a table of dicts
# We assume all dicts have the same keys and are sorted by key
def print_tableoutput(table, sortby=None, filter=[]):
  x = PrettyTable()
  x.align = 'l'
  x.field_names = table[0].keys()
  for line in table:
    for key in ['mem', 'allocatedmem', 'maxmem', 'disk', 'allocateddisk', 'maxdisk'] :
      if key in line:
        line[key] = naturalsize(line[key], binary=True)
    x.add_row( line.values() )
  print(x.get_string(sortby=sortby))

def filter_keys(input, keys):
  # Filter keys from input dict
  output = OrderedDict()
  for key in keys:
      output[key] = input[key]
  return output

def print_taskstatus(task):
  output = [ filter_keys(task.__dict__, ['upid', 'exitstatus', 'node', 'runningstatus', 'type', 'user', 'starttime']) ]
  print_tableoutput(output)

def print_task(proxmox, upid, follow = False, wait = False, show_logs = False):
  task = proxmox.find_task(upid)
  logging.debug("Task: %s", task)
  # Vanished tasks don't have any more information available in the API
  if task.vanished():
    print_taskstatus(task)
    return

  if task.running() and (follow or wait):
    print_taskstatus(task)

  log = task.log(limit=0)
  logging.debug("Task Log: %s", log)
  if task.running() and follow:
    lastline = 0
    print("log output, follow mode")
    while task.running():
      task.refresh()
#      logging.debug("Task status: %s", status)
      log = task.log(limit=0, start=lastline)
      logging.debug("Task Log: %s", log)
      for line in log:
        print("%s"%line['t'])
        if line['n'] > lastline:
          lastline = line['n']
      time.sleep(1)

  if task.running() and wait:
    while task.running():
      task.refresh()
      print(".", end="")
      sys.stdout.flush()
      time.sleep(1)
    print("")

  if (show_logs and not follow) or not (task.running() or follow or wait):
    print_tableoutput([{"log output": task.decode_log()}])

  print_taskstatus(task)
