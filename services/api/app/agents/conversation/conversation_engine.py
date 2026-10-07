from typing import Any, Dict, List, Optional, Tuple
from packages.shared_types.conversation import (
    IntentClassificationResult,
    ObjectionClassification,
    ProspectIntent,
    ReplyObjective,
)
from services.api.app.agents.conversation.conversation_memory import (
    ConversationContext,
    ConversationMemoryManager,
    MessageSummaryItem,
)
from services.api.app.agents.conversation.intent_classifier import IntentClassifier
from services.api.app.agents.conversation.message_analyzer import (
    ReplyMessageAnalyzer,
    ReplyValidationResult,
)
from services.api.app.agents.conversation.objection_handler import ObjectionHandler
from services.api.app.agents.conversation.reply_generator import (
    GeneratedReplyVariant,
    ReplyGenerator,
)
from services.api.app.agents.conversation.reply_strategy import (
    ReplyStrategy,
    ReplyStrategyEngine,
)
from services.api.app.agents.conversation.validators import sanitize_inbound_message


class ConversationAnalysisResult:
    def __init__(
        self,
        sanitized_content: str,
        intent: IntentClassificationResult,
        objection: Optional[ObjectionClassification],
        strategy: ReplyStrategy,
        reply_variants: List[GeneratedReplyVariant],
        validation_results: List[ReplyValidationResult],
        updated_summary: str,
    ):
        self.sanitized_content = sanitized_content
        self.intent = intent
        self.objection = objection
        self.strategy = strategy
        self.reply_variants = reply_variants
        self.validation_results = validation_results
        self.updated_summary = updated_summary


class ConversationEngine:
    """
    Central orchestrator for Conversation Intelligence:
    Sanitizes inbound message -> Classifies Intent -> Detects Objections ->
    Updates Memory -> Formulates Strategy -> Generates Replies -> Validates Drafts.
    """

    @classmethod
    def process_inbound_message(
        cls,
        raw_message: str,
        channel: str,
        context: ConversationContext,
    ) -> ConversationAnalysisResult:
        # 1. Sanitize inbound message (neutralize prompt injections)
        sanitized_content = sanitize_inbound_message(raw_message)

        # 2. Classify intent
        intent_res = IntentClassifier.classify(sanitized_content)

        # 3. Detect objections
        objection_res = ObjectionHandler.evaluate(sanitized_content)

        # 4. Update rolling conversation summary
        new_item = MessageSummaryItem(
            direction="INBOUND",
            author_type="PROSPECT",
            content=sanitized_content,
        )
        updated_summary = ConversationMemoryManager.generate_rolling_summary(
            existing_summary=context.current_summary,
            new_messages=[new_item],
        )

        # 5. Formulate reply strategy
        strategy = ReplyStrategyEngine.determine(
            intent=intent_res.intent,
            objection=objection_res,
            context=context,
        )

        # 6. Generate reply variants
        reply_variants = ReplyGenerator.generate_replies(
            strategy=strategy,
            intent=intent_res.intent,
            latest_message=sanitized_content,
            context=context,
            channel=channel,
        )

        # 7. Validate generated reply variants
        validation_results: List[ReplyValidationResult] = []
        for variant in reply_variants:
            val_res = ReplyMessageAnalyzer.analyze(
                reply_body=variant.body,
                channel=channel,
                prospect_name=context.contact_handle or "there",
                service_name=context.recommended_service or "Custom Web Development",
                intent_name=intent_res.intent.value,
            )
            variant.quality_score = val_res.quality_score
            variant.risk_flags = val_res.risk_flags
            validation_results.append(val_res)

        return ConversationAnalysisResult(
            sanitized_content=sanitized_content,
            intent=intent_res,
            objection=objection_res,
            strategy=strategy,
            reply_variants=reply_variants,
            validation_results=validation_results,
            updated_summary=updated_summary,
        )
