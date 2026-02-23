from .agent import WebNavAgent
from .llm import call_llm
from .save_results import save_run

if __name__ == "__main__":
    task = input("Task: ").strip()
    agent = WebNavAgent(llm_fn=call_llm, headless=False)
    steps = agent.run(task)
    run_dir = save_run(task, steps)
    print(f"\nResults saved to: {run_dir}")
