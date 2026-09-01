class PlanGenerator:
    def propose_plan(self, state):
        print("\n--- PHASE 2: PLAN ---")
        plan = {
            "Title": f"Research on {state['topic']}",
            "Venue": state['venue'],
            "Deadline": state['deadline'],
            "Sections": ["1. Introduction", "2. Literature Review", "3. Methodology", "4. Conclusion"]
        }
        return self.revise_plan(plan)

    def revise_plan(self, plan):
        while True:
            print("\nCurrent Plan:")
            for key, value in plan.items():
                print(f"{key}: {value}")
            
            feedback = input("\nAssistant: Does this look good? (Type 'yes' to approve, or type a new section to add it)\n> ")
            if feedback.lower() in ['yes', 'y', 'looks good']:
                print("Plan approved by user.")
                return plan
            else:
                print("Assistant: Adding your revision...")
                plan["Sections"].append(f"{len(plan['Sections']) + 1}. {feedback}")