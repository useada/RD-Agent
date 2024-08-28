import json
from pathlib import Path
from typing import List, Tuple

from jinja2 import Environment, StrictUndefined

from rdagent.components.coder.factor_coder.factor import FactorExperiment, FactorTask
from rdagent.components.proposal.factor_proposal import (
    FactorHypothesis,
    FactorHypothesis2Experiment,
    FactorHypothesisGen,
)
from rdagent.core.prompts import Prompts
from rdagent.core.proposal import Hypothesis, Scenario, Trace
from rdagent.scenarios.kaggle_feature.experiment.feature_experiment import FEFeatureExperiment

prompt_dict = Prompts(file_path=Path(__file__).parent.parent / "prompts.yaml")

KGFeatureHypothesis = FactorHypothesis


class KGFeatureHypothesisGen(FactorHypothesisGen):
    def __init__(self, scen: Scenario) -> Tuple[dict, bool]:
        super().__init__(scen)

    def prepare_context(self, trace: Trace) -> Tuple[dict, bool]:
        hypothesis_feedback = (
            Environment(undefined=StrictUndefined)
            .from_string(prompt_dict["hypothesis_and_feedback"])
            .render(trace=trace)
        )
        context_dict = {
            "hypothesis_and_feedback": hypothesis_feedback,
            "RAG": "",
            "hypothesis_output_format": prompt_dict["hypothesis_output_format"],
            "hypothesis_specification": "...",
        }
        return context_dict, True

    def convert_response(self, response: str) -> FactorHypothesis:
        response_dict = json.loads(response)
        hypothesis = KGFeatureHypothesis(
            hypothesis=response_dict["hypothesis"],
            reason=response_dict["reason"],
            concise_reason=response_dict["concise_reason"],
            concise_observation=response_dict["concise_observation"],
            concise_justification=response_dict["concise_justification"],
            concise_knowledge=response_dict["concise_knowledge"],
        )
        return hypothesis


class KGModelHypothesis2Experiment(FactorHypothesis2Experiment):
    def prepare_context(self, hypothesis: Hypothesis, trace: Trace) -> Tuple[dict, bool]:
        scenario = trace.scen.get_scenario_all_desc()
        experiment_output_format = prompt_dict["model_experiment_output_format"]

        hypothesis_and_feedback = (
            Environment(undefined=StrictUndefined)
            .from_string(prompt_dict["hypothesis_and_feedback"])
            .render(trace=trace)
        )

        experiment_list: List[FactorExperiment] = [t[1] for t in trace.hist]

        model_list = []
        for experiment in experiment_list:
            model_list.extend(experiment.sub_tasks)

        return {
            "target_hypothesis": str(hypothesis),
            "scenario": scenario,
            "hypothesis_and_feedback": hypothesis_and_feedback,
            "experiment_output_format": experiment_output_format,
            "target_list": model_list,
            "RAG": ...,
        }, True

    def convert_response(self, response: str, trace: Trace) -> FactorExperiment:
        response_dict = json.loads(response)
        tasks = []
        for model_name in response_dict:
            description = response_dict[model_name]["description"]
            formulation = response_dict[model_name]["formulation"]
            architecture = response_dict[model_name]["architecture"]
            variables = response_dict[model_name]["variables"]
            hyperparameters = response_dict[model_name]["hyperparameters"]
            model_type = response_dict[model_name]["model_type"]
            tasks.append(
                FactorTask(model_name, description, formulation, architecture, variables, hyperparameters, model_type)
            )
        exp = FEFeatureExperiment(tasks)
        exp.based_experiments = [t[1] for t in trace.hist if t[2]]
        return exp