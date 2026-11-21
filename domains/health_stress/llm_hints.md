Example (hand-written):
Sentence: Work stress was linked to a higher risk of burnout among nurses.
Entities:
[0] Work stress (Stressor)
[1] burnout (Condition)
Allowed relations (head -> tail):
[0] -> [1]: INCREASES_RISK_OF, ASSOCIATED_WITH
[1] -> [0]: ASSOCIATED_WITH
Answer: {"relations": [{"head": 0, "tail": 1, "type": "INCREASES_RISK_OF", "negated": false, "hedged": false, "confidence": 0.8}]}

Example (hand-written):
Sentence: Yoga showed no effect on cortisol.
Entities:
[0] Yoga (Intervention)
[1] cortisol (Biomarker)
Allowed relations (head -> tail):
[0] -> [1]: REDUCES, ASSOCIATED_WITH
[1] -> [0]: ASSOCIATED_WITH
Answer: {"relations": [{"head": 0, "tail": 1, "type": "REDUCES", "negated": true, "hedged": false, "confidence": 0.85}]}

Example (hand-written):
Sentence: Patients with depression and patients with hypertension were recruited.
Entities:
[0] depression (Condition)
[1] hypertension (Condition)
Allowed relations (head -> tail):
[0] -> [1]: INCREASES_RISK_OF, ASSOCIATED_WITH
[1] -> [0]: INCREASES_RISK_OF, ASSOCIATED_WITH
Answer: {"relations": []}
