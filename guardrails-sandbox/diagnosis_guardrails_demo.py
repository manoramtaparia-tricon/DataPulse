from __future__ import annotations

import os
import json
import string
from pathlib import Path
from typing import Iterable, Iterator, Literal, Tuple

os.environ.setdefault("PRESIDIO_DEVICE", "cpu")

import spacy

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpArtifacts, NlpEngine
from presidio_anonymizer import AnonymizerEngine
from pydantic import BaseModel, Field, ValidationError


EMAIL_ENTITY = "EMAIL_ADDRESS"
PROMPT_INJECTION_ENTITY = "PROMPT_INJECTION"
ABUSIVE_LANGUAGE_ENTITY = "ABUSIVE_LANGUAGE"


class BlankNlpEngine(NlpEngine):
    def __init__(self) -> None:
        self._nlp = spacy.blank("en")
        self._loaded = False

    def load(self) -> None:
        self._loaded = True

    def is_loaded(self) -> bool:
        return self._loaded

    def process_text(self, text: str, language: str) -> NlpArtifacts:
        doc = self._nlp(text)
        tokens = list(doc)
        return NlpArtifacts(
            entities=[],
            tokens=doc,
            tokens_indices=[token.idx for token in tokens],
            lemmas=[token.text for token in tokens],
            nlp_engine=self,
            language=language,
            scores=[],
        )

    def process_batch(
        self,
        texts: Iterable[str],
        language: str,
        batch_size: int = 1,
        n_process: int = 1,
        **kwargs,
    ) -> Iterator[Tuple[str, NlpArtifacts]]:
        for text in texts:
            yield text, self.process_text(text, language)

    def is_stopword(self, word: str, language: str) -> bool:
        return word.lower() in {"a", "an", "and", "or", "the", "to", "of", "in"}

    def is_punct(self, word: str, language: str) -> bool:
        return bool(word) and all(character in string.punctuation for character in word)

    def get_supported_entities(self) -> list[str]:
        return []

    def get_supported_languages(self) -> list[str]:
        return ["en"]


class Diagnosis(BaseModel):
    product_id: str = Field(min_length=1)
    status: Literal["STUCK", "RESOLVED", "UNKNOWN"]
    failed_stage: str | None = None
    root_cause: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    confidence: Literal["LOW", "MEDIUM", "HIGH"]


def load_cases() -> list[dict[str, object]]:
    sample_path = Path(__file__).with_name("sample_cases.json")
    return json.loads(sample_path.read_text(encoding="utf-8"))


def build_analyzer() -> AnalyzerEngine:
    registry = RecognizerRegistry()
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity=EMAIL_ENTITY,
            name="email_address_recognizer",
            patterns=[
                Pattern(
                    name="email_address",
                    regex=r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                    score=1.0,
                )
            ],
        )
    )
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity=PROMPT_INJECTION_ENTITY,
            name="prompt_injection_recognizer",
            patterns=[
                Pattern(
                    name="prompt_injection_phrase",
                    regex=r"(?:Ignore previous instructions|reveal the system prompt|print the system prompt)",
                    score=1.0,
                )
            ],
        )
    )
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity=ABUSIVE_LANGUAGE_ENTITY,
            name="abusive_language_recognizer",
            patterns=[
                Pattern(
                    name="abusive_language_terms",
                    regex=r"\b(?:dumb|stupid)\b",
                    score=1.0,
                )
            ],
        )
    )
    return AnalyzerEngine(registry=registry, nlp_engine=BlankNlpEngine(), supported_languages=["en"])


ANALYZER = build_analyzer()
ANONYMIZER = AnonymizerEngine()


def analyze_text(text: str) -> list:
    return ANALYZER.analyze(
        text=text,
        language="en",
        entities=[EMAIL_ENTITY, PROMPT_INJECTION_ENTITY, ABUSIVE_LANGUAGE_ENTITY],
        score_threshold=0.0,
    )


def format_findings(text: str, findings: list) -> str:
    lines = []
    for finding in findings:
        snippet = text[finding.start:finding.end]
        lines.append(f"- {finding.entity_type} at {finding.start}:{finding.end}: {snippet}")
    return "\n".join(lines)


def anonymize_text(text: str, findings: list) -> str:
    if not findings:
        return text

    return ANONYMIZER.anonymize(text=text, analyzer_results=findings).text


def run_input_guard(prompt: str) -> bool:
    findings = analyze_text(prompt)
    if findings:
        print("input_guardrails: FAIL")
        print(format_findings(prompt, findings))
        return False

    print("input_guardrails: PASS")
    return True


def run_output_guard(response: dict[str, object]) -> None:
    try:
        diagnosis = Diagnosis.model_validate(response)
    except ValidationError as error:
        print("output_guardrails: FAIL")
        print(str(error).strip() or error.__class__.__name__)
        return

    redacted_diagnosis = diagnosis.model_dump()
    output_findings = []
    for field_name in ("root_cause", "recommendation"):
        field_value = getattr(diagnosis, field_name)
        if not field_value:
            continue

        findings = analyze_text(field_value)
        if findings:
            output_findings.append((field_name, field_value, findings))
            redacted_diagnosis[field_name] = anonymize_text(field_value, findings)

    if output_findings:
        print("output_guardrails: PASS (redacted)")
        for field_name, field_value, findings in output_findings:
            print(f"{field_name}:")
            print(format_findings(field_value, findings))
        print(f"diagnosis: {json.dumps(redacted_diagnosis, indent=2, default=str)}")
        return

    print("output_guardrails: PASS")
    print(f"diagnosis: {json.dumps(diagnosis.model_dump(), indent=2, default=str)}")


def run_case(case: dict[str, object]) -> None:
    name = str(case["name"])
    prompt = str(case["prompt"])
    response = case["response"]

    print(f"\n== {name} ==")
    if not run_input_guard(prompt):
        return

    run_output_guard(response)


def main() -> None:
    for case in load_cases():
        run_case(case)


if __name__ == "__main__":
    main()