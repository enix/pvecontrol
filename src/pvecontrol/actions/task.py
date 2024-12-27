from pvecontrol.utils import print_task, print_output


def action_tasklist(proxmox, args):
    print_output(
        proxmox.tasks,
        columns=args.columns,
        sortby=args.sort_by,
        filters=args.filter,
        output=args.output,
    )


def action_taskget(proxmox, args):
    print_task(proxmox, args.upid, args.follow, args.wait)
