import logging
import time
import sys
import re
import curses

from prettytable import PrettyTable
from collections import OrderedDict
from humanize import naturalsize
from enum import Enum

class fonts:
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

def terminal_support_colors():
  try:
      _stdscr = curses.initscr()
      curses.start_color()
      if curses.has_colors():
          _num_colors = curses.color_pair(1)
          if curses.COLORS > 0:
              return True
          else:
              return False
      else:
          return False
  except Exception as e:
      return False
  finally:
      curses.endwin()

def teminal_support_utf_8():
  return sys.stdout.encoding.lower() == 'utf-8'

# Pretty output a table from a table of dicts
# We assume all dicts have the same keys and are sorted by key
def print_tableoutput(table, columns=[], sortby=None, filters=[]):
  if len(columns) == 0:
    columns = table[0].keys()
  else:
    table = [ filter_keys(n.__dict__ if hasattr(n, '__dict__') else n, columns) for n in table ]

  do_sort = not sortby is None

  x = PrettyTable()
  x.align = 'l'
  x.field_names = [*table[0].keys(), "sortby"] if do_sort else table[0].keys()

  for line in table:
    if do_sort:
      line["sortby"] = line[sortby]
      if isinstance(line[sortby], Enum):
        line["sortby"] = str(line[sortby])
    for key in ['mem', 'allocatedmem', 'maxmem', 'disk', 'allocateddisk', 'maxdisk'] :
      if key in line:
        line[key] = naturalsize(line[key], binary=True)

  for filter_key, filter_value in filters:
    re_filter = re.compile(filter_value)
    table = [ line for line in table if re_filter.search(str(line[filter_key])) ]

  for line in table:
    x.add_row( line.values() )

  print(x.get_string(sortby="sortby" if do_sort else None, fields=columns))

def filter_keys(input, keys):
  # Filter keys from input dict
  output = OrderedDict()
  for key in keys:
      output[key] = input[key]
  return output

def print_taskstatus(task):
  columns = ['upid', 'exitstatus', 'node', 'runningstatus', 'type', 'user', 'starttime']
  print_tableoutput([task], columns)

def print_task(proxmox, upid, follow = False, wait = False):
  task = proxmox.find_task(upid)
  logging.debug("Task: %s", task)
  # Vanished tasks don't have any more information available in the API
  if task.vanished():
    print_taskstatus(task)
    return

  log = task.log(limit=0)
  logging.debug("Task Log: %s", log)

  if task.running():
    if follow:
      print_taskstatus(task)
      lastline = 0
      print("log output, follow mode")
      while task.running():
        task.refresh()
        # logging.debug("Task status: %s", status)
        log = task.log(limit=0, start=lastline)
        logging.debug("Task Log: %s", log)
        for line in log:
          print("%s"%line['t'])
          if line['n'] > lastline:
            lastline = line['n']
        time.sleep(1)
    elif wait:
      print_taskstatus(task)
      while task.running():
        task.refresh()
        print(".", end="")
        sys.stdout.flush()
        time.sleep(1)
      print("")
  elif not wait:
    print_tableoutput([{"log output": task.decode_log()}])

  print_taskstatus(task)
