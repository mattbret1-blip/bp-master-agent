from __future__ import annotations
import os

class AnthropicAdapter:
    def __init__(self, model=None):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model or os.environ["ANTHROPIC_MODEL"]

    def generate_structured(self, system, messages, schema, schema_name):
        response = self.client.messages.create(
            model=self.model,
            max_tokens=7000,
            system=system,
            messages=messages,
            tools=[{
                "name":schema_name,
                "description":"Return the required structured object.",
                "input_schema":schema,
                "strict":True
            }],
            tool_choice={"type":"tool","name":schema_name},
        )
        for block in response.content:
            if getattr(block,"type",None) == "tool_use":
                return block.input
        raise RuntimeError("Anthropic did not return the required structured object.")
