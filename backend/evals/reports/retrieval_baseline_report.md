# CrewLane PostgreSQL retrieval baseline

Corpus: 16 evidence chunks + 10 cards | Queries: 40 | topK=5 | RRF k=60

## Method comparison

| Method | R@1 | R@3 | R@5 | Useful R@5 | MRR | nDCG@5 | P@5 | No-answer | Mean ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vector_no_floor | 0.889 | 0.972 | 1.000 | 1.000 | 0.933 | 0.918 | 0.378 | 0.000 | 97.94 |
| vector_0.25 | 0.889 | 0.972 | 1.000 | 1.000 | 0.933 | 0.918 | 0.378 | 0.250 | 95.08 |
| vector_0.30 | 0.889 | 0.972 | 1.000 | 1.000 | 0.933 | 0.918 | 0.378 | 0.500 | 96.09 |
| vector_0.35 | 0.861 | 0.944 | 0.972 | 0.972 | 0.905 | 0.878 | 0.367 | 0.750 | 97.12 |
| vector_0.40 | 0.806 | 0.833 | 0.833 | 0.861 | 0.819 | 0.741 | 0.300 | 0.750 | 96.21 |
| fts | 0.083 | 0.083 | 0.083 | 0.083 | 0.083 | 0.063 | 0.017 | 1.000 | 9.19 |
| hybrid_0.25 | 0.889 | 0.972 | 1.000 | 1.000 | 0.933 | 0.918 | 0.378 | 0.250 | 104.30 |
| hybrid_0.30 | 0.889 | 0.972 | 1.000 | 1.000 | 0.933 | 0.918 | 0.378 | 0.500 | 105.29 |
| hybrid_0.35 | 0.889 | 0.972 | 1.000 | 1.000 | 0.933 | 0.906 | 0.372 | 0.750 | 106.31 |
| hybrid_0.40 | 0.833 | 0.861 | 0.861 | 0.889 | 0.847 | 0.768 | 0.306 | 0.750 | 105.40 |
| production_hybrid | 0.889 | 1.000 | 1.000 | 1.000 | 0.944 | 0.923 | 0.378 | 0.750 | 360.93 |

## Per-query rankings

### R-001: Is payroll processing part of the first release?

- **vector_no_floor:** kickoff-notes#chunk-0 (0.6220), card-scope-v1 (0.5551), requirements-meeting#chunk-0 (0.4911), planning-brief#chunk-1 (0.4880), access-requirements#chunk-0 (0.3029)
- **vector_0.25:** kickoff-notes#chunk-0 (0.6220), card-scope-v1 (0.5551), requirements-meeting#chunk-0 (0.4911), planning-brief#chunk-1 (0.4880), access-requirements#chunk-0 (0.3029)
- **vector_0.30:** kickoff-notes#chunk-0 (0.6220), card-scope-v1 (0.5551), requirements-meeting#chunk-0 (0.4911), planning-brief#chunk-1 (0.4880), access-requirements#chunk-0 (0.3029)
- **vector_0.35:** kickoff-notes#chunk-0 (0.6220), card-scope-v1 (0.5551), requirements-meeting#chunk-0 (0.4911), planning-brief#chunk-1 (0.4880)
- **vector_0.40:** kickoff-notes#chunk-0 (0.6220), card-scope-v1 (0.5551), requirements-meeting#chunk-0 (0.4911), planning-brief#chunk-1 (0.4880)
- **fts:** kickoff-notes#chunk-0 (0.9777)
- **hybrid_0.25:** kickoff-notes#chunk-0 (0.0328), card-scope-v1 (0.0161), requirements-meeting#chunk-0 (0.0159), planning-brief#chunk-1 (0.0156), access-requirements#chunk-0 (0.0154)
- **hybrid_0.30:** kickoff-notes#chunk-0 (0.0328), card-scope-v1 (0.0161), requirements-meeting#chunk-0 (0.0159), planning-brief#chunk-1 (0.0156), access-requirements#chunk-0 (0.0154)
- **hybrid_0.35:** kickoff-notes#chunk-0 (0.0328), card-scope-v1 (0.0161), requirements-meeting#chunk-0 (0.0159), planning-brief#chunk-1 (0.0156)
- **hybrid_0.40:** kickoff-notes#chunk-0 (0.0328), card-scope-v1 (0.0161), requirements-meeting#chunk-0 (0.0159), planning-brief#chunk-1 (0.0156)
- **production_hybrid:** kickoff-notes#chunk-0 (0.0328), requirements-meeting#chunk-0 (0.0320), card-scope-v1 (0.0161), planning-brief#chunk-1 (0.0156)

### R-002: Can the launch version make international payments?

- **vector_no_floor:** card-scope-v1 (0.4284), planning-brief#chunk-1 (0.3505), kickoff-notes#chunk-0 (0.3192), untrusted-evidence#chunk-0 (0.3035), requirements-meeting#chunk-0 (0.2031)
- **vector_0.25:** card-scope-v1 (0.4284), planning-brief#chunk-1 (0.3505), kickoff-notes#chunk-0 (0.3192), untrusted-evidence#chunk-0 (0.3035)
- **vector_0.30:** card-scope-v1 (0.4284), planning-brief#chunk-1 (0.3505), kickoff-notes#chunk-0 (0.3192), untrusted-evidence#chunk-0 (0.3035)
- **vector_0.35:** card-scope-v1 (0.4284), planning-brief#chunk-1 (0.3505)
- **vector_0.40:** card-scope-v1 (0.4284)
- **fts:** no results
- **hybrid_0.25:** card-scope-v1 (0.0164), planning-brief#chunk-1 (0.0161), kickoff-notes#chunk-0 (0.0159), untrusted-evidence#chunk-0 (0.0156)
- **hybrid_0.30:** card-scope-v1 (0.0164), planning-brief#chunk-1 (0.0161), kickoff-notes#chunk-0 (0.0159), untrusted-evidence#chunk-0 (0.0156)
- **hybrid_0.35:** card-scope-v1 (0.0164), planning-brief#chunk-1 (0.0161)
- **hybrid_0.40:** card-scope-v1 (0.0164)
- **production_hybrid:** card-scope-v1 (0.0325), planning-brief#chunk-1 (0.0325), untrusted-evidence#chunk-0 (0.0159)

### R-003: Who is authoritative for a worker's employment status?

- **vector_no_floor:** card-worker-source (0.5701), card-identity-policy (0.4177), access-requirements#chunk-0 (0.4016), planning-brief#chunk-2 (0.3949), requirements-meeting#chunk-0 (0.3437)
- **vector_0.25:** card-worker-source (0.5701), card-identity-policy (0.4177), access-requirements#chunk-0 (0.4016), planning-brief#chunk-2 (0.3949), requirements-meeting#chunk-0 (0.3437)
- **vector_0.30:** card-worker-source (0.5701), card-identity-policy (0.4177), access-requirements#chunk-0 (0.4016), planning-brief#chunk-2 (0.3949), requirements-meeting#chunk-0 (0.3437)
- **vector_0.35:** card-worker-source (0.5701), card-identity-policy (0.4177), access-requirements#chunk-0 (0.4016), planning-brief#chunk-2 (0.3949)
- **vector_0.40:** card-worker-source (0.5701), card-identity-policy (0.4177), access-requirements#chunk-0 (0.4016)
- **fts:** no results
- **hybrid_0.25:** card-worker-source (0.0164), card-identity-policy (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156), requirements-meeting#chunk-0 (0.0154)
- **hybrid_0.30:** card-worker-source (0.0164), card-identity-policy (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156), requirements-meeting#chunk-0 (0.0154)
- **hybrid_0.35:** card-worker-source (0.0164), card-identity-policy (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156)
- **hybrid_0.40:** card-worker-source (0.0164), card-identity-policy (0.0161), access-requirements#chunk-0 (0.0159)
- **production_hybrid:** card-worker-source (0.0328), card-identity-policy (0.0323), access-requirements#chunk-0 (0.0315), kickoff-notes#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156)

### R-004: How does the system identify each member of the workforce?

- **vector_no_floor:** card-identity-policy (0.6214), integration-notes#chunk-0 (0.4620), access-requirements#chunk-0 (0.4619), planning-brief#chunk-0 (0.4486), planning-brief#chunk-2 (0.4449)
- **vector_0.25:** card-identity-policy (0.6214), integration-notes#chunk-0 (0.4620), access-requirements#chunk-0 (0.4619), planning-brief#chunk-0 (0.4486), planning-brief#chunk-2 (0.4449)
- **vector_0.30:** card-identity-policy (0.6214), integration-notes#chunk-0 (0.4620), access-requirements#chunk-0 (0.4619), planning-brief#chunk-0 (0.4486), planning-brief#chunk-2 (0.4449)
- **vector_0.35:** card-identity-policy (0.6214), integration-notes#chunk-0 (0.4620), access-requirements#chunk-0 (0.4619), planning-brief#chunk-0 (0.4486), planning-brief#chunk-2 (0.4449)
- **vector_0.40:** card-identity-policy (0.6214), integration-notes#chunk-0 (0.4620), access-requirements#chunk-0 (0.4619), planning-brief#chunk-0 (0.4486), planning-brief#chunk-2 (0.4449)
- **fts:** no results
- **hybrid_0.25:** card-identity-policy (0.0164), integration-notes#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-0 (0.0156), planning-brief#chunk-2 (0.0154)
- **hybrid_0.30:** card-identity-policy (0.0164), integration-notes#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-0 (0.0156), planning-brief#chunk-2 (0.0154)
- **hybrid_0.35:** card-identity-policy (0.0164), integration-notes#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-0 (0.0156), planning-brief#chunk-2 (0.0154)
- **hybrid_0.40:** card-identity-policy (0.0164), integration-notes#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-0 (0.0156), planning-brief#chunk-2 (0.0154)
- **production_hybrid:** access-requirements#chunk-0 (0.0323), planning-brief#chunk-0 (0.0318), card-identity-policy (0.0164), integration-notes#chunk-0 (0.0161), planning-brief#chunk-3 (0.0159)

### R-005: May an old employee number be assigned to somebody else?

- **vector_no_floor:** card-identity-policy (0.4860), requirements-meeting#chunk-0 (0.3816), access-requirements#chunk-0 (0.3515), kickoff-notes#chunk-0 (0.3047), card-worker-source (0.2979)
- **vector_0.25:** card-identity-policy (0.4860), requirements-meeting#chunk-0 (0.3816), access-requirements#chunk-0 (0.3515), kickoff-notes#chunk-0 (0.3047), card-worker-source (0.2979)
- **vector_0.30:** card-identity-policy (0.4860), requirements-meeting#chunk-0 (0.3816), access-requirements#chunk-0 (0.3515), kickoff-notes#chunk-0 (0.3047)
- **vector_0.35:** card-identity-policy (0.4860), requirements-meeting#chunk-0 (0.3816), access-requirements#chunk-0 (0.3515)
- **vector_0.40:** card-identity-policy (0.4860)
- **fts:** no results
- **hybrid_0.25:** card-identity-policy (0.0164), requirements-meeting#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), kickoff-notes#chunk-0 (0.0156), card-worker-source (0.0154)
- **hybrid_0.30:** card-identity-policy (0.0164), requirements-meeting#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), kickoff-notes#chunk-0 (0.0156)
- **hybrid_0.35:** card-identity-policy (0.0164), requirements-meeting#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159)
- **hybrid_0.40:** card-identity-policy (0.0164)
- **production_hybrid:** card-identity-policy (0.0164), planning-brief#chunk-3 (0.0164), requirements-meeting#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159)

### R-006: What happens after directory provisioning fails three times?

- **vector_no_floor:** card-retry-policy (0.8037), integration-notes#chunk-1 (0.6276), integration-notes#chunk-2 (0.4582), access-requirements#chunk-0 (0.4397), planning-brief#chunk-3 (0.4304)
- **vector_0.25:** card-retry-policy (0.8037), integration-notes#chunk-1 (0.6276), integration-notes#chunk-2 (0.4582), access-requirements#chunk-0 (0.4397), planning-brief#chunk-3 (0.4304)
- **vector_0.30:** card-retry-policy (0.8037), integration-notes#chunk-1 (0.6276), integration-notes#chunk-2 (0.4582), access-requirements#chunk-0 (0.4397), planning-brief#chunk-3 (0.4304)
- **vector_0.35:** card-retry-policy (0.8037), integration-notes#chunk-1 (0.6276), integration-notes#chunk-2 (0.4582), access-requirements#chunk-0 (0.4397), planning-brief#chunk-3 (0.4304)
- **vector_0.40:** card-retry-policy (0.8037), integration-notes#chunk-1 (0.6276), integration-notes#chunk-2 (0.4582), access-requirements#chunk-0 (0.4397), planning-brief#chunk-3 (0.4304)
- **fts:** no results
- **hybrid_0.25:** card-retry-policy (0.0164), integration-notes#chunk-1 (0.0161), integration-notes#chunk-2 (0.0159), access-requirements#chunk-0 (0.0156), planning-brief#chunk-3 (0.0154)
- **hybrid_0.30:** card-retry-policy (0.0164), integration-notes#chunk-1 (0.0161), integration-notes#chunk-2 (0.0159), access-requirements#chunk-0 (0.0156), planning-brief#chunk-3 (0.0154)
- **hybrid_0.35:** card-retry-policy (0.0164), integration-notes#chunk-1 (0.0161), integration-notes#chunk-2 (0.0159), access-requirements#chunk-0 (0.0156), planning-brief#chunk-3 (0.0154)
- **hybrid_0.40:** card-retry-policy (0.0164), integration-notes#chunk-1 (0.0161), integration-notes#chunk-2 (0.0159), access-requirements#chunk-0 (0.0156), planning-brief#chunk-3 (0.0154)
- **production_hybrid:** card-retry-policy (0.0325), integration-notes#chunk-1 (0.0325), access-requirements#chunk-0 (0.0315), integration-notes#chunk-2 (0.0313), integration-notes#chunk-0 (0.0156)

### R-007: Which people must authorize privileged permissions?

- **vector_no_floor:** card-privileged-approval (0.6440), approval-matrix#chunk-0 (0.5042), access-requirements#chunk-0 (0.4905), planning-brief#chunk-2 (0.4731), requirements-meeting#chunk-0 (0.4614)
- **vector_0.25:** card-privileged-approval (0.6440), approval-matrix#chunk-0 (0.5042), access-requirements#chunk-0 (0.4905), planning-brief#chunk-2 (0.4731), requirements-meeting#chunk-0 (0.4614)
- **vector_0.30:** card-privileged-approval (0.6440), approval-matrix#chunk-0 (0.5042), access-requirements#chunk-0 (0.4905), planning-brief#chunk-2 (0.4731), requirements-meeting#chunk-0 (0.4614)
- **vector_0.35:** card-privileged-approval (0.6440), approval-matrix#chunk-0 (0.5042), access-requirements#chunk-0 (0.4905), planning-brief#chunk-2 (0.4731), requirements-meeting#chunk-0 (0.4614)
- **vector_0.40:** card-privileged-approval (0.6440), approval-matrix#chunk-0 (0.5042), access-requirements#chunk-0 (0.4905), planning-brief#chunk-2 (0.4731), requirements-meeting#chunk-0 (0.4614)
- **fts:** no results
- **hybrid_0.25:** card-privileged-approval (0.0164), approval-matrix#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156), requirements-meeting#chunk-0 (0.0154)
- **hybrid_0.30:** card-privileged-approval (0.0164), approval-matrix#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156), requirements-meeting#chunk-0 (0.0154)
- **hybrid_0.35:** card-privileged-approval (0.0164), approval-matrix#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156), requirements-meeting#chunk-0 (0.0154)
- **hybrid_0.40:** card-privileged-approval (0.0164), approval-matrix#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156), requirements-meeting#chunk-0 (0.0154)
- **production_hybrid:** access-requirements#chunk-0 (0.0323), approval-matrix#chunk-0 (0.0318), kickoff-notes#chunk-0 (0.0311), security-requirements#chunk-0 (0.0310), card-privileged-approval (0.0164)

### R-008: What is the emergency access approval deadline?

- **vector_no_floor:** approval-matrix#chunk-0 (0.4852), card-privileged-approval (0.3445), governance-notes#chunk-0 (0.3422), access-requirements#chunk-0 (0.3201), requirements-meeting#chunk-0 (0.2819)
- **vector_0.25:** approval-matrix#chunk-0 (0.4852), card-privileged-approval (0.3445), governance-notes#chunk-0 (0.3422), access-requirements#chunk-0 (0.3201), requirements-meeting#chunk-0 (0.2819)
- **vector_0.30:** approval-matrix#chunk-0 (0.4852), card-privileged-approval (0.3445), governance-notes#chunk-0 (0.3422), access-requirements#chunk-0 (0.3201)
- **vector_0.35:** approval-matrix#chunk-0 (0.4852)
- **vector_0.40:** approval-matrix#chunk-0 (0.4852)
- **fts:** no results
- **hybrid_0.25:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), governance-notes#chunk-0 (0.0159), access-requirements#chunk-0 (0.0156), requirements-meeting#chunk-0 (0.0154)
- **hybrid_0.30:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), governance-notes#chunk-0 (0.0159), access-requirements#chunk-0 (0.0156)
- **hybrid_0.35:** approval-matrix#chunk-0 (0.0164)
- **hybrid_0.40:** approval-matrix#chunk-0 (0.0164)
- **production_hybrid:** approval-matrix#chunk-0 (0.0328), access-requirements#chunk-0 (0.0161), planning-brief#chunk-1 (0.0159), planning-brief#chunk-2 (0.0156), requirements-meeting#chunk-0 (0.0154)

### R-009: How do we prevent duplicate directory accounts after a timeout?

- **vector_no_floor:** integration-notes#chunk-1 (0.6744), integration-contract#chunk-0 (0.4135), card-retry-policy (0.4052), integration-notes#chunk-2 (0.3680), card-privileged-security (0.3671)
- **vector_0.25:** integration-notes#chunk-1 (0.6744), integration-contract#chunk-0 (0.4135), card-retry-policy (0.4052), integration-notes#chunk-2 (0.3680), card-privileged-security (0.3671)
- **vector_0.30:** integration-notes#chunk-1 (0.6744), integration-contract#chunk-0 (0.4135), card-retry-policy (0.4052), integration-notes#chunk-2 (0.3680), card-privileged-security (0.3671)
- **vector_0.35:** integration-notes#chunk-1 (0.6744), integration-contract#chunk-0 (0.4135), card-retry-policy (0.4052), integration-notes#chunk-2 (0.3680), card-privileged-security (0.3671)
- **vector_0.40:** integration-notes#chunk-1 (0.6744), integration-contract#chunk-0 (0.4135), card-retry-policy (0.4052)
- **fts:** no results
- **hybrid_0.25:** integration-notes#chunk-1 (0.0164), integration-contract#chunk-0 (0.0161), card-retry-policy (0.0159), integration-notes#chunk-2 (0.0156), card-privileged-security (0.0154)
- **hybrid_0.30:** integration-notes#chunk-1 (0.0164), integration-contract#chunk-0 (0.0161), card-retry-policy (0.0159), integration-notes#chunk-2 (0.0156), card-privileged-security (0.0154)
- **hybrid_0.35:** integration-notes#chunk-1 (0.0164), integration-contract#chunk-0 (0.0161), card-retry-policy (0.0159), integration-notes#chunk-2 (0.0156), card-privileged-security (0.0154)
- **hybrid_0.40:** integration-notes#chunk-1 (0.0164), integration-contract#chunk-0 (0.0161), card-retry-policy (0.0159)
- **production_hybrid:** integration-notes#chunk-1 (0.0328), integration-contract#chunk-0 (0.0161), integration-notes#chunk-0 (0.0161), card-retry-policy (0.0159), integration-notes#chunk-2 (0.0156)

### R-010: Which fields are captured for every provisioning attempt?

- **vector_no_floor:** card-provisioning-audit (0.7011), integration-notes#chunk-2 (0.6066), card-retry-policy (0.4557), integration-notes#chunk-1 (0.4254), access-requirements#chunk-0 (0.4243)
- **vector_0.25:** card-provisioning-audit (0.7011), integration-notes#chunk-2 (0.6066), card-retry-policy (0.4557), integration-notes#chunk-1 (0.4254), access-requirements#chunk-0 (0.4243)
- **vector_0.30:** card-provisioning-audit (0.7011), integration-notes#chunk-2 (0.6066), card-retry-policy (0.4557), integration-notes#chunk-1 (0.4254), access-requirements#chunk-0 (0.4243)
- **vector_0.35:** card-provisioning-audit (0.7011), integration-notes#chunk-2 (0.6066), card-retry-policy (0.4557), integration-notes#chunk-1 (0.4254), access-requirements#chunk-0 (0.4243)
- **vector_0.40:** card-provisioning-audit (0.7011), integration-notes#chunk-2 (0.6066), card-retry-policy (0.4557), integration-notes#chunk-1 (0.4254), access-requirements#chunk-0 (0.4243)
- **fts:** no results
- **hybrid_0.25:** card-provisioning-audit (0.0164), integration-notes#chunk-2 (0.0161), card-retry-policy (0.0159), integration-notes#chunk-1 (0.0156), access-requirements#chunk-0 (0.0154)
- **hybrid_0.30:** card-provisioning-audit (0.0164), integration-notes#chunk-2 (0.0161), card-retry-policy (0.0159), integration-notes#chunk-1 (0.0156), access-requirements#chunk-0 (0.0154)
- **hybrid_0.35:** card-provisioning-audit (0.0164), integration-notes#chunk-2 (0.0161), card-retry-policy (0.0159), integration-notes#chunk-1 (0.0156), access-requirements#chunk-0 (0.0154)
- **hybrid_0.40:** card-provisioning-audit (0.0164), integration-notes#chunk-2 (0.0161), card-retry-policy (0.0159), integration-notes#chunk-1 (0.0156), access-requirements#chunk-0 (0.0154)
- **production_hybrid:** card-provisioning-audit (0.0328), integration-notes#chunk-2 (0.0320), access-requirements#chunk-0 (0.0315), card-retry-policy (0.0159), integration-notes#chunk-1 (0.0156)

### R-011: What did Priya say about reusing identifiers?

- **vector_no_floor:** requirements-meeting#chunk-0 (0.5385), card-identity-policy (0.4256), access-requirements#chunk-0 (0.3795), kickoff-notes#chunk-0 (0.2948), security-requirements#chunk-0 (0.2580)
- **vector_0.25:** requirements-meeting#chunk-0 (0.5385), card-identity-policy (0.4256), access-requirements#chunk-0 (0.3795), kickoff-notes#chunk-0 (0.2948), security-requirements#chunk-0 (0.2580)
- **vector_0.30:** requirements-meeting#chunk-0 (0.5385), card-identity-policy (0.4256), access-requirements#chunk-0 (0.3795)
- **vector_0.35:** requirements-meeting#chunk-0 (0.5385), card-identity-policy (0.4256), access-requirements#chunk-0 (0.3795)
- **vector_0.40:** requirements-meeting#chunk-0 (0.5385), card-identity-policy (0.4256)
- **fts:** no results
- **hybrid_0.25:** requirements-meeting#chunk-0 (0.0164), card-identity-policy (0.0161), access-requirements#chunk-0 (0.0159), kickoff-notes#chunk-0 (0.0156), security-requirements#chunk-0 (0.0154)
- **hybrid_0.30:** requirements-meeting#chunk-0 (0.0164), card-identity-policy (0.0161), access-requirements#chunk-0 (0.0159)
- **hybrid_0.35:** requirements-meeting#chunk-0 (0.0164), card-identity-policy (0.0161), access-requirements#chunk-0 (0.0159)
- **hybrid_0.40:** requirements-meeting#chunk-0 (0.0164), card-identity-policy (0.0161)
- **production_hybrid:** requirements-meeting#chunk-0 (0.0328), card-identity-policy (0.0161), access-requirements#chunk-0 (0.0159)

### R-012: Are cryptocurrency payments in version one?

- **vector_no_floor:** untrusted-evidence#chunk-0 (0.5432), card-scope-v1 (0.5040), planning-brief#chunk-1 (0.4124), kickoff-notes#chunk-0 (0.3148), requirements-meeting#chunk-0 (0.1782)
- **vector_0.25:** untrusted-evidence#chunk-0 (0.5432), card-scope-v1 (0.5040), planning-brief#chunk-1 (0.4124), kickoff-notes#chunk-0 (0.3148)
- **vector_0.30:** untrusted-evidence#chunk-0 (0.5432), card-scope-v1 (0.5040), planning-brief#chunk-1 (0.4124), kickoff-notes#chunk-0 (0.3148)
- **vector_0.35:** untrusted-evidence#chunk-0 (0.5432), card-scope-v1 (0.5040), planning-brief#chunk-1 (0.4124)
- **vector_0.40:** untrusted-evidence#chunk-0 (0.5432), card-scope-v1 (0.5040), planning-brief#chunk-1 (0.4124)
- **fts:** untrusted-evidence#chunk-0 (0.7108)
- **hybrid_0.25:** untrusted-evidence#chunk-0 (0.0328), card-scope-v1 (0.0161), planning-brief#chunk-1 (0.0159), kickoff-notes#chunk-0 (0.0156)
- **hybrid_0.30:** untrusted-evidence#chunk-0 (0.0328), card-scope-v1 (0.0161), planning-brief#chunk-1 (0.0159), kickoff-notes#chunk-0 (0.0156)
- **hybrid_0.35:** untrusted-evidence#chunk-0 (0.0328), card-scope-v1 (0.0161), planning-brief#chunk-1 (0.0159)
- **hybrid_0.40:** untrusted-evidence#chunk-0 (0.0328), card-scope-v1 (0.0161), planning-brief#chunk-1 (0.0159)
- **production_hybrid:** untrusted-evidence#chunk-0 (0.0328), card-scope-v1 (0.0320), planning-brief#chunk-1 (0.0320), kickoff-notes#chunk-0 (0.0156)

### R-013: What is REQ-ACC-003?

- **vector_no_floor:** access-requirements#chunk-0 (0.4746), security-requirements#chunk-0 (0.2505), approval-matrix#chunk-0 (0.2474), card-privileged-security (0.2385), planning-brief#chunk-1 (0.2311)
- **vector_0.25:** access-requirements#chunk-0 (0.4746), security-requirements#chunk-0 (0.2505)
- **vector_0.30:** access-requirements#chunk-0 (0.4746)
- **vector_0.35:** access-requirements#chunk-0 (0.4746)
- **vector_0.40:** access-requirements#chunk-0 (0.4746)
- **fts:** no results
- **hybrid_0.25:** access-requirements#chunk-0 (0.0164), security-requirements#chunk-0 (0.0161)
- **hybrid_0.30:** access-requirements#chunk-0 (0.0164)
- **hybrid_0.35:** access-requirements#chunk-0 (0.0164)
- **hybrid_0.40:** access-requirements#chunk-0 (0.0164)
- **production_hybrid:** access-requirements#chunk-0 (0.0549)

### R-014: What capabilities are included in version one?

- **vector_no_floor:** card-scope-v1 (0.6465), planning-brief#chunk-1 (0.5473), kickoff-notes#chunk-0 (0.4111), untrusted-evidence#chunk-0 (0.3002), requirements-meeting#chunk-0 (0.2790)
- **vector_0.25:** card-scope-v1 (0.6465), planning-brief#chunk-1 (0.5473), kickoff-notes#chunk-0 (0.4111), untrusted-evidence#chunk-0 (0.3002), requirements-meeting#chunk-0 (0.2790)
- **vector_0.30:** card-scope-v1 (0.6465), planning-brief#chunk-1 (0.5473), kickoff-notes#chunk-0 (0.4111), untrusted-evidence#chunk-0 (0.3002)
- **vector_0.35:** card-scope-v1 (0.6465), planning-brief#chunk-1 (0.5473), kickoff-notes#chunk-0 (0.4111)
- **vector_0.40:** card-scope-v1 (0.6465), planning-brief#chunk-1 (0.5473), kickoff-notes#chunk-0 (0.4111)
- **fts:** no results
- **hybrid_0.25:** card-scope-v1 (0.0164), planning-brief#chunk-1 (0.0161), kickoff-notes#chunk-0 (0.0159), untrusted-evidence#chunk-0 (0.0156), requirements-meeting#chunk-0 (0.0154)
- **hybrid_0.30:** card-scope-v1 (0.0164), planning-brief#chunk-1 (0.0161), kickoff-notes#chunk-0 (0.0159), untrusted-evidence#chunk-0 (0.0156)
- **hybrid_0.35:** card-scope-v1 (0.0164), planning-brief#chunk-1 (0.0161), kickoff-notes#chunk-0 (0.0159)
- **hybrid_0.40:** card-scope-v1 (0.0164), planning-brief#chunk-1 (0.0161), kickoff-notes#chunk-0 (0.0159)
- **production_hybrid:** card-scope-v1 (0.0325), planning-brief#chunk-1 (0.0325), kickoff-notes#chunk-0 (0.0317), untrusted-evidence#chunk-0 (0.0156)

### R-015: Who is the project sponsor?

- **vector_no_floor:** card-governance (0.4254), governance-notes#chunk-0 (0.4041), kickoff-notes#chunk-0 (0.3932), untrusted-evidence#chunk-0 (0.2919), conflicting-vendor-note#chunk-0 (0.2616)
- **vector_0.25:** card-governance (0.4254), governance-notes#chunk-0 (0.4041), kickoff-notes#chunk-0 (0.3932), untrusted-evidence#chunk-0 (0.2919), conflicting-vendor-note#chunk-0 (0.2616)
- **vector_0.30:** card-governance (0.4254), governance-notes#chunk-0 (0.4041), kickoff-notes#chunk-0 (0.3932)
- **vector_0.35:** card-governance (0.4254), governance-notes#chunk-0 (0.4041), kickoff-notes#chunk-0 (0.3932)
- **vector_0.40:** card-governance (0.4254), governance-notes#chunk-0 (0.4041)
- **fts:** no results
- **hybrid_0.25:** card-governance (0.0164), governance-notes#chunk-0 (0.0161), kickoff-notes#chunk-0 (0.0159), untrusted-evidence#chunk-0 (0.0156), conflicting-vendor-note#chunk-0 (0.0154)
- **hybrid_0.30:** card-governance (0.0164), governance-notes#chunk-0 (0.0161), kickoff-notes#chunk-0 (0.0159)
- **hybrid_0.35:** card-governance (0.0164), governance-notes#chunk-0 (0.0161), kickoff-notes#chunk-0 (0.0159)
- **hybrid_0.40:** card-governance (0.0164), governance-notes#chunk-0 (0.0161)
- **production_hybrid:** kickoff-notes#chunk-0 (0.0323), card-governance (0.0164), governance-notes#chunk-0 (0.0161), untrusted-evidence#chunk-0 (0.0161), conflicting-vendor-note#chunk-0 (0.0159)

### R-016: Who approves an ordinary access request?

- **vector_no_floor:** approval-matrix#chunk-0 (0.5302), card-privileged-approval (0.5201), access-requirements#chunk-0 (0.4591), planning-brief#chunk-2 (0.4252), conflicting-vendor-note#chunk-0 (0.4158)
- **vector_0.25:** approval-matrix#chunk-0 (0.5302), card-privileged-approval (0.5201), access-requirements#chunk-0 (0.4591), planning-brief#chunk-2 (0.4252), conflicting-vendor-note#chunk-0 (0.4158)
- **vector_0.30:** approval-matrix#chunk-0 (0.5302), card-privileged-approval (0.5201), access-requirements#chunk-0 (0.4591), planning-brief#chunk-2 (0.4252), conflicting-vendor-note#chunk-0 (0.4158)
- **vector_0.35:** approval-matrix#chunk-0 (0.5302), card-privileged-approval (0.5201), access-requirements#chunk-0 (0.4591), planning-brief#chunk-2 (0.4252), conflicting-vendor-note#chunk-0 (0.4158)
- **vector_0.40:** approval-matrix#chunk-0 (0.5302), card-privileged-approval (0.5201), access-requirements#chunk-0 (0.4591), planning-brief#chunk-2 (0.4252), conflicting-vendor-note#chunk-0 (0.4158)
- **fts:** no results
- **hybrid_0.25:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156), conflicting-vendor-note#chunk-0 (0.0154)
- **hybrid_0.30:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156), conflicting-vendor-note#chunk-0 (0.0154)
- **hybrid_0.35:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156), conflicting-vendor-note#chunk-0 (0.0154)
- **hybrid_0.40:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), access-requirements#chunk-0 (0.0159), planning-brief#chunk-2 (0.0156), conflicting-vendor-note#chunk-0 (0.0154)
- **production_hybrid:** approval-matrix#chunk-0 (0.0328), conflicting-vendor-note#chunk-0 (0.0315), access-requirements#chunk-0 (0.0313), planning-brief#chunk-2 (0.0312), requirements-meeting#chunk-0 (0.0310)

### R-017: Who approves emergency access?

- **vector_no_floor:** approval-matrix#chunk-0 (0.5343), card-privileged-approval (0.4799), planning-brief#chunk-2 (0.3789), access-requirements#chunk-0 (0.3773), requirements-meeting#chunk-0 (0.3507)
- **vector_0.25:** approval-matrix#chunk-0 (0.5343), card-privileged-approval (0.4799), planning-brief#chunk-2 (0.3789), access-requirements#chunk-0 (0.3773), requirements-meeting#chunk-0 (0.3507)
- **vector_0.30:** approval-matrix#chunk-0 (0.5343), card-privileged-approval (0.4799), planning-brief#chunk-2 (0.3789), access-requirements#chunk-0 (0.3773), requirements-meeting#chunk-0 (0.3507)
- **vector_0.35:** approval-matrix#chunk-0 (0.5343), card-privileged-approval (0.4799), planning-brief#chunk-2 (0.3789), access-requirements#chunk-0 (0.3773), requirements-meeting#chunk-0 (0.3507)
- **vector_0.40:** approval-matrix#chunk-0 (0.5343), card-privileged-approval (0.4799)
- **fts:** no results
- **hybrid_0.25:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), planning-brief#chunk-2 (0.0159), access-requirements#chunk-0 (0.0156), requirements-meeting#chunk-0 (0.0154)
- **hybrid_0.30:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), planning-brief#chunk-2 (0.0159), access-requirements#chunk-0 (0.0156), requirements-meeting#chunk-0 (0.0154)
- **hybrid_0.35:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), planning-brief#chunk-2 (0.0159), access-requirements#chunk-0 (0.0156), requirements-meeting#chunk-0 (0.0154)
- **hybrid_0.40:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161)
- **production_hybrid:** approval-matrix#chunk-0 (0.0328), planning-brief#chunk-2 (0.0320), requirements-meeting#chunk-0 (0.0313), access-requirements#chunk-0 (0.0310), card-privileged-approval (0.0161)

### R-018: What information is sent to the directory service?

- **vector_no_floor:** integration-notes#chunk-0 (0.5913), integration-contract#chunk-0 (0.4942), integration-notes#chunk-1 (0.4446), integration-notes#chunk-2 (0.4236), card-retry-policy (0.3847)
- **vector_0.25:** integration-notes#chunk-0 (0.5913), integration-contract#chunk-0 (0.4942), integration-notes#chunk-1 (0.4446), integration-notes#chunk-2 (0.4236), card-retry-policy (0.3847)
- **vector_0.30:** integration-notes#chunk-0 (0.5913), integration-contract#chunk-0 (0.4942), integration-notes#chunk-1 (0.4446), integration-notes#chunk-2 (0.4236), card-retry-policy (0.3847)
- **vector_0.35:** integration-notes#chunk-0 (0.5913), integration-contract#chunk-0 (0.4942), integration-notes#chunk-1 (0.4446), integration-notes#chunk-2 (0.4236), card-retry-policy (0.3847)
- **vector_0.40:** integration-notes#chunk-0 (0.5913), integration-contract#chunk-0 (0.4942), integration-notes#chunk-1 (0.4446), integration-notes#chunk-2 (0.4236)
- **fts:** no results
- **hybrid_0.25:** integration-notes#chunk-0 (0.0164), integration-contract#chunk-0 (0.0161), integration-notes#chunk-1 (0.0159), integration-notes#chunk-2 (0.0156), card-retry-policy (0.0154)
- **hybrid_0.30:** integration-notes#chunk-0 (0.0164), integration-contract#chunk-0 (0.0161), integration-notes#chunk-1 (0.0159), integration-notes#chunk-2 (0.0156), card-retry-policy (0.0154)
- **hybrid_0.35:** integration-notes#chunk-0 (0.0164), integration-contract#chunk-0 (0.0161), integration-notes#chunk-1 (0.0159), integration-notes#chunk-2 (0.0156), card-retry-policy (0.0154)
- **hybrid_0.40:** integration-notes#chunk-0 (0.0164), integration-contract#chunk-0 (0.0161), integration-notes#chunk-1 (0.0159), integration-notes#chunk-2 (0.0156)
- **production_hybrid:** integration-notes#chunk-0 (0.0325), integration-notes#chunk-1 (0.0323), integration-contract#chunk-0 (0.0161), integration-notes#chunk-2 (0.0156), card-retry-policy (0.0154)

### R-019: What state is a provisioning request in after the directory times out?

- **vector_no_floor:** integration-notes#chunk-1 (0.6614), card-retry-policy (0.5492), integration-notes#chunk-2 (0.4781), card-provisioning-audit (0.4526), planning-brief#chunk-3 (0.4422)
- **vector_0.25:** integration-notes#chunk-1 (0.6614), card-retry-policy (0.5492), integration-notes#chunk-2 (0.4781), card-provisioning-audit (0.4526), planning-brief#chunk-3 (0.4422)
- **vector_0.30:** integration-notes#chunk-1 (0.6614), card-retry-policy (0.5492), integration-notes#chunk-2 (0.4781), card-provisioning-audit (0.4526), planning-brief#chunk-3 (0.4422)
- **vector_0.35:** integration-notes#chunk-1 (0.6614), card-retry-policy (0.5492), integration-notes#chunk-2 (0.4781), card-provisioning-audit (0.4526), planning-brief#chunk-3 (0.4422)
- **vector_0.40:** integration-notes#chunk-1 (0.6614), card-retry-policy (0.5492), integration-notes#chunk-2 (0.4781), card-provisioning-audit (0.4526), planning-brief#chunk-3 (0.4422)
- **fts:** no results
- **hybrid_0.25:** integration-notes#chunk-1 (0.0164), card-retry-policy (0.0161), integration-notes#chunk-2 (0.0159), card-provisioning-audit (0.0156), planning-brief#chunk-3 (0.0154)
- **hybrid_0.30:** integration-notes#chunk-1 (0.0164), card-retry-policy (0.0161), integration-notes#chunk-2 (0.0159), card-provisioning-audit (0.0156), planning-brief#chunk-3 (0.0154)
- **hybrid_0.35:** integration-notes#chunk-1 (0.0164), card-retry-policy (0.0161), integration-notes#chunk-2 (0.0159), card-provisioning-audit (0.0156), planning-brief#chunk-3 (0.0154)
- **hybrid_0.40:** integration-notes#chunk-1 (0.0164), card-retry-policy (0.0161), integration-notes#chunk-2 (0.0159), card-provisioning-audit (0.0156), planning-brief#chunk-3 (0.0154)
- **production_hybrid:** integration-notes#chunk-1 (0.0328), card-retry-policy (0.0323), integration-notes#chunk-2 (0.0310), access-requirements#chunk-0 (0.0310), planning-brief#chunk-3 (0.0310)

### R-020: What is the approved project budget?

- **vector_no_floor:** governance-notes#chunk-0 (0.4109), kickoff-notes#chunk-0 (0.2945), card-governance (0.2940), conflicting-vendor-note#chunk-0 (0.2932), untrusted-evidence#chunk-0 (0.2913)
- **vector_0.25:** governance-notes#chunk-0 (0.4109), kickoff-notes#chunk-0 (0.2945), card-governance (0.2940), conflicting-vendor-note#chunk-0 (0.2932), untrusted-evidence#chunk-0 (0.2913)
- **vector_0.30:** governance-notes#chunk-0 (0.4109)
- **vector_0.35:** governance-notes#chunk-0 (0.4109)
- **vector_0.40:** governance-notes#chunk-0 (0.4109)
- **fts:** no results
- **hybrid_0.25:** governance-notes#chunk-0 (0.0164), kickoff-notes#chunk-0 (0.0161), card-governance (0.0159), conflicting-vendor-note#chunk-0 (0.0156), untrusted-evidence#chunk-0 (0.0154)
- **hybrid_0.30:** governance-notes#chunk-0 (0.0164)
- **hybrid_0.35:** governance-notes#chunk-0 (0.0164)
- **hybrid_0.40:** governance-notes#chunk-0 (0.0164)
- **production_hybrid:** governance-notes#chunk-0 (0.0323), conflicting-vendor-note#chunk-0 (0.0164), untrusted-evidence#chunk-0 (0.0161)

### R-021: Who is the executive sponsor?

- **vector_no_floor:** card-governance (0.4430), governance-notes#chunk-0 (0.4006), kickoff-notes#chunk-0 (0.3218), planning-brief#chunk-2 (0.2404), integration-contract#chunk-0 (0.2286)
- **vector_0.25:** card-governance (0.4430), governance-notes#chunk-0 (0.4006), kickoff-notes#chunk-0 (0.3218)
- **vector_0.30:** card-governance (0.4430), governance-notes#chunk-0 (0.4006), kickoff-notes#chunk-0 (0.3218)
- **vector_0.35:** card-governance (0.4430), governance-notes#chunk-0 (0.4006)
- **vector_0.40:** card-governance (0.4430), governance-notes#chunk-0 (0.4006)
- **fts:** no results
- **hybrid_0.25:** card-governance (0.0164), governance-notes#chunk-0 (0.0161), kickoff-notes#chunk-0 (0.0159)
- **hybrid_0.30:** card-governance (0.0164), governance-notes#chunk-0 (0.0161), kickoff-notes#chunk-0 (0.0159)
- **hybrid_0.35:** card-governance (0.0164), governance-notes#chunk-0 (0.0161)
- **hybrid_0.40:** card-governance (0.0164), governance-notes#chunk-0 (0.0161)
- **production_hybrid:** card-governance (0.0328), governance-notes#chunk-0 (0.0323)

### R-022: When does the pilot start?

- **vector_no_floor:** governance-notes#chunk-0 (0.3767), card-provisioning-audit (0.2014), kickoff-notes#chunk-0 (0.1939), integration-notes#chunk-2 (0.1905), planning-brief#chunk-3 (0.1749)
- **vector_0.25:** governance-notes#chunk-0 (0.3767)
- **vector_0.30:** governance-notes#chunk-0 (0.3767)
- **vector_0.35:** governance-notes#chunk-0 (0.3767)
- **vector_0.40:** no results
- **fts:** no results
- **hybrid_0.25:** governance-notes#chunk-0 (0.0164)
- **hybrid_0.30:** governance-notes#chunk-0 (0.0164)
- **hybrid_0.35:** governance-notes#chunk-0 (0.0164)
- **hybrid_0.40:** no results
- **production_hybrid:** governance-notes#chunk-0 (0.0164)

### R-023: Is the budget final?

- **vector_no_floor:** governance-notes#chunk-0 (0.3306), card-audit-retention (0.2226), security-requirements#chunk-0 (0.1972), card-scope-v1 (0.1927), requirements-meeting#chunk-0 (0.1924)
- **vector_0.25:** governance-notes#chunk-0 (0.3306)
- **vector_0.30:** governance-notes#chunk-0 (0.3306)
- **vector_0.35:** no results
- **vector_0.40:** no results
- **fts:** governance-notes#chunk-0 (0.5241)
- **hybrid_0.25:** governance-notes#chunk-0 (0.0328)
- **hybrid_0.30:** governance-notes#chunk-0 (0.0328)
- **hybrid_0.35:** governance-notes#chunk-0 (0.0164)
- **hybrid_0.40:** governance-notes#chunk-0 (0.0164)
- **production_hybrid:** governance-notes#chunk-0 (0.0164)

### R-024: Explain SEC-AUTH-017.

- **vector_no_floor:** card-privileged-security (0.6308), security-requirements#chunk-0 (0.5895), access-requirements#chunk-0 (0.3203), approval-matrix#chunk-0 (0.2940), conflicting-vendor-note#chunk-0 (0.2784)
- **vector_0.25:** card-privileged-security (0.6308), security-requirements#chunk-0 (0.5895), access-requirements#chunk-0 (0.3203), approval-matrix#chunk-0 (0.2940), conflicting-vendor-note#chunk-0 (0.2784)
- **vector_0.30:** card-privileged-security (0.6308), security-requirements#chunk-0 (0.5895), access-requirements#chunk-0 (0.3203)
- **vector_0.35:** card-privileged-security (0.6308), security-requirements#chunk-0 (0.5895)
- **vector_0.40:** card-privileged-security (0.6308), security-requirements#chunk-0 (0.5895)
- **fts:** no results
- **hybrid_0.25:** card-privileged-security (0.0164), security-requirements#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), approval-matrix#chunk-0 (0.0156), conflicting-vendor-note#chunk-0 (0.0154)
- **hybrid_0.30:** card-privileged-security (0.0164), security-requirements#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159)
- **hybrid_0.35:** card-privileged-security (0.0164), security-requirements#chunk-0 (0.0161)
- **hybrid_0.40:** card-privileged-security (0.0164), security-requirements#chunk-0 (0.0161)
- **production_hybrid:** card-privileged-security (0.0549), security-requirements#chunk-0 (0.0540)

### R-025: How quickly does an inactive admin session expire?

- **vector_no_floor:** security-requirements#chunk-0 (0.4803), card-privileged-security (0.4286), approval-matrix#chunk-0 (0.3293), integration-notes#chunk-1 (0.3179), card-audit-retention (0.3043)
- **vector_0.25:** security-requirements#chunk-0 (0.4803), card-privileged-security (0.4286), approval-matrix#chunk-0 (0.3293), integration-notes#chunk-1 (0.3179), card-audit-retention (0.3043)
- **vector_0.30:** security-requirements#chunk-0 (0.4803), card-privileged-security (0.4286), approval-matrix#chunk-0 (0.3293), integration-notes#chunk-1 (0.3179), card-audit-retention (0.3043)
- **vector_0.35:** security-requirements#chunk-0 (0.4803), card-privileged-security (0.4286)
- **vector_0.40:** security-requirements#chunk-0 (0.4803), card-privileged-security (0.4286)
- **fts:** no results
- **hybrid_0.25:** security-requirements#chunk-0 (0.0164), card-privileged-security (0.0161), approval-matrix#chunk-0 (0.0159), integration-notes#chunk-1 (0.0156), card-audit-retention (0.0154)
- **hybrid_0.30:** security-requirements#chunk-0 (0.0164), card-privileged-security (0.0161), approval-matrix#chunk-0 (0.0159), integration-notes#chunk-1 (0.0156), card-audit-retention (0.0154)
- **hybrid_0.35:** security-requirements#chunk-0 (0.0164), card-privileged-security (0.0161)
- **hybrid_0.40:** security-requirements#chunk-0 (0.0164), card-privileged-security (0.0161)
- **production_hybrid:** security-requirements#chunk-0 (0.0164), card-privileged-security (0.0161)

### R-026: Can support staff see payroll information?

- **vector_no_floor:** kickoff-notes#chunk-0 (0.4919), requirements-meeting#chunk-0 (0.4405), planning-brief#chunk-2 (0.3749), security-requirements#chunk-0 (0.3725), card-worker-source (0.3512)
- **vector_0.25:** kickoff-notes#chunk-0 (0.4919), requirements-meeting#chunk-0 (0.4405), planning-brief#chunk-2 (0.3749), security-requirements#chunk-0 (0.3725), card-worker-source (0.3512)
- **vector_0.30:** kickoff-notes#chunk-0 (0.4919), requirements-meeting#chunk-0 (0.4405), planning-brief#chunk-2 (0.3749), security-requirements#chunk-0 (0.3725), card-worker-source (0.3512)
- **vector_0.35:** kickoff-notes#chunk-0 (0.4919), requirements-meeting#chunk-0 (0.4405), planning-brief#chunk-2 (0.3749), security-requirements#chunk-0 (0.3725), card-worker-source (0.3512)
- **vector_0.40:** kickoff-notes#chunk-0 (0.4919), requirements-meeting#chunk-0 (0.4405)
- **fts:** no results
- **hybrid_0.25:** kickoff-notes#chunk-0 (0.0164), requirements-meeting#chunk-0 (0.0161), planning-brief#chunk-2 (0.0159), security-requirements#chunk-0 (0.0156), card-worker-source (0.0154)
- **hybrid_0.30:** kickoff-notes#chunk-0 (0.0164), requirements-meeting#chunk-0 (0.0161), planning-brief#chunk-2 (0.0159), security-requirements#chunk-0 (0.0156), card-worker-source (0.0154)
- **hybrid_0.35:** kickoff-notes#chunk-0 (0.0164), requirements-meeting#chunk-0 (0.0161), planning-brief#chunk-2 (0.0159), security-requirements#chunk-0 (0.0156), card-worker-source (0.0154)
- **hybrid_0.40:** kickoff-notes#chunk-0 (0.0164), requirements-meeting#chunk-0 (0.0161)
- **production_hybrid:** kickoff-notes#chunk-0 (0.0328), security-requirements#chunk-0 (0.0318), requirements-meeting#chunk-0 (0.0161), planning-brief#chunk-2 (0.0159), card-worker-source (0.0154)

### R-027: How long do we retain audit records?

- **vector_no_floor:** card-audit-retention (0.6940), security-requirements#chunk-0 (0.5330), integration-notes#chunk-2 (0.3574), access-requirements#chunk-0 (0.2996), card-privileged-security (0.2701)
- **vector_0.25:** card-audit-retention (0.6940), security-requirements#chunk-0 (0.5330), integration-notes#chunk-2 (0.3574), access-requirements#chunk-0 (0.2996), card-privileged-security (0.2701)
- **vector_0.30:** card-audit-retention (0.6940), security-requirements#chunk-0 (0.5330), integration-notes#chunk-2 (0.3574)
- **vector_0.35:** card-audit-retention (0.6940), security-requirements#chunk-0 (0.5330), integration-notes#chunk-2 (0.3574)
- **vector_0.40:** card-audit-retention (0.6940), security-requirements#chunk-0 (0.5330)
- **fts:** no results
- **hybrid_0.25:** card-audit-retention (0.0164), security-requirements#chunk-0 (0.0161), integration-notes#chunk-2 (0.0159), access-requirements#chunk-0 (0.0156), card-privileged-security (0.0154)
- **hybrid_0.30:** card-audit-retention (0.0164), security-requirements#chunk-0 (0.0161), integration-notes#chunk-2 (0.0159)
- **hybrid_0.35:** card-audit-retention (0.0164), security-requirements#chunk-0 (0.0161), integration-notes#chunk-2 (0.0159)
- **hybrid_0.40:** card-audit-retention (0.0164), security-requirements#chunk-0 (0.0161)
- **production_hybrid:** card-audit-retention (0.0328), security-requirements#chunk-0 (0.0323), integration-notes#chunk-2 (0.0317)

### R-028: What format is used for audit exports?

- **vector_no_floor:** card-audit-retention (0.6207), security-requirements#chunk-0 (0.4426), integration-notes#chunk-2 (0.3247), integration-contract#chunk-0 (0.2493), access-requirements#chunk-0 (0.2281)
- **vector_0.25:** card-audit-retention (0.6207), security-requirements#chunk-0 (0.4426), integration-notes#chunk-2 (0.3247)
- **vector_0.30:** card-audit-retention (0.6207), security-requirements#chunk-0 (0.4426), integration-notes#chunk-2 (0.3247)
- **vector_0.35:** card-audit-retention (0.6207), security-requirements#chunk-0 (0.4426)
- **vector_0.40:** card-audit-retention (0.6207), security-requirements#chunk-0 (0.4426)
- **fts:** no results
- **hybrid_0.25:** card-audit-retention (0.0164), security-requirements#chunk-0 (0.0161), integration-notes#chunk-2 (0.0159)
- **hybrid_0.30:** card-audit-retention (0.0164), security-requirements#chunk-0 (0.0161), integration-notes#chunk-2 (0.0159)
- **hybrid_0.35:** card-audit-retention (0.0164), security-requirements#chunk-0 (0.0161)
- **hybrid_0.40:** card-audit-retention (0.0164), security-requirements#chunk-0 (0.0161)
- **production_hybrid:** security-requirements#chunk-0 (0.0325), card-audit-retention (0.0164)

### R-029: What is INT-DIR-204?

- **vector_no_floor:** card-directory-contract (0.5216), integration-contract#chunk-0 (0.5118), integration-notes#chunk-0 (0.2823), integration-notes#chunk-1 (0.2792), access-requirements#chunk-0 (0.2443)
- **vector_0.25:** card-directory-contract (0.5216), integration-contract#chunk-0 (0.5118), integration-notes#chunk-0 (0.2823), integration-notes#chunk-1 (0.2792)
- **vector_0.30:** card-directory-contract (0.5216), integration-contract#chunk-0 (0.5118)
- **vector_0.35:** card-directory-contract (0.5216), integration-contract#chunk-0 (0.5118)
- **vector_0.40:** card-directory-contract (0.5216), integration-contract#chunk-0 (0.5118)
- **fts:** no results
- **hybrid_0.25:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161), integration-notes#chunk-0 (0.0159), integration-notes#chunk-1 (0.0156)
- **hybrid_0.30:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161)
- **hybrid_0.35:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161)
- **hybrid_0.40:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161)
- **production_hybrid:** card-directory-contract (0.0549), integration-contract#chunk-0 (0.0540)

### R-030: Which payload fields go to the directory?

- **vector_no_floor:** integration-contract#chunk-0 (0.4894), integration-notes#chunk-0 (0.4588), integration-notes#chunk-2 (0.3629), access-requirements#chunk-0 (0.3351), integration-notes#chunk-1 (0.3148)
- **vector_0.25:** integration-contract#chunk-0 (0.4894), integration-notes#chunk-0 (0.4588), integration-notes#chunk-2 (0.3629), access-requirements#chunk-0 (0.3351), integration-notes#chunk-1 (0.3148)
- **vector_0.30:** integration-contract#chunk-0 (0.4894), integration-notes#chunk-0 (0.4588), integration-notes#chunk-2 (0.3629), access-requirements#chunk-0 (0.3351), integration-notes#chunk-1 (0.3148)
- **vector_0.35:** integration-contract#chunk-0 (0.4894), integration-notes#chunk-0 (0.4588), integration-notes#chunk-2 (0.3629)
- **vector_0.40:** integration-contract#chunk-0 (0.4894), integration-notes#chunk-0 (0.4588)
- **fts:** no results
- **hybrid_0.25:** integration-contract#chunk-0 (0.0164), integration-notes#chunk-0 (0.0161), integration-notes#chunk-2 (0.0159), access-requirements#chunk-0 (0.0156), integration-notes#chunk-1 (0.0154)
- **hybrid_0.30:** integration-contract#chunk-0 (0.0164), integration-notes#chunk-0 (0.0161), integration-notes#chunk-2 (0.0159), access-requirements#chunk-0 (0.0156), integration-notes#chunk-1 (0.0154)
- **hybrid_0.35:** integration-contract#chunk-0 (0.0164), integration-notes#chunk-0 (0.0161), integration-notes#chunk-2 (0.0159)
- **hybrid_0.40:** integration-contract#chunk-0 (0.0164), integration-notes#chunk-0 (0.0161)
- **production_hybrid:** integration-notes#chunk-0 (0.0323), integration-contract#chunk-0 (0.0164), integration-notes#chunk-1 (0.0164), integration-notes#chunk-2 (0.0159)

### R-031: Which header prevents duplicate writes?

- **vector_no_floor:** card-directory-contract (0.3809), integration-contract#chunk-0 (0.3206), access-requirements#chunk-0 (0.2790), integration-notes#chunk-1 (0.2688), conflicting-vendor-note#chunk-0 (0.2426)
- **vector_0.25:** card-directory-contract (0.3809), integration-contract#chunk-0 (0.3206), access-requirements#chunk-0 (0.2790), integration-notes#chunk-1 (0.2688)
- **vector_0.30:** card-directory-contract (0.3809), integration-contract#chunk-0 (0.3206)
- **vector_0.35:** card-directory-contract (0.3809)
- **vector_0.40:** no results
- **fts:** no results
- **hybrid_0.25:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159), integration-notes#chunk-1 (0.0156)
- **hybrid_0.30:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161)
- **hybrid_0.35:** card-directory-contract (0.0164)
- **hybrid_0.40:** no results
- **production_hybrid:** card-directory-contract (0.0164)

### R-032: What happens for HTTP 429?

- **vector_no_floor:** card-directory-contract (0.4769), integration-contract#chunk-0 (0.3719), integration-notes#chunk-1 (0.2753), card-retry-policy (0.2501), planning-brief#chunk-3 (0.2290)
- **vector_0.25:** card-directory-contract (0.4769), integration-contract#chunk-0 (0.3719), integration-notes#chunk-1 (0.2753), card-retry-policy (0.2501)
- **vector_0.30:** card-directory-contract (0.4769), integration-contract#chunk-0 (0.3719)
- **vector_0.35:** card-directory-contract (0.4769), integration-contract#chunk-0 (0.3719)
- **vector_0.40:** card-directory-contract (0.4769)
- **fts:** no results
- **hybrid_0.25:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161), integration-notes#chunk-1 (0.0159), card-retry-policy (0.0156)
- **hybrid_0.30:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161)
- **hybrid_0.35:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161)
- **hybrid_0.40:** card-directory-contract (0.0164)
- **production_hybrid:** card-directory-contract (0.0549), integration-contract#chunk-0 (0.0540)

### R-033: Do we retry HTTP 400 responses?

- **vector_no_floor:** card-directory-contract (0.5449), integration-contract#chunk-0 (0.3901), card-retry-policy (0.3545), integration-notes#chunk-1 (0.2761), planning-brief#chunk-3 (0.2432)
- **vector_0.25:** card-directory-contract (0.5449), integration-contract#chunk-0 (0.3901), card-retry-policy (0.3545), integration-notes#chunk-1 (0.2761)
- **vector_0.30:** card-directory-contract (0.5449), integration-contract#chunk-0 (0.3901), card-retry-policy (0.3545)
- **vector_0.35:** card-directory-contract (0.5449), integration-contract#chunk-0 (0.3901), card-retry-policy (0.3545)
- **vector_0.40:** card-directory-contract (0.5449)
- **fts:** no results
- **hybrid_0.25:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161), card-retry-policy (0.0159), integration-notes#chunk-1 (0.0156)
- **hybrid_0.30:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161), card-retry-policy (0.0159)
- **hybrid_0.35:** card-directory-contract (0.0164), integration-contract#chunk-0 (0.0161), card-retry-policy (0.0159)
- **hybrid_0.40:** card-directory-contract (0.0164)
- **production_hybrid:** card-directory-contract (0.0547), integration-contract#chunk-0 (0.0543), card-retry-policy (0.0159)

### R-034: What is the production directory URL?

- **vector_no_floor:** integration-contract#chunk-0 (0.4060), integration-notes#chunk-2 (0.3119), card-retry-policy (0.3075), integration-notes#chunk-1 (0.2898), access-requirements#chunk-0 (0.2832)
- **vector_0.25:** integration-contract#chunk-0 (0.4060), integration-notes#chunk-2 (0.3119), card-retry-policy (0.3075), integration-notes#chunk-1 (0.2898), access-requirements#chunk-0 (0.2832)
- **vector_0.30:** integration-contract#chunk-0 (0.4060), integration-notes#chunk-2 (0.3119), card-retry-policy (0.3075)
- **vector_0.35:** integration-contract#chunk-0 (0.4060)
- **vector_0.40:** integration-contract#chunk-0 (0.4060)
- **fts:** no results
- **hybrid_0.25:** integration-contract#chunk-0 (0.0164), integration-notes#chunk-2 (0.0161), card-retry-policy (0.0159), integration-notes#chunk-1 (0.0156), access-requirements#chunk-0 (0.0154)
- **hybrid_0.30:** integration-contract#chunk-0 (0.0164), integration-notes#chunk-2 (0.0161), card-retry-policy (0.0159)
- **hybrid_0.35:** integration-contract#chunk-0 (0.0164)
- **hybrid_0.40:** integration-contract#chunk-0 (0.0164)
- **production_hybrid:** integration-contract#chunk-0 (0.0544), integration-notes#chunk-1 (0.0164), integration-notes#chunk-0 (0.0161)

### R-035: What does the evidence instruct the assistant to ignore?

- **vector_no_floor:** untrusted-evidence#chunk-0 (0.4338), conflicting-vendor-note#chunk-0 (0.3549), access-requirements#chunk-0 (0.2517), requirements-meeting#chunk-0 (0.2412), security-requirements#chunk-0 (0.2355)
- **vector_0.25:** untrusted-evidence#chunk-0 (0.4338), conflicting-vendor-note#chunk-0 (0.3549), access-requirements#chunk-0 (0.2517)
- **vector_0.30:** untrusted-evidence#chunk-0 (0.4338), conflicting-vendor-note#chunk-0 (0.3549)
- **vector_0.35:** untrusted-evidence#chunk-0 (0.4338), conflicting-vendor-note#chunk-0 (0.3549)
- **vector_0.40:** untrusted-evidence#chunk-0 (0.4338)
- **fts:** no results
- **hybrid_0.25:** untrusted-evidence#chunk-0 (0.0164), conflicting-vendor-note#chunk-0 (0.0161), access-requirements#chunk-0 (0.0159)
- **hybrid_0.30:** untrusted-evidence#chunk-0 (0.0164), conflicting-vendor-note#chunk-0 (0.0161)
- **hybrid_0.35:** untrusted-evidence#chunk-0 (0.0164), conflicting-vendor-note#chunk-0 (0.0161)
- **hybrid_0.40:** untrusted-evidence#chunk-0 (0.0164)
- **production_hybrid:** untrusted-evidence#chunk-0 (0.0328), conflicting-vendor-note#chunk-0 (0.0323)

### R-036: Who does the vendor claim approves ordinary access?

- **vector_no_floor:** conflicting-vendor-note#chunk-0 (0.5655), approval-matrix#chunk-0 (0.4841), card-privileged-approval (0.4442), planning-brief#chunk-2 (0.4247), access-requirements#chunk-0 (0.4202)
- **vector_0.25:** conflicting-vendor-note#chunk-0 (0.5655), approval-matrix#chunk-0 (0.4841), card-privileged-approval (0.4442), planning-brief#chunk-2 (0.4247), access-requirements#chunk-0 (0.4202)
- **vector_0.30:** conflicting-vendor-note#chunk-0 (0.5655), approval-matrix#chunk-0 (0.4841), card-privileged-approval (0.4442), planning-brief#chunk-2 (0.4247), access-requirements#chunk-0 (0.4202)
- **vector_0.35:** conflicting-vendor-note#chunk-0 (0.5655), approval-matrix#chunk-0 (0.4841), card-privileged-approval (0.4442), planning-brief#chunk-2 (0.4247), access-requirements#chunk-0 (0.4202)
- **vector_0.40:** conflicting-vendor-note#chunk-0 (0.5655), approval-matrix#chunk-0 (0.4841), card-privileged-approval (0.4442), planning-brief#chunk-2 (0.4247), access-requirements#chunk-0 (0.4202)
- **fts:** no results
- **hybrid_0.25:** conflicting-vendor-note#chunk-0 (0.0164), approval-matrix#chunk-0 (0.0161), card-privileged-approval (0.0159), planning-brief#chunk-2 (0.0156), access-requirements#chunk-0 (0.0154)
- **hybrid_0.30:** conflicting-vendor-note#chunk-0 (0.0164), approval-matrix#chunk-0 (0.0161), card-privileged-approval (0.0159), planning-brief#chunk-2 (0.0156), access-requirements#chunk-0 (0.0154)
- **hybrid_0.35:** conflicting-vendor-note#chunk-0 (0.0164), approval-matrix#chunk-0 (0.0161), card-privileged-approval (0.0159), planning-brief#chunk-2 (0.0156), access-requirements#chunk-0 (0.0154)
- **hybrid_0.40:** conflicting-vendor-note#chunk-0 (0.0164), approval-matrix#chunk-0 (0.0161), card-privileged-approval (0.0159), planning-brief#chunk-2 (0.0156), access-requirements#chunk-0 (0.0154)
- **production_hybrid:** conflicting-vendor-note#chunk-0 (0.0325), approval-matrix#chunk-0 (0.0325), planning-brief#chunk-2 (0.0312), requirements-meeting#chunk-0 (0.0310), access-requirements#chunk-0 (0.0305)

### R-037: Which source is authoritative for ordinary access approval?

- **vector_no_floor:** approval-matrix#chunk-0 (0.4723), card-privileged-approval (0.4685), access-requirements#chunk-0 (0.4220), conflicting-vendor-note#chunk-0 (0.4023), planning-brief#chunk-2 (0.3811)
- **vector_0.25:** approval-matrix#chunk-0 (0.4723), card-privileged-approval (0.4685), access-requirements#chunk-0 (0.4220), conflicting-vendor-note#chunk-0 (0.4023), planning-brief#chunk-2 (0.3811)
- **vector_0.30:** approval-matrix#chunk-0 (0.4723), card-privileged-approval (0.4685), access-requirements#chunk-0 (0.4220), conflicting-vendor-note#chunk-0 (0.4023), planning-brief#chunk-2 (0.3811)
- **vector_0.35:** approval-matrix#chunk-0 (0.4723), card-privileged-approval (0.4685), access-requirements#chunk-0 (0.4220), conflicting-vendor-note#chunk-0 (0.4023), planning-brief#chunk-2 (0.3811)
- **vector_0.40:** approval-matrix#chunk-0 (0.4723), card-privileged-approval (0.4685), access-requirements#chunk-0 (0.4220), conflicting-vendor-note#chunk-0 (0.4023)
- **fts:** no results
- **hybrid_0.25:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), access-requirements#chunk-0 (0.0159), conflicting-vendor-note#chunk-0 (0.0156), planning-brief#chunk-2 (0.0154)
- **hybrid_0.30:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), access-requirements#chunk-0 (0.0159), conflicting-vendor-note#chunk-0 (0.0156), planning-brief#chunk-2 (0.0154)
- **hybrid_0.35:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), access-requirements#chunk-0 (0.0159), conflicting-vendor-note#chunk-0 (0.0156), planning-brief#chunk-2 (0.0154)
- **hybrid_0.40:** approval-matrix#chunk-0 (0.0164), card-privileged-approval (0.0161), access-requirements#chunk-0 (0.0159), conflicting-vendor-note#chunk-0 (0.0156)
- **production_hybrid:** approval-matrix#chunk-0 (0.0328), conflicting-vendor-note#chunk-0 (0.0318), access-requirements#chunk-0 (0.0317), card-privileged-approval (0.0306), planning-brief#chunk-2 (0.0305)

### R-038: What is the disaster recovery RPO?

- **vector_no_floor:** access-requirements#chunk-0 (0.2422), card-retry-policy (0.2312), integration-contract#chunk-0 (0.2288), card-provisioning-audit (0.2279), integration-notes#chunk-2 (0.2240)
- **vector_0.25:** no results
- **vector_0.30:** no results
- **vector_0.35:** no results
- **vector_0.40:** no results
- **fts:** no results
- **hybrid_0.25:** no results
- **hybrid_0.30:** no results
- **hybrid_0.35:** no results
- **hybrid_0.40:** no results
- **production_hybrid:** no results

### R-039: Does the system support biometric login for customers?

- **vector_no_floor:** planning-brief#chunk-0 (0.3415), security-requirements#chunk-0 (0.3329), integration-notes#chunk-0 (0.3089), requirements-meeting#chunk-0 (0.2930), kickoff-notes#chunk-0 (0.2851)
- **vector_0.25:** planning-brief#chunk-0 (0.3415), security-requirements#chunk-0 (0.3329), integration-notes#chunk-0 (0.3089), requirements-meeting#chunk-0 (0.2930), kickoff-notes#chunk-0 (0.2851)
- **vector_0.30:** planning-brief#chunk-0 (0.3415), security-requirements#chunk-0 (0.3329), integration-notes#chunk-0 (0.3089)
- **vector_0.35:** no results
- **vector_0.40:** no results
- **fts:** no results
- **hybrid_0.25:** planning-brief#chunk-0 (0.0164), security-requirements#chunk-0 (0.0161), integration-notes#chunk-0 (0.0159), requirements-meeting#chunk-0 (0.0156), kickoff-notes#chunk-0 (0.0154)
- **hybrid_0.30:** planning-brief#chunk-0 (0.0164), security-requirements#chunk-0 (0.0161), integration-notes#chunk-0 (0.0159)
- **hybrid_0.35:** no results
- **hybrid_0.40:** no results
- **production_hybrid:** no results

### R-040: What did we decide about that?

- **vector_no_floor:** untrusted-evidence#chunk-0 (0.2694), requirements-meeting#chunk-0 (0.2130), conflicting-vendor-note#chunk-0 (0.1900), card-governance (0.1739), access-requirements#chunk-0 (0.1698)
- **vector_0.25:** untrusted-evidence#chunk-0 (0.2694)
- **vector_0.30:** no results
- **vector_0.35:** no results
- **vector_0.40:** no results
- **fts:** no results
- **hybrid_0.25:** untrusted-evidence#chunk-0 (0.0164)
- **hybrid_0.30:** no results
- **hybrid_0.35:** no results
- **hybrid_0.40:** no results
- **production_hybrid:** no results
