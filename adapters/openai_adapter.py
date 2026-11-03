from __future__ import annotations
import json, os

class OpenAIAdapter:
    def __init__(self, model=None):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = model or os.environ["OPENAI_MODEL"]

    def generate_structured(self, system, messages, schema, schema_name):
        response = self.client.responses.create(
            model=self.model,
            instructions=system,
            input=messages,
            text={"format":{
                "type":"json_schema",
                "name":schema_name,
                "schema":schema,
                "strict":True
            }},
        )
        return json.loads(response.output_text)
