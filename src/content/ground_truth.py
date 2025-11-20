import json
import os
from openai import OpenAI
from tqdm.auto import tqdm
from string import Template

gt_prompt_template = Template(
    """ 
You are emulating realistic book readers with diverse reading habits. 
The readers have mostly read the book and are now trying to recall, clarify, 
or explore details by searching within the book. 
Some are precise, some are vague, some type in full questions, 
and others use only a couple of words or short phrases.


TASK:
Formulate exactly 5 distinct search queries that a reader might ask 
based only on the following 'Record' (viz. a chunked information from the book/content).

Record:

id: $id
text: $text
num_tokens: $num_tokens
num_chars: $num_chars
                              
HARD CONSTRAINTS:
- Use ONLY details present in the record (no external knowledge).
- Max 15 words per query.
- Each query must sound like something a real book reader would type.
- Ensure a MIX of query STYLES and INTENT across the 5:
    • 1 short keyword-style query (2–4 words).  Occasionally, this may be purely keyword-based.
    • 1 natural-language full question.
    • 1 phrase-like query (fragment, not a full sentence).
    • 1 detail-oriented recall query (who/what/where).
    • 1 deeper reflective or interpretive query (asking about meaning, emotion, theme, or motivation).
- Avoid reusing the same key noun/adjective across queries; vary wording and style.
- At least one query must be **thoughtful and reflective** (not just factual or keyword-based).
- Queries should sound like a human reader’s questions, not summaries.
- Do NOT always output the 5 query types in the same sequence. Randomly vary the order 
  so the set looks natural and less templated.

OUTPUT FORMAT:
Return only a JSON array of 5 strings, with no extra text:
[
  "query_1",
  "query_2",
  "query_3",
  "query_4",
  "query_5"
]
"""
)


class GoldenDataGenerator:

    def __init__(self) -> None:
        self.llm = None  # Lazy initialization - only create when generating
        self.results = {}
        self.aiw_gt = []

    def generate_questions(self, doc):
        # Lazy initialization of OpenAI client (only once)
        if self.llm is None:
            self.llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        gt_prompt = gt_prompt_template.substitute(**doc)

        response = self.llm.chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "user", "content": gt_prompt}]
        )

        json_response = response.choices[0].message.content
        return json_response

    def bulk_generate(self, chunks):
        for doc in tqdm(chunks):
            doc_id = doc["id"]
            if doc_id in self.results:
                continue
            try:
                res = self.generate_questions(doc) or "[]"
                self.results[doc["id"]] = json.loads(res)
            except Exception as e:
                print("Error for doc:", doc["id"], e)

    def save(self, out_path="../../../DATA/GT/aiw_golden_data.json"):
        with open(out_path, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"Saved {len(self.results)} records to {out_path}")

    def load(self, in_path="../../../DATA/GT/aiw_golden_data.json"):
        with open(in_path, "r") as f:
            res = json.load(f)

            for cid, queries in res.items():
                for q in queries:
                    self.aiw_gt.append({"gold_id": cid, "query": q})

    def get_golden_data(self):
        return self.aiw_gt


if __name__ == "__main__":
    # gen = GoldenDataGenerator()
    # gen.bulk_generate(chunks)
    # gen.save()
    # gen.load()
    # aiw_gt = gen.get_golden_data()
    # print(aiw_gt[:3])  # print first 3 records..
    pass
