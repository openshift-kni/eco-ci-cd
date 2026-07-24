# Molecule Test: Spoke Lockdown URI with Digests

## Purpose

This molecule scenario validates the **lockdown digest preservation and validation mode** functionality. It confirms that when operators are loaded from a lockdown URI (with bundle/fbc digests), those digests are preserved throughout the mirroring process, enabling bit-identical operator deployments.

**Related Documentation:**
- `docs/eco-ci-cd/spoke-lockdown-validation-digest-mismatch-analysis.md`
- **Fixed in:** Build #116 (fix for build #115 validation failure)

## Fixed Behavior Being Tested

When operators are extracted from a spoke lockdown URI containing `bundle` and `fbc` digest fields, the system now:
1. **Preserves** bundle/fbc digests (does NOT strip them)
2. **Uses** frozen digests for bit-identical mirroring (not querying production)
3. **Accumulates** metadata from mirrored operators (hooks still fire)
4. **Validates** that generated lockdown matches input lockdown (validation passes)

**Result:** Lockdown mode ensures reproducible, bit-identical operator deployments across ZTP spoke clusters.

## Test Flow

1. **Prepare:** Creates mock lockdown JSON with operators containing bundle/fbc digests
2. **Converge:** 
   - Parses lockdown using `lockdowns` role
   - Verifies digests are PRESERVED (not stripped) → **PASSES**
   - Mocks ocp_operator_mirror using lockdown digests
   - Mocks metadata accumulation (frozen digests)
   - Generates lockdown from accumulated metadata
   - Compares input vs generated lockdown → **MATCH** (validation passes)
3. **Verify:**
   - Confirms operators preserve bundle/fbc digests (fixed behavior)
   - Asserts lockdown generation succeeded with metadata
   - Asserts input and generated lockdowns have identical digests
   - Confirms validation mode would PASS

## Running the Test

```bash
cd playbooks/telco-kpis/roles/lockdowns
molecule test -s spoke-lockdown-uri-with-digests
```

## What This Tests

✓ **Digest preservation:** Operators from lockdown URI keep bundle/fbc fields  
✓ **Lockdown generation:** Successfully creates lockdown with accumulated metadata  
✓ **Validation mode:** Input and generated lockdowns match (bit-identical)  
✓ **Fix confirmation:** Validation PASSES (not FAILS like in build #115)  

## What This Doesn't Test

✗ Actual operator mirroring via `ocp_operator_mirror` role (metadata accumulation is mocked)  
✗ Real accumulate hooks firing (simulated with set_fact)  
✗ End-to-end integration with Jenkins job (isolated unit test)  
✗ Production catalog digest usage in oc-mirror (requires full integration test)

## Implementation Details

The fix involved two changes:

1. **mirror-spoke-operators.yml:** Removed bundle/fbc stripping, preserves digests
2. **ocp_operator_mirror role:**
   - `mirror_operators_prod.yaml`: Extracts lockdown FBC digest, uses in catalog_index_map
   - `mirror_from_fbc.yaml`: Detects lockdown bundle/fbc, skips catalog parsing when present

## Related Files

- `playbooks/telco-kpis/mirror-spoke-operators.yml` - Preserves digests (removed stripping)
- `playbooks/roles/ocp_operator_mirror/tasks/mirror_operators_prod.yaml` - Uses lockdown FBC digest
- `playbooks/roles/ocp_operator_mirror/tasks/mirror_from_fbc.yaml` - Uses lockdown bundle digest
- `docs/eco-ci-cd/spoke-lockdown-validation-digest-mismatch-analysis.md` - Root cause analysis
