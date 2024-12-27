"""
File structure
- ___init__.py: the entrance/agent of coder
- evaluator.py
- conf.py
- exp.py: everything under the experiment, e.g.
    - Task
    - Experiment
    - Workspace
- test.py
    - Each coder could be tested.
"""

import json

from rdagent.components.coder.CoSTEER import CoSTEER
from rdagent.components.coder.CoSTEER.config import CoSTEER_SETTINGS
from rdagent.components.coder.CoSTEER.evaluators import CoSTEERMultiEvaluator
from rdagent.components.coder.CoSTEER.evolving_strategy import (
    MultiProcessEvolvingStrategy,
)
from rdagent.components.coder.CoSTEER.knowledge_management import (
    CoSTEERQueriedKnowledge,
)
from rdagent.components.coder.data_science.ensemble.eval import EnsembleCoSTEEREvaluator
from rdagent.components.coder.data_science.ensemble.exp import EnsembleTask
from rdagent.core.experiment import FBWorkspace
from rdagent.core.scenario import Scenario
from rdagent.oai.llm_utils import APIBackend
from rdagent.utils.agent.tpl import T


class EnsembleMultiProcessEvolvingStrategy(MultiProcessEvolvingStrategy):
    def implement_one_task(
        self,
        target_task: EnsembleTask,
        queried_knowledge: CoSTEERQueriedKnowledge | None = None,
        workspace: FBWorkspace | None = None,
    ) -> dict[str, str]:
        # Get task information for knowledge querying
        ensemble_information_str = target_task.get_task_information()

        # Query knowledge
        queried_similar_successful_knowledge = (
            queried_knowledge.task_to_similar_task_successful_knowledge[ensemble_information_str]
            if queried_knowledge is not None
            else []
        )
        queried_former_failed_knowledge = (
            queried_knowledge.task_to_former_failed_traces[ensemble_information_str]
            if queried_knowledge is not None
            else []
        )

        # Generate code with knowledge integration
        competition_info = self.scen.get_scenario_all_desc()
        system_prompt = T(".prompts:ensemble_coder.system").r(
            competition_info=competition_info,
            queried_similar_successful_knowledge=queried_similar_successful_knowledge,
            queried_former_failed_knowledge=(
                queried_former_failed_knowledge[0] if queried_former_failed_knowledge else None
            ),
        )
        user_prompt = T(".prompts:ensemble_coder.user").r(ensemble_spec=workspace.file_dict["spec/ensemble.md"])

        ensemble_code = json.loads(
            APIBackend().build_messages_and_create_chat_completion(
                user_prompt=user_prompt, system_prompt=system_prompt, json_mode=True
            )
        )["code"]

        return {
            "ensemble.py": ensemble_code,
        }

    def assign_code_list_to_evo(self, code_list: list[dict[str, str]], evo):
        """
        Assign the code list to the evolving item.

        The code list is aligned with the evolving item's sub-tasks.
        If a task is not implemented, put a None in the list.
        """
        for index in range(len(evo.sub_tasks)):
            if code_list[index] is None:
                continue
            if evo.sub_workspace_list[index] is None:
                # evo.sub_workspace_list[index] = FBWorkspace(target_task=evo.sub_tasks[index])
                evo.sub_workspace_list[index] = evo.experiment_workspace
            evo.sub_workspace_list[index].inject_files(**code_list[index])
        return evo


class EnsembleCoSTEER(CoSTEER):
    def __init__(
        self,
        scen: Scenario,
        *args,
        **kwargs,
    ) -> None:
        eva = CoSTEERMultiEvaluator(EnsembleCoSTEEREvaluator(scen=scen), scen=scen)
        es = EnsembleMultiProcessEvolvingStrategy(scen=scen, settings=CoSTEER_SETTINGS)

        super().__init__(*args, settings=CoSTEER_SETTINGS, eva=eva, es=es, evolving_version=2, scen=scen, **kwargs)