# Discovery Interview Guide

_For: Dr. Biruk Bekele, Dr. Daniel Gizaw · Goal: validate the problem before we build past Phase 1_

We have not yet confirmed, with the people who would use Empowered Care, which problem
hurts most and whether they would pay for (or sponsor) a fix. This guide turns 6–8
conversations into decisions about the build. Each conversation is 30–45 minutes.

## Rules for every interview
- **Ask about the past, not the future.** "Tell me about the last outbreak you caught
  late" beats "Would you use a tool that…?". People are polite about hypotheticals.
- **Don't pitch until the last five minutes.** The first 30 minutes are for listening.
- **Ask for artefacts.** A blank PHEM form, a bulletin, a screenshot of the DHIS2 data
  set, an example sitrep. These are worth more than opinions.
- **Write down exact words.** Their phrasing becomes our product language.
- After each interview, fill in the decision table at the end within 24 hours.

## Who to talk to

| # | Person | Why them | Priority |
|---|---|---|---|
| 1 | EPHI PHEM directorate / PHEOC epidemiologist | Primary user and buyer; owns outbreak declaration | Must |
| 2 | EPHI EIOS or media-monitoring focal person | Tells us what event-based surveillance looks like today | Must |
| 3–5 | 2–3 Regional Health Bureau PHEM officers (one pastoralist region, e.g. Somali or Afar; one highland, e.g. Amhara) | Regional users; reporting realities differ sharply by region | Must |
| 6 | EPI (immunization) programme officer | Second buyer for the measles risk map; owns campaign planning | Should |
| 7 | EPIDEMIA team (Amhara Public Health Institute / Bahir Dar University) | Built an operational early-warning system in Ethiopia; lessons on adoption | Should |
| 8 | HISP Ethiopia or a DHIS2 administrator | Data structure, access process, facility-level reporting | Should |

## Core questions (everyone)
1. Walk me through how you found out about the last measles outbreak in your area.
   Who told you first, how, and how many days after the first case?
2. Which source usually tells you first: DHIS2 weekly data, a phone call, a health
   worker, the community, a hospital, media?
3. What takes most of your week? (Listen for: compiling reports, chasing late reports,
   cleaning data, investigating.)
4. Tell me about an outbreak that was caught late. What would have had to be different
   to catch it a week earlier?
5. When a signal comes in, how do you decide whether to investigate? What makes you
   ignore one?
6. What do you produce every week (bulletin, sitrep, briefing)? Who reads it? How long
   does it take?
7. If a tool did one thing for you tomorrow, what would you stop doing?

## Role-specific questions

**EPHI PHEM / PHEOC**
- Which measles thresholds do you actually apply today, and at what level (kebele,
  woreda, facility catchment)? Have they changed since the 2023 PHEM guideline?
- Do you see facility-level PHEM data in DHIS2, or only woreda totals?
- How long does it take from a facility's weekly report to it being visible to you?
- Who approves data access for a pilot, and what would they need to see first?
- **Data governance:** may report text or images that can identify patients be processed
  by a cloud AI service outside Ethiopia (for example Google's), or must all processing
  stay on servers in Ethiopia? Does the answer change for de-identified or aggregate data?
- Does EPHI (or the Ministry) have a data centre or GPU server that could host an
  AI model, and who would operate it?

**EIOS / media monitoring**
- Does anyone scan Amharic, Afaan Oromo, Somali or Tigrinya media today? How?
- How many signals a week, and how many turn out to be real?
- How do community-based surveillance triggers reach you today?

**Regional PHEM officers**
- Do health extension workers in your region have working smartphones and data? Is
  eCHIS used daily, sometimes, or rarely?
- If a health worker wanted to report a cluster of fever and rash today, what would they
  do? SMS, call, paper, eCHIS, Telegram?
- How much weekly reporting still starts on paper? How long before it is entered?
- Which woredas go "silent" (stop reporting)? Why?

**EPI programme**
- How do you decide where to run measles catch-up campaigns? How often is the WHO
  measles risk assessment done, and by whom?
- Would a monthly zone-level risk ranking change any decision you make? Which one?

**EPIDEMIA team**
- What made regional staff actually use EPIDEMIA week after week? What made them stop?
- What did you learn about data delays and completeness in Amhara?

## How answers change the build

| If we hear… | Then we… |
|---|---|
| Facility-level PHEM data is available in DHIS2 | Model and detect at facility-catchment level as well as woreda |
| Health workers use SMS far more than smartphones | Build the SMS adapter for `/intake/trigger` first |
| eCHIS is used daily | Integrate with eCHIS instead of a separate channel |
| Telegram is common among regional staff | Build a Telegram adapter for officers (not for scraping) |
| Most reporting starts on paper and waits weeks | Prioritise measuring photo-OCR accuracy on real forms |
| Bulletins/sitreps take many hours a week | Move the sitrep generator earlier |
| EPI would act on a monthly risk ranking | Make the risk map the headline product for the first demo |
| Thresholds differ from WHO AFRO defaults | Update `config` thresholds and the fusion ladder |
| Identifiable data must stay in Ethiopia | Run the text and vision models on-premises through `LLMProvider` (SYSTEM_SPEC 11.1); until then process only de-identified text in the cloud |
| Nobody would act on a signal without a phone call | Add a "call the reporter" step to the triage workflow |

## Decision log (fill in after each interview)

| Date | Person / role | Biggest pain (their words) | First source of outbreak news | Channel reality | Would sponsor a pilot? | Build change |
|---|---|---|---|---|---|---|
| | | | | | | |
