from pvecontrol.utils import _print_task, _print_tableoutput, _filter_keys


def action_tasklist(proxmox, args):
  tasks = [ _filter_keys(t.__dict__, ['upid', 'exitstatus', 'node', 'type', 'starttime', 'endtime', 'runningstatus', 'description']) for t in proxmox.tasks ]
  _print_tableoutput(tasks, sortby='starttime')

def action_taskget(proxmox, args):
  _print_task(proxmox, args.upid, args.follow)
