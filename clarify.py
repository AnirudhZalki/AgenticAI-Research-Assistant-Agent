class RequestClarifier:
    def __init__(self):
        self.required = ["topic", "venue", "collaborators", "deadline"]
        self.state = {}

    def clarify(self):
        print("--- PHASE 1: UNDERSTAND ---")
        # Ask for initial prompt
        initial = input("User: What do you want to research? \n> ")
        self.state["topic"] = initial
        
        # Loop through missing requirements
        for req in self.required:
            if req not in self.state or not self.state[req]:
                answer = input(f"Assistant: Please provide the {req}:\n> ")
                self.state[req] = answer
        
        print("\nAll constraints gathered!")
        return self.state