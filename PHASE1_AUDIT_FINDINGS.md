# System 02 Pressure Convey — Phase 1 Audit Findings

**Scope:** Read-only audit of `Adjuvants_2026_06_10_logic.md` (neutral-text export) against the
customer spec (brief §7), the P&ID (`flow diagram.png`), the CIP table, and the HMI screenshot.
No code was modified. Line references are to `Adjuvants_2026_06_10_logic.md`.

**Key context established during the audit (used as evidence below):**

- The P&ID title block states **"No. of Sources: 1, No. of Destinations: 1"** — the convey line is
  designed to run one source at a time, even in dual-hopper campaigns. This is the tiebreaker for
  the derived valve table in brief §5: the per-valve auto logic (one hose valve at a time, keyed to
  the active convey state) matches the P&ID; the `Valves` proof rung (which expects both hose
  valves open simultaneously for configs 3/6) does not.
- Tag CSV resolves device identities: X01SCH01/05 = scale-hopper dust valves, X01SCH02/06 =
  hopper inlet valves, X01SCH03/07 = air-dry valves, X01SCH04/08 = solimar pads.
- The hose-station `_ZS` inputs (VLV07–10) are commented **"HOSE CONNECTED"** in code and used as
  connection proofs (`SCHxx_CONNECTED`, UTILITY rungs 3–4), although the tag descriptions call them
  "Closed Proof Sw". These are distinct from the four **new** proof-of-connection switches at the
  blender pinch valves (§7.2), which are not yet wired (spare DI Local:4 Pt10–15 / Local:5 available).
- Placeholder tags `aa_STATE_PLACE_HOLDER`, `ab_STATE_PLACE_HOLDER`, `aa_high_pressure_alm`,
  `aa_blower_aux_alm`, `aa_conditions_stopping_xfr`, `aa_blower_aux`, `aa_hi_press_switch`,
  `aa_convey_valve_proofs` are **never driven by any rung**. `aa_Ctrl_Power` is forced TRUE
  unconditionally (UTILITY rung 0). Every contact on these tags is dead logic.

---

## SAFETY-SEVERITY FINDINGS (all subsystems)

```
ID:            DEV-01
Type:          spec-deviation
Location:      Valves rung 2 (line 72); UTILITY rungs 3-4 (lines 1983-1984); Panel_1_DI (lines 2095-2116)
Severity:      safety
What the code does:
               Convey is interlocked only on the hose-station switch inputs
               (X01VLV07..10_ZS_ZSC) via SCH01_CONNECTED / SCH02_CONNECTED. There is no
               interlock — not even a placeholder — for the proof-of-connection switches at the
               blender pinch valves. The four inputs are unmapped (spare DI rungs 60-81 are
               XIC/XIO no-op pairs).
What the spec expects:
               §7.2: 2 proof switches per blender at each pinch valve (4 new DIs, new DI card);
               §7.3 popup acknowledgment that hoses are connected. Conveying pressurized powder
               to an unconnected/misconnected hose in a C1D2 area is the hazard being protected
               against.
Evidence:      Spare inputs Local:4:I.Pt10..15 and all of Local:5 are stubbed (lines 2095-2116);
               no tags exist for the new switches.
Proposed fix:  Add 4 DI device instances + mapping when hardware lands; AND the appropriate pair
               into CONVEY_BDR_VALVES_OK (or a new CONVEY_HOSE_PROOF_OK) per BLENDER_CONFIG;
               define behavior for unwired switches per Q5 before implementing (bypass bit vs.
               hard interlock).
Confidence:    high — exhaustive grep shows no other interlock source.
```

```
ID:            DEV-02
Type:          spec-deviation
Location:      X02FAN01 rung 3 (line 1651); X02FLT01 rungs 1,4 (lines 1676-1680); Valves rung 1 (line 71)
Severity:      safety
What the code does:
               The dust-collection fan X02FAN01 auto branch is gated on ab_STATE_PLACE_HOLDER
               (never true) — the fan never runs in Auto. The filter pulse timer X02FLT01_KC is
               gated on a Delay_TMR whose TOF input is also ab_STATE_PLACE_HOLDER — never runs
               in Auto. CONVEY_BDR_VALVES_OK proves only that the X02 dust VALVE is open; nothing
               proves the fan is running before/while conveying.
What the spec expects:
               §7.3: "Active dust collection at: destination blender, BBU, scale bin" during
               transfer. Combustible-dust housekeeping in a C1D2 area depends on this.
Evidence:      Only X02FAN01_M.HOA.HH (manual) can start the fan; grep shows no rung drives
               X02FAN01_M.HOA.HA. SPG_BLP_XFR TIMERS[2] (line 1949) checks X01FAN01/X01BLP01
               but not X02FAN01.
Proposed fix:  Drive X02FAN01_M.HOA.HA from SPG_BLP_XFR.Enabled (or states 2-6); add
               X02FAN01_MCY.MI to the convey permissives; give X02FLT01_KC a real run condition
               (typically: pulse while fan runs + offline delay).
Confidence:    high.
```

```
ID:            BUG-01
Type:          bug
Location:      X01SCH06 rung 3 (line 1200); X01SCH01 rung 3 (line 915)
Severity:      safety
What the code does:
               Both rungs contain an extra parallel branch OUTSIDE the Auto/Manual selection:
               X01SCH06 (SCH02 inlet valve) opens whenever SCH02_REFILL or SCH02_BGD_REFILL is
               on, and X01SCH01 (SCH01 dust valve) opens whenever X01ALK01_MCY.MI (BBU1 airlock
               running), regardless of the device's Auto_Mode and regardless of operator HOA
               commands. A device the operator has placed in Manual-OFF will still actuate.
               Compare X01SCH02 rung 3 (line 1009) — the SCH01 inlet valve — which is the same
               class of device and has NO bypass branch (asymmetric with X01SCH06).
What the spec expects:
               Template behavior everywhere else: Auto_Mode selects between sequence control
               (HOA.HA) and operator control (HOA.HH / Manual_Op). No silent bypasses.
Evidence:      Rung text branch `[XIC(BLENDER_XFR.SCH02_BGD_REFILL) ,XIC(BLENDER_XFR.SCH02_REFILL)]`
               sits as a third OR branch driving X01SCH06_FYO.MO directly; rung 4 already drives
               HOA.HA from the same bits, so the bypass is redundant in Auto and only has effect
               in Manual.
Proposed fix:  Delete the bypass branches; the existing HOA.HA rungs already provide the Auto
               behavior.
Confidence:    high — the branches are provably redundant in Auto and only change Manual behavior.
```

---

## A. Pressure convey sequence (SPG_BLP_XFR / BLENDER_XFR / Valves)

```
ID:            BUG-02
Type:          bug
Location:      X01BLP01 rung 3 (line 848); X01FAN01 rung 3 (line 886)
Severity:      functional (blocks all auto operation on real hardware)
What the code does:
               Blower X01BLP01 and fan X01FAN01 auto branches require HOA.HA, and grep confirms
               NO rung anywhere drives X01BLP01_M.HOA.HA or X01FAN01_M.HOA.HA. The only
               state-driven start branch is qualified XIC(SIM_ENABLED) — i.e., the blower/fan
               start from SPG states 3/4/5 ONLY in simulation. On real hardware, SPG state 3
               ("Start Blower") starts nothing; TIMERS[2] (airflow established, line 1949)
               requires X01FAN01_MCY.MI AND X01BLP01_MCY.MI, so the sequence stalls in state 3
               forever. Additionally X01BLP01_M.Interlock = X01FAN01_MCY.MI (rung 2, line 847),
               so the blower cannot even be started manually until the fan is manually started.
What the spec expects:
               State 3 starts the blower; convey proceeds when airflow established.
Evidence:      The SIM-only branch `XIC(SIM_ENABLED)[XIC(SPG_BLP_XFR.STATES.3),...]` in both
               rungs is clearly the intended auto condition, mis-qualified with SIM_ENABLED.
Proposed fix:  Drive X01BLP01_M.HOA.HA and X01FAN01_M.HOA.HA from SPG states 3/4/5 (and
               include Auto_Mode in the rung-3 selection per template), or remove the
               SIM_ENABLED qualifier from the existing branch. To be designed in Phase 2.
Confidence:    high.
```

```
ID:            BUG-03
Type:          bug
Location:      Valves rung 2 (line 72) vs. X01VLV07/08/09/10 rung 4 (lines 1418/1465/1512/1559)
Severity:      functional (dual-hopper configs 3 and 6 can never convey)
What the code does:
               For CONVEY_CONFIG 3, Valves rung 2 requires X01VLV07_FYO.MO AND X01VLV09_FYO.MO
               both TRUE (both hose paths commanded open simultaneously); config 6 likewise
               requires VLV08+VLV10. But the hose-valve auto rungs are state-exclusive:
               VLV09/VLV08 open only in BLENDER_XFR.STATES.3, VLV07/VLV10 only in STATES.4.
               The two conditions can never be true at once, so CONVEY_SCH_VALVES_OK is never
               true for configs 3/6, TIMERS[1] (valves-in-position, line 1947) never finishes,
               and SPG_BLP_XFR is stuck in state 2 ("Position Valves") indefinitely.
What the spec expects:
               P&ID: 1 source at a time. The per-valve logic (one hose path at a time, keyed to
               the active hopper's convey state) matches the P&ID; the proof rung does not.
               This also corrects brief §5's derived table for configs 3/6: hose valves open
               sequentially, not simultaneously.
Evidence:      Config-3 branch: `XIC(X01VLV07_FYO.MO) ... XIC(X01VLV09_FYO.MO)`; VLV07 rung 4:
               `LIMIT(2,CONVEY_CONFIG,3) XIC(BLENDER_XFR.STATES.4)`; VLV09 rung 4:
               `[EQ(CONFIG,1),EQ(CONFIG,3)] XIC(BLENDER_XFR.STATES.3)`.
Proposed fix:  Make Valves rung 2 state-aware for configs 3/6 (expect the STATES.3 valve set
               during SCH01 convey, the STATES.4 set during SCH02 convey, inactive path closed),
               not simultaneous-open. Confirm against Q3/Q9 before implementing.
Confidence:    high.
```

```
ID:            BUG-04
Type:          bug
Location:      SPG_BLP_XFR rung 10 (line 1921), rung 12 (1929), rung 17 (1934);
               BLENDER_XFR rungs 23-24 (lines 1830-1832)
Severity:      functional (convey line is never purged in any automatic path; spec 7.6 violated)
What the code does:
               TRANS.10 branch 1 fires whenever `XIO(Enabled) XIO(STATES.0)` — i.e., the moment
               SPG_BLP_XFR.Enabled is unlatched while in ANY non-idle state, including state 5
               (Purge). BLENDER_XFR rung 24 unlatches Enabled on Stop_PB AND whenever
               BLENDER_XFR enters state 5 (Refill) — which is the normal hopper-empty path.
               Scan trace: Enabled drops → rung 6 TRANS.6 (to purge) and rung 10 TRANS.10 (to
               idle) both fire; rung 17 executes after rung 12 so the scan ends in STATES.5; next
               scan TRANS.10 branch 1 fires again (Enabled still 0, not state 0) and rung 12
               forces STATES.0 — purge lasted exactly one scan, purge TIMERS[3] never completes.
               There is no other path that completes a purge: the call signal (UTILITY rung 12)
               never drops at hopper-empty, so TRANS.6's "call lost" path can't trigger purge
               with Enabled held, and every campaign-driven disable goes through rung 24.
What the spec expects:
               §7.6: "When scale-bin weight drops to empty: purge the convey line, ready the
               opposite scale bin." Purge must complete before switching/stopping.
Evidence:      Rung order in SPG_BLP_XFR Section 2 (TRANS.10 handled at rung 12, TRANS.6 at
               rung 17) plus OTL/OTU pairing of Enabled in BLENDER_XFR rungs 23-24.
Proposed fix:  Exclude STATES.5 (and arguably 6) from TRANS.10's disable branch so a purge in
               progress runs to completion, and/or delay the Enabled unlatch until SPG reaches
               state 1/0 after purging. Also requires the Q3 answer (purge between hopper swap?).
               Scan-order and OTL/OTU sensitive — emulator-verify in Phase 2.
Confidence:    high on the mechanism; medium on intended purge policy (Q3).
```

```
ID:            BUG-05
Type:          bug
Location:      BLENDER_XFR rung 5 (line 1792), rung 6 (line 1795), rung 7 (1798), rung 9 (1803)
Severity:      functional (last bag never conveyed; campaign deadlocks; totals understate)
What the code does:
               State-3 exit (TRANS.4) has branch `[XIO(SCH01_SELECTED) ,EQ(BBU01_BAGS_REMAINING,0)]`
               which skips the convey state immediately when the bag counter is zero. But the
               counter is decremented in state 5 when a bag is REFILLED into the hopper (rung 7),
               so it reaches 0 at the moment the LAST bag is loaded. On the next pass,
               state 3 is skipped without conveying and without recording deltas. The material
               sits in the hopper; state-5 completion (TRANS.6, rung 9) requires hopper weight
               <= EMPTYALM.SP, which is now impossible → the campaign deadlocks in state 5 with
               a full hopper, and CAMPAIGN_WEIGHT omits the final load. Same structure for SCH02
               (rung 6) including the bag-dump branch.
               Related off-by-one: the initial fill in state 1 is never decremented, so a recipe
               bag count of N consumes N+1 bags (initial + N refills) — unless the author
               intended the count to mean "refills after initial fill" (see Q8).
What the spec expects:
               Every loaded bag is conveyed and totalized (§7.3, §7.6).
Evidence:      Rung 7 decrement is gated XIC(STATES.5); rung 5 branch EQ(...,0) short-circuits
               TRANS.4 with no weight condition and no delta recording.
Proposed fix:  Make the skip branch require the hopper actually empty
               (e.g., EQ(bags,0) AND weight <= EMPTYALM.SP), or restructure so the
               convey-until-empty branch does not depend on bags remaining. Resolve Q8 first.
Confidence:    high on the mechanism; medium on intent (depends on bag-count semantics, Q8).
```

```
ID:            BUG-06
Type:          bug
Location:      BLENDER_XFR rung 13 (line 1812); X01BGD01_LDC01 routine (lines 753-778)
Severity:      functional (bag-dump campaigns cannot refill)
What the code does:
               The state-5 bag-dump refill permissive requires
               GE(BLENDER_XFR.BGD01_WEIGHT, X01BGD01_LDC01.EMPTYALM.SP), but BLENDER_XFR.BGD01_WEIGHT
               is never written anywhere in the program (grep: read-only). Unlike
               X01SCH01_LDC01/X01SCH02_LDC01 (rung 1 copies WT into BLENDER_XFR.SCHxx_WEIGHT),
               X01BGD01_LDC01 has no such move. BGD01_WEIGHT stays 0, the GE fails for any
               positive setpoint, and SCH02_BGD_REFILL never asserts in state 5.
What the spec expects:
               Bag-dump refills SCH02 when selected (§7.6).
Evidence:      Grep for BGD01_WEIGHT: single read at line 1812, no writes.
Proposed fix:  Add MOVE(X01BGD01_LDC01.WT.Gross (or .Net), BLENDER_XFR.BGD01_WEIGHT) in
               X01BGD01_LDC01 rung 1, mirroring the SCH load-cell routines.
Confidence:    high.
```

```
ID:            BUG-07
Type:          bug
Location:      SPG_BLP_XFR rung 10, branch 2 (line 1921)
Severity:      functional
What the code does:
               Fault branch `XIC(Enabled) [STATES.4/5/6] XIO(TIMERS[1].DN)` resets the sequence
               to state 0 whenever the valves-in-position timer drops while conveying/purging.
               During the BLENDER_XFR state 3→4 handoff (dual-hopper campaign), CONVEY_CONFIG
               stays constant but the commanded hose-valve set changes (VLV09 closes, VLV07
               opens), so CONVEY_SCH_VALVES_OK necessarily drops during the swap, TIMERS[1]
               resets, and TRANS.10 aborts the whole sequence to state 0 mid-campaign instead of
               re-proving valves in state 2.
What the spec expects:
               Hopper-to-hopper switchover should re-position valves (state 2) — or purge first
               (Q3) — not fault-reset.
Evidence:      TIMERS[1] (line 1947) is conditioned on all three *_VALVES_OK bits; hose valve HA
               rungs are state-exclusive (BUG-03 evidence).
Proposed fix:  On loss of valve proof during convey, transition to purge or back to state 2
               (Position Valves) rather than hard reset — design with Q3. (Masked today by
               BUG-03/BUG-04, which abort earlier.)
Confidence:    medium-high — depends on resolution of BUG-03 for configs 3/6.
```

```
ID:            BUG-08
Type:          bug
Location:      SPG_BLP_XFR rungs 6, 10, 21 (lines 1909, 1921, 1945); UTILITY rung 0 (1980)
Severity:      functional (protections are dead logic)
What the code does:
               aa_conditions_stopping_xfr (TRANS.6 branch), aa_high_pressure_alm and
               aa_blower_aux_alm (TRANS.10 branches and the call-timer gate in rung 21) are
               never driven by any rung — those abort/permissive branches can never operate.
               aa_Ctrl_Power is unconditionally OTE'd TRUE, so the XIO(aa_Ctrl_Power) branch of
               TRANS.10 is also inert. The only live high-pressure protection is
               X01BLP01_PT.HIHIALM.A (timers 4/5 driving states 6/4). There is no blower-aux
               (X01BLP01_MCY) abort: a blower that fails to prove only raises the
               (permanently-latched, see BUG-13) MCY alarm but does not stop the sequence.
What the spec expects:
               High pressure and blower-failure handling per the state machine narrative
               (state 6 exists; TRANS.10 is the fault interrupt).
Evidence:      Grep: no OTE/OTL/MOVE writes any aa_* tag except aa_Ctrl_Power and aa_CALL_signal.
Proposed fix:  Either wire these to real conditions (aa_high_pressure_alm :=
               X01BLP01_PT.HIHIALM.A or the future aa_hi_press_switch DI; aa_blower_aux_alm :=
               X01BLP01_MCY.ALM.A) or delete the dead branches. Note the overlap: if
               aa_high_pressure_alm is tied to the same HIHI bit that drives TRANS.7→state 6,
               TRANS.10 (reset) and TRANS.7 (clear-HP state) race; the design must pick one
               responder. Flagged rather than resolved (new Q10).
Confidence:    high that the logic is dead; design intent needs the customer (Q10).
```

```
ID:            BUG-09
Type:          bug
Location:      SPG_BLP_XFR rung 28 (line 1964)
Severity:      functional (dead feature)
What the code does:
               Pause/Resume latches SPG_BLP_XFR.Paused, but no rung anywhere consumes .Paused —
               pausing has no effect on any state, timer, or device.
What the spec expects:
               (No explicit spec item; presumably pause should hold the convey state/feed.)
Evidence:      Grep: .Paused appears only in rung 28.
Proposed fix:  Either implement (e.g., hold airlock HA / freeze call timer while Paused) or
               remove the buttons. Needs customer intent.
Confidence:    high.
```

```
ID:            BUG-10
Type:          bug
Location:      SPG_BLP_XFR rung 13 (line 1930)
Severity:      functional (possible) / cosmetic (likely export artifact)
What the code does:
               `XIC(SPG_BLP_XFR.TRANS.08)` — Logix bit references do not take leading zeros; if
               the project literally contains a different bit than TRANS.8, the purge-done
               return to state 1 (TRANS.8, set by rung 8) would never be consumed.
What the spec expects:
               Purge complete → state 1 (Wait for Call).
Evidence:      Rung 8 sets TRANS.8; rung 13 reads "TRANS.08".
Proposed fix:  Verify in Studio 5000 that rung 13 references TRANS.8. If it's an export artifact,
               no change.
Confidence:    low that it's a real defect; flagged for verification.
```

```
ID:            DEV-03
Type:          spec-deviation
Location:      Valves rung 2 (line 72): XIC(X01SCH01_ZSC.MI) XIC(X01SCH05_ZSC.MI) in every config branch
Severity:      functional
What the code does:
               Requires BOTH scale-hopper dust valves closed (proof) during convey, for all
               configs — including the hopper that isn't conveying.
What the spec expects:
               §7.3 lists "active dust collection at ... scale bin" during transfer. The code's
               position is physically defensible (a pressure-conveying hopper must be sealed;
               the device routines open the dust valves during REFILL instead — X01SCH01 rung 4,
               X01SCH05 rung 4), but it contradicts a literal reading of §7.3, and requiring the
               IDLE hopper's dust valve closed will conflict with fill-while-feeding (Q1).
What the spec expects: see above.
Evidence:      X01SCH01/X01SCH05 rung 4 drive HA from the REFILL bits only.
Proposed fix:  None yet — flagged as new open question Q6.
Confidence:    high on what the code does; intent unresolved.
```

```
ID:            DEV-04
Type:          spec-deviation
Location:      Valves rungs 0-2 (lines 70-72); X01BFV02/04 rung 4 (lines 624/699)
Severity:      functional (minor)
What the code does:
               No VALVES_OK condition proves the active source's convey-air butterfly
               (X01BFV02/X01BFV04) OPEN — they are commanded via HOA.HA but never proofed before
               starting the blower. A stuck-closed butterfly dead-heads the blower and is caught
               only by the HIHI pressure alarm.
What the spec expects:
               Brief §5 derived table: convey butterfly open for active source (verify).
Evidence:      Rung 0 checks only BFV01/BFV03 CLOSED; rungs 1-2 don't reference BFV02/BFV04.
Proposed fix:  Add X01BFV02_ZSO.MI / X01BFV04_ZSO.MI (state-appropriate) to CONVEY_SCH_VALVES_OK.
Confidence:    high.
```

## B. Auto Mode / campaign, totalization, recipes

```
ID:            BUG-11
Type:          bug
Location:      RECIPE_MANAGEMENT rung 0 (line 1861)
Severity:      functional
What the code does:
               COP(BLENDER_XFR.RECIPES[BLENDER_XFR.RECIPE_INDEX], ...) executes every scan with
               no bounds check on RECIPE_INDEX. An HMI write outside the array range will major-
               fault the controller (indexed addressing fault).
What the spec expects:
               n/a (robustness).
Proposed fix:  Clamp/validate RECIPE_INDEX before the COP. (The whole routine is slated for
               rework per §8, but the fault risk exists today.)
Confidence:    high.
```

```
ID:            DEV-05
Type:          spec-deviation
Location:      RECIPE_MANAGEMENT rungs 1-4 (lines 1862-1865); BLENDER_XFR rung 2 (line 1782)
Severity:      functional
What the code does:
               CAMPAIGN_MATERIAL and the three CAMPAIGN_*_BAG_COUNT tags are overwritten from the
               active recipe EVERY scan — an operator-entered Material string (§7.4) is destroyed
               within one scan. Campaign accumulators (CAMPAIGN_WEIGHT, per-source weights,
               deltas) are cleared automatically on every auto-start (TRANS.1), so a mid-campaign
               Stop → Start zeroes the running totals instead of the §7.3 workflow (operator
               stops, records weight, resets totalizer, starts next campaign).
What the spec expects:
               §7.4: Material is an operator-entered verification string; Campaign Weight is
               view-only from a recipe card; the operator manages the recipe by counting bags.
Evidence:      Unconditioned MOVE rungs; CLR list in rung 2.
Proposed fix:  Part of the known recipe rework (§8). Keep totals across stop/start; clear only
               on an explicit operator "reset totalizer / new campaign" action. Resolve Q2 first.
Confidence:    high on behavior; rework already expected.
```

```
ID:            DEV-06
Type:          spec-deviation
Location:      BLENDER_XFR rungs 6, 7, 13 (lines 1795, 1798, 1812); X01BGD01_LDC01 (753-778)
Severity:      functional (clarification needed)
What the code does:
               The bag dump IS totalized: BGD bags are counted (BGD_BAGS_REMAINING), deltas
               accumulate into BGD_CAMPAIGN_WT, and a load cell X01BGD01_LDC01 exists.
What the spec expects:
               §4 refill table and §7.6: bag dump is "NOT totalized"; source-select chooses
               BBU (totalized) or bag dump (not totalized).
Evidence:      Rung 7 BGD branch: SUB bag count, ADD delta to BGD_CAMPAIGN_WT.
Proposed fix:  None yet — flagged as new open question Q7 (the scale-hopper delta totalization
               may be acceptable even if the BGD itself isn't a totalizing device).
Confidence:    high on code behavior; intent unresolved.
```

```
ID:            BUG-12
Type:          bug
Location:      BLENDER_XFR rung 10 (line 1806)
Severity:      functional (minor)
What the code does:
               BLENDER_XFR.NEXT_BAG (operator PB) gates TRANS.7 but is never unlatched by the
               PLC, unlike every other PB in this program (Start_PB/Stop_PB/Pause_PB/Resume_PB/
               SEQ_RST_PB are all OTU'd after use). If the HMI writes it maintained/latched, the
               machine will auto-advance through every subsequent refill without operator
               confirmation.
What the spec expects:
               Consistent momentary-PB handling.
Proposed fix:  OTU(NEXT_BAG) when TRANS.7 fires (match the rung-25 pattern). Verify HMI button
               type on the cMT3092X first.
Confidence:    medium (depends on HMI configuration, which is outside this export).
```

## C. Source devices / airlocks

```
ID:            BUG-13
Type:          bug
Location:      X01ALK03 rung 12 (line 210); compare X01ALK04 rung 12 (line 286)
Severity:      functional (SCH01 airlock never feeds in Auto)
What the code does:
               ALK03's CMD_SPD rung has Auto/Manual contacts inverted relative to ALK04:
               branch 1 `XIC(Auto_Mode) XIO(AR) XIO(HOA.HH) MOVE(0,CMD_SPD.MO)` and branch 2
               `XIO(Auto_Mode) XIC(HOA.HA) OTE(AR) MOVE(HA_SP,...)`. In Auto, branch 2 is false,
               so AR never asserts and branch 1 forces speed 0 every scan — the SCH01 convey
               airlock runs at 0 Hz during auto convey. ALK04's version (branch 2 gated
               XIC(Auto_Mode)) is the correct template.
What the spec expects:
               Airlock feeds at the auto setpoint (and eventually pressure±deadband per §7.5).
Evidence:      Side-by-side rung text, lines 210 vs 286.
Proposed fix:  Re-gate ALK03 rung 12 to match ALK04 (Auto→HA_SP branch with XIC(Auto_Mode);
               manual HH branch with XIO(Auto_Mode); zero branch without the mode contact).
Confidence:    high.
```

```
ID:            BUG-14
Type:          bug
Location:      X01ALK02 rung 1 (line 139); X01ALK02 rung 6 (145); X01ALK03 rung 6 (204);
               X01ALK04 rung 6 (280); X01ALK01 rung 1 (78)
Severity:      functional (minor) / consistency
What the code does:
               - ALK02 rung 1 is prefixed AFI() — the whole delay-timer rung is disabled
                 (leftover debug). Its .DN check in rung 6 is separately bypassed by an empty
                 parallel branch `[XIC(Delay_TMR.DN) ,]` (always true).
               - ALK03 rung 6 has the same empty-branch bypass; ALK04 rung 6 genuinely requires
                 Delay_TMR.DN. One of the two is wrong — the four airlock seal-purge solenoids
                 implement three different behaviors.
               - Delay-timer RES branches use ab_STATE_PLACE_HOLDER (never true) in ALK01/03/04.
What the spec expects:
               Consistent seal-purge behavior across airlocks (TOF on M.MO gives run + post-stop
               purge; the bypass extends purge to the whole HA window).
Proposed fix:  Pick one behavior (recommend the ALK04 pattern: TOF-based run/post-purge), remove
               AFI and empty branches, replace placeholder resets with the intended state
               condition or delete.
Confidence:    high on the inconsistency; medium on which behavior is intended.
```

```
ID:            BUG-15
Type:          bug
Location:      X01BBU01_YI rung 3 (line 381); X01BBU02_YI rung 3 (459); X01SCH04 rung 3 (1140);
               X01SCH08 rung 3 (1275)
Severity:      functional
What the code does:
               BBU bag agitators and both scale-hopper solimar pad groups have their Auto branch
               gated on ab_STATE_PLACE_HOLDER (never true) — none of them ever run in Auto.
What the spec expects:
               BBU paddle agitation during bag discharge (§4 refill table); solimar pads to
               promote flow during convey/refill (exact policy unconfirmed — included in Q4/Q11
               scope below).
Proposed fix:  Drive HOA.HA: agitators from SCHxx_REFILL (matching X01ALK01/02 rung 7); solimar
               pads from the respective convey state (e.g., BLENDER_XFR.STATES.3 + SPG state 4)
               — confirm policy first.
Confidence:    high that they never run; medium on intended trigger conditions.
```

## D. Alarm / template defects (multiple devices)

```
ID:            BUG-16
Type:          bug
Location:      X01BLP01 rung 5 (line 851); X01ALK01_ZS r3 (119); X01ALK02_ZS r3 (178);
               X01ALK03_ZS r3 (254); X01ALK04_ZS r3; X01BBU01_AA r3 (359); X01BBU02_AA r3 (437);
               X01BBU01_ZS r3 (410); X01BBU02_ZS r3 (488); X01VLV07_ZS r3 (1441);
               X01VLV08_ZS r3; X01VLV09_ZS r3; X01VLV10_ZS r3
Severity:      functional (permanent nuisance alarms)
What the code does:
               In all listed rungs the alarm TON has NO input condition — the timer runs from
               first scan, ATMR.DN latches true after ATMR_SP, and ALM.A then seals in
               permanently via the `[XIC(ATMR.DN) ,XIC(A) XIO(Reset_Ack)] OTE(A)` branch.
               Compare the correct template (e.g., X01ALK01 rung 9, X01BBU04 rung 6) where the
               TON is gated by a discrepancy condition.
What the spec expects:
               Alarms gated by a real fault condition (proof mismatch, hose disconnected while
               required, bag-empty during refill, etc.).
Evidence:      Rung text: `[[MUL(...) ,TON(ATMR,?,?)] ,[XIC(ATMR.DN) ,...] OTE(ALM.A)]` with no
               leading contact.
Proposed fix:  Define and add the trigger condition per device (e.g., VLVxx_ZS: required path
               selected but switch not made; BBU_AA: bag empty while refill active; BLP01_MCY:
               MO/MCY mismatch). List of intended conditions to be confirmed in Phase 2.
Confidence:    high that the rungs latch permanently as written; the intended conditions are a
               design question.
```

```
ID:            BUG-17
Type:          bug
Location:      X01BGD01_LDC01 rungs 8-10 (lines 767-769)
Severity:      cosmetic/functional-minor
What the code does:
               Rung 9 compares WT.Gross against High_TMR_SP (a TIMER setpoint, seconds) instead
               of a weight setpoint — unit mismatch; rungs 8 and 10 are exact duplicates (Low_TMR
               driven twice).
What the spec expects:
               High timer driven by GT(WT.Gross, HITOLALM.SP) per the SCH LDC template (line 966).
Proposed fix:  Replace High_TMR_SP with HITOLALM.SP in the comparison; delete duplicate rung 10.
Confidence:    high.
```

```
ID:            BUG-18
Type:          bug
Location:      X01BGD02 rung 3 (line 787)
Severity:      cosmetic/functional-minor
What the code does:
               Manual branch is `XIC(HOA.HH)` without the template's XIO(Auto_Mode) — a manual
               HH command actuates the bag-dump dust valve even in Auto mode.
Proposed fix:  Add XIO(X01BGD02.Auto_Mode) to the HH branch per template.
Confidence:    high.
```

```
ID:            BUG-19
Type:          bug
Location:      UTILITY rung 13 (line 1996); Panel_1_DI rungs 57-58 (lines 2092-2093)
Severity:      cosmetic (sim-only)
What the code does:
               In simulation, CUST_INTERLOCK requires X01BDR01/02_ZS_ZSC.SIM.MI, but no routine
               exists for the BDR_ZS devices (they are tags only, not in the Devices Mainroutine
               JSR list), so nothing drives SIM.MI and the call signal can never assert in sim
               without a manual tag write.
Proposed fix:  Drive the BDR ZS SIM bits (e.g., enable when a blender is selected), or document
               the manual write needed for sim testing.
Confidence:    high.
```

```
ID:            BUG-20
Type:          bug (cosmetic)
Location:      Tag CSV lines 41-54; X01SCH02_LS description (line 125-126)
Severity:      cosmetic
What the code does:
               X01ALK03/X01ALK04 tag descriptions read "BBU1/BBU2 AIRLOCK" (copied from
               ALK01/02) though they are the SCH discharge convey airlocks. X01SCH02_LS is
               described "BBU2 LEVEL SWITCH" though it is the SCH02 high-level switch (the
               "BBU1/BBU2" naming is used loosely for the two hopper trains throughout).
Proposed fix:  Description cleanup pass.
Confidence:    high.
```

## E. Stub confirmations (per brief §8 — develop, not bugs)

```
ID:            STUB-01
Type:          stub
Location:      SPG_CIP routine (line 1973); X01BFV01/03 (no HA rungs); X01SCH03/07 (no HA rungs);
               X01VLV01/02 (no HA rungs); CIP_MODE tag (SPG_CIP type, CSV line 17)
Severity:      functional
What exists:   Only the tag/type scaffold (CIP_MODE : SPG_CIP) and the CIP-only devices with
               template Auto/Manual rungs but no auto-call conditions: line drains BFV01/BFV03,
               air-dry valves SCH03/SCH07, blender CIP diverters VLV01/VLV02 ("(WIP)" in tag
               descriptions). The SPG_CIP routine body was not flattened in this export — request
               a separate export before Phase 2; assume empty/minimal.
Missing vs spec:
               §7.7/7.8 entirely: water + drying matrices, flush-time setpoints, blender-vessel
               start/stop mode, min-scale-bin-weight interlock before CIP, auto drain-open after
               flush, valve positioning per selection (CIP table attachment defines the matrix —
               Q4 confirms valve lists), dust-collector high-level popup (§7.5 — no level switch
               tag exists for X02FLT01 at all, so this likely also needs an IO addition).
Confidence:    high.
```

```
ID:            STUB-02
Type:          stub
Location:      X01ALK03/04 CMD_SPD rungs (lines 210/286)
Severity:      functional
What exists:   Fixed-setpoint speed (HA_SP / HH_SP) only.
Missing vs spec:
               §7.5 target convey pressure ± deadband modulation of airlock VFD frequency from
               X01BLP01_PT. No pressure-control logic exists anywhere.
Confidence:    high.
```

```
ID:            STUB-03
Type:          stub
Location:      BLENDER_XFR state 1 + rungs 11-13 (lines 1786, 1808-1812)
Severity:      functional
What exists:   Both selected hoppers fill simultaneously in state 1; convey is strictly
               sequential (state 3 then 4); refill happens only in state 5 with convey stopped
               (SPG Enabled is unlatched on STATES.5 — see BUG-04).
Missing vs spec:
               The customer note suggests one-at-a-time fill with the second hopper filling
               WHILE the first feeds (Q1). Note: fill-while-feeding will also collide with
               Valves rung 0/2 requirements (inlet valves and idle-hopper dust valve must be
               closed during convey) — flag for the Q1 design discussion.
Confidence:    high.
```

## F. Open questions (brief Q1-Q5 retained; new items added)

- **Q1 (fill strategy)** — unresolved. Current code: both hoppers fill up front (state 1), refill
  only with convey stopped. Fill-while-feeding additionally conflicts with `Valves` rung 0
  (X01SCH02/06_ZSC required closed during convey) and rung 2 (idle hopper dust valve closed) —
  these proofs must change if Q1 resolves to fill-while-feeding.
- **Q2 (recipe/bag-count/totalizer interaction)** — unresolved; see DEV-05. Today the recipe
  overwrites the operator fields each scan and totals auto-clear at start.
- **Q3 (empty-weight handoff / purge-then-switch)** — unresolved; gates the fixes for BUG-04 and
  BUG-07. Today there is no purge between hoppers and no completed purge at all.
- **Q4 (CIP valve matrix)** — unresolved; CIP table attachment lists the six selectable items
  (Scale Bin1/2 flush-time, Blender7/8 convey line flush-time, Blender7/8 vessel start/stop) but
  not the valve lists per item.
- **Q5 (proof-of-connection interlock policy)** — unresolved; see DEV-01. Note the existing
  VLV07-10 `_ZS` inputs already behave as hose-connected proofs at the switching station (code
  comments say "HOSE CONNECTED"; HMI shows a "Valve Switch Connections" legend); the new switches
  are at the blender pinch valves. Define behavior when a new switch is absent/not yet wired.
- **Q6 (new)** — Scale-bin dust valves during convey: code requires them CLOSED (proofed) during
  convey and opens them only during refill; §7.3 says "active dust collection at scale bin."
  Which is intended? (DEV-03)
- **Q7 (new)** — Bag-dump totalization: spec says NOT totalized, code totalizes BGD bags and
  weight via the scale-hopper delta and has a BGD load cell. Confirm intent. (DEV-06)
- **Q8 (new)** — Bag-count semantics: does the recipe count include the initial state-1 fill, or
  only refills? Determines the BUG-05 fix shape (off-by-one + last-bag handling).
- **Q9 (new)** — For dual-hopper configs (3/6): should the inactive hose path be commanded closed
  during the other hopper's convey (current per-valve logic, matches P&ID 1-source-at-a-time), with
  the `Valves` proof rung made state-aware (BUG-03)? Assumed yes pending confirmation.
- **Q10 (new)** — High-pressure response ownership: state 6 (clear-HP, from PT HIHI) vs TRANS.10
  reset (from the never-driven aa_high_pressure_alm) vs purge-on-call-loss (rung 21 gate). Which
  single behavior does the customer want when HIHI trips? (BUG-08)
- **Q11 (new)** — What is X01FAN01 ("PRESSURE DILUTE FAN") physically, and what is its run policy?
  It interlocks the blower (X01BLP01 rung 2) but has no auto-start logic (BUG-02). P&ID review
  suggests it is part of the convey-air train; confirm start order and whether it should run for
  CIP drying too.
- **Q12 (new)** — Dust-collector high level (§7.5 popup): no level switch input or tag exists for
  X02FLT01. Is a new DI planned alongside the §7.2 card change?

---

## Suggested Phase 2 priority (pending your approval per item)

1. BUG-02 (blower/fan auto start) — nothing runs without it.
2. BUG-13 (ALK03 speed rung) — SCH01 never feeds.
3. BUG-03 + Q9 (dual-config valve proof) — configs 3/6 unusable.
4. BUG-05/BUG-06 + Q8 (bag counting, BGD weight move) — campaign completion.
5. BUG-04 + Q3 (purge completion) — spec 7.6.
6. BUG-16 (always-on alarm rungs) — commissioning noise that will mask real faults.
7. DEV-01/DEV-02 + Q5 (proof-of-connection, dust fan proof) — when hardware lands.
8. Stubs (CIP, recipe, pressure control) per §8 after the above.
