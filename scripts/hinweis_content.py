"""
The paper's content, arranged into the section structure Hinweis prescribes.

Every figure here is the figure the LaTeX paper reports and was measured by a
committed script: 155 textbooks and 43,621 passages from the database, the
77-query ablation from cross_lingual_retrieval.py, the grounding separation
from grounding_estimators.py, the memory figures from serving_footprint.py.

Nothing is restated more loosely than it was measured. Where the venue's
structure asks for something the work does not have -- a sensitivity analysis
over parameter sweeps, for instance -- the section says what was varied rather
than inventing a sweep.
"""

FIGURE_CAPTIONS = {
    "img1.png": ("Figure 1.  The mandatory request path. Medians over 15 warm "
                 "requests, five questions run three times on an 8 GB Apple M1. "
                 "The dashed line is the machine boundary: the corpus and all "
                 "retrieval stay left of it."),
    "img2.png": ("Figure 2.  The five retrieval configurations over 77 queries "
                 "with 95% Wilson score intervals: BM25 0/77, BM25 with rewriting "
                 "42/77, dense 47/77, dense with rewriting 66/77, and the deployed "
                 "pooling of both 67/77."),
    "img3.png": ("Figure 3.  Mean reciprocal rank of the deployed configuration "
                 "for each language, averaged over that language's seven topics. "
                 "Five of the eleven answer all seven at rank one."),
    "img4.png": ("Figure 4.  Four grounding estimators over 16 matched and 240 "
                 "mismatched answer-passage pairs, with one standard deviation. "
                 "Concatenated passages separate the populations by 0.360."),
}

TABLES = {
    "comparison": (
        "Table I.  Comparison with deployed systems. n/d: not disclosed by the "
        "operator. Rows are architectural properties, not performance claims.",
        [["Property", "Khanmigo", "BYJU'S", "Bhashini", "Shiksha Setu"],
         ["NCERT-aligned corpus", "no", "yes", "—", "yes"],
         ["Indian languages", "no", "n/d", "22", "11"],
         ["Corpus held locally", "no", "no", "—", "yes"],
         ["Retrieval runs locally", "no", "no", "—", "yes"],
         ["Generation runs locally", "no", "no", "—", "no"],
         ["Runs without a network", "no", "no", "no", "no"],
         ["Per-answer grounding", "n/d", "n/d", "—", "yes"],
         ["Corpus corruption audit", "n/d", "n/d", "—", "yes"],
         ["Stated memory target", "n/d", "n/d", "n/d", "4 GB"],
         ["Tutoring function", "yes", "yes", "no", "yes"]]),
    "corpus": (
        "Table II.  The corpus the retrieval results are measured against.",
        [["Property", "Value"],
         ["Textbooks ingested", "155"],
         ["Chapters", "1,557"],
         ["Indexed passages", "43,621"],
         ["Passages with an embedding", "43,621 of 43,621"],
         ["Classes represented", "1 to 12"],
         ["Books at class 1 / class 12", "3 / 34"],
         ["Catalog size", "559 textbooks"],
         ["Taught subset targeted", "263 books"]]),
    "ablation": (
        "Table III.  Retrieval over 77 queries: seven topics in each of eleven "
        "Indian languages, against an English-medium corpus. A query counts as "
        "correct only when the top passage is on topic.",
        [["Configuration", "Correct at rank 1", "Percent", "95% Wilson interval"],
         ["Lexical baseline (BM25)", "0 of 77", "0", "[0.000, 0.048]"],
         ["BM25 with rewriting", "42 of 77", "55", "[0.435, 0.652]"],
         ["Dense embedding", "47 of 77", "61", "[0.499, 0.712]"],
         ["Dense with rewriting", "66 of 77", "86", "[0.762, 0.918]"],
         ["Pooled (deployed)", "67 of 77", "87", "[0.777, 0.928]"]]),
    "topic": (
        "Table IV.  The same 77 queries by topic, showing that how a term is "
        "built matters more than which language asks for it.",
        [["Topic", "Dense", "Rewriting", "Pooled"],
         ["Digestion (ordinary vocabulary)", "11/11", "11/11", "11/11"],
         ["Acids and bases", "5/11", "11/11", "11/11"],
         ["Electric current", "7/11", "11/11", "11/11"],
         ["Pythagoras (transliterated name)", "5/11", "11/11", "11/11"],
         ["The eye", "9/11", "5/11", "7/11"],
         ["Water cycle", "8/11", "7/11", "7/11"],
         ["Photosynthesis (native compound)", "2/11", "10/11", "9/11"]]),
    "precision": (
        "Table V.  Half precision against full precision for the embedding model.",
        [["Metric", "float32", "float16"],
         ["Weight memory", "2,166 MB", "1,083 MB"],
         ["Encode four queries", "2,255 ms", "1,197 ms"],
         ["Model load time", "8.5 s", "8.1 s"],
         ["Cosine fidelity, mean", "—", "0.999998"],
         ["Cosine fidelity, minimum", "—", "0.999964"]]),
}

SECTIONS = [
 ("Introduction", [
   ("p", "India has 1.4 billion people and 22 scheduled languages written in more "
         "than a dozen scripts. The National Council of Educational Research and "
         "Training (NCERT) publishes the curriculum that governs instruction for "
         "the 24.7 crore children enrolled in school, yet its textbooks exist only "
         "in English, Hindi and Urdu. A Tamil-speaking student in rural Tamil Nadu, "
         "a Marathi-speaking student in Maharashtra and a Bengali-speaking student "
         "in West Bengal all study the same curriculum, but none of them can read "
         "it in their mother tongue unless a human teacher translates it in real "
         "time."),
   ("p", "Artificial intelligence can bridge that gap, and the dominant approach "
         "is a cloud-hosted large language model answering from its own training. "
         "That approach introduces three structural failures for Indian education. "
         "It requires continuous connectivity, which rural schools do not have. It "
         "operates primarily in English, which most of its users do not read. And "
         "it answers from whatever the model absorbed during training rather than "
         "from the curriculum the student is examined on."),
   ("p", "This paper presents Shiksha Setu, a tutoring platform in which the "
         "corpus, the embeddings over it and the whole of retrieval run on the "
         "user's own machine, and only generation is a hosted call. The paper is "
         "explicit about which half is which and does not claim to be offline. "
         "Every number reported was produced by a script committed with the "
         "system, run against a recorded corpus state, on hardware named in the "
         "text."),
 ]),
 ("Related Work or Literature Studies", [
   ("p", "Lewis et al. introduced retrieval-augmented generation for "
         "knowledge-intensive tasks, establishing that grounding a generator in "
         "retrieved documents reduces fabrication. Their evaluation is in English "
         "over Wikipedia; the question this work asks is what happens when the "
         "query and the corpus are in different scripts, which their setting never "
         "raises."),
   ("p", "Karpukhin et al. demonstrated dense passage retrieval outperforming "
         "BM25 for open-domain question answering. Their comparison is within one "
         "language. This work finds the gap is not a matter of degree across "
         "scripts: BM25 returns nothing at all, because a Devanagari query shares "
         "no tokens with an English index."),
   ("p", "Ma et al. showed that rewriting a query before embedding improves "
         "retrieval quality, in English. This work measures the same technique "
         "where the rewrite also crosses a script boundary, and finds it is the "
         "single largest effect in the pipeline, worth nineteen queries out of 77."),
   ("p", "Chen et al. released BGE-M3, a multilingual embedding model covering "
         "over 100 languages in a shared 1024-dimensional space. Its cross-lingual "
         "property is what allows a Hindi question to retrieve an English passage "
         "without explicit translation, and it is the model this system embeds "
         "with. Gala et al. developed IndicTrans2 covering all 22 scheduled Indian "
         "languages, and Khanuja et al. trained MuRIL on transliterated Indic text. "
         "Both are translation and representation backbones rather than retrieval "
         "systems, and neither reports what a curriculum corpus does to retrieval "
         "accuracy."),
   ("p", "Nogueira and Cho established cross-encoder re-ranking as the standard "
         "answer to imperfect ranking. This work differs by measuring that answer "
         "rather than assuming it, and reports that on this corpus the "
         "cross-encoder lowers accuracy from 67 to 65 of 77 while requiring memory "
         "the target device does not have."),
   ("p", "Malkov and Yashunin proposed the HNSW graph structure used here through "
         "the pgvector extension for PostgreSQL, and Micikevicius et al. "
         "established the safety of half-precision arithmetic, which is the basis "
         "for the memory result in Section XI."),
 ]),
 ("Motivation", [
   ("p", "The motivation is a gap that is visible in any Indian classroom outside "
         "the English-medium stream. The curriculum is national and uniform; the "
         "language of its textbooks is not. A student who cannot read the textbook "
         "is dependent on a teacher's translation for every question asked outside "
         "class hours, and there is no such teacher at nine at night."),
   ("p", "The technical motivation came from the related work. Cross-lingual "
         "embeddings were reported to place semantically equivalent text from "
         "different languages near each other, and retrieval-augmented generation "
         "was reported to reduce fabrication. Both were established in settings "
         "where the query and the corpus share a language. Whether they hold when "
         "a Tamil question must reach an English passage was not something the "
         "literature answered, and it is the difference between a system that "
         "works for Indian students and one that does not."),
 ]),
 ("Problem Domain", [
   ("p", "The domain is cross-lingual information retrieval applied to a fixed, "
         "curriculum-aligned corpus, under a device memory constraint."),
   ("p", "Three bodies of technique meet here. Dense retrieval represents text as "
         "vectors and searches by geometric proximity rather than word overlap. "
         "Cross-lingual representation learning places different languages in one "
         "vector space so that proximity survives a change of script. Approximate "
         "nearest-neighbour search, here the HNSW graph, makes that search "
         "tractable over tens of thousands of passages on ordinary hardware."),
   ("p", "The constraint that shapes the domain is the device. Indian schools run "
         "predominantly Windows desktops, and the memory budget this work targets "
         "is 4 GB. That budget decides which models can be resident, which is why "
         "precision and component choice are treated as measurements in this paper "
         "rather than as configuration."),
 ]),
 ("Problem Definition", [
   ("p", "Given a question asked in any of eleven Indian languages, and a corpus "
         "of NCERT textbooks that exists almost entirely in English, retrieve the "
         "passage that answers the question and do so on a machine with 4 GB of "
         "memory and no guarantee of connectivity for the retrieval stage."),
   ("p", "The difficulty is that the two halves of the problem pull against each "
         "other. Crossing the script boundary reliably suggests a large "
         "multilingual model; the memory budget forbids one. Any solution has to "
         "establish which components earn their memory, which requires measuring "
         "each of them rather than adopting the configuration the literature "
         "recommends."),
 ]),
 ("Statement", [
   ("p", "Retrieve curriculum-aligned passages from an English corpus for "
         "questions asked in eleven Indian languages, within a 4 GB memory budget, "
         "and establish by measurement which components of the retrieval pipeline "
         "are responsible for the accuracy obtained."),
 ]),
 ("Innovative Content", [
   ("p", "Against Karpukhin et al., who report dense retrieval outperforming BM25 "
         "within a language, this work reports a stronger and different result "
         "across scripts. The lexical baseline retrieves correctly for 0 of 77 "
         "queries, with a 95% Wilson upper bound of 0.048. It is not weaker at the "
         "task; it is structurally incapable of it, because the inverted index has "
         "no token in common with the query. That is the argument for carrying a "
         "568 M-parameter embedding model on a small machine, and it is an "
         "argument from measurement rather than from preference."),
   ("p", "Against Ma et al., who report query rewriting as an improvement, this "
         "work locates where the improvement comes from. Direct embedding "
         "retrieves correctly for 47 of 77 and rewriting into English first for "
         "66. The gain of nineteen queries is concentrated on terms the embedding "
         "cannot decompose: on photosynthesis, whose name in most of these "
         "languages is a compound of morphemes meaning light and joining, direct "
         "embedding attends to the constituents, retrieves optics, and scores 2 of "
         "11, while the rewrite recovers 10."),
   ("p", "Against Nogueira and Cho, who establish cross-encoder re-ranking as "
         "standard practice, this work reports a negative result obtained by "
         "running it. Over the same 77 queries and the same candidate lists, "
         "BGE-Reranker-v2-M3 scores 65 of 77 against 67 without it, promoting "
         "seven queries and demoting nine. Held resident beside the embedder the "
         "pair requested 8.6 GB on an 8 GB machine and drove swap to 12.5 GB. The "
         "component is excluded on that evidence."),
   ("p", "A fourth contribution has no counterpart in the retrieval literature "
         "because it belongs to the corpus rather than the method. NCERT's older "
         "Hindi textbooks are typeset in a legacy font that maps Devanagari glyphs "
         "onto ASCII codepoints with no ToUnicode table, so every PDF text "
         "extractor returns Latin gibberish that looks like successfully extracted "
         "text. Two-thirds of the Hindi curriculum is affected. The pipeline "
         "detects and rejects it rather than indexing it."),
 ]),
 ("Problem Formulation or Representation or Design", [
   ("p", "The system is formulated as an eight-stage pipeline, six stages of "
         "which are mandatory for every question. Figure 1 gives the path with "
         "measured medians and marks the machine boundary."),
   ("fig", "img1.png"),
   ("p", "Formally, a question q in language L is first mapped by a rewriting "
         "function r to an English search string r(q). Both q and r(q) are "
         "embedded by the encoder E into the shared space, giving vectors E(q) and "
         "E(r(q)) in R^1024. Each vector retrieves its k nearest passages from the "
         "index by cosine distance, and the two result sets are pooled by taking "
         "the higher similarity for any passage appearing in both. The generator "
         "then produces an answer a from the pooled passages P, and a grounding "
         "function g(a, P), also a cosine similarity, decides whether the answer "
         "was written from those passages or drifted away from them."),
   ("sub", "Why the pipeline has this shape", "A"),
   ("p", "Each stage exists because a measurement required it. Rewriting exists "
         "because romanised Hindi retrieves class 1 picture books for a class 10 "
         "chemistry question: the embedding attends to surface form. Pooling "
         "exists because the two arms fail on different inputs. The grounding "
         "check exists because a fluent answer that has drifted from its source is "
         "indistinguishable from a correct one without a numerical test."),
   ("sub", "The persistence layer", "B"),
   ("p", "Passages and their embeddings are stored in PostgreSQL 17 with the "
         "pgvector extension, indexed with HNSW using cosine distance, m = 16 and "
         "ef_construction = 64. An earlier migration stored embeddings as a "
         "double precision array where the vector type was required, which made "
         "index creation impossible and left every search falling back to a "
         "sequential scan over all 43,621 rows at 1,389 ms. With the index used, "
         "the same search takes 62 ms and returns the identical top passage."),
 ]),
 ("Solution Methodologies or Problem Solving", [
   ("sub", "Corpus construction", "A"),
   ("p", "NCERT encodes every textbook with a five-character code from which the "
         "subject letters are not algorithmically derivable, so the catalog is "
         "scraped from the publisher's textbook picker and cached. The complete "
         "catalog contains 559 textbooks: 209 in English, 191 in Hindi and 159 in "
         "Urdu. The platform teaches from a deliberate subset of 263 books."),
   ("p", "Each book passes through five stages: archive download, per-chapter PDF "
         "extraction, text cleanup, semantic chunking at 1,200 characters with "
         "200 characters of overlap and a preference for paragraph boundaries, "
         "embedding at half precision, and storage. Each book commits as one "
         "database transaction so that a failure leaves no partial book behind."),
   ("p", "A book that cannot be ingested writes a marker naming the reason, so "
         "the shortfall can be audited rather than assumed. That mechanism found "
         "two books whose loss was not the source material's: one run exhausted "
         "the disk, and one chunk embedded to a non-finite vector, which the "
         "single-transaction commit turned into a whole rolled-back book."),
   ("sub", "Detecting a corpus defect that reports success", "B"),
   ("p", "Two-thirds of the Hindi curriculum is unreadable by every PDF text "
         "extractor tested. The older Hindi textbooks are typeset in "
         "Walkman-Chanakya 905, a legacy font mapping Devanagari glyphs onto ASCII "
         "codepoints with no ToUnicode table, so extraction returns raw byte "
         "values rather than failing. Of 41 Devanagari-only books analysed, 27 are "
         "affected and yield 0.0% Devanagari characters, while the 14 typeset in "
         "Unicode fonts yield 97.9 to 100%. The detector measures the proportion "
         "of Devanagari codepoints and rejects a book that reports text but no "
         "script."),
   ("sub", "Cross-lingual retrieval", "C"),
   ("p", "A question is rewritten into an English search query by the language "
         "model before embedding, and both the original and the rewritten form are "
         "embedded and searched. The two result sets are pooled by best score. "
         "Rewriting runs for every question rather than only ones that look "
         "non-English, because deciding what looks romanised is guesswork and the "
         "call is under a second."),
   ("sub", "Grounding", "D"),
   ("p", "After generation, the answer and the concatenated retrieved passages "
         "are embedded and compared by cosine similarity. The threshold was "
         "originally set at 0.55 from four hand-verified examples. Calibrating it "
         "on 256 constructed pairs moved it to 0.715."),
 ]),
 ("Results and Sensitivity Analysis", [
   ("p", "Retrieval was evaluated over 77 queries: seven topics in each of the "
         "eleven supported Indian languages, against the English-medium portion of "
         "the corpus. Holding the topic constant across languages makes language "
         "the only variable that moves within a topic. The topics span mathematics, "
         "physics, chemistry, biology and geography and were fixed before any was "
         "run, each required to have enough English material to answer it. A query "
         "counts as correct only when the top passage is on topic."),
   ("tab", "ablation"),
   ("fig", "img2.png"),
   ("p", "The lexical baseline retrieves nothing at all for any of the 77 "
         "queries. Given an English query from the rewrite it becomes viable at "
         "once, at 55%, which locates the difficulty precisely: the barrier is the "
         "script, not the vocabulary. Rewriting before embedding gains nineteen "
         "queries over embedding directly, which is the largest effect measured in "
         "this work. Pooling the two scores one query above rewriting alone, with "
         "intervals that almost coincide, and is reported as what the system "
         "deploys rather than as a configuration shown to be better."),
   ("fig", "img3.png"),
   ("sub", "What was varied, and what the results are sensitive to", "A"),
   ("p", "Three variables were moved deliberately. Language was varied across "
         "eleven languages within each topic: the spread of mean reciprocal rank "
         "is 0.786 to 1.000, and five of the eleven answer all seven topics at "
         "rank one. Topic was varied across seven: the spread there is far wider, "
         "from 2 of 11 to 11 of 11 for direct embedding. Pipeline configuration "
         "was varied across the five arms of Table III."),
   ("p", "The result is therefore far more sensitive to how a term is "
         "morphologically built than to which language asks for it, which is the "
         "opposite of what a reader would expect from a multilingual evaluation."),
   ("tab", "topic"),
   ("p", "One source of variance is not controlled. The rewrite is a "
         "language-model call and is not deterministic at temperature zero. "
         "Repeated runs at 22 queries returned 16 and 17, and between that run and "
         "the 77-query run reported here the Tamil photosynthesis query changed "
         "from failing to succeeding. No figure here is given more precision than "
         "its interval carries."),
   ("sub", "Memory", "B"),
   ("p", "The embedding model was evaluated at both full and half precision."),
   ("tab", "precision"),
   ("p", "Half precision halves the weights and encodes about 1.88 times faster "
         "at a mean cosine fidelity of 0.999998 and a worst case of 0.999964 over "
         "400 corpus passages. Whether that matters is a question about rankings, "
         "so it was tested as one: over eight queries the top twelve passages are "
         "the same twelve under both precisions, in the same order for six of the "
         "eight, with the first difference at rank nine. The peak resident set "
         "through the serving pipeline is 2,094 MB, measured at the kernel rather "
         "than summed from component sizes; an earlier arithmetic estimate of "
         "1,600 MB understated it by 31%."),
 ]),
 ("Data Model", [
   ("p", "All retrieval results are measured against one recorded corpus state, "
         "given in Table II, so that the numbers can be reproduced rather than "
         "taken on trust."),
   ("tab", "corpus"),
   ("p", "The grounding results precede the recovery of two books and are "
         "reported against the 153-textbook state that preceded this one, with "
         "1,542 chapters and 42,995 passages. Reporting a single state for both "
         "would have been tidier and false."),
   ("p", "The evaluation data model has three inputs and one output per trial. "
         "The inputs are the language, the topic and the pipeline configuration; "
         "the output is the rank of the first on-topic passage, from which both "
         "the rank-1 verdict and the reciprocal rank are derived. Seventy-seven "
         "queries across five configurations give 385 trials. The grounding "
         "evaluation uses a different model: 16 questions produce 16 matched "
         "answer-passage pairs and 240 mismatched ones, by pairing each answer "
         "with the passages retrieved for a different question."),
   ("p", "The corpus itself is not distributed with the system. NCERT publishes "
         "these textbooks for free public download; the pipeline fetches them "
         "directly and stores extracted text for retrieval, and the catalog rather "
         "than the books is what the repository carries."),
 ]),
 ("Comparison of Results", [
   ("p", "Two comparisons are reported. The first is against the systems an "
         "Indian student is most likely to encounter, and is confined to "
         "architectural properties. Every cell is a structural fact, a published "
         "vendor figure, or n/d where none exists, and no row sets a measurement "
         "of ours against a number that could not be obtained, because commercial "
         "products publish neither latency distributions nor retrieval quality nor "
         "memory footprints."),
   ("tab", "comparison"),
   ("p", "Three rows are stated against our own interest: generation is not "
         "local, the system needs a network, and BYJU'S covers the curriculum at a "
         "scale this work does not approach."),
   ("p", "The second comparison is internal and is the one that carries the "
         "result, because it holds everything constant except the component under "
         "test. It is given across the five configurations of Table III and the "
         "seven topics of Table IV, and it is not based on a single set of inputs: "
         "77 queries in eleven languages across seven subjects, with each "
         "configuration run over all of them."),
   ("p", "A third comparison was run and produced a negative result. Adding a "
         "cross-encoder re-ranker to the deployed configuration, over the same "
         "queries and the same candidate lists, scores 65 of 77 against 67 without "
         "it, promoting seven queries to rank one and demoting nine."),
 ]),
 ("Justification of the Results", [
   ("p", "The lexical result is justified by the mechanism rather than by the "
         "count. A Devanagari, Tamil or Perso-Arabic query tokenises to symbols "
         "that do not occur in an English inverted index, so there is nothing for "
         "the ranking function to score. That is why the interval is [0.000, "
         "0.048] and why supplying an English rewrite lifts the same method to "
         "55% immediately. Karpukhin et al. report dense retrieval as better than "
         "BM25 within a language; across scripts the relationship is not better "
         "but categorical, and the mechanism explains why."),
   ("p", "The rewriting result is justified by where the gain lands. If rewriting "
         "helped uniformly it would suggest a general quality effect. It does not: "
         "the gain is concentrated on compound terms, 2 of 11 to 10 of 11 on "
         "photosynthesis, while on the eye, whose name is ordinary vocabulary, "
         "rewriting is worse than direct embedding at 5 of 11 against 9. That "
         "pattern is consistent with the stated mechanism, that the rewrite "
         "normalises a compound the embedder decomposes into the wrong "
         "constituents, and inconsistent with a general improvement."),
   ("p", "The grounding separation of 0.360 is justified by reproducing it "
         "outside the embedding space that produced it. BGE-M3 both retrieved "
         "these passages and scored them, so the separation could be a property of "
         "one model's geometry. Repeating the measurement with character n-gram "
         "TF-IDF and with a second encoder family reproduces the separation, so it "
         "is a property of the answers."),
   ("fig", "img4.png"),
   ("p", "The memory result is justified by the method of measurement. Component "
         "sizes summed arithmetically gave 1,600 MB; the kernel reports a peak "
         "resident set of 2,094 MB for the same pipeline, because loading a model "
         "costs more than the weights it ends up holding. The reported figure is "
         "the measured one."),
   ("p", "Two limitations bound all of this. The grounding negatives are "
         "constructed by mismatching answers to other questions' passages rather "
         "than collected from observed hallucinations, so they capture topical "
         "drift and not fluent fabrication within the right topic. And there is no "
         "human evaluation: no teacher or student has assessed whether a retrieved "
         "passage actually helps a learner, which is the question a tutoring "
         "system exists to answer."),
 ]),
 ("Conclusion", [
   ("p", "This paper presented Shiksha Setu, a tutoring platform whose corpus, "
         "embeddings and retrieval run on the user's own machine and whose "
         "generation is a hosted call, with the boundary stated rather than "
         "blurred. The evaluation rests on 155 ingested textbooks and 43,621 "
         "indexed passages spanning all twelve classes."),
   ("p", "Four results are reported. A lexical baseline retrieves correctly for "
         "none of 77 cross-lingual queries, which is a structural failure rather "
         "than a weak score. Rewriting a question into English before embedding it "
         "gains nineteen queries over embedding it directly, 66 of 77 against 47, "
         "and that gain is concentrated on morphologically compound terms. "
         "Half-precision inference halves the embedding footprint to 1,083 MB at a "
         "mean cosine fidelity of 0.999998, bringing the serving pipeline inside a "
         "4 GB budget verified by kernel-level measurement. And ingestion detects "
         "a legacy-font defect that renders 66% of Hindi textbooks as Latin "
         "gibberish while reporting successful extraction."),
   ("p", "A cross-encoder re-ranker, the standard remedy for imperfect ranking, "
         "was measured rather than assumed and is excluded on the result: it "
         "lowers accuracy from 67 to 65 of 77 and does not fit beside the embedder "
         "on the target device."),
 ]),
 ("Future Work", [
   ("p", "The most consequential gap is the absence of human evaluation. A "
         "pilot with practising teachers, measuring whether a retrieved passage "
         "helps a learner rather than whether it is on topic, would test the claim "
         "this system actually makes."),
   ("p", "Three narrower directions follow from the results. The grounding "
         "negatives should be drawn from observed hallucinations rather than "
         "constructed by mismatching, so the metric is calibrated against the "
         "failure it is meant to catch. The query set should grow beyond 77, which "
         "needs native speakers of eleven languages rather than compute. And the "
         "single query that fails in every configuration, Urdu photosynthesis, "
         "points at a class of Perso-Arabic technical vocabulary that shares no "
         "root with either English or the Sanskrit-derived compounds the other ten "
         "languages use; whether a targeted lexicon closes that gap is an open "
         "question."),
 ]),
 ("References", []),
]

REFERENCES = [
 "P. Lewis et al., “Retrieval-augmented generation for knowledge-intensive NLP tasks,” in Proc. NeurIPS, 2020.",
 "V. Karpukhin et al., “Dense passage retrieval for open-domain question answering,” in Proc. EMNLP, 2020, pp. 6769–6781.",
 "X. Ma, Y. Gong, P. He, H. Zhao and N. Duan, “Query rewriting for retrieval-augmented large language models,” in Proc. EMNLP, 2023.",
 "R. Nogueira and K. Cho, “Passage re-ranking with BERT,” arXiv:1901.04085, 2019.",
 "J. Chen, S. Xiao, P. Zhang, K. Luo, D. Lian and Z. Liu, “BGE M3-Embedding: multi-lingual, multi-granularity text embeddings via self-knowledge distillation,” arXiv:2402.03216, 2024.",
 "A. Gala et al., “IndicTrans2: accessible machine translation for all 22 scheduled Indian languages,” Trans. Mach. Learn. Res., 2023.",
 "S. Khanuja et al., “MuRIL: multilingual representations for Indian languages,” 2021.",
 "D. Kakwani et al., “IndicNLPSuite: corpora, benchmarks and pre-trained models for Indian languages,” in Findings of EMNLP, 2020.",
 "Z. Xu et al., “Multilingual retrieval-augmented generation for knowledge-intensive task,” arXiv:2504.03616, 2025.",
 "Y. Chen et al., “Language drift in multilingual RAG: characterization and decoding-time mitigation,” arXiv:2511.09984, 2025.",
 "Y. A. Malkov and D. A. Yashunin, “Efficient and robust approximate nearest neighbor search using HNSW graphs,” IEEE Trans. Pattern Anal. Mach. Intell., vol. 42, no. 4, pp. 824–836, 2020.",
 "N. Reimers and I. Gurevych, “Sentence-BERT: sentence embeddings using Siamese BERT-networks,” in Proc. EMNLP, 2019, pp. 3982–3992.",
 "P. Micikevicius et al., “Mixed precision training,” in Proc. ICLR, 2018.",
 "S. Robertson and H. Zaragoza, “The probabilistic relevance framework: BM25 and beyond,” Found. Trends Inf. Retr., vol. 3, no. 4, pp. 333–389, 2009.",
 "E. B. Wilson, “Probable inference, the law of succession, and statistical inference,” J. Amer. Statist. Assoc., vol. 22, no. 158, pp. 209–212, 1927.",
 "S. Es, J. James, L. Espinosa-Anke and S. Schockaert, “RAGAs: automated evaluation of retrieval augmented generation,” in Proc. EACL: System Demonstrations, 2024, pp. 150–158.",
 "Y. Gao et al., “Retrieval-augmented generation for large language models: a survey,” arXiv:2312.10997, 2023.",
 "Z. Ji et al., “Survey of hallucination in natural language generation,” ACM Comput. Surv., vol. 55, no. 12, art. 248, 2023.",
 "Khan Academy, “Khanmigo: an AI tutor for learners and assistant for teachers,” 2023. [Online]. Available: khanmigo.ai",
 "Ministry of Electronics and Information Technology, Government of India, “BHASHINI: National Language Translation Mission,” 2022. [Online]. Available: bhashini.gov.in",
 "Department of School Education and Literacy, “UDISE+ 2024–25 report,” Ministry of Education, India, 2025.",
 "Registrar General of India, “Census of India 2011, Table C-17: bilingualism and trilingualism,” 2011.",
]
