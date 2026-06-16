# Phase 2B — Campaign Engine Simplification (single bag count, transactional record)

**Basis:** the operator-sequence email (2026-06-16) and `PHASE1_AUDIT_FINDINGS.md`.
**Goal:** collapse the per-refill-device bag counters into ONE campaign bag count, gut the recipe
system, make the campaign a transactional record (campaign #, material, total weight), expand
history, and stop totalizing scale hopper 2 when the bag dump (BGD) is its refill device.

**Workflow unchanged:** neutral rung text + instruction diffs; you transcribe and emulator-verify
before download. This package edits `MainProgram/BLENDER_XFR`, `MainProgram/RECIPE_MANAGEMENT`,
`MainProgram/MainRoutine`, the `SPG_BLENDER_XFR` UDT, and two SIM rungs in the LDC routines.

---

## 0. Reconciliation with Packages 4 & 5 (read first)

This package **supersedes Package 4's bag-counting logic entirely** (4.2, 4.3, 4.4 are replaced by
the rungs here — do not also apply them). It **keeps**:
- **Package 4.1** (BGD weight move into `BLENDER_XFR.BGD01_WEIGHT`) — still used to confirm a bag is
  present in the dump before a BGD refill.
- **Package 5** (purge-to-completion). The new TRANS.4/TRANS.5 rungs below retain the
  `XIC(SPG_BLP_XFR.STATES.1)` purge handshake, so SCH1-convey→purge→SCH2-convey→purge→refill all
  still sequence through the SPG state machine. Purges are NOT re-implemented here.

Packages 1, 2, 3, 6, 7 are independent of this package.

---

## 1. Model and decisions (assumptions flagged for your on-site meeting)

**One counter.** `CAMPAIGN_BAGS_REMAINING` = physical bags **not yet loaded** into a hopper.
Decremented when a hopper reaches level-high (one bag loaded). A "bag" = one hopper fill to the
level switch, both for the initial fill and each refill.

**Loop control.**
- A campaign cycle = fill included hopper(s) → convey SCH1 (if incl.) → purge → convey SCH2
  (if incl.) → purge → refill if more bags remain → operator "Next Cycle" → repeat.
- Continue while bags remain to load; end (record + stop) when the count reaches 0 and the last
  loaded material has been conveyed.

**Totalization.** `CAMPAIGN_WEIGHT` accumulates the conveyed delta (start−end) of each hopper.
SCH1 is always totalized (BBU1). **SCH2 is totalized only when BBU2 is its refill device; when
BAG_DUMP_SELECTED (BGD) is the SCH2 refill, SCH2 is conveyed but NOT totalized** — per your email.

**Sequential allocation (dual hopper).** SCH1 is filled first; SCH2 is filled only if a bag
remains after SCH1's allocation (`GT(rem,1)` when both are selected). Consequence for an **odd**
total with both hoppers: the last cycle fills SCH1 only. SCH1-priority is an assumption.

### Assumptions to confirm at the meeting (these are real ambiguities)
- **A1 — continue threshold.** Email says "refill if bag count > 1"; with decrement-at-load the
  arithmetically correct continue condition is **> 0** (otherwise the final bag is stranded). I
  implemented `> 0`. Confirm.
- **A2 — odd count, both hoppers.** Last cycle feeds SCH1 only (SCH1-priority). Confirm priority
  and whether odd totals are even allowed when both hoppers run.
- **A3 — one refill device per campaign.** BAG_DUMP_SELECTED is a single campaign-level selection
  (SCH2 = BBU2 *or* BGD, never both). Matches your "(only one per campaign?)". Confirm.
- **A4 — bag = one hopperful to level-high.** If a single physical bag does not reliably fill the
  hopper to the level switch, this whole counting model needs rework (count by BBU bag-empty
  signal instead). Confirm the physical assumption.
- **A5 — skipped-hopper purge.** When SCH2 is selected but skipped (odd last cycle), the SPG
  machine still runs one empty convey+purge on line 2 before advancing. Harmless air cycle;
  flag if you want it optimized out.

---

## 2. UDT changes — `SPG_BLENDER_XFR`

Apply in Studio 5000 (Logix Designer → Data Types → User-Defined → SPG_BLENDER_XFR). Adding
members is non-destructive; **do not delete the now-unused members for MVP** — leave them so
existing HMI tags don't go invalid. Remove them in a later cleanup once the HMI is repointed.

### 2.1 ADD members
| Member | Type | Purpose |
|---|---|---|
| `CAMPAIGN_BAG_COUNT` | DINT | Operator-entered total bags for the campaign |
| `CAMPAIGN_BAGS_REMAINING` | DINT | Bags not yet loaded (countdown) |
| `REFILL_PENDING` | BOOL | Latched at state-5 entry: this cycle has more bags to load |
| `REFILL_DEC_DONE` | BOOL | One-shot guard for the state-5 refill decrement |
| `NEXT_CYCLE` | BOOL | Operator "Next Cycle" pushbutton (replaces `NEXT_BAG`) |
| `NEXT_CYCLE_AVAILABLE` | BOOL | HMI indicator: refills done, ready for operator |

### 2.2 CHANGE dimension
- `CAMPAIGN_HISTORY` : increase from `[30]` to **`[100]`** (adjust to taste; ~10 KB, trivial on
  the L320ER). All wrap literals in the record rung change from `29` to `99` (§5.10).

### 2.3 (Optional) transactional timestamp
If you want a date/time stamp on each record, add to the `CAMPAIGN_HISTORY` element UDT:
- `CAMPAIGN_DATETIME` : DINT[7]  (populated by `GSV(WALLCLOCKTIME,,DateTime,...)` — see §5.10 note).

### 2.4 Now-UNUSED after this package (leave in place for MVP, delete later)
`CAMPAIGN_BBU01_BAG_COUNT`, `CAMPAIGN_BBU02_BAG_COUNT`, `CAMPAIGN_BGD_BAG_COUNT`,
`BBU01_BAGS_REMAINING`, `BBU02_BAGS_REMAINING`, `BGD_BAGS_REMAINING`,
`BBU01_CAMPAIGN_WT`, `BBU02_CAMPAIGN_WT`, `BGD_CAMPAIGN_WT`,
`BBU01_REFILL_UPDATE_DONE`, `BBU02_REFILL_UPDATE_DONE`, `BGD_REFILL_UPDATE_DONE`,
`REFILL_UPDATE_DONE`, `REFILL_COMPLETE`, `ACTIVE_REFILL_SOURCE`, `LAST_REFILL_SOURCE`,
`NEXT_BAG`, `RECIPES[]`, `RECIPE_INDEX`, `ACTIVE_RECIPE` (and its recipe element UDT).

---

## 3. Gut the recipe system

### 3.1 MainProgram/MainRoutine rung 1 — remove the JSR
```
CURRENT:  Rung 1: JSR(RECIPE_MANAGEMENT,0);
PROPOSED: (delete the rung)
```
Renumbers the remaining JSRs; functionally just removes the recipe scan.

### 3.2 RECIPE_MANAGEMENT — empty the routine
Replace all 5 rungs (lines 1861-1865) with a single:
```
Rung 0: NOP();
```
(Or delete the routine after the JSR is removed. NOP is the lower-risk choice.)

### 3.3 HMI consequence
The operator now writes **`BLENDER_XFR.CAMPAIGN_MATERIAL`** (string) and
**`BLENDER_XFR.CAMPAIGN_BAG_COUNT`** (DINT) directly from input fields — no recipe card lookup in
the PLC. Material and bag count are no longer overwritten each scan (this also closes DEV-05).

---

## 4. Totalization change — BGD does not totalize SCH2

Folded into the TRANS.5 rewrite in §5.5. Net effect: the three `CPT(... CAMPAIGN_WEIGHT ...)` /
`SCH02_CAMPAIGN_WT` adds for SCH2 are gated `XIO(BLENDER_XFR.BAG_DUMP_SELECTED)`.

---

## 5. BLENDER_XFR rung rewrites

Rung numbers reference the current export (lines 1777-1849). Where a rung is **NEW**, insert it at
the indicated point; renumber downstream. Unchanged rungs: R0, R1, R4, R15-R19, R21-R33 (except
the small reset edits in §5.11). `rem` below is shorthand for `BLENDER_XFR.CAMPAIGN_BAGS_REMAINING`.

### 5.1 R2 — TRANS.1 init (REWRITE)
```
CURRENT (line 1782):  [XIO(SIM_ENABLED) ,XIC(SIM_ENABLED) XIC(SIM_BITS.1) ]XIC(BLENDER_XFR.TRANS.1)[MOVE(BLENDER_XFR.CAMPAIGN_BBU01_BAG_COUNT,BLENDER_XFR.BBU01_BAGS_REMAINING) , ... long per-device clears ... ];

PROPOSED: [XIO(SIM_ENABLED) ,XIC(SIM_ENABLED) XIC(SIM_BITS.1) ]XIC(BLENDER_XFR.TRANS.1)[MOVE(BLENDER_XFR.CAMPAIGN_BAG_COUNT,BLENDER_XFR.CAMPAIGN_BAGS_REMAINING) ,CLR(BLENDER_XFR.CAMPAIGN_WEIGHT) ,CLR(BLENDER_XFR.SCH01_CAMPAIGN_WT) ,CLR(BLENDER_XFR.SCH02_CAMPAIGN_WT) ,CLR(BLENDER_XFR.SCH01_REFILL_DELTA_WT) ,CLR(BLENDER_XFR.SCH02_REFILL_DELTA_WT) ,OTU(BLENDER_XFR.REFILL_PENDING) ,OTU(BLENDER_XFR.REFILL_DEC_DONE) ,OTU(BLENDER_XFR.NEXT_CYCLE) ];
```
- Loads the single counter from the operator value; clears campaign totals and the new flags.

### 5.2 R3 — TRANS.2, initial fill complete (REWRITE)
```
PROPOSED: [XIO(SIM_ENABLED) ,XIC(SIM_ENABLED) XIC(SIM_BITS.2) ]XIC(BLENDER_XFR.STATES.1)XIC(BLENDER_XFR.ENABLED)XIO(BLENDER_XFR.SCH01_REFILL)XIO(BLENDER_XFR.SCH02_REFILL)XIO(BLENDER_XFR.SCH02_BGD_REFILL)[XIC(BLENDER_XFR.SCH01_SELECTED) XIC(X01SCH01_LS_LSH.MI) ,XIC(BLENDER_XFR.SCH02_SELECTED) XIC(X01SCH02_LS_LSH.MI) ]OTE(BLENDER_XFR.TRANS.2);
```
- Fill done when no fill driver is still active (all commanded fills reached level-high) AND at
  least one selected hopper is at level-high (confirms a real fill; covers the odd-count skip).

### 5.3 NEW rung after R3 — initial-fill bag decrement
```
NEW Rung: XIC(BLENDER_XFR.TRANS.2)[XIC(BLENDER_XFR.SCH01_SELECTED) XIC(X01SCH01_LS_LSH.MI) SUB(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,1,BLENDER_XFR.CAMPAIGN_BAGS_REMAINING) ,XIC(BLENDER_XFR.SCH02_SELECTED) XIC(X01SCH02_LS_LSH.MI) SUB(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,1,BLENDER_XFR.CAMPAIGN_BAGS_REMAINING) ];
```
- TRANS.2 is true for one scan → natural one-shot. Decrements once per hopper actually filled.

### 5.4 R5 — TRANS.4, SCH1 convey complete + totalize (REWRITE; keeps Package 5 handshake)
```
PROPOSED: [XIO(SIM_ENABLED) ,XIC(SIM_ENABLED) XIC(SIM_BITS.4) ]XIC(BLENDER_XFR.STATES.3)XIC(BLENDER_XFR.ENABLED)[XIO(BLENDER_XFR.SCH01_SELECTED) ,XIC(BLENDER_XFR.SCH01_SELECTED) XIC(SPG_BLP_XFR.STATES.1) LT(BLENDER_XFR.SCH01_WEIGHT,X01SCH01_LDC01.EMPTYALM.SP) [MOVE(BLENDER_XFR.SCH01_WEIGHT,BLENDER_XFR.SCH01_REFILL_END_WT) ,CPT(BLENDER_XFR.SCH01_REFILL_DELTA_WT,BLENDER_XFR.SCH01_REFILL_START_WT - BLENDER_XFR.SCH01_WEIGHT) ,CPT(BLENDER_XFR.SCH01_CAMPAIGN_WT,BLENDER_XFR.SCH01_CAMPAIGN_WT + (BLENDER_XFR.SCH01_REFILL_START_WT - BLENDER_XFR.SCH01_WEIGHT)) ,CPT(BLENDER_XFR.CAMPAIGN_WEIGHT,BLENDER_XFR.CAMPAIGN_WEIGHT + (BLENDER_XFR.SCH01_REFILL_START_WT - BLENDER_XFR.SCH01_WEIGHT)) ] ]OTE(BLENDER_XFR.TRANS.4);
```
- SCH1 always totalized. Not-selected branch advances immediately. `XIC(SPG_BLP_XFR.STATES.1)`
  holds the transition until the line has purged (Package 5).

### 5.5 R6 — TRANS.5, SCH2 convey complete + totalize unless BGD (REWRITE)
```
PROPOSED: [XIO(SIM_ENABLED) ,XIC(SIM_ENABLED) XIC(SIM_BITS.5) ]XIC(BLENDER_XFR.STATES.4)XIC(BLENDER_XFR.ENABLED)[XIO(BLENDER_XFR.SCH02_SELECTED) ,XIC(BLENDER_XFR.SCH02_SELECTED) XIC(SPG_BLP_XFR.STATES.1) LT(BLENDER_XFR.SCH02_WEIGHT,X01SCH02_LDC01.EMPTYALM.SP) [MOVE(BLENDER_XFR.SCH02_WEIGHT,BLENDER_XFR.SCH02_REFILL_END_WT) ,XIO(BLENDER_XFR.BAG_DUMP_SELECTED) CPT(BLENDER_XFR.SCH02_REFILL_DELTA_WT,BLENDER_XFR.SCH02_REFILL_START_WT - BLENDER_XFR.SCH02_WEIGHT) ,XIO(BLENDER_XFR.BAG_DUMP_SELECTED) CPT(BLENDER_XFR.SCH02_CAMPAIGN_WT,BLENDER_XFR.SCH02_CAMPAIGN_WT + (BLENDER_XFR.SCH02_REFILL_START_WT - BLENDER_XFR.SCH02_WEIGHT)) ,XIO(BLENDER_XFR.BAG_DUMP_SELECTED) CPT(BLENDER_XFR.CAMPAIGN_WEIGHT,BLENDER_XFR.CAMPAIGN_WEIGHT + (BLENDER_XFR.SCH02_REFILL_START_WT - BLENDER_XFR.SCH02_WEIGHT)) ] ]OTE(BLENDER_XFR.TRANS.5);
```
- The three `XIO(BAG_DUMP_SELECTED)`-gated CPTs are the **BGD no-totalize** behavior: when BGD
  feeds SCH2, the convey still completes (TRANS.5 fires) but no weight is accumulated.

### 5.6 R7 and R8 — DELETE
Old per-device delta validation, bag decrement, and `REFILL_UPDATE_DONE` composition are removed
(replaced by §5.3, §5.7, §5.8).

### 5.7 NEW rung — capture REFILL_PENDING at state-5 entry, re-arm decrement
```
NEW Rung: XIC(BLENDER_XFR.TRANS.5)[GT(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,0) OTL(BLENDER_XFR.REFILL_PENDING) ,LE(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,0) OTU(BLENDER_XFR.REFILL_PENDING) ,OTU(BLENDER_XFR.REFILL_DEC_DONE) ];
```
- One scan (TRANS.5). Latches "this cycle still has bags to load" from the live count BEFORE the
  state-5 refill decrement runs — this is what prevents the last bag from being stranded.

### 5.8 NEW rung — state-5 refill bag decrement (one-shot)
```
NEW Rung: XIC(BLENDER_XFR.STATES.5)XIC(BLENDER_XFR.REFILL_PENDING)XIO(BLENDER_XFR.REFILL_DEC_DONE)XIO(BLENDER_XFR.SCH01_REFILL)XIO(BLENDER_XFR.SCH02_REFILL)XIO(BLENDER_XFR.SCH02_BGD_REFILL)[XIC(BLENDER_XFR.SCH01_SELECTED) XIC(X01SCH01_LS_LSH.MI) SUB(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,1,BLENDER_XFR.CAMPAIGN_BAGS_REMAINING) ,XIC(BLENDER_XFR.SCH02_SELECTED) XIC(X01SCH02_LS_LSH.MI) SUB(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,1,BLENDER_XFR.CAMPAIGN_BAGS_REMAINING) ,[XIC(BLENDER_XFR.SCH01_SELECTED) XIC(X01SCH01_LS_LSH.MI) ,XIC(BLENDER_XFR.SCH02_SELECTED) XIC(X01SCH02_LS_LSH.MI) ] OTL(BLENDER_XFR.REFILL_DEC_DONE) ];
```
- Fires once when the refill drivers have dropped (hoppers at level-high). Decrements per hopper
  refilled; latches `REFILL_DEC_DONE` so it can't repeat. Re-armed by §5.7 on the next entry.

### 5.9 NEW rung — NEXT_CYCLE_AVAILABLE indicator
```
NEW Rung: XIC(BLENDER_XFR.STATES.5)XIC(BLENDER_XFR.REFILL_PENDING)XIO(BLENDER_XFR.SCH01_REFILL)XIO(BLENDER_XFR.SCH02_REFILL)XIO(BLENDER_XFR.SCH02_BGD_REFILL)[XIC(BLENDER_XFR.SCH01_SELECTED) XIC(X01SCH01_LS_LSH.MI) ,XIC(BLENDER_XFR.SCH02_SELECTED) XIC(X01SCH02_LS_LSH.MI) ]OTE(BLENDER_XFR.NEXT_CYCLE_AVAILABLE);
```
- HMI lamp/button-enable: refills complete, waiting for the operator.

### 5.10 R9 / R10 — TRANS.6 (end) and TRANS.7 (next cycle) (REWRITE)
```
R9 (TRANS.6 → record end) PROPOSED:
[XIO(SIM_ENABLED) ,XIC(SIM_ENABLED) XIC(SIM_BITS.7) ]XIC(BLENDER_XFR.STATES.5)XIC(BLENDER_XFR.ENABLED)XIO(BLENDER_XFR.REFILL_PENDING)OTE(BLENDER_XFR.TRANS.6);

R10 (TRANS.7 → next cycle, back to state 2) PROPOSED:
[XIO(SIM_ENABLED) ,XIC(SIM_ENABLED) XIC(SIM_BITS.8) ]XIC(BLENDER_XFR.STATES.5)XIC(BLENDER_XFR.ENABLED)XIC(BLENDER_XFR.NEXT_CYCLE_AVAILABLE)XIC(BLENDER_XFR.NEXT_CYCLE)OTE(BLENDER_XFR.TRANS.7);
```
- At state-5 entry, `REFILL_PENDING=0` (count was 0) → TRANS.6 → record/stop. Otherwise refills
  run, `NEXT_CYCLE_AVAILABLE` sets, and the operator's `NEXT_CYCLE` press → TRANS.7 → state 2.

### 5.10b NEW rung — clear the momentary NEXT_CYCLE (fixes BUG-12)
```
NEW Rung: XIC(BLENDER_XFR.TRANS.7)OTU(BLENDER_XFR.NEXT_CYCLE);
```

### 5.11 R11 / R12 / R13 — fill/refill drivers (REWRITE, single counter + sequential alloc)
```
R11 SCH01_REFILL PROPOSED:
[XIC(BLENDER_XFR.STATES.1) ,XIC(BLENDER_XFR.STATES.5) XIC(BLENDER_XFR.REFILL_PENDING) ]XIC(BLENDER_XFR.SCH01_SELECTED)XIO(X01SCH01_LS_LSH.MI)GT(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,0)OTE(BLENDER_XFR.SCH01_REFILL);

R12 SCH02_REFILL (BBU2) PROPOSED:
[XIC(BLENDER_XFR.STATES.1) ,XIC(BLENDER_XFR.STATES.5) XIC(BLENDER_XFR.REFILL_PENDING) ]XIC(BLENDER_XFR.SCH02_SELECTED)XIO(BLENDER_XFR.BAG_DUMP_SELECTED)XIO(X01SCH02_LS_LSH.MI)[XIC(BLENDER_XFR.SCH01_SELECTED) GT(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,1) ,XIO(BLENDER_XFR.SCH01_SELECTED) GT(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,0) ]OTE(BLENDER_XFR.SCH02_REFILL);

R13 SCH02_BGD_REFILL PROPOSED:
[XIC(BLENDER_XFR.STATES.1) ,XIC(BLENDER_XFR.STATES.5) XIC(BLENDER_XFR.REFILL_PENDING) ]XIC(BLENDER_XFR.SCH02_SELECTED)XIC(BLENDER_XFR.BAG_DUMP_SELECTED)XIO(X01SCH02_LS_LSH.MI)GE(BLENDER_XFR.BGD01_WEIGHT,X01BGD01_LDC01.EMPTYALM.SP)[XIC(BLENDER_XFR.SCH01_SELECTED) GT(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,1) ,XIO(BLENDER_XFR.SCH01_SELECTED) GT(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,0) ]OTE(BLENDER_XFR.SCH02_BGD_REFILL);
```
- SCH2's `GT(rem,1)`-when-SCH1-also-selected branch is the sequential allocation (SCH1 takes one
  bag first). `GE(BGD01_WEIGHT, EMPTYALM.SP)` requires Package 4.1's weight move; if you skip 4.1,
  drop that one term.

### 5.12 R14 — state 6, transactional record (REWRITE)
```
PROPOSED: XIC(BLENDER_XFR.STATES.6)[ADD(BLENDER_XFR.CAMPAIGN_NUMBER,1,BLENDER_XFR.CAMPAIGN_NUMBER) ,MOVE(BLENDER_XFR.CAMPAIGN_NUMBER,BLENDER_XFR.CAMPAIGN_HISTORY[BLENDER_XFR.CAMPAIGN_INDEX].CAMPAIGN_NUMBER) ,MOVE(BLENDER_XFR.CAMPAIGN_MATERIAL,BLENDER_XFR.CAMPAIGN_HISTORY[BLENDER_XFR.CAMPAIGN_INDEX].CAMPAIGN_MATERIAL) ,MOVE(BLENDER_XFR.CAMPAIGN_WEIGHT,BLENDER_XFR.CAMPAIGN_HISTORY[BLENDER_XFR.CAMPAIGN_INDEX].CAMPAIGN_WEIGHT) ,MOVE(BLENDER_XFR.SCH01_CAMPAIGN_WT,BLENDER_XFR.CAMPAIGN_HISTORY[BLENDER_XFR.CAMPAIGN_INDEX].CAMPAIGN_SCH01_WEIGHT) ,MOVE(BLENDER_XFR.SCH02_CAMPAIGN_WT,BLENDER_XFR.CAMPAIGN_HISTORY[BLENDER_XFR.CAMPAIGN_INDEX].CAMPAIGN_SCH02_WEIGHT) ,[GE(BLENDER_XFR.CAMPAIGN_INDEX,99) MOVE(0,BLENDER_XFR.CAMPAIGN_INDEX) ,LT(BLENDER_XFR.CAMPAIGN_INDEX,99) ADD(BLENDER_XFR.CAMPAIGN_INDEX,1,BLENDER_XFR.CAMPAIGN_INDEX) ] ,OTE(BLENDER_XFR.TRANS.8) ];
```
- `CAMPAIGN_NUMBER` is now a running, retentive counter incremented once per completed campaign
  (state 6 is a single scan). Ring buffer of 100; bump the two `99` literals if you change depth.
- **Optional timestamp:** add `GSV(WALLCLOCKTIME,,DateTime,BLENDER_XFR.CAMPAIGN_HISTORY[BLENDER_XFR.CAMPAIGN_INDEX].CAMPAIGN_DATETIME)` (needs §2.3 member).

### 5.13 R20 — TRANS.5 reset block (REWRITE)
```
CURRENT (line 1824):  XIC(BLENDER_XFR.TRANS.5)[OTU(BBU01_REFILL_UPDATE_DONE) ,OTU(BBU02_REFILL_UPDATE_DONE) ,OTU(BGD_REFILL_UPDATE_DONE) ,CLR(LAST_REFILL_SOURCE) ];
PROPOSED: (delete the rung — the REFILL_DEC_DONE re-arm now lives in §5.7)
```

---

## 6. SIM rung updates (emulator support)

### 6.1 X01SCH01_LDC01 rung 15 (line 975)
```
CHANGE: both NE(BLENDER_XFR.BBU01_BAGS_REMAINING,0) → NE(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,0)
```

### 6.2 X01SCH02_LDC01 rung 15 (line 1069)
```
CURRENT bracket: [XIC(BLENDER_XFR.BAG_DUMP_SELECTED) NE(BLENDER_XFR.BGD_BAGS_REMAINING,0) ,XIO(BLENDER_XFR.BAG_DUMP_SELECTED) NE(BLENDER_XFR.BBU02_BAGS_REMAINING,0) ]
PROPOSED: NE(BLENDER_XFR.CAMPAIGN_BAGS_REMAINING,0)
```
(One condition now; the BGD/BBU distinction no longer affects the counter.)

---

## 7. Emulator verification (SIM_ENABLED = 1)

1. **Single hopper, 3 bags (SCH1→BDR01, config 1).** `CAMPAIGN_BAG_COUNT=3`. Expect 3 fill/convey
   cycles; `CAMPAIGN_BAGS_REMAINING` 3→2→1→0; two "Next Cycle" prompts; campaign record logged
   with NUMBER+1, material string, `CAMPAIGN_WEIGHT` ≈ 3 × sim load; ends in state 0.
2. **Both hoppers, 4 bags (config 3, BBU2).** 2 cycles, both hoppers each cycle; SCH1 and SCH2
   both totalized; rem 4→2→0.
3. **Both hoppers, 3 bags (odd).** Cycle 1 fills both; cycle 2 fills SCH1 only, SCH2 convey skipped;
   total weight = SCH1×2 + SCH2×1; rem 3→1→0.
4. **BGD as SCH2 refill.** Select bag dump. Confirm SCH2 conveys but `CAMPAIGN_WEIGHT` and
   `SCH02_CAMPAIGN_WT` do NOT increase for SCH2; SCH1 still totalized; bag count still decrements
   for SCH2 fills.
5. **Last-bag integrity.** In every case the final loaded bag is conveyed before state 6 (no
   stranded bag, no deadlock) — this is the core fix vs. the old per-device counters.
6. **Next Cycle is momentary.** Hold `NEXT_CYCLE` on: machine must advance exactly one cycle, not
   free-run (verify the §5.10b OTU).
7. **History wrap.** Force `CAMPAIGN_INDEX=99`, complete a campaign, confirm it writes index 99
   then wraps to 0; `CAMPAIGN_NUMBER` keeps incrementing.

---

## 8. HMI notes (cMT3092X)
- Replace recipe-management navigation with two input fields bound to `CAMPAIGN_MATERIAL` and
  `CAMPAIGN_BAG_COUNT`.
- Add a **Next Cycle** momentary button (`NEXT_CYCLE`) shown/enabled by `NEXT_CYCLE_AVAILABLE`.
- Campaign history viewer: expand to the new depth; show NUMBER / MATERIAL / total WEIGHT
  (+ SCH01/SCH02 split and timestamp if added).
- Keep the destination-blender select + hose-connected acknowledgment popup (existing CUST_INTERLOCK
  / SCH0x_CONNECTED path); this package does not change that interlock.

---

## 9. Open questions carried to the customer meeting
A1 continue threshold (>0 vs >1) · A2 odd-count both-hopper priority · A3 one refill device per
campaign · A4 one bag == one hopperful to level-high · A5 skipped-hopper purge cycle.
Plus from Phase 1: Q2 (recipe/totalizer interaction — largely resolved by gutting recipes), Q3
(purge sequence — implemented per Package 5), Q7 (BGD totalization — now implemented as "not
totalized" per your email).
