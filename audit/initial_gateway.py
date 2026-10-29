"""Minimal AI-assisted event-handling example retained for the audit.

This isolated prototype demonstrates two parsing flaws. It is not a complete
first version of the application and is never imported by the running gateway.
"""

def openai_delta(event):
    return event.choices[0].delta.content or ""


def anthropic_usage(previous_output, event):
    if event.type == "message_delta":
        return previous_output + event.usage.output_tokens
    return previous_output
