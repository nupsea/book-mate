from abc import ABC, abstractmethod
import re
import tiktoken
import hashlib

from pathlib import Path


class TextReader(ABC):

    def __init__(self, file_path, slug, source, split_pattern=None) -> None:
        self.file_path = Path(file_path)
        self.source = source
        self.text = ""
        self.enc = tiktoken.get_encoding("cl100k_base")
        self.pattern = split_pattern
        self.slug = slug

    @staticmethod
    def simple_hash(text: str, length: int = 7) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()[:length]

    @abstractmethod
    def parse(self, max_tokens=500, overlap=100):
        raise NotImplementedError("Subclasses must implement parse method.")


class GutenbergReader(TextReader):

    def __init__(self, file_path, slug, source="gutenberg", split_pattern=None):
        self.pattern = split_pattern or r"^(?:CHAPTER [IVXLCDM]+\.)\s*\n"
        super().__init__(
            file_path, slug=slug, source=source, split_pattern=self.pattern
        )

    def _section_split(self):
        return re.split(self.pattern, self.text, flags=re.IGNORECASE | re.MULTILINE)

    def _chunk_split(self, section: str, max_tokens=1000, overlap=100):
        tokens = self.enc.encode(section)
        chunks = []
        for i in range(0, len(tokens), max_tokens - overlap):
            chunk = self.enc.decode(tokens[i : i + max_tokens])
            chunks.append(chunk)
        return chunks

    def _strip_gutenberg(self, text: str) -> str:
        start_match = re.search(r"\*\*\* START OF.*\*\*\*", text)
        end_match = re.search(r"\*\*\* END OF.*\*\*\*", text)
        if start_match and end_match:
            return text[start_match.end() : end_match.start()]
        return text

    def _parse_into_chunks(self, max_tokens, overlap):
        sections = self._section_split()
        all_chunks = []
        for sid, section in enumerate(sections):
            section_chunks = self._chunk_split(section, max_tokens, overlap)
            for cid, sub in enumerate(section_chunks):
                hash_id = TextReader.simple_hash(sub)
                all_chunks.append(
                    {
                        "id": f"{self.slug}_{sid+1:02d}_{cid+1:03d}_{hash_id}",
                        "text": sub,
                        "num_tokens": len(self.enc.encode(sub)),
                        "num_chars": len(sub),
                    }
                )
        return all_chunks

    def parse(self, max_tokens=500, overlap=100):
        book_path = Path(self.file_path)
        raw_text = book_path.read_text(encoding="utf-8")

        self.text = self._strip_gutenberg(raw_text)
        print("Clean word count:", len(self.text.split()))

        chunks = self._parse_into_chunks(max_tokens, overlap)
        return chunks
