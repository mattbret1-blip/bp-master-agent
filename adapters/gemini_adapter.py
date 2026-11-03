from __future__ import annotations
import json, os

class GeminiAdapter:
    def __init__(self, model=None):
        from google import genai
        from google.genai import types
        self._types = types
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.model = model or os.environ["GEMINI_MODEL"]

    def generate_structured(self, system, messages, schema, schema_name):
        contents = [
            self._types.Content(
                role=("user" if m["role"]=="user" else "model"),
                parts=[self._types.Part.from_text(text=m["content"])]
            ) for m in messages
        ]
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=self._types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema
            )
        )
        if getattr(response,"parsed",None) is not None:
            return response.parsed
        return json.loads(response.text)
