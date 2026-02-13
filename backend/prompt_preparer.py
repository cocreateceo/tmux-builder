"""
Prompt Preparer Module

Prepares prompts and writes them to disk following SmartBuild pattern.
Returns instruction text that tells Claude where to read the prompt.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple

from config import get_prompts_dir, get_output_dir

logger = logging.getLogger(__name__)


def prepare_echo_test_prompt(session_id: str, message: str) -> Tuple[str, Path, Path]:
    """
    Prepare a simple echo test prompt.

    This is the simplest job type for testing the file-based I/O pattern.

    Args:
        session_id: Session ID
        message: Message to echo

    Returns:
        Tuple of (instruction_text, prompt_file_path, output_file_path)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Get directories
    prompts_dir = get_prompts_dir(session_id)
    output_dir = get_output_dir(session_id)

    # File paths
    prompt_filename = f"echo_test_{timestamp}.txt"
    output_filename = f"echo_output_{timestamp}.txt"

    prompt_path = prompts_dir / prompt_filename
    output_path = output_dir / output_filename

    # Build full prompt
    full_prompt = f"""# Echo Test Prompt

You are testing the file-based I/O pattern for tmux-builder.

## Task:
Please read this message and write it back to the output file:

**Message to echo:**
{message}

## Output Instructions:
Write the following to {output_path}:

```
Echo Test Response
==================
Original message: {message}
Timestamp: {datetime.now().isoformat()}
Status: SUCCESS
```

Please write this output now and confirm when done.
"""

    # Write prompt to disk
    logger.info(f"Writing prompt to: {prompt_path}")
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(full_prompt)

    # Build instruction (what gets sent to Claude)
    instruction = f"Please read and process the prompt file at {prompt_path}. Write your output to {output_path}."

    logger.info(f"Prepared echo test prompt. Output will be at: {output_path}")

    return instruction, prompt_path, output_path


def prepare_file_analysis_prompt(session_id: str, file_path: str) -> Tuple[str, Path, Path]:
    """
    Prepare a file analysis prompt.

    Args:
        session_id: Session ID
        file_path: Path to file to analyze

    Returns:
        Tuple of (instruction_text, prompt_file_path, output_file_path)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Get directories
    prompts_dir = get_prompts_dir(session_id)
    output_dir = get_output_dir(session_id)

    # File paths
    prompt_filename = f"file_analysis_{timestamp}.txt"
    output_filename = f"analysis_output_{timestamp}.md"

    prompt_path = prompts_dir / prompt_filename
    output_path = output_dir / output_filename

    # Read file to analyze
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        file_content = f"[Error reading file: {e}]"

    # Build full prompt
    full_prompt = f"""# File Analysis Prompt

You are analyzing a file for tmux-builder.

## File Information:
- Path: {file_path}
- Analysis Time: {datetime.now().isoformat()}

## File Content:
```
{file_content}
```

## Analysis Task:
Please analyze this file and provide:
1. File type and language (if code)
2. Summary of contents
3. Key observations
4. Any issues or suggestions

## Output Instructions:
Write your analysis in Markdown format to {output_path}.

Use this structure:
```markdown
# File Analysis Report

**File:** {file_path}
**Analyzed:** {datetime.now().isoformat()}

## File Type
[Your analysis here]

## Summary
[Your analysis here]

## Key Observations
[Your analysis here]

## Recommendations
[Your analysis here]
```

Please write this analysis now.
"""

    # Write prompt to disk
    logger.info(f"Writing prompt to: {prompt_path}")
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(full_prompt)

    # Build instruction
    instruction = f"Please read and process the prompt file at {prompt_path}. Write your analysis to {output_path}."

    logger.info(f"Prepared file analysis prompt. Output will be at: {output_path}")

    return instruction, prompt_path, output_path


def prepare_generic_prompt(
    session_id: str,
    prompt_text: str,
    job_type: str = "generic"
) -> Tuple[str, Path, Path]:
    """
    Prepare a generic prompt.

    Args:
        session_id: Session ID
        prompt_text: The full prompt text
        job_type: Type of job (for naming files)

    Returns:
        Tuple of (instruction_text, prompt_file_path, output_file_path)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Get directories
    prompts_dir = get_prompts_dir(session_id)
    output_dir = get_output_dir(session_id)

    # File paths
    prompt_filename = f"{job_type}_{timestamp}.txt"
    output_filename = f"{job_type}_output_{timestamp}.txt"

    prompt_path = prompts_dir / prompt_filename
    output_path = output_dir / output_filename

    # Add output instructions to prompt
    full_prompt = f"""{prompt_text}

## Output Instructions:
Please write your complete response to: {output_path}

When done, ensure the file is written and contains your full response.
"""

    # Write prompt to disk
    logger.info(f"Writing prompt to: {prompt_path}")
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(full_prompt)

    # Build instruction
    instruction = f"Please read and process the prompt file at {prompt_path}. Write your output to {output_path}."

    logger.info(f"Prepared {job_type} prompt. Output will be at: {output_path}")

    return instruction, prompt_path, output_path
