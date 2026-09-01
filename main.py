from clarify import RequestClarifier
from plan import PlanGenerator
from search import SearchTools
from verify import ToolVerifier

def run_research_assistant():
    print("Starting Research Assistant Agent (Labs 1 & 2)\n")
    
    # 1. Initialize Everyone's Modules
    clarifier = RequestClarifier()
    planner = PlanGenerator()
    tools = SearchTools()
    verifier = ToolVerifier(tools)
    
    # 2.(Clarify Request)
    completed_state = clarifier.clarify()
    
    # 3. (Propose & Revise Plan)
    locked_plan = planner.propose_plan(completed_state)
    
    # 4.(Tool Execution & Validation)
    # We extract a keyword from the user's topic to search the corpus
    search_keyword = completed_state["topic"].split()[0] 
    
    report = verifier.run_and_verify("read_corpus", search_keyword)
    
    if report["valid"]:
            print("\n" + "="*40)
            print(" FINAL APPROVED RESEARCH BRIEF")
            print("="*40)
            print(f"Title: {locked_plan['Title']}")
            print(f"Venue: {locked_plan['Venue']}  |  Deadline: {locked_plan['Deadline']}\n")
            
            print("Outline:")
            for section in locked_plan['Sections']:
                print(f"  {section}")
                
            print("\nVerified Evidence / Citations:")
            for paper in report["data"]:
                print(f"  - [{paper['id']}] {paper['title']}")
            print("="*40 + "\n")
    else:
        print("\nPipeline stopped due to validation failure.")

if __name__ == "__main__":
    run_research_assistant()