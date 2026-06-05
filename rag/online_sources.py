from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from html.parser import HTMLParser
from pathlib import Path
from tempfile import SpooledTemporaryFile

import requests

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

ROOT = Path(__file__).resolve().parents[1]
ONLINE_RAW_DIR = ROOT / "data" / "raw" / "online"


@dataclass(frozen=True)
class OnlineSource:
    slug: str
    url: str
    title: str
    source_type: str
    topic: str
    year: int | None = None


ONLINE_SOURCES: list[OnlineSource] = [
    OnlineSource(
        slug="stanford_andrew_ng_publications_current",
        url="https://ai.stanford.edu/~ang/papers.php",
        title="Andrew Ng Stanford Publications",
        source_type="publication_index",
        topic="research publications",
    ),
    OnlineSource(
        slug="stanford_andrew_ng_publications_archive",
        url="https://ai.stanford.edu/~ang/papers.html",
        title="Andrew Ng Stanford Publications Archive",
        source_type="publication_index",
        topic="research publications",
    ),
    OnlineSource(
        slug="andrewng_org_research",
        url="https://www.andrewng.org/research",
        title="Andrew Ng Research Overview",
        source_type="research_profile",
        topic="research overview",
    ),
    OnlineSource(
        slug="deeplearning_ai_home",
        url="https://www.deeplearning.ai/",
        title="DeepLearning.AI Home and The Batch",
        source_type="organization_page",
        topic="ai education and commentary",
    ),
    OnlineSource(
        slug="machine_learning_specialization",
        url="https://learn.deeplearning.ai/specializations/machine-learning/information",
        title="Machine Learning Specialization",
        source_type="course_page",
        topic="machine learning education",
    ),
    OnlineSource(
        slug="machine_learning_in_production",
        url="https://learn.deeplearning.ai/courses/machine-learning-in-production/information",
        title="Machine Learning In Production",
        source_type="course_page",
        topic="ml engineering",
    ),
    OnlineSource(
        slug="andrew_ng_curriculum_vitae",
        url="https://ai.stanford.edu/~ang/curriculum-vitae.pdf",
        title="Andrew Ng Curriculum Vitae",
        source_type="cv_pdf",
        topic="biography and publications",
    ),
    OnlineSource(
        slug="stanford_ecorner_near_future_ai_transcript",
        url="https://ecorner.stanford.edu/wp-content/uploads/sites/2/2023/10/the-near-future-of-ai-entire-talk-transcript.pdf",
        title="The Near Future of AI Talk Transcript",
        source_type="talk_transcript_pdf",
        topic="ai future and applications",
        year=2023,
    ),
    OnlineSource(
        slug="machine_learning_yearning_public_pdf",
        url="https://home-wordpress.deeplearning.ai/wp-content/uploads/2022/03/andrew-ng-machine-learning-yearning.pdf",
        title="Machine Learning Yearning",
        source_type="book_pdf",
        topic="machine learning strategy",
    ),
    OnlineSource(
        slug="wikipedia_andrew_ng",
        url="https://en.wikipedia.org/wiki/Andrew_Ng",
        title="Andrew Ng Wikipedia Biography",
        source_type="biography_wikipedia",
        topic="biography and achievements",
    ),
    OnlineSource(
        slug="stanford_andrew_ng_bio",
        url="https://ai.stanford.edu/~ang/bio.html",
        title="Andrew Ng Stanford Bio",
        source_type="academic_bio",
        topic="academic biography",
    ),
    OnlineSource(
        slug="amazon_board_andrew_ng",
        url="https://www.aboutamazon.com/news/company-news/amazon-board-directors-andrew-ng",
        title="Amazon Board Appointment",
        source_type="press_release",
        topic="amazon board appointment",
        year=2024,
    ),
    OnlineSource(
        slug="coursera_co_founder_profile",
        url="https://about.coursera.org/",
        title="Coursera Co-founder Profile",
        source_type="corporate_bio",
        topic="educational entrepreneurship",
    ),
]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            cleaned = re.sub(r"\s+", " ", data).strip()
            if cleaned:
                self.parts.append(cleaned)

    def text(self) -> str:
        return "\n".join(self.parts)


def fetch_online_sources(
    sources: list[OnlineSource] | None = None,
    output_dir: Path = ONLINE_RAW_DIR,
    timeout: int = 30,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source in sources or ONLINE_SOURCES:
        try:
            response = requests.get(
                source.url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 AndrewNgDigitalTwinStudentProject/0.1"},
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "pdf" in content_type or source.url.lower().endswith(".pdf"):
                text = extract_pdf_text(response.content)
            else:
                text = extract_html_text(response.text)
        except Exception as exc:
            text = (
                f"Online source could not be fetched during ingestion.\n"
                f"Title: {source.title}\n"
                f"URL: {source.url}\n"
                f"Error: {exc}\n"
                "Keep this source in the registry and retry later, or download it manually."
            )

        text_path = output_dir / f"{source.slug}.txt"
        text_path.write_text(text, encoding="utf-8")
        meta_path = output_dir / f"{source.slug}.meta.json"
        meta_path.write_text(
            json.dumps({**asdict(source), "source": source.url}, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        written.append(text_path)
    return written


def extract_html_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return parser.text()


def extract_pdf_text(content: bytes) -> str:
    if PdfReader is None:
        return "PDF source downloaded, but pypdf is not installed, so text extraction was skipped."
    with SpooledTemporaryFile() as handle:
        handle.write(content)
        handle.seek(0)
        reader = PdfReader(handle)
        return "\n".join(page.extract_text() or "" for page in reader.pages)


if __name__ == "__main__":
    paths = fetch_online_sources()
    print(f"Fetched {len(paths)} online sources into {ONLINE_RAW_DIR}")
