"""Case 5 - Agentic Controller: Groq Cloud API Integration

Objective: Verify that the agentic controller correctly connects to the Groq
Cloud API, sends a formatted prompt, and receives a parseable LLM response,
addressing Objective O3.

Action:
  1. Set up the Groq API client with a valid API key.
  2. Send a single reasoning prompt to the Llama-3.1-8B-Instruct model via
     the Groq endpoint.
  3. Verify the response is received and contains parseable content.

Expected Result:
  The API returns a response within 30 seconds. The response content is
  non-empty and can be parsed by the action extraction logic. No
  authentication or connection errors are raised.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_engine.llm_interface import LLMEngine

def run_case5():
    print("\n--- Agentic Controller: Groq Cloud API Integration ---")

    # Step 1: Initialise LLM engine (reads GROQ_API_KEY from .env)
    llm = LLMEngine()
    print(f"  Provider   : {llm.provider}")
    print(f"  Model      : {llm.model}")

    # Step 2: Send a single reasoning prompt
    prompt = (
        "You are a log analysis assistant using ReAct reasoning.\n"
        "Log entry: '081109 203518 143 ERROR dfs.DataNode$DataXceiver: "
        "Got exception while serving blk_-1608999687919862906'\n\n"
        "Based on this log, what action should be taken?\n"
        "Respond with one of: RETRIEVE, ANALYZE, FINALIZE\n"
        "Then explain your reasoning in one sentence."
    )

    print(f"\n  Prompt sent: {prompt[:100]}...")

    t0 = time.perf_counter()
    response = llm.generate(prompt, max_tokens=200, temperature=0.1)
    elapsed_s = time.perf_counter() - t0

    # Step 3: Inspect response
    print(f"\n  Response time      : {elapsed_s:.2f} seconds")
    has_error = response.content and response.content.startswith('Error:')
    print(f"  Error              : {response.content if has_error else None}")
    print(f"  Response content   : {response.content[:200] if response.content else 'None'}")

    # Parse action from response
    action_found = None
    if response.content and not response.content.startswith('Error:'):
        content_upper = response.content.upper()
        for action in ['RETRIEVE', 'ANALYZE', 'FINALIZE']:
            if action in content_upper:
                action_found = action
                break

    print(f"  Action extracted   : {action_found}")
    print(f"  Within 30s limit   : {'YES' if elapsed_s < 30 else 'NO'} ({elapsed_s:.2f}s)")

    # Assertions
    assert response.content and not response.content.startswith('Error:'), \
        f"API returned error: {response.content}"
    assert len(response.content) > 0, "Response content is empty"
    assert elapsed_s < 30, f"Response took {elapsed_s:.2f}s, expected < 30s"
    assert action_found is not None, \
        f"Could not extract action from response: {response.content}"

    print("\n  RESULT : Test PASSED")
    print("  All assertions passed: valid response received, parseable content, "
          f"action={action_found}, time={elapsed_s:.2f}s, model={llm.model}")

if __name__ == '__main__':
    run_case5()
