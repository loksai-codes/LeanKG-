Example (hand-written):
Sentence: Technicians found a crack in the housing after the pump overheated.
Entities:
[0] crack (FailureMode)
[1] pump (Component)
[2] overheated (FailureMode)
Allowed relations (head -> tail):
[0] -> [2]: CAUSED_BY
[2] -> [0]: CAUSED_BY
[1] -> [0]: HAS_FAILURE_MODE
[1] -> [2]: HAS_FAILURE_MODE
Answer: {"relations": [{"head": 1, "tail": 2, "type": "HAS_FAILURE_MODE", "negated": false, "hedged": false, "confidence": 0.85}, {"head": 0, "tail": 2, "type": "CAUSED_BY", "negated": false, "hedged": true, "confidence": 0.55}]}

Example (hand-written):
Sentence: Corrosion was ruled out as the reason for the leak.
Entities:
[0] Corrosion (Cause)
[1] leak (FailureMode)
Allowed relations (head -> tail):
[1] -> [0]: CAUSED_BY
Answer: {"relations": [{"head": 1, "tail": 0, "type": "CAUSED_BY", "negated": true, "hedged": false, "confidence": 0.85}]}

Example (hand-written):
Sentence: The bearing and the seal were cleaned during the shift.
Entities:
[0] bearing (Component)
[1] seal (Component)
[2] cleaned (MaintenanceAction)
Allowed relations (head -> tail):
[0] -> [1]: PART_OF
[1] -> [0]: PART_OF
[0] -> [2]: FIXED_BY
[1] -> [2]: FIXED_BY
Answer: {"relations": []}
