import asyncio
from collections import defaultdict
from openai import AsyncOpenAI
import tiktoken


chapter_prompt = """
Summarize this chapter from the book into 1–2 concise paragraphs.
Capture key events, themes, and character actions.
Avoid bullet points. Do not mention chunking.

Chapter text:
{text}
"""

book_prompt = """
Here are summaries of each chapter of a book.
Write a single cohesive overall summary of the book in 2–3 paragraphs. 
Do NOT enumerate chapter by chapter. Instead, merge into one flowing narrative. 
Focus on major themes, central characters, and the overall arc.

Chapter summaries:
{joined}
"""


class SummaryGenerator:
    def __init__(self):
        self.client = AsyncOpenAI()
        self.semaphore = asyncio.Semaphore(4)
        self.enc = tiktoken.get_encoding("cl100k_base")
        self.max_tokens = 100000  # Safe limit well below 200k TPM

    def split_text_into_batches(self, text: str, max_tokens: int = None):
        """Split text into batches that fit within token limit."""
        if max_tokens is None:
            max_tokens = self.max_tokens

        tokens = self.enc.encode(text)

        if len(tokens) <= max_tokens:
            return [text]

        # Split into roughly equal batches
        num_batches = (len(tokens) // max_tokens) + 1
        batch_size = len(tokens) // num_batches

        batches = []
        for i in range(0, len(tokens), batch_size):
            batch_tokens = tokens[i:i + batch_size]
            batch_text = self.enc.decode(batch_tokens)
            batches.append(batch_text)

        return batches

    async def summarize_text_batch(self, text: str, batch_num: int = None):
        """Summarize a batch of text."""
        async with self.semaphore:
            prompt = chapter_prompt.format(text=text)
            resp = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # fast + cheap
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return str(resp.choices[0].message.content).strip()

    async def summarize_chapter(self, text, sid):
        """Summarize a single chapter, handling large texts by batching."""
        # Check if text is too large
        batches = self.split_text_into_batches(text)

        if len(batches) == 1:
            # Small enough to summarize directly
            summary = await self.summarize_text_batch(text)
        else:
            # Need to batch: summarize each batch, then combine summaries
            print(f"Chapter {sid} is large ({len(batches)} batches), summarizing in parts...")
            batch_summaries = await asyncio.gather(*[
                self.summarize_text_batch(batch, i)
                for i, batch in enumerate(batches)
            ])

            # Combine batch summaries into final summary
            combined_text = "\n\n".join([
                f"Part {i+1}: {summary}"
                for i, summary in enumerate(batch_summaries)
            ])

            # Summarize the combined summaries
            async with self.semaphore:
                prompt = f"""
These are summaries of different parts of the same chapter.
Combine them into 1-2 cohesive paragraphs that capture the chapter's key points.

{combined_text}
"""
                resp = await self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                summary = str(resp.choices[0].message.content).strip()

        return {
            "chapter_id": sid,
            "summary": summary,
        }

    async def summarize_book(self, chapter_summaries):
        """Synthesize whole-book summary from chapter summaries."""
        joined = "\n\n".join(
            [f"Chapter {c['chapter_id']}: {c['summary']}" for c in chapter_summaries]
        )
        prompt = book_prompt.format(joined=joined)
        resp = await self.client.chat.completions.create(
            model="gpt-4o",  # can use bigger model for better synthesis
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return str(resp.choices[0].message.content).strip()

    async def summarize_hierarchy(self, chunks):
        """
        Summarize book hierarchy.
        Returns (chapter_summaries, book_summary).
        """
        # Group chunks by chapter_id (sid)
        section_map = defaultdict(list)
        for c in chunks:
            sid = int(c["id"].split("_")[1])  # parse sid from id
            section_map[sid].append(c["text"])

        # Join chapter text
        chapters = {sid: "\n".join(texts) for sid, texts in section_map.items()}

        # Summarize chapters in parallel
        tasks = [self.summarize_chapter(text, sid) for sid, text in chapters.items()]
        chapter_summaries = await asyncio.gather(*tasks)

        # Summarize entire book
        book_summary = await self.summarize_book(chapter_summaries)

        return chapter_summaries, book_summary
