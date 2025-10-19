import asyncio
from collections import defaultdict
from openai import AsyncOpenAI


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

    async def summarize_chapter(self, text, sid):
        """Summarize a single chapter."""
        async with self.semaphore:
            prompt = chapter_prompt.format(text=text)
            resp = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # fast + cheap
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return {
                "chapter_id": sid,
                "summary": str(resp.choices[0].message.content).strip(),
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
