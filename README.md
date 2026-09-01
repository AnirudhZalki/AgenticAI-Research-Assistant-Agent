# Agentic AI: Research Assistant Agent

This repository contains the implementation of the **Research Assistant Agent**, built using the **14-Lab Method**. The system transforms manual academic research workflows into a multi-agent, human-gated pipeline.

> **Guiding Principle:** Agents draft and flag; a named human approves. No consequential action is taken autonomously.

## Current Status: Phase A (Foundations)
**Completed: Labs 1 & 2 (Week 1 Milestone)**
We have successfully built the initial `apniLeap AURA Coordinator` loop and the base specialist workers.

* **Lab 1 (Agent vs Chatbot):** Established the `clarify → plan → revise` loop. The agent refuses to answer vague prompts and instead builds a locked, human-approved research plan.
* **Lab 2 (Tool-Using Agent):** Replaced LLM hallucinations with real data tools. The agent reads from mock scholarly databases (`corpus.json`, `library.json`) and strictly validates all retrieved data.

## 👥 Team Roles & Contributions

The workload was distributed to mirror the agentic node graph:

* **Goutam (Understand & Features):** Built `goutam_clarify.py`. Handles the initial state evaluation and loops to ask the user for missing constraints (Topic, Venue, Collaborators, Deadline).
* **Karthik (Plan & Revise):** Built `karthik_plan.py`. Generates a structured research outline based on gathered constraints and runs a revision loop until the human authority approves.
* **Anirudh (Search & Tools):** Built `anirudh_search.py` and the mock `data/` layer. Created the typed tools (`read_corpus`, `read_library`) that connect the agent to external knowledge bases.
* **Harshad (Verify & Grounding):** Built `harshad_verify.py`. The hard validation gate. Ensures the agent only uses data outputted by Anirudh's tools and prevents hallucinated citations.

## Project Structure

```text
research_agent/
├── data/
│   ├── corpus.json          # Mock global scholarly database
│   └── library.json         # Mock researcher personal library
├── anirudh_search.py        # Tool layer for data retrieval
├── goutam_clarify.py        # Intent and parameter clarification
├── harshad_verify.py        # Output validation and grounding
├── karthik_plan.py          # Plan blueprint generation
├── main.py                  # The apniLeap AURA Coordinator
└── README.md                # Project documentation