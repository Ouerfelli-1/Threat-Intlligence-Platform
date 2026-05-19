# Ported from AvailableServices/Flowviz/flowviz-main/src/features/flow-analysis/types/attack-flow.ts
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class FlowNode(BaseModel):
    id: str
    type: str
    data: dict[str, Any]


class FlowEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str = "floating"
    label: str


class FlowOutput(BaseModel):
    nodes: list[FlowNode]
    edges: list[FlowEdge]


class FlowRequest(BaseModel):
    input: str
    system: str | None = None
    # Optional per-request model override (LiteLLM-format, e.g. "github/gpt-4o").
    # When set, flowviz spins up a one-off client with this model instead of
    # using its global default. Threat-intel uses this to route attack-flow
    # generation through the same smart-tier model that produced the hunting
    # hypothesis, so all three pieces of the threat insight share a quota pool
    # with enough headroom (gpt-4o-mini's free daily quota chokes on 4K-token
    # attack flows).
    model: str | None = None


class FlowOut(BaseModel):
    id: uuid.UUID
    input_hash: str
    output: FlowOutput
    model_name: str
    generated_at: datetime

    model_config = {"from_attributes": True}
