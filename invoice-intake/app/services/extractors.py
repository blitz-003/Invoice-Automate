from __future__ import annotations

from app.models.input_errors import InputError, InputErrorKind
from app.schema.fast_rules import FastRulesTemplate
from app.services.extractor import (
    ExtractedData,
    build_prompt,
    extraction_errors,
    parse_llm_output,
)
from app.services.llm_clients import LLMClient


class TextExtractor:
    def __init__(self, llm: LLMClient, schema: FastRulesTemplate):
        self.llm = llm
        self.schema = schema

    def extract(self, document_text: str) -> tuple[ExtractedData, list[InputError]]:
        if not document_text.strip():
            return ExtractedData(source="text"), [
                InputError(kind=InputErrorKind.OCR_FAILED,
                           message="No usable text was available for extraction.")
            ]
        prompt = build_prompt(self.schema, document_text)
        output = self.llm.complete(prompt)
        if not output:
            return ExtractedData(source="text"), [
                InputError(
                    kind=InputErrorKind.EXTRACTION_FAILED,
                    message="LLM text extraction returned no output.",
                    hints=_llm_hints(),
                ),
            ]
        data = parse_llm_output(output, self.schema)
        data.source = "text"
        data.raw = output
        return data, extraction_errors(self.schema, data)


class VisionExtractor:
    def __init__(self, llm: LLMClient, schema: FastRulesTemplate):
        self.llm = llm
        self.schema = schema

    def extract(self, image_paths: list[str]) -> tuple[ExtractedData, list[InputError]]:
        if not image_paths:
            return ExtractedData(source="vision"), [
                InputError(kind=InputErrorKind.VISION_FAILED,
                           message="No page images were available for vision extraction.")
            ]
        prompt = (
            build_prompt(self.schema, "(image-based extraction)")
            + "\n\nAnalyze the attached invoice image(s) and return the YAML object."
        )
        output = self.llm.vision_complete(prompt, image_paths)
        if not output:
            return ExtractedData(source="vision"), [
                InputError(
                    kind=InputErrorKind.VISION_FAILED,
                    message="Vision extraction returned no output.",
                    hints=_llm_hints(),
                ),
            ]
        data = parse_llm_output(output, self.schema)
        data.source = "vision"
        data.raw = output
        return data, extraction_errors(self.schema, data)


def _llm_hints() -> list[str]:
    from app.config import get_settings

    settings = get_settings()
    if not settings.llm_api_key:
        return ["Set GROQ_API_KEY (or a valid LLM key) in .env, then re-run this job."]
    return ["Check LLM connectivity / base URL in .env, then re-run via POST /api/jobs/{job}/reprocess."]