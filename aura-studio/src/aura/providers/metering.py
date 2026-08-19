"""Cost metering and tool gating.

CostMeter wraps the provider protocols and charges a static per-call price
into the run's budget (exact accounting comes from Langfuse traces in
production; this table is the *governor*, not the invoice). ToolBelt is the
façade handed to each spawned agent task: it exposes only the tools the
role is allowed, and refuses expensive calls once the budget is exhausted.
"""

from __future__ import annotations

from typing import Callable

from aura.config import Providers
from aura.planning.schemas import AgentRole, RunBudget

# Static per-call prices (USD) — deliberately conservative overestimates.
PRICES = {
    "llm": 0.03,
    "judge": 0.15,
    "image_gen": 0.08,
    "video_gen": 1.50,
    "renderer": 0.0,
}


class BudgetExceeded(RuntimeError):
    pass


class ToolNotAllowed(RuntimeError):
    pass


class ToolBelt:
    """What a spawned agent may touch: role-gated, budget-metered providers."""

    def __init__(self, providers: Providers, role: AgentRole, budget: RunBudget,
                 on_spend: Callable[[float, str], None] | None = None):
        self._p = providers
        self._role = role
        self._budget = budget
        self._on_spend = on_spend

    def _charge(self, tool: str) -> None:
        if tool not in self._role.allowed_tools and tool != "judge":
            raise ToolNotAllowed(f"role {self._role.role_key!r} may not use {tool!r}")
        price = PRICES[tool]
        if price > 0 and self._budget.remaining_usd < price:
            raise BudgetExceeded(
                f"budget exhausted (${self._budget.spent_usd:.2f}/"
                f"${self._budget.cap_usd:.2f}) before {tool} call")
        self._budget.spent_usd += price
        if self._on_spend:
            self._on_spend(price, tool)

    @property
    def llm(self):
        belt = self

        class _Metered:
            async def structured(self, **kwargs):
                belt._charge("judge" if belt._role.uses_judge_model else "llm")
                provider = belt._p.judge if belt._role.uses_judge_model else belt._p.llm
                return await provider.structured(**kwargs)

        return _Metered()

    @property
    def image_gen(self):
        belt = self

        class _Metered:
            async def generate(self, **kwargs):
                belt._charge("image_gen")
                return await belt._p.image_gen.generate(**kwargs)

        return _Metered()

    @property
    def video_gen(self):
        belt = self

        class _Metered:
            async def generate(self, **kwargs):
                belt._charge("video_gen")
                return await belt._p.video_gen.generate(**kwargs)

        return _Metered()

    @property
    def renderer(self):
        return self._p.renderer  # deterministic and free — never gated

    def metered_providers(self) -> Providers:
        """A Providers view with metering applied, for code paths (like the
        render executor) that expect the plain Providers shape."""
        return Providers(llm=self.llm, judge=self.llm, image_gen=self.image_gen,
                         video_gen=self.video_gen, renderer=self.renderer)
