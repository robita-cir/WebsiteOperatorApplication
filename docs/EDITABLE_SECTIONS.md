# Editable sections of the CIR website template

**Status:** draft for the CIR team, reviewed 17 October 2026.
**Basis:** the template repository at commit `23f4878b60d337ebd18fac22427dcd31bdf14a86` (branch `template`). Every fact below was checked by reading the files. Nothing was built, installed or run. Paths start at the template's top folder. Line numbers refer to the file named in the same row.
**Companion:** [REQUIREMENTS.md](REQUIREMENTS.md) says what the operator tool must do with each area.

## 1. How to read this

- **Kind.** *Record*: one file per item, with fields (for example one file per person). *Page text*: sentences written inside a page file. *Setting*: a value used across the whole site. *File*: a picture or PDF.
- **Editing modes.** Add, Edit, Delete, Replace file. The template has no "archive" state, so each area says how to take an item off the site today.
- **Constraints.** "Required" means the build fails without the value. "Proposed limit" is a limit suggested by this review. The template does not enforce it.
- **Owner.** The service that should make the change. Service names are proposed; they are defined in REQUIREMENTS, section (e).

## 2. What the template holds today

| Area | Entries | Marked as samples |
|---|---|---|
| People | 62 | all 62 |
| Student projects | 11 | all 11 |
| Research directions | 4 | cannot be marked (no sample field) |
| Events | 9 | all 9 |
| News and announcements | 2 | both |
| Job openings | 2 | both |
| Publications | 3 | all 3 |
| Facilities | 4 | all 4 |
| Documents | 2 (no PDF files yet) | both |
| Partners | 12 | cannot be marked (no sample field) |
| Funded programmes | 4 | cannot be marked (no sample field) |
| Gallery albums | 4 | all 4 |

99 entries carry `sample: true`. Almost every entry is a placeholder: names such as "Professor 1", "PhD 1" and "Student 1", and sentences that begin "Placeholder".

---

## Area 1. People

- **Files:** `src/content/people/<name>.md`, one file per person. The file name becomes the profile address, for example `/people/jane-doe/`.
- **Kind:** record, with an optional biography (main text).
- **Editing modes:** Add, Edit, Delete, Replace file (portrait). To take someone off the lists, change their group to an alumni group. That is the template's only route to "archive".
- **Shown on:** `/people/` (lists by group), each `/people/<name>/` profile, the homepage (faculty, first four by order, with no Sample label, `src/pages/index.astro` 143), research project pages (student links), site map.
- **Owner:** PeopleService (proposed).

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| name | text | yes | None in the template | Must equal a project's student name exactly to link (`src/pages/research/projects/[slug].astro` 33) |
| group | one choice | yes | faculty, scholar, mtech, alumni-research, alumni-mtech, alumni-btech | Decides which list the person appears in |
| role | text | no | Proposed limit 80 characters | Card and profile |
| dept | text | no | Proposed limit 120 characters | Card and profile |
| interests | list of text | no (empty) | Proposed: up to 10 items, 60 characters each | Shown as tags. Profile says "To be added." if empty (`people/[slug].astro` 79) |
| homepage | web address | no | Schema accepts any valid web address. Docs say https | Profile link |
| photo | file path | no | Path under `public/`, for example `/people/jane-doe.jpg`. Not checked for existence | If the file is missing, the card shows a broken picture, not initials |
| order | whole number | no (default 100) | Lower numbers first within a group | Decides which four faculty appear on the homepage |
| sample | yes or no | no (default no) | | Sample label on faculty cards and profiles only |
| (body) | main text | no | Proposed: 80 to 250 words | Profile text. Empty shows "Biography to be added" (`people/[slug].astro` 103-104) |

**Current state.** All 62 files carry the sample flag and the sentence "Placeholder biography". No portraits are supplied. 16 homepage addresses point to `example.org`. The folder `public/people/` holds only a placeholder file.

**Portraits.** Store in `public/people/<name>.jpg`. The card crops to 4:5 (`src/components/PersonCard.astro` 28). Guidance in the template: at least 800 px tall. The alternative text is the person's name (`PersonCard.astro` 31).

---

## Area 2. Research directions

- **Files:** `src/content/research/<id>.md`. Exactly four files, named `human-robot-interaction`, `perception-manipulation`, `navigation-planning` and `assistive-health`. The file name is the id that projects and publications use.
- **Kind:** record.
- **Editing modes:** Edit only. Adding or removing a direction is a structure change: the four ids are fixed in `src/content.config.ts` (line 12).
- **Shown on:** `/research/`, each `/research/<id>/`, homepage (four cards), site map.
- **Owner:** ResearchAreaService (proposed).

| Field | Type | Required | Rules |
|---|---|---|---|
| code | text | yes | Letter shown on the card. Template uses A to D |
| title | text | yes | Proposed limit 60 characters |
| description | text | yes | Proposed limit 300 characters |
| order | whole number | no (default 100) | Sort order on the research page |

**Current state.** A = Human–robot interaction; B = Perception and manipulation; C = Navigation and motion planning; D = Assistive and health-care robotics.

---

## Area 3. Student and research projects

- **Files:** `src/content/projects/<name>.md` (11 files).
- **Kind:** record, with an optional abstract (main text).
- **Editing modes:** Add, Edit, Delete. There is no archive; set status to Completed to show that a project has ended.
- **Shown on:** `/research/`, each research direction page, each `/research/projects/<name>/` page, the profile of each named student, homepage (featured, first four by order), site map.
- **Owner:** ProjectService (proposed).

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| title | text | yes | Proposed limit 120 characters | Page title shrinks above 70 and 120 characters (`PageHero.astro` 18) |
| area | one choice | yes | human-robot-interaction, perception-manipulation, navigation-planning, assistive-health, other | "other" appears under "Other projects" |
| students | list of names | yes (an empty list `[]` is allowed) | Each name should match a person's name | Matching is exact. "Student A" (project 9) and "Student B" (project 11) match nobody |
| status | one choice | no | Active, Completed or Planned | Shown as a label. None of the 11 template projects has a status |
| summary | text | no | Proposed limit 300 characters | Card text |
| featured | yes or no | no (default no) | | The first four featured projects by order appear on the homepage |
| order | whole number | no (default 100) | | Sort order within each direction |
| sample | yes or no | no | | Sample label |
| (body) | main text | no | Proposed: 120 to 250 words | Abstract. Empty shows "Abstract to be added" (`research/projects/[slug].astro` 92-93) |

**Current state.** All 11 bodies begin "Placeholder abstract". Projects 1 to 4 are featured.

---

## Area 4. Events

- **Files:** `src/content/events/<name>.md` (9 files).
- **Kind:** record, with an optional description (main text).
- **Editing modes:** Add, Edit, Delete. Past events leave "Upcoming" automatically at the next site build. The archive lists every event by year, so no action is needed.
- **Shown on:** `/events/` (upcoming, workshop series, archive by year), each `/events/<name>/` page, homepage (the three newest items across events and news), the news feed, site map.
- **Owner:** EventService. The operator tool already has an events module (`events.py`) that this should extend.

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| title | text | yes | Proposed limit 120 characters | |
| kind | one choice | yes | workshop, programme, talk | Shown as a label |
| series | one choice or none | no | The site shows only the series named `series-1` on its series section (`src/pages/events.astro` 21) | Other series names are not grouped anywhere. Proposed: a fixed list |
| date | calendar date (YYYY-MM-DD) | yes | Must be a real date | Shown as day and month |
| endDate | calendar date | no | Should be the same day or later than `date`. The template does not check this | The event stays "upcoming" until this date passes |
| venue | text | no | Proposed limit 120 characters | Blank shows "To be confirmed" (`events/[slug].astro` 43) |
| summary | text | no | Proposed limit 300 characters | Card text and feed description |
| sample | yes or no | no | | Sample label |
| (body) | main text | no | Proposed: 60 to 200 words, required before publishing | Blank shows "Programme details, the speakers and the registration route will be added here when they are confirmed." (`events/[slug].astro` 61). That is template wording shown to visitors |

**Current state.** No event is upcoming on 17 October 2026. The latest end date is 26 June 2026 (`event-9`). The homepage's "Recent activity" shows Announcement 1, Insight 1 and Event 9.

---

## Area 5. News, announcements and insights

- **Files:** `src/content/news/<name>.md` (2 files).
- **Kind:** record, with optional body text.
- **Editing modes:** Add, Edit, Delete.
- **Shown on:** `/news/`, each `/news/<name>/` page, homepage "Recent activity", the news feed, site map.
- **Owner:** NewsService (proposed).

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| title | text | yes | Proposed limit 120 characters | |
| kind | one choice | yes | news, announcement, insight | Shown as a label |
| date | calendar date | yes | | |
| summary | text | yes | Proposed limit 300 characters | Used in lists and the feed |
| sample | yes or no | no | | |
| (body) | main text | no | Proposed: 100 to 250 words | Blank body shows nothing (unlike events, which show a fallback sentence) |

**Note.** The template's guide (`docs/02-editing-content.md` line 128) shows a `featured` field for news. The schema has no such field, so it has no effect.

---

## Area 6. Job openings

- **Files:** `src/content/openings/<name>.md` (2 files).
- **Kind:** record.
- **Editing modes:** Add, Edit, Delete. "Close" means set status to closed. Closed listings stay visible as "Applications closed".
- **Shown on:** `/join/` only.
- **Owner:** OpeningService (proposed).

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| title | text | yes | Proposed limit 120 characters | Both current titles start with "[Sample]" |
| type | one choice | yes | phd, mtech, research-assistant, internship, faculty, staff, other | Shown as a label |
| status | one choice | yes | open or closed | Only status decides whether the position is open |
| deadline | calendar date | no | | Printed as "Deadline …". **A past deadline does not close the position** (`join.astro` 112) |
| summary | text | yes | Proposed limit 400 characters | |
| applyEmail | email address | no | Must be a valid email address | If blank, the centre's general address is used (`join.astro` 117) |
| order | whole number | no (default 100) | | Sort order within open or closed |
| sample | yes or no | no | | |

---

## Area 7. Publications

- **Files:** `src/content/publications/<name>.md` (3 files).
- **Kind:** record.
- **Editing modes:** Add, Edit, Delete. No archive.
- **Shown on:** `/publications/` (grouped by year), `/research/` (the four most recent), each research direction page (when the area matches). The site map does not list them.
- **Owner:** PublicationService (proposed).

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| title | text | yes | Proposed limit 250 characters | |
| authors | list of names | yes, at least one | Keep the order used in the paper | Shown separated by commas |
| venue | text | yes | | Journal, conference, institution or "Preprint" |
| year | whole number | yes | Four digits | Groups the list |
| type | one choice | yes | journal, conference, workshop, preprint, thesis, other | Shown as a label |
| doi | text | no | **No check in the template.** The link is built as `https://doi.org/` followed by the value (`PublicationItem.astro` 16) | A value that already starts with a web address produces a broken link |
| url | web address | no | Valid web address | Shown as "Link" only when there is no DOI (`PublicationItem.astro` 35) |
| area | one choice | no | The four directions, or other | Lists the entry on that direction's page |
| sample | yes or no | no | | |

**Current state.** Three samples. Their titles begin "[Sample]". One DOI, `10.0000/sample.2026.001`, is a placeholder prefix and is not a real registration.

---

## Area 8. Partners and collaborators

- **Files:** `src/content/partners/<name>.md` (12 files).
- **Kind:** record.
- **Editing modes:** Add, Edit, Delete. Set status to former to move a partner to the former list.
- **Shown on:** `/partners/` (academic, industry, former), homepage (featured and present partners, academic first, `src/pages/index.astro` 78-80).
- **Owner:** PartnerService (proposed).

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| name | text | yes | | No logo field exists. Partners appear as text tiles |
| country | text | no | | |
| kind | one choice | yes | academic or industry | |
| status | one choice | yes | present or former | |
| summary | text | no | Proposed limit 200 characters | Shown on the partners page only |
| featured | yes or no | no (default no) | | Homepage only when also present. The template has no limit (proposed: six) |
| order | whole number | no (default 100) | | |

**No sample field.** Placeholder partners cannot be marked as samples, and the launch check cannot see them.

**Current state.** Twelve entries named "Partner 1" to "Partner 12". Eleven have "Country name". Every summary begins "Placeholder summary".

---

## Area 9. Funded programmes

- **Files:** `src/content/funding/<name>.md` (4 files).
- **Kind:** record.
- **Editing modes:** Add, Edit, Delete. There is no status field, so a finished programme can only be removed. Proposed: add a status.
- **Shown on:** `/research/` (funded programmes list), `/partners/` (funders list: title and funder), and the homepage count of funded programmes.
- **Owner:** FundingService (proposed).

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| title | text | yes | Proposed limit 120 characters | |
| funder | text | yes | Proposed limit 120 characters | |
| partner | text | no | Free text | Not linked to the partners list |
| amount | text | no | Proposed limit 60 characters | Kept as the funder writes it; never calculated |
| period | text | no | Proposed format: 2024–2027 | |
| summary | text | no | Proposed limit 300 characters | |
| order | whole number | no (default 100) | | |

**No sample field.** The four current programmes ("Funded programme 1" to "4", "Funder 1" to "4", amount "Amount placeholder") cannot be marked. The featured programme block on `/research/` is separate and hard-coded (Area 14).

---

## Area 10. Facilities and equipment

- **Files:** `src/content/facilities/<name>.md` (4 files).
- **Kind:** record.
- **Editing modes:** Add, Edit, Delete.
- **Shown on:** `/facilities/` only. **The About page does not use this collection.** It has its own four hard-coded cards (`src/pages/about.astro` 21-26). The template docs say otherwise (see Area 20).
- **Owner:** FacilityService (proposed).

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| name | text | yes | | |
| kind | text | yes | Free text. Proposed: a choice list with "other" | Shown as a label |
| summary | text | yes | Proposed limit 200 characters | |
| order | whole number | no (default 100) | | |
| sample | yes or no | no | | Sample label |

**Current state.** "Facility 1" to "Facility 4", kind "Facility type", summary "Placeholder description of Facility N."

---

## Area 11. Documents (PDF files)

- **Files:** `src/content/documents/<name>.md` (2 files), plus the PDFs in `public/documents/` (none supplied; the folder holds one placeholder file).
- **Kind:** record and file.
- **Editing modes:** Add (with PDF), Edit, Replace file, Delete.
- **Shown on:** `/documents/` (kind, date, title, description and a Download PDF button), site map (count only).
- **Owner:** DocumentService (proposed).

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| title | text | yes | Proposed limit 120 characters | |
| kind | one choice | yes | report, brochure, policy, form, other | Shown as a label |
| date | calendar date | no | | Shown as a long date |
| description | text | yes | Proposed limit 300 characters | |
| file | file path | no | Path such as `/documents/annual-report-2025.pdf`. Not checked for existence | Blank shows "File to be uploaded" (`documents.astro` 50). A wrong path gives a broken download link |
| order | whole number | no (default 100) | | |
| sample | yes or no | no | | |

**Current state.** Two samples, neither with a file. The button text "Download PDF" is the same on every row (accessibility issue; proposed fix: include the title).

---

## Area 12. Gallery albums

- **Files:** `src/content/gallery/<name>.md` (4 files).
- **Kind:** record.
- **Editing modes:** Add, Edit, Delete. **Photographs cannot be added.** The template has no photo field; that needs a code change (see REQUIREMENTS, proposed change P15).
- **Shown on:** `/gallery/` (album cards) and each `/gallery/<name>/` page (six placeholder frames, `src/pages/gallery/[slug].astro` 18).
- **Owner:** GalleryService (proposed).

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| title | text | yes | Proposed limit 120 characters | |
| period | text | no | e.g. "2026" | Shown above the title on the album page |
| description | text | yes | Proposed limit 300 characters | |
| order | whole number | no (default 100) | | |
| sample | yes or no | no | | Sample label on the album page only |

**Current state.** "Album 1" to "Album 4", each with "Placeholder description of Album N." Every card on `/gallery/` says "Photographs to be supplied" (`gallery.astro` 27), whatever the album holds.

---

## Area 13. Site settings

- **Files:** `src/config/site.ts` (values and navigation), `astro.config.mjs` (line 9, the domain). Both are **code files**. Editing them today means editing TypeScript or JavaScript.
- **Kind:** setting.
- **Editing modes:** Edit.
- **Shown on:** every page (header, footer, page titles, contact pages, feeds, social sharing).
- **Owner:** SiteSettingsService (proposed). Moving these values to a data file is proposed (REQUIREMENTS, P1).

| Setting | Current value | Where it appears | Rules and notes |
|---|---|---|---|
| name | Centre for Intelligent Robotics | Header, footer, page titles, feed, terms text | Required |
| shortName | CIR | End of page titles only (`Layout.astro` 20) | The header monogram "CIR" is typed in separately (`Wordmark.astro` 8) |
| institute | "Institute name" (placeholder) | Footer, top strip, privacy notice | Placeholder. The launch check does not detect it |
| instituteShort | "Institute name" (placeholder) | Header label, homepage eyebrow | Placeholder |
| instituteUrl | `https://example.org/` | Top-strip link | Placeholder domain |
| url | `https://example.org` | Page addresses in links, sitemap, feed, social image | Also in `astro.config.mjs` line 9. The launch check blocks while it contains "example." |
| description | Sentence containing "Institute name" | Default page description, feed, social sharing | Placeholder wording |
| email | `centre@example.org` | Contact pages, footer, buttons | Two pages hard-code the same address instead (Area 14, People and Gallery) |
| phone | `+00-000-000-0000` | Dialling link (digits only) | Must match `phoneHtml` |
| phoneHtml | `+00‑000‑000‑0000` (non-breaking hyphens) | The number as shown | Must match `phone` |
| address | Two lines: "Building name, campus" and "Institute name, City, State 000000" | Contact page, footer, privacy notice | Placeholder |
| social | Empty list | **Nothing.** No page reads it | Has no effect today |
| robita | Label "Student club"; address `https://example.org/student-club` | Header button (desktop and menu), footer link | The docs say it goes to GitHub. It does not (Area 20) |
| nav | Eight items: About, Research, People, News, Events, Partners, Join, Contact | Header, mobile menu, 404 page, site map | Keep to about eight. Labels must stay on one line |
| footerGroups | Five columns with four or five links each | Footer, site map | Links must point to existing pages. Section anchors such as `/research/#funding` must stay |

**Technical settings, not operator settings:** the domain (both files), the launch-check settings, and the student club address once the club site is live.

---

## Area 14. Page text (wording written into page files)

**What this means.** These sentences sit in the page files under `src/pages/`, not in content files. The operator cannot change them without editing code, until the copy is moved into a data file (REQUIREMENTS, P1). Each row gives the file and lines. Owner for all rows: PageTextService (proposed). Legal pages and fixed contact details have their own owners (Areas 13 and 15).

**Counts.** About 50 lines in page files contain the word "Placeholder" (about 22 in `about.astro`, 14 in `research.astro`, 5 in `support.astro`). The Join page has four "Sample answer" lines, and a Sample label is always shown on every FAQ answer (`join.astro` 164).

### 14.1 Home (`src/pages/index.astro`)

| Text | Lines | Says now | Notes |
|---|---|---|---|
| Hero headline | 88-90 | "Intelligent robots that perceive, reason and work alongside people." | Box is narrow, so long text wraps over many lines |
| Hero lead | 91-93 | The centre conducts research, training and product development… | Claim to confirm with the centre |
| Hero buttons | 95-96 | "Explore research", "Meet the team" | |
| Figure caption | 103 | "Fig. 1 · Planar three-link manipulator…" | Technical drawing; caption is copy |
| Statistic labels | 28, 29, 32 | "Student research projects", "Externally funded programmes", "Editions of the workshop series" | Counts include samples. The third counts only `series-1` events |
| Section headings and leads | 117, 126, 139, 150, 161 | "Four research directions", "Recent activity", "Faculty", "Selected student projects", "Partners and collaborators" | "Four" is fixed in the text |
| Button labels | 131, 140, 151, 166 | "All events and workshops →", "All people and students →", "All projects →", "All partners and collaborators →" | |
| Call-to-action blocks | 174-189 | "Study, research or teach with us"; "Collaborate or support the centre"; their text and buttons | |

### 14.2 About (`src/pages/about.astro`)

| Text | Lines | Says now | Notes |
|---|---|---|---|
| Page headline and intro | 32-33 | "Placeholder headline for the about page"; "Placeholder introduction…" | Placeholder |
| Mission heading and three paragraphs | 40, 43-45 | Placeholder text | Placeholder |
| History heading and lead | 52 | Placeholder text | Placeholder |
| Seven milestones | 11-19 | Year label "Year 1" to "Year 7", title "Milestone 1" to "7", placeholder text | Hard-coded; not a collection |
| Facilities heading and lead | 61 | "Laboratory infrastructure"; "Placeholder lead…" | |
| Four facility cards | 21-26 | "Facility 1" to "4", kind "Facility type" | **Not linked to the facilities collection** |
| Leadership: head | 82-84 | "Head"; name "CIR Head"; placeholder description | Duplicates `people/cir-head.md` but is not linked to it |
| Leadership: founder | 87-89 | "Founder"; name "Professor 1"; placeholder description | Duplicates a people entry but is not linked |
| Buttons | 72, 93-94 | "See the laboratory in the gallery →", "Meet the people", "Write to the centre →" | |

### 14.3 Research (`src/pages/research.astro`)

| Text | Lines | Says now | Notes |
|---|---|---|---|
| Page title and intro | 62-63 | Title and "Placeholder introduction…" | |
| Directions heading and lead | 69 | "Four research directions"; "Each direction groups the centre's student projects by topic." | |
| Funding heading and lead | 88 | "Externally funded programmes"; "Placeholder lead for the funded programmes." | |
| Featured programme title and lead | 114 | "Placeholder programme name"; "Placeholder lead…" | Not linked to funding entries |
| Featured programme paragraph | 118 | "Placeholder paragraph…" | |
| Featured programme facts | 122-130 | "000000", "Funder name", "Start year to end year", "Amount placeholder", "Number of partners" | |
| Consortium list | 45 | "Partner 1 (lead)" to "Partner 6" | |
| Planned outcomes | 48-55, 142 | Eight placeholder sentences; "Placeholder targets…" | |
| Publications heading and lead | 194 | Text | |
| Empty publications text | 213-214 | "The publication list is being compiled" | |

### 14.4 Research direction and project pages

| Page | Text | Lines | Notes |
|---|---|---|---|
| Direction page | Empty projects message | 54-55 | "No projects are listed in this direction yet" |
| Direction page | Empty publications message | 83-84 | |
| Project page | "About the project" and "Abstract" labels | 84 | |
| Project page | Empty abstract message | 92-93 | "Abstract to be added" |
| Project page | "More projects in …" heading | 105 | Built from the direction name |

### 14.5 People

| Page | Text | Lines | Notes |
|---|---|---|---|
| `/people/` | Title and intro | 36-37 | |
| `/people/` | Faculty lead | 43 | "Placeholder lead for the faculty section…" |
| `/people/` | Research scholars lead and empty message | 64, 86 | |
| `/people/` | M.Tech heading | 94 | |
| `/people/` | Alumni lead | 111 | "The list is not yet complete…" |
| `/people/` | "Know someone who should be listed?" box | 139-141 | **Hard-codes `centre@example.org`** (should be the site email) |
| Profile | Group labels | 19-26 | Faculty, Research scholar, M.Tech student, Research alumnus, M.Tech alumnus, B.Tech alumnus |
| Profile | Interests fallback | 79 | "To be added." |
| Profile | Biography fallback | 103-104 | "Biography to be added" |
| Profile | Projects heading and lead | 116 | |

### 14.6 News

| Page | Text | Lines | Notes |
|---|---|---|---|
| `/news/` | Title and intro | 26-27 | |
| `/news/` | Latest stories heading | 32 | |
| `/news/` | Empty message | 48-49 | "No news has been published yet" |
| `/news/` | Press and media block | 62-65 | "For journalists" and the enquiry text |
| `/news/` | Press kit message | 73-74 | Promises a press kit with logos and photographs |
| Article | "← All news" link and kind labels | 42, 14 | Kind labels also appear in `src/lib/format.ts` (32-41) |

### 14.7 Events

| Page | Text | Lines | Notes |
|---|---|---|---|
| `/events/` | Title and intro | 51-52 | Claims "international workshops" |
| `/events/` | "What is coming up" heading | 58 | |
| `/events/` | Upcoming empty message | 66-67 | |
| `/events/` | "Ask to be notified" link | 73 | |
| `/events/` | Workshop series title and lead | 80 | "Placeholder title for the workshop series" |
| `/events/` | Archive heading and lead | 89 | |
| Event page | Venue fallback | 43 | "To be confirmed" |
| Event page | Description fallback | 61 | Template sentence (Area 4) |
| Event page | Labels "Dates", "Venue", "Type" | 38-46 | |

### 14.8 Partners, facilities, publications, documents, gallery

| Page | Text | Lines | Notes |
|---|---|---|---|
| `/partners/` | Title and intro | 33 | "Placeholder lead for the partners page…" |
| `/partners/` | Section leads | 39, 48, 57, 76 | Industry lead (48) and funders lead (57) are real copy |
| `/partners/` | Call to action | 87-89 | |
| `/facilities/` | Title and intro | 19-20 | |
| `/facilities/` | Equipment lead | 24 | |
| `/facilities/` | "Laboratory spaces" section | 43-46 | "Laboratory spaces to be described" |
| `/facilities/` | Visit box | 54-56 | |
| `/publications/` | Title and intro | 31-32 | |
| `/publications/` | Empty message | 66-67 | |
| `/publications/` | "Missing a paper?" box | 77-79 | Says the centre checks entries before adding them. That is a process promise |
| `/documents/` | Intro | 26 | |
| `/documents/` | "Available documents" heading | 30 | |
| `/documents/` | "File to be uploaded" | 50 | |
| `/documents/` | Empty message | 57-58 | |
| `/gallery/` | Title and intro | 15-16 | |
| `/gallery/` | Albums lead | 20 | "Photographs are being collected for every album." |
| `/gallery/` | Card text | 27 | "Photographs to be supplied" on every card |
| `/gallery/` | Send-photos box | 44-45 | **Hard-codes `centre@example.org`** |
| Album page | Lead | 31 | |
| Album page | Frame labels | 38, 41 | "Placeholder 1: photograph to be supplied" |
| Album page | Send-photos box | 48-49 | Uses the site email correctly |

### 14.9 Join, Support, Contact, Search, 404, site map

| Page | Text | Lines | Notes |
|---|---|---|---|
| `/join/` | Title and intro | 73-74 | |
| `/join/` | Four routes | 29-46 | Eligibility claims (for example "Eligibility and dates are given in each listing") |
| `/join/` | Four steps | 48-53 | |
| `/join/` | Openings lead | 94 | "Closed calls stay listed for reference…" |
| `/join/` | Empty openings message | 128-129 | |
| `/join/` | FAQ lead | 154 | Says sample answers "will be replaced" |
| `/join/` | FAQ questions | 56-59 | Four questions; answers read "Sample answer. …" |
| `/join/` | Sample label on FAQ answers | 164 | **Always shown**, whatever the answer |
| `/support/` | Title and intro | 41-42 | |
| `/support/` | Giving lead | 47 | "Donations are made to the institute and recorded for the centre." |
| `/support/` | Two giving routes | 11-22 | Cheque route says "Payable to 'Institute name'" (14) |
| `/support/` | Bank transfer text | 18-20 | Says account details are given on request and are not printed on the site (a policy) |
| `/support/` | Tax lead and notes | 64, 27, 31 | "Placeholder notes…"; finance office must confirm |
| `/support/` | Recognition lead | 80 | "A name is listed only after the donor has confirmed…" |
| `/support/` | Donor tiers | 35, 86 | Platinum, Gold, Silver, Bronze; "Names to be confirmed" |
| `/support/` | Contact box | 98-100 | |
| `/contact/` | Title and intro | 23 | |
| `/contact/` | Enquiry types | 11-16 | Four types with text |
| `/contact/` | Campus note | 44 | "Placeholder note: describe how to find the centre on the campus." |
| `/contact/` | No-form note | 64-66 | Claims no personal data is stored on the site |
| `/search/` | Intro and messages | 10, 17, 30 | |
| `/search/` | Search box placeholder text | 38 | Interface text |
| 404 page | Heading and text | 10-12 | |
| Site map | Intro | 38 | |
| Site map | Main-page list typed in | 43-52 | Must be kept in step with navigation (Area 13) |

### 14.10 Layout, header and footer

| Where | Text | Lines | Notes |
|---|---|---|---|
| `Layout.astro` | Default description | 19 (uses site description) | Placeholder through site settings |
| `Layout.astro` | Skip-link text | 57 | "Skip to content" (interface) |
| `Footer.astro` | Footer paragraph | 13-15 | "Research, training and product development…" |
| `Footer.astro` | Copyright line | 52 | Year is automatic |
| `Header.astro` | Hidden text on the club link | 33 | "(student club website)" |

### 14.11 Internal page

`src/pages/styleguide.astro` is an internal component page. It must be deleted before launch (blocker in the launch check). It is not content.

---

## Area 15. Legal pages

- **Files:** `src/pages/accessibility.astro`, `src/pages/privacy.astro`, `src/pages/terms.astro`.
- **Kind:** page text, with fill-in fields in square brackets and a "Draft for review" notice in each file (line 13).
- **Editing modes:** Edit text; complete the bracket fields. **The notice must not be removed by the tool.** Removing it is a technical step after the institute approves the text.
- **Owner:** LegalPageService (proposed). The text must come from the institute's legal office. The model must not draft legal text.

| File | Bracket field (line) | Needs |
|---|---|---|
| accessibility | "[number] working days" (39) | Response time |
| accessibility | "[Add the institute's accessibility or grievance contact here.]" (42) | Contact |
| accessibility | "[date]" twice and "[Record the tools and browsers used.]" (45) | Review date and test record |
| privacy | "[retention period]" (22) | How long enquiries are kept |
| privacy | "[Name of the data controller, as set by the institute.]" (34) | Controller name |
| privacy | "[date]" (38) | Last update date |
| terms | "[Governing law and jurisdiction, as set by the institute.]" (36) | Legal wording |

**Statements that must be kept true.**
- Accessibility (lines 32-34): "Some photographs have not yet been supplied", "Some entries are marked as sample content", "On small screens the in-page navigation scrolls sideways". These go stale as content changes.
- Privacy (line 18): "no analytics, advertising or tracking cookies, and no contact form and no accounts". Any change to this (for example adding analytics) makes the notice wrong.

---

## Area 16. Images and files

| File or type | What it is | Now | Who changes it | Rules |
|---|---|---|---|---|
| `public/people/<name>.jpg` | Portraits | None supplied | Replace file | JPG or PNG; at least 800 px tall; about 4:5; consent needed |
| `public/documents/<name>.pdf` | Documents | None supplied | Upload | PDF only; proposed maximum 20 MB |
| `public/og-default.png` | Social-sharing image | A 1200 × 630 image that shows "INSTITUTE NAME" and "example.org" | Replace file (technical sign-off) | 1200 × 630 px. The launch check only checks that the file exists, so the placeholder passes (`scripts/launch-check.mjs` 75-79) |
| `public/favicon.svg` | Browser tab icon | Present | Technical only | |
| Gallery photographs | Not supported | None | Needs code change | Proposed (P15) |
| Partner logos | Not supported | Text tiles | Needs code change | Proposed |

---

## Area 17. Placeholder and sample markers

| Marker | Where | Count | Launch check today |
|---|---|---|---|
| `sample: true` | Areas 1, 3, 4, 5, 6, 7, 10, 11, 12 | 99 entries | **Blocker**: lists every file |
| "[Sample]" in titles | 2 openings, 3 publications, 2 documents | 7 | Not checked |
| "Placeholder" text in entries | 62 bios, 11 project bodies, 9 event bodies, 2 news bodies, 12 partner summaries, 4 funding summaries, 4 gallery descriptions, 4 facility summaries | 108 entries | **Not checked** |
| "Partner N", "Funder N", "Country name", "Amount placeholder", "Facility type", "Venue name, City" | Partners, funding, facilities, events | Many | **Not checked** |
| "Sample answer" | 4 FAQ answers on `/join/` | 4 | Not checked |
| "Placeholder" in page files | About 50 lines (Area 14) | About 50 | **Not checked** |
| "Institute name", "example.org", "+00-000-000-0000", "Building name, campus" | Site settings, `astro.config.mjs`, `og-default.png`, `support.astro` 14 | Several | Only the site URL (blocker) and the student club URL (warning) |
| "centre@example.org" | Site settings, `people.astro` 140, `gallery.astro` 45 | 3 | Not checked |
| Bracket fields | 3 legal pages | 9 | Warnings |
| "Draft for review" notice | 3 legal pages | 3 | **Blocker** |
| Internal styleguide page | `src/pages/styleguide.astro` | 1 | **Blocker** |

**The gap in one sentence.** Once the 99 sample entries are removed, the launch check would pass while placeholder sentences remain in the pages and in the partner, funding and research data. A launch check that passes would be misleading.

**Statistics that count samples.** The homepage counts projects (11) and funded programmes (4) including samples, and the research page shows "11 projects" in its lead (`research.astro` 160). Counts will be wrong until samples are removed.

---

## Area 18. Things that depend on each other

Changing one of these without the other breaks something, often without any build error.

| Dependency | Where | What breaks if one side changes |
|---|---|---|
| Student name ↔ person name | Project `students` ↔ person `name` | Exact match. A spelling difference silently removes the link and the project from the person's profile (`research/projects/[slug].astro` 33; `people/[slug].astro` 33) |
| Research direction id | Four file names ↔ schema list (`src/content.config.ts` 12) ↔ project and publication `area` values ↔ research pages | Renaming a file breaks projects and publications silently |
| File name ↔ web address | Every entry | Renaming a file changes its address. No redirects exist |
| `series-1` | Event `series` value ↔ `events.astro` 21 ↔ `index.astro` 31 | Any other series name is never shown, and the homepage count drops to zero |
| Site address | `site.ts` line 13 ↔ `astro.config.mjs` line 9 | Canonical links, sitemap and feed use different domains if only one changes |
| Telephone | `phone` ↔ `phoneHtml` | Dialling link and displayed number can disagree |
| Section anchors | Footer links (`site.ts` 61-62, 70) and buttons (`index.astro` 151, `partners.astro` 69) use `#projects`, `#funding`, `#featured`, `#alumni` | Rename a section id and the link stops working |
| Homepage limits | Four faculty (`index.astro` 68-71); four featured projects (73-76); three recent items (47-66) | Extra entries are silently hidden |
| Funding partner | Funding `partner` text ↔ partner `name` | Not linked; typos are not caught |
| Opening contact | Blank `applyEmail` ↔ centre email | Applications go to the general address |
| DOI and URL | Publication `doi` and `url` | A URL is hidden when a DOI is present (`PublicationItem.astro` 35) |
| Leadership | About page "CIR Head" and "Professor 1" ↔ people entries | Two copies of the same facts |
| Facilities | `facilities` collection ↔ About page cards | Two separate lists; editing one does not change the other |
| Address and privacy | Site address ↔ privacy notice (`privacy.astro` 34) | A new address must be reflected in the privacy notice |

---

## Area 19. Not editable through the operator tool (structure)

These are part of the site's structure. Changing them needs a developer, and the operator tool should not offer them.

- Page list and page addresses. Adding a page needs code.
- The homepage layout, the colours, fonts, spacing, and the technical drawing (`src/components/ManipulatorFigure.astro`).
- The choice lists that the schema enforces: group, kind, type, status, area. The tool can show them as dropdowns, but adding a value needs a code change.
- Layout counts: four faculty and four featured projects on the homepage, three recent items, four latest publications, six placeholder frames per album.
- The XML sitemap's list of top-level pages (`src/pages/sitemap.xml.ts` 6-25); the feed's 50-item limit (`rss.xml.ts` 26); `robots.txt` rules.
- Accessibility features, print styles and reduced-motion behaviour.
- Build configuration: `package.json`, `package-lock.json`, `astro.config.mjs` (except the domain), `.gitignore`, `.gitattributes`, `tsconfig.json`.

---

## Area 20. Where the template's own documents disagree with the code

Each row is a statement an operator or the technical contact might rely on.

| Document and line | What it says | What the code does |
|---|---|---|
| `docs/02-editing-content.md` 18; `docs/03-handover-checklist.md` 27 | The About page shows the facilities collection | About has four hard-coded cards (`about.astro` 21-26) |
| `docs/01-site-overview.md` 166 | Every collection can carry `sample: true` | Research, partners and funding have no sample field (`content.config.ts` 44-52, 132-156) |
| `README.md` 57 | Every placeholder has `sample: true` | Partner, funding and research placeholders do not |
| `docs/01-site-overview.md` 166 | Sample entries are labelled "Sample" on the site | Not on the scholar, M.Tech and alumni lists (`people.astro` 65-82, 95-104, 116-134) or on the homepage faculty cards (`index.astro` 143). Every FAQ answer always has the label (`join.astro` 164) |
| `docs/01-site-overview.md` 186 | The student club pointer goes to the club's GitHub repository | It goes to `https://example.org/student-club` (`site.ts` 31) |
| `docs/02-editing-content.md` 118 | Older events move to the archive | The archive lists every event, including upcoming ones (`events.astro` 24-28) |
| `docs/02-editing-content.md` 117 | Events with the same series name are grouped | Only `series-1` is shown (`events.astro` 21) |
| `docs/02-editing-content.md` 128 | News has a `featured` field | No such field in the schema (`content.config.ts` 68-77) |
| `docs/02-editing-content.md` 153 | Open positions show an apply link when `applyEmail` is set | Every open position shows the apply button, falling back to the centre address (`join.astro` 116-117) |
| `docs/02-editing-content.md` 164-165 | Example publication has both `doi` and `url` | Only the DOI is shown (`PublicationItem.astro` 35) |
| `docs/02-editing-content.md` 67 | Homepage must start with `https://` | The schema accepts any valid web address |
| `docs/01-site-overview.md` 160 | The XML sitemap is built from content, so new entries appear automatically; only the HTML site map needs manual changes | The XML sitemap also has a hand-kept list of top-level pages (`sitemap.xml.ts` 6-25), which must also be updated for a new page |
| `docs/01-site-overview.md` 172 | The build checks broken links to content | No link check exists; html-validate checks markup only |
| `docs/03-handover-checklist.md` 218 | The launch check confirms the domain in both `astro.config.mjs` and `site.ts` | Only `site.ts` is checked (`scripts/launch-check.mjs` 59-66) |
| `docs/01-site-overview.md` 184 | "Most project abstracts are placeholders" | All 11 are |
| `scripts/launch-check.mjs` 78 | "See docs/06-handover-checklist.md" | No such file; the handover is `docs/03-handover-checklist.md` |
