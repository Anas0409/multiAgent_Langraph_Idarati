import json
import re

def clean_json_response(content: str) -> dict:
    """
    Cleans LLM response to extract and parse JSON.
    Handles markdown code blocks and extra text.
    """
    if not content:
        return {}

    # Strip DeepSeek-R1 / reasoning model thinking blocks
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    
    # Try direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Try finding JSON block
    # Matches ```json ... ``` or just ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
            
    # Try finding first { and last }
    match = re.search(r"(\{.*\})", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
            
    return {}
