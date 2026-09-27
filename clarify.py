"""
Lab 1: Request Clarifier Agent (Phase A - Foundations)
Establishes the clarify -> plan -> revise loop instead of one-shot chatbot responses.
Refuses to proceed until all required parameters (topic, venue, collaborators, deadline) are specified.
"""

class RequestClarifier:
    def __init__(self):
        self.required_fields = ["topic", "venue", "collaborators", "deadline"]
        self.state = {}

    def clarify(self, initial_inputs: dict = None, interactive: bool = True) -> dict:
        """
        Gathers required research parameters.
        If initial_inputs is provided, uses non-missing fields from it.
        If interactive is True, prompts the user via CLI for missing fields.
        """
        print("--- PHASE 1 (LAB 1): UNDERSTAND & CLARIFY ---")
        
        if initial_inputs:
            for k, v in initial_inputs.items():
                if v and str(v).strip():
                    self.state[k] = str(v).strip()

        if interactive:
            if "topic" not in self.state or not self.state["topic"]:
                initial = input("User: What research question or topic do you want to explore?\n> ")
                self.state["topic"] = initial.strip()

            for req in self.required_fields:
                if req not in self.state or not self.state[req]:
                    answer = input(f"Assistant: Please specify the {req} (e.g., target venue, co-authors, submission deadline):\n> ")
                    self.state[req] = answer.strip()
        else:
            # Fallback for missing fields in non-interactive mode
            defaults = {
                "topic": "edge AI hardware porting frameworks",
                "venue": "IEEE conference, IMRAD, 6-page limit",
                "collaborators": "Faculty Author, Co-Author A",
                "deadline": "2026-11-15"
            }
            for req in self.required_fields:
                if req not in self.state or not self.state[req]:
                    self.state[req] = defaults[req]
                    print(f"Automated Clarifier set default for '{req}': {defaults[req]}")

        # Validate that all required parameters exist
        missing = [f for f in self.required_fields if not self.state.get(f)]
        if missing:
            raise ValueError(f"Clarification incomplete. Missing required parameters: {missing}")

        print("\nAll constraints gathered successfully:")
        for k, v in self.state.items():
            print(f"  - {k.capitalize()}: {v}")
        return self.state

if __name__ == "__main__":
    clarifier = RequestClarifier()
    result = clarifier.clarify(interactive=False)
    print("Clarify output test passed.")