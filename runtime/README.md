# Runtime

Runtime contains local execution machinery. It is not the product brain.

Workflows define what useful work should happen. Triggers detect that something happened. Tool connections read and write external systems. Runtime provides the laptop-local mechanics that let those pieces run:

- coding-agent CLI invocation
- scheduling entry points
- state and dedupe files under `TENX_PRIVATE_DIR/tmp/`
- reply logging
- lightweight trigger-to-workflow hosting

```text
trigger -> runtime host -> workflow -> tool connections -> output
cron/launchd -> runtime scheduling -> workflow -> tool connections -> output
```

## Contents

```text
agent_clients/       Cursor / Claude / Codex invocation helpers
scheduling/          Cron/launchd-friendly entry points and run state
events.py            Normalized event shape emitted by triggers
host.py              Lightweight trigger-to-workflow dispatcher
replies.py           Reply bridge for invoked agents
env.py               Public/private env loading helpers
```

Keep this layer thin. If logic becomes reusable work guidance, move it to `workflows/`. If it accesses a specific external system, move it to `tool_connections/`. If it detects an event, move it to `triggers/`.
