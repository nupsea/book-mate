# Debug Guide: Troubleshooting LLM Book Selection

## Current Issue

When selecting "The Adventures of Sherlock Holmes" (slug: `ash`) from the dropdown and asking "Give me the plot", the LLM incorrectly called `get_book_summary` with `book_identifier: 'aiw'` (Alice in Wonderland) instead of `'ash'`.

## Database State

Current books in database:
```
slug | title                                                        | author
-----|--------------------------------------------------------------|--------------------
aiw  | Alice's Adventures in Wonderland                             | Lewis Carroll
gtr  | Gulliver's Travels into Several Remote Nations of the World | Jonathan Swift
ash  | The Adventures of Sherlock Holmes                            | Arthur Conan Doyle
mam  | The Meditations                                              | Marcus Aurelius
ody  | The Odyssey                                                  | Homer
wow  | The War of the Worlds                                        | H.G. Wells
```

## Enhanced Logging Added

The following detailed logs have been added to trace the entire flow:

### 1. UI Layer (`src/ui/app.py`)
```
[UI] Original message: <user_input>
[UI] Selected book slug from dropdown: <slug_or_none>
[UI] Found book title for slug 'ash': The Adventures of Sherlock Holmes
[UI] Injected title into message: <final_message>
```

### 2. Chat Layer (`src/mcp_client/agent.py`)
```
================================================================================
[CHAT] NEW REQUEST
[CHAT] User message: <final_message_with_title>
[CHAT] Conversation history length: 0
================================================================================

[CHAT] Creating NEW conversation
[CHAT] Title-to-slug mapping: {'alice\'s adventures in wonderland': 'aiw', ...}
[CHAT] Available books shown to LLM:
Available books:
- Alice's Adventures in Wonderland by Lewis Carroll
- Gulliver's Travels into Several Remote Nations of the World by Jonathan Swift
- The Adventures of Sherlock Holmes by Arthur Conan Doyle
...

[CHAT] Full conversation being sent to LLM:
  [0] SYSTEM: You are a helpful book assistant with access to book summaries...
  [1] USER: Give me the plot (for the book 'The Adventures of Sherlock Holmes')
```

### 3. Tool Translation Layer (`src/mcp_client/agent.py`)
```
[TOOL] LLM provided book_identifier: '<what_llm_said>'
[TOOL] Available mappings: {'the adventures of sherlock holmes': 'ash', ...}
[TOOL] ✓ Translated 'The Adventures of Sherlock Holmes' → 'ash'
   OR
[TOOL] ✗ NO TRANSLATION - passing 'aiw' as-is

[TOOL] Calling: get_book_summary({'book_identifier': 'ash'})

[TOOL] Result length: 1234 chars
[TOOL] Result preview: The book summary starts here...
```

## Testing Steps

1. **Restart the application** to apply logging changes:
   ```bash
   make down
   make up
   ```

2. **Clear your browser cache** or open incognito mode to ensure fresh UI state

3. **Test the problematic scenario**:
   - Open http://localhost:7860
   - From the dropdown, select "The Adventures of Sherlock Holmes"
   - Type: "Give me the plot"
   - Click "Clear Conversation" first if you had previous messages
   - Click Send

4. **Analyze the console output** in this order:

   a. **Check UI layer** - Did it inject the correct title?
   ```
   [UI] Found book title for slug 'ash': The Adventures of Sherlock Holmes
   [UI] Injected title into message: Give me the plot (for the book 'The Adventures of Sherlock Holmes')
   ```

   b. **Check system prompt** - Is the title-to-slug mapping correct?
   ```
   [CHAT] Title-to-slug mapping: {'the adventures of sherlock holmes': 'ash', ...}
   ```

   c. **Check LLM input** - What did we send to the LLM?
   ```
   [CHAT] Full conversation being sent to LLM:
     [1] USER: Give me the plot (for the book 'The Adventures of Sherlock Holmes')
   ```

   d. **Check LLM output** - What book_identifier did the LLM provide?
   ```
   [TOOL] LLM provided book_identifier: '<CHECK_THIS>'
   ```
   - If this says 'aiw', the LLM is hallucinating/ignoring our instructions
   - If this says 'The Adventures of Sherlock Holmes', the translation should work

   e. **Check translation** - Did we translate correctly?
   ```
   [TOOL] ✓ Translated 'The Adventures of Sherlock Holmes' → 'ash'
   ```

   f. **Check tool call** - What did we actually send to the MCP server?
   ```
   [TOOL] Calling: get_book_summary({'book_identifier': 'ash'})
   ```

## Possible Root Causes

### Hypothesis 1: Conversation History Contamination
- **Symptom**: Old messages in conversation history mentioning Alice in Wonderland
- **Check**: Look for `[CHAT] CONTINUING conversation` instead of `[CHAT] Creating NEW conversation`
- **Fix**: Always click "Clear Conversation" button before testing

### Hypothesis 2: LLM Ignoring Instructions
- **Symptom**: LLM provides 'aiw' directly instead of using the title
- **Check**: `[TOOL] LLM provided book_identifier: 'aiw'`
- **Fix**: This means the LLM is making up slugs despite being told to use titles. Need stronger prompting or switch to GPT-4.

### Hypothesis 3: Title Not Being Injected
- **Symptom**: User message doesn't contain the book title
- **Check**: `[UI] Injected title into message:` should show the title
- **Fix**: Check dropdown selection logic

### Hypothesis 4: Case-Sensitivity Issue
- **Symptom**: Translation fails because of case mismatch
- **Check**: `[TOOL] Available mappings:` shows lowercase keys
- **Note**: We use `.lower()` for case-insensitive matching, but log the original

### Hypothesis 5: Multiple Books with Similar Names
- **Symptom**: LLM gets confused between similar titles
- **Check**: Look at the full conversation to see if there's ambiguity
- **Fix**: May need more explicit book identification in the prompt

## What to Share for Debugging

When reporting the issue, please copy the **entire console output** from these sections:

1. The UI layer logs (starts with `[UI]`)
2. The CHAT layer logs (starts with `[CHAT]`)
3. The TOOL layer logs (starts with `[TOOL]`)
4. Any ERROR messages

This will help identify exactly where the flow breaks down.

## Expected Successful Flow

```
[UI] Selected book slug from dropdown: ash
[UI] Found book title for slug 'ash': The Adventures of Sherlock Holmes
[UI] Injected title into message: Give me the plot (for the book 'The Adventures of Sherlock Holmes')

[CHAT] Creating NEW conversation
[CHAT] Title-to-slug mapping: {'the adventures of sherlock holmes': 'ash', ...}
[CHAT] USER: Give me the plot (for the book 'The Adventures of Sherlock Holmes')

[TOOL] LLM provided book_identifier: 'The Adventures of Sherlock Holmes'
[TOOL] ✓ Translated 'The Adventures of Sherlock Holmes' → 'ash'
[TOOL] Calling: get_book_summary({'book_identifier': 'ash'})
[TOOL] Result preview: <actual Sherlock Holmes summary>
```

## Next Steps

1. Test with the new logging
2. Share the complete console output
3. Based on the logs, we can identify which hypothesis is correct
4. Apply the appropriate fix
