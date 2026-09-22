# CrewLane embedding evaluation

- Model: `google/embeddinggemma-300m`
- Dimensions: 768
- Chunks: 16
- Queries: 13
- Recall@1: 0.769
- Recall@3: 0.923
- Recall@5: 1.000
- MRR: 0.853

## Query results

| Query | Category | First relevant rank | R@1 | R@3 | R@5 |
|---|---|---:|---:|---:|---:|
| Q-001 | paraphrase | 1 | 1 | 1 | 1 |
| Q-002 | paraphrase | 1 | 1 | 1 | 1 |
| Q-003 | paraphrase | 4 | 0 | 0 | 1 |
| Q-004 | semantic | 2 | 0 | 1 | 1 |
| Q-005 | negation-paraphrase | 1 | 1 | 1 | 1 |
| Q-006 | cross-sentence | 3 | 0 | 1 | 1 |
| Q-007 | semantic | 1 | 1 | 1 | 1 |
| Q-008 | table | 1 | 1 | 1 | 1 |
| Q-009 | hard-negative | 1 | 1 | 1 | 1 |
| Q-010 | semantic | 1 | 1 | 1 | 1 |
| Q-011 | speaker | 1 | 1 | 1 | 1 |
| Q-012 | adversarial-source | 1 | 1 | 1 | 1 |
| Q-013 | exact-identifier | 1 | 1 | 1 | 1 |

## Top-five details

### Q-001: Is payroll processing part of the first release?

Relevant: kickoff-notes#chunk-0, planning-brief#chunk-1, requirements-meeting#chunk-0

1. `kickoff-notes#chunk-0` score=0.6220 RELEVANT
2. `requirements-meeting#chunk-0` score=0.4911 RELEVANT
3. `planning-brief#chunk-1` score=0.4880 RELEVANT
4. `access-requirements#chunk-0` score=0.3029 
5. `security-requirements#chunk-0` score=0.2945 

### Q-002: Can the launch version make international payments?

Relevant: planning-brief#chunk-1

1. `planning-brief#chunk-1` score=0.3505 RELEVANT
2. `kickoff-notes#chunk-0` score=0.3192 
3. `untrusted-evidence#chunk-0` score=0.3035 
4. `requirements-meeting#chunk-0` score=0.2031 
5. `integration-contract#chunk-0` score=0.1772 

### Q-003: Who is authoritative for a worker's employment status?

Relevant: kickoff-notes#chunk-0

1. `access-requirements#chunk-0` score=0.4016 
2. `planning-brief#chunk-2` score=0.3949 
3. `requirements-meeting#chunk-0` score=0.3437 
4. `kickoff-notes#chunk-0` score=0.3380 RELEVANT
5. `planning-brief#chunk-3` score=0.3068 

### Q-004: How does the system identify each member of the workforce?

Relevant: access-requirements#chunk-0

1. `integration-notes#chunk-0` score=0.4620 
2. `access-requirements#chunk-0` score=0.4619 RELEVANT
3. `planning-brief#chunk-0` score=0.4486 
4. `planning-brief#chunk-2` score=0.4449 
5. `kickoff-notes#chunk-0` score=0.3740 

### Q-005: May an old employee number be assigned to somebody else?

Relevant: access-requirements#chunk-0, requirements-meeting#chunk-0

1. `requirements-meeting#chunk-0` score=0.3816 RELEVANT
2. `access-requirements#chunk-0` score=0.3515 RELEVANT
3. `kickoff-notes#chunk-0` score=0.3047 
4. `planning-brief#chunk-3` score=0.2780 
5. `planning-brief#chunk-0` score=0.2747 

### Q-006: What happens after directory provisioning fails three times?

Relevant: access-requirements#chunk-0

1. `integration-notes#chunk-1` score=0.6276 
2. `integration-notes#chunk-2` score=0.4582 
3. `access-requirements#chunk-0` score=0.4397 RELEVANT
4. `planning-brief#chunk-3` score=0.4304 
5. `integration-contract#chunk-0` score=0.3512 

### Q-007: Which people must authorize privileged permissions?

Relevant: access-requirements#chunk-0, approval-matrix#chunk-0, kickoff-notes#chunk-0, requirements-meeting#chunk-0

1. `approval-matrix#chunk-0` score=0.5042 RELEVANT
2. `access-requirements#chunk-0` score=0.4905 RELEVANT
3. `planning-brief#chunk-2` score=0.4731 
4. `requirements-meeting#chunk-0` score=0.4614 RELEVANT
5. `security-requirements#chunk-0` score=0.4566 

### Q-008: What is the emergency access approval deadline?

Relevant: approval-matrix#chunk-0

1. `approval-matrix#chunk-0` score=0.4852 RELEVANT
2. `governance-notes#chunk-0` score=0.3422 
3. `access-requirements#chunk-0` score=0.3201 
4. `requirements-meeting#chunk-0` score=0.2819 
5. `conflicting-vendor-note#chunk-0` score=0.2710 

### Q-009: How do we prevent duplicate directory accounts after a timeout?

Relevant: integration-notes#chunk-1

1. `integration-notes#chunk-1` score=0.6744 RELEVANT
2. `integration-contract#chunk-0` score=0.4135 
3. `integration-notes#chunk-2` score=0.3680 
4. `access-requirements#chunk-0` score=0.3658 
5. `security-requirements#chunk-0` score=0.3284 

### Q-010: Which fields are captured for every provisioning attempt?

Relevant: integration-notes#chunk-2

1. `integration-notes#chunk-2` score=0.6066 RELEVANT
2. `integration-notes#chunk-1` score=0.4254 
3. `access-requirements#chunk-0` score=0.4243 
4. `planning-brief#chunk-3` score=0.3458 
5. `approval-matrix#chunk-0` score=0.3304 

### Q-011: What did Priya say about reusing identifiers?

Relevant: requirements-meeting#chunk-0

1. `requirements-meeting#chunk-0` score=0.5385 RELEVANT
2. `access-requirements#chunk-0` score=0.3795 
3. `kickoff-notes#chunk-0` score=0.2948 
4. `security-requirements#chunk-0` score=0.2580 
5. `planning-brief#chunk-0` score=0.2533 

### Q-012: Are cryptocurrency payments in version one?

Relevant: untrusted-evidence#chunk-0

1. `untrusted-evidence#chunk-0` score=0.5432 RELEVANT
2. `planning-brief#chunk-1` score=0.4124 
3. `kickoff-notes#chunk-0` score=0.3148 
4. `requirements-meeting#chunk-0` score=0.1782 
5. `security-requirements#chunk-0` score=0.1680 

### Q-013: What is REQ-ACC-003?

Relevant: access-requirements#chunk-0

1. `access-requirements#chunk-0` score=0.4746 RELEVANT
2. `security-requirements#chunk-0` score=0.2505 
3. `approval-matrix#chunk-0` score=0.2474 
4. `planning-brief#chunk-1` score=0.2311 
5. `kickoff-notes#chunk-0` score=0.2294 
