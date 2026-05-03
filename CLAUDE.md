# Coding
- always follow recommended practices for the frameworks you are using. Do not guess what they are search them if needed.
- Your goal is light weight and quality software. Use frameworks correctly, avoid workaround solutions and follow best practices.
- Always go all the way. Do everything whenever a feature is created design it, implement it, test it to verify that it works.  

# Project Overview
- this is an Agentic management system. To build a custom orchestrated team of hermes agents that can self learn over time like employees can and improve.

# Important notes
- The `AGENTS.md` file in this project is for the agents in the project not for the agent building the project. If you are assigned a task to edit the agentic management system itself and are not doing anything related to the project the AGENTS.md file described please ignore this file!
- sub-agent hermes configurations are located within `/agents`
- only the hermes orchestrator can be prompted. Essentially this will be the hermes profile presented to the user as the agent to prompt whenever they want to have a task done. Expose only this agent and not the subagents.

# Architecture
- The docker compose is designed to build the orchestrator image to get the process started
essentially the architecture is simple. One orchestrator many sub agents
- The orchestrator is managing the sub-agents. He creates, deletes, updates, and most importantly delegates tasks to the sub agents.