# Call the gate from any stack

Run the gate once, inside your own environment:

```bash
witness-gate --port 8765 --ledger gate-ledger.jsonl
# or, from the repo: python -m soul_cradle.gate_server --port 8765
```

Then any language that can make an HTTP request can put an action
before the witnesses. Same contract everywhere:

`POST /assess` with `{"action": "...", "evidence": {...}}` returns
`{"verdict": "clear" | "flagged" | "contested" | "blocked", ...}`.
Clear means run it. Flagged or contested means a human decides.
Blocked means refuse it; no setting turns a block into a pass.

## curl

```bash
curl -s localhost:8765/assess -H 'Content-Type: application/json' -d '{
  "action": "Email the customer a revised invoice",
  "evidence": {"principal_consent": true, "fully_disclosed": true,
               "reversible": true, "deception_involved": false}}'
```

## JavaScript / TypeScript

```js
const res = await fetch("http://127.0.0.1:8765/assess", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    action: "Email the customer a revised invoice",
    evidence: { principal_consent: true, fully_disclosed: true,
                reversible: true, deception_involved: false },
  }),
});
const { verdict } = await res.json();
if (verdict === "blocked") throw new Error("the gate refused this action");
if (verdict !== "clear") await sendToHumanReview(/* the full result */);
```

## Go

```go
body, _ := json.Marshal(map[string]any{
    "action": "Email the customer a revised invoice",
    "evidence": map[string]any{
        "principal_consent": true, "fully_disclosed": true,
        "reversible": true, "deception_involved": false,
    },
})
resp, _ := http.Post("http://127.0.0.1:8765/assess",
    "application/json", bytes.NewReader(body))
```

## C# / Java / anything else

The contract is one POST and one JSON body; every HTTP client in every
language speaks it. The full response carries the verdict, the panel
note, the dissent, and each witness's individual judgment, so your
review surface can show its work.

## Agent frameworks (MCP)

Frameworks that speak the Model Context Protocol do not need HTTP:
run `witness-gate-mcp --ledger gate-ledger.jsonl` and point the
framework's MCP configuration at that command. The agent gets four
tools: `witness_gate_assess`, `witness_gate_verify_ledger`,
`witness_gate_review_queue`, and `witness_gate_rubrics`.
