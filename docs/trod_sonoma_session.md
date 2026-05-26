# T-Rod — Sonoma Coaching Session (Verbatim)

**Source:** T-Rod (pro coach) coaching session at Sonoma Raceway, BMW M3, intermediate driver. Transcript captured 2026-04-28.

**Why this matters for Pitwall:** the [Sonoma intelligence research](sonoma_track_intelligence.md) found that Bentley's authoritative Sonoma material is paywalled, and the only public Bentley-on-Sonoma source is a 2018 Kanga session diary. T-Rod's coaching session below is the **second authoritative pro voice on Sonoma we have direct access to** — it's not Bentley, but it's the same level of practitioner specificity, on this track, in our exact car (BMW M3), with our exact driver level (intermediate). It is canonical pace-note material.

T-Rod's voice is more direct than Bentley's question-driven style. He gives specific actions ("just go 100", "be closer to the tire stacks", "distance is king"), specific numbers (60% vs 100% throttle = 20 ft-lbs), and corrects misreadings of the data ("that's reading brake switch, not brake pressure"). For the intermediate-pod system prompt this is closer to the canonical voice we want than my earlier paraphrases.

---

## Per-corner extraction

### Universal themes (recurring across the session)
- **"When you tip into 60 % throttle, just go 100"** — the torque difference between 60 % and 100 % is ~20 ft-lbs; not worth being timid for.
- **"Wait, I'm not at the apex yet"** — mental check before getting back to throttle. Delay early throttle so you can commit harder *at* apex.
- **"Distance is king"** in long sweepers (T6, T7, T11) — cut the inside, don't trade meters for mph.
- **"It's not a digital pedal"** — peak then *taper* the brake; don't square-wave it. Hold light brake to mid-corner.
- **"Roll the brake into the apex"** — keep nose loaded for steering grip; off brake at maximum-grip mid-corner.
- **"Trust the curbs"** — Sonoma's serrated berms catch the car; the camber is in your favour.
- **Cool-down laps:** drive the same line, just slowly. Make the line a learned thing.
- **Higher gear = less wanting to move** — lugging in 4th is sometimes smoother than dropping to 3rd.

### T2 — heel-and-toe matters here
- "Coming up to the top of two is such a short distance — you have to be really comfortable with that heel-and-toe to grab the gears in order to do it smoothly."
- M3 boosted brake is feathery — focus on application before adding more inputs.

### T4 — earlier brake, roll into the apex
- "You break a little early, right? … And then you're slowing down so much, but you're also pulling out of the brake 100 % there. Be more like you were trying at four, where you're rolling off the brake."
- Driver was confusing the digital brake-switch trace with brake-pressure trace; T-Rod corrects: "this is reading brake switch, not brake pressure."
- Want to see: "the spike, then you taper down" rather than "spike then off."
- "Hold more light brake as we're turning in … we're getting a little bit of grip on the front axle with holding that brake. We're keeping the nose weight there."
- "Should be off-brake at maximum grip in the middle of the corner."

### T6 — Carousel — distance is king
- The session's recurring corner. T-Rod calls out commitment to throttle by apex.
- "We want to be committed to more throttle at this point. I want to be slamming the throttle over."

### T7 — single apex, treat as double
- "There's a way you can do both — to where you come in, you cut the distance on the entry, you care about the first apex, and then you rotate that car in the centre and then you get on the second apex and treat it like a double. But really it's a single."
- "A lot of measure do the opposite — late trail brake and they'll use the second berm as an apex."
- "The fastest way is cutting all the distance."

### T9 — open the wheel, set up T10
- "I would let the car breathe more in here … open up the wheel and use a little bit more space coming out of nine."
- Reasoning: "When we come up to 10, we don't want to be having the angle in the car like this as we're approaching the curb. Because then we immediately have to go and do this. If we open up nine a little bit, we can get a straight shot into 10."
- Holding ~95 mph through here is the target for an M3.

### T10 — rolling speed, throttle by apex
- "We're rolling 25, 30 % throttle. Right. So let's get more in there."
- "The car is giving you feedback that it's not going to kill you, so let's start pulling that throttle out of the early phase of the corner and start committing to full throttle by the apex of the corner."

### T11 — be closer, distance is king
- "I want you to be closer to the berm. You know, I want you to be closer to the tire."
- "You can break a little earlier to get the car tucked down, if that works. I want you to be closer because distance is king in these kinds of [long sweeping] corners."
- "When we have long sweeping corners like six, like seven, like 11, there's a long curve to them. So we're not really looking at maximizing that line in, opening up the entry so much to carry a lot of speed through. Because distance is king."
- "The more time that you spend offline, the more time you're losing on the clock."
- T-Rod's verdict on a clean T11: "this is more what I want to see on a trail. Coming to 11, look at your brake trace where it goes up, it hits peak, and then it starts rolling down."

---

## Canonical T-Rod pace-note phrasings (extracted for system-prompt use)

Short lines our intermediate-pod LLM coach should know how to produce in T-Rod voice:

- "Distance is king" — for T6 / T7 / T11 entries.
- "Be closer to the tire stacks" — T11.
- "Open up nine, straight shot to ten" — T9 → T10 transition.
- "Just go 100" — when driver hesitates on throttle.
- "Wait, you're not at the apex yet" — early-throttle correction.
- "Roll the brake to the apex" — T4-style trail-brake coaching.
- "Trust the curb, it catches you" — when driver avoids berms.
- "Single apex, treat as double" — T7.
- "Cool-down means same line, slower" — between sessions.
- "Cut the distance, don't open up" — long-sweeper rebuttal to "carry more speed".

---

## How this maps to existing markers

The named landmarks from `data/tracks/sonoma.json` and the `markers.md` doc remain authoritative — T-Rod did not introduce new physical reference points. Instead, his contribution is **technique phrasing per corner**. Specifically:

| Corner | Existing marker | T-Rod technique addition |
|---|---|---|
| T4 | "where the left wall steps up" (brake_ref) | "roll the brake to the apex, off-brake at mid-corner" |
| T6 | "just after the slight crest" (brake_ref) | "slam the throttle by apex" |
| T7 | "the 300 board" (brake_ref) | "single apex, treat as double, cut the inside" |
| T9 | (none authored) | "open the wheel, straight shot to T10" |
| T11 | "the bump where the road widens left" (brake_ref) + "the third tire stack" (apex_ref) | "be closer, distance is king" |

These technique phrasings are now reflected in the per-driver-level system prompts in `src/pitwall/features/coaching/prompts.py` (`_LEVEL_SYSTEM_PROMPT["intermediate"]`) and the Sonoma track lore in `src/pitwall/features/track/sonoma.py:SYSTEM_PROMPT_LORE` (the legacy `_TRACK_LORE` dict and the monolithic `coach_engine.py` were split into focused modules in PR #30).

---

## Full transcript (verbatim, light copy-edits for readability)

> I walk. There we go. Okay. Can set up at break. I didn't shift. Yeah. No shift without spines and fifth. Yeah. But good line. Yeah. Good approach and good line. I can just do fourth, I think — not even brake that much.
>
> Yeah, if you're not going to shift, then maybe when you want to do the shift is right here. Do it downshift? Yeah. Right there. Pop it in and then just scoot out. Because you're already focused on the brake zone. You've already got the good brakes in. You got the good line in. You're hitting the marks. So now that you've got a little bit more mental capacity, you can go: okay, let's go down a gear and scoot up and get out of there. Get out of there. Because it's bugging. And you want fourth gear through this section anyway. Better. Good hustle to get over.
>
> Yep. The thing is, when you're in a higher gear, the car is less wanting to move, right? Because of how the rear drive line is — like the higher the gear you're in, the more it's sluggish to move over. There's more load on it. It's kind of a bummer that this is the fastest lap, but it was the lug lap that was testing lugging. But that just goes to show you — power. I went from fifth to third there. But it just goes to show you how important hitting your marks are and how important getting the throttle application right and the brake application right. Like, you can be in the highest gear, fifth gear, and lug it around the track and still be fast just by doing those things — practicing the right things.
>
> What I usually tell people is, when you're on a cool-down lap or behind traffic, don't relax your lines, do the same lines, because then it becomes a known learned thing that you're constantly doing. So on the cool-down laps, I'll do the line, even though we're going really slow.
>
> Here, if we go back, interestingly, I went from fifth to third into turn four, which I was doing in turn two. So I still had to do it, but I had to do it over a longer distance. The thing with when you're coming up to the top of two is such a short distance that you have to be really comfortable with that heel-and-toe to grab the gears in order to do it smoothly. The other thing is — when you have a booster system in the M3, it's pretty feathery to the touch. Your brake pads are pretty feathery to the touch, right? So that application is very important. Be more focused on the application and then start to add more things once you're fully comfortable with it.
>
> It's subtle, but you do see how you're lifting off the brake, you're pulling it out, you're starting to get comfortable with — I'm trying to really modulate it, modulate and pull. And the car is now turned. Great. We're getting down to the apex. Right. We're rolling good throttle. What I want to see is a little bit more commitment to that throttle. *"Oh, I was scared."* Watch — when you go out, you still have room. That curbing is more room for you to use.
>
> The first time I went out there, I just went out with DSC off. It wiggled all around. The serrated berms — they're also raised, right? It's kind of like coming on a camber in the corner. It catches you. Kuka is like this too — a lot of the curbs are kind of banked in your favour. So when you go hit them, it catches you and stops the momentum. It says: okay, you sit here now. So you can use that to your advantage. *"In other words, don't be a wuss."* I got it.
>
> You're diving in, you're in there. You're maintaining good throttle, and you're starting to focus on: when am I getting back to throttle? You have the average speed with just a little bit to keep the car balanced. Once you do that stab, why did you only go 60 %? *"I didn't want it to spin out and die."* It doesn't make enough power to do that. So next time, when you start to think about going slamming to 60 % throttle, think about going to 100 % throttle. The torque difference between 60 % and 100 % is not much — about 20 ft-lbs. That's not a lot of difference when you're modulating already up to 60 %. The tunes that we have in the ST4 cars, we limit the throttle down to 65 % to make the power that we need to. We're pretty fast in ST4 — but we're only using 60 % of the throttle.
>
> So when you tip into 60 % of throttle, just be like: yo, just go 100.
>
> The breaking point — I would say you brake a little early. Because what I suggest is a brake point should be about right here. You were early here, which is fine. But then you're slowing down so much, and you're also pulling out of the brake 100 % there. Be more like you were trying at four, where you're rolling off the brake. It's not a digital pedal.
>
> *"I really believe I'm rolling off, but maybe I'm not."* You are rolling off — but the pressures are saying. So I think this might be the brake switch and not brake pressure. Look — these are your brake pressures. So this should be reading pressure, but it's reading switch right now. When you look at it, it goes down to zero, right? There's no modulation there. But when we look at the actual pressure itself, there's a taper. We zoom in even more — that's more of what we're looking for. What I would like to see is not the spike here, right? *"That's when I'm shifting."* Yeah, you've got to get that down to have that consistent feel. But yeah, I like the taper off here. That's good. I like it.
>
> I want to see it curve more like this. When we talk about these kinds of pressures, this is half of what you were doing on the maximum. I want to see it taper more and just hold more light brake. Why? Because when we hold more light brake as we're turning in, as we're asking for the steering, we're getting a little bit of grip on the front axle by holding that brake. We're keeping the nose weight there. The tires can handle multiple inputs, but not too much of either one. *"I should be going fast when I do that."* Yes — you should probably come with better entry speed to be able to use it. And then you just hold lightly and you'll trail in. But you are trailing in — I want to see the trail hold to almost there. We're going to be coming up to maximum grip, maximum load in the middle of the corner. *"I want to be off-brake there."* Got it.
>
> See how quickly you come to throttle. That means that you know there's more speed there. You can mentally think: ah, there's more speed here. So when you're focusing on the brake and getting down into that corner, I want you to realize: hey, roll all that speed in — how light do I have to be on the brake to just keep that speed rolling in? Because by the time we get to this point, this is the middle of our corner. And we want to be committed to more throttle at this point. I want to be slamming the throttle over. To a degree, depending on what the rear is going to take. You're half-throttle until you're full-throttle here, whereas if we hadn't done this early throttle here, we would have been able to come into more throttle here.
>
> Especially on corners like seven and like eleven.
>
> I went late this time. I tried to stay out, like you were saying, coming into the esses. It's good. You're driving to where it needs to go. The car is hitting the marks that you're looking for. My suggestion in nine — I would let the car breathe more in here. What does that mean? I would open up the wheel and use a little bit more space coming out of nine. Why? Because when we come up to ten, we don't want to be having the angle in the car like this as we're approaching the curb. Because then we immediately have to go and do this. If we open up nine a little bit, we can get a straight shot into ten. That means that when we approach ten, we're not going from less steering to right steering angle — we're going straight to right.
>
> You've got a little bit of angle in the steering still, and then I do. *"And then you can see it."* Just slightly, yeah. And I got to switch over. But it's good. The speed that you got to — 95 miles an hour — that's really good. You're holding very good speed through here, and you're able to hold the line and get it to where you need it to go. But once again, I would like to say: hey, we're at the apex of the corner now, so let's start thinking about rolling to full throttle. You're already rolling 25, 30 % throttle. So let's get more in there.
>
> *"This is me just being a wuss."* Yeah, absolutely. We can agree. But you can trust it. It will be there.
>
> This is actually a pretty good look to a trail. Let's zoom out. Coming to 11 — look at your brake trace where it goes up, hits peak, and then starts rolling down. *"I can see where you downshift."* That's fine. It happens, especially with boosted systems. The pedal is very sensitive. It's not got hard feedback to you. So you kind of have to go: oh, okay. That's a good taper down.
>
> *"I wasn't thinking about 11 at all."* That's fine. Knowing your mental capacity and your ability to tackle things is part of the game. You know, 11 is a pretty simple corner when you break it down. I just want you to be closer to the berm. Closer to the tire stacks. The grip. You can break a little earlier to get the car tucked down. I want you to be closer because distance is king in these kinds of corners. When you have long sweeping corners like six, like seven, like eleven, there's a long curve to them. So we're not really looking at maximizing that line in, opening up the entry so much to carry a lot of speed through. Because distance is king. The more time that you spend offline, the more time you're losing on the clock. Typically, when we try to open up a corner and carry larger speed through, the delta doesn't trade off. The distance is worth more than the two miles per hour that you gain through the corner. The distance that you cut is more — makes you faster.
>
> You can tell this when you're on the street and you're in a two-lane left-hand turn. The car that's on the inside is always faster. Much less distance.
>
> *"That's helpful — coming into turn seven, I was wondering if I should single-apex it, do the trail brake like you said, but then forget the second berm and just take a very wide arc to accelerate sooner."* No — you want to cut the distance. There's a way you can do both: come in, cut the distance on the entry, care about the first apex, then rotate the car in the centre and get on the second apex and treat it like a double. But really it's a single. A lot of guys do the opposite — late trail brake and use the second berm as an apex. There are other ways to tackle it, but the fastest way is cutting all the distance. Both sides — there's a way you can achieve full throttle by the middle of the corner in both cases, but the one that does the shorter distance is faster. Car set-up notwithstanding. Your car can do it, so try to practice it.
>
> Overall — I really like how you're hitting your marks. You're getting comfortable with the track. You're rolling with good speed. You're putting the car in the right places. For the most part, you're hitting pretty much everything that you're supposed to hit in terms of markers and apexes — which is fantastic. Now it's time to start working on rolling the speed in and committing to throttle on the exit.
>
> Let's not work on the rolling-speed-in at this point. Let's work on you committing to throttle on the exit. So what needs to happen if we do that? *"Stop being a wuss. Step on the pedal sooner."* Yeah. At the apex, basically. Let's delay that throttle action — that early throttle action that we were starting to exhibit in some of these corners. Anytime you think you come into the corner is throttle time, do a mental check: I'm not at the apex yet. Once you're at the apex, let's start committing to more throttle. And that throttle needs to be significant. We want it to be a lot of throttle. 100 %. Because the car in most of these corners isn't going to bite you.
>
> Done. Cool.
