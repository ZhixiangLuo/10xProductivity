# Project Idea

10xProductivity is the public, open-source home for reusable AI productivity infrastructure.

The goal is to help someone download the repo, connect their own tools, and build a useful personal AI assistant on their own machine. The repo should contain general patterns, setup guides, skills, workflows, and connection recipes that can work for many people without inheriting the maintainer's private context.

## Relationship To Private Incubation

A private workspace is where personal workflows can be incubated, tested, and refined against real work before they are generalized.

10xProductivity is the public repo. It receives only the parts of that private work that have been generalized enough for external users.

This means private spaces can contain personal facts, diary entries, local machine assumptions, employer-specific links, private credentials workflows, rough experiments, and opinionated personal routines. 10xProductivity should not.

## Promotion Criteria

A capability can move from private incubation to 10xProductivity when it is:

- **General:** Useful beyond one person's exact job, machine, or private workflow.
- **Depersonalized:** Free of names, diary content, employer-specific context, private URLs, tokens, cookies, local-only paths, and personal preferences that do not belong in an open-source repo.
- **Configurable:** Uses environment variables, config files, or documented placeholders instead of hardcoded private values.
- **Documented:** Explains what it does, when to use it, how to set it up, and how to verify it.
- **Tested in practice:** Proven through real personal use before being promoted, with at least a small smoke test or verification path for new users.

## What Belongs Here

- Tool connection recipes that teach agents how to use common work tools.
- Reusable workflows that combine connected tools into practical outcomes.
- Agent skills that teach repeatable work patterns in a portable way.
- Local-first automation patterns that users can run on their own computers.
- Setup docs that assume a new user is starting from scratch.

## What Does Not Belong Here

- Private diary or memory bank content.
- Personal identity, preferences, or biographical facts.
- Employer-specific or internal-company instructions.
- Secrets, tokens, cookies, or authenticated session state.
- Hardcoded paths that only work on the maintainer's machine.
- Experimental workflows that have not survived real use yet.

## Current Direction

The repo starts from tool connections and grows upward into skills, workflows, and local automation. Private workspaces remain the proving ground. 10xProductivity is where the reusable, sanitized, externally useful pieces land after they have earned their way out of private incubation.
