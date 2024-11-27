"""
Model workflow with session control
It is from `rdagent/app/qlib_rd_loop/model.py` and try to replace `rdagent/app/qlib_rd_loop/RDAgent.py`
"""

from typing import Any

from rdagent.components.workflow.conf import BasePropSetting
from rdagent.core.developer import Developer
from rdagent.core.proposal import (
    Experiment2Feedback,
    Hypothesis,
    Hypothesis2Experiment,
    HypothesisGen,
    Trace,
)
from rdagent.core.scenario import Scenario
from rdagent.core.utils import import_class
from rdagent.log import rdagent_logger as logger
from rdagent.log.time import measure_time
from rdagent.utils.workflow import LoopBase, LoopMeta


class NextLoopException(Exception):
    """TODO: should we place in in rdagent/core/exception.py?"""

    pass


class RDLoop(LoopBase, metaclass=LoopMeta):

    @measure_time
    def __init__(self, PROP_SETTING: BasePropSetting):
        with logger.tag("init"):
            scen: Scenario = import_class(PROP_SETTING.scen)()
            logger.log_object(scen, tag="scenario")

            self.hypothesis_gen: HypothesisGen = import_class(PROP_SETTING.hypothesis_gen)(scen)
            logger.log_object(self.hypothesis_gen, tag="hypothesis generator")

            self.hypothesis2experiment: Hypothesis2Experiment = import_class(PROP_SETTING.hypothesis2experiment)()
            logger.log_object(self.hypothesis2experiment, tag="hypothesis2experiment")

            self.coder: Developer = import_class(PROP_SETTING.coder)(scen)
            logger.log_object(self.coder, tag="coder")
            self.runner: Developer = import_class(PROP_SETTING.runner)(scen)
            logger.log_object(self.runner, tag="runner")

            self.summarizer: Experiment2Feedback = import_class(PROP_SETTING.summarizer)(scen)
            logger.log_object(self.summarizer, tag="summarizer")
            self.trace = Trace(scen=scen)
            super().__init__()

    # excluded steps
    @measure_time
    def _propose(self):
        hypothesis = self.hypothesis_gen.gen(self.trace)
        logger.log_object(hypothesis, tag="hypothesis generation")
        return hypothesis

    @measure_time
    def _exp_gen(self, hypothesis: Hypothesis):
        exp = self.hypothesis2experiment.convert(hypothesis, self.trace)
        logger.log_object(exp.sub_tasks, tag="experiment generation")
        return exp

    # included steps
    @measure_time
    def direct_exp_gen(self, prev_out: dict[str, Any]):
        with logger.tag("r"):  # research
            hypo = self._propose()
            exp = self._exp_gen(hypo)
        return {"propose": hypo, "exp_gen": exp}

    @measure_time
    def coding(self, prev_out: dict[str, Any]):
        with logger.tag("d"):  # develop
            exp = self.coder.develop(prev_out["direct_exp_gen"]["exp_gen"])
            logger.log_object(exp.sub_workspace_list, tag="coder result")
        return exp

    @measure_time
    def running(self, prev_out: dict[str, Any]):
        with logger.tag("ef"):  # evaluate and feedback
            exp = self.runner.develop(prev_out["coding"])
            logger.log_object(exp, tag="runner result")
        return exp

    @measure_time
    def feedback(self, prev_out: dict[str, Any]):
        feedback = self.summarizer.generate_feedback(
            prev_out["running"], prev_out["direct_exp_gen"]["propose"], self.trace
        )
        with logger.tag("ef"):  # evaluate and feedback
            logger.log_object(feedback, tag="feedback")
        self.trace.hist.append((prev_out["direct_exp_gen"]["propose"], prev_out["running"], feedback))
