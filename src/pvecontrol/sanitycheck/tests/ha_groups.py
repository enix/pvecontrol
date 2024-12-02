from pvecontrol.sanitycheck.checks import Check, CheckType, CheckMessage, CheckCode


# Check HA groups
def get_checks(sanity):
  check = Check(CheckType.HA, "Check HA groups")
  for group in sanity._ha['groups']:
    num_nodes = len(group['nodes'].split(","))
    if num_nodes < 2:
      msg = f"Group {group['group']} contain only {num_nodes} node"
      check.add_messages(CheckMessage(CheckCode.WARN, msg))

  if not check.messages:
    msg = "HA Group checked"
    check.add_messages(CheckMessage(CheckCode.OK, msg))
  return [check]
