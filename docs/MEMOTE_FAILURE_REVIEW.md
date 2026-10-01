# iMcBath: all 80 failed checks and 8 skipped cases

This review explains **every nonpassing JUnit case** in the preserved MEMOTE 0.17.0 audit: **80 failed + 8 skipped = 88 individually analyzed cases**. The 59 passing cases remain in the original audit; six additional false SBO passes discovered during source review are noted separately below. No model chemistry or coefficient has been changed.

The principal conclusion is that **80 failures do not mean 80 independent biological defects**. Many cases repeat the same annotation gap across database namespaces. Some requirements are unsuitable for this bacterium; several assertions are defective. There are also material chemistry, representation and network findings that deserve scientific review before SYMBIONT calibration.

## Read and use this review

- [Searchable HTML review](../reports/failure-review/review.html) — filter all 88 cases by group, priority or text; expand complete evidence.
- [88-row CSV](../reports/failure-review/review.csv) — one analyzed check per row.
- [Complete structured review](../reports/failure-review/review.json) — exact testcase names, all affected data, interpretation and sources.
- [Affected-entity index](../reports/failure-review/affected-entities.csv) — every entity/group listed by the underlying nonpassing tests; repeated entities retain their case links.
- [Chemistry details](../reports/failure-review/chemistry-details.json), [network details](../reports/failure-review/network-details.json), [annotation details](../reports/failure-review/annotation-details.json) and [SBO source audit](../reports/failure-review/sbo-source-audit.json).

**Identity:** unchanged upstream commit `f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160`; SBML SHA-256 `c2591237d8968164faeb8fafe741a9a42f95131b919086d5eb1a14b159fee092`. The baseline audit began on 2026-10-01 at 18:42:55 UTC. See [run metadata](../reports/baseline-audit/run-metadata.json), [JUnit](../reports/baseline-audit/junit.xml) and [raw results](../reports/baseline-audit/memote-results.json).

The raw **54.08% score is unchanged** and is not prediction accuracy. Zero JUnit `error` elements does **not** mean no software exceptions: two `TypeError` exceptions occurred during test calls and are recorded as failures. Some annotation messages use a different denominator from the proportion of annotated entities; each case below states its denominator explicitly. “Source data count” can mean a list size or number of overlapping groups, not necessarily unique defects.

## Exact reconciliation

| Failed group | Cases | IDs |
| --- | ---: | --- |
| Annotation | 57 | F01–F57 |
| Basic model/GPR/duplicates/medium | 6 | F58–F63 |
| Biomass | 3 | F64–F66 |
| Consistency/network | 9 | F67–F75 |
| SBO roles | 5 | F76–F80 |
| **Failed total** | **80** | **F01–F80** |
| **Skipped total** | **8** | **S01–S08** |

Case identifiers follow the order within each status in the original JUnit file, including parameterized namespaces. None has been merged away.

## What should be improved first

| Order | Proposed work | Biological/computational reason | Acceptance gate |
| --- | --- | --- | --- |
| 1 | Repair or supplement the audit harness; preserve raw results | Fast-growth assertion is reversed; ten SBO predicates are reversed; dead-end assertion compares a list with zero; duplicate/medium reporting raises TypeErrors | Small known-good/known-bad fixtures establish correct test behavior; compare raw and interpreted outcomes without concealing findings |
| 2 | Curate fatty-acid units and the entire associated charge convention, then reconstruct the biomass mass ledger | `MC_Average_FattyAcid` mixes a formula scaled by 1000 with an unscaled output coefficient; biomass diagnostic is 0.902411 g per nominal unit | Joint element/charge consistency and a documented dry-weight basis; source-supported coefficients and recalculated yields |
| 3 | Review `XANt2pp`, the redox/carrier charge defects and membrane-Q8 test coverage | Named xanthine transport actually duplicates guanine transport; several electron/charge conventions disagree; existing Q8 in `im` is missed by cytosol-only lookup | Correct identities, compartments and gene evidence; independent energy-cycle and phenotype checks |
| 4 | Apply verified annotation repairs in a separate derivative | 570 reaction references use legacy `seed`; 64 SEED compound records have whitespace; some references contain serialization corruption | Verified identifiers with provenance; unchanged stoichiometric matrix, bounds, objectives and numerical reference for metadata-only work |
| 5 | Review missing GPRs, PLP representation and condition-dependent network gaps | 119 reactions lack GPRs; active PLP is missing; 66/256 blocked reactions are explicitly zero-bounded | Evidence-based scope/GPR decisions, no arbitrary gapfill, and transparent bound choices |
| 6 | Restore historical phenotype tests and add independent SYMBIONT validation | Published data were not configured in this audit; no new essentiality or process validation was supplied | Condition-level predictions, measured mass/substrate balances and held-out validation with uncertainty |

Priority labels in individual records: P0 = audit interpretation first; P1 = high-priority scientific/functional review; P2 = curation/completeness; P3 = applicability or low-risk interpretation. They are planning priorities, not measured effect sizes. A P3 namespace may appropriately remain absent.

## Scientific findings that affect interpretation

- **Mass balance:** 7 raw flags reduce to one substantial encoded defect plus six floating-point residuals. Exact-decimal arithmetic balances those six; changing their chemistry to eliminate machine roundoff would be inappropriate.
- **Charge balance:** 11 raw flags comprise ten exact discrepancies and one floating-point-only flag (`MC_AFAA`). The three exact lipid discrepancies of ±0.001 must not be discarded as roundoff; the other seven are unit-scale. Review shared carrier definitions, rather than inserting protons into otherwise atom-balanced equations.
- **Fatty-acid sensitivity diagnostic:** a temporary in-memory change of the average-fatty-acid output coefficient from 1 to 0.001 eliminated its elemental residual but left charge residual +0.998. Reference pFBA growth changed from 0.225583 to 0.194778 h⁻¹ (−13.66%). This is an **unaccepted diagnostic candidate**, not a calibrated prediction or complete correction. No altered model was saved.
- **Biomass:** the 9.76% mass shortfall requires a monomer/polymer, lipid, water/by-product and maintenance ledger. The close correspondence with polymerization-like water is a lead to investigate, not permission to delete water or multiply every coefficient by 1/0.902411.
- **Network:** 256 blocked reactions, 74 orphans, 81 dead ends, 58 isolated species, 329 unproducible and 369 unconsumable metabolites are heavily overlapping findings. The 51-cycle diagnostic also resets internal bounds and maintenance, so it is not a direct report of cycles under the SYMBIONT profile.
- **Applicability:** CCDS/HPRD/EcoGene requirements must not be satisfied by inserting human/mouse/E. coli identities into Bath genes. Four skipped quinone couples have no identified counterpart in the model; Q8 is a distinct compartment-lookup gap.

The full equations, Decimal residuals, original notebook evidence and before/after diagnostic results are in the linked chemistry appendix. Detailed interpretation of every case follows.

## Individual failed cases


<a id="f01"></a>

### F01 — `test_metabolite_annotation_presence`

**P2 · missing all annotation**

**Observed:** 21/879 metabolites (2.39%) have no parsed annotation at all.

**Biological meaning:** Missing identities include both defined small molecules (for example thiocyanate tcynt_c and allophanate allphn_c) and deliberate averaged lipid/macromolecular entities. The latter are not single molecules and should not receive fictitious exact structure IDs.

**Suggested improvement:** For defined chemicals, curate verified identity references and meaningful names. For mc_fattyacid_c and *_MC_* averaged pools, document compositional definitions, source measurements and units with qualified class/provenance annotations.

**How to verify:** Every component has a scientifically justified identity or abstraction definition; no averaging pool is mislabeled as one exact chemical.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [MEMOTE annotation-test implementation](https://memote.readthedocs.io/en/latest/_modules/memote/support/annotation.html)


<a id="f02"></a>

### F02 — `test_reaction_annotation_presence`

**P2 · missing all annotation**

**Observed:** 53/913 reactions (5.81%) have no parsed annotation.

**Biological meaning:** The missing set contains BIOMASS_Mcapsulatus, methane exchange/transport, demand/sink pseudo-reactions, custom fatty-acid lumped reactions and ordinary transport. A missing reaction database link is not itself evidence of absent enzyme or wrong stoichiometry.

**Suggested improvement:** Annotate bookkeeping roles using appropriate SBO terms and document biomass/lumping derivations; add exact external reaction identifiers only when chemistry genuinely matches. Keep reaction/GPR evidence distinct.

**How to verify:** Each reaction has a correct role and provenance; pseudo-reactions remain explicitly nonenzymatic abstractions, and chemical aliases are independently verified.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [MEMOTE annotation-test implementation](https://memote.readthedocs.io/en/latest/_modules/memote/support/annotation.html)


<a id="f03"></a>

### F03 — `test_gene_product_annotation_presence`

**P2 · missing all annotation**

**Observed:** 730/730 genes (100%) have empty parsed annotation dictionaries.

**Biological meaning:** MCA locus tags and GPR expressions exist, but there are no machine-readable gene/protein cross-references. This weakens assembly/strain traceability and transcriptome/proteome joins; it does not mean the model has no genes.

**Suggested improvement:** Build a versioned mapping from the published Bath genome feature table to MCA locus tags and verified RefSeq/UniProt/NCBI records, preserving ambiguous and retired mappings. Do not use unrelated-species databases to fill gaps.

**How to verify:** Every represented gene has a supported locus/assembly provenance record; available sequence cross-references are taxonomically and version-correct.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [NCBI Reference Sequence Database](https://www.ncbi.nlm.nih.gov/refseq/)


<a id="f04"></a>

### F04 — `test_metabolite_annotation_overview[pubchem.compound]`

**P3 · namespace coverage gap**

**Observed:** 879/879 metabolites lack the pubchem.compound namespace (100.00%); 0 carry that key.

**Biological meaning:** PubChem CID identifies a chemical structure. Missing CIDs impede structure joins but do not invalidate flux balance.

**Suggested improvement:** Map only defined chemical identities to verified CIDs; distinguish Compound CID from Substance SID. Averaged lipids and abstract pools may have no exact CID.

**How to verify:** Verified compound-level matches, with structure/protonation checks and documented not-applicable pools.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [PubChem CID versus SID record identifiers](https://pubchem.ncbi.nlm.nih.gov/docs/quick-search)


<a id="f05"></a>

### F05 — `test_metabolite_annotation_overview[kegg.compound]`

**P3 · namespace coverage gap**

**Observed:** 63/879 metabolites lack the kegg.compound namespace (7.17%); 816 carry that key.

**Biological meaning:** KEGG C identifiers connect metabolites to compound and pathway records. Separate G glycan and D drug identifiers are different namespaces.

**Suggested improvement:** Validate C-number identity against structure, charge and stereochemistry. Preserve genuine G/D cross-references under their own namespaces instead of changing their letters.

**How to verify:** All retained kegg.compound values resolve as the intended C-entry; absence has a documented reason.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [KEGG identifiers and database namespaces](https://www.genome.jp/kegg/docs/weblinks.html)


<a id="f06"></a>

### F06 — `test_metabolite_annotation_overview[seed.compound]`

**P3 · namespace coverage gap**

**Observed:** 88/879 metabolites lack the seed.compound namespace (10.01%); 791 carry that key.

**Biological meaning:** ModelSEED compound links support reconstruction interoperability. A missing cross-reference is not a missing metabolite.

**Suggested improvement:** Use the official compound table and identity evidence; do not create a cpd number from the local name. Clean whitespace on already verified IDs before seeking new matches.

**How to verify:** Applicable mappings resolve to the same chemical identity, with unmapped lumped entities documented.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [ModelSEED authoritative biochemical database](https://github.com/ModelSEED/ModelSEEDDatabase)


<a id="f07"></a>

### F07 — `test_metabolite_annotation_overview[inchikey]`

**P3 · namespace coverage gap**

**Observed:** 879/879 metabolites lack the inchikey namespace (100.00%); 0 carry that key.

**Biological meaning:** An InChIKey is a compact structure key. None are present, so structure-based lookup is less convenient; a key does not itself prove biological presence.

**Suggested improvement:** Generate standard keys only from chemically reviewed structures using a pinned InChI implementation. Do not assign an exact-molecule key to average lipids or undefined polymers.

**How to verify:** Each added key agrees with the reviewed full InChI/structure and standard version; undefined species are explicitly excluded.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [InChI Trust technical FAQ](https://www.inchi-trust.org/technical-faq/)


<a id="f08"></a>

### F08 — `test_metabolite_annotation_overview[inchi]`

**P3 · namespace coverage gap**

**Observed:** 245/879 metabolites lack the inchi namespace (27.87%); 634 carry that key.

**Biological meaning:** Full InChI supports structural identity and distinguishing stereoisomers. Missing structure information weakens chemical deduplication, not the LP solve itself.

**Suggested improvement:** Recover verified structures for defined small molecules, remove empty URI stubs in a derived copy, and document abstract species that lack a unique molecular graph.

**How to verify:** Roundtrip SBML has no empty InChI resources; retained InChIs resolve to the intended stereochemical and protonation state.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [InChI Trust technical FAQ](https://www.inchi-trust.org/technical-faq/)


<a id="f09"></a>

### F09 — `test_metabolite_annotation_overview[chebi]`

**P3 · namespace coverage gap**

**Observed:** 130/879 metabolites lack the chebi namespace (14.79%); 749 carry that key.

**Biological meaning:** ChEBI provides curated chemical identities and classes, useful for charge/state reconciliation. A broad chemical class is not identical to a specific molecular species.

**Suggested improvement:** Map each defined entity to a verified accession with its appropriate state; use class annotations carefully for macromolecules or generic pools.

**How to verify:** The URI syntax and current accession are valid and the ontology relation matches the model entity; no arbitrary IDs are invented.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [ChEBI scope and chemical entities](https://www.ebi.ac.uk/chebi/about)


<a id="f10"></a>

### F10 — `test_metabolite_annotation_overview[hmdb]`

**P3 · namespace coverage gap**

**Observed:** 389/879 metabolites lack the hmdb namespace (44.25%); 490 carry that key.

**Biological meaning:** HMDB is a human-metabolome resource. Shared chemicals can have useful cross-references, but bacterial-specific compounds and model abstractions need not occur there.

**Suggested improvement:** Add HMDB links only for verified shared chemical identities; document bacterial-specific and lumped entities as outside coverage. Check current accession conventions independently of the bundled regex.

**How to verify:** Correct optional matches and a reasoned coverage report, rather than forced 100% human-database coverage.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [Human Metabolome Database scope and seven-digit identifiers](https://www.hmdb.ca/about)


<a id="f11"></a>

### F11 — `test_metabolite_annotation_overview[reactome]`

**P3 · namespace coverage gap**

**Observed:** 497/879 metabolites lack the reactome namespace (56.54%); 382 carry that key.

**Biological meaning:** Reactome distinguishes chemical physical entities, reactions and species-specific events. Shared chemicals can be cross-referenced without implying that a human pathway operates in Bath.

**Suggested improvement:** Resolve existing internal identifiers to authoritative stable records and verify entity type and species. Add only applicable matches; do not attach human events to bacterial genes or reactions as equivalence.

**How to verify:** Each reference has correct entity type/identity and a justified relationship; species-specific or absent records are not fabricated.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [Reactome identifiers: internal DB_ID and species-aware stable IDs](https://reactome.org/documentation/faq/37-general-website/201-identifiers)


<a id="f12"></a>

### F12 — `test_metabolite_annotation_overview[metanetx.chemical]`

**P3 · namespace coverage gap**

**Observed:** 55/879 metabolites lack the metanetx.chemical namespace (6.26%); 824 carry that key.

**Biological meaning:** MNXref chemical mappings reconcile database identities but must still respect protonation, compartment-independent chemistry and stereochemistry.

**Suggested improvement:** Look up current and deprecated MNXM cross-references in a pinned MNXref release. For unresolved or averaged entities, retain a documented local identifier.

**How to verify:** Every added MNXM is a verified same-identity match, with mapping version and ambiguity retained.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [MetaNetX/MNXref identifier documentation](https://beta.metanetx.org/mnxdoc/mnxref.html)


<a id="f13"></a>

### F13 — `test_metabolite_annotation_overview[bigg.metabolite]`

**P3 · namespace coverage gap**

**Observed:** 143/879 metabolites lack the bigg.metabolite namespace (16.27%); 736 carry that key.

**Biological meaning:** BiGG metabolite aliases help model comparisons. Local Bath-specific averaged lipids need not have universal BiGG entries.

**Suggested improvement:** Use a verified BiGG universal metabolite ID, preserving the local compartment suffix separately. Maintain an explicit alias map for historical hyphen forms.

**How to verify:** Current BiGG records and structures agree; unique custom metabolites remain local instead of receiving guessed aliases.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [BiGG L-alanine record, current and historical identifiers](https://bigg.ucsd.edu/models/iJO1366/metabolites/ala__L_c)


<a id="f14"></a>

### F14 — `test_metabolite_annotation_overview[biocyc]`

**P3 · namespace coverage gap**

**Observed:** 153/879 metabolites lack the biocyc namespace (17.41%); 726 carry that key.

**Biological meaning:** BioCyc/MetaCyc frame identifiers connect compounds or reactions to curated knowledge; free-text names are not frame identifiers.

**Suggested improvement:** Use a verified organism/database-qualified frame with the appropriate chemical or reaction identity. Keep descriptive labels in name/notes fields.

**How to verify:** All retained references resolve to the correct frame type and biological identity; local abstractions remain explicit.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [MEMOTE annotation-test implementation](https://memote.readthedocs.io/en/latest/_modules/memote/support/annotation.html)


<a id="f15"></a>

### F15 — `test_reaction_annotation_overview[rhea]`

**P3 · namespace coverage gap**

**Observed:** 420/913 reactions lack the rhea namespace (46.00%); 493 carry that key.

**Biological meaning:** Rhea identifies curated reaction chemistry; its directional quartet matters when comparing reactions.

**Suggested improvement:** Map fully reviewed biochemical equations to the appropriate Rhea record and direction. Biomass, exchange and deliberately lumped pseudo-reactions may have no exact Rhea counterpart.

**How to verify:** Mapped chemistry, charge/proton convention and reaction direction agree; pseudo-reaction exceptions are documented.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [Rhea directional reaction quartets](https://www.rhea-db.org/help/reaction-side-direction)


<a id="f16"></a>

### F16 — `test_reaction_annotation_overview[kegg.reaction]`

**P3 · namespace coverage gap**

**Observed:** 278/913 reactions lack the kegg.reaction namespace (30.45%); 635 carry that key.

**Biological meaning:** KEGG R identifiers connect biochemical conversions to reaction records, independently of evidence that a particular Bath enzyme catalyzes them.

**Suggested improvement:** Match full stoichiometric chemistry and specificity; keep organism/GPR evidence separately. Exclude bookkeeping exchanges and biomass from forced enzyme-reaction mappings.

**How to verify:** Verified R records correspond to the modeled chemistry; missing appropriate counterparts are documented.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [KEGG identifiers and database namespaces](https://www.genome.jp/kegg/docs/weblinks.html)


<a id="f17"></a>

### F17 — `test_reaction_annotation_overview[seed.reaction]`

**P2 · namespace mismatch**

**Observed:** 913/913 reactions lack the seed.reaction namespace (100.00%); 0 carry that key.

**Biological meaning:** MEMOTE looks for seed.reaction, but the SBML contains 570 syntactically valid rxn references under legacy key seed. Thus 0% recognized coverage exaggerates missing information.

**Suggested improvement:** In a derived copy, verify the 570 existing references against a pinned ModelSEED release, then migrate the namespace key from seed to seed.reaction while preserving provenance. Curate the other 343 only where applicable.

**How to verify:** The 570 reviewed aliases become machine-recognized without changing any equations; absent reaction matches are not fabricated.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [ModelSEED authoritative biochemical database](https://github.com/ModelSEED/ModelSEEDDatabase)


<a id="f18"></a>

### F18 — `test_reaction_annotation_overview[metanetx.reaction]`

**P3 · namespace coverage gap**

**Observed:** 206/913 reactions lack the metanetx.reaction namespace (22.56%); 707 carry that key.

**Biological meaning:** MNXR aliases reconcile reaction identities across reconstruction resources. Not all pseudo-reactions and custom lumped transformations have equivalents.

**Suggested improvement:** Match reaction participants, stoichiometry and direction against a pinned release, including replaced-ID history; document nonstandard pseudo-reactions.

**How to verify:** Verified MNXR mappings are chemically equivalent, with unresolved cases and version information retained.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [MetaNetX/MNXref identifier documentation](https://beta.metanetx.org/mnxdoc/mnxref.html)


<a id="f19"></a>

### F19 — `test_reaction_annotation_overview[bigg.reaction]`

**P3 · namespace coverage gap**

**Observed:** 164/913 reactions lack the bigg.reaction namespace (17.96%); 749 carry that key.

**Biological meaning:** BiGG reaction identifiers support interoperability; chemically distinct transport coupling and organism-specific lumped reactions must not be conflated.

**Suggested improvement:** Validate candidate aliases against full equations and compartments. Prefer an explicit local identifier over a superficially similar reaction name.

**How to verify:** Every mapping preserves reaction identity and direction; custom reactions have traceable rationale.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [BiGG L-alanine record, current and historical identifiers](https://bigg.ucsd.edu/models/iJO1366/metabolites/ala__L_c)


<a id="f20"></a>

### F20 — `test_reaction_annotation_overview[reactome]`

**P3 · namespace coverage gap**

**Observed:** 759/913 reactions lack the reactome namespace (83.13%); 154 carry that key.

**Biological meaning:** Reactome distinguishes chemical physical entities, reactions and species-specific events. Shared chemicals can be cross-referenced without implying that a human pathway operates in Bath.

**Suggested improvement:** Resolve existing internal identifiers to authoritative stable records and verify entity type and species. Add only applicable matches; do not attach human events to bacterial genes or reactions as equivalence.

**How to verify:** Each reference has correct entity type/identity and a justified relationship; species-specific or absent records are not fabricated.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [Reactome identifiers: internal DB_ID and species-aware stable IDs](https://reactome.org/documentation/faq/37-general-website/201-identifiers)


<a id="f21"></a>

### F21 — `test_reaction_annotation_overview[ec-code]`

**P2 · namespace coverage and activity mapping gap**

**Observed:** 913/913 reactions lack the ec-code namespace (100.00%); 0 carry that key.

**Biological meaning:** No ec-code namespace exists, although 506 reactions have brenda annotations. EC numbers describe catalyzed activity rather than a unique enzyme sequence or every model pseudo-reaction.

**Suggested improvement:** Review BRENDA activity entries against current IUBMB classifications, then add verified official EC numbers only where justified. Do not copy preliminary BRENDA B-numbers blindly into ec-code.

**How to verify:** Applicable enzyme reactions have supported EC classes; exchanges, biomass, transport without EC and unresolved activities are documented.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [BRENDA fields and preliminary BRENDA enzyme numbers](https://www.brenda-enzymes.org/datafields.php)


<a id="f22"></a>

### F22 — `test_reaction_annotation_overview[brenda]`

**P3 · namespace coverage gap**

**Observed:** 407/913 reactions lack the brenda namespace (44.58%); 506 carry that key.

**Biological meaning:** BRENDA activity links help trace enzymology, but its coverage is not a universal reaction checklist. It also recognizes provisional B-number classes.

**Suggested improvement:** Curate supported activity references separately from enzyme/gene identity. Preserve legitimate preliminary BRENDA identifiers with provenance and a suitable checker.

**How to verify:** Chemically supported activity mappings; no invented full EC specificity for broadly characterized enzymes.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [BRENDA fields and preliminary BRENDA enzyme numbers](https://www.brenda-enzymes.org/datafields.php)


<a id="f23"></a>

### F23 — `test_reaction_annotation_overview[biocyc]`

**P3 · namespace coverage gap**

**Observed:** 403/913 reactions lack the biocyc namespace (44.14%); 510 carry that key.

**Biological meaning:** BioCyc/MetaCyc frame identifiers connect compounds or reactions to curated knowledge; free-text names are not frame identifiers.

**Suggested improvement:** Use a verified organism/database-qualified frame with the appropriate chemical or reaction identity. Keep descriptive labels in name/notes fields.

**How to verify:** All retained references resolve to the correct frame type and biological identity; local abstractions remain explicit.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [MEMOTE annotation-test implementation](https://memote.readthedocs.io/en/latest/_modules/memote/support/annotation.html)


<a id="f24"></a>

### F24 — `test_gene_product_annotation_overview[refseq]`

**P2 · namespace coverage gap**

**Observed:** 730/730 genes lack the refseq namespace (100.00%); 0 carry that key.

**Biological meaning:** RefSeq links gene products to reference sequence records. All 730 MCA locus identifiers lack this machine-readable link, weakening traceability of GPR evidence.

**Suggested improvement:** Map MCA loci against the pinned Bath genome/annotation release and record stable protein accession.version where resolvable. Distinguish genomic accessions from protein accessions.

**How to verify:** Resolved links match Bath locus/protein evidence; current legitimate WP_ accessions are accepted even though MEMOTE 0.17 regex omits WP.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [NCBI Reference Sequence Database](https://www.ncbi.nlm.nih.gov/refseq/); [NCBI nonredundant WP protein accessions](https://www.ncbi.nlm.nih.gov/refseq/about/nonredundantproteins/)


<a id="f25"></a>

### F25 — `test_gene_product_annotation_overview[uniprot]`

**P2 · namespace coverage gap**

**Observed:** 730/730 genes lack the uniprot namespace (100.00%); 0 carry that key.

**Biological meaning:** UniProt cross-references connect gene products to protein records and function evidence; a matching function name alone is not a strain-specific identity proof.

**Suggested improvement:** Use curated Bath locus-tag/sequence cross-references with taxonomy and assembly evidence, recording reviewed/unreviewed status and ambiguity.

**How to verify:** Links identify the intended Bath proteins and preserve uncertain mapping evidence instead of guessing from gene names.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [UniProt accession identifiers](https://www.uniprot.org/help/accession_numbers)


<a id="f26"></a>

### F26 — `test_gene_product_annotation_overview[ecogene]`

**P3 · not applicable organism scope**

**Observed:** 730/730 genes lack the ecogene namespace (100.00%); 0 carry that key.

**Biological meaning:** EcoGene EG identifiers are for Escherichia coli K-12, whereas this model is Methylococcus capsulatus Bath. Their absence is biologically appropriate.

**Suggested improvement:** Mark this namespace requirement not applicable for direct identity annotation. If an E. coli homolog is scientifically useful, store it as a qualified homolog relationship rather than same-entity annotation.

**How to verify:** No false E. coli identity assignments; organism-scoped QC records the exclusion while preserving the raw MEMOTE failure.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [EcoGene 3.0: Escherichia coli K-12 scope](https://pmc.ncbi.nlm.nih.gov/articles/PMC3531124/)


<a id="f27"></a>

### F27 — `test_gene_product_annotation_overview[kegg.genes]`

**P2 · namespace coverage gap**

**Observed:** 730/730 genes lack the kegg.genes namespace (100.00%); 0 carry that key.

**Biological meaning:** KEGG genes use organism:gene identifiers. Bare MCA locus tags are local IDs and do not constitute a namespaced KEGG mapping.

**Suggested improvement:** Verify the KEGG organism code and exact Bath locus entry against the genome release before adding organism-prefixed identifiers.

**How to verify:** Each reference resolves to the intended strain/locus, with assembly-version caveats retained.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [KEGG identifiers and database namespaces](https://www.genome.jp/kegg/docs/weblinks.html)


<a id="f28"></a>

### F28 — `test_gene_product_annotation_overview[ncbigi]`

**P3 · legacy optional namespace**

**Observed:** 730/730 genes lack the ncbigi namespace (100.00%); 0 carry that key.

**Biological meaning:** GI is a legacy sequence identifier. NCBI moved toward accession.version identifiers; absent GI annotations are not evidence of missing sequence biology.

**Suggested improvement:** Prefer supported accession.version links; retain legacy GI references only when already verified. Do not prioritize adding obsolete IDs merely to improve a score.

**How to verify:** Modern sequence identity is traceable; the GI-specific target is explicitly treated as legacy/optional.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [NCBI transition from GI to accession.version identifiers](https://ncbiinsights.ncbi.nlm.nih.gov/2016/09/12/the-future-of-existing-gi-numbers-at-ncbi/amp/)


<a id="f29"></a>

### F29 — `test_gene_product_annotation_overview[ncbigene]`

**P2 · namespace coverage gap**

**Observed:** 730/730 genes lack the ncbigene namespace (100.00%); 0 carry that key.

**Biological meaning:** NCBI Gene identifiers link loci and gene records, distinct from protein accession numbers.

**Suggested improvement:** Resolve the Bath locus tags to current or historical Gene records where those records exist; verify taxon and assembly rather than copying numeric IDs from other organisms.

**How to verify:** All mapped Gene IDs identify the intended Bath loci; unavailable/deprecated entries are documented.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [NCBI Reference Sequence Database](https://www.ncbi.nlm.nih.gov/refseq/)


<a id="f30"></a>

### F30 — `test_gene_product_annotation_overview[ncbiprotein]`

**P2 · namespace coverage gap**

**Observed:** 730/730 genes lack the ncbiprotein namespace (100.00%); 0 carry that key.

**Biological meaning:** NCBI Protein accessions identify sequence records; protein and gene identifiers are not interchangeable.

**Suggested improvement:** Map each Bath gene product to an authoritative protein accession.version using the genome feature table and cross-references.

**How to verify:** Sequence records, organism and locus agree; multiple candidates remain explicit until resolved.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [NCBI nonredundant WP protein accessions](https://www.ncbi.nlm.nih.gov/refseq/about/nonredundantproteins/)


<a id="f31"></a>

### F31 — `test_gene_product_annotation_overview[ccds]`

**P3 · not applicable organism scope**

**Observed:** 730/730 genes lack the ccds namespace (100.00%); 0 carry that key.

**Biological meaning:** CCDS covers consensus human and mouse coding regions. A bacterial Bath gene should not have a CCDS identity annotation.

**Suggested improvement:** Record this namespace test as not applicable in organism-aware interpretation; retain its raw failure. Never add human/mouse identifiers to force a pass.

**How to verify:** No fabricated cross-species identities; exclusion is justified by authoritative database scope.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [NCBI CCDS: human and mouse coding regions](https://www.ncbi.nlm.nih.gov/CCDS/CcdsBrowse.cgi)


<a id="f32"></a>

### F32 — `test_gene_product_annotation_overview[hprd]`

**P3 · not applicable organism scope**

**Observed:** 730/730 genes lack the hprd namespace (100.00%); 0 carry that key.

**Biological meaning:** HPRD describes human proteins. Direct identity links for bacterial Bath genes would be biologically incorrect.

**Suggested improvement:** Treat this namespace as not applicable; preserve raw QC results and use bacterial sequence resources for real gene traceability.

**How to verify:** No human identity misannotations and a documented organism-specific QC scope.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [Original Human Protein Reference Database paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC403728/)


<a id="f33"></a>

### F33 — `test_gene_product_annotation_overview[asap]`

**P3 · namespace coverage gap**

**Observed:** 730/730 genes lack the asap namespace (100.00%); 0 carry that key.

**Biological meaning:** ASAP is a community genome resource with a strong enterobacterial focus but broader technical scope. Bath coverage cannot be assumed or inferred from the score.

**Suggested improvement:** Check whether the exact Bath genome is represented before mapping any features. If not represented, document lack of database coverage and rely on verified genome/protein resources.

**How to verify:** Mappings are made only to actual Bath features; optional coverage gaps are retained honestly.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [Original ASAP database scope and community annotation](https://pmc.ncbi.nlm.nih.gov/articles/PMC1347526/)


<a id="f34"></a>

### F34 — `test_metabolite_annotation_wrong_ids[pubchem.compound]`

**P3 · absence precondition duplicate**

**Observed:** No pubchem.compound annotations exist (0/879); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. PubChem CID identifies a chemical structure. Missing CIDs impede structure joins but do not invalidate flux balance.

**Suggested improvement:** Map only defined chemical identities to verified CIDs; distinguish Compound CID from Substance SID. Averaged lipids and abstract pools may have no exact CID. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** Verified compound-level matches, with structure/protonation checks and documented not-applicable pools. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [PubChem CID versus SID record identifiers](https://pubchem.ncbi.nlm.nih.gov/docs/quick-search)


<a id="f35"></a>

### F35 — `test_metabolite_annotation_wrong_ids[kegg.compound]`

**P2 · namespace mismatch**

**Observed:** 176/816 annotated metabolites fail the bundled kegg.compound regex (21.57% of annotated components).

**Biological meaning:** All invalid entries begin with D or G: 266 D-valued and 24 G-valued occurrences across 176 components. For example 4abz_c carries D02456 under kegg.compound. These may be real KEGG drug/glycan records stored in the wrong namespace, not invented chemical IDs.

**Suggested improvement:** Resolve each D/G entry, retain justified cross-references under kegg.drug or kegg.glycan, and retain validated C entries under kegg.compound. A drug salt or formulation is not automatically identical to the modeled species; do not change D/G prefixes to C.

**How to verify:** All compound-namespace values are valid same-identity C entries; drug/glycan links use their proper namespace and qualified relation, with no change to stoichiometry.

Representative encoded values (all records are retained in the structured evidence):

```json
[
  {
    "id": "4abz_c",
    "value": [
      "C00568",
      "D02456"
    ]
  },
  {
    "id": "5aop_c",
    "value": [
      "C00430",
      "D07567",
      "D02908"
    ]
  },
  {
    "id": "5fthf_c",
    "value": [
      "C03479",
      "D07986"
    ]
  }
]
```

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [KEGG identifiers and database namespaces](https://www.genome.jp/kegg/docs/weblinks.html)


<a id="f36"></a>

### F36 — `test_metabolite_annotation_wrong_ids[seed.compound]`

**P2 · whitespace serialization error**

**Observed:** 64/791 annotated metabolites fail the bundled seed.compound regex (8.09% of annotated components).

**Biological meaning:** All 64 flagged components have at least one leading-space value (for example 3dhsk_c: " cpd01725"). Trimming the offending values satisfies the bundled syntax, but does not by itself establish chemical equivalence.

**Suggested improvement:** Trim external whitespace in a separately versioned mapping, deduplicate list values and verify each resolved ModelSEED record against the metabolite identity.

**How to verify:** No leading/trailing whitespace; retained cpd references resolve to chemically correct records and SBML/JSON roundtrip preserves the list.

Representative encoded values (all records are retained in the structured evidence):

```json
[
  {
    "id": "3dhsk_c",
    "value": [
      "cpd01716",
      " cpd01725"
    ]
  },
  {
    "id": "3hmop_c",
    "value": [
      "cpd02606",
      " cpd10162"
    ]
  },
  {
    "id": "3hodcoa_c",
    "value": [
      "cpd14936",
      " cpd15204"
    ]
  }
]
```

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [ModelSEED authoritative biochemical database](https://github.com/ModelSEED/ModelSEEDDatabase)


<a id="f37"></a>

### F37 — `test_metabolite_annotation_wrong_ids[inchikey]`

**P3 · absence precondition duplicate**

**Observed:** No inchikey annotations exist (0/879); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. An InChIKey is a compact structure key. None are present, so structure-based lookup is less convenient; a key does not itself prove biological presence.

**Suggested improvement:** Generate standard keys only from chemically reviewed structures using a pinned InChI implementation. Do not assign an exact-molecule key to average lipids or undefined polymers. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** Each added key agrees with the reviewed full InChI/structure and standard version; undefined species are explicitly excluded. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [InChI Trust technical FAQ](https://www.inchi-trust.org/technical-faq/)


<a id="f38"></a>

### F38 — `test_metabolite_annotation_wrong_ids[chebi]`

**P2 · serialized list corruption**

**Observed:** 8/749 annotated metabolites fail the bundled chebi regex (1.07% of annotated components).

**Biological meaning:** Eight components contain bracketed list fragments and literal &apos; entities instead of individual ChEBI accessions; examples include fald_e/fald_p and sodium/cytochrome forms. Decoding text alone cannot decide whether every former cross-reference denotes the same redox/protonation state.

**Suggested improvement:** Recover intended source lists from upstream curation evidence, store each verified CHEBI:number separately, remove double-escaped serialization artifacts, and review redox/protonation and class-versus-instance equivalence.

**How to verify:** Clean resolvable ChEBI values, with a documented identity decision for each retained accession and no accidental loss of valid alternatives.

Representative encoded values (all records are retained in the structured evidence):

```json
[
  {
    "id": "fald_e",
    "value": [
      "CHEBI:[&apos;16842&apos;",
      "CHEBI:&apos;5142&apos;",
      "CHEBI:&apos;24077&apos;",
      "CHEBI:&apos;337763&apos;",
      "CHEBI:&apos;14274&apos;]"
    ]
  },
  {
    "id": "fald_p",
    "value": [
      "CHEBI:[&apos;16842&apos;",
      "CHEBI:&apos;5142&apos;",
      "CHEBI:&apos;24077&apos;",
      "CHEBI:&apos;337763&apos;",
      "CHEBI:&apos;14274&apos;]"
    ]
  },
  {
    "id": "ficytcc553_p",
    "value": [
      "CHEBI:[&apos;5028&apos;",
      "CHEBI:&apos;14239&apos;",
      "CHEBI:&apos;16951&apos;]"
    ]
  }
]
```

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [ChEBI scope and chemical entities](https://www.ebi.ac.uk/chebi/about)


<a id="f39"></a>

### F39 — `test_metabolite_annotation_wrong_ids[reactome]`

**P2 · legacy identifier representation**

**Observed:** 382/382 annotated metabolites fail the bundled reactome regex (100.00% of annotated components).

**Biological meaning:** All 382 annotated metabolites fail because their values are REACTOME:<numeric DB_ID>, e.g. 10fthf_c has REACTOME:419151. Reactome distinguishes DB_ID from stable identifiers; this is a systematic representation issue, not 382 proven chemical misidentifications.

**Suggested improvement:** Resolve numeric IDs through Reactome and migrate verified physical-entity references to appropriate current stable IDs (including species-independent simple-chemical records where supported). Do not invent R-ALL/R-HSA prefixes from numbers alone.

**How to verify:** Each stable identifier resolves to the intended entity and compartment/state relationship. Validate against current registry rules; MEMOTE 0.17 also mishandles dotted version suffixes on modern stable IDs.

Representative encoded values (all records are retained in the structured evidence):

```json
[
  {
    "id": "10fthf_c",
    "value": "REACTOME:419151"
  },
  {
    "id": "12dgr_EC_c",
    "value": [
      "REACTOME:114519",
      "REACTOME:162777",
      "REACTOME:163414",
      "REACTOME:2023883",
      "REACTOME:76103",
      "REACTOME:1524057",
      "REACTOME:1500596",
      "REACTOME:429773",
      "REACTOME:112275",
      "REACTOME:174675"
    ]
  },
  {
    "id": "12dmpo_c",
    "value": "REACTOME:1237155"
  }
]
```

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [Reactome identifiers: internal DB_ID and species-aware stable IDs](https://reactome.org/documentation/faq/37-general-website/201-identifiers)


<a id="f40"></a>

### F40 — `test_metabolite_annotation_wrong_ids[metanetx.chemical]`

**P2 · name in identifier field**

**Observed:** 1/824 annotated metabolites fail the bundled metanetx.chemical regex (0.12% of annotated components).

**Biological meaning:** Only 2omhmbl_c is flagged: its metanetx.chemical value is the free-text name "3-demethylubiquinol-8", not an MNXM accession. Quinone/quinol redox state makes name-only replacement especially unsafe.

**Suggested improvement:** Use the molecule structure, formula, charge and existing aliases to establish the exact current MNXM identity; move the descriptive name into name/notes and leave the external mapping unresolved if ambiguous.

**How to verify:** A verified MNXM identifier matches the intended redox state, or an explicit unresolved mapping is retained without a false ID.

Representative encoded values (all records are retained in the structured evidence):

```json
[
  {
    "id": "2omhmbl_c",
    "value": "3-demethylubiquinol-8"
  }
]
```

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [MetaNetX/MNXref identifier documentation](https://beta.metanetx.org/mnxdoc/mnxref.html)


<a id="f41"></a>

### F41 — `test_metabolite_annotation_wrong_ids[bigg.metabolite]`

**P2 · legacy alias representation**

**Observed:** 68/736 annotated metabolites fail the bundled bigg.metabolite regex (9.24% of annotated components).

**Biological meaning:** 68 components contain hyphenated historical aliases such as ala-L, while current universal BiGG identifiers use forms such as ala__L. This is partly namespace-version normalization; blind punctuation replacement is not an identity proof.

**Suggested improvement:** Resolve historical aliases against BiGG old-ID mappings, use verified current universal IDs and retain the original string in provenance. Review stereochemical tokens and organism-specific pools individually.

**How to verify:** Current aliases resolve correctly, stereochemistry is preserved, and historical strings remain traceable.

Representative encoded values (all records are retained in the structured evidence):

```json
[
  {
    "id": "26dap_LL_c",
    "value": "26dap-LL"
  },
  {
    "id": "26dap_M_c",
    "value": "26dap-M"
  },
  {
    "id": "4hpro_LT_c",
    "value": "4hpro-LT"
  }
]
```

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [BiGG L-alanine record, current and historical identifiers](https://bigg.ucsd.edu/models/iJO1366/metabolites/ala__L_c)


<a id="f42"></a>

### F42 — `test_metabolite_annotation_wrong_ids[biocyc]`

**P2 · serialized list and semantic annotation errors**

**Observed:** 5/726 annotated metabolites fail the bundled biocyc regex (0.69% of annotated components).

**Biological meaning:** dolp_c has escaped list fragments; four cytochrome entities have free-text phrases instead of frames. focytcc555_p is a reduced cytochrome yet its annotation says "an oxidized c-type cytochrome", so there is a redox-semantic contradiction in addition to malformed syntax.

**Suggested improvement:** Recover verified dolichol-phosphate frame IDs and separately verify oxidized/reduced cytochrome identities against molecular state. Place descriptive phrases in notes; use true database-qualified frame IDs only where appropriate.

**How to verify:** All retained frames resolve and agree with redox state; no incorrect oxidized alias remains on the reduced species.

Representative encoded values (all records are retained in the structured evidence):

```json
[
  {
    "id": "dolp_c",
    "value": [
      "META:[&apos;CPD-17833&apos;",
      "META:&apos;DOLICHOLP&apos;]"
    ]
  },
  {
    "id": "ficytcc553_p",
    "value": "META:an oxidized c-type cytochrome"
  },
  {
    "id": "ficytcc555_p",
    "value": "META:an oxidized c-type cytochrome"
  }
]
```

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [MEMOTE annotation-test implementation](https://memote.readthedocs.io/en/latest/_modules/memote/support/annotation.html)


<a id="f43"></a>

### F43 — `test_reaction_annotation_wrong_ids[rhea]`

**P2 · serialized list corruption**

**Observed:** 1/493 annotated reactions fail the bundled rhea regex (0.20% of annotated components).

**Biological meaning:** NO3R1 contains one concatenated value "29147: &apos;29148: &apos;29149: &apos;29150". These look like a Rhea directional quartet serialized incorrectly; this observation alone does not establish the correct direction or chemistry.

**Suggested improvement:** Resolve all candidate records, compare nitrate-reductase participants/electron donor and direction, then store verified appropriate Rhea references as separate values with direction provenance.

**How to verify:** Valid Rhea identifiers point to the intended chemistry/direction; no malformed concatenation remains.

Representative encoded values (all records are retained in the structured evidence):

```json
[
  {
    "id": "NO3R1",
    "value": "29147: &apos;29148: &apos;29149: &apos;29150"
  }
]
```

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [Rhea directional reaction quartets](https://www.rhea-db.org/help/reaction-side-direction)


<a id="f44"></a>

### F44 — `test_reaction_annotation_wrong_ids[seed.reaction]`

**P3 · absence precondition duplicate**

**Observed:** No seed.reaction annotations exist (0/913); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. MEMOTE looks for seed.reaction, but the SBML contains 570 syntactically valid rxn references under legacy key seed. Thus 0% recognized coverage exaggerates missing information.

**Suggested improvement:** In a derived copy, verify the 570 existing references against a pinned ModelSEED release, then migrate the namespace key from seed to seed.reaction while preserving provenance. Curate the other 343 only where applicable. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** The 570 reviewed aliases become machine-recognized without changing any equations; absent reaction matches are not fabricated. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [ModelSEED authoritative biochemical database](https://github.com/ModelSEED/ModelSEEDDatabase)


<a id="f45"></a>

### F45 — `test_reaction_annotation_wrong_ids[bigg.reaction]`

**P2 · escaped quote serialization error**

**Observed:** 1/749 annotated reactions fail the bundled bigg.reaction regex (0.13% of annotated components).

**Biological meaning:** VALDHr carries literal escaped quotes (&apos;VALDHr&apos;) in its BiGG reference. The identifier field has presentation artifacts rather than a clean database accession.

**Suggested improvement:** Verify the BiGG equation and current identifier, decode/remove only surrounding serialization artifacts, and record the provenance of the repair.

**How to verify:** The clean reference resolves to matching chemistry and survives SBML/JSON roundtrip without quote entities.

Representative encoded values (all records are retained in the structured evidence):

```json
[
  {
    "id": "VALDHr",
    "value": "&apos;VALDHr&apos;"
  }
]
```

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [BiGG L-alanine record, current and historical identifiers](https://bigg.ucsd.edu/models/iJO1366/metabolites/ala__L_c)


<a id="f46"></a>

### F46 — `test_reaction_annotation_wrong_ids[ec-code]`

**P3 · absence precondition duplicate**

**Observed:** No ec-code annotations exist (0/913); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. No ec-code namespace exists, although 506 reactions have brenda annotations. EC numbers describe catalyzed activity rather than a unique enzyme sequence or every model pseudo-reaction.

**Suggested improvement:** Review BRENDA activity entries against current IUBMB classifications, then add verified official EC numbers only where justified. Do not copy preliminary BRENDA B-numbers blindly into ec-code. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** Applicable enzyme reactions have supported EC classes; exchanges, biomass, transport without EC and unresolved activities are documented. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [BRENDA fields and preliminary BRENDA enzyme numbers](https://www.brenda-enzymes.org/datafields.php)


<a id="f47"></a>

### F47 — `test_reaction_annotation_wrong_ids[brenda]`

**P2 · mixed format errors and checker scope defect**

**Observed:** 15/506 annotated reactions fail the bundled brenda regex (2.96% of annotated components).

**Biological meaning:** 15 reactions fail: 12 have only three EC fields (e.g. 2.6.1), FDH and SMMOi have trailing serialized quote/colon fragments, and FALDDHipp has 1.2.2.B1. BRENDA explicitly supports preliminary B-numbers, so the latter is not invalid merely because MEMOTE applies an official-EC-like regex.

**Suggested improvement:** For the 12 partial classifications, preserve their uncertainty: use a correctly represented partial class only where registry semantics support it, never invent the final digit. Recover the two corrupted entries from provenance. Check whether preliminary 1.2.2.B1 is still current/reclassified and retain a justified BRENDA reference with an appropriate validator.

**How to verify:** All curated values are supported by current BRENDA/IUBMB records, intended specificity is preserved, and checker exceptions for legitimate provisional IDs are explicit. Do not silently replace a B-number to chase a pass.

Representative encoded values (all records are retained in the structured evidence):

```json
[
  {
    "id": "3SALATAi",
    "value": [
      "2.6.1",
      "2.6.1.1"
    ]
  },
  {
    "id": "4HTHRS",
    "value": [
      "4.2.3",
      "4.2.3.1"
    ]
  },
  {
    "id": "APCS",
    "value": [
      "2.5.1",
      "2.5.1.16"
    ]
  }
]
```

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [BRENDA fields and preliminary BRENDA enzyme numbers](https://www.brenda-enzymes.org/datafields.php)


<a id="f48"></a>

### F48 — `test_gene_product_annotation_wrong_ids[refseq]`

**P3 · absence precondition duplicate**

**Observed:** No refseq annotations exist (0/730); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. RefSeq links gene products to reference sequence records. All 730 MCA locus identifiers lack this machine-readable link, weakening traceability of GPR evidence.

**Suggested improvement:** Map MCA loci against the pinned Bath genome/annotation release and record stable protein accession.version where resolvable. Distinguish genomic accessions from protein accessions. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** Resolved links match Bath locus/protein evidence; current legitimate WP_ accessions are accepted even though MEMOTE 0.17 regex omits WP. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [NCBI Reference Sequence Database](https://www.ncbi.nlm.nih.gov/refseq/); [NCBI nonredundant WP protein accessions](https://www.ncbi.nlm.nih.gov/refseq/about/nonredundantproteins/)


<a id="f49"></a>

### F49 — `test_gene_product_annotation_wrong_ids[uniprot]`

**P3 · absence precondition duplicate**

**Observed:** No uniprot annotations exist (0/730); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. UniProt cross-references connect gene products to protein records and function evidence; a matching function name alone is not a strain-specific identity proof.

**Suggested improvement:** Use curated Bath locus-tag/sequence cross-references with taxonomy and assembly evidence, recording reviewed/unreviewed status and ambiguity. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** Links identify the intended Bath proteins and preserve uncertain mapping evidence instead of guessing from gene names. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [UniProt accession identifiers](https://www.uniprot.org/help/accession_numbers)


<a id="f50"></a>

### F50 — `test_gene_product_annotation_wrong_ids[ecogene]`

**P3 · not applicable and absence precondition**

**Observed:** No ecogene annotations exist (0/730); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. EcoGene EG identifiers are for Escherichia coli K-12, whereas this model is Methylococcus capsulatus Bath. Their absence is biologically appropriate.

**Suggested improvement:** Mark this namespace requirement not applicable for direct identity annotation. If an E. coli homolog is scientifically useful, store it as a qualified homolog relationship rather than same-entity annotation. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** No false E. coli identity assignments; organism-scoped QC records the exclusion while preserving the raw MEMOTE failure. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [EcoGene 3.0: Escherichia coli K-12 scope](https://pmc.ncbi.nlm.nih.gov/articles/PMC3531124/)


<a id="f51"></a>

### F51 — `test_gene_product_annotation_wrong_ids[kegg.genes]`

**P3 · absence precondition duplicate**

**Observed:** No kegg.genes annotations exist (0/730); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. KEGG genes use organism:gene identifiers. Bare MCA locus tags are local IDs and do not constitute a namespaced KEGG mapping.

**Suggested improvement:** Verify the KEGG organism code and exact Bath locus entry against the genome release before adding organism-prefixed identifiers. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** Each reference resolves to the intended strain/locus, with assembly-version caveats retained. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [KEGG identifiers and database namespaces](https://www.genome.jp/kegg/docs/weblinks.html)


<a id="f52"></a>

### F52 — `test_gene_product_annotation_wrong_ids[ncbigi]`

**P3 · absence precondition duplicate**

**Observed:** No ncbigi annotations exist (0/730); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. GI is a legacy sequence identifier. NCBI moved toward accession.version identifiers; absent GI annotations are not evidence of missing sequence biology.

**Suggested improvement:** Prefer supported accession.version links; retain legacy GI references only when already verified. Do not prioritize adding obsolete IDs merely to improve a score. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** Modern sequence identity is traceable; the GI-specific target is explicitly treated as legacy/optional. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [NCBI transition from GI to accession.version identifiers](https://ncbiinsights.ncbi.nlm.nih.gov/2016/09/12/the-future-of-existing-gi-numbers-at-ncbi/amp/)


<a id="f53"></a>

### F53 — `test_gene_product_annotation_wrong_ids[ncbigene]`

**P3 · absence precondition duplicate**

**Observed:** No ncbigene annotations exist (0/730); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. NCBI Gene identifiers link loci and gene records, distinct from protein accession numbers.

**Suggested improvement:** Resolve the Bath locus tags to current or historical Gene records where those records exist; verify taxon and assembly rather than copying numeric IDs from other organisms. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** All mapped Gene IDs identify the intended Bath loci; unavailable/deprecated entries are documented. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [NCBI Reference Sequence Database](https://www.ncbi.nlm.nih.gov/refseq/)


<a id="f54"></a>

### F54 — `test_gene_product_annotation_wrong_ids[ncbiprotein]`

**P3 · absence precondition duplicate**

**Observed:** No ncbiprotein annotations exist (0/730); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. NCBI Protein accessions identify sequence records; protein and gene identifiers are not interchangeable.

**Suggested improvement:** Map each Bath gene product to an authoritative protein accession.version using the genome feature table and cross-references. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** Sequence records, organism and locus agree; multiple candidates remain explicit until resolved. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [NCBI nonredundant WP protein accessions](https://www.ncbi.nlm.nih.gov/refseq/about/nonredundantproteins/)


<a id="f55"></a>

### F55 — `test_gene_product_annotation_wrong_ids[ccds]`

**P3 · not applicable and absence precondition**

**Observed:** No ccds annotations exist (0/730); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. CCDS covers consensus human and mouse coding regions. A bacterial Bath gene should not have a CCDS identity annotation.

**Suggested improvement:** Record this namespace test as not applicable in organism-aware interpretation; retain its raw failure. Never add human/mouse identifiers to force a pass. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** No fabricated cross-species identities; exclusion is justified by authoritative database scope. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [NCBI CCDS: human and mouse coding regions](https://www.ncbi.nlm.nih.gov/CCDS/CcdsBrowse.cgi)


<a id="f56"></a>

### F56 — `test_gene_product_annotation_wrong_ids[hprd]`

**P3 · not applicable and absence precondition**

**Observed:** No hprd annotations exist (0/730); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. HPRD describes human proteins. Direct identity links for bacterial Bath genes would be biologically incorrect.

**Suggested improvement:** Treat this namespace as not applicable; preserve raw QC results and use bacterial sequence resources for real gene traceability. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** No human identity misannotations and a documented organism-specific QC scope. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [Original Human Protein Reference Database paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC403728/)


<a id="f57"></a>

### F57 — `test_gene_product_annotation_wrong_ids[asap]`

**P3 · absence precondition duplicate**

**Observed:** No asap annotations exist (0/730); this check fails before testing identifier syntax.

**Biological meaning:** This is a second report of missing namespace coverage, not evidence that malformed identifiers were found. ASAP is a community genome resource with a strong enterobacterial focus but broader technical scope. Bath coverage cannot be assumed or inferred from the score.

**Suggested improvement:** Check whether the exact Bath genome is represented before mapping any features. If not represented, document lack of database coverage and rely on verified genome/protein resources. Treat syntax assessment as not assessable until relevant annotations exist.

**How to verify:** Mappings are made only to actual Bath features; optional coverage gaps are retained honestly. Empty applicable namespaces must be labeled unassessed; retain the raw failure separately.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_annotation.py

**Sources:** [Original ASAP database scope and community annotation](https://pmc.ncbi.nlm.nih.gov/articles/PMC1347526/)


<a id="f58"></a>

### F58 — `test_gene_protein_reaction_rule_presence`

**P1 · Evidence gap; some justified exceptions**

**Observed:** 119 reactions lack a GPR; 42 have GAPFILLING in their IDs. The returned set includes ATPM, biomass, average-fatty-acid construction and numerous transport steps.

**Biological meaning:** A gene–protein–reaction rule connects an enzyme reaction to the Bath genome and determines which gene deletions remove its activity. Missing GPRs weaken gene-essentiality predictions and the provenance of reconstructed pathways. A bookkeeping biomass/maintenance reaction or passive diffusion can legitimately have no single enzyme gene.

**Suggested improvement:** Classify all 119 as enzymatic, passive/spontaneous, bookkeeping, or unsupported gapfill. Add Bath-specific genes only with sequence/function or literature evidence; record AND for required subunits and OR for alternative enzymes. Record justified exceptions separately.

**How to verify:** Every enzymatic addition has strain-specific evidence; complex/isoenzyme logic is reviewed and tested by deletion. Pseudo-reactions retain documented exceptions. No arbitrary genes are assigned just to reach zero missing GPRs.

63 of these reactions are also in the transport-GPR finding. Overlap is not an additional set of defects. Examples requiring classification include CH4tex/CH4trpp and O2tex/O2tpp; diffusion and transport energetics must be distinguished.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 basic tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_basic.py)


<a id="f59"></a>

### F59 — `test_transport_reaction_gpr_presence`

**P1 · Evidence gap; heuristic threshold**

**Observed:** 63 of 122 classified transport reactions (51.64%) lack a GPR; this test requires less than 20%.

**Biological meaning:** Transport defines which substrates can reach metabolism and whether uptake consumes ATP, protons or ions. Unsupported transport assumptions can distort methane, oxygen and nitrogen yields. Absence of a GPR can be reasonable for diffusion, especially gases.

**Suggested improvement:** Review each transport step for compartment, direction, charge transfer, coupling stoichiometry and Bath-specific evidence. Prioritize methane, oxygen, ammonium/nitrate and ion-coupled transport used by SYMBIONT. Annotate confirmed transporters; document passive diffusion exceptions.

**How to verify:** Transport chemistry and evidence are consistent with the intended medium; no artificial energy cycles appear; uptake/yield comparisons are rerun. A residual missing-GPR fraction is acceptable when scientifically justified.

The 20% cutoff is a generic suite heuristic, not a biological law or proof that 63 transporter genes are missing.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 basic tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_basic.py)


<a id="f60"></a>

### F60 — `test_find_reactions_with_partially_identical_annotations`

**P2 · Overlapping annotation heuristic**

**Observed:** 109 overlapping annotation groups involve 226 unique reactions.

**Biological meaning:** The same EC class or database reference can describe enzymes with multiple substrates, different cofactors, compartments or reaction variants. These are candidate curation groups, not 226 demonstrated duplicate equations.

**Suggested improvement:** Compare actual substrates/products, stoichiometric ratios, compartments, reversibility, cofactors and GPR logic within each group. Correct overbroad/wrong references first; merge only genuinely redundant reactions while retaining evidence and bounds.

**How to verify:** Each group has an explicit retain/repair/merge decision. No distinct chain lengths, redox cofactors or compartments are collapsed. Regression checks cover growth, flux ranges and affected knockout behavior.

Examples: fatty-acid chain-length variants share BRENDA EC classes; ATPSNaipp and ATPSipp overlap in annotation despite different coupling ions. The 109 groups overlap with one another.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 basic tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_basic.py); [MEMOTE duplicate heuristics](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/basic.py)


<a id="f61"></a>

### F61 — `test_find_duplicate_reactions`

**P1 · Harness exception plus confirmed equation defect**

**Observed:** JUnit records TypeError: sequence item 0: expected str instance, tuple found. Before reporting crashed, the helper found one pair: GUAt2pp and XANt2pp, 2 unique reactions.

**Biological meaning:** Both encoded equations are gua_p + h_p <=> gua_c + h_c, although XANt2pp is named xanthine transport. Guanine and xanthine are different purine bases. The model therefore duplicates guanine transport and does not provide the xanthine transfer implied by that reaction name.

**Suggested improvement:** Repair pair formatting in the audit harness. Curate XANt2pp against its source and Bath transporter specificity: a candidate intended equation is xan_p + h_p <=> xan_c + h_c, but retain or remove the reaction according to evidence. Review MCA1664 substrate range and bounds rather than changing metabolites solely on the name.

**How to verify:** The helper runs to completion; any accepted equation conserves elements/charge; xanthine and guanine transport behavior is tested separately. Review XPPT (currently zero-bounded) before inferring restored xanthine utilization.

This is a real encoded duplicate, not an identical-InChI artifact: guanine is C5H5N5O; xanthine is C5H4N4O2, with distinct InChIs. GUAt2pp and XANt2pp also occur in the cycle finding because equal reversible reactions can carry opposite fluxes.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 basic tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_basic.py); [MEMOTE structural duplicate detection](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/basic.py)


<a id="f62"></a>

### F62 — `test_find_reactions_with_identical_genes`

**P2 · Gene-set overlap heuristic**

**Observed:** 145 gene-set groups involve 405 unique reactions.

**Biological meaning:** A protein can catalyze several steps or accept several substrates. Reactions sharing genes are not automatically redundant. The helper compares unordered gene sets, so it also ignores the difference between AND and OR logic.

**Suggested improvement:** Review each group for plausible enzyme multifunctionality, substrate breadth and GPR logic. Retain supported chain-length/cofactor variants; correct unsupported overassignment. Use equation and annotation evidence together before merging.

**How to verify:** Each reviewed group records its rationale; required complex subunits and isoenzymes are preserved; targeted deletion behavior agrees with curated evidence.

Examples: MCA2445/MCA2878 recur across fatty-acid dehydratase chain lengths; MCA1664 is assigned to ADEt2rpp/GUAt2pp/XANt2pp. These groups overlap the other duplicate screens.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 basic tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_basic.py); [MEMOTE gene-set comparison](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/basic.py)


<a id="f63"></a>

### F63 — `test_find_medium_metabolites`

**P0 · Harness exception; informational check**

**Observed:** JUnit records TypeError: unsupported operand type(s) for /: int and list. Twenty uptake-enabled extracellular metabolites are returned; 54 extracellular metabolites exist. The intended ratio is 20/54 = 0.37037, not the stale raw metric 1.0.

**Biological meaning:** This check reports what the default exchange bounds permit the cell to take up. It has no mandatory biological pass criterion. An uptake upper limit is a modeling permission, not a measured concentration or uptake rate.

**Suggested improvement:** Correct the denominator to len(find_external_metabolites(model)) and handle an empty denominator explicitly. Independently review the default medium against the declared simulation profile, including nitrate, carbon monoxide and trace-ion availability.

**How to verify:** The informational check completes and lists exactly the enabled uptake exchanges. Default and SYMBIONT reference media remain distinguishable and versioned.

The upstream default permits CH4 uptake up to 18.46 and nitrate/O2/CO up to 1000 in model flux units. The SYMBIONT reference profile is a different set of constraints. The exception does not show that the medium is biologically wrong.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 basic tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_basic.py); [MEMOTE medium helpers](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/basic.py)


<a id="f64"></a>

### F64 — `test_biomass_consistency[BIOMASS_Mcapsulatus]`

**P1 · Genuine encoded dry-mass normalization discrepancy; mechanism not resolved by the test**

**Observed:** MEMOTE computes 0.9024111134789822 g of net retained material per nominal biomass unit, below its accepted open interval (0.999, 1.000001). The shortfall from 1 is 0.0975888865 g (9.7589%). All biomass precursors have defined formulas, so this is not a missing-annotation failure.

**Biological meaning:** Biomass flux is being interpreted as a dry-weight growth rate without a chemically reconciled 1 g dry-weight basis. This affects biomass yield comparisons, consortium exchange budgets and SYMBIONT mass accounting. The test does not establish that measured biomass composition is wrong or that every coefficient should be multiplied by 1.10814. Products and polymerization by-products must be subtracted: total reactant mass is 12.9475401 g and product mass is 12.0451289 g, dominated by ATP turnover rather than retained cell material.

**Suggested improvement:** Rebuild a documented mass ledger from the original composition table and notebook, distinguishing free monomers from polymer residues, lipid pseudo-unit scaling, nucleic-acid by-products, measured versus estimated fractions, and ash/ion definitions. First resolve the separate fatty-acid representation defect. Keep a balanced GAM hydrolysis component separate from retained material and record the NGAM basis. Reconcile experimental composition before generating a named revised biomass variant; do not apply blanket rescaling or remove water just to pass.

**How to verify:** For any evidence-approved variant, publish the component mass ledger and provenance, achieve the stated 1 g dry-weight basis within a justified rounding tolerance, retain correct atom/charge bookkeeping for biosynthesis, specify GAM/NGAM units and assumptions, and reassess measured yields/growth under unchanged media. Preserve the original biomass as the baseline.

**Evidence:**

- reports/baseline-audit/memote-results.json: test_biomass_consistency.data.BIOMASS_Mcapsulatus = 0.9024111134789822.
- The 20 amino-acid terms total 5.311 mmol and 0.67687422222 g of free amino acids per nominal unit.
- Removing only the balanced GAM component of 23.08742079 mmol ATP hydrolysis exposes net water release of 5.31162623 mmol (0.09569043379 g), close in amount to amino-acid polymerization water. This numerical correspondence is a diagnostic lead, not proof of a correction.
- Original correction notebook cell 276 already recorded a biomass mass near 0.90234. The discrepancy predates the SYMBIONT adapter.

**Sources:** [Pinned original iMcBath SBML](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/ModelFiles/xml/iMcBath.xml); [MEMOTE 0.17.0 biomass tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_biomass.py); [MEMOTE 0.17.0 biomass support functions](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/biomass.py); [Lieven et al. (2018), original iMcBath reconstruction](https://doi.org/10.3389/fmicb.2018.02947); [Original biomass and average fatty-acid construction notebook](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/ComplementaryScripts/4.%20Full-Scale%20Biomass%20Reaction%20And%20Further%20Corrections.ipynb); [Original validation corrections notebook](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/ComplementaryScripts/8.%20Corrections%20to%20Validation.ipynb)


<a id="f65"></a>

### F65 — `test_fast_growth_default[BIOMASS_Mcapsulatus]`

**P3 · MEMOTE 0.17.0 assertion direction defect; no excessive-growth failure is demonstrated**

**Observed:** The model default FBA biomass flux is 0.1780041817185448 h^-1, below the test threshold 2.81 h^-1. Nevertheless the JUnit case fails. Both the installed source and official 0.17.0 tag compute outcome = growth > 2.81 and then assert outcome, while the docstring and lower-growth message expect growth below that threshold.

**Biological meaning:** This failure is not evidence that iMcBath grows too quickly. The nominal flux implies a doubling time of 3.89399 h, subject to the unresolved biomass mass basis. The test threshold corresponds to approximately 14.8 minutes. Passing this assertion by increasing model growth would contradict the intended biological check.

**Suggested improvement:** Keep the original audit unchanged and attach a version-specific interpretation or corrected supplementary assertion. Report the intended excessive-growth predicate independently; validate any updated MEMOTE release or local test patch before treating its pass/fail as comparable. No model coefficient change follows from this failure.

**How to verify:** A corrected check accepts a finite, feasible default growth below the stated threshold and flags a synthetic above-threshold case. Its output is clearly distinguished from the preserved MEMOTE 0.17.0 JUnit result; the original model remains unchanged.

**Evidence:**

- reports/baseline-audit/memote-results.json: test_fast_growth_default.data.BIOMASS_Mcapsulatus = false, result = failed; message explicitly describes lower growth as expected.
- Official tag 0.17.0 and installed memote/suite/tests/test_biomass.py lines 390-433 contain the contradictory assertion.
- The biomass_default_production result supplies the numerical default growth used for this interpretation.

**Sources:** [MEMOTE 0.17.0 biomass tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_biomass.py); [Pinned original iMcBath SBML](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/ModelFiles/xml/iMcBath.xml)


<a id="f66"></a>

### F66 — `test_essential_precursors_not_in_biomass[BIOMASS_Mcapsulatus]`

**P2 · Likely genuine omission of active pyridoxal phosphate and its dilution demand; not a simple identifier mismatch**

**Observed:** MEMOTE reports one missing universal precursor, MNXM161 (pyridoxal 5-prime-phosphate, PLP; C8H8NO6P, charge -2; BiGG pydx5p; KEGG C00018). The model instead contains pdx5p_c, pyridoxine 5-prime-phosphate (PNP; C8H10NO6P, charge -2; MNXM454; KEGG C00627), with no associated reactions and no biomass coefficient. The active PLP species cannot be identified by the MEMOTE helper.

**Biological meaning:** PLP is a catalytic vitamin B6 cofactor. An omitted biosynthesis/salvage requirement and biomass dilution demand can make cofactor synthesis appear dispensable and obscure nutrient dependencies. PNP differs chemically from PLP by two hydrogens; renaming it does not supply the missing active form. This finding does not prove the organism is auxotrophic, nor does it justify consuming one PLP molecule per catalytic enzyme turnover.

**Suggested improvement:** Review Bath genome annotations and organism-specific B6 synthesis/salvage evidence, represent correctly identified active PLP and supported conversion routes with GPR/provenance, and add only an evidence-supported biomass replacement/dilution demand. Review the disconnected PNP metabolite. Do not add an unrestricted exchange or arbitrary biomass coefficient just to satisfy the universal list.

**How to verify:** Correct PLP and PNP identities remain distinct; the model has a documented endogenous or supported salvage route under the declared medium, a justified growth-associated cofactor demand, and no artificial unlimited source. Recheck precursor producibility, biomass normalization and B6-pathway gene/nutrient predictions against available experiments, or label them unvalidated hypotheses.

**Evidence:**

- reports/baseline-audit/memote-results.json: test_essential_precursors_not_in_biomass lists [MNXM161], 1.12% of counted precursors.
- The SBML pdx5p_c annotation agrees with PNP (MNXM454/C00627); formula C8H10NO6P and zero attached reactions confirm this is not the active PLP pool.
- MEMOTE helper lookup for MNXM161 in compartment c fails; its internal mapping points to pydx5p/C00018 rather than pdx5p/C00627.

**Sources:** [Pinned original iMcBath SBML](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/ModelFiles/xml/iMcBath.xml); [MEMOTE 0.17.0 biomass tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_biomass.py); [MEMOTE 0.17.0 biomass support functions](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/biomass.py); [MetaNetX MNXM161 chemical identity](https://www.metanetx.org/chem_info/MNXM161); [Xavier et al. (2017), essential cofactor biomass formulations](https://doi.org/10.1016/j.ymben.2016.12.002)


<a id="f67"></a>

### F67 — `test_reaction_charge_balance`

**P1 · Mixed: ten exact encoded charge discrepancies and one floating-point false positive**

**Observed:** Raw MEMOTE flags 11 of 843 assessed reactions. Exact-decimal charge residuals are PFOR +1, CYP460ipp +2, ACCOAC_1 -1, BTNC +1, MC_Average_FattyAcid -0.001, HAORipp +2, APG3PAT_MCi +0.001, ASNTRAT +1, POR_syn -2 and G3PAT_MCi +0.001. MC_AFAA is exactly balanced; its -4.44e-16 floating residual is numerical. All metabolites have charges assigned.

**Biological meaning:** These flags concern the consistency of encoded chemistry rather than missing metadata. Redox-carrier electron counts and charged carrier/pseudo-lipid conventions can alter proton coupling, nutrient oxidation and predicted yields. Four affected reactions are disabled by baseline bounds [0,0] (ACCOAC_1, BTNC, HAORipp, ASNTRAT); their errors are latent until a variant enables them. The remaining exact discrepancies can affect allowed fluxes. Apart from the average-fatty-acid defect, the flagged equations are element balanced, so adding/removing H+ alone would introduce atom errors.

**Suggested improvement:** Audit shared carrier definitions and reaction evidence in groups: PFOR/POR_syn redox carriers; CYP460ipp/HAORipp products and cytochrome electron counts; ACCOAC_1/BTNC modified biotin; ASNTRAT aminoacyl-tRNA; and the full scaled lipid network. Specify a consistent protonation convention and distinguish true electron transfer from proton changes. Keep MC_AFAA as a numerical-only raw flag. Do not silently patch proton coefficients or broaden the tolerance until the exact ±0.001 lipid errors disappear from view.

**How to verify:** Each revised reaction preserves both atoms and charge under a stated chemical convention, changes to shared metabolite definitions are checked across every incident reaction, and literature supports carrier capacity/product identity. Recheck energy-generating cycles and medium-specific predictions after any accepted change. Report both the original MEMOTE result and the supplementary numerical classification.

**PFOR:** The model uses one oxidized flavodoxin (charge 0) and one reduced flavodoxin (charge -1), with identical XH formulas, for pyruvate oxidative decarboxylation. This is a candidate mismatch between a one-electron carrier convention and a two-electron substrate oxidation, not evidence for inserting a proton. Audit the intended flavodoxin electron capacity, substrate oxidation and MCA0769 evidence, jointly with POR_syn and every reaction sharing flxso_c/flxr_c.

**POR_syn:** The alternative MCA0769 pyruvate reaction consumes two fdxox_c and three protons. Both ferredoxin forms have charge 0; fdxrd_c instead adds H2 to its formula. The encoded equation is atom balanced but has charge residual -2. This mixes protonation and electron-carrier conventions. Resolve ferredoxin oxidation/protonation conventions across all linked reactions and reconcile parallel MCA0769 routes; do not patch this equation independently.

**CYP460ipp:** The encoded hydroxylamine-to-nitrite conversion transfers electrons to only two cytochrome-c-555 carriers, each reduced from charge +3 to +2. That substrate/product oxidation requires four electrons, explaining the +2 residual. Historical Bath experiments reported nitrite, whereas later P460 work discusses NO intermediates and N2O; model product choice also warrants review. Reconcile the intended net reaction, product(s), aerobic side chemistry and cytochrome electron count with organism-specific literature. Review HAORipp independently rather than making both enzymes duplicates or merely changing a proton coefficient.

**HAORipp:** Has the same hydroxylamine/nitrite and two-cytochrome equation as CYP460ipp and the same +2 charge residual, but bounds [0,0]. This latent inconsistency matters if a later scenario activates the reaction; expression evidence does not determine its stoichiometry. Audit the HAO-specific reaction, GPR and product evidence alongside CYP460ipp; retain explicit baseline disabled status until supported.

**ACCOAC_1:** The carboxybiotin and biotin carrier pseudo-species both have charge 0. Carboxyl transfer from acetyl-CoA(-4) to malonyl-CoA(-5) leaves residual -1. The paired BTNC residual is opposite, suggesting a shared modified-carrier representation issue even though the summed two-step pathway may cancel charge. Reconcile carboxybiotin versus biotin carrier protonation/charge consistently in both ACCOAC_1 and BTNC and other uses; check each reaction separately.

**BTNC:** ATP-dependent bicarbonate loading of the same charge-0 biotin carrier has residual +1, opposite ACCOAC_1. Cancellation across a pathway does not validate either individual reaction. Audit the shared carrier definition jointly with ACCOAC_1 before enabling this baseline-disabled route.

**ASNTRAT:** The encoded aspartyl-tRNA has charge 0 and asparaginyl-tRNA has charge +1; the ATP/glutamine amidotransferase reaction has charge residual +1 while preserving its encoded atoms. Audit aminoacyl-tRNA residue formulas, charge conventions and the intended amidation equation across linked tRNA reactions before changing protons or enabling this route.

**MC_Average_FattyAcid:** Eight fatty-acid reactant weights sum to 0.999, all with charge -1; product coefficient 1 and charge -1 yield exact -0.001 charge. The much larger atom mismatch arises from the 1000-fold formula conversion. Changing the product coefficient to 0.001 alone instead gives +0.998 charge. Resolve mixture normalization, pseudo-unit formula scale and charge scale jointly, propagating consistent definitions to downstream lipid synthesis and biomass.

**G3PAT_MCi:** The integer-scaled fatty-acyl-CoA pseudo-metabolite has charge -3001 and is consumed with coefficient 0.001. The glycerol-phosphate acyltransferase equation has exact +0.001 charge; its atom residuals are only floating-point noise. This is consistent with the notebook conversion/truncation problem, not a missing-formula problem. Audit all scaled lipid formulas and charges as a coupled representation; do not hide the exact charge discrepancy with an overly loose tolerance.

**APG3PAT_MCi:** The second acyltransferase similarly consumes 0.001 of the charge -3001 acyl-CoA pseudo-metabolite and has exact +0.001 charge. Its apparent atom imbalance is numerical only. Audit jointly with MC_Average_FattyAcid, MC_AFAA and G3PAT_MCi, maintaining consistent charge per encoded pseudo-unit.

**MC_AFAA:** The encoded charge sum is exactly zero under decimal recomputation; floating arithmetic gives -4.44e-16. This specific failure is not evidence for changing its chemistry, although the shared lipid representation still needs network-wide review. Retain the raw MEMOTE result and classify this residual as numerical with a declared supplementary tolerance or exact-decimal check.

**Evidence:**

- reports/baseline-audit/memote-results.json supplies all 11 IDs; decimal residuals and complete equations/formulas/charges are recorded in chemistry-details.json.
- CYP460ipp/HAORipp reduce two +3 ferricytochromes to +2 while converting hydroxylamine to nitrite; the encoded substrate/product conversion is a four-electron oxidation, giving the +2 discrepancy.
- The biotin-carrier pair has opposite charge residuals; both carrier states are encoded charge 0. The two glycerol-phosphate acyltransferases use a scaled acyl-CoA charge -3001 with coefficient 0.001, leaving exact +0.001.
- Notebook 8 formula_changer sets charge using integer conversion after rescaling; this motivates a network-wide pseudo-unit review rather than treating the lipid residuals as floating-point noise.

**Sources:** [Pinned original iMcBath SBML](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/ModelFiles/xml/iMcBath.xml); [MEMOTE 0.17.0 exact-zero conservation predicates](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency_helpers.py#L348); [Original validation corrections notebook](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/ComplementaryScripts/8.%20Corrections%20to%20Validation.ipynb); [Zahn et al. (1994), Bath cytochrome P460 hydroxylamine oxidation](https://doi.org/10.1128/jb.176.19.5879-5887.1994); [Bergmann et al. (1998), Bath P460 genes and four-electron oxidation](https://pmc.ncbi.nlm.nih.gov/articles/PMC107742/); [2019 Bath P460 structural and functional study; revised product context](https://pmc.ncbi.nlm.nih.gov/articles/PMC6427953/); [Poret-Peterson et al. (2008), Bath HAO ammonia response](https://doi.org/10.1038/ismej.2008.71)


<a id="f68"></a>

### F68 — `test_reaction_mass_balance`

**P1 · Mixed: one large genuine pseudo-metabolite unit defect and six exact-zero floating-point false positives**

**Observed:** Raw MEMOTE flags 7 of 843 assessed non-boundary/non-biomass reactions. Decimal recomputation shows six have exactly zero elemental residual; their floating residuals are at most 7.11e-15. MC_Average_FattyAcid instead has exact product-minus-reactant residuals C +16024.959, H +31023.945 and O +1996.002. This is not caused by absent formulas.

**Biological meaning:** The average-fatty-acid product retains coefficient 1 after its formula was expanded from a one-unit average to C16041H31055O1998, an integer representation 1000 times the weighted composition. The weighted inputs supply C16.041H31.055O1.998 (255.9320 g/mol on that averaging basis), whereas one product pseudo-unit weighs 255932.0166 g/mol. Downstream pseudo-lipid stoichiometry and biomass lipid coefficients are divided by 1000. This breaks elemental accounting and materially changes predicted growth/yields. A feasible S·v=0 solution or positive-mass stoichiometric consistency result does not validate the assigned chemical formulas.

**Suggested improvement:** Preserve the seven raw flags, but supplement them with an explicit numerical-tolerance or decimal audit so six numerical residuals do not trigger chemistry edits. For the real defect, review the original fatty-acid distribution and choose a single consistent pseudo-unit representation, propagating atom counts, charges and coefficients through every linked reaction and biomass. Separately resolve the 0.999 reactant-weight sum from rounding; do not conflate that 0.1% issue with the factor-1000 error. Treat any isolated coefficient change as a diagnostic until the whole representation passes conservation and phenotype checks.

**How to verify:** A reviewed variant has consistent units across synthesis, activation, phospholipid synthesis and biomass; atom and charge balances meet a declared tight tolerance (or exact finite-decimal equality); mixture proportions have source provenance; all affected bounds/units are assessed if reaction scaling changes; and yields are revalidated. The unchanged original baseline and candidate limitations remain available for comparison.

**Evidence:**

- reports/baseline-audit/memote-results.json records the seven reaction IDs; exact-zero comparisons are in MEMOTE 0.17.0 support/consistency_helpers.py.
- Numerical-only elemental flags: PHCYT_MCi, MC_AFAA, PGSA_MCi, APG3PAT_MCi, PSSA_MCi and G3PAT_MCi. APG3PAT_MCi and G3PAT_MCi still have exact charge discrepancies handled separately.
- Notebook 4 cell 215 builds the weighted fatty-acid reaction with product coefficient 1. Notebook 8 cells 254-269 replace the average formula with integer counts and divide downstream pseudo-metabolite coefficients by 1000; cell 275 divides biomass lipid coefficients by 1000.
- An isolated in-memory product-coefficient 1→0.001 diagnostic removed the elemental residual but changed charge residual to +0.998, so it is not an accepted correction. Default pFBA mu changed 0.1780041644→0.1606294615 (-9.7608%); reference mu changed 0.2255827703→0.1947779028 (-13.6557%). Original SBML hash is unchanged.

**Sources:** [Pinned original iMcBath SBML](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/ModelFiles/xml/iMcBath.xml); [MEMOTE 0.17.0 exact-zero conservation predicates](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency_helpers.py#L348); [Original biomass and average fatty-acid construction notebook](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/ComplementaryScripts/4.%20Full-Scale%20Biomass%20Reaction%20And%20Further%20Corrections.ipynb); [Original validation corrections notebook](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/ComplementaryScripts/8.%20Corrections%20to%20Validation.ipynb)


<a id="f69"></a>

### F69 — `test_blocked_reactions`

**P1 · Mixed constraints and network gaps**

**Observed:** 256 of 913 reactions cannot carry flux with exchange reactions opened. Of those, 66 already have bounds (0,0): 58 internal reactions and 8 sink boundaries.

**Biological meaning:** The model contains inactive routes because of fixed constraints, missing precursor supply, missing downstream consumption or conserved-cofactor limitations. A blocked reaction does not prove that the organism lacks its enzyme. pMMO routes, several tRNA charging reactions and selected nitrogen routes are stored with zero bounds; their intended condition-specific rationale must be checked against reconstruction records.

**Suggested improvement:** Classify the 66 explicitly closed reactions separately; document condition-specific choices. Trace the remaining 190 through substrate/product connectivity and cofactor balance. Reopen or gapfill only when supported by Bath physiology and the intended condition.

**How to verify:** Report FVA under both preserved-condition bounds and a documented structural diagnostic. Every reopened route has evidence and passes element/charge, energy-cycle and phenotype checks. Never open every internal bound to erase the count.

COBRApy open_exchanges=True opens exchanges, not every sink/demand or internal reaction. EX_n2_e is also initially closed but is opened by that diagnostic, explaining why the model has 67 zero-bounded reactions but only 66 of them remain in this list.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [COBRApy blocked-reaction analysis](https://cobrapy.readthedocs.io/en/latest/autoapi/cobra/flux_analysis/variability/index.html)


<a id="f70"></a>

### F70 — `test_find_stoichiometrically_balanced_cycles`

**P1 · Potential internal loops; altered diagnostic bounds**

**Observed:** 51 reactions can participate in internal cycles under MEMOTE’s diagnostic boundary handling.

**Biological meaning:** A balanced internal loop can carry flux without net exchange, obscuring flux interpretation. It is not automatically an ATP- or reductant-generating cycle. Equal reversible duplicate reactions can form a harmless mathematical loop; wrong reversibility or cofactor coupling can produce more serious defects.

**Suggested improvement:** Start with GUAt2pp/XANt2pp and the redox/cofactor variants in the list. Compare FVA with loopless constraints and with physiologically justified directionality. Separate cycles enabled only by the diagnostic from those possible under the SYMBIONT profile.

**How to verify:** Document representative cycle flux vectors, compartment/cofactor changes and feasibility under production constraints. Accepted constraints remove unsupported loops without losing known phenotypes; energy-dissipation tests remain separate.

Crucial implementation detail: close_boundaries_sensibly resets EVERY internal reaction to (-1,1) if reversible, otherwise (0,1), then closes boundaries. This can reopen reactions fixed to zero in the baseline, e.g. NTPP8. The 51-reaction result therefore is not a direct statement that all 51 cycle in the actual reference simulation. It also resets fixed ATPM from (8.39,8.39) to (0,1). The returned list uses an FVA range reaching +1 or -1 within 1e-7, rather than simply detecting every nonzero flux.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [MEMOTE consistency algorithms](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency.py); [MEMOTE compartment and boundary helpers](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/helpers.py)


<a id="f71"></a>

### F71 — `test_find_orphans`

**P1 · Structural precursor-supply gap**

**Observed:** 74 of 879 metabolites have consuming reactions but no producing reaction under the structural direction/bound test.

**Biological meaning:** At steady state, consuming an internal metabolite requires a replenishing route. Orphans can block dependent pathways. They can also be remnants of incomplete or out-of-scope pathways rather than evidence of an actual cellular deficiency.

**Suggested improvement:** Trace each orphan to a supported biosynthetic, transport or salvage source; inspect its formula/identifier and current reaction bounds first. Repair proven missing steps or document/prune unsupported disconnected scope in a derivative model.

**How to verify:** Each retained metabolite has an evidence-supported supply route when its pathway should function; no arbitrary source/sink is added. Recheck blocked reactions and relevant nutrient/knockout phenotypes.

All 74 are included in the unproducible-metabolite list; 57 are also unconsumable. Examples include methionine-salvage intermediates and 6-pyruvoyltetrahydropterin. These overlaps must not be counted as independent defects.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [MEMOTE consistency algorithms](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency.py)


<a id="f72"></a>

### F72 — `test_find_deadends`

**P1 · Real product-disposal gaps plus defective assertion**

**Observed:** 81 of 879 metabolites have producing reactions but no consuming reaction. The test then compares the returned list directly with integer zero (data == 0), which would fail even for an empty list.

**Biological meaning:** A dead-end product cannot accumulate indefinitely in a steady-state model, so its production route may be blocked. Missing degradation, export or biomass use are possible explanations; indiscriminate drains would hide incorrect chemistry.

**Suggested improvement:** Correct the assertion to test list length/emptiness. Review each metabolite for documented consumption, secretion or biomass incorporation; remove unsupported scope only with a recorded decision.

**How to verify:** A zero-result fixture passes the corrected check and a known dead-end fixture fails. Curated disposal routes conserve chemistry and preserve observed phenotype constraints.

All 81 occur in the unconsumable list and 55 in the unproducible list. Examples include cadaverine and sulfur-containing products. The current data show real dead ends even though the predicate itself is faulty.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [MEMOTE consistency algorithms](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency.py)


<a id="f73"></a>

### F73 — `test_find_disconnected`

**P2 · Unused model inventory**

**Observed:** 58 of 879 metabolites participate in no reaction at all.

**Biological meaning:** These entries cannot influence flux directly. They may be retained reconstruction inventory, obsolete alternatives or remnants of removed pathways. Their presence inflates model and annotation counts and makes scope less clear.

**Suggested improvement:** For each entry, either connect it through evidence-supported reactions if needed by the intended model scope, or archive its annotation/provenance and remove it from a separately curated derivative. Prioritize confusing duplicate lipid and cofactor species.

**How to verify:** Removal of a truly isolated metabolite leaves feasible fluxes/objective unchanged and preserves an archive mapping. Any newly connected metabolite receives justified chemistry and tests.

All 58 appear in both unproducible and unconsumable lists. Examples include 12dgr_EC_c and unused quinone intermediates; their removal alone does not repair any active metabolic pathway.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [MEMOTE consistency algorithms](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency.py)


<a id="f74"></a>

### F74 — `test_find_metabolites_not_produced_with_open_bounds`

**P1 · Flux-based production limitation**

**Observed:** 329 of 879 metabolites cannot be individually produced with exchange reactions opened; this includes all 74 orphans and all 58 isolated metabolites.

**Biological meaning:** The network cannot sustain a drain for each of these individual species. Beyond obvious missing reactions, causes include closed internal bounds and conserved carrier pools. Inability to synthesize an isolated carrier moiety does not necessarily mean that the model cannot recycle that carrier during growth.

**Suggested improvement:** Separate isolated/orphan species, intentionally disabled pathways, conserved pools and remaining coupled bottlenecks. Review flux status and limiting constraints per case; prioritize biomass/cofactor and methane–nitrogen paths relevant to the intended profile.

**How to verify:** Producibility tests record objective value, solver status, medium and internal bounds. Supported biomass/cofactor supply is verified without creating arbitrary sources or treating an unmodeled carrier pool as a reason to fabricate a pathway.

Despite the test title/summary, the helper opens model.exchanges only, retaining other internal and sink/demand constraints. It treats NaN/infeasibility or values below model tolerance as blocked. The baseline biomass-precursor tests pass separately.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [MEMOTE consistency algorithms](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency.py); [MEMOTE compartment and boundary helpers](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/helpers.py)


<a id="f75"></a>

### F75 — `test_find_metabolites_not_consumed_with_open_bounds`

**P1 · Flux-based consumption limitation**

**Observed:** 369 of 879 metabolites cannot be individually consumed with exchanges opened; this includes all 81 structural dead ends and all 58 isolated species.

**Biological meaning:** The network cannot sustain a source into each species followed by net consumption. Missing downstream reactions, fixed bounds and conserved-moiety restrictions can cause this. It is a capacity/scope diagnostic, not a measurement of intracellular accumulation.

**Suggested improvement:** Group by isolated species, dead ends, cofactor/carrier pools and coupled pathway constraints. Add supported recycling/export/incorporation routes or narrow documented model scope; audit topology before adding sinks.

**How to verify:** Each accepted change has physiological evidence and is checked for element/charge conservation, effects on growth/yield and unintended alternative nutrient use. Record solver status and the exact diagnostic medium.

The 329 and 369 sets overlap and should not be added to count distinct biological defects. Complete affected IDs and their participating reactions are supplied in network-details.json.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [MEMOTE consistency algorithms](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency.py); [MEMOTE compartment and boundary helpers](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/helpers.py)


<a id="f76"></a>

### F76 — `test_metabolite_sbo_presence`

**P2 · metadata gap and checker defect**

**Observed:** 858 of 879 components lack the expected SBO annotation; MEMOTE result failed.

**Biological meaning:** 858 of 879 SBML-loaded species have no SBO key; 21 have SBO:0000247. The underlying metadata gap is real despite the inverted assertion.

**Suggested improvement:** Assign an appropriate SBO entity class to each of the 858 missing species after distinguishing small molecules, macromolecules and averaged pools. Fix the inverted audit predicate separately; retain the original result and verify that stoichiometry, bounds and objectives are unchanged.

**How to verify:** All applicable components have correct SBO metadata. A reviewed checker expects zero missing terms. Preserve the baseline and ensure annotation-only changes leave the computational model unchanged.

Recorded checker predicate: `assert len(ann["data"]) == len(model.metabolites), ann["message"]`.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_sbo.py:58

**Sources:** [MEMOTE implementation and documentation](https://raw.githubusercontent.com/opencobra/memote/0.17.0/src/memote/suite/tests/test_sbo.py); [MEMOTE implementation and documentation](https://memote.readthedocs.io/en/latest/autoapi/test_sbo/index.html); [SBO ontology](https://raw.githubusercontent.com/EBI-BioModels/SBO/master/SBO_OBO.obo)


<a id="f77"></a>

### F77 — `test_reaction_sbo_presence`

**P2 · metadata gap and checker defect**

**Observed:** 772 of 913 components lack the expected SBO annotation; MEMOTE result failed.

**Biological meaning:** 772 of 913 SBML-loaded reactions have no SBO key. Of the 141 annotated reactions, 98 use generic SBO:0000375 (process), and 43 use SBO:0000627 (exchange reaction).

**Suggested improvement:** Classify the 772 unannotated reactions by function, then assign the appropriate biochemical, transport, exchange, demand, sink or biomass term. Review the 98 generic process terms for more specific classification. Correct the inverted audit predicate separately and verify boundary classification after annotation changes.

**How to verify:** All applicable components have correct SBO metadata. A reviewed checker expects zero missing terms. Preserve the baseline and ensure annotation-only changes leave the computational model unchanged.

Recorded checker predicate: `assert len(ann["data"]) == len(model.reactions), ann["message"]`.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_sbo.py:89

**Sources:** [MEMOTE implementation and documentation](https://raw.githubusercontent.com/opencobra/memote/0.17.0/src/memote/suite/tests/test_sbo.py); [MEMOTE implementation and documentation](https://memote.readthedocs.io/en/latest/autoapi/test_sbo/index.html); [SBO ontology](https://raw.githubusercontent.com/EBI-BioModels/SBO/master/SBO_OBO.obo)


<a id="f78"></a>

### F78 — `test_metabolite_specific_sbo_presence`

**P2 · metadata gap and checker defect**

**Observed:** 858 of 879 components lack the expected SBO annotation; MEMOTE result failed.

**Biological meaning:** 858 species lack SBO:0000247; none of those 858 has another SBO. The failure message incorrectly calls these transport reactions. A blanket simple-chemical annotation needs semantic review for macromolecular/lumped species; this checker tests exact strings rather than ontology relationships.

**Suggested improvement:** Use SBO:0000247 (simple chemical) for applicable defined small molecules. Review proteins, tRNAs, polymers and averaged lipid pools for semantically correct ontology classes instead of labeling everything as a simple chemical. Record justified exceptions and correct the inverted predicate.

**How to verify:** All applicable components have correct SBO metadata. A reviewed checker expects zero missing terms. Preserve the baseline and ensure annotation-only changes leave the computational model unchanged.

Recorded checker predicate: `assert len(ann["data"]) == len(model.metabolites), ann["message"]`.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_sbo.py:231

**Sources:** [MEMOTE implementation and documentation](https://raw.githubusercontent.com/opencobra/memote/0.17.0/src/memote/suite/tests/test_sbo.py); [MEMOTE implementation and documentation](https://memote.readthedocs.io/en/latest/autoapi/test_sbo/index.html); [SBO ontology](https://raw.githubusercontent.com/EBI-BioModels/SBO/master/SBO_OBO.obo)


<a id="f79"></a>

### F79 — `test_exchange_specific_sbo_presence`

**P2 · metadata gap and checker defect**

**Observed:** 5 of 48 components lack the expected SBO annotation; MEMOTE result failed.

**Biological meaning:** Exactly EX_ch4_e, EX_co_e, EX_fol_e, EX_ham_e, and EX_n2_e lack the expected exchange term. The other 43 of 48 detected exchanges have it. The failure has a real metadata basis even though the assertion is inverted.

**Suggested improvement:** Verify EX_ch4_e, EX_co_e, EX_fol_e, EX_ham_e and EX_n2_e are external exchange reactions, then annotate them SBO:0000627. Keep transport between compartments distinct from environment exchange; fix the inverted audit predicate and verify that intended exchange classification is retained.

**How to verify:** All applicable components have correct SBO metadata. A reviewed checker expects zero missing terms. Preserve the baseline and ensure annotation-only changes leave the computational model unchanged.

Recorded checker predicate: `assert len(ann["data"]) == len(exchanges), ann["message"]`.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_sbo.py:309

**Sources:** [MEMOTE implementation and documentation](https://raw.githubusercontent.com/opencobra/memote/0.17.0/src/memote/suite/tests/test_sbo.py); [MEMOTE implementation and documentation](https://memote.readthedocs.io/en/latest/autoapi/test_sbo/index.html); [SBO ontology](https://raw.githubusercontent.com/EBI-BioModels/SBO/master/SBO_OBO.obo)


<a id="f80"></a>

### F80 — `test_biomass_specific_sbo_presence`

**P2 · metadata gap**

**Observed:** 1 of 1 components lack the expected SBO annotation; MEMOTE result failed.

**Biological meaning:** BIOMASS_Mcapsulatus lacks SBO:0000629. This test correctly asserts zero missing terms and is a genuine annotation failure, without the inversion defect.

**Suggested improvement:** Annotate BIOMASS_Mcapsulatus with SBO:0000629 (biomass production) in a tracked derivative. This improves semantic discovery of the biomass objective; it does not resolve the separate dry-mass normalization or cofactor findings.

**How to verify:** All applicable components have correct SBO metadata. A reviewed checker expects zero missing terms. Preserve the baseline and ensure annotation-only changes leave the computational model unchanged.

Recorded checker predicate: `assert len(ann["data"]) == 0, ann["message"]`.

**Evidence:**

- reports/baseline-audit/junit.xml
- reports/baseline-audit/memote-results.json
- work/.venv/Lib/site-packages/memote/suite/tests/test_sbo.py:447

**Sources:** [MEMOTE implementation and documentation](https://raw.githubusercontent.com/opencobra/memote/0.17.0/src/memote/suite/tests/test_sbo.py); [MEMOTE implementation and documentation](https://memote.readthedocs.io/en/latest/autoapi/test_sbo/index.html); [SBO ontology](https://raw.githubusercontent.com/EBI-BioModels/SBO/master/SBO_OBO.obo)


## Individual skipped cases


<a id="s01"></a>

### S01 — `work..venv.Lib.site-packages.memote.suite.tests.test_thermodynamics`

**P1 · Suite feature disabled**

**Observed:** Module collection is skipped: thermodynamic tests are disabled until upgrade to a new equilibrator-api version.

**Biological meaning:** No thermodynamic reaction-direction feasibility result was obtained. Flux/stoichiometric consistency alone does not establish a feasible Gibbs-energy profile or account for pH, redox state and membrane potential.

**Suggested improvement:** Implement a separately versioned thermodynamic assessment using a compatible supported API and verified compound mappings. Specify temperature, pH, ionic strength, concentration ranges and membrane conventions appropriate to the modeled scenario; label unsupported lumped species explicitly.

**How to verify:** The tool runs with mapped/unmapped coverage and uncertainty reported; direction changes are supported by energy ranges and phenotype checks. Do not claim thermodynamic validation from the baseline’s pass count.

This is one module-level skipped JUnit entry, not proof that one individual thermodynamic test was attempted. Enabling a disabled module may introduce several cases and change suite counts.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE disabled thermodynamics module](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_thermodynamics.py)


<a id="s02"></a>

### S02 — `test_detect_energy_generating_cycles[MNXM191]`

**P1 · Compartment lookup gap; metabolites present**

**Observed:** MNXM191 lookup fails in cytosol c, but both redox partners are present in inner-membrane compartment im: q8h2_im / q8_im.

**Biological meaning:** This is an audit coverage gap caused by compartment selection, not absence of ubiquinol biology. The membrane quinone pool participates in respiratory electron transfer and is particularly relevant to methane oxidation and energy yield.

**Suggested improvement:** Extend the energy-cycle diagnostic to use the actual membrane quinone pool, with explicit proton-side and redox conventions. Check both oxidized/reduced mappings and the respiratory reactions. Keep these metabolites in their biologically intended compartment.

**How to verify:** A compartment-aware closed-uptake dissipation test runs for the existing Q8 pool, reports its assumptions and flux residuals, and either rules out a cycle under those conditions or supplies its reaction evidence. Do not move Q8 into cytosol merely to satisfy the lookup.

The helper identifies the main compartment as c and filters its candidates to c. q8h2_im has formula C49H76O4; q8_im has C49H74O4. Eleven other baseline energy couples passed, but do not cover this skipped membrane pool.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [MEMOTE consistency algorithms](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency.py); [MEMOTE compartment and boundary helpers](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/helpers.py); [MEMOTE pinned redox cross-reference shortlist](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/data/met_id_shortlist.json); [MetaNetX MNXM191](https://www.metanetx.org/chem_info/MNXM191)


<a id="s03"></a>

### S03 — `test_detect_energy_generating_cycles[MNXM223]`

**P3 · Absent model carrier; applicability review**

**Observed:** MNXM223 (menaquinol-8 / menaquinone-8) is not found by the cytosolic lookup; no corresponding pair was identified in the inspected model inventory.

**Biological meaning:** The suite cannot assess resource-free generation of the reduced carrier in the menaquinol-8 / menaquinone-8 couple. This absence is not evidence that Bath must contain this quinone chain length or that a pathway must be added.

**Suggested improvement:** Document whether this carrier pair belongs to the intended Bath model scope using strain-specific biochemical evidence. If absent by design, retain an explicit not-applicable reason. If evidence establishes its presence, curate the actual pathway and both partner mappings before adding a diagnostic.

**How to verify:** Either a documented organism/model-scope exclusion remains visible, or an evidence-supported mapped pair is tested. Do not create metabolites and reactions solely to turn a skip into a pass.

The MEMOTE 0.17 mapping uses reduced MNXM223 and oxidized MNXM509. The inventory contains Q8 in im, but no equivalent menaquinone/demethylmenaquinone pair under the inspected names/identifiers. Current MetaNetX identifiers may be deprecated or split; resolve identities rather than blindly replacing IDs.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [MEMOTE consistency algorithms](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency.py); [MEMOTE compartment and boundary helpers](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/helpers.py); [MEMOTE pinned redox cross-reference shortlist](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/data/met_id_shortlist.json); [MetaNetX MNXM223](https://www.metanetx.org/chem_info/MNXM223)


<a id="s04"></a>

### S04 — `test_detect_energy_generating_cycles[MNXM7517]`

**P3 · Absent model carrier; applicability review**

**Observed:** MNXM7517 (menaquinol-6 / menaquinone-6) is not found by the cytosolic lookup; no corresponding pair was identified in the inspected model inventory.

**Biological meaning:** The suite cannot assess resource-free generation of the reduced carrier in the menaquinol-6 / menaquinone-6 couple. This absence is not evidence that Bath must contain this quinone chain length or that a pathway must be added.

**Suggested improvement:** Document whether this carrier pair belongs to the intended Bath model scope using strain-specific biochemical evidence. If absent by design, retain an explicit not-applicable reason. If evidence establishes its presence, curate the actual pathway and both partner mappings before adding a diagnostic.

**How to verify:** Either a documented organism/model-scope exclusion remains visible, or an evidence-supported mapped pair is tested. Do not create metabolites and reactions solely to turn a skip into a pass.

The MEMOTE 0.17 mapping uses reduced MNXM7517 and oxidized MNXM12235. The inventory contains Q8 in im, but no equivalent menaquinone/demethylmenaquinone pair under the inspected names/identifiers. Current MetaNetX identifiers may be deprecated or split; resolve identities rather than blindly replacing IDs.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [MEMOTE consistency algorithms](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency.py); [MEMOTE compartment and boundary helpers](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/helpers.py); [MEMOTE pinned redox cross-reference shortlist](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/data/met_id_shortlist.json)


<a id="s05"></a>

### S05 — `test_detect_energy_generating_cycles[MNXM12233]`

**P3 · Absent model carrier; applicability review**

**Observed:** MNXM12233 (menaquinol-7 / menaquinone-7) is not found by the cytosolic lookup; no corresponding pair was identified in the inspected model inventory.

**Biological meaning:** The suite cannot assess resource-free generation of the reduced carrier in the menaquinol-7 / menaquinone-7 couple. This absence is not evidence that Bath must contain this quinone chain length or that a pathway must be added.

**Suggested improvement:** Document whether this carrier pair belongs to the intended Bath model scope using strain-specific biochemical evidence. If absent by design, retain an explicit not-applicable reason. If evidence establishes its presence, curate the actual pathway and both partner mappings before adding a diagnostic.

**How to verify:** Either a documented organism/model-scope exclusion remains visible, or an evidence-supported mapped pair is tested. Do not create metabolites and reactions solely to turn a skip into a pass.

The MEMOTE 0.17 mapping uses reduced MNXM12233 and oxidized MNXM12236. The inventory contains Q8 in im, but no equivalent menaquinone/demethylmenaquinone pair under the inspected names/identifiers. Current MetaNetX identifiers may be deprecated or split; resolve identities rather than blindly replacing IDs.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [MEMOTE consistency algorithms](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency.py); [MEMOTE compartment and boundary helpers](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/helpers.py); [MEMOTE pinned redox cross-reference shortlist](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/data/met_id_shortlist.json); [MetaNetX MNXM12233](https://www.metanetx.org/chem_info/MNXM12233)


<a id="s06"></a>

### S06 — `test_detect_energy_generating_cycles[MNXM558]`

**P3 · Absent model carrier; applicability review**

**Observed:** MNXM558 (2-demethylmenaquinol-8 / 2-demethylmenaquinone-8) is not found by the cytosolic lookup; no corresponding pair was identified in the inspected model inventory.

**Biological meaning:** The suite cannot assess resource-free generation of the reduced carrier in the 2-demethylmenaquinol-8 / 2-demethylmenaquinone-8 couple. This absence is not evidence that Bath must contain this quinone chain length or that a pathway must be added.

**Suggested improvement:** Document whether this carrier pair belongs to the intended Bath model scope using strain-specific biochemical evidence. If absent by design, retain an explicit not-applicable reason. If evidence establishes its presence, curate the actual pathway and both partner mappings before adding a diagnostic.

**How to verify:** Either a documented organism/model-scope exclusion remains visible, or an evidence-supported mapped pair is tested. Do not create metabolites and reactions solely to turn a skip into a pass.

The MEMOTE 0.17 mapping uses reduced MNXM558 and oxidized MNXM2178. The inventory contains Q8 in im, but no equivalent menaquinone/demethylmenaquinone pair under the inspected names/identifiers. Current MetaNetX identifiers may be deprecated or split; resolve identities rather than blindly replacing IDs.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE 0.17 consistency tests](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_consistency.py); [MEMOTE consistency algorithms](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/consistency.py); [MEMOTE compartment and boundary helpers](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/helpers.py); [MEMOTE pinned redox cross-reference shortlist](https://github.com/opencobra/memote/blob/0.17.0/src/memote/support/data/met_id_shortlist.json); [MetaNetX MNXM558](https://www.metanetx.org/chem_info/MNXM558)


<a id="s07"></a>

### S07 — `test_gene_essentiality_from_data_qualitative[experiment0]`

**P1 · Experimental evidence not supplied**

**Observed:** Pytest received an empty experiment parameter set; no qualitative gene-essentiality experiment was run. The inherited data directory has no essentiality table.

**Biological meaning:** No comparison has tested whether predicted lethal gene deletions agree with measured Bath phenotypes. GPR completeness and feasible wild-type growth cannot establish gene-level predictive accuracy.

**Suggested improvement:** Obtain a licensed/provenanced Bath-specific deletion or essentiality dataset with medium, strain and endpoint definitions; reconcile gene identifiers, specify the experiment configuration, and reserve independent validation data.

**How to verify:** Report TP/FP/TN/FN and an appropriate balanced metric alongside accuracy, uncertainty and dataset size. A generic >0.95 accuracy target alone is inadequate for an imbalanced essentiality dataset.

The inherited experiments.yml defines an essentiality path but no essentiality experiments/data. This skip must remain until actual reference evidence is available; generated labels are not experiments.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE essentiality comparison](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_essentiality.py); [iMcBath pinned data configuration](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/data/experiments.yml)


<a id="s08"></a>

### S08 — `test_growth_from_data_qualitative[experiment0]`

**P1 · Available historical data not configured in audit**

**Observed:** Pytest received an empty experiment parameter set. This baseline run did not load the inherited growth configuration.

**Biological meaning:** No experimental growth/no-growth comparison contributes to this audit. Obtaining a positive biomass objective demonstrates model feasibility under bounds, not agreement with observed substrate use or reactor trajectories.

**Suggested improvement:** Validate and port the preserved experiments.yml and growth/media CSV files to the current test interface, checking literature provenance and units. Run the four configured experiments as historical regression tests, then add independent SYMBIONT validation with measured biomass, substrate and gas balances.

**How to verify:** Report each historical condition and confusion matrix with explicit model/profile version. Keep published-data regression separate from held-out process validation. Record unsupported or ambiguous observations rather than silently relabeling them.

The inherited configuration includes nitrogen-source growth, carbon-source growth, and CO2 cofeeding with H2 or formate (four experiment definitions, three growth CSV files). Their presence in the repository does not mean they were used by the fresh audit.

**Evidence:**

Original JUnit case and raw MEMOTE data; independently inspected unchanged SBML. See network-details.json for equations, bounds and complete entity evidence.

**Sources:** [MEMOTE growth comparison](https://github.com/opencobra/memote/blob/0.17.0/src/memote/suite/tests/test_growth.py); [iMcBath pinned data configuration](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/data/experiments.yml)


## Additional checker limitations discovered among passing cases

These six cases are **outside** the requested 80 failures and 8 skips. They are retained as extra findings because all six pass due to inverted SBO predicates even though every assessed component lacks the expected term. They do not change the raw 80/59/8 reconciliation.

| Reported passing case | Missing/nonmatching | Interpretation |
| --- | ---: | --- |

| `test_gene_sbo_presence` | 730/730 | All 730 gene annotations are empty. The reported pass is a false pass caused by the inverted assertion. |

| `test_metabolic_reaction_specific_sbo_presence` | 721/721 | All 721 detected pure metabolic reactions lack the exact expected term. 668 have no SBO and 53 have generic SBO:0000375. The pass is false; the count includes both absent and insufficiently specific terms. |

| `test_transport_reaction_specific_sbo_presence` | 122/122 | All 122 detected transport reactions lack an accepted transport term. 77 have no SBO and 45 have generic SBO:0000375. The pass is false. The message also incorrectly labels transport reactions as metabolic/biochemical. |

| `test_gene_specific_sbo_presence` | 730/730 | All 730 genes lack SBO:0000243. The pass is false; this does not imply the model has no genes or GPR rules. |

| `test_demand_specific_sbo_presence` | 12/12 | All 12 detected demands lack SBO:0000628 and have no SBO. Reported pass is false. The first docstring line wrongly says SBO:0000627, but code uses 0000628; the message also wrongly says genes. |

| `test_sink_specific_sbo_presence` | 1/1 | The one detected sink, SK_cyan_c, has no SBO:0000632 or other SBO. Reported pass is false. The message wrongly says genes. |


Four further SBO predicates are also inverted but currently fail with genuine partial annotation gaps; the biomass SBO predicate is correct. See the [source audit](../reports/failure-review/sbo-source-audit.json). Updating or patching the test suite can increase failures while making the assessment more truthful. A target of “zero red tests” is therefore not an adequate scientific acceptance criterion.

## Limits and next decision

This is a complete case-by-case review of the recorded nonpassing audit, supported by source inspection and targeted model calculations. It is not a fresh full-suite rerun, a fully corrected reconstruction, or experimental validation. The preserved baseline, source hashes and original raw results remain unchanged. Proposed scientific edits should be introduced as named, reviewable model variants with explicit coefficient/formula/charge/GPR provenance and a new audit.

For SYMBIONT, record separately: the immutable reconstruction, any scientifically curated variant, condition-specific bounds, and reactor calibration/measurement assumptions. Metadata repairs improve traceability; they do not establish process prediction accuracy.
