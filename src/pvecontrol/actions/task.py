from pvecontrol.utils import print_task, print_tableoutput, filter_keys


def action_tasklist(proxmox, args):
  print_tableoutput(proxmox.tasks, columns=args.columns, sortby=args.sort_by, filters=args.filter)

def action_taskget(proxmox, args):
  print_task(proxmox, args.upid, args.follow, args.wait, show_logs = True)
