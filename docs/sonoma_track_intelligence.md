# Sonoma Raceway — Track Intelligence

Compiled 2026-04-28 from public sources for the Pitwall coaching system. The auto-built `data/tracks/sonoma.json` already gives 11 corner geometries with brake-zone metrics (T3, T6, T9, T10, T11). What this doc adds is **named reference points, per-corner technique, common mistakes, and Bentley-flavored coaching language** that the geometry alone cannot give.

## Executive summary — what's new vs `sonoma.json`

- **Real coordinates and physical scale.** Track is 38.1601°N, -122.4594°W; long course 4.06 km / 2.52 mi, 49 m elevation change ([latitude.to](https://latitude.to/articles-by-country/us/united-states/8854/sonoma-raceway), [Wikipedia](https://en.wikipedia.org/wiki/Sonoma_Raceway)). The dataset's coords (~23.49°N) are anonymized.
- **The Carousel = Turns 4–6**, not just T6, and "the Chute" is the NASCAR bypass connecting T4a to T7a ([Wikipedia](https://en.wikipedia.org/wiki/Sonoma_Raceway)).
- **Visual landmarks beat brake boards** at Sonoma — most pros call out "bridge", "pavement cracks", "Toyota sign letters", "K-wall bend", "tire stacks", "pit-entry lines", "bump in the road" ([Kanga Track Notes](http://www.kangamotorsports.com/track-notes), [Blayze T11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11)).
- **T3 is a "give-away" corner** — sacrifice T3 entry speed to win T3a → T4 → straight ([Kanga Notes](http://www.kangamotorsports.com/track-notes)).
- **T4 is the most-mistimed brake zone**: "back up the brake by one marker" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **T11 has no painted marker** — best reference is a bump in the road; "wait until the car compresses and settles after that bump to start the brake zone" ([Blayze](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11)).
- **Bentley's actual Sonoma material is paywalled** ($79 Virtual Track Walk on speedsecrets.com). What we *do* have is a recorded Bentley coaching-day diary from Kanga Motorsports with quotable language about T1, T6, brake-release rate and "3 % more throttle" ([Kanga blog](http://www.kangamotorsports.com/blog/2018/ross-bentley-coaching)).
- **Sector layout**: GTA America 2023 PDF exists but is binary-only and not extractable via WebFetch.

---

## Per-corner intelligence

The auto-built `sonoma.json` enumerates T1–T11. Where public sources also reference T2a/T3a/T4a/T8a/T9a, those are appended as sub-corners. Anything not found in public sources is marked **NF** (not found) so we don't fabricate.

### T1 — Right-hander after start/finish

- **Direction**: right; uphill power section ([Sonoma Raceway news](https://www.sonomaraceway.com/media/news/sonoma-nascar-track-layout-why-challenges-even-best.html)).
- **Approach**: 4th gear, full throttle ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Reference points**: "Swing tight to inside K-wall" — use the bend in the left K-wall as the apex; track out toward the right ([Kanga](http://www.kangamotorsports.com/track-notes), [lapmeta corner notes](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
- **Speed correction**: "Once you are tracked out, this is where most cars will make a speed correction — for some of the faster cars, this might be a brake, for others a lift" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
- **Bentley note**: "Change the arc of Turn 1" was identified as the highest-leverage lap-time gain in a Bentley coaching session ([Kanga blog](http://www.kangamotorsports.com/blog/2018/ross-bentley-coaching)).
- **Tip**: The author of that session ended up "carrying more throttle and speed out of Turn 1 and into Turn 2" — T1/T2 is a connected complex.

### T2 — Off-camber uphill blind right-hander (some sources call it a hairpin)

- **Direction**: right (right-then-left double-apex per [lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway); off-camber uphill blind right per [Kanga](http://www.kangamotorsports.com/track-notes)). Sources disagree because configurations differ; on the long course Kanga's description matches.
- **Brake refs**: "Bridge" overhead, plus pavement cracks ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Gear**: downshift to 3rd ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Apex**: slightly late.
- **Quote**: "You can brake less than you think and carry speed as you head uphill" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Common mistake**: following the left entry berm too far left; over-braking ([Kanga](http://www.kangamotorsports.com/track-notes)).

(In NASCAR commentary T2 is described as a hairpin requiring trail-braking and double-apex; that applies to the NASCAR config: "tight double-apex hairpin and key for getting speed for the fast infield Turn 3, 4, 5 and 6 complex … brake hard downshifting to 2nd and trail brake into the corner" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).)

### T3 / T3a — Left-right complex; T3a is "the blindest in NASCAR"

- **Direction**: T3 left, T3a right; T3a's apex is blind ([Sonoma news](https://www.sonomaraceway.com/media/news/sonoma-nascar-track-layout-why-challenges-even-best.html)).
- **Brake**: "Light lift or left-foot brake before turn-in" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Gear**: 3rd; "try 4th but slower" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Reference points**: right-hand curbing, light poles in the stands ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Strategy**: "Compromise Turn 3 exit for good Turn 3a exit" ([Kanga](http://www.kangamotorsports.com/track-notes)). lapmeta restates: "Turn 3 is a give-away turn. You will sacrifice a little speed to gain more speed through Turn 3A and down into Turn 4."
- **Turn-in for 3a**: "Turn in very late and end up far at track left and parallel to the track for a split second. Be patient with your turn-in for 3A. Carry speed over the crest and power down to Turn 4" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
- **Common mistake**: braking too early at T3 (it's a give-away); turning in early at T3a and missing the late apex.

### T4 — Downhill, off-camber turn-in

- **Direction**: right; "downhill braking and an off-camber turn-in make this corner quite a struggle for many racers — most drivers brake too late for Turn 4" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
- **Brake refs**: "Walls on sides; wall height increase on left" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Quote/heuristic**: "Where you think you should start braking, back that up by one brake marker" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
- **Technique**: "Brake early, get the car slowed down and move the weight balance to the rear as you turn-in to this medium-apex corner. Clipping the apex berm slightly can help rotate the car" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
- **Common mistake**: overshooting the brake point on the downhill; late on the brake.

### T5 — Setup corner for the Carousel

- **Direction**: right (continuation into the Carousel).
- **Throttle**: "Generally a flat or close to flat-out corner for most cars where you breathe the throttle a little bit and keep it as tight and right as your car will allow around the bend to set up Turn 6" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
- **Gear**: "Shift up to 4th" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Tip**: T5 is throwaway speed; preserve T6 entry.

### T6 — The Carousel (the iconic corner)

- **Direction**: long sweeping left-hander, downhill, off-camber.
- **Description**: "Sonoma's most iconic corner, known as the carousel … a blind entry … rapid downward undulation into the sweeping left hander challenges drivers to slow the car down enough to make the corner, but carry enough momentum to set themselves up well for the passing zone in Turn 7" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
- **Brake point**: "Just after cresting slight hill" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Brake refs**: "Tires on left, corner station on right" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Quote (technique)**: "Apex the inside berm and get a smooth exit. Speed through here carries up long straight" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Bentley angle**: Bentley specifically asked drivers about Sonoma's T6 carousel: "How did the bumps in the Turn 6 carousel affect the car?" — and used "moving the brake zone for Turn 6" as a coaching session theme ([Kanga blog](http://www.kangamotorsports.com/blog/2018/ross-bentley-coaching)).
- **Common mistake**: early throttle on the off-camber section; "the off-camber Carousel banking punishes early throttle application" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).

### T7 — Hard-braking right-hander, "the Chute" exit

- **Direction**: right.
- **Brake**: "Braking around 300 board" ([Blayze](https://blayze.io/blog/car-racing/one-corner-analysis-sonoma-turn-7)). Pavement cracks/chips and signs on left as additional refs ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Gear**: hard downshift to 3rd; upshift to 4th on exit ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Configuration**: "Long double-apex turn — second apex more important than first" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Quote**: "Hard braking here, and late turn in and late apex … important to keep your eyes up" — Dion von Moltke ([Blayze](https://blayze.io/blog/car-racing/one-corner-analysis-sonoma-turn-7)).
- **Tip**: "Open your hands as early as possible" — unwind the wheel to allow throttle ([Blayze](https://blayze.io/blog/car-racing/one-corner-analysis-sonoma-turn-7)).
- **Common mistake**: turning in or hitting the first apex too early; under-braking on entry.

### T8 / T8a — The Esses

- **Direction**: left-right-left-right rhythm ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Quote (technique)**: "Be smooth, pour on the throttle and don't pinch. Apexes are all slightly late" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Bentley note**: A Bentley-coached driver reported "gains on the back fast sections" (T8/8a) by getting "more comfortable being at full throttle more of the time" ([Kanga blog](http://www.kangamotorsports.com/blog/2018/ross-bentley-coaching)).
- **Common mistake**: pinching the line on T8a, sacrificing exit onto the run to T9.

### T9 — Connector to T10

- **Direction**: NF in detail.
- **Throttle**: "Exit Turn 8a at full throttle" — T9 is essentially a setup for T10 ([Kanga](http://www.kangamotorsports.com/track-notes)).

### T10 — Fastest corner on the track

- **Direction**: right ("fast right-hand bend, big wall on left") ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Status**: "The fastest corner on the racetrack where cars reach top speeds" ([Sonoma news](https://www.sonomaraceway.com/media/news/sonoma-nascar-track-layout-why-challenges-even-best.html)).
- **Reference points**: "Run over left berm, use Toyota sign letters as visual guide" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **Apex**: slightly late.
- **Quote (technique)**: "Progress from dragging brake to small lift only … full throttle before the Apex all the way down to Turn 11" ([Kanga](http://www.kangamotorsports.com/track-notes)).
- **lapmeta corollary**: "The keys to Turn 10 are to get your speed correction done early, which in most cars will be a brake — some quite a bit of brakes" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
- **Common mistake**: too cautious — drivers brake when they only need a lift, losing the run to T11.

### T11 — "Calamity Corner" (the hairpin)

- **Direction**: right-hand 180° hairpin onto the front straight ([Sonoma news](https://www.sonomaraceway.com/media/news/sonoma-nascar-track-layout-why-challenges-even-best.html), [Sonoma Raceway business](https://www.sonomaraceway.com/business/turn-11/)).
- **Nicknames**: "Calamity Corner" (in NASCAR commentary) ([Sonoma news](https://www.sonomaraceway.com/media/news/sonoma-nascar-track-layout-why-challenges-even-best.html)).
- **Brake refs**: "Pit entry lines on left" ([Kanga](http://www.kangamotorsports.com/track-notes)). Better visual: "A bump in the road where the road gets wider to drivers' left … wait until the car compresses and settles after that bump to start the brake zone" ([Blayze T11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11)).
- **Reason no painted marker works**: "Turn 11 is quite flat which makes it visually difficult to pick out markers, and the favorite marker is actually a bump in the road" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
- **Turn-in**: "Turn in approximately at the start of the tire stacks on our left hand side" ([Blayze T11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11)).
- **Apex**: "Apex the third tire stack … maintain very slow trail brake all the way down there. No initial throttle before apex point" ([Blayze T11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11)).
- **Exit**: "Use absolutely all of the road on exit to maximize our exit speed. Pick up initial throttle at the apex and let the car be free as possible" ([Blayze T11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11)).
- **Race-craft**: "Be as far left as possible and trail brake in, be patient on turn in and come down late as it's a full 180 degree corner" ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)). T11 is the canonical late-race passing battleground; produces "dive-bomb passes, aggressive contact" ([Sonoma news](https://www.sonomaraceway.com/media/news/sonoma-nascar-track-layout-why-challenges-even-best.html)).
- **Common mistakes**: crabbing on entry; throttle too early causing snap oversteer; not using full road on exit; fighting understeer before entry — all enumerated in the Blayze breakdown.

### T12 — Not a separate corner on the long course

The "long" Grand Prix configuration has 12 turns when T11 is split into T11/T12 (entry + apex/exit). Most non-NASCAR sources count it as one hairpin. Kanga groups it as "Turn 11 & 12 — Hairpin" with the same instructions ([Kanga](http://www.kangamotorsports.com/track-notes)).

---

## Bentley on Sonoma — verifiable quotes and language

Ross Bentley's authoritative Sonoma material (Virtual Track Walk co-presented with Peter Krause, 98 minutes, $79) is paywalled at [speedsecrets.com](https://speedsecrets.com/product/sonoma-raceway-virtual-track-walk/) and not extractable. The product description itself does carry useful framing: "the ideal cornering line, reference points to use at track surface, eye-level and above, where surface, camber and elevation increase traction, and the most important corners to focus on to improve your lap times … most corners are blind, no place to rest, and a balance of fast and slow corners."

What we can quote directly from a public Bentley Sonoma coaching session, recorded by Kanga Motorsports ([blog](http://www.kangamotorsports.com/blog/2018/ross-bentley-coaching)):

- **Coaching style is question-driven**, not directive: e.g. *"How did the bumps in the Turn 6 carousel affect the car?"* — used to push the driver toward self-discovery.
- **"3 % more throttle"** — Bentley framing of measurable throttle adjustments rather than vague "drive faster."
- **"End of Braking"** and **rate of brake release** as named focus areas (matches the EoB > BoB principle on PDF p39).
- **"Throttle awareness"** — getting "more comfortable being at full throttle more of the time."
- **T1 and T6 are his lap-time levers at Sonoma**: T1's arc and T6's brake-zone position were the day's highest-leverage targets.

Bentley's Substack ([rossbentley.substack.com](https://rossbentley.substack.com/)) and Speed Secrets blog do not surface track-specific Sonoma articles in indexable form. His "Coaching With Data" piece uses Watkins Glen data, not Sonoma. So for licensed canonical Bentley Sonoma phrasings the Virtual Track Walk purchase is required.

Generic Bentley pace-note language we can use confidently (from the Performance-Driving-Illustrated PDF + Kanga session) at Sonoma:

- **T2/T6**: "You can brake less than you think."
- **T3**: "Patience — wait for the turn-in."
- **T4**: "One marker earlier."
- **T6**: "Smooth exit, the straight is long."
- **T7**: "Eyes up. Late apex."
- **T10**: "Lift, don't brake."
- **T11**: "Trail to the apex. All the road on exit."

---

## Sonoma-specific tricks

1. **Visual references > brake boards.** The track's most distinctive markers are environmental — bridge over T2, tire stacks at T11, Toyota sign at T10, K-wall bend at T1, pit-entry lines before T11 ([Kanga](http://www.kangamotorsports.com/track-notes), [Blayze T11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11)). Coaching that name-checks these will sound native; coaching that says "brake at 124 m" will not.
2. **Compromise corners exist on purpose.** T3 → T3a → T4 is one connected sequence; T5 → T6 is another. "Sacrifice T3, win T4" and "T5 is throwaway, save T6" are the rules. ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway), [Kanga](http://www.kangamotorsports.com/track-notes)).
3. **The Carousel punishes throttle, not brake.** Most drivers' instinct on the long sweeping left is "more throttle"; the off-camber + downhill geometry punishes that ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
4. **T4 is consistently mistimed.** "Most drivers brake too late." Default coaching: back the brake up by one marker ([lapmeta](https://lapmeta.com/en/blog/track-guide-sonoma-raceway)).
5. **T11 has no painted marker — use the bump.** Listen to suspension, not eyes. Wait for compression-then-settle ([Blayze T11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11)).
6. **Exit speed at T6 carries the longest straight on the track.** Lap-time leverage is much higher than corner speed at T6 — classic late-apex argument from Bentley (PDF p18) made concrete.
7. **T8/T8a esses reward "smooth, don't pinch."** Bentley's advice was to get more comfortable at full throttle here.
8. **Weather pattern: morning fog burns off mid-morning** ([AccuWeather](https://www.accuweather.com/en/us/sonoma-raceway/95476/weather-forecast/35265_poi)). First session of an HPDE day often has lower grip from cool damp surface; pace builds through the day. Worth a coaching mode flag.
9. **49 m of total elevation change** ([Wikipedia](https://en.wikipedia.org/wiki/Sonoma_Raceway)) — the track's character. Three meaningful elevation features: uphill into T2, downhill into T4, undulating Carousel.
10. **"Calamity Corner" is the late-race passing zone.** If we're scoring sessions, the "T11 dive-bomb" is the diagnostic moment for race-craft.

---

## Sector layout

Public sector-line GPS coordinates were **not extractable** from public sources on 2026-04-28. The 2023 GTA America Sonoma Track Sector Map PDF exists ([gtamerica.us](https://www.gtamerica.us/documents/notice/953/2023+Sonoma+Track+Sector+Map+230330.pdf)) but is image/binary and could not be parsed via WebFetch in this run.

What we know structurally: the auto-built `sonoma.json` defines 3 sectors. The official long-course config has 12 turns (T1–T11/T12 with T8a/8b sometimes split). NASCAR's "Chute" bypasses the Carousel via a straight from T4a to T7a, producing a 1.99 mi / 12-turn variant ([Wikipedia](https://en.wikipedia.org/wiki/Sonoma_Raceway), [Sonoma news](https://www.sonomaraceway.com/media/news/sonoma-nascar-track-layout-why-challenges-even-best.html)).

Best path forward to fill in: convert the GTA America PDF to images (e.g. `pdftoppm`) and OCR / read the rendered map; or hand-author from the official Sonoma facility map.

---

## Marker GPS coordinates

**No public source publishes per-marker GPS coordinates** for Sonoma's brake boards or reference points as of 2026-04-28. The only authoritative geographic anchors found:

- **Track centroid**: 38.1601°N, -122.4594°W ([latitude.to](https://latitude.to/articles-by-country/us/united-states/8854/sonoma-raceway)).
- **Finish & Timing Line**: 38.16152°N, -122.45472°W ([latitude.to](https://latitude.to/articles-by-country/us/united-states/8854/sonoma-raceway)).
- **OpenStreetMap centerline**: `way[name="Sonoma Raceway"]` via Overpass — usable for the centerline and approximate corner positions, but not for marker boards.

Marker GPS data for individual brake boards lives in commercial track scans (iRacing, Assetto Corsa Competizione laser scans) or has to be authored once by walking the track with a GPS unit. Bentley's Virtual Track Walk video (paywalled) is the closest blessed-pro reference but does not publish raw coordinates.

**Recommendation**: hand-author a `markers: []` array in `sonoma_real.json` from the named landmarks above (bridge, tire stacks, K-wall bend, Toyota sign, pit-entry lines, "the bump"), measured once during a real track day with a phone GPS — the visual landmarks survive longer than painted boards anyway.

---

## Sources

| Source | Contributed to |
|---|---|
| [Wikipedia — Sonoma Raceway](https://en.wikipedia.org/wiki/Sonoma_Raceway) | Track layout, configurations, Carousel/Chute history, T8a/T8b distinction |
| [latitude.to — Sonoma Raceway](https://latitude.to/articles-by-country/us/united-states/8854/sonoma-raceway) | Real GPS coords (track centroid + finish line) |
| [Kanga Motorsports — Track Notes](http://www.kangamotorsports.com/track-notes) | Per-corner brake refs, gears, speeds, technique tips for T1 through T11/12 (best single source) |
| [Kanga Motorsports — Test Day with Ross Bentley](http://www.kangamotorsports.com/blog/2018/ross-bentley-coaching) | Direct Bentley quotes about T1, T6, brake-release, "3% more throttle", question-driven coaching |
| [lapmeta — Track Guide: Sonoma Raceway](https://lapmeta.com/en/blog/track-guide-sonoma-raceway) | T1, T2 (NASCAR config), T3 give-away, T4 "one marker earlier", T5, T6 carousel, T10, T11 "bump" reference |
| [Blayze — Sonoma Raceway Turn 11](https://blayze.io/blog/car-racing/sonoma-raceway-turn-11) | Detailed T11 coaching: bump-as-marker, tire-stack apex, exit strategy, common mistakes |
| [Blayze — Turn 7 Analysis (Dion von Moltke)](https://blayze.io/blog/car-racing/one-corner-analysis-sonoma-turn-7) | T7 brake at "300 board", late apex, "open your hands" |
| [Sonoma Raceway news — NASCAR layout](https://www.sonomaraceway.com/media/news/sonoma-nascar-track-layout-why-challenges-even-best.html) | T1–T11 NASCAR descriptions, T11 = "Calamity Corner", T10 = fastest |
| [Sonoma Raceway — Turn 11 venue](https://www.sonomaraceway.com/business/turn-11/) | Confirms T11 hairpin nickname; mostly venue marketing |
| [Speed Secrets — Sonoma Virtual Track Walk product](https://speedsecrets.com/product/sonoma-raceway-virtual-track-walk/) | Bentley + Krause video metadata; paywalled at $79 |
| [Ross Bentley Substack](https://rossbentley.substack.com/) | General coaching framework; no Sonoma-specific public articles indexed |
| [GTA America 2023 Sector Map (PDF)](https://www.gtamerica.us/documents/notice/953/2023+Sonoma+Track+Sector+Map+230330.pdf) | Sector layout (binary; not text-extractable in this run) |
| [AccuWeather — Sonoma Raceway forecast](https://www.accuweather.com/en/us/sonoma-raceway/95476/weather-forecast/35265_poi) | Morning fog pattern |

---
