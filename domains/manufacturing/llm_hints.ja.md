Example (hand-written, Japanese):
Sentence: ホースに亀裂があり、作動油が漏れていた。
Entities:
[0] ホース (Component)
[1] 亀裂 (FailureMode)
[2] 漏れ (FailureMode)
Allowed relations (head -> tail):
[0] -> [1]: HAS_FAILURE_MODE
[0] -> [2]: HAS_FAILURE_MODE
[1] -> [2]: CAUSED_BY
[2] -> [1]: CAUSED_BY
Answer: {"relations": [{"head": 0, "tail": 1, "type": "HAS_FAILURE_MODE", "negated": false, "hedged": false, "confidence": 0.9}, {"head": 2, "tail": 1, "type": "CAUSED_BY", "negated": false, "hedged": false, "confidence": 0.7}]}

Example (hand-written, Japanese):
Sentence: 異音の原因は芯ずれではなく、ベアリングの摩耗だった。
Entities:
[0] 異音 (Observation)
[1] 芯ずれ (Cause)
[2] ベアリング (Component)
[3] 摩耗 (Cause)
Allowed relations (head -> tail):
[0] -> [1]: CAUSED_BY
[0] -> [3]: CAUSED_BY
Answer: {"relations": [{"head": 0, "tail": 1, "type": "CAUSED_BY", "negated": true, "hedged": false, "confidence": 0.85}, {"head": 0, "tail": 3, "type": "CAUSED_BY", "negated": false, "hedged": false, "confidence": 0.9}]}

Example (hand-written, Japanese):
Sentence: なぜなぜ分析で真因を追究し、ポカヨケを設置して再発を防いだ。
Entities:
[0] なぜなぜ分析 (TPSConcept)
[1] ポカヨケ (TPSConcept)
Allowed relations (head -> tail):
(none)
Answer: {"relations": []}
