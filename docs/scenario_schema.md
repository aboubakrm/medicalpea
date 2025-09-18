# Scenario Schema (Stateful, Paused)

**Format:** One JSON object per line in `*.jsonl`.

## Top-level fields

- `scenario_id` (string): Unique ID, e.g., `"D01"`.
- `context` (object): Seed info the HCP might reference.
  - `tumor_biology` (object): e.g., `{ er: "pos", her2: "neg", pr: "pos" }`
  - `prior_lines` (array of string): e.g., `["AI", "CDK4/6"]`
  - `constraints` (array of string): e.g., `["time-pressed", "payer: EU public"]`
- `turns` (array): Alternating roles with optional templated text.

## Turn objects

- `role` (string): `"rep"` or `"hcp"`.
- `template` (string, optional for rep): A templated utterance that may reference:
  - `${last.hcp}`: The last HCP reply (full text).
  - `${extracted.slot}`: A value pulled from the last HCP reply (heuristic).
  - `${slot}` / `${topic}` / `${context.*}`: Known context fields.
- `slots` (array of string, optional): Hints for the extractor (e.g., `"tumor_biology"`, `"prior_lines"`).

### Example template tokens (illustrative)
- `Doctor, given ${last.hcp ? 'one-line summary' : 'your breast oncology practice'}, may I confirm ${slot}?`
- `Thanks—based on ${extracted.slot}, would one on-label data point on ${topic} be helpful?`

## Runner expectations (if/when re-enabled)

- Render each `"rep"` template by:
  1) Inspecting the last HCP message (`${last.hcp}`).
  2) Applying a simple keyword/regex heuristic to set `${extracted.slot}`.
  3) Falling back to blanks if nothing is found.
- Append the **growing transcript** to the model context before generating the next HCP reply.

> This design is intentionally **paused** for the deliverable. It’s preserved here for future revival with a real rep agent or human-in-the-loop.


mkdir -p src results/evals
tee src/run_eval.py > /dev/null <<'EOF'
# (content inserted below)
