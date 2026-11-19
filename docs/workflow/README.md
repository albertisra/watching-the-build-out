# Workflow

The project was built with Claude Code as an orchestrator that delegates tasks to specialised subagents.
`claude-agents/` holds a copy of their definitions (role, tools, rules). The working copies live in
`.claude/agents/`, which is not tracked here; this copy may lag behind them.
