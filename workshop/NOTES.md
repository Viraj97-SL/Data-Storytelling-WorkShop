# Workshop notes — Python for Data Storytelling

UCL SODA (Social Data Institute), Edinburgh, 16–17 July 2026. Funded by
UKRI under the Data Storytelling for Digital Research Infrastructure (DRI)
project. Convened by Dr. Igor Tkalec (UCL SODA). Source material:
`notebooks/PDS_Workshop_FINAL.ipynb`.

## The agenda as actually run

**Day 1**
- Intro talk: Reem Khurshid (data journalist, UCL Geographic Data Service) —
  what makes a visual explanatory rather than exploratory, from a
  journalist's side of the fence rather than an analyst's.
- Session 1: explanatory data visualisation — theory (below).
- Session 2a: Plotly.
- Session 2b: Bokeh.
- Session 3: Altair (marked "bonus" in the notebook, i.e. time-permitting),
  plus a practice-dataset list and a package-comparison table.

**Day 2**
- Session 4: Streamlit dashboards — deliberately switched out of the
  notebook into a proper IDE ("more efficient to build dashboards as `.py`
  rather than `.ipynb` files"), demoed in VS Code, plus a walkthrough of
  deploying to Streamlit Community Cloud via the `streamlit/app-starter-kit`
  template.
- Session 5: free-flow exercise — build your own Streamlit dashboard from
  the practice datasets or your own data.
- Session 6: back to the notebook — machine learning as a route into a data
  story: decision-tree classification (car buying preferences, worked
  example) and K-means clustering (car fuel-efficiency/CO2, worked example).
- Session 7 (optional): two ML exercises — athletic-ability classification,
  and open-choice clustering on one of the practice datasets.

## Theory

**Visual literacy (Trumbo, 1999).** Three components: visual thinking (how
eyes + brain organise and perceive images — pattern recognition), visual
learning (developing images for an intended purpose — the craft of
visualisation itself), visual communication (using visuals to express ideas
to an audience — this is where design and audience considerations enter).

**Persuasive communication (Burnett, Holt, Borron & Wojdynski, 2019).**
Central route persuasion is thoughtful, cognitively expensive, and produces
lasting attitude change. Peripheral route is affective, cognitively cheap,
and produces short-term attitude change — the notebook's claim is that
*interactive* visuals work the peripheral route specifically to engage
people who are least likely to engage at all. Cross-referenced against
Aristotle's persuasion criteria (ethos, logos, pathos, telos, kairos) as the
underlying frame for "insight" in a data story.

**Exploratory vs. explanatory (Echeverria, Martinez-Maldonado, Buckingham
Shum, Chiluiza, Granda & Conati, 2018; Dzuranin, n.d.).** Exploratory
visualisation is for *finding* insight — descriptive statistics, better
underlying understanding, no fixed audience. Explanatory visualisation is
for *communicating* an insight you already have — clear, concise, inspiring
a call to action. Dzuranin's explanatory process has three stages:
preparation (verify the data's accuracy/completeness/consistency/freshness,
define the purpose before touching the chart, profile the audience),
creation (match the visual to purpose + data, follow best practice — Tufte's
data-to-ink ratio, pre-attentive attributes: size, colour, position), and
telling the actual story without misleading the audience (no truncated
y-axes, no cherry-picked ranges).

**The data storytelling Venn.** Referenced but not restated in full in the
markdown — the standard three-circle framing (data / narrative /
visualisation, story sits at the intersection) that the "explanatory data
visualisation process" diagram builds on.

**Visualisation ecosystems (Kosara, Dasgupta & Bertini, n.d.).** Three
means, each with different design priorities: analysis (own exploration —
priorities are generality, quick iteration, avoiding dead ends, trust,
fidelity to your own data), guided analysis (leading someone else's
exploration — priority is "information scent," giving them a sense of
trends worth chasing), presentation/communication (priorities: guidance/
sequence, specificity/focus, semantics, efficiency, emphasis,
expressiveness, low visual complexity). The line the notebook draws: in
presentation the *point is fixed by the author*; in analysis it's open-
ended. Same source gives the evaluation criteria for a finished explanatory
visual: drawing interest, engagement, willingness to explore, memorability,
persuasion, inspiring action.

**Closing line (Schwabish, 2014, p.213):** "Effective [and explanatory]
visualizations show the data to tell the story, reduce clutter to keep the
focus on the important points, and integrate the text with the graphs to
transfer information efficiently."

## Techniques covered

Plotly, Bokeh and Altair were each run through the same four "objectives"
(trend, comparison, relationship, proportion), basic version first, then a
customised version with an explicit "IMPROVEMENTS FOR A DATA STORY" note.
The recurring techniques across all three libraries:

- **Reference lines and annotations** — a horizontal average/mean line
  (`add_hline` in Plotly, a `Span` in Bokeh) with a text annotation calling
  out the specific value; in the Bokeh temperature example, an `Arrow` +
  `Label` pointing at one specific year (1950) rather than a bare
  reference line.
- **Highlight-one-bar-in-grey (or the inverse)** — the college-majors bar
  chart colours every bar grey except the one the story is actually about,
  which gets a saturated colour.
- **Custom category labels** — remapping raw category strings (e.g. full
  major names) to short, presentation-safe labels via a lookup dict rather
  than truncating or rotating long default labels.
- **Sorted categories** — `categoryorder`/`categoryarray` in Plotly,
  `sort=` in Altair — bars in descending order of value rather than
  whatever order groupby happened to produce.
- **Removing axis titles** where the value is self-evident from the title
  or the chart is one of several facets sharing an axis label.
- **`template="simple_white"`** (Plotly) as the go-to clean theme once a
  chart moves from exploratory to explanatory — dropped in the same cell as
  the reference line + highlighted bar in the college-majors example,
  i.e. theme change is part of the same "clean it up for the story" pass,
  not a separate step.
- **K-means as a route to a story angle**, not an end in itself. The car
  fuel-efficiency/CO2 example: cluster on fuel efficiency + CO2 emissions,
  then look at what's inside the outlier cluster. The finding — 5 of the 15
  outliers are diesel cars with emissions close to electric-hybrid levels —
  is treated as the "disbalance" that becomes the actual narrative hook
  (what diesel technology gets there, and does it generalise). The
  clustering isn't the story; the anomaly the clustering surfaces is.
- **Decision trees / random forest** for the athletic-ability exercise
  (Height, Weight, Reaction_Time, Endurance, Agility → Athletic_Skill) — same
  pattern as the notebook's own worked decision-tree example (car buying
  preferences: initial assumption was SUV-over-sedan is about practicality;
  feature-importance from the fitted tree pointed at lifestyle factors
  instead, which is the actual disbalance-to-explain). The exercise is
  explicitly testing "taller people perform better athletically" against
  the same initial-assumption-vs-model-disagreement pattern.

## What I did differently in `application/`

The workshop's own worked examples run on stock prices, gapminder, tips,
wine quality — clean library datasets, no real-world dirt. `application/`
runs the same technique vocabulary against an actual scraped, messy dataset
(a UK job-market export with missing fields, placeholder zeros, and no
schema documentation), which changes what each technique is *for*:

- **Reference lines and annotations** → `viz/04_bokeh.py`'s weekly posting
  volume chart: a `Span` at the median week plus a `Label`, same mechanism
  as the notebook's Apple-stock average line. Difference: the notebook's
  reference line answers "is this point above or below average"; mine
  additionally has to survive a dataset where some weeks have zero
  postings (scraper gaps), so the median (not mean) is the reference,
  chosen because it isn't dragged around by those zero weeks.
- **Highlight-one-bar(-in-a-darker-shade)** → `viz/01_matplotlib_seaborn.py`'s
  top-hiring-organisations chart. Instead of highlighting the *interesting*
  bar in colour (the workshop's pattern), I darken the bars that are
  suspected recruitment agencies by name-pattern match — the highlight
  marks a *caveat* (nearly a third of "hiring organisations" aren't actual
  employers) rather than a finding to celebrate. Same visual mechanism,
  opposite emotional register: warn, not applaud.
- **Sorted categories** → used everywhere a bar chart appears
  (`01_matplotlib_seaborn.py`'s role-category and top-hiring-organisations
  charts, `02_plotly.py`'s experience-level box plot ordered by median
  salary, `03_altair.py`'s top-locations chart via explicit `sort=order`).
  The one place I *didn't* sort — the pay-band histogram — is deliberate:
  lower/mid/upper has a natural ordinal reading order that a value-sort
  would destroy.
- **Custom category labels** → `shared.py`'s `humanize_label()` turns
  DB-native snake_case (`ai_engineer`, `mlops_engineer`) into presentation
  labels (`AI Engineer`, `MLOps Engineer`), with a small acronym-override
  table (`ai`, `ml`, `nlp`, `llm` upper-cased) rather than the workshop's
  one-off hand-written dict — because the label set here comes from a
  live database column, not a fixed list of ten college majors.
- **`template="simple_white"` / "clean theme as part of the polish pass"**
  → generalised much further than the workshop's single Plotly template
  swap: the whole dashboard (`viz/dashboard.py`) is one deliberate theme —
  dark, greyscale, a single amber accent, no rounded corners, Streamlit's
  own chrome hidden via CSS. The workshop's version of this idea is
  "pick a nicer built-in template for this one chart"; mine is "commit to
  one palette and typeface everywhere, including inside every embedded
  Plotly figure's `layout.font`," because a dashboard with five
  independently-themed charts reads as unfinished in a way a single static
  chart doesn't.
- **K-means-outlier-as-narrative-hook** → structurally, not literally,
  reused in `viz/story/build_story_data.py`. There's no clustering
  anywhere in `application/` — the equivalent move is treating a
  *counted* anomaly as the hook instead of a *clustered* one: of 480
  employers actually checked against the real UK sponsor register, only 49
  hold a licence, and separately, of the postings that explicitly claim to
  offer sponsorship, only 6 were ever checked at all. That gap — not a
  cluster, just an honest cross-tabulation — plays the same role the 5
  diesel outliers play in the car example: it's the "disbalance" the whole
  story is built around. I considered running K-means on the job-market
  data (e.g. clustering postings by salary + seniority + skill count) but
  didn't find a cluster result that supported a claim I could stand behind
  with this data's actual coverage — see `viz/story/README.md`'s
  cut-corners list for the numbers that didn't make the cut, rather than
  forcing an ML angle the data didn't earn.
- **Decision tree / random forest** → not applied anywhere in
  `application/`. Honest gap: there's no labelled target variable in this
  dataset that a classifier would be predicting *toward* a data-story
  claim (the athletic-ability exercise has a clear target,
  `Athletic_Skill`; nothing here plays that role without inventing one).
  Left out rather than shoehorned in.
- **What the taught dashboards (`streamlit-demos/`) do that mine
  deliberately doesn't**: `enhanced_basic_dashboard.py` and
  `final_cool_dashboard.py` are teaching artefacts, not explanatory
  dashboards, and it shows — `st.metric` for every KPI, a Comic Sans
  font-family override, a five-way theme picker (Light/Dark/Blue toggle +
  a separate dark-mode checkbox that does almost the same thing), emoji in
  sidebar captions, hardcoded hex colours per category, and placeholder
  "Text text text" body copy standing in for analysis. `viz/dashboard.py`
  fixes the two of these that are actual bugs rather than style choices:
  `st.metric`'s fixed-width CSS silently truncates a compound value like
  "829 (43.0%)" to "829 (43...." (see `viz/README.md`) — replaced with
  hand-built HTML KPI blocks with no such limit. And `st.plotly_chart`'s
  default `theme="streamlit"` (present on every `st.plotly_chart` call in
  both taught dashboards) silently re-themes the figure client-side after
  Python has already set it up correctly — every call in `dashboard.py`
  passes `theme=None` instead. The rest (one committed palette instead of
  a runtime theme-picker, computed finding-statement titles instead of
  static labels, no emoji, no placeholder copy) is the explanatory-vs-
  exploratory distinction from the theory section, applied to the
  dashboard layer itself: the taught examples are exploratory tech demos
  (here's what the widget can do); mine tries to be an explanatory
  artefact (here's what the data actually says).
