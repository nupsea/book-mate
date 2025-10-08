# book-mate
Upload the contents of a book and seek answers. 



### Setup
Install UV
```
git clone <repository-url>
cd book-mate

cp .env_template .env
# Update .env with your OpenAI API key, PG_USER and PG_PASS


uv pip install -e .

make start

# check for running containers
docker ps

```

### Debug
```
psql -h localhost -U bookuser -d booksdb
```

### Verification Usage
Run the below ingestion command to load the book of interest: (here "Sherlock Holmes") and verify the chunks, id which contains the book slug, **chapter number**, chunk number and a hash.
```
 uv run python -m src.app.ingest
Clean word count: 104506
Generating summaries for 'Sherlock Holmes' (slug: sha)...
Book 'Sherlock Holmes' (slug: sha, id: 7) loaded into data store.
Total chunks parsed: 352
Total characters: 698597
First chunk: {'id': 'sha_01_001_54db4ba', 'text': '\n\n\n\n\nThe Adventures of Sherlock Holmes\n\nby Arthur Conan Doyle\n\n\nContents\n\n   I.     A Scandal in Bohemia\n   II.    The Red-Headed League\n   III.   A Case of Identity\n   IV.    The Boscombe Valley Mystery\n   V.     The Five Orange Pips\n   VI.    The Man with the Twisted Lip\n   VII.   The Adventure of the Blue Carbuncle\n   VIII.  The Adventure of the Speckled Band\n   IX.    The Adventure of the Engineer’s Thumb\n   X.     The Adventure of the Noble Bachelor\n   XI.    The Adventure of the Beryl Coronet\n   XII.   The Adventure of the Copper Beeches\n\n\n\n\n', 'num_tokens': 151, 'num_chars': 554}
Last chunk: {'id': 'sha_13_033_dfbf9a7', 'text': ' Holmes, “for you\nhave certainly cleared up everything which puzzled us. And here comes\nthe country surgeon and Mrs. Rucastle, so I think, Watson, that we had\nbest escort Miss Hunter back to Winchester, as it seems to me that our\n_locus standi_ now is rather a questionable one.”\n\nAnd thus was solved the mystery of the sinister house with the copper\nbeeches in front of the door. Mr. Rucastle survived, but was always a\nbroken man, kept alive solely through the care of his devoted wife.\nThey still live with their old servants, who probably know so much of\nRucastle’s past life that he finds it difficult to part from them. Mr.\nFowler and Miss Rucastle were married, by special license, in\nSouthampton the day after their flight, and he is now the holder of a\ngovernment appointment in the island of Mauritius. As to Miss Violet\nHunter, my friend Holmes, rather to my disappointment, manifested no\nfurther interest in her when once she had ceased to be the centre of\none of his problems, and she is now the head of a private school at\nWalsall, where I believe that she has met with considerable success.\n\n\n\n\n\n\n', 'num_tokens': 259, 'num_chars': 1112}
```


### Ingestion Flow
```
> uv run python -m src.flows.book_ingest
Starting ingestion for: The Odyssey (slug: ody)
Validation passed - File size: 717826 bytes
Clean word count: 129571
Parsed 445 chunks, 841715 chars
Generated 25 chapter summaries + book summary
Stored to database - Book ID: 8
/Users/sethurama/DEV/LM/book-mate/src/search/vec.py:11: UserWarning: Qdrant client version 1.15.1 is incompatible with server version 1.8.3. Major versions should match and minor version difference must not exceed 1. Set check_compatibility=False to skip version check.
  self.qdrant = QdrantClient("localhost", port=6333)
BM25 index saved to indexes/bm25_index.pkl
Vector shape: 445 384
 ## Inserted: 445 chunks into Qdrant
Built search indexes - BM25: 445, Vector: 445 chunks
Verification complete - Status: success

Ingestion complete: {'slug': 'ody', 'book_id': 8, 'title': 'The Odyssey', 'chapters': 25, 'chunks': 445, 'search_indexed': 445, 'status': 'success'}
```

### Query Flow
```

❯ uv run python -m src.flows.book_query
Starting query for book: mma
Book validated - ID: 3
Retrieved 14 chapter summaries
Retrieved book summary (2045 chars)
Query complete

Query result: Found 14 chapters
Book summary preview: The book presents a profound exploration of the life and philosophy of Marcus Aurelius Antoninus, weaving together his personal experiences, philosoph...
Starting query for book: ody
Book validated - ID: 8
Searching for: 'odysseus journey home' in book: ody
/Users/sethurama/DEV/LM/book-mate/src/search/vec.py:11: UserWarning: Qdrant client version 1.15.1 is incompatible with server version 1.8.3. Major versions should match and minor version difference must not exceed 1. Set check_compatibility=False to skip version check.
  self.qdrant = QdrantClient("localhost", port=6333)
BM25 index loaded from indexes/bm25_index.pkl (445 documents)
Search completed - Found 5 results
Retrieved book summary (1537 chars)
Query complete


Search results for: 'odysseus journey home'
Found 5 matching chunks:

1. [ody_01_005_5618b8f]
   ighted, the slayer of Argos, that he should neither kill the
    man, nor woo his wife. For the son of Atreus shall be avenged at
    the hand of Orestes, so soon as he shall come to man’s estate and
...

2. [ody_01_003_2cfa4ff]
   In an appendix I have also reprinted the paragraphs explanatory of the
plan of Ulysses’ house, together with the plan itself. The reader is
recommended to study this plan with some attention.

In the ...

3. [ody_04_010_50b4863]
   us, though very anxious to press forward, had to wait
in order to bury his comrade and give him his due funeral rites.
Presently, when he too could put to sea again, and had sailed on as far
as the Ma...

4. [ody_01_004_894fc68]
   eward path, the lady nymph Calypso
    held, that fair goddess, in her hollow caves, longing to have him
    for her lord. But when now the year had come in the courses of the
    seasons, wherein the...

5. [ody_16_007_080d745]
    on and they flew forward nothing loath; ere long they came
to Pylos, and then Telemachus said:

“Pisistratus, I hope you will promise to do what I am going to ask you.
You know our fathers were old f...
```




