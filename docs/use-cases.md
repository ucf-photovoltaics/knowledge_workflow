# Use cases for cross-domain runs

The library is `scripts/use-cases.txt`. Run a use case with `USE_CASE=<name> sbatch scripts/slurm-sweep.sh`.
This memo records why each strong use case was chosen.

Cross-domain integration matters because ontologies in materials science and its neighbouring fields are built separately and stay fragmented. Aligning them is an open problem [1, 2], and one of the documented conflicts is between how materials science and chemistry conceptualize the same things [2].

## Domains outside photovoltaics

The prompts name the paper's field as `{{domain}}` and give examples as `{{ex:<name>}}`, filled in from `src/config.py`.
- **Setting a domain.** A collection's entry in `COLLECTIONS` can set `"domain"`, for example `"polymer coatings"`. Without it, the domain is `photovoltaics`.
- **PV runs.** The prompts render byte-for-byte as before for photovoltaics, so PV runs, cached answers and earlier results are unaffected.
- **Other domains.** The PV example lists (Voc/Jsc/FF, LeTID/PID, EL/PL, damp heat, and so on) are replaced with neutral ones.
- **Mixed use cases.** Each domain is extracted in its own field, and integration names all of them, for example "polymer coatings and photovoltaics".
- **Still PV-flavoured.** The MDS-Onto facet examples ("passivated emitter and rear cell" -> PV-Cell) are unchanged, because they illustrate MDS-Onto's own taxonomy.

## How the use cases were picked

- **Source.** The 2026-10-16 inventory of every collection the Zotero key can read (`outputs/zotero-inventory.json`): 5 libraries, about 2,050 collections.
- **Overlap.** In a strong use case, no two domains share more than 2 PDFs. The pipeline does not remove shared papers, so a paper in two domains would produce trivial cross-domain matches.
- **Sweep size.** `max=` is the largest size every domain can fill with PDFs it does not share with the other domains.
- **Content checked, not names.** I read sample titles from each collection. `Polysilicon` (2189702/5NLP8DAI) holds poly-Si contact papers, not feedstock. `QualificationTests` (CWRU) holds annotation and crowdsourcing papers. `Bondwirecorrosion` is mostly image-processing references. All three were left out.
- **Evidence.** Each strong use case answers a question that published work or official data says matters, and that no single domain answers alone.

## Strong use cases

**pv-cost-chain** (tea, reliability, si-topcon; max 50). The current SWJ triple, kept as the baseline.

**si-cell-transition** (si-perc, si-topcon, si-shj; max 50). ITRPV puts PERC at about 14% of production and falling. TOPCon is dominant and expected to hold about 50% through 2036 [3]. The three ontologies should share device physics while separating the contact and passivation stacks.

**silver-to-copper** (metallization, tea, recycling; max 50). At 20% of 2019 silver supply, silver limits sustainable manufacturing to 377 GW a year for PERC and 227 GW for TOPCon. Zhang et al. set a 2 mg/W target, which needs leaner printing or copper plating [4]. Silver is also up to 47% of a panel's recoverable value, so thrifting cuts recycling revenue [5]. The integration should tie a metallization choice to its cost and to its end-of-life value.

**backsheet-weathering** (coatings [polymer coatings], backsheets, field-studies; max 35). Polyamide backsheets cracked in the field within 4 years, with more than 90% failing within 7. IEC 61215-type tests did not reproduce this; combined-accelerated stress testing did [6]. Coatings research has long linked accelerated lab weathering to outdoor degradation through a shared mechanism [7]. The question is whether integration links coatings-weathering concepts to PV backsheet failures.

**corrosion-across** (coatings, cell-corrosion [PV], xct [X-ray CT of materials]; max 40). Corrosion costs about $2.5 trillion a year, or 3.4% of global GDP, and known prevention practice could save 15–35% of that [8]. In PV, moisture-driven electrochemical failures cost some TOPCon modules 4–65% of their power in damp heat, against 1–2% for PERC [9]. Protective coatings, PV contact corrosion and tomography of corroding metals describe the same mechanisms in three vocabularies.

**am-materials-chain** (diw-am [additive manufacturing], indentation [nanoindentation and thin-film mechanics], xct; max 45). The NIST AM roadmapping workshop asked for predictive capabilities that link material, process and part, and for shared data repositories, as prerequisites for qualifying AM parts [10]. Printing process, measured mechanical properties and CT defect inspection are the three links in that chain. Shared PDFs: 0.

**autonomous-characterization** (xrd [X-ray diffraction and scattering], microstructure-sim, matdatasci; max 50). Over 17 days, the A-Lab made 36 of 57 target compounds. It proposed recipes from 33,343 text-mined syntheses and identified phases from XRD with a neural network trained on simulated patterns [11]. Diffraction, microstructure modelling and data-driven materials science are the literatures that loop draws on.

**chem-materials-bridge** (chem-reactions [chemistry and chemical synthesis], matdatasci [materials data science], onto-chem [chemistry ontologies and KGs]; max 35). The RDA working group on materials-science terminologies names conflicting conceptualizations between materials science and chemistry, and weak interoperability, as core problems [2]. Chemistry already has reaction-network ontologies such as OntoRXN [12]. This use case tests whether integration finds where the two vocabularies meet.

**semantic-web-stack** (kg-rdf [knowledge graphs], reasoning [ontology reasoning], fair-data [FAIR research data]; max 40). The FAIR principles emphasize machine-actionable data, meaning data that machines can find and use without help [13]. Automatic KG construction is surveyed as a multi-stage problem: acquisition, refinement and evolution [14]. For an SWJ audience, the pipeline building an ontology of the semantic-web literature itself is a direct demonstration.

**polymer-durability** (pmma, eva-pe-degr [polymer degradation], rubber-microplastics [rubber and tire materials]; max 30). Tire wear averages about 0.81 kg per person per year and makes up an estimated 5–10% of the plastic entering the oceans [15]. Photo- and thermo-oxidative degradation of PMMA optics and EVA encapsulants is the PV side of the same chemistry [6]. The integration should link degradation mechanisms across applications.

## Possible use cases

`scripts/use-cases.txt` lists 26 with a one-line reason each. They are weaker for one of these reasons:
- **Overlapping papers:** imaging-defects-ml (8 shared PDFs), encapsulant-corrosion (9), measurement-scales (6), am-qualification (5).
- **Small domains:** weather-resilience and geo-hazards stop at n20.
- **Thinner evidence**, or they overlap a strong use case's question.

Some do have support:
- **circular-economy:** recovered panel materials could reach 78 Mt by 2050, worth over USD 15 billion [16]. Recycling costs $15–45 per module versus $1–5 to landfill [17].
- **test-to-field:** IEC TS 63126 adds test levels for modules whose 98th-percentile temperature exceeds 70 °C or 80 °C [18].
- **weather-resilience:** hail is about 2% of solar insurance claims but over 50% of losses [19].
- **field-loss-analytics:** IEA PVPS found performance-loss rates disagree across calculation methods [20]. A study of 1.25 million German systems used panel regression [21].
- **grid-buildings / pv-in-buildings:** buildings use about 37% of US energy once electrical losses are counted [22].

## Before running on HPC

- **Check the CWRU-SDLE PDFs (library 37619).** Most non-PV collections live there, and no run has used it yet. The pipeline downloads PDFs from zotero.org and passes over linked files. Run `python -m src.run extract --collection coatings --limit 5` once to confirm.
- **`max=` counts PDFs listed in Zotero, not downloads.** The sweep stops early if fewer actually download.
- **Mixed or broad collections.** Some non-PV collections are group-member reading lists (`pmma`, `building-energy`) or include a few off-topic references. The citation-ranked top 50 should be mostly on-topic, but check `selected` in each run's `run.json`.

## Sources

1. de Baas et al., "Review and Alignment of Domain-Level Ontologies for Materials Science" (2023): https://sintef.brage.unit.no/sintef-xmlui/handle/11250/3125970
2. RDA, Harmonised terminologies and schemas for FAIR data in materials science WG, case statement (2024): https://rd-alliance.org/app/uploads/2024/05/Harmonised20terminologies20and20schemas20for20FAIR20data20in20materials20science20and20related20domains20WG20-20Case20Statement.pdf
3. ITRPV 17th edition, via TaiyangNews: https://taiyangnews.info/technology/itrpv-sees-pv-shipments-stabilize-at-706-gw-in-2025
4. Zhang, Kim, Wang, Verlinden, Hallam, Energy Environ. Sci. 2021: https://pubs.rsc.org/en/content/articlehtml/2021/ee/d1ee01814k
5. UNSW/Gdansk, Sol. Energy Mater. Sol. Cells, via pv magazine (2026-06-24): https://www.pv-magazine.com/2026/06/24/solar-industrys-shift-from-silver-presents-potential-barrier-for-panel-recycling/
6. Owen-Bellini et al., Scientific Reports 11, 2019 (2021): https://pmc.ncbi.nlm.nih.gov/articles/PMC7820324
7. Gu et al., Service Life Prediction for Polymeric Materials, Springer 2008: https://www.nist.gov/publications/linking-accelerated-laboratory-test-outdoor-performance-results-model-epoxy-coating
8. NACE IMPACT study (2016), via Inspectioneering: https://inspectioneering.com/news/2016-03-08/5202/nace-study-estimates-global-cost-of-corrosion-at-25-trillion-ann
9. UNSW, Sol. Energy Mater. Sol. Cells 2024, via PV Tech: https://pv-tech.org/topcon-modules-significant-degredation-damp-heat-testing-perc
10. NIST, Roadmapping Workshop: Measurement Science for Metal-Based AM, Qualification & Certification breakout (2012): https://www.nist.gov/document/amreportoutqualcertpdf
11. Szymanski et al., "An autonomous laboratory for the accelerated synthesis of inorganic materials", Nature 624 (2023): https://pmc.ncbi.nlm.nih.gov/articles/PMC10700133
12. Garay-Ruiz and Bo, "Chemical reaction network knowledge graphs: the OntoRXN ontology", J. Cheminform. 14 (2022): https://iciq.org/publication/chemical-reaction-network-knowledge-graphs-the-ontorxn-ontology/
13. Wilkinson et al., "The FAIR Guiding Principles for scientific data management and stewardship", Scientific Data (2016): https://researchportal.hw.ac.uk/en/publications/the-fair-guiding-principles-for-scientific-data-management-and-st/
14. Zhong et al., "A Comprehensive Survey on Automatic Knowledge Graph Construction" (2023): https://arxiv.org/abs/2302.05019v1
15. Kole et al., "Wear and Tear of Tyres: A Stealthy Source of Microplastics in the Environment", IJERPH 14 (2017): https://pmc.ncbi.nlm.nih.gov/articles/PMC5664766
16. IRENA/IEA-PVPS, End-of-Life Management: Solar PV Panels (2016): https://www.irena.org/publications/2016/Jun/End-of-life-management-Solar-Photovoltaic-Panels
17. Kwong et al., Waste Management, via pv magazine USA (2026-06-05): https://pv-magazine-usa.com/2026/06/05/solar-panel-recycling-costs-outpace-recovered-material-value-as-2030-waste-surge-approaches/
18. NREL, temperature estimation for IEC TS 63126 compliance: https://nrel.gov/docs/fy23osti/85093.pdf
19. VDE Americas, via pv magazine (2025-04-22): https://www.pv-magazine.com/2025/04/22/new-tool-aims-to-cut-costly-hail-losses-in-utility-scale-solar/
20. IEA PVPS Task 13, Assessment of Performance Loss Rate of PV Power Systems: https://iea-pvps.org/key-topics/assessment-of-performance-loss-rate-of-pv-power-systems/
21. BTU Cottbus, "From shine to decline", Energy Economics, via pv magazine (2026-03-18): https://www.pv-magazine.com/2026/03/18/survey-reveals-pv-systems-in-germany-outperform-lifespan-expectations/
22. U.S. EIA, energy use in buildings (2023 data): https://www.eia.gov/tools/faqs/faq.php?id=86&t=1
