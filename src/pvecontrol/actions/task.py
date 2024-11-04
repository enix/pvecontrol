from pvecontrol.utils import print_task, print_tableoutput, filter_keys


def action_tasklist(proxmox, args):
  tasks = [ filter_keys(t.__dict__, ['upid', 'exitstatus', 'node', 'type', 'starttime', 'endtime', 'runningstatus', 'description']) for t in proxmox.tasks ]
  print_tableoutput(tasks, sortby='starttime')

def action_taskget(proxmox, args):
  print_task(proxmox, args.upid, args.follow)
