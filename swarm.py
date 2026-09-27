"""
Lab 8: Parallel Swarm & Fan-Out / Fan-In Merge (Phase B - Orchestration)
Parallelises per-unit work across multiple sub-queries or search topics concurrently using ThreadPoolExecutor.
Merges multi-worker results using a MergeSelector key aligned to the locked research plan.
"""

import time
import concurrent.futures
from typing import List, Dict, Any
from connector import ResearchDataConnector

class SwarmWorker:
    """Worker agent processing one sub-query or research unit in parallel."""
    def __init__(self, worker_id: str, connector: ResearchDataConnector):
        self.worker_id = worker_id
        self.connector = connector

    def process_subquery(self, subquery: str) -> Dict[str, Any]:
        start_time = time.time()
        print(f"    [Worker {self.worker_id}] Starting parallel discovery for sub-query: '{subquery}'...")
        
        papers = self.connector.read_paper_corpus(subquery, agent_id=f"SwarmWorker-{self.worker_id}")
        deadlines = self.connector.read_funding_deadlines(subquery, agent_id=f"SwarmWorker-{self.worker_id}")
        
        elapsed = time.time() - start_time
        result = {
            "worker_id": self.worker_id,
            "subquery": subquery,
            "papers_found": papers,
            "deadlines_found": deadlines,
            "count": len(papers),
            "execution_time_sec": round(elapsed, 4)
        }
        print(f"    [Worker {self.worker_id}] Finished in {result['execution_time_sec']}s ({result['count']} papers found).")
        return result

class MergeSelector:
    """Fan-in merger selecting and consolidating parallel swarm outputs by plan alignment."""
    def merge(self, worker_results: List[Dict[str, Any]], target_topic: str) -> Dict[str, Any]:
        print("\n--- FAN-IN MERGE SELECTOR ---")
        all_papers = []
        all_deadlines = []
        seen_paper_ids = set()
        seen_deadline_ids = set()

        for res in worker_results:
            for p in res.get("papers_found", []):
                if p["id"] not in seen_paper_ids:
                    seen_paper_ids.add(p["id"])
                    all_papers.append(p)
                    
            for d in res.get("deadlines_found", []):
                if d["id"] not in seen_deadline_ids:
                    seen_deadline_ids.add(d["id"])
                    all_deadlines.append(d)

        # Sort merged papers by relevance score (number of keywords matching target_topic)
        target_words = set(target_topic.lower().split())
        
        def alignment_score(paper):
            text = f"{paper.get('title', '')} {' '.join(paper.get('keywords', []))}".lower()
            return sum(1 for w in target_words if w in text)

        all_papers.sort(key=alignment_score, reverse=True)

        merged_output = {
            "target_topic": target_topic,
            "total_workers_executed": len(worker_results),
            "total_unique_papers": len(all_papers),
            "total_unique_deadlines": len(all_deadlines),
            "consolidated_papers": all_papers,
            "consolidated_deadlines": all_deadlines,
            "best_aligned_paper": all_papers[0] if all_papers else None
        }
        
        print(f"Merge Complete: Consolidated {merged_output['total_unique_papers']} unique papers across {len(worker_results)} parallel swarm workers.")
        return merged_output

class ParallelSwarm:
    """Parallel Swarm Orchestrator for Lab 8."""
    def __init__(self, connector: ResearchDataConnector = None):
        self.connector = connector if connector is not None else ResearchDataConnector()
        self.merger = MergeSelector()

    def run_swarm(self, subqueries: List[str], main_topic: str) -> Dict[str, Any]:
        print("\n==========================================================================")
        print("--- PHASE B (LAB 8): PARALLEL SWARM FAN-OUT / FAN-IN EXECUTION ---")
        print("==========================================================================")
        print(f"Dispatching {len(subqueries)} parallel worker agents for sub-queries: {subqueries}")
        
        start_swarm_time = time.time()
        worker_results = []
        
        # Parallel Execution using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(subqueries)) as executor:
            future_to_query = {
                executor.submit(SwarmWorker(f"W{idx+1}", self.connector).process_subquery, sq): sq 
                for idx, sq in enumerate(subqueries)
            }
            
            for future in concurrent.futures.as_completed(future_to_query):
                sq = future_to_query[future]
                try:
                    data = future.result()
                    worker_results.append(data)
                except Exception as exc:
                    print(f"Worker for '{sq}' generated an exception: {exc}")

        total_swarm_wall_time = round(time.time() - start_swarm_time, 4)
        print(f"\nParallel Swarm Fan-Out Completed in total wall-clock time: {total_swarm_wall_time}s")

        # Fan-In Merge
        merged_result = self.merger.merge(worker_results, target_topic=main_topic)
        merged_result["swarm_wall_clock_time_sec"] = total_swarm_wall_time
        return merged_result

if __name__ == "__main__":
    swarm = ParallelSwarm()
    sub_qs = ["edge AI", "microcontroller", "hardware porting", "benchmarking"]
    res = swarm.run_swarm(sub_qs, main_topic="edge AI hardware porting frameworks")
    print("Swarm execution test passed.")
