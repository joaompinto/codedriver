def parse_file_changes(content: str) -> dict:
    """Parse Claude's response into a dictionary of file changes"""
    file_changes = {}
    current_file = None
    current_content = []

    for line in content.split("\n"):
        # Handle file headers (both with and without markdown links)
        if line.startswith("### [") and "]" in line:
            if current_file and current_content:
                file_changes[current_file] = "\n".join(current_content).strip()
            current_file = line[4:].strip("[]")  # Remove ### [ and ]
            current_content = []
            continue
