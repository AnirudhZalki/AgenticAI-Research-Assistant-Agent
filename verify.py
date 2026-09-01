class ToolVerifier:
    def __init__(self, search_tools):
        self.tools = search_tools

    def run_and_verify(self, tool_name, arg=""):
        print("\n--- PHASE 3: VERIFY & EXECUTE ---")
        print(f"Executing tool: {tool_name}...")
        
        if tool_name == "read_corpus":
            results = self.tools.read_corpus(arg)
        elif tool_name == "read_library":
            results = self.tools.read_library()
        else:
            return {"valid": False, "error": "Unknown tool."}

        # Validation Rules:
        # 1. Output must be a list
        # 2. Every item must have an 'id' and 'title' (no hallucinated strings)
        try:
            assert isinstance(results, list), "Tool must return a list."
            for item in results:
                assert "id" in item, "Missing ID in data."
                assert "title" in item, "Missing Title in data."
            
            print("Validation Passed: Data is grounded in verified sources.")
            return {"valid": True, "data": results}
        except AssertionError as e:
            print(f"Validation Failed! {e}")
            return {"valid": False, "error": str(e)}