import base64
import json
import os
import re
from datetime import datetime, timezone

from .agent import Step


def save_run(
    task: str,
    steps: list[Step],
    output_dir: str = "results",
) -> str:
    """Save all run data at:
        <output_dir>/<timestamp>/
            summary.json (task, steps, actions, reasoning)
            screenshots/
                step_00.png
                step_01.png
                ...

    Return the path to the created run directory.
    """
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S"
    )
    run_dir = os.path.join(output_dir, timestamp)
    screenshots_dir = os.path.join(run_dir, "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    step_records = []
    for i, step in enumerate(steps):
        img_path = os.path.join(
            screenshots_dir, f"step_{i:02d}.png"
        )
        with open(img_path, "wb") as f:
            f.write(base64.b64decode(step.state.screenshot_b64))

        reasoning_match = re.search(
            r"<reasoning>(.*?)</reasoning>",
            step.response,
            re.DOTALL,
        )
        reasoning = (
            reasoning_match.group(1).strip()
            if reasoning_match
            else ""
        )

        step_records.append(
            {
                "step": i,
                "url": step.state.url,
                "screenshot": f"screenshots/step_{i:02d}.png",
                "llm_response": step.response,
                "reasoning": reasoning,
                "action": step.action.name,
                "action_args": step.action.args,
                "error": step.action.error,
            }
        )

    summary = {
        "task": task,
        "timestamp": timestamp,
        "total_steps": len(steps),
        "steps": step_records,
    }

    summary_path = os.path.join(run_dir, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    return run_dir
