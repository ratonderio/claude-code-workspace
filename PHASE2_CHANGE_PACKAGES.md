# System 02 Pressure Convey — Phase 2 Change Packages

**Basis:** `PHASE1_AUDIT_FINDINGS.md`, approved priority order. Approved design decisions:

| Question | Decision |
|---|---|
| Q8 — bag count semantics | **Total bags**, including the initial state-1 fill (decrement on initial fill too) |
| Q3 — purge policy | **Purge between hoppers**: bin empty → purge line to completion → then switch |
| Q9 — dual-config hose valves | **State-aware**: one hose path open at a time, keyed to the active convey state |

**Workflow:** Packages are ordered; transcribe and emulator-verify each before starting the next.
Rung text is Logix neutral text. "CURRENT" lines are verbatim from
`Adjuvants_2026_06_10_logic.md` (line refs given). Renumbering notes assume rungs are inserted
where stated. **Do not download any package without emulator verification.**

**Cross-package dependency:** Packages 3, 4, 5 interact (TRANS.4/5 rewrite, Valves rung 2
rewrite, purge handshake). They are written to be transcribed independently in order 3 → 4 → 5,
but full campaign regression should be run after Package 5 is in.

---

## PACKAGE 1 — Blower & convey fan auto start (BUG-02)

**Routines:** `Devices/X01BLP01`, `Devices/X01FAN01` — Status: ready.

### 1.1 X01BLP01 — new HOA.HA rung (insert after rung 2, before the existing rung 3)

```
NEW Rung: [XIC(SPG_BLP_XFR.STATES.3) ,XIC(SPG_BLP_XFR.STATES.4) ,XIC(SPG_BLP_XFR.STATES.5) ,XIC(SPG_BLP_XFR.STATES.6) ]OTE(X01BLP01_M.HOA.HA);
```

Annotations:
- States 3 (Start Blower), 4 (Convey), 5 (Purge) are obvious. **State 6 (Clear High Pressure) is
  included deliberately**: feed is stopped in state 6 (airlock HA rungs exclude it) but air keeps
  pushing the slug. If the customer prefers blower-off on HIHI, delete the STATES.6 branch —
  but then expect oscillation 6→4→6 because pressure clears as soon as air stops.
- OTE (not OTL): HA drops the scan the sequence leaves states 3-6; the motor stops via rung 3.

### 1.2 X01BLP01 rung 3 — remove the SIM-only start branch (current line 848)

```
CURRENT:  XIC(X01BLP01_M.Interlock)[XIC(X01BLP01_M.HOA.HA) OTE(X01BLP01_M.AR) ,XIC(X01BLP01_M.HOA.HH) ,XIC(SIM_ENABLED) [XIC(SPG_BLP_XFR.STATES.3) ,XIC(SPG_BLP_XFR.STATES.4) ,XIC(SPG_BLP_XFR.STATES.5) ] ]OTE(X01BLP01_M.MO);
PROPOSED: XIC(X01BLP01_M.Interlock)[XIC(X01BLP01_M.HOA.HA) OTE(X01BLP01_M.AR) ,XIC(X01BLP01_M.HOA.HH) ]OTE(X01BLP01_M.MO);
```

- Diff: delete branch 3 (`XIC(SIM_ENABLED)[states 3/4/5]`) — now redundant: the new HA rung fires
  in sim too, and the existing SIM feedback rungs (rungs 25/26) still close the loop.
- Deliberately NOT adding `Auto_Mode` contacts (template deviation noted in Phase 1): keeping the
  current behavior that HH works in any mode minimizes the diff. Flag if you want full template
  conformance.
- Interlock chain check: rung 2 (`XIC(X01FAN01_MCY.MI)`) is untouched — blower waits for fan
  proof, which is why 1.3 must be transcribed in the same session.

### 1.3 X01FAN01 — new HOA.HA rung (insert after rung 2) and rung 3 edit (current line 886)

```
NEW Rung: [XIC(SPG_BLP_XFR.STATES.3) ,XIC(SPG_BLP_XFR.STATES.4) ,XIC(SPG_BLP_XFR.STATES.5) ,XIC(SPG_BLP_XFR.STATES.6) ]OTE(X01FAN01_M.HOA.HA);

CURRENT:  XIC(X01FAN01_M.Interlock)[XIC(X01FAN01_M.HOA.HA) OTE(X01FAN01_M.AR) ,XIC(X01FAN01_M.HOA.HH) ,XIC(SIM_ENABLED) [XIC(SPG_BLP_XFR.STATES.3) ,XIC(SPG_BLP_XFR.STATES.4) ,XIC(SPG_BLP_XFR.STATES.5) ] ]OTE(X01FAN01_M.MO);
PROPOSED: XIC(X01FAN01_M.Interlock)[XIC(X01FAN01_M.HOA.HA) OTE(X01FAN01_M.AR) ,XIC(X01FAN01_M.HOA.HH) ]OTE(X01FAN01_M.MO);
```

- Both HA bits assert simultaneously in state 3; the blower's interlock on `X01FAN01_MCY.MI`
  enforces fan-first start order with no extra logic.

### Emulator checks (Package 1)
1. SIM off-line test not possible for motors; in emulator with SIM_ENABLED=1: start a config-1
   transfer, verify SPG reaches state 3 and `X01FAN01_M.MO` then `X01BLP01_M.MO` assert, TIMERS[2]
   times out, sequence reaches state 4.
2. Force `X01FAN01_MCY.SIM.MI` off: blower must never start (interlock).
3. Drive `X01BLP01_PT.SIM.Value` above HIHIALM.SP for TIMERS[4]: state 6 entered, blower stays
   running, airlock HA drops.

---

## PACKAGE 2 — ALK03 VFD speed rung mode inversion (BUG-13)

**Routine:** `Devices/X01ALK03` rung 12 (current line 210) — Status: ready.

```
CURRENT:  XIC(X01ALK03_VFD.CMD_SPD.Interlock)[XIC(X01ALK03.Auto_Mode) XIO(X01ALK03_VFD.CMD_SPD.AR) XIO(X01ALK03_VFD.CMD_SPD.HOA.HH) MOVE(0,X01ALK03_VFD.CMD_SPD.MO) ,XIO(X01ALK03.Auto_Mode) XIC(X01ALK03_VFD.CMD_SPD.HOA.HA) OTE(X01ALK03_VFD.CMD_SPD.AR) MOVE(X01ALK03_VFD.CMD_SPD.HA_SP,X01ALK03_VFD.CMD_SPD.MO) ,XIC(X01ALK03_VFD.CMD_SPD.HOA.HH) MOVE(X01ALK03_VFD.CMD_SPD.HH_SP,X01ALK03_VFD.CMD_SPD.MO) ];

PROPOSED: XIC(X01ALK03_VFD.CMD_SPD.Interlock)[XIO(X01ALK03_VFD.CMD_SPD.AR) XIO(X01ALK03_VFD.CMD_SPD.HOA.HH) MOVE(0,X01ALK03_VFD.CMD_SPD.MO) ,XIC(X01ALK03.Auto_Mode) XIC(X01ALK03_VFD.CMD_SPD.HOA.HA) OTE(X01ALK03_VFD.CMD_SPD.AR) MOVE(X01ALK03_VFD.CMD_SPD.HA_SP,X01ALK03_VFD.CMD_SPD.MO) ,XIO(X01ALK03.Auto_Mode) XIC(X01ALK03_VFD.CMD_SPD.HOA.HH) MOVE(X01ALK03_VFD.CMD_SPD.HH_SP,X01ALK03_VFD.CMD_SPD.MO) ];
```

Instruction-level diff (makes it exactly match the known-good ALK04 rung 12, line 286):
- Branch 1: **delete** `XIC(X01ALK03.Auto_Mode)`.
- Branch 2: **change** `XIO(X01ALK03.Auto_Mode)` → `XIC(X01ALK03.Auto_Mode)`.
- Branch 3: **insert** `XIO(X01ALK03.Auto_Mode)` before `XIC(...HOA.HH)`.

Scan-order note: branches execute in order; on the first Auto scan branch 1 writes 0 (AR still
off), branch 2 then writes HA_SP and sets AR — final MO = HA_SP. Same semantics as ALK04.

### Emulator checks (Package 2)
1. Auto + HA called (BLENDER state 3, SPG state 4): `CMD_SPD.MO` = HA_SP, `X01ALK03_PF525:O.FreqCommand`
   = HA_SP×60.
2. Auto + HA dropped: MO returns to 0.
3. Manual + HH: MO = HH_SP. Manual without HH: 0.

---

## PACKAGE 3 — State-aware valve proof for dual configs (BUG-03, Q9 approved)

**Routine:** `Devices/Valves` rung 2 (current line 72) — Status: ready.

Only the CONFIG-3 and CONFIG-6 branches change; configs 1/2/4/5 are verbatim from current.
Each dual config splits into two branches keyed on the active convey state. Both hose
CONNECTED proofs are required throughout (hoses are physically placed for the whole campaign).

```
PROPOSED (full rung):
[EQ(BLENDER_XFR.CONVEY_CONFIG,1) XIC(X01SCH01_ZSC.MI) XIC(X01SCH05_ZSC.MI) XIO(X01VLV07_FYO.MO) XIO(X01VLV08_FYO.MO) XIC(X01VLV09_FYO.MO) XIO(X01VLV10_FYO.MO) XIC(BLENDER_XFR.SCH01_CONNECTED)
,EQ(BLENDER_XFR.CONVEY_CONFIG,2) XIC(X01SCH01_ZSC.MI) XIC(X01SCH05_ZSC.MI) XIC(X01VLV07_FYO.MO) XIO(X01VLV08_FYO.MO) XIO(X01VLV09_FYO.MO) XIO(X01VLV10_FYO.MO) XIC(BLENDER_XFR.SCH02_CONNECTED)
,EQ(BLENDER_XFR.CONVEY_CONFIG,3) XIC(BLENDER_XFR.STATES.3) XIC(X01SCH01_ZSC.MI) XIC(X01SCH05_ZSC.MI) XIO(X01VLV07_FYO.MO) XIO(X01VLV08_FYO.MO) XIC(X01VLV09_FYO.MO) XIO(X01VLV10_FYO.MO) XIC(BLENDER_XFR.SCH01_CONNECTED) XIC(BLENDER_XFR.SCH02_CONNECTED)
,EQ(BLENDER_XFR.CONVEY_CONFIG,3) XIC(BLENDER_XFR.STATES.4) XIC(X01SCH01_ZSC.MI) XIC(X01SCH05_ZSC.MI) XIC(X01VLV07_FYO.MO) XIO(X01VLV08_FYO.MO) XIO(X01VLV09_FYO.MO) XIO(X01VLV10_FYO.MO) XIC(BLENDER_XFR.SCH01_CONNECTED) XIC(BLENDER_XFR.SCH02_CONNECTED)
,EQ(BLENDER_XFR.CONVEY_CONFIG,4) XIC(X01SCH01_ZSC.MI) XIC(X01SCH05_ZSC.MI) XIO(X01VLV07_FYO.MO) XIC(X01VLV08_FYO.MO) XIO(X01VLV09_FYO.MO) XIO(X01VLV10_FYO.MO) XIC(BLENDER_XFR.SCH01_CONNECTED)
,EQ(BLENDER_XFR.CONVEY_CONFIG,5) XIC(X01SCH01_ZSC.MI) XIC(X01SCH05_ZSC.MI) XIO(X01VLV07_FYO.MO) XIO(X01VLV08_FYO.MO) XIO(X01VLV09_FYO.MO) XIC(X01VLV10_FYO.MO) XIC(BLENDER_XFR.SCH02_CONNECTED)
,EQ(BLENDER_XFR.CONVEY_CONFIG,6) XIC(BLENDER_XFR.STATES.3) XIC(X01SCH01_ZSC.MI) XIC(X01SCH05_ZSC.MI) XIO(X01VLV07_FYO.MO) XIC(X01VLV08_FYO.MO) XIO(X01VLV09_FYO.MO) XIO(X01VLV10_FYO.MO) XIC(BLENDER_XFR.SCH01_CONNECTED) XIC(BLENDER_XFR.SCH02_CONNECTED)
,EQ(BLENDER_XFR.CONVEY_CONFIG,6) XIC(BLENDER_XFR.STATES.4) XIC(X01SCH01_ZSC.MI) XIC(X01SCH05_ZSC.MI) XIO(X01VLV07_FYO.MO) XIO(X01VLV08_FYO.MO) XIO(X01VLV09_FYO.MO) XIC(X01VLV10_FYO.MO) XIC(BLENDER_XFR.SCH01_CONNECTED) XIC(BLENDER_XFR.SCH02_CONNECTED)
]OTE(BLENDER_XFR.CONVEY_SCH_VALVES_OK);
```

Annotations:
- The state contacts use BLENDER_XFR.STATES.3/.4 — the same keys the hose-valve HA rungs already
  use (X01VLV07/08/09/10 rung 4), so command and proof can never disagree by design.
- SPG TIMERS[1] only matters in SPG states 2-6, which only run while BLENDER_XFR is in states
  3/4 (Enabled latch, rung 23) — so no extra branches are needed for BLENDER states 1/2/5/6.
- DEV-04 (no BFV02/BFV04 open-proof) is intentionally NOT folded in here to keep this diff
  reviewable; propose separately if wanted.

### Emulator checks (Package 3)
1. Config 3 campaign in sim: verify SPG passes state 2 during SCH01 convey (previously stuck),
   VLV09 commanded/VLV07 not; after handoff (Package 5) VLV07 commanded/VLV09 not, and SPG
   re-proves through state 2 without TRANS.10.
2. Configs 1/2/4/5 regression: unchanged behavior.
3. Force `X01VLV10_ZS_ZSC.SIM.MI` on during config 3: SCH02_CONNECTED drops (UTILITY rung 4
   XIO contact) → proof fails → TIMERS[1] resets.

---

## PACKAGE 4 — Bag counting & bag-dump weight (BUG-05, BUG-06, Q8 approved)

**Routines:** `Devices/X01BGD01_LDC01`, `MainProgram/BLENDER_XFR` — Status: ready.
**Note:** TRANS.4/TRANS.5 rewrites below already include the `XIC(SPG_BLP_XFR.STATES.1)` purge
handshake from Package 5 so these rungs are only touched once. Until Package 5 is transcribed,
that contact is satisfied whenever SPG is idle-waiting, so Package 4 is testable standalone
(purge will simply not be triggered yet).

### 4.1 X01BGD01_LDC01 — write the bag-dump weight register (BUG-06)

Insert as new rung 1 (after the `Special` NOP rung 0), mirroring X01SCH01_LDC01 rung 1:

```
NEW Rung: [XIO(SIM_ENABLED) MOVE(X01BGD01_LDC01.WT.Gross,BLENDER_XFR.BGD01_WEIGHT) ,XIC(SIM_ENABLED) MOVE(X01BGD01_LDC01.WT.SIM.Value,BLENDER_XFR.BGD01_WEIGHT) ];
```

- Uses **WT.Gross** (not .Net) because the consumer (BLENDER_XFR rung 13) compares against
  `X01BGD01_LDC01.EMPTYALM.SP`, and the EMPTYALM rung (line 761) alarms on WT.Gross. Keep the
  comparison basis identical.

### 4.2 BLENDER_XFR — decrement on initial fill (Q8: total bags)

Insert new rung immediately after rung 3 (the TRANS.2 rung). TRANS.2 is true for exactly one
scan (rung 17 changes the state the same scan), so this is a one-shot by construction — no ONS
needed:

```
NEW Rung: XIC(BLENDER_XFR.TRANS.2)[XIC(BLENDER_XFR.SCH01_SELECTED) GT(BLENDER_XFR.BBU01_BAGS_REMAINING,0) SUB(BLENDER_XFR.BBU01_BAGS_REMAINING,1,BLENDER_XFR.BBU01_BAGS_REMAINING) ,XIC(BLENDER_XFR.SCH02_SELECTED) [XIO(BLENDER_XFR.BAG_DUMP_SELECTED) GT(BLENDER_XFR.BBU02_BAGS_REMAINING,0) SUB(BLENDER_XFR.BBU02_BAGS_REMAINING,1,BLENDER_XFR.BBU02_BAGS_REMAINING) ,XIC(BLENDER_XFR.BAG_DUMP_SELECTED) GT(BLENDER_XFR.BGD_BAGS_REMAINING,0) SUB(BLENDER_XFR.BGD_BAGS_REMAINING,1,BLENDER_XFR.BGD_BAGS_REMAINING) ] ];
```

- Only TRANS.2 (state-1 fill complete) is used; the refill-loop return (TRANS.7) keeps its
  decrement in rung 7, unchanged.
- Assumption carried from the audit: one fill-to-LS-high cycle = one bag (this is the existing
  state-5 convention). For the 50-lb bag dump this PLC count is secondary to the operator's
  manual count per §7.4.

### 4.3 BLENDER_XFR rung 5 — TRANS.4 rewrite (BUG-05, removes bag-count gating)

```
CURRENT (line 1792):
[XIO(SIM_ENABLED) ,XIC(SIM_ENABLED) XIC(SIM_BITS.4) ]XIC(BLENDER_XFR.STATES.3)XIC(BLENDER_XFR.ENABLED)[[XIO(BLENDER_XFR.SCH01_SELECTED) ,EQ(BLENDER_XFR.BBU01_BAGS_REMAINING,0) ] ,NE(BLENDER_XFR.BBU01_BAGS_REMAINING,0) LT(BLENDER_XFR.SCH01_WEIGHT,X01SCH01_LDC01.EMPTYALM.SP) [MOVE(BLENDER_XFR.SCH01_WEIGHT,BLENDER_XFR.SCH01_REFILL_END_WT) ,CPT(BLENDER_XFR.SCH01_REFILL_DELTA_WT,BLENDER_XFR.SCH01_REFILL_START_WT - BLENDER_XFR.SCH01_WEIGHT) ,CPT(BLENDER_XFR.SCH01_CAMPAIGN_WT,BLENDER_XFR.SCH01_CAMPAIGN_WT + (BLENDER_XFR.SCH01_REFILL_START_WT - BLENDER_XFR.SCH01_WEIGHT)) ,CPT(BLENDER_XFR.CAMPAIGN_WEIGHT,BLENDER_XFR.CAMPAIGN_WEIGHT + (BLENDER_XFR.SCH01_REFILL_START_WT - BLENDER_XFR.SCH01_WEIGHT)) ] ]OTE(BLENDER_XFR.TRANS.4);

PROPOSED:
[XIO(SIM_ENABLED) ,XIC(SIM_ENABLED) XIC(SIM_BITS.4) ]XIC(BLENDER_XFR.STATES.3)XIC(BLENDER_XFR.ENABLED)XIC(SPG_BLP_XFR.STATES.1)[XIO(BLENDER_XFR.SCH01_SELECTED) ,XIC(BLENDER_XFR.SCH01_SELECTED) LT(BLENDER_XFR.SCH01_WEIGHT,X01SCH01_LDC01.EMPTYALM.SP) [MOVE(BLENDER_XFR.SCH01_WEIGHT,BLENDER_XFR.SCH01_REFILL_END_WT) ,CPT(BLENDER_XFR.SCH01_REFILL_DELTA_WT,BLENDER_XFR.SCH01_REFILL_START_WT - BLENDER_XFR.SCH01_WEIGHT) ,CPT(BLENDER_XFR.SCH01_CAMPAIGN_WT,BLENDER_XFR.SCH01_CAMPAIGN_WT + (BLENDER_XFR.SCH01_REFILL_START_WT - BLENDER_XFR.SCH01_WEIGHT)) ,CPT(BLENDER_XFR.CAMPAIGN_WEIGHT,BLENDER_XFR.CAMPAIGN_WEIGHT + (BLENDER_XFR.SCH01_REFILL_START_WT - BLENDER_XFR.SCH01_WEIGHT)) ] ]OTE(BLENDER_XFR.TRANS.4);
```

Instruction-level diff:
- **Insert** `XIC(SPG_BLP_XFR.STATES.1)` after `XIC(BLENDER_XFR.ENABLED)` (purge handshake —
  state 3 cannot be left until SPG has purged and returned to Wait-for-Call).
- **Delete** the `EQ(BBU01_BAGS_REMAINING,0)` skip sub-branch and the `NE(...,0)` qualifier on
  the convey-complete branch. Bag counts no longer gate state transitions at all — they live
  only in the fill/refill logic. The hopper conveys to empty regardless of count, which fixes
  the stranded-last-bag deadlock and the missing final deltas.
- **Insert** `XIC(BLENDER_XFR.SCH01_SELECTED)` on the convey-complete branch (was implied by the
  old NE qualifier path; making it explicit keeps the not-selected skip exclusive).
- Delta-recording one-shot is preserved by the same mechanism as today (TRANS.4 true one scan).
  If hopper was already empty at entry, delta computes ≈0 — harmless.

### 4.4 BLENDER_XFR rung 6 — TRANS.5 rewrite (same pattern, SCH02 / bag dump)

```
PROPOSED:
[XIO(SIM_ENABLED) ,XIC(SIM_ENABLED) XIC(SIM_BITS.5) ]XIC(BLENDER_XFR.STATES.4)XIC(BLENDER_XFR.ENABLED)XIC(SPG_BLP_XFR.STATES.1)[XIO(BLENDER_XFR.SCH02_SELECTED) ,XIC(BLENDER_XFR.SCH02_SELECTED) LT(BLENDER_XFR.SCH02_WEIGHT,X01SCH02_LDC01.EMPTYALM.SP) [MOVE(BLENDER_XFR.SCH02_WEIGHT,BLENDER_XFR.SCH02_REFILL_END_WT) ,CPT(BLENDER_XFR.SCH02_REFILL_DELTA_WT,BLENDER_XFR.SCH02_REFILL_START_WT - BLENDER_XFR.SCH02_WEIGHT) ,CPT(BLENDER_XFR.SCH02_CAMPAIGN_WT,BLENDER_XFR.SCH02_CAMPAIGN_WT + (BLENDER_XFR.SCH02_REFILL_START_WT - BLENDER_XFR.SCH02_WEIGHT)) ,CPT(BLENDER_XFR.CAMPAIGN_WEIGHT,BLENDER_XFR.CAMPAIGN_WEIGHT + (BLENDER_XFR.SCH02_REFILL_START_WT - BLENDER_XFR.SCH02_WEIGHT)) ] ]OTE(BLENDER_XFR.TRANS.5);
```

- All BBU02/BGD bag-count branches removed; same handshake and selected-qualifier as 4.3.
- Rungs 7, 8, 9, 10 (refill update, completion, TRANS.6/7) are **unchanged** — verified against
  the new counting: N total bags = initial fill (−1 at TRANS.2) + N−1 refills (−1 each in
  rung 7); after the last load conveys, state 5 finds bags=0 + hoppers empty → TRANS.6 → record
  end values. TRANS.7 can't fire (LS low, hoppers empty).

### Emulator checks (Package 4)
1. Config 1, BBU01 bag count = 3: campaign must consume exactly 3 fill cycles and convey all 3
   (watch BBU01_BAGS_REMAINING: 3→2 at TRANS.2, →1, →0 in state-5 refills; final load conveys;
   state 6 reached; CAMPAIGN_WEIGHT ≈ 3 × sim load).
2. Bag-dump campaign (BAG_DUMP_SELECTED, BGD count = 2): state-5 refill must now occur (BGD01
   weight register now lives) and campaign completes.
3. Regression: bag count = 1 (single fill, no refill) completes with one convey.

---

## PACKAGE 5 — Purge-to-completion at hopper handoff and campaign end (BUG-04, Q3 approved)

**Routines:** `MainProgram/UTILITY`, `Devices/X01ALK03`, `Devices/X01ALK04` — Status: ready
(requires Packages 3 & 4 transcribed first).

### Design summary (read before transcribing)

- Trigger: the existing dead contact `aa_conditions_stopping_xfr` in SPG TRANS.6 (rung 6) becomes
  the "active hopper reached empty" signal. SPG then runs state 5 (Purge) to completion and
  returns to state 1.
- Handoff: BLENDER_XFR TRANS.4/TRANS.5 are already gated on `XIC(SPG_BLP_XFR.STATES.1)`
  (Package 4), so the source switch happens only after the purge finishes. Valve commands hold
  during the purge because BLENDER_XFR stays in state 3/4 and `SPG_BLP_XFR.Enabled` stays
  latched (rung 23) — `TIMERS[1]` therefore stays DN and **TRANS.10 needs no modification**.
- Scan-order (verified): MainProgram order is UTILITY → RECIPE → BLENDER_XFR → SPG_BLP_XFR.
  The scan after SPG reaches state 1, BLENDER_XFR runs first and takes TRANS.4/5 before SPG can
  re-arm TRANS.3 — no double-convey of the empty hopper, no race.
- **Explicit behavior decision:** operator STOP remains an immediate abort with NO purge
  (current behavior, unchanged). Spec 7.6 only requires purge at the empty-weight handoff; at
  campaign end the line is already purged before the stop. If a graceful purge-on-stop is wanted
  later, it is a separate package (Stop must defer the Enabled unlatch until purge completes).

### 5.1 UTILITY — new rung driving aa_conditions_stopping_xfr (insert after rung 12)

```
NEW Rung: [XIC(BLENDER_XFR.STATES.3) XIC(BLENDER_XFR.SCH01_SELECTED) LT(BLENDER_XFR.SCH01_WEIGHT,X01SCH01_LDC01.EMPTYALM.SP) ,XIC(BLENDER_XFR.STATES.4) XIC(BLENDER_XFR.SCH02_SELECTED) LT(BLENDER_XFR.SCH02_WEIGHT,X01SCH02_LDC01.EMPTYALM.SP) ]OTE(aa_conditions_stopping_xfr);
```

- Same comparison (LT vs EMPTYALM.SP, same weight tags) as TRANS.4/5 so the purge trigger and
  the state transition can never disagree on "empty".
- SPG rung 6 (TRANS.6) already contains `XIC(aa_conditions_stopping_xfr)` — no change there.
- Sequence at empty: SPG state 4 → TRANS.6 → state 5 (purge, TIMERS[3]) → TRANS.8 → state 1 →
  BLENDER TRANS.4/5 fires → valves reposition under the new state → SPG TRANS.3 → state 2 →
  re-prove (TIMERS[1]) → state 3 → state 4. Blower runs throughout (Package 1 HA covers 3-6).
- If SPG is in state 6 (high pressure) when the hopper empties, it returns to state 4 first
  (TIMERS[5]) and then purges — acceptable; note for FAT.

### 5.2 X01ALK03 rung 11 — stop the airlock motor during purge (current line 209)

```
CURRENT:  XIC(BLENDER_XFR.STATES.3)[XIC(SPG_BLP_XFR.STATES.3) ,XIC(SPG_BLP_XFR.STATES.4) ,XIC(SPG_BLP_XFR.STATES.5) ]OTE(X01ALK03_VFD.M.HOA.HA);
PROPOSED: XIC(BLENDER_XFR.STATES.3)[XIC(SPG_BLP_XFR.STATES.3) ,XIC(SPG_BLP_XFR.STATES.4) ]OTE(X01ALK03_VFD.M.HOA.HA);
```

- Delete the `XIC(SPG_BLP_XFR.STATES.5)` branch: no material feed while purging. Rung 7
  (`X01ALK03_FYO.HOA.HA`, the shaft seal-purge solenoid) **keeps** state 5 — seal air should
  stay on while the line is pressurized.

### 5.3 X01ALK04 rung 11 — same change (current line 285)

```
CURRENT:  XIC(BLENDER_XFR.STATES.4)[XIC(SPG_BLP_XFR.STATES.3) ,XIC(SPG_BLP_XFR.STATES.4) ,XIC(SPG_BLP_XFR.STATES.5) ]OTE(X01ALK04_VFD.M.HOA.HA);
PROPOSED: XIC(BLENDER_XFR.STATES.4)[XIC(SPG_BLP_XFR.STATES.3) ,XIC(SPG_BLP_XFR.STATES.4) ]OTE(X01ALK04_VFD.M.HOA.HA);
```

- Rung 7 (ALK04_FYO) likewise unchanged.

### Emulator checks (Package 5)
1. Config 3 full campaign: at SCH01 empty, verify order: ALK03 stops → SPG state 5 for the full
   TIMERS_PRE[3] → state 1 → BLENDER state 4 → hose valves swap (VLV09 closes, VLV07 opens) →
   SPG 2→3→4 → ALK04 feeds. No TRANS.10 events during the swap.
2. Campaign end (SCH02 empty): purge completes BEFORE BLENDER_XFR enters state 5 (refill);
   SPG then parks 1→0 via TRANS.2 after Enabled unlatches. Confirm TIMERS[3].DN reached every
   purge (counter or trend in emulator).
3. Stop_PB during convey: immediate abort, no purge (expected per design decision above);
   confirm no dead-head — all valves and blower drop together.

---

## PACKAGE 6 — Alarm trigger conditions (BUG-16)

**Routines:** 13 device routines — Status: ready, but **each proposed condition is a design
proposal** — review the intended meaning per device before transcribing. All keep the existing
`[COND [MUL ,TON] ,[XIC(ATMR.DN) ,XIC(ALM.A) XIO(Reset_Ack)] OTE(ALM.A)]` template (the same
shape as the known-good X01BBU04 rung 6); the only change is adding the leading condition
to the timer branch group.

### 6.1 X01BLP01 rung 5 — motor proof mismatch (current line 851)

```
PROPOSED: [[XIC(X01BLP01_M.MO) XIO(X01BLP01_MCY.MI) ,XIO(X01BLP01_M.MO) XIC(X01BLP01_MCY.MI) ] [MUL(X01BLP01_MCY.ALM.ATMR_SP,1000,X01BLP01_MCY.ALM.ATMR.PRE) ,TON(X01BLP01_MCY.ALM.ATMR,?,?) ] ,[XIC(X01BLP01_MCY.ALM.ATMR.DN) ,XIC(X01BLP01_MCY.ALM.A) XIO(X01BLP01_MCY.ALM.Reset_Ack) ] OTE(X01BLP01_MCY.ALM.A) ];
```
(Identical structure to X01ALK01 rung 9 / X01FAN01 rung 5.)

### 6.2 Airlock ZS proofs — alarm when running without proof
Apply the pattern `<motor-running> XIO(<ZS_ZSC.MI>)` as the new leading condition:

| Routine/rung | Leading condition to insert |
|---|---|
| X01ALK01_ZS rung 3 | `XIC(X01ALK01_M.MO) XIO(X01ALK01_ZS_ZSC.MI)` |
| X01ALK02_ZS rung 3 | `XIC(X01ALK02_M.MO) XIO(X01ALK02_ZS_ZSC.MI)` |
| X01ALK03_ZS rung 3 | `XIC(X01ALK03_VFD.M.MO) XIO(X01ALK03_ZS_ZSC.MI)` |
| X01ALK04_ZS rung 3 | `XIC(X01ALK04_VFD.M.MO) XIO(X01ALK04_ZS_ZSC.MI)` |

> Open point carried from the audit: ALK01/02 REQUIRE their ZS in the run interlock but
> ALK03/04 do not (ALK03 rung 9 interlocks only on VLV03). If the ZS is a guard/access switch,
> ALK03/04 should also interlock on it — **not included here; confirm the switch's physical
> function first** (added as Q13 below).

### 6.3 BBU bag-empty relays — alarm when refilling from an empty bag
(`AA_YC.MI` made = bag empty, per the XIO usage in BLENDER_XFR rungs 11/12.)

| Routine/rung | Leading condition |
|---|---|
| X01BBU01_AA rung 3 | `XIC(BLENDER_XFR.SCH01_REFILL) XIC(X01BBU01_AA_YC.MI)` |
| X01BBU02_AA rung 3 | `XIC(BLENDER_XFR.SCH02_REFILL) XIC(X01BBU02_AA_YC.MI)` |

### 6.4 BBU door switches — alarm when refilling with door open

| Routine/rung | Leading condition |
|---|---|
| X01BBU01_ZS rung 3 | `XIC(BLENDER_XFR.SCH01_REFILL) XIO(X01BBU01_ZS_ZSC.MI)` |
| X01BBU02_ZS rung 3 | `XIC(BLENDER_XFR.SCH02_REFILL) XIO(X01BBU02_ZS_ZSC.MI)` |

> Same caveat: the door switches currently appear in NO interlock. If they are safety guards,
> alarming is not enough — see Q13.

### 6.5 Hose switches — alarm when the selected config requires a path that isn't connected
(Mirrors each routine's own SIM.Enabled config mapping, rung 13.)

| Routine/rung | Leading condition |
|---|---|
| X01VLV07_ZS rung 3 | `LIMIT(2,BLENDER_XFR.CONVEY_CONFIG,3) XIO(X01VLV07_ZS_ZSC.MI)` |
| X01VLV08_ZS rung 3 | `[EQ(BLENDER_XFR.CONVEY_CONFIG,4) ,EQ(BLENDER_XFR.CONVEY_CONFIG,6) ] XIO(X01VLV08_ZS_ZSC.MI)` |
| X01VLV09_ZS rung 3 | `[EQ(BLENDER_XFR.CONVEY_CONFIG,1) ,EQ(BLENDER_XFR.CONVEY_CONFIG,3) ] XIO(X01VLV09_ZS_ZSC.MI)` |
| X01VLV10_ZS rung 3 | `LIMIT(5,BLENDER_XFR.CONVEY_CONFIG,6) XIO(X01VLV10_ZS_ZSC.MI)` |

### Emulator checks (Package 6)
1. Cold boot, everything idle: NO alarm active after ATMR_SP elapses (this is the bug being
   fixed — today all 13 latch).
2. Trip each condition (e.g., refill active + AA_YC forced) → alarm after its ATMR delay; clear
   condition + Reset_Ack → alarm clears.

---

## PACKAGE 7 — Dust collection proof & proof-of-connection (DEV-02 now; DEV-01 blocked)

### 7a — X02 dust fan/filter auto + convey proof (DEV-02) — Status: ready, no new hardware

**X02FAN01 rung 3 (current line 1651) + new HA rung:**
```
NEW Rung: XIC(SPG_BLP_XFR.Enabled)OTE(X02FAN01_M.HOA.HA);
CURRENT:  XIC(X02FAN01_M.Interlock)[XIC(X02FAN01_M.HOA.HA) XIC(ab_STATE_PLACE_HOLDER) OTE(X02FAN01_M.AR) ,XIC(X02FAN01_M.HOA.HH) ]OTE(X02FAN01_M.MO);
PROPOSED: XIC(X02FAN01_M.Interlock)[XIC(X02FAN01_M.HOA.HA) OTE(X02FAN01_M.AR) ,XIC(X02FAN01_M.HOA.HH) ]OTE(X02FAN01_M.MO);
```
- HA keyed to `SPG_BLP_XFR.Enabled` — the same key as the X02 dust valves (X02VLV01/02 rung 4),
  so fan and valves run together for the whole transfer.
- Delete the `ab_STATE_PLACE_HOLDER` contact (never true).

**Valves rung 1 — add fan proof to CONVEY_BDR_VALVES_OK (current line 71):**
```
CURRENT:  [EQ(BLENDER_XFR.BLENDER_CONFIG,1) XIC(X02VLV01_ZSO.MI) XIC(X02VLV02_ZSC.MI) XIC(X01VLV11_FYO.MO) XIO(X01VLV12_FYO.MO) ,EQ(BLENDER_XFR.BLENDER_CONFIG,2) XIC(X02VLV01_ZSC.MI) XIC(X02VLV02_ZSO.MI) XIO(X01VLV11_FYO.MO) XIC(X01VLV12_FYO.MO) ]OTE(BLENDER_XFR.CONVEY_BDR_VALVES_OK);
PROPOSED: XIC(X02FAN01_MCY.MI)[EQ(BLENDER_XFR.BLENDER_CONFIG,1) XIC(X02VLV01_ZSO.MI) XIC(X02VLV02_ZSC.MI) XIC(X01VLV11_FYO.MO) XIO(X01VLV12_FYO.MO) ,EQ(BLENDER_XFR.BLENDER_CONFIG,2) XIC(X02VLV01_ZSC.MI) XIC(X02VLV02_ZSO.MI) XIO(X01VLV11_FYO.MO) XIC(X01VLV12_FYO.MO) ]OTE(BLENDER_XFR.CONVEY_BDR_VALVES_OK);
```
- Series `XIC(X02FAN01_MCY.MI)` ahead of the config branches: no convey without the dust fan
  proven. SIM note: X02FAN01 rung 17 needs `X02FAN01_MCY.SIM.Enabled` — there is no rung driving
  it today; add `NEW Rung: XIC(SIM_ENABLED)XIC(X02FAN01_M.MO)OTE(X02FAN01_MCY.SIM.Enabled);`
  (mirrors X01FAN01 rung 18 pattern) or emulator tests will stall in SPG state 2.

**X02FLT01 — filter pulse timer runs with the fan + offline-delay (current lines 1676-1680):**
```
CURRENT rung 1:  [MUL(X02FLT01_KC.Delay_Time_SP,1000,X02FLT01_KC.Delay_TMR.PRE) ,XIC(ab_STATE_PLACE_HOLDER) TOF(X02FLT01_KC.Delay_TMR,?,?) ,XIC(ab_STATE_PLACE_HOLDER) RES(X02FLT01_KC.Delay_TMR) ];
PROPOSED rung 1: [MUL(X02FLT01_KC.Delay_Time_SP,1000,X02FLT01_KC.Delay_TMR.PRE) ,XIC(X02FAN01_M.MO) TOF(X02FLT01_KC.Delay_TMR,?,?) ];
NEW Rung (after rung 1): XIC(X02FLT01_KC.Delay_TMR.DN)OTE(X02FLT01_KC.HOA.HA);
```
- TOF semantics: Delay_TMR.DN is true while the fan is commanded AND for Delay_Time_SP after it
  stops → pulse cleaning continues offline for the setpoint, then stops. Rung 4 (which already
  ANDs HOA.HA with Delay_TMR.DN) is left unchanged. The RES branch is deleted (placeholder).

### 7b — Proof-of-connection interlock (DEV-01, Q5) — Status: **BLOCKED, do not transcribe**

Blocked on: (a) DI card installation + terminal assignment, (b) customer answer to Q5 (behavior
when a switch is absent/unwired). Prepared skeleton for when both land:
- 4 new tags `X01BDR01_PSW01/02_ZSC`, `X01BDR02_PSW01/02_ZSC` (SPG_DI) + Panel_1_DI map rungs on
  the spare points.
- New proof word: `[EQ(BLENDER_CONFIG,1) XIC(PSW01) XIC(PSW02-of-BDR01) ,EQ(BLENDER_CONFIG,2) ...]
  OTE(BLENDER_XFR.CONVEY_HOSE_PROOF_OK)` ANDed into SPG TIMERS[1] (rung 22) alongside the three
  existing *_VALVES_OK bits, plus a maintained `HOSE_PROOF_BYPASS` HMI bit (alarm-annunciated)
  for commissioning. Final form after Q5.

---

## Deferred to next round (not in the approved priority list)

- BUG-14 (ALK02 AFI / seal-purge inconsistency), BUG-17 (BGD01_LDC01 unit mismatch), BUG-18
  (BGD02 HH mode contact), BUG-12 (NEXT_BAG OTU), BUG-11 (RECIPE_INDEX bounds), BUG-19 (sim
  CUST_INTERLOCK), BUG-20 (descriptions) — small, low-risk; can be batched on request.
- Item 8 stubs (CIP state machine, recipe rework, pressure±deadband control): each needs a short
  design doc + answers to Q2/Q4/Q12 before rung text is worth writing.

## New open question raised while drafting

- **Q13.** Physical function of X01ALK01..04_ZS ("Airlock Closed Proof Sw") and the BBU door
  switches: are these safety guards? ALK01/02 interlock on their ZS, ALK03/04 do not, and the
  BBU door switches appear in no interlock at all. If guards, ALK03/04 interlocks and the BBU
  airlock interlocks should include them (beyond the Package 6 alarms).
