# LCAI-0012E PRIMARY DRAFT IMPORT

Authoritative source:
{'commit': '7e4f649', 'isolated_database': 'data\\learning_coach_v2_0012e_full_test.duckdb', 'quality_results_path': 'resources\\content\\quality\\lcai_0012e_quality_results.json'}

Import campaign:
LCAI-0012E-PRIMARY-IMPORT-V1

Drafts expected:
1293

New Drafts imported:
1293

Already present identical:
1293

Already present different:
0

Excluded unresolved curriculum:
18

Invalid references:
0

Failed imports:
0

Isolated-to-production ID mappings:
1293

AI_HIGH total:
271

AI_HIGH resolved to production Draft:
271

AI_HIGH unresolved:
0

Review-count reconciliation:
PASS

Lifecycle Draft only:
PASS

Production gates created:
0

Approved versions created:
0

Tier coverage before:
CM1: {'tier1': 0, 'tier2': 0, 'tier3': 118, 'total_active_skills': 118}
CM2: {'tier1': 0, 'tier2': 0, 'tier3': 125, 'total_active_skills': 125}
6e: {'tier1': 0, 'tier2': 0, 'tier3': 143, 'total_active_skills': 143}
5e: {'tier1': 0, 'tier2': 0, 'tier3': 161, 'total_active_skills': 161}

Tier coverage after:
CM1: {'tier1': 0, 'tier2': 0, 'tier3': 118, 'total_active_skills': 118}
CM2: {'tier1': 0, 'tier2': 0, 'tier3': 125, 'total_active_skills': 125}
6e: {'tier1': 0, 'tier2': 0, 'tier3': 143, 'total_active_skills': 143}
5e: {'tier1': 0, 'tier2': 0, 'tier3': 161, 'total_active_skills': 161}

Tier coverage unchanged:
PASS

Dry-run:
PASS

Execution:
PASS

Idempotence:
PASS

Rollback:
NOT RUN

Production DB modified:
YES — DRAFT IMPORT ONLY

Backup:
data/learning_coach_v2_backup_20260728T140051Z.duckdb
checksum:
785450af53a5e4d765b32e6bae6d5f2fef8cd7220a19e780e9e9c7e81cc5a485

Import command:
python scripts/run_primary_draft_import_0012e.py --execute --database data/learning_coach_v2.duckdb --campaign LCAI-0012E-PRIMARY-IMPORT-V1 --confirm-primary-draft-import

Rollback command:
python scripts/run_primary_draft_import_0012e.py --rollback --execute --database data/learning_coach_v2.duckdb --campaign LCAI-0012E-PRIMARY-IMPORT-V1 --confirm-primary-draft-import-rollback

Code commit:
NOT COMMITTED

Database commit:
NOT COMMITTED

Push:
NOT PERFORMED

Verdict:
LCAI-0012E PRIMARY DRAFT IMPORT: READY FOR PUBLICATION DRY-RUN
