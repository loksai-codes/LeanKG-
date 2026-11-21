Example (hand-written, Japanese):
Sentence: 長時間労働によるストレスで不眠症が悪化した。
Entities:
[0] ストレス (Stressor)
[1] 不眠症 (Condition)
Allowed relations (head -> tail):
[0] -> [1]: INCREASES_RISK_OF, ASSOCIATED_WITH
[1] -> [0]: ASSOCIATED_WITH
Answer: {"relations": [{"head": 0, "tail": 1, "type": "INCREASES_RISK_OF", "negated": false, "hedged": false, "confidence": 0.85}]}

Example (hand-written, Japanese):
Sentence: 瞑想が不安を和らげるとは言い切れない。
Entities:
[0] 瞑想 (Intervention)
[1] 不安 (Symptom)
Allowed relations (head -> tail):
[0] -> [1]: REDUCES, ASSOCIATED_WITH
[1] -> [0]: ASSOCIATED_WITH
Answer: {"relations": [{"head": 0, "tail": 1, "type": "REDUCES", "negated": false, "hedged": true, "confidence": 0.5}]}

Example (hand-written, Japanese):
Sentence: うつ病の患者と高血圧の患者を対象とした。
Entities:
[0] うつ病 (Condition)
[1] 高血圧 (Condition)
Allowed relations (head -> tail):
[0] -> [1]: INCREASES_RISK_OF, ASSOCIATED_WITH
[1] -> [0]: INCREASES_RISK_OF, ASSOCIATED_WITH
Answer: {"relations": []}
