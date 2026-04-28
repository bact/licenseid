# New matcher design

There is an an issue with licenses that slightly modified from another license. Like small revision in one section or an additional of only one clause.

For example, `Apache-2.0` vs `Pixar` confusion.

- According to [SPDX License List](https://spdx.org/licenses/Pixar.html), `Pixar` "is essentially Apache-2.0 with modifications to section 6." They are very similar.
- Currently in the test, `Apache-2.0` license text is misidentified as `Pixar`.

## Background & statistics

Based on the current license database (v3.28.0), here are the statistics for the license texts (normalized word counts):

### Overall Statistics

- Total Licenses: 695
- Average Length: ~1,021 words
- Shortest License: any-OSI (12 words)
- Longest License: APL-1.0 (7,286 words)

### Top 5 Shortest Licenses

- any-OSI: 12 words
- TermReadKey: 15 words
- diffmark: 17 words
- check-cvs: 19 words
- man2html: 20 words

### Top 5 Longest Licenses

- APL-1.0: 7,286 words
- LGPL-3.0-or-later: 6,890 words
- LGPL-3.0-only: 6,890 words
- GPL-3.0-or-later: 5,652 words
- GPL-3.0-only: 5,652 words

Note that the LGPL-3.0 licenses are longer than GPL-3.0 because they typically include the full GPL-3.0 text plus additional permissions and requirements. APL-1.0 (Adaptive Public License) is exceptionally long due to its detailed multi-part structure.

## Redesign of the matcher

To handle legal licenses with the precision required for "shall" vs. "shall not" while accounting for massive length discrepancies, you need a multi-stage pipeline. With 1,000 licenses, this process is computationally "light" but logically complex.

Here is the deep dive into the scoring architecture, the sliding window logic, and how to integrate your tech stack.

---

## 1. The Pipeline Architecture

You cannot rely on a single score. A "90% match" on a 10-word license is different from a "90% match" on a 7,000-word license.

### Stage A: Retrieval (SQLite FTS5 or Tantivy)

The goal here is to reduce 1,000 licenses down to the **Top 20** candidates in <10ms.
(The number of top candidates could be adjusted based on the actual performance. We may need to make it higher if our recall is not good enough.)

- **How it helps:** You pass your 1,200-word query into a BM25 search.
- **The Logic:** SQLite/Tantivy looks for "rare" legal terms (e.g., "sublicensable," "irrevocable," "derivative works"). Even if the query is only a partial match, these unique tokens will float the correct license to the top.

### Stage B: The Sliding Window (Pre-processing)

Once you have the Top 20 candidates, you don't compare the query to the *entire* license (especially if the license is the 7,000-word APL-1.0). You use a sliding window.

- **Window Size:** Match it to your query length (e.g., 1,200 words).
- **Step Size (Stride):** Use an overlap (e.g., 200 words) to ensure you don't "cut" a legal clause in half.
- **The Logic:** If the license is 6,000 words, you break it into roughly 6 overlapping segments. You then compare your 1,200-word query against each segment individually.

---

## 2. Advanced Scoring Metrics

This is how you generate the specific "98% match, but only 15% coverage" report. You need two distinct formulas.

### Metric 1: Similarity ($S$)

This tells you how much the text was **modified**.

- **Tool:** RapidFuzz (`fuzz.token_sort_ratio`).
- **Formula:** Compare the query against the **best-matching window** in the license.
- **Example:** If the query is a slightly tweaked version of the "Conditions" section of the GPL, RapidFuzz will return a $98\%$ score because the word order and content are nearly identical to that specific window.

### Metric 2: Coverage ($C$)

This tells you how much of the **total license** is represented by the query.

- **Formula:** $$C = \left( \frac{\text{Word Count of Query}}{\text{Total Word Count of License in DB}} \right) \times 100$$
- **The "Why":** If your query is 1,000 words and the license (like GPL-3.0) is 5,652 words, your coverage is $\approx 17.7\%$.

---

## 3. Implementing the "Tech Stack" Logic

Here is how the code would logically flow using your chosen tools:

### Step 1: Broad Filter (Tantivy/SQLite)

```sql
-- SQLite FTS5 example
SELECT license_id, bm25(licenses_fts) as rank 
FROM licenses_fts 
WHERE licenses_fts MATCH :query_text
ORDER BY rank LIMIT 20;
```

### Step 2: Fine-Grained Reranking (RapidFuzz)

For each of the 20 candidates:

1. **Fetch** the full text from the database.
2. **Slide:** Break the full text into segments (windows).
3. **Compare:**

    ```python
    from rapidfuzz import fuzz

    best_window_score = 0
    for window in license_windows:
        score = fuzz.token_sort_ratio(query_text, window)
        if score > best_window_score:
            best_window_score = score
    ```

4. **Calculate Coverage:**

    ```python
    coverage = (len(query_words) / len(total_license_words)) * 100
    ```

---

## 4. Why this is the "Legal-Grade" Approach

| Feature | Why it matters for Licenses |
| :--- | :--- |
| **BM25 (SQLite/Tantivy)** | Ignores common words like "the" or "and," focusing on unique legal identifiers. |
| **Sliding Window** | Prevents a short query from getting a low score just because it's being compared to a massive 7,000-word document. |
| **RapidFuzz** | Handles "typo-level" changes or small insertions (like a company name inserted into a template) that would break an exact hash match. |
| **Dual-Scoring** | Crucial for compliance. A user needs to know if they have the *whole* license or just a *snippet* of it. |

### Summary of Results for a 1,200-word Query

- **Target:** GPL-3.0 (5,652 words).

- **Query:** The "Termination" clause of the GPL-3.0.
- **System Result:** "Match found: **GPL-3.0**. Similarity: **100%** (The text is identical). Coverage: **8%** (This query is only a small section of the full license)."

This approach gives you the speed of a database search with the surgical precision of a manual legal comparison.

Since you are working with 1,000 licenses, have you considered how you will handle "nested" licenses (where one license text actually contains two or three different licenses, like a header and a body)?

## Dealing with cases like `Apache-2.0` vs `Pixar`

Dealing with "shadow licenses" or slightly modified variants is the most challenging part of legal text matching. In the legal world, a **1% difference** (adding the word "not") can change the entire meaning of a contract.

To solve this, you need to move beyond simple scoring and implement **Structural Diffing** and **Template Neutralization.**

---

## 1. The Strategy: "Base + Delta" Analysis

Instead of treating a modified license as a new, unknown entity, your system should identify the **Base License** and then highlight the **Delta** (the changes).

### The 3-Step "Variant" Detection Pipeline

1. **Normalization (Placeholder Stripping):**
    Legal templates often change only the name of the owner, the year, or the jurisdiction.
    - **Action:** Before matching, use Regex to replace common variables (e.g., `Copyright (c) [YEAR] [HOLDER]`) with a generic token like `{{COPYRIGHT_BLOCK}}`.
    - **Result:** This prevents "modified" scores caused simply by different company names.

2. **The "High-Water Mark" Score:**
    Use RapidFuzz’s `fuzz.ratio` (which is sensitive to order) against your database.
    - If you get a score between **95% and 99.9%**, you have a **Variant**.
    - If you get a score of **100%**, you have an **Identical Match**.

3. **Visual Diffing (The "Redline"):**
    When a match is $>90\%$ but $<100\%$, you shouldn't just give a number. You should generate a "Redline" diff.

---

## 2. Dealing with the "One Clause Addition"

If a 1,200-word query is identical to an MIT license but adds one paragraph at the end, a standard `fuzz.ratio` might drop to 85%, which looks "low" to a user.

To catch this, use **Segmented Comparison**:

- **Logic:** Break the query into paragraphs.
- **Check:** Match each paragraph individually against the candidate license.
- **Outcome:** Your system can report: *"This text is 100% identical to the Apache 2.0 license, but it contains **one additional paragraph** not found in the original."*

---

## 3. How the Tech Stack Handles This

| Tool | Role in "Variant" Detection |
| :--- | :--- |
| **SQLite / Tantivy** | **The Anchor:** Quickly finds the "Parent" license (e.g., "This looks like a GPL-2.0 variant"). |
| **RapidFuzz** | **The Auditor:** Uses `partial_ratio` to confirm that large chunks of the text are identical, even if one section is missing or added. |
| **Python `difflib`** | **The Lawyer:** Once RapidFuzz identifies the closest match, `difflib` produces the actual word-by-word comparison to show *exactly* what was modified. |

---

## 4. Handling "Shall" vs. "Shall Not" (The Semantic Trap)

Fuzzy matching can sometimes be "too fuzzy." It might treat "Licensee **shall** pay" and "Licensee **shall not** pay" as a 95% match.

**The Solution: Keyword Safeguards**
In your final reranking step, create a list of "Critical Legal Tokens":

- `not`, `except`, `unless`, `exclusive`, `irrevocable`.

If your RapidFuzz score is high (e.g., 98%), perform a final check: **Does the query contain a 'not' that the database text doesn't?** If so, flag it as a "Critical Modification" rather than a "Minor Revision."

---

## Summary Recommendation for Variants

To handle your ~1,000 licenses and their modified versions:

1. **Retrieve** the closest 5 licenses using **Tantivy/SQLite**.
2. **Normalize** both the query and the candidates (remove dates, names, and extra whitespace).
3. **Compare** using `rapidfuzz.fuzz.ratio`.
4. **If score is >90%:** Run a **Diff Algorithm** (`difflib.SequenceMatcher`) to find the exact added or removed words.
5. **Output to User:** > "Match: **MIT License (97% similarity)**.
    > **Note:** The 'Limitation of Liability' section has been modified to include 'under the laws of New York'."

This approach ensures that you don't just "match" the text, but you actually **analyze** the legal deviation.

Would you like a code snippet showing how to implement the "Redline" diffing between two license texts?

--

## Database schema revision

If there are license information that can be useful for the matcher, can be heuristics, and having them in database may help, we can revise the database schema. For example, the word count (length) of the license text.
