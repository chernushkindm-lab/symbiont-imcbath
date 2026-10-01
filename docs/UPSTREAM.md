# Upstream model and provenance

The model requested as “iBath” is **iMcBath**, Christian Lieven and colleagues' genome-scale metabolic model of *Methylococcus capsulatus* (Bath). The original repository is [ChristianLieven/memote-m-capsulatus](https://github.com/ChristianLieven/memote-m-capsulatus); the publication is [Lieven et al., Frontiers in Microbiology (2018), DOI 10.3389/fmicb.2018.02947](https://doi.org/10.3389/fmicb.2018.02947).

This repository provides an independently usable SYMBIONT integration around a preserved source model. The publication describes a curated network and tests of metabolic hypotheses; it does not validate a particular SYMBIONT deployment or a different strain. Any VS1/Bath equivalence remains an explicitly declared simulation assumption.

## Pinned source

- Upstream revision: [`f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160`](https://github.com/ChristianLieven/memote-m-capsulatus/tree/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160).
- Retrieved and checked: 2026-10-01.
- Current source branch at retrieval: `master`. The upstream README and paper's `develop` link is historical; the GitHub branch listing returned only `master` and `gh-pages` on this date.
- Local JSON inspection: model ID `iMcBath`; 913 reactions, 879 metabolites, 730 genes; biomass objective `BIOMASS_Mcapsulatus` with coefficient 1. The preserved `ATPM` reaction has lower and upper bounds both equal to 8.39.

The following SHA-256 values describe the delivered files' exact bytes:

| File | SHA-256 |
| --- | --- |
| `ModelFiles/xml/iMcBath.xml` | `c2591237d8968164faeb8fafe741a9a42f95131b919086d5eb1a14b159fee092` |
| `ModelFiles/json/iMcBath.json` | `92ae700bd42fae2339a1b2ad2d3d6c6011e7004d163bf4c708f4bed0b944bdda` |
| `ModelFiles/yml/iMcBath.yml` | `ade8aa1a71d1fb406f7ab85aab40b51477876720eff0a4558d0eb0e777836038` |

Exact Git blob identity was also checked using `git hash-object --no-filters` against the pinned commit's `git ls-tree` output:

| Format | Git blob ID |
| --- | --- |
| SBML/XML | `57050fb95e87f4af398f6bbc6861fb8094602210` |
| JSON | `f33b986e4b33dc26184dddeb9815b88630f2338b` |
| YAML | `1bcc3e1bfb04ccd01ca59d471a11d16e0b2110a6` |

All three files match the canonical upstream Git blobs. A Windows checkout may convert LF line endings to CRLF and consequently produce different SHA-256 values without changing model content. The delivered files use the canonical LF bytes; the inspected Windows source checkout matched after CRLF-to-LF normalization.

## What is historical

`ComplementaryScripts/`, `ComplementaryData/`, `data/`, `MetabolicMap/`, `MCapsReport.html`, and the upstream root `index.html` preserve source material. Their presence does **not** mean that the original notebooks, publication tables, experimental validation, or report history were rerun here. New validation evidence must identify its model hash, software environment, command, and timestamp; see [MEMOTE.md](MEMOTE.md).

The upstream [README](https://github.com/ChristianLieven/memote-m-capsulatus/blob/f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160/README.md) records Python 2.7.9, COBRApy 0.8.1, pandas 0.22.0 and NumPy 1.14.0. Its `requirements.txt` only says `memote>=0.4.1`. These do not specify a reproducible modern environment, and old notebooks can require porting. The new integration's dependency files govern its execution. Retain upstream notebooks as historical reconstruction evidence until each is independently checked.

## License and citation

Upstream uses the ISC license, copyright © 2018 Christian Lieven. It permits use, copying, modification and distribution while requiring the copyright and permission notices to remain in copies. The original [LICENSE](../LICENSE) is retained. Preserve it when redistributing the model, and cite both the paper and upstream repository. MEMOTE itself has a separate Apache 2.0 license; installing or using it does not replace the model's license.

The paper also notes that some underlying biomass-composition data are subject to access restrictions. The repository license should not be interpreted as supplying or granting rights to third-party datasets absent from this distribution.
