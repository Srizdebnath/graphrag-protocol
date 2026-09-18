#!/usr/bin/env python3
"""Generate benchmark queries from papers.jsonl.

Creates 50 queries across 4 categories + reference answers, all grounded in the actual paper data.

Usage:
    .venv/bin/python hackathon/scripts/build_queries.py
"""

import json
from pathlib import Path

DATA_DIR = Path("hackathon/data")
PAPERS_FILE = DATA_DIR / "papers" / "papers.jsonl"
QUERIES_DIR = DATA_DIR / "queries"


def load_papers():
    """Load all papers from JSONL."""
    papers = []
    with open(PAPERS_FILE) as f:
        for line in f:
            papers.append(json.loads(line))
    return {p["id"]: p for p in papers}


def validate_paper_ids(paper_ids, paper_db):
    """Validate that all paper IDs exist in the database."""
    missing = [pid for pid in paper_ids if pid not in paper_db]
    if missing:
        print(f"  WARNING: {len(missing)} missing paper IDs: {missing[:5]}...")
        return False
    return True


def build_single_hop_queries(paper_db):
    """Build 15 single-hop queries grounded in real papers."""
    queries = [
        {
            "id": "q001",
            "category": "single_hop",
            "query": "What is the title of the paper authored by Linzhan Mou, Jiahui Lei, and Zhiyang Dou?",
            "papers": ["2609.05415"],
        },
        {
            "id": "q002",
            "category": "single_hop",
            "query": "What problem does the paper 'WearableQA: A Benchmark for Health Reasoning over Real-World Wearable Data' address?",
            "papers": ["2609.05405"],
        },
        {
            "id": "q003",
            "category": "single_hop",
            "query": "What are the main categories of the paper 'Diffusion TV: Experiencing Diffusion Models through Tangible, Embodied Interaction'?",
            "papers": ["2609.05404"],
        },
        {
            "id": "q004",
            "category": "single_hop",
            "query": "In the paper 'RegionFed: Federated Learning for Personalized Query Understanding in Heterogeneous Retail Environments', what type of learning is proposed?",
            "papers": ["2609.05403"],
        },
        {
            "id": "q005",
            "category": "single_hop",
            "query": "What is the ROBORMBENCH paper about regarding vision language reward models?",
            "papers": ["2609.05401"],
        },
        {
            "id": "q006",
            "category": "single_hop",
            "query": "What technique does the paper 'Necessary or Sufficient? Evaluating LLM Explanations With Behavioural Evidence' propose for evaluating LLM explanations?",
            "papers": ["2609.05385"],
        },
        {
            "id": "q007",
            "category": "single_hop",
            "query": "What task does the paper 'Influence Score and Transformers interpretability: Measure of the Effective Impact of Attention Heads' address?",
            "papers": ["2609.05074"],
        },
        {
            "id": "q008",
            "category": "single_hop",
            "query": "What is the main contribution of the paper 'Pattern Over-Generalization of Knowledge Graph Embedding'?",
            "papers": ["2609.03487"],
        },
        {
            "id": "q009",
            "category": "single_hop",
            "query": "What problem does 'PEARL: Path-Entity Aligned Relational Learning with Contextual Subgraphs for Inductive Knowledge Graph Completion' solve?",
            "papers": ["2609.02216"],
        },
        {
            "id": "q010",
            "category": "single_hop",
            "query": "What is the focus of the paper 'SMILE: Self-Explainable Multimodal Information Bottleneck for Medical Diagnosis'?",
            "papers": ["2609.05174"],
        },
        {
            "id": "q011",
            "category": "single_hop",
            "query": "What approach does 'Online Change-point Detection for Cooperative Multi-Agent Reinforcement Learning' propose?",
            "papers": ["2609.05298"],
        },
        {
            "id": "q012",
            "category": "single_hop",
            "query": "What is the title and main topic of the paper with ID 2609.04772?",
            "papers": ["2609.04772"],
        },
        {
            "id": "q013",
            "category": "single_hop",
            "query": "What benchmark does 'MM-IFEval-Pro: A Multilingual and Attack-Resistant Benchmark for Instruction-Following Evaluation' evaluate?",
            "papers": ["2609.04859"],
        },
        {
            "id": "q014",
            "category": "single_hop",
            "query": "What problem does 'HyGRAIL: Cost-Aware and Evidence-Grounded Scientific Hypothesis Discovery over Knowledge Graphs' address?",
            "papers": ["2609.02056"],
        },
        {
            "id": "q015",
            "category": "single_hop",
            "query": "What is the main contribution of 'Athena: Vulnerability-Affected Library Identification via Knowledge Graph Completion'?",
            "papers": ["2609.01187"],
        },
    ]
    return queries


def build_multi_hop_queries(paper_db):
    """Build 15 multi-hop queries linking 2-3 real papers via shared concepts."""
    queries = [
        {
            "id": "q016",
            "category": "multi_hop",
            "query": "How do papers on knowledge graph embedding and inductive knowledge graph completion differ in their approaches to link prediction?",
            "papers": ["2609.03487", "2609.02216"],
        },
        {
            "id": "q017",
            "category": "multi_hop",
            "query": "What common challenges do papers on multimodal emotion recognition and multimodal information bottleneck for medical diagnosis share regarding feature encoding?",
            "papers": ["2609.04690", "2609.05174"],
        },
        {
            "id": "q018",
            "category": "multi_hop",
            "query": "How do the approaches to evaluating LLM explanations and measuring attention head impact in transformers relate to each other?",
            "papers": ["2609.05385", "2609.05074"],
        },
        {
            "id": "q019",
            "category": "multi_hop",
            "query": "What connections exist between the work on diffusion language models for mobile edge AI and distilled continuous diffusion language models for code generation?",
            "papers": ["2609.04778", "2609.04531"],
        },
        {
            "id": "q020",
            "category": "multi_hop",
            "query": "How do the papers on knowledge graph embedding pattern over-generalization and uncertain knowledge graph initialization address different aspects of knowledge graph quality?",
            "papers": ["2609.03487", "2609.02519"],
        },
        {
            "id": "q021",
            "category": "multi_hop",
            "query": "What methodological similarities exist between the approaches for counterfactual explanations of graph neural networks and GNN-based watermark frameworks?",
            "papers": ["2609.05113", "2609.04772"],
        },
        {
            "id": "q022",
            "category": "multi_hop",
            "query": "How do the papers on on-policy distillation for language models and recursive improvement via self-extrapolating policy distillation both address post-training efficiency?",
            "papers": ["2609.05295", "2609.05198"],
        },
        {
            "id": "q023",
            "category": "multi_hop",
            "query": "What common themes connect the work on retrieval-augmented generation context compression and the retrieval-augmented GenAI assistant for quantum workflows?",
            "papers": ["2609.05152", "2609.05039"],
        },
        {
            "id": "q024",
            "category": "multi_hop",
            "query": "How do the approaches to knowledge graph completion for vulnerability-affected library identification and scientific hypothesis discovery both leverage knowledge graphs?",
            "papers": ["2609.01187", "2609.02056"],
        },
        {
            "id": "q025",
            "category": "multi_hop",
            "query": "What relationships exist between the papers on transformer compression for plant disease detection and the paper on influence scores for transformer interpretability?",
            "papers": ["2609.05334", "2609.05074"],
        },
        {
            "id": "q026",
            "category": "multi_hop",
            "query": "How do the papers on spatiotemporal graph neural networks for air quality and mesh-based physics learning with hierarchical graph networks both apply graph neural networks?",
            "papers": ["2609.04693", "2608.13827"],
        },
        {
            "id": "q027",
            "category": "multi_hop",
            "query": "What connections exist between the work on multimodal chain-of-thought reasoning and multimodal time series question answering?",
            "papers": ["2609.04947", "2609.04842"],
        },
        {
            "id": "q028",
            "category": "multi_hop",
            "query": "How do the papers on reinforcement learning for solar PV policy design and cooperative multi-agent reinforcement learning address different aspects of RL challenges?",
            "papers": ["2609.04880", "2609.05298"],
        },
        {
            "id": "q029",
            "category": "multi_hop",
            "query": "What common approaches do the papers on LLM-driven quantum circuit synthesis and LLM decompilers share regarding LLM-based problem solving?",
            "papers": ["2609.05327", "2609.05370"],
        },
        {
            "id": "q030",
            "category": "multi_hop",
            "query": "How do the papers on neural-symbolic spatio-temporal GraphRAG and the Qlippy retrieval-augmented assistant both address knowledge retrieval challenges?",
            "papers": ["2609.05139", "2609.05039"],
        },
    ]
    return queries


def build_global_queries(paper_db):
    """Build 10 global synthesis queries grounded in corpus-wide patterns."""
    queries = [
        {
            "id": "q031",
            "category": "global",
            "query": "What are the dominant research themes across the 8000 papers in this corpus?",
            "papers": [],
        },
        {
            "id": "q032",
            "category": "global",
            "query": "Which arXiv categories appear most frequently in the dataset and what do they reveal about the research landscape?",
            "papers": [],
        },
        {
            "id": "q033",
            "category": "global",
            "query": "What are the most common methods or techniques mentioned across the paper titles in this collection?",
            "papers": [],
        },
        {
            "id": "q034",
            "category": "global",
            "query": "How is research on large language models (LLMs) represented across different arXiv categories in this dataset?",
            "papers": [],
        },
        {
            "id": "q035",
            "category": "global",
            "query": "What role do benchmarking and evaluation play across the papers in this corpus?",
            "papers": [],
        },
        {
            "id": "q036",
            "category": "global",
            "query": "What are the main application domains targeted by the AI research papers in this dataset?",
            "papers": [],
        },
        {
            "id": "q037",
            "category": "global",
            "query": "How prevalent is graph-based learning across the different research areas represented in the corpus?",
            "papers": [],
        },
        {
            "id": "q038",
            "category": "global",
            "query": "What trends in multimodal AI research can be observed from the paper titles and categories in this dataset?",
            "papers": [],
        },
        {
            "id": "q039",
            "category": "global",
            "query": "How is research on agent-based systems distributed across the AI subfields in this collection?",
            "papers": [],
        },
        {
            "id": "q040",
            "category": "global",
            "query": "What are the most active intersection areas between different arXiv categories in this corpus?",
            "papers": [],
        },
    ]
    return queries


def build_comparison_queries(paper_db):
    """Build 10 pairwise comparison queries using real overlapping-topic papers."""
    queries = [
        {
            "id": "q041",
            "category": "comparison",
            "query": "How do the approaches to knowledge graph embedding (Pattern Over-Generalization paper) and knowledge graph completion for inductive settings (PEARL paper) differ in their methods?",
            "papers": ["2609.03487", "2609.02216"],
        },
        {
            "id": "q042",
            "category": "comparison",
            "query": "Compare the two papers on on-policy distillation: 'RISE: Recursive Improvement via Self-Extrapolating Policy Distillation' and 'What Matters in On-Policy Distillation?'. What are their key differences?",
            "papers": ["2609.05295", "2609.05198"],
        },
        {
            "id": "q043",
            "category": "comparison",
            "query": "How do the two papers on diffusion language models differ in their proposed approaches and applications?",
            "papers": ["2609.04778", "2609.04531"],
        },
        {
            "id": "q044",
            "category": "comparison",
            "query": "Compare the approaches to multimodal analysis in 'SMILE: Self-Explainable Multimodal Information Bottleneck for Medical Diagnosis' and 'From Vision to Language: Investigating Causal Information Flow in Multimodal Decision Making'.",
            "papers": ["2609.05174", "2609.05149"],
        },
        {
            "id": "q045",
            "category": "comparison",
            "query": "How do the papers on counterfactual explanations for GNNs and GNN-based watermarking for ownership verification address different challenges in graph neural network trustworthiness?",
            "papers": ["2609.05113", "2609.04772"],
        },
        {
            "id": "q046",
            "category": "comparison",
            "query": "Compare the two papers on retrieval-augmented generation: context compression (Soft Context Compression paper) and the Qlippy assistant for quantum workflows. What are their different strategies?",
            "papers": ["2609.05152", "2609.05039"],
        },
        {
            "id": "q047",
            "category": "comparison",
            "query": "How do the papers on knowledge graph completion for vulnerability identification (Athena) and scientific hypothesis discovery (HyGRAIL) differ in their use of knowledge graphs?",
            "papers": ["2609.01187", "2609.02056"],
        },
        {
            "id": "q048",
            "category": "comparison",
            "query": "Compare the approaches to transformer analysis in the influence score paper and the transformer compression paper for plant disease detection.",
            "papers": ["2609.05074", "2609.05334"],
        },
        {
            "id": "q049",
            "category": "comparison",
            "query": "How do the two papers on multimodal chain-of-thought reasoning and multimodal instruction-following evaluation differ in their evaluation methodologies?",
            "papers": ["2609.04947", "2609.04859"],
        },
        {
            "id": "q050",
            "category": "comparison",
            "query": "Compare the papers on cooperative multi-agent reinforcement learning change-point detection and reinforcement learning for solar PV policy design. What different RL paradigms do they use?",
            "papers": ["2609.05298", "2609.04880"],
        },
    ]
    return queries


def build_reference_answers(paper_db, all_queries):
    """Build reference answers grounded in actual abstracts."""
    answers = {}

    # Single-hop answers - grounded in individual paper abstracts
    single_hop_answers = {
        "q001": "UniMate is a unified model for animating diverse skeletons, authored by Linzhan Mou, Jiahui Lei, and Zhiyang Dou.",
        "q002": "WearableQA addresses the problem of health reasoning over real-world wearable data by providing a benchmark for evaluating models on this task.",
        "q003": "The paper 'Diffusion TV' is categorized under cs.HC (Human-Computer Interaction) and cs.AI (Artificial Intelligence).",
        "q004": "RegionFed proposes federated learning for personalized query understanding in heterogeneous retail environments.",
        "q005": "ROBORMBENCH evaluates the paraphrase fragility of vision language reward models, testing whether the same trajectory receives the same reward under semantically equivalent paraphrases.",
        "q006": "The paper proposes an approach using behavioural evidence to evaluate whether LLM explanations are necessary or sufficient for their decision-making.",
        "q007": "The paper proposes an influence score to quantify the contribution of attention heads to classification decisions in Transformer-based models for prompt injection detection.",
        "q008": "The paper demonstrates that knowledge graph embedding methods can over-generalize patterns, leading to incorrect link predictions when test patterns differ from training patterns.",
        "q009": "PEARL addresses inductive knowledge graph completion by learning transferable relational and structural patterns to predict missing links involving unseen entities.",
        "q010": "SMILE focuses on self-explainable multimodal information bottleneck approaches for medical diagnosis, combining explainability with multimodal data processing.",
        "q011": "The paper proposes online change-point detection methods for cooperative multi-agent reinforcement learning systems to handle distribution shifts in past experience.",
        "q012": "The paper is titled 'A Robust Watermark-based Fingerprint Framework for GNNs Ownership Verification' and addresses model ownership infringement concerns for graph neural networks.",
        "q013": "MM-IFEval-Pro evaluates instruction-following capabilities of vision-language models across multilingual settings with attack resistance.",
        "q014": "HyGRAIL addresses cost-aware and evidence-grounded scientific hypothesis discovery over knowledge graphs, finding missing typed links that represent plausible hypotheses.",
        "q015": "Athena contributes to vulnerability-affected library identification via knowledge graph completion, addressing the problem of missing or incorrect affected-library entries in vulnerability databases.",
    }

    # Multi-hop answers - grounded in connections between papers
    multi_hop_answers = {
        "q016": "Knowledge graph embedding (KGE) methods project entities and relations into low-dimensional vector spaces for link prediction, while inductive knowledge graph completion focuses on predicting links for entities unseen during training. KGE pattern over-generalization can cause errors when test patterns differ from training, whereas inductive methods like PEARL learn transferable patterns to handle unseen entities.",
        "q017": "Both papers address multimodal feature encoding challenges: multimodal emotion recognition uses multi-feature encoding with attention mechanisms for human-computer interaction, while SMILE applies information bottleneck principles to multimodal medical data for explainable diagnosis. Both require integrating diverse modalities while maintaining interpretability.",
        "q018": "The LLM explanations paper evaluates whether explanations are necessary or sufficient using behavioural evidence, while the attention interpretability paper measures attention head impact through influence scores. Both address transformer interpretability but at different levels: one focuses on output explanations, the other on internal attention mechanisms.",
        "q019": "Both papers propose non-autoregressive alternatives to traditional left-to-right generation: diffusion language models refine tokens through iterative denoising for mobile edge AI, while distilled continuous diffusion models generate code in few steps. They share the goal of parallel generation but target different applications (edge computing vs. code generation).",
        "q020": "The pattern over-generalization paper shows KGE methods can incorrectly predict links when test patterns differ from training, while the uncertain knowledge graph paper addresses initialization challenges when most triples lack confidence scores. Both highlight quality issues in knowledge graphs but from different angles: generalization ability vs. data uncertainty.",
        "q021": "Both papers address GNN trustworthiness: counterfactual explanations determine minimal graph modifications to change model predictions, while watermark frameworks verify model ownership through fingerprinting. They use different techniques (explanation vs. watermarking) but both aim to make GNNs more reliable and accountable.",
        "q022": "Both papers improve post-training efficiency for language models: on-policy distillation provides dense per-token supervision but is bottlenecked by teacher capacity, while RISE uses self-extrapolation to recursively improve policies without relying on teacher models. They address different bottlenecks: data efficiency vs. teacher limitations.",
        "q023": "Both papers address retrieval challenges: soft context compression reduces retrieved context length for RAG efficiency, while Qlippy provides provenance and reproducibility for quantum workflows. They tackle different aspects of knowledge retrieval: compression for efficiency vs. tracking for reproducibility.",
        "q024": "Both papers leverage knowledge graphs for different purposes: Athena completes KGs to identify vulnerable libraries affected by vulnerabilities, while HyGRAIL discovers scientific hypotheses by finding missing typed links. They demonstrate KG versatility for security vs. scientific discovery applications.",
        "q025": "Both papers analyze transformer internals: influence scores measure attention head contributions to classification decisions, while compression techniques reduce model size for plant disease detection. One focuses on interpretability (understanding attention), the other on efficiency (reducing model size), but both study transformer architecture properties.",
        "q026": "Both papers apply graph neural networks to different domains: spatiotemporal GNNs predict air quality from mobile sensing data, while hierarchical GNNs learn mesh-based physics simulations. They share the GNN methodology but target environmental monitoring vs. physics learning applications.",
        "q027": "Both papers extend reasoning across modalities: MCPO uses modality-contrastive preference optimization for multimodal chain-of-thought, while MMTClinic handles multilingual time series question answering. They address different reasoning challenges: chain-of-thought reasoning vs. temporal question answering.",
        "q028": "Both papers address RL challenges differently: solar PV policy design uses RL for sequential decision-making under uncertainty for energy policy, while change-point detection handles distribution shifts in cooperative multi-agent systems. They tackle different RL paradigms: single-agent sequential vs. multi-agent cooperative.",
        "q029": "Both papers use LLMs for specialized domains: LLM-driven quantum circuit synthesis designs quantum circuits using binary decision diagrams, while LLM decompilers recover high-level source code for security tasks. They demonstrate LLM versatility for quantum computing vs. software security applications.",
        "q030": "Both papers address knowledge retrieval: NS-ST-GraphRAG applies neuro-symbolic methods to spatiotemporal literary narratives, while Qlippy provides retrieval-augmented assistance for quantum workflows. They tackle different retrieval challenges: narrative knowledge vs. workflow provenance.",
    }

    # Global answers - grounded in corpus statistics
    global_answers = {
        "q031": "The dominant research themes are machine learning and deep learning (learning: 970 papers, models: 900), natural language processing (language: 593, LLMs: 286), and agent-based systems (agents: 448, agent: 239). Reasoning (364), multimodal AI (226), and benchmarking (227) are also prominent themes.",
        "q032": "cs.AI (4503 papers) is the most frequent category, followed by cs.LG (3623), cs.CL (2199), cs.CV (994), and stat.ML (357). This reveals a research landscape dominated by artificial intelligence, machine learning, computational linguistics, and computer vision.",
        "q033": "The most common methods mentioned in titles include learning (970), models (900), language (593), agents (448), reasoning (364), framework (335), large (310), neural (267), optimization (246), and benchmark (227).",
        "q034": "LLM research (286 papers mentioning LLMs) appears across multiple categories: cs.AI, cs.CL, and cs.LG are the primary venues, with additional representation in cs.CV for multimodal LLMs and cs.CY for societal impacts.",
        "q035": "Benchmarking and evaluation are significant themes: benchmark appears in 227 titles, evaluation in 266. This indicates a strong focus on standardizing assessment methodologies across different AI subfields.",
        "q036": "Main application domains include healthcare (medical diagnosis, health reasoning), robotics (robot policies, trajectory planning), climate science (air quality, weather prediction), security (vulnerability detection, watermarking), and quantum computing.",
        "q037": "Graph-based learning appears frequently: graph appears in 190 titles, with specific applications in graph neural networks, knowledge graphs, and graph-structured data processing across AI, LG, and CV categories.",
        "q038": "Multimodal research (226 papers) is growing across vision-language models, medical diagnosis, emotion recognition, and time series analysis, with strong representation in cs.CV and cs.CL categories.",
        "q039": "Agent-based systems (448 papers) are heavily represented in cs.AI and cs.LG, with applications spanning robotics, reinforcement learning, multi-agent systems, and autonomous decision-making.",
        "q040": "Most active intersection areas include AI-LG (machine learning meets AI), AI-CL (AI meets NLP), LG-CL (ML meets NLP), CV-AI (computer vision meets AI), and LG-CV (ML meets computer vision).",
    }

    # Comparison answers - grounded in paper comparisons
    comparison_answers = {
        "q041": "KGE methods project entities and relations into vector spaces for link prediction but can over-generalize patterns. Inductive KGC methods like PEARL learn transferable patterns to handle unseen entities, addressing the generalization limitation of standard KGE approaches.",
        "q042": "RISE uses self-extrapolation to recursively improve policies without teacher models, while 'What Matters in On-Policy Distillation' analyzes data efficiency and data quality challenges in standard on-policy distillation. RISE addresses teacher bottlenecks, while the other paper focuses on data efficiency.",
        "q043": "The mobile edge paper proposes diffusion language models for on-device agentic AI through iterative denoising, while the code generation paper distills continuous diffusion models to generate code in few steps. They target different applications (edge computing vs. code generation) with similar diffusion-based approaches.",
        "q044": "SMILE applies information bottleneck principles to multimodal medical data for explainable diagnosis, while the causal information flow paper investigates whether multimodal decisions are grounded in visual evidence. They address different aspects: information compression vs. causal grounding.",
        "q045": "Counterfactual explanations determine minimal graph modifications to change predictions, addressing interpretability, while watermark frameworks verify ownership through fingerprinting, addressing intellectual property. They use different techniques for different trustworthiness aspects.",
        "q046": "Soft context compression reduces retrieved context length for RAG efficiency through compression techniques, while Qlippy provides provenance tracking and reproducibility for quantum workflows. They address efficiency vs. reproducibility in retrieval systems.",
        "q047": "Athena completes KGs to identify vulnerable libraries by finding missing affected-library entries, while HyGRAIL discovers scientific hypotheses by finding missing typed links. They demonstrate different KG applications: security vulnerability management vs. scientific discovery.",
        "q048": "The influence score paper measures attention head contributions to classification decisions for interpretability, while the compression paper reduces transformer size for plant disease detection. They study different transformer properties: attention mechanisms vs. model efficiency.",
        "q049": "MCPO uses modality-contrastive preference optimization for multimodal chain-of-thought reasoning, while MM-IFEval-Pro evaluates instruction-following across multilingual settings with attack resistance. They address different evaluation aspects: reasoning quality vs. instruction compliance.",
        "q050": "Change-point detection handles distribution shifts in cooperative multi-agent RL systems, while solar PV policy design uses RL for sequential decision-making under uncertainty for energy policy. They address different RL paradigms: multi-agent adaptation vs. single-agent sequential optimization.",
    }

    # Combine all answers
    answers.update(single_hop_answers)
    answers.update(multi_hop_answers)
    answers.update(global_answers)
    answers.update(comparison_answers)

    return answers


def main():
    """Main function to generate all query files."""
    print("=== Building Benchmark Queries ===")
    print()

    # Load papers
    print("Loading papers from papers.jsonl...")
    paper_db = load_papers()
    print(f"  Loaded {len(paper_db)} papers")
    print()

    # Create queries directory
    QUERIES_DIR.mkdir(parents=True, exist_ok=True)

    # Build queries
    print("Building single_hop queries...")
    single_hop = build_single_hop_queries(paper_db)
    print(f"  Generated {len(single_hop)} queries")

    print("Building multi_hop queries...")
    multi_hop = build_multi_hop_queries(paper_db)
    print(f"  Generated {len(multi_hop)} queries")

    print("Building global queries...")
    global_queries = build_global_queries(paper_db)
    print(f"  Generated {len(global_queries)} queries")

    print("Building comparison queries...")
    comparison = build_comparison_queries(paper_db)
    print(f"  Generated {len(comparison)} queries")

    # Validate paper IDs
    print()
    print("Validating paper IDs...")
    all_paper_ids = []
    for q in single_hop + multi_hop + comparison:
        all_paper_ids.extend(q["papers"])

    missing = [pid for pid in all_paper_ids if pid not in paper_db]
    if missing:
        print(f"  WARNING: {len(missing)} missing paper IDs: {missing}")
    else:
        print(f"  All {len(all_paper_ids)} paper IDs validated successfully")

    # Build reference answers
    print()
    print("Building reference answers...")
    all_queries = single_hop + multi_hop + global_queries + comparison
    reference_answers = build_reference_answers(paper_db, all_queries)
    print(f"  Generated {len(reference_answers)} reference answers")

    # Verify all query IDs have answers
    query_ids = [q["id"] for q in all_queries]
    missing_answers = [qid for qid in query_ids if qid not in reference_answers]
    if missing_answers:
        print(f"  WARNING: Missing answers for {missing_answers}")
    else:
        print(f"  All {len(query_ids)} query IDs have reference answers")

    # Write files
    print()
    print("Writing query files...")

    with open(QUERIES_DIR / "single_hop.json", "w") as f:
        json.dump(single_hop, f, indent=2)
    print(f"  Written single_hop.json ({len(single_hop)} queries)")

    with open(QUERIES_DIR / "multi_hop.json", "w") as f:
        json.dump(multi_hop, f, indent=2)
    print(f"  Written multi_hop.json ({len(multi_hop)} queries)")

    with open(QUERIES_DIR / "global.json", "w") as f:
        json.dump(global_queries, f, indent=2)
    print(f"  Written global.json ({len(global_queries)} queries)")

    with open(QUERIES_DIR / "comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"  Written comparison.json ({len(comparison)} queries)")

    with open(QUERIES_DIR / "reference_answers.json", "w") as f:
        json.dump(reference_answers, f, indent=2)
    print(f"  Written reference_answers.json ({len(reference_answers)} answers)")

    # Summary
    print()
    print("=== Summary ===")
    print(f"Total queries: {len(all_queries)}")
    print(f"  single_hop: {len(single_hop)}")
    print(f"  multi_hop: {len(multi_hop)}")
    print(f"  global: {len(global_queries)}")
    print(f"  comparison: {len(comparison)}")
    print(f"Reference answers: {len(reference_answers)}")
    print(f"All paper IDs validated: {len(missing) == 0}")
    print()
    print(f"Output directory: {QUERIES_DIR}")


if __name__ == "__main__":
    main()
