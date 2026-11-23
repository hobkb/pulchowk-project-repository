# Pulchowk Project Repository Strategy

## Vision

<!-- vision: author-approved 2026-11-23 -->

The Pulchowk Project Repository exists so that engineering work already done at Pulchowk Campus is found, understood, and built on instead of repeated or lost.
It serves students deciding what to build, supervisors judging whether an idea is new, and the department reviewers who keep the record accurate.
It turns project reports and the code, data, and demos behind them into reviewed, structured, searchable catalogue records.
It owns exactly one thing: Pulchowk Campus's authoritative catalogue of its projects and the people who made them.

### The record is the product

Every project surface leads with metadata: title, authors, supervisor, department, level, batch, and cluster.
Classification uses fixed, validated vocabularies, such as the seven research clusters and the canonical departments, and the API rejects values outside them.
Corrections only ever add information; an empty incoming value never erases a value a person entered by hand.
A project is published once and atomically, and a second publish of the same report is refused.
Each student and supervisor has a campus-visible page listing the projects they authored or supervised, drawn from the same reviewed records.

### A person verifies before anything is published

Students submit their own reports and artifacts, and reviewers can upload on their behalf; both enter the same review queue.
Any one author may submit a project; teammates and the supervisor are not asked first, because review of the record is the gate.
Extraction from a PDF produces a draft, never a record.
A department reviewer checks every extracted field against the source document before the project goes live.
No extraction is confident enough to skip that review, however clean it looks.
Pipeline internals, logs, and extraction confidence are shown to reviewers and never to readers.

### Reports stay with the department

The repository indexes and describes each project; it does not redistribute the full report or its artifacts.
Readers see the metadata, the abstract, and the structured sections the department chose to expose.
Code, datasets, and demo videos sit behind the same access gate as the full report.
No response a reader can trigger contains verbatim report text, artifact files, or PDF bytes, unless that reader holds an approved access request for that project.
Access is requested inside the application and decided by department reviewers, so an approval actually unlocks the report and the decision is on record.
Authors do not grant access to their own reports; the department holds the consent-of-use terms and answers for them.
Restricted surfaces show a drawn placeholder, never real content that is blurred or hidden.

### Measurements say only what they can support

Similarity and search thresholds are measured against this corpus and stored with the corpus they were measured on, so staleness is visible.
Raw similarity scores and percentiles never leave the system, not to readers and not to reviewers or committees; a result is explained by the subject matter it shares.
No result claims copying or originality; the strongest statement is that related work exists and should be read.
The research assistant may draw on full report text to answer, and cites the projects it used.
It may explain a restricted report's method and results in its own words to any reader, and quotes report body verbatim only to a reader with an approved request for that project.
A capability that does not exist is not imitated: no mock data presented as real, and no disabled input implying a working assistant.

### A campus system

Sign-in is limited to Pulchowk institutional accounts, and every user completes an institutional profile before using the repository.
Nothing, including titles, abstracts, and person pages, is readable without signing in or indexed by public search engines.
Privileged roles are granted only by an administrator; reviewers cannot grant roles to others.
A reader never sees an administrative control, not even a disabled one.
The interface reads as department infrastructure carrying the institution's name and crest, not as a generic dashboard or a marketing site.
Discovery is the center of gravity: search and browse come first, and submission is a side door into review.
Supervisors can post open project ideas, each linked to related past work, so students see what has been done before they choose.

### Scope

It is not a plagiarism checker and does not issue originality verdicts.
It is not a publishing or distribution channel for full reports or artifacts.
It is not a grading, proposal-approval, or project-management system for courses.
It is not a platform for other campuses; it serves Pulchowk alone.
It is not a general academic search engine; its answers describe this repository only.

A change aligns when it makes a reviewed project record easier to find, understand, or correct, while report content stays behind the department's access decision.
A change aligns when every number, label, or claim it shows a user is backed by a measurement on this corpus.
A change should be resisted when it publishes anything without human review, exposes verbatim report text, artifacts, or PDF bytes to a reader without an approved request, or makes any content reachable from outside the campus sign-in.
A change should be resisted when it shows anyone a raw score or verdict, presents a capability more confidently than the system supports, or pulls the product toward distribution or decoration over discovery.
