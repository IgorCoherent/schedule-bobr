def initials_for_name(display_name: str) -> str:
    parts = display_name.strip().split()
    if not parts:
        return "?"
    if len(parts) == 1:
        s = parts[0]
        return (s[:2] if len(s) >= 2 else s).upper()
    return (parts[0][0] + parts[-1][0]).upper()


def placeholder_color(participant_id: int) -> str:
    hues = [
        "#e8f0f6",
        "#eef3ea",
        "#f5ebe8",
        "#ebe8f5",
        "#e8f5f0",
        "#f5f0e8",
    ]
    return hues[participant_id % len(hues)]
