# Sonoma — Named Manoeuvres & Signature Moves

**Compiled 2026-04-28; rewritten 2026-04-28 with stricter source attribution.**

This is the *vocabulary layer* on top of the existing Sonoma intelligence — the named moves, signature techniques, and idiomatic phrases drivers and coaches use at Sonoma. The repo already contains [`sonoma_track_intelligence.md`](sonoma_track_intelligence.md) (per-corner brake refs and technique tips), [`trod_sonoma_session.md`](trod_sonoma_session.md) (a verbatim T-Rod coaching transcript), and [`markers.md`](markers.md) (16 named landmark markers).

## Methodology — what counts as "Sonoma-specific"

After an internal audit on 2026-04-28, this doc separates content into three parts so the coaching system never confuses Sonoma vocabulary with generic driving advice:

- **Part A — Sonoma-specific.** A manoeuvre or term is in Part A only if a source whose **title or page-level subject is Sonoma** directly attributes it to Sonoma. Examples: a Blayze article titled *"Sonoma Raceway Turn 11"* counts; a generic forum thread on cold-weather track driving does not, even when its advice would apply at Sonoma.
- **Part B — Universal driving principles applied to Sonoma corners.** Techniques that come from Bentley's pedagogy or T-Rod's general voice and are clearly applicable at a specific Sonoma corner, but the source doesn't name them as Sonoma-specific. Coaching may use these — but the system prompt should not claim Sonoma authorship.
- **Part C — Synthesized / inferred.** Framings that the previous compilation introduced as plausible Sonoma patterns but cannot be sourced. Kept here for transparency; should not feed the coach until a Sonoma source confirms them.

The audit also dropped one cited source as off-target — see Part D at the end of this doc.

---

# Part A — Sonoma-specific named manoeuvres

Every item in this section traces to a source whose subject is Sonoma. Quotes are verbatim where possible.

## A.1 Passing manoeuvres

### T11 dive bomb (the canonical Sonoma move)

T11 is **"Calamity Corner"** — the 180° hairpin onto the front straight ([Sonoma Raceway media](https://www.sonomaraceway.com/business/turn-11/), [Sonoma Raceway news on NASCAR layout](https://www.sonomaraceway.com/media/news/sonoma-nascar-track-layout-why-challenges-even-best.html)). It is the canonical late-race passing zone. The Press Democrat reports drivers will *"bomb you all day long down there if there's a shot at it"* ([Press Democrat — Terror on Turn 11](https://www.pressdemocrat.com/article/news/nascar-at-sonoma-terror-on-turn-11/)).

Shape of the move: come in deep on the inside-left under heavy braking, force the defender to lift, take the apex from the outside-running car, exit wide to the right.

The defining failure mode is **"running into the back of other cars"** because of the heavy brake demand ([Sonoma Raceway news on NASCAR layout](https://www.sonomaraceway.com/media/news/sonoma-nascar-track-layout-why-challenges-even-best.html)). Historical reference incidents documented at [NASCAR.com — Big moments in Turn 11 at Sonoma](https://www.nascar.com/gallery/big-moments-in-turn-11-at-sonoma-raceway/): Rudd vs Allison 1991 (5-second penalty), Gordon vs Truex 2009, Stewart vs Vickers 2011.

### T7 "diamond" / over-and-under

The track's *other* passing zone. T7 is preceded by hard braking after the long Chute. The move turns Turn 7 into a "diamond" — bring entry speed deep into the corner, get the left-side tires onto the white line, and *"only pick up the throttle after you have rotated the car and heading towards the second apex"* ([Racers360 — One Corner Analysis: Sonoma Turn 7](https://racers360.com/racecar-driver-education/one-corner-analysis-sonoma-turn-7/)).

Dion von Moltke's exact phrasing: *"Hard braking here, and late turn in and late apex … Open your hands as early as possible"* ([Blayze — One Corner Analysis: Sonoma Turn 7](https://blayze.io/blog/car-racing/one-corner-analysis-sonoma-turn-7)).

The pass is set up by going deeper on the brakes than the defender, sacrificing the first apex, getting a better second apex, and using all the road on exit. Both source articles are titled and centered on Sonoma's Turn 7.

## A.2 Recovery manoeuvres

### T11 over-cooked entry — trail-brake all the way to apex

The canonical save at Sonoma. Blayze's Sonoma T11 article is explicit: *"make sure you are trail braking all the way down to the apex"* ([Blayze — Sonoma Raceway Turn 11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11)). The instinct is to dump the brake and try to rotate; that gives understeer that ends in the wall. Hold light brake, keep the nose loaded, scrub speed via the trail to the third tire stack.

This is the single most useful recovery prompt the coach can fire on a T11 entry that's gone wrong: *"Over-cooked? Stay on the brake."*

### T11 exit oversteer — check early throttle

If the rear steps out past the T11 apex, [Blayze](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11) names the cause: *"picking up initial throttle too early"* creates snap oversteer. Recovery word: *"ease, don't lift"* — abrupt lift transfers weight forward and makes it worse.

### T9A chicane bail-out (architecture-level)

The Turn 9A chicane was widened by 10 feet in 2012 to provide adequate runoff for non-NASCAR series ([RacingCircuits.info — Sonoma Raceway](https://www.racingcircuits.info/north-america/usa/sonoma-raceway.html)). The architectural intent of the chicane is the bail-out — when a club car has nowhere to go after over-cooking T9, the chicane is the route. Coaching prompt for novice HPDE drivers: *"if you've lost it through 9, take the chicane, don't fight."*

## A.3 Hustle areas

The general hustle principle ("100 % throttle for even a fraction of a second is recoverable lap time") is a universal Bentley/T-Rod idea — see Part B. But Sonoma sources name specific zones where it applies:

### T8A apex commitment

*"By the time you get to the apex of Turn 8A, you should be at or near full throttle. Let the car out as you crest the hill and get all the way to the exit curbing on the left side of the track"* ([NASA Speed News — One Lap Around Sonoma Raceway](https://nasaspeed.news/columns/driver-instruction/one-lap-around-sonoma-raceway/), accessed via search-engine excerpt; direct fetch returned 403).

### T9 → T10 full-throttle setup

*"Exit Turn 8a at full throttle"* ([Kanga Motorsports — Sonoma track notes](http://www.kangamotorsports.com/track-notes)) into a T10 that is a *"lift, don't brake"* corner ([Kanga](http://www.kangamotorsports.com/track-notes), reaffirmed in our T-Rod transcript). The T9 → T10 sequence is the longest unbroken full-throttle stretch on a clean lap — staying at 100 % through T9 because T10 only needs a lift is the named hustle pattern.

### T5 throttle breath (the *non-hustle* zone)

*"Generally a flat or close to flat-out corner for most cars where you breathe the throttle a little bit"* ([lapmeta — Sonoma Raceway track guide](https://lapmeta.com/en/blog/track-guide-sonoma-raceway), via search excerpt; direct fetch returned 403). Naming this explicitly matters because the coach should *not* fire a hustle prompt at T5 — it'd be wrong. *"T5 is throwaway, save T6."*

## A.4 Trail-brake variants per Sonoma corner

The general T-Rod rule (*"roll the brake to the apex, peak then taper, off-brake at maximum-grip mid-corner"*) is universal — see Part B. The per-Sonoma-corner variants are named in Sonoma sources:

### T11 — *very slow* trail to the apex

*"Maintain very slow trail brake all the way down there. No initial throttle before apex point"* ([Blayze — Sonoma Raceway Turn 11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11)). The most aggressive trail-brake corner on the lap.

### T7 — hard initial brake + late-released trail

*"Braking around 300 board. Hard braking here, and late turn in and late apex"* ([Blayze — Sonoma Turn 7](https://blayze.io/blog/car-racing/one-corner-analysis-sonoma-turn-7)). The trail isn't as long as T11 because T7 has a short brake zone, but the late release is essential to the diamond shape.

### T4 — trail-and-rotate

*"Brake early, get the car slowed down and move the weight balance to the rear as you turn-in"* ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway), via search excerpt). Downhill, off-camber. The trail keeps weight on the front so the off-camber doesn't fight the steering.

### T3 — light trail (the give-away)

T3 is *"a give-away turn. You will sacrifice a little speed to gain more speed through Turn 3A and down into Turn 4"* ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway), via search excerpt). The trail is light, the corner is taken patiently. *"Light lift or left-foot brake before turn-in"* ([Kanga](http://www.kangamotorsports.com/track-notes)).

### T2 — minimal-trail uphill

*"You can brake less than you think and carry speed as you head uphill"* ([Kanga](http://www.kangamotorsports.com/track-notes)). The uphill scrubs speed for free; the trail is barely there.

## A.5 Curb-use signature moves

### T6 Carousel apex curb

*"Apex the inside berm and get a smooth exit"* ([Kanga](http://www.kangamotorsports.com/track-notes)). The curb compensates for the off-camber, which would otherwise push the car wide. Trent Hindman's pole-winning onboard at Sonoma in the Acura NSX GT3 Evo shows the canonical apex-curb hit at T6 ([Sportscar365 — Sonoma Onboard with Acura's Trent Hindman](https://sportscar365.com/videos/sonoma-onboard-with-acuras-trent-hindman/), [YouTube](https://www.youtube.com/watch?v=Mc87KzZypic)).

### T11 third-tire-stack apex + all-the-road exit

Two named curb moves at T11, both from [Blayze — Sonoma Raceway Turn 11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11):

- **Apex**: *"Apex the third tire stack … If you are getting onto the painted curb more than a length before the tire stack you are in too early."* The third stack is the canonical Sonoma reference.
- **Exit**: *"Use absolutely all of the road on exit to maximize our exit speed."* All-the-road-on-exit is non-negotiable here because T11 is the highest exit-speed-leverage corner on the lap.

### T8 apex-curbing on driver's left + T8A exit-curb-left

*"Smooth yet quick turn-in getting the car to the apex curbing on drivers left … By the time you get to the apex of Turn 8A, you should be at or near full throttle. Let the car out as you crest the hill and get all the way to the exit curbing on the left side of the track"* ([NASA Speed News — One Lap Around Sonoma Raceway](https://nasaspeed.news/columns/driver-instruction/one-lap-around-sonoma-raceway/), via search excerpt; direct fetch returned 403). The esses sequence has *two* named curbs: T8 inside, T8A exit-left.

### T10 left berm + Toyota sign visual

*"Run over left berm, use Toyota sign letters as visual guide"* ([Kanga](http://www.kangamotorsports.com/track-notes)). Aggressive berm-use at T10 is part of the lift-don't-brake move — committing to the inside means trusting the berm. The Toyota sign letters are the visual reference.

### T7A apex curb — the diamond shape's throttle reference

*"Start your apex and initial throttle where the apex curb starts. Trying to commit to full throttle by the end of that apex curb"* ([Racers360 — Sonoma Turn 7](https://racers360.com/racecar-driver-education/one-corner-analysis-sonoma-turn-7/)). The apex curb at T7A *is* the throttle reference.

## A.6 Setup-for-next-corner manoeuvres

### "Open up nine, straight shot to ten" (T-Rod)

The most-cited Sonoma transition. Quoted verbatim in [`trod_sonoma_session.md`](trod_sonoma_session.md): *"If we open up nine a little bit, we can get a straight shot into 10. That means that when we approach 10, we're not going from less steering to right steering angle — we're going straight to right."* T-Rod's coaching session was at Sonoma, so this is Sonoma-attributed — though the underlying principle is universal, the named application is Sonoma's.

### T3 → T3A → T4 "give-away" sequence

Three corners as one decision: T3 is given away, T3A is rotated late, T4 is the destination. *"Compromise Turn 3 exit for good Turn 3a exit"* ([Kanga](http://www.kangamotorsports.com/track-notes)). *"Turn in very late and end up far at track left and parallel to the track for a split second. Be patient with your turn-in for 3A. Carry speed over the crest and power down to Turn 4"* ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway), via search excerpt).

The named rule: **sacrifice T3, win T4.**

### T5 → T6 "throwaway" rule

T5 is throwaway speed — preserve T6 entry. From the same lapmeta article (*"breathe the throttle a little bit and keep it as tight and right as your car will allow around the bend to set up Turn 6"*).

### T8 → T8A → T9 "no-lift" sequence

*"A common mistake is to go into Turn 8 too hot, having to lift between 8 and 8A, which kills exit speed through Turn 9"* ([NASA Speed News — One Lap Around Sonoma Raceway](https://nasaspeed.news/columns/driver-instruction/one-lap-around-sonoma-raceway/), via search excerpt). Rule: enter T8 at the *exact* speed you can hold all the way through T8A apex without lifting. If you have to lift, you went in too hot.

## A.7 Track-architecture context (manoeuvre-relevant)

### "The Chute" (NASCAR-only architecture)

890-foot stretch between Turns 4 and 7 created in 1998 specifically for NASCAR ([RacingCircuits.info — Sonoma Raceway](https://www.racingcircuits.info/north-america/usa/sonoma-raceway.html)). NASCAR cars bypass the Carousel via the Chute. **Club drivers and HPDE use the full 12-turn long course; the Chute is not a club move.** Worth flagging in the system-prompt lore so the coach doesn't fire NASCAR-bypass advice for an M3 driver running the long course.

### Repaved surface (February 2024)

Sonoma's full 12-turn 2.52-mile circuit underwent its first full repave in 23 years during the 2024 offseason ([NASCAR.com — Drivers offer feedback on Sonoma repave at Goodyear test](https://www.nascar.com/news-media/2024/03/28/drivers-offer-feedback-on-sonoma-repave-at-goodyear-test-a-whole-new-ballgame/), [Jayski — Goodyear tire test at repaved Sonoma Raceway](https://www.jayski.com/2024/03/27/goodyear-tire-test-at-repaved-sonoma-raceway/), [SpeedSF — Sonoma's recent repave helps set new records](https://www.speedsf.com/blog/2024/3/20/after-sonomas-repave-our-best-post-new-records)). Drivers were *"routinely putting down laps 2.5 seconds faster than the track record."* Josh Berry: *"a lot more grip."* Implications:

- Any reference dataset captured pre-2024 has *materially lower grip* than the current surface.
- Brake-point and apex-speed gold standards from pre-2024 may be slow by ~2.5 s per lap on the repaved surface for similar cars.
- *"Dirty off-line"* is more pronounced on the new surface — the rubbered groove is narrower until enough laps run ([NASCAR.com](https://www.nascar.com/news-media/2024/03/28/drivers-offer-feedback-on-sonoma-repave-at-goodyear-test-a-whole-new-ballgame/)).
- **Implication for `data/reference/sonoma_gold.json`**: source-file date matters. Pre-2024 reference = "achievable on the old surface"; 2024+ field tests should use a repave-era reference if available. This fact is now baked into `src/pitwall/features/sonoma.py:SURFACE_HISTORY` and the system-prompt lore.

## A.8 Named driver-error patterns (Sonoma-cited)

### "T4 brake-late"

The single most-named error at Sonoma. *"Most drivers brake too late for Turn 4"* ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway), via search excerpt). Coaching response: *"back the brake up by one marker"* (already in our enrichment).

### "T6 throttle-too-early"

The off-camber Carousel *"punishes early throttle application"* ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway), via search excerpt). Snap oversteer or wide push depending on the car.

### "T11 dive-bomb gone wrong"

The defining incident at Sonoma — defined by [NASCAR.com](https://www.nascar.com/gallery/big-moments-in-turn-11-at-sonoma-raceway/): the dive-bomb that lands too late, with the inside car running into the back of the defender. In club racing the equivalent is over-cooking entry while trying to set up the pass.

### "Crabbing into T11"

Specific name, specific failure mode. From [Blayze — Sonoma Raceway Turn 11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11): the car *"drifts towards the inside of the corner before the turn in point,"* forcing the driver to turn from the middle of the track rather than the outside edge. Coach response: *"be all the way out to the left at the start of the tire stacks; do not crab in early."*

### "T8 too hot, lift between T8 and T8A"

*"A common mistake is to go into Turn 8 too hot, having to lift between 8 and 8A, which kills exit speed through Turn 9"* ([NASA Speed News — One Lap Around Sonoma Raceway](https://nasaspeed.news/columns/driver-instruction/one-lap-around-sonoma-raceway/), via search excerpt). The entry speed at T8 is the variable to dial, not the line.

---

# Part B — Universal driving principles applied to Sonoma corners

Items in this section come from general driving pedagogy (Bentley's *Performance Driving Illustrated*, T-Rod's voice, universal cold-tire HPDE practice). They apply at Sonoma but are not Sonoma-named. The coach can voice these with confidence; the system prompt should not claim Sonoma authorship for them.

## B.1 The hustle principle (general)

T-Rod's universal phrasing in the recorded coaching session: *"60% throttle is only 20 ft-lbs less than 100% — just go 100"* ([`trod_sonoma_session.md`](trod_sonoma_session.md)). The principle is universal driving advice; the *Sonoma-named applications* (T8A apex commitment, T9 → T10) live in Part A.

## B.2 The "smooth is fast" trail-brake rule

T-Rod again: *"roll the brake to the apex, peak then taper, off-brake at maximum-grip mid-corner."* Universal Bentley pedagogy (PDF p32–33). The Sonoma-specific *variants* per corner live in Part A.4; the *rule itself* is universal.

## B.3 Off-throttle understeer correction

If a corner develops mid-corner understeer, ease throttle, wait for weight transfer, re-apply steering as the car settles. Bentley *Performance Driving Illustrated* p11. Often surfaces at T6 because the off-camber Carousel amplifies the failure mode, but no Sonoma source names it as a Sonoma manoeuvre.

## B.4 Late-session tire-degradation pace

Late-session pace drops with tire wear; *"smoothness > aggression in the last stints"* — already in T-Rod's general voice. No Sonoma-specific degradation profile in public sources beyond this universal advice.

## B.5 Cold-tire HPDE warm-up

Standard HPDE practice for cold mornings: gradual out-laps, conservative cold-tire pressures, build pace across the first 3-5 laps. This applies *whenever* it's a cool morning at any track — including Sonoma's morning fog phase. It is NOT a Sonoma-specific manoeuvre, despite the previous version of this doc citing a Track Mustangs forum thread for Sonoma's fog. (See Part D below.)

## B.6 Bentley's reference points

Turn-in / apex / exit reference points; "look ahead, look where you want to go" ([Bentley PDF p5](Performance-Driving-Illustrated-2-23-24.pdf)). Universal — applied at every Sonoma corner.

---

# Part C — Synthesized / inferred (use with care)

Items in this section are framings the previous compilation introduced that **cannot be sourced to a Sonoma article**. They are plausible patterns derived from Sonoma-adjacent material, kept here for transparency. They should NOT feed the coach's Sonoma system prompt until a Sonoma source confirms them.

| Synthesized claim | What we actually have | Why it didn't make Part A |
|---|---|---|
| **T4 inside-line passing move** | lapmeta calls T4 the *"most-mistimed brake zone"* — implies an opportunity exists | No Sonoma source names this as a passing move. The previous compilation acknowledged: *"Most sources don't call this a named pass."* |
| **T2 late-brake passing move** | Kanga describes the T2 cornering line; Bentley describes uphill scrub effect | No Sonoma source names a T2 pass. Synthesised by inverting the cornering line into a passing scenario. |
| **T6 carousel "patience pass"** | lapmeta says T6 *"punishes early throttle"* | No Sonoma source names a "patience pass" framing. Synthesised. |
| **T1 "for an M3, brief lift is the right answer"** | lapmeta says *"this is where most cars will make a speed correction — for some of the faster cars this might be a brake, for others a lift"* | The lapmeta quote is car-agnostic. The M3-specific interpretation is the previous compilation's. |
| **"T5 false hustle" error pattern** | T5 is a documented throwaway corner | No source names *"false hustle"* as an error pattern. Plausible derivative, not cited. |
| **"T2 over-brake on the climb" error pattern** | Kanga's *"you can brake less than you think"* implies the error | The error is named *implicitly* by inverting the technique. Not directly named in any Sonoma source. |
| **Wet-line offset (camber-driven)** | T4 and T6 are off-camber | No Sonoma source documents Sonoma's wet line. Inferred from camber geometry. The previous compilation flagged this as *"inferred, not cited."* |

The coaching system can use Part C content as *hypotheses for future field-test confirmation*, not as canonical pace-note vocabulary.

---

# Part D — What was dropped and why

The previous version of this document (compiled earlier on 2026-04-28) cited [Track Mustangs forum — Cold Weather Track Advice](https://trackmustangsonline.com/threads/cold-weather-track-advice.15474/) under "Morning fog & cool-tire warm-up routine." On audit, the forum thread is **about cold-weather track driving in general, not Sonoma**. Quotes like *"first 4 laps felt like ice"*, *"+2 psi cold setting"*, and *"R-compound tires above 50°F"* are universal cold-tire advice attributed to no specific track.

Sonoma's morning fog pattern is a real and well-documented phenomenon ([AccuWeather — Sonoma Raceway forecast](https://www.accuweather.com/en/us/sonoma-raceway/95476/weather-forecast/35265_poi)). The pattern itself is Sonoma-specific (see `src/pitwall/features/sonoma.py:WEATHER_PHASES`), but the *quoted forum content* is not.

Action taken: the cold-weather forum citation has been removed. The Sonoma-fog-specific framing now lives in `src/pitwall/features/sonoma.py:WEATHER_PHASES["morning_fog"]` with the coaching note *"First session of the day — surface is cool and possibly damp. Build pace gradually; T6 carousel and T11 hairpin grip is below normal."* Part B.5 above acknowledges generic cold-tire HPDE practice as a universal principle, not a Sonoma manoeuvre.

---

# Carousel naming convention — resolution

[Wikipedia — Sonoma Raceway](https://en.wikipedia.org/wiki/Sonoma_Raceway) calls the Carousel the entire **T4 through T6 banked complex**. Most coaching sources (Kanga, lapmeta, T-Rod, our existing markers schema) call **T6 alone** the Carousel.

This repo follows the coaching-source convention: **T6 = the Carousel**. The Wikipedia reading is noted as historical / architectural context but is not the operating definition for the Pitwall coaching system. Anyone editing the system prompt or markers should keep this convention.

---

# Sources audit

This table makes the Part A / B / C split visible at the source level. "Sonoma-titled?" means the URL or article title explicitly references Sonoma; "Used for" tells you which named manoeuvres each source actually attributes.

| Source | Sonoma-titled? | Used for |
|---|---|---|
| [Sonoma Raceway news — NASCAR Track Layout Why Challenges](https://www.sonomaraceway.com/media/news/sonoma-nascar-track-layout-why-challenges-even-best.html) | Yes | T11 = "Calamity Corner"; dive-bomb culture; T7+T11 as the only real passing zones |
| [Sonoma Raceway — Turn 11](https://www.sonomaraceway.com/business/turn-11/) | Yes | Confirms Calamity Corner naming |
| [NASCAR.com — Big moments in Turn 11 at Sonoma](https://www.nascar.com/gallery/big-moments-in-turn-11-at-sonoma-raceway/) | Yes | Incident vocabulary; Rudd-Allison 1991, Gordon-Truex 2009, Stewart-Vickers 2011 |
| [Press Democrat — NASCAR at Sonoma: Terror on Turn 11](https://www.pressdemocrat.com/article/news/nascar-at-sonoma-terror-on-turn-11/) | Yes | "bomb you all day long" |
| [Blayze — The Racing Line, Turn 11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11) | Yes (Sonoma T11) | Bump reference, third tire stack apex, all-the-road exit, crabbing error, over-cooked-entry recovery, "very slow trail to apex" |
| [Blayze — One Corner Analysis: Turn 7 (Dion von Moltke)](https://blayze.io/blog/car-racing/one-corner-analysis-sonoma-turn-7) | Yes (Sonoma T7) | 300 board, late turn-in/late apex, "open your hands as early as possible" |
| [Racers360 — One Corner Analysis: Sonoma Turn 7](https://racers360.com/racecar-driver-education/one-corner-analysis-sonoma-turn-7/) | Yes (Sonoma T7) | "Diamond" shape, double-apex strategy, white line entry, throttle reference at apex curb |
| [Kanga Motorsports — Track Notes (Sonoma)](http://www.kangamotorsports.com/track-notes) | Yes | T1 K-wall, T2 bridge, T3 give-away + light poles, T4 wall step, T6 crest + tire stacks, T7 300 board, T8a esses, T9→T10 setup, T10 Toyota sign + left berm, T11 pit-entry lines |
| [lapmeta — Track Guide: Sonoma Raceway](https://lapmeta.com/en/blog/track-guide-sonoma-raceway) | Yes | T1 speed correction, T3 give-away, T4 "back up one marker", T5 throttle breath, T6 carousel off-camber, T11 bump reference, T8/T8A common error. *Note: direct fetch returned 403; quotes via search-engine excerpts only.* |
| [NASA Speed News — One Lap Around Sonoma Raceway](https://nasaspeed.news/columns/driver-instruction/one-lap-around-sonoma-raceway/) | Yes | T8/T8A "no-lift" sequence, T8A apex full-throttle commitment. *Note: direct fetch returned 403; quotes via search-engine excerpts only.* |
| [RacingCircuits.info — Sonoma Raceway](https://www.racingcircuits.info/north-america/usa/sonoma-raceway.html) | Yes | "The Chute" (1998), Turn 11A (2003), Turn 11B (2012), Turn 9A widening (2012), historic pit road |
| [Wikipedia — Sonoma Raceway](https://en.wikipedia.org/wiki/Sonoma_Raceway) | Yes | Carousel = T4-T6 banked complex (Wikipedia convention; we use the coaching-source convention of T6 alone). Track configurations history. |
| [NASCAR.com — Drivers offer feedback on Sonoma repave at Goodyear test](https://www.nascar.com/news-media/2024/03/28/drivers-offer-feedback-on-sonoma-repave-at-goodyear-test-a-whole-new-ballgame/) | Yes | February 2024 full repave, "super gripped up", 2.5 s under track record, Josh Berry "a lot more grip", "dirty off-line" on new pavement |
| [Jayski — Goodyear tire test at repaved Sonoma Raceway](https://www.jayski.com/2024/03/27/goodyear-tire-test-at-repaved-sonoma-raceway/) | Yes | Repave details, milling 1.5 in, three-manufacturer tire test |
| [SpeedSF — Sonoma's Recent Repave Helps Set New Records](https://www.speedsf.com/blog/2024/3/20/after-sonomas-repave-our-best-post-new-records) | Yes | Repave-era lap records are materially faster |
| [Sportscar365 — Sonoma Onboard with Acura's Trent Hindman](https://sportscar365.com/videos/sonoma-onboard-with-acuras-trent-hindman/) + [YouTube](https://www.youtube.com/watch?v=Mc87KzZypic) | Yes | Carousel apex-curb usage in a pole-winning lap |
| [Speed Secrets — Sonoma Virtual Track Walk product](https://speedsecrets.com/product/sonoma-raceway-virtual-track-walk/) | Yes | Bentley + Krause material, paywalled — referenced as the canonical pro source we don't have direct access to |
| [AccuWeather — Sonoma Raceway forecast](https://www.accuweather.com/en/us/sonoma-raceway/95476/weather-forecast/35265_poi) | Yes (location) | Sonoma's morning-fog burn-off pattern (the pattern itself; coaching content is in `sonoma.py:WEATHER_PHASES`) |
| `Performance-Driving-Illustrated-2-23-24.pdf` (Bentley, in-repo) | No (universal pedagogy) | General trail-brake rule, vision rule, weight-transfer rule. Used in Part B only. |
| [Track Mustangs — Cold Weather Track Advice](https://trackmustangsonline.com/threads/cold-weather-track-advice.15474/) | **No (general)** | **Dropped from the Sonoma-specific section.** See Part D. |

---

# Existing-doc cross-references

This doc complements but does not replace:

- [`sonoma_track_intelligence.md`](sonoma_track_intelligence.md) — per-corner brake refs and base technique tips
- [`trod_sonoma_session.md`](trod_sonoma_session.md) — verbatim T-Rod coaching transcript
- [`markers.md`](markers.md) — 16 named landmark markers with kinds and source attribution
- [`adr/014-sonoma-as-the-product.md`](adr/014-sonoma-as-the-product.md) — the system-design ADR that consumes Part A as canonical Sonoma vocabulary in `src/pitwall/features/sonoma.py:SYSTEM_PROMPT_LORE`
