from pvecontrol.utils import print_task, print_tableoutput, filter_keys


def action_tasklist(proxmox, args):
  tasks = [ filter_keys(t.__dict__, ['upid', 'exitstatus', 'node', 'type', 'starttime', 'endtime', 'runningstatus', 'description']) for t in proxmox.tasks ]
  print_tableoutput(tasks, sortby=args.sort_by)

def action_taskget(proxmox, args):
  print_task(proxmox, args.upid, args.follow, args.wait, show_logs = True)
