const MODEL_LINEAGE = {
  project: "LSC / MHLM model-lineage archive",
  date: "2026-05-01",
  status: "experimental core",
  tags: ["#LuciferSun", "#Codex", "#FlameBornLLC"],
  mission:
    "Archive how different AI systems changed, corrected, amplified, or constrained the LSC theory line, then simulate when model agreement looks like understanding versus when it may be correlated hallucination.",
  models: [
    {
      id: "gpt",
      name: "GPT",
      phase: "LSC 5.0@",
      role: "Synthesis and narrative reframing",
      contribution:
        "Moved the anomaly explanation away from PBH-centered language and toward detector-side relativistic energy misestimation.",
      strengthened: "A small reconstruction shift can be amplified into an observed rate deficit.",
      weakened: "Direct reliance on dark-neutrino or PBH-centric explanation as the main mechanism.",
      decision_style: "Generative synthesis",
      stance: "constructive",
      validation_status: "historical, source-backed, not validation",
      scores: {
        novelty: 0.82,
        conservatism: 0.34,
        validation_pressure: 0.38,
        hallucination_risk: 0.68,
        coherence: 0.76,
        disagreement: 0.42
      }
    },
    {
      id: "manus",
      name: "Manus",
      phase: "LSC 5.5",
      role: "Integration, redaction, and package cleanup",
      contribution:
        "Merged the LSC 4.2 propagation line and LSC 5.0 detector line into one preprint-oriented framework.",
      strengthened: "The unified model can be treated as one effective propagation-plus-detection framework.",
      weakened: "Mandatory dark-neutrino centrality.",
      decision_style: "Integrator",
      stance: "constructive",
      validation_status: "historical, source-backed, stronger packaging than validation",
      scores: {
        novelty: 0.67,
        conservatism: 0.45,
        validation_pressure: 0.44,
        hallucination_risk: 0.58,
        coherence: 0.83,
        disagreement: 0.36
      }
    },
    {
      id: "gemini",
      name: "Gemini",
      phase: "LSC 6.2.0",
      role: "Literature-style review, gap analysis, conservative reframing",
      contribution:
        "Forced explicit separation of true energy and reconstructed energy, sharpened uncertainty language, and named missing tests.",
      strengthened: "The detector tensor must be treated as a testable ansatz, not a validated mechanism.",
      weakened: "Any implication that anchor fits alone establish predictive success.",
      decision_style: "Conservative reviewer",
      stance: "corrective",
      validation_status: "historical and source-backed review layer, not validation",
      scores: {
        novelty: 0.48,
        conservatism: 0.78,
        validation_pressure: 0.82,
        hallucination_risk: 0.34,
        coherence: 0.79,
        disagreement: 0.55
      }
    },
    {
      id: "codex",
      name: "Codex",
      phase: "LSC 6.2.1",
      role: "Reproducible analysis, fit diagnostics, leave-one-out validation",
      contribution:
        "Built the reproducible 6.2.1 continuation analysis, exposed exact anchor fits, and showed weak leave-one-out stability.",
      strengthened: "The model must be judged by predictive stability, not only by fit to anchor points.",
      weakened: "Any claim that exact anchor fits imply confirmation.",
      decision_style: "Reproducibility engineer",
      stance: "validation-critical",
      validation_status: "strongest validation-layer result in the archive",
      scores: {
        novelty: 0.42,
        conservatism: 0.84,
        validation_pressure: 0.91,
        hallucination_risk: 0.22,
        coherence: 0.72,
        disagreement: 0.63
      }
    },
    {
      id: "deepseek",
      name: "DeepSeek",
      phase: "LSC 6.2.0 review slot",
      role: "Formal consistency review",
      contribution:
        "Identified dimension, tensor-average, and frame-definition problems that must be fixed before defense.",
      strengthened: "The theory needs a dimensionally consistent detector term, fixed sidereal frame, and experiment-specific likelihoods.",
      weakened: "Defense-oriented presentation before formal repair.",
      decision_style: "Adversarial formal reviewer",
      stance: "critical",
      validation_status: "source-backed critique, not validation",
      scores: {
        novelty: 0.36,
        conservatism: 0.9,
        validation_pressure: 0.95,
        hallucination_risk: 0.18,
        coherence: 0.69,
        disagreement: 0.74
      }
    },
    {
      id: "lsc622",
      name: "LSC 6.2.2 correction layer",
      phase: "LSC 6.2.2",
      role: "Formal repair and deterministic simulation layer",
      contribution:
        "Separated isotropic trace from traceless anisotropy, removed ambiguous detector scaling, and added deterministic simulation outputs.",
      strengthened: "A repair path exists, but it is not physics validation.",
      weakened: "The earlier mixed detector scaling and unclear anisotropy averaging.",
      decision_style: "Repair synthesis",
      stance: "corrective",
      validation_status: "formal repair, not validation",
      scores: {
        novelty: 0.55,
        conservatism: 0.76,
        validation_pressure: 0.86,
        hallucination_risk: 0.28,
        coherence: 0.81,
        disagreement: 0.49
      }
    }
  ]
};
