from typing import Any, Callable, Dict, Optional, Type
from pydantic import BaseModel, Field

from packages.shared_types.agent import ToolPermissionLevel, ToolRiskLevel


class ToolDefinition(BaseModel):
    """Declarative definition of a controlled browser agent tool."""
    name: str
    description: str
    risk_level: ToolRiskLevel
    permission_level: ToolPermissionLevel
    requires_approval: bool = False
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None


# --- Tool Input Schemas ---

class OpenPageInput(BaseModel):
    url: str = Field(..., description="Target HTTP/HTTPS URL to open")


class NavigateInput(BaseModel):
    direction: str = Field(..., description="'back', 'forward', or 'reload'")


class ReadPageInput(BaseModel):
    max_length: int = Field(default=5000, description="Max characters to return from visible text")


class FindTextInput(BaseModel):
    query: str = Field(..., min_length=1, description="Text string or pattern to find")


class ScrollInput(BaseModel):
    direction: str = Field(default="down", description="'down' or 'up'")
    amount: int = Field(default=500, description="Pixel scroll distance")


class ClickInput(BaseModel):
    selector: Optional[str] = Field(None, description="CSS selector of element to click")
    text: Optional[str] = Field(None, description="Exact visible text of element to click")


class ExtractContentInput(BaseModel):
    include_links: bool = Field(default=True, description="Whether to extract outbound links")


class ExtractLinksInput(BaseModel):
    filter_pattern: Optional[str] = Field(None, description="Optional regex or substring to filter hrefs")


class RequestApprovalInput(BaseModel):
    action_type: str = Field(..., description="'COMMENT', 'DM', or 'EMAIL'")
    recipient: Optional[str] = Field(None, description="Target profile handle or URL")
    content: str = Field(..., min_length=1, description="Proposed message or comment text")


# --- Tool Registry ---

class BrowserToolRegistry:
    """Central registry of verified browser tools with risk & permission boundaries."""

    _tools: Dict[str, ToolDefinition] = {}

    @classmethod
    def register(cls, tool: ToolDefinition) -> None:
        cls._tools[tool.name] = tool

    @classmethod
    def get(cls, name: str) -> Optional[ToolDefinition]:
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> Dict[str, ToolDefinition]:
        return dict(cls._tools)

    @classmethod
    def is_valid_tool(cls, name: str) -> bool:
        return name in cls._tools

    @classmethod
    def requires_approval(cls, name: str) -> bool:
        tool = cls.get(name)
        return tool.requires_approval if tool else False


# Register default controlled browser tools
_DEFAULT_TOOLS = [
    ToolDefinition(
        name="open_page",
        description="Navigate the browser tab to a specified public URL.",
        risk_level=ToolRiskLevel.LOW,
        permission_level=ToolPermissionLevel.READ_ONLY,
        requires_approval=False,
        input_schema=OpenPageInput.model_json_schema(),
    ),
    ToolDefinition(
        name="navigate",
        description="Control browser history: back, forward, or reload.",
        risk_level=ToolRiskLevel.LOW,
        permission_level=ToolPermissionLevel.READ_ONLY,
        requires_approval=False,
        input_schema=NavigateInput.model_json_schema(),
    ),
    ToolDefinition(
        name="read_page",
        description="Extract visible readable text and structure from active webpage.",
        risk_level=ToolRiskLevel.LOW,
        permission_level=ToolPermissionLevel.READ_ONLY,
        requires_approval=False,
        input_schema=ReadPageInput.model_json_schema(),
    ),
    ToolDefinition(
        name="find_text",
        description="Search for specific keywords, phrases, or buying signals in page.",
        risk_level=ToolRiskLevel.LOW,
        permission_level=ToolPermissionLevel.READ_ONLY,
        requires_approval=False,
        input_schema=FindTextInput.model_json_schema(),
    ),
    ToolDefinition(
        name="scroll",
        description="Scroll page up or down to inspect content incrementally.",
        risk_level=ToolRiskLevel.LOW,
        permission_level=ToolPermissionLevel.READ_ONLY,
        requires_approval=False,
        input_schema=ScrollInput.model_json_schema(),
    ),
    ToolDefinition(
        name="click",
        description="Click a visible public link, button, or profile element.",
        risk_level=ToolRiskLevel.MEDIUM,
        permission_level=ToolPermissionLevel.USER_INTERACTION,
        requires_approval=False,
        input_schema=ClickInput.model_json_schema(),
    ),
    ToolDefinition(
        name="extract_visible_content",
        description="Extract structured text, profile bio, website links, or post caption.",
        risk_level=ToolRiskLevel.LOW,
        permission_level=ToolPermissionLevel.READ_ONLY,
        requires_approval=False,
        input_schema=ExtractContentInput.model_json_schema(),
    ),
    ToolDefinition(
        name="extract_links",
        description="Extract external website links from the current visible document.",
        risk_level=ToolRiskLevel.LOW,
        permission_level=ToolPermissionLevel.READ_ONLY,
        requires_approval=False,
        input_schema=ExtractLinksInput.model_json_schema(),
    ),
    ToolDefinition(
        name="request_user_approval",
        description="Submit an outbound message or comment for human approval before execution.",
        risk_level=ToolRiskLevel.HIGH,
        permission_level=ToolPermissionLevel.SENSITIVE_ACTION,
        requires_approval=True,
        input_schema=RequestApprovalInput.model_json_schema(),
    ),
]

for t in _DEFAULT_TOOLS:
    BrowserToolRegistry.register(t)
